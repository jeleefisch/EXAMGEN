"""OMR feasibility spike: read a phone photo of an ExamGen answer sheet.

Standalone (no Django). Pipeline:
  1. find the 4 black corner markers
  2. straighten the page with a perspective transform (markers -> known positions)
  3. read the QR code (this also tells us if the photo is upside down / rotated)
  4. measure how dark each bubble is, normalised for lighting
  5. decide per item: selected / blank / multiple / ambiguous  (never guess)

All positions come from core/sheet_layout.py. Run:
    python -m spike.omr_spike photo.jpg --items 40 --tf 7,14 --debug out.png
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field

import cv2
import numpy as np

from core import sheet_layout as L

DPI = 150
SCALE = DPI / 72.0
WARP_W = int(round(L.PAGE_W * SCALE))
WARP_H = int(round(L.PAGE_H * SCALE))

# Decision thresholds are RELATIVE to this sheet's own "fully shaded" level (see _learn_levels).
T_MARK = 0.50    # ratio at/above this counts as a mark
T_FAINT = 0.20   # between T_FAINT and T_MARK is "faint": needs review
MIN_SPAN = 0.15  # floor on (full-ink level - empty level), protects against dividing noise
INNER = 0.62     # measure the inner 62% of the bubble radius (avoids the printed ring)


class OMRError(Exception):
    """The sheet could not be read at all (for example, markers not found)."""


@dataclass
class ItemResult:
    item: int
    status: str            # selected | blank | multiple | ambiguous
    answer: str | None     # the letter when status == "selected"
    marked: list = field(default_factory=list)
    faint: list = field(default_factory=list)
    ratios: list = field(default_factory=list)
    scores: list = field(default_factory=list)


@dataclass
class SheetResult:
    qr_ok: bool
    version_code: str | None
    serial: int | None
    rotation_steps: int
    items: list
    stats: dict
    warnings: list
    warped: np.ndarray | None = None


# ------------------------------------------------------------------ step 1
def find_marker_centers(gray: np.ndarray):
    """Return the 4 marker centres in image order [TL, TR, BR, BL] (full-res pixels)."""
    h, w = gray.shape
    f = 1600.0 / max(h, w) if max(h, w) > 1600 else 1.0
    small = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f != 1.0 else gray
    sh, sw = small.shape
    blur = cv2.GaussianBlur(small, (5, 5), 0)
    block = int(0.12 * min(sh, sw)) | 1
    bw = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, block, 12)
    contours, _ = cv2.findContours(bw, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    img_area = sh * sw
    cands = []
    for c in contours:
        area = cv2.contourArea(c)
        if not (0.00005 * img_area <= area <= 0.004 * img_area):
            continue
        (cx, cy), (rw, rh), _ = cv2.minAreaRect(c)
        if min(rw, rh) < 1 or min(rw, rh) / max(rw, rh) < 0.6:
            continue
        if area / (rw * rh) < 0.8:   # solid square, not a ring or a letter
            continue
        m = cv2.moments(c)
        if m["m00"] == 0:
            continue
        cands.append((m["m10"] / m["m00"], m["m01"] / m["m00"], area))
    if len(cands) < 4:
        raise OMRError(f"Found only {len(cands)} marker-like squares (need 4). "
                       "Retake the photo with all four black corner squares visible.")
    pts = np.array([(x, y) for x, y, _ in cands])
    s, d = pts[:, 0] + pts[:, 1], pts[:, 0] - pts[:, 1]
    tl, br, tr, bl = pts[np.argmin(s)], pts[np.argmax(s)], pts[np.argmax(d)], pts[np.argmin(d)]
    chosen = [tl, tr, br, bl]
    if len({tuple(p) for p in chosen}) < 4:
        raise OMRError("Corner markers are not distinct. Retake the photo.")
    areas = [a for (x, y, a) in cands if any(abs(x - p[0]) < 1e-6 and abs(y - p[1]) < 1e-6 for p in chosen)]
    if max(areas) / min(areas) > 3.0:
        raise OMRError("The four corner squares look inconsistent in size. Retake the photo.")
    return [(float(p[0] / f), float(p[1] / f)) for p in chosen]


def _page_marker_pixels():
    """Expected marker centres in the straightened image, order [TL, TR, BR, BL]."""
    m = L.markers()  # [BL, BR, TL, TR] in PDF points
    order = [m[2], m[3], m[1], m[0]]
    return [L.to_pixel(r.x + r.w / 2, r.y + r.h / 2, SCALE) for r in order]


# ------------------------------------------------------------------ step 3
def _qr_variants(crop):
    yield crop
    _, otsu = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield otsu
    blur = cv2.GaussianBlur(crop, (0, 0), 2.0)
    yield cv2.addWeighted(crop, 1.8, blur, -0.8, 0)          # sharpen


def qr_crop(gray: np.ndarray, m: np.ndarray, upscale: float = 2.0) -> np.ndarray:
    """Cut the QR area straight from the ORIGINAL photo at higher resolution.

    m maps original photo pixels -> the straightened 150 dpi page. Warping only this small
    area (instead of reusing the straightened page) avoids losing detail twice.
    """
    q, pad = L.qr_box(), 14.0
    x0, y1 = L.to_pixel(q.x - pad, q.y - pad, SCALE)
    x1, y0 = L.to_pixel(q.x + q.w + pad, q.y + q.h + pad, SCALE)
    scale = np.diag([upscale, upscale, 1.0])
    shift = np.array([[1, 0, -x0 * upscale], [0, 1, -y0 * upscale], [0, 0, 1.0]])
    size = (int((x1 - x0) * upscale), int((y1 - y0) * upscale))
    return cv2.warpPerspective(gray, shift @ scale @ m, size, flags=cv2.INTER_CUBIC, borderValue=255)


def read_qr(crop: np.ndarray):
    """Return (version_code, serial) or None. The CRC in the payload rejects misreads."""
    detectors = [cv2.QRCodeDetector()]
    if hasattr(cv2, "QRCodeDetectorAruco"):
        detectors.append(cv2.QRCodeDetectorAruco())
    for img in _qr_variants(crop):
        for det in detectors:
            try:
                text, _, _ = det.detectAndDecode(img)
            except cv2.error:
                continue
            decoded = L.decode_payload(text)
            if decoded:
                return decoded
    return None


# ------------------------------------------------------------------ step 4
def darkness_map(warped_gray: np.ndarray) -> np.ndarray:
    """0 = paper white, 1 = black ink, corrected for uneven lighting."""
    k = int(round(2.4 * 2 * L.BUBBLE_R * SCALE)) | 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    bg = cv2.morphologyEx(warped_gray, cv2.MORPH_CLOSE, kernel)   # removes ink smaller than k
    bg = cv2.GaussianBlur(bg, (0, 0), k / 4).astype(np.float32)
    norm = np.clip(warped_gray.astype(np.float32) / np.maximum(bg, 1.0), 0.0, 1.0)
    return 1.0 - norm


def _disc(radius):
    yy, xx = np.mgrid[-radius:radius + 1, -radius:radius + 1]
    return (xx * xx + yy * yy) <= radius * radius


def bubble_scores(dark: np.ndarray, bubbles) -> list:
    r = max(2, int(round(INNER * L.BUBBLE_R * SCALE)))
    mask = _disc(r)
    out = []
    for b in bubbles:
        cx, cy = L.to_pixel(b.cx, b.cy, SCALE)
        cx, cy = int(round(cx)), int(round(cy))
        patch = dark[cy - r:cy + r + 1, cx - r:cx + r + 1]
        out.append(float(patch[mask].mean()) if patch.shape == mask.shape else 0.0)
    return out


def ring_score(dark: np.ndarray, bubbles) -> float:
    """How well the printed bubble rings line up with this orientation (about 0 if wrong).

    For each bubble: mean darkness ON the ring minus mean darkness just OUTSIDE it.
    """
    ang = np.linspace(0, 2 * np.pi, 16, endpoint=False)
    r_in = L.BUBBLE_R * SCALE
    h, w = dark.shape
    vals = []
    for b in bubbles:
        cx, cy = L.to_pixel(b.cx, b.cy, SCALE)
        xi = np.clip(np.rint(cx + r_in * np.cos(ang)).astype(int), 0, w - 1)
        yi = np.clip(np.rint(cy + r_in * np.sin(ang)).astype(int), 0, h - 1)
        xo = np.clip(np.rint(cx + (r_in + 7) * np.cos(ang)).astype(int), 0, w - 1)
        yo = np.clip(np.rint(cy + (r_in + 7) * np.sin(ang)).astype(int), 0, h - 1)
        vals.append(dark[yi, xi].mean() - dark[yo, xo].mean())
    return float(np.mean(vals))


def _learn_levels(scores: np.ndarray):
    """Learn this sheet's empty-bubble level E, noise sigma and full-ink level F."""
    e = float(np.percentile(scores, 20))
    low = scores[scores <= np.median(scores)]
    sigma = float(1.4826 * np.median(np.abs(low - np.median(low)))) if low.size else 0.0
    cut = e + max(6 * sigma, 0.08)
    dark_ones = scores[scores > cut]
    f = float(np.median(dark_ones)) if dark_ones.size else e + MIN_SPAN
    f = max(f, e + MIN_SPAN)
    return e, sigma, f


def classify(items_scores: list, choices_per_item: list):
    flat = np.array([s for row in items_scores for s in row])
    e, sigma, f = _learn_levels(flat)
    span = f - e
    results = []
    for i, row in enumerate(items_scores, start=1):
        ratios = [(s - e) / span for s in row]
        letters = L.LABELS[:len(row)]
        marked = [letters[j] for j, r in enumerate(ratios) if r >= T_MARK]
        faint = [letters[j] for j, r in enumerate(ratios) if T_FAINT <= r < T_MARK]
        if len(marked) == 1 and not faint:
            status, answer = "selected", marked[0]
        elif len(marked) >= 2:
            status, answer = "multiple", None
        elif marked or faint:
            status, answer = "ambiguous", None
        else:
            status, answer = "blank", None
        results.append(ItemResult(i, status, answer, marked, faint,
                                  [round(r, 3) for r in ratios], [round(s, 4) for s in row]))
    return results, {"empty_level": round(e, 4), "noise_sigma": round(sigma, 4),
                     "full_ink_level": round(f, 4)}


# ------------------------------------------------------------------ pipeline
def read_sheet(image: np.ndarray, choices_per_item: list) -> SheetResult:
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    src = find_marker_centers(gray)
    dst = np.float32(_page_marker_pixels())
    bubbles = L.all_bubbles(choices_per_item)
    warnings = []

    # The four markers look identical, so there are 4 possible page rotations.
    mats = []
    for k in range(4):
        pts = np.float32([src[(i + k) % 4] for i in range(4)])
        mats.append(cv2.getPerspectiveTransform(pts, dst))

    # 1) Best evidence: the QR code decodes (and passes its checksum) in exactly one rotation.
    k, qr = None, None
    for kk in range(4):
        qr = read_qr(qr_crop(gray, mats[kk]))
        if qr:
            k = kk
            break

    def warp(kk):
        return cv2.warpPerspective(gray, mats[kk], (WARP_W, WARP_H), flags=cv2.INTER_LINEAR,
                                   borderValue=255)

    # 2) No QR: work out the rotation from the printed bubble rings. Refuse if unsure.
    if k is None:
        warps = [warp(kk) for kk in range(4)]
        scores = [ring_score(darkness_map(w), bubbles) for w in warps]
        order = np.argsort(scores)[::-1]
        best, second = scores[order[0]], scores[order[1]]
        if best < 0.04 or best < 2.0 * max(second, 0.005):
            raise OMRError("QR code not read and the page orientation is unclear. "
                           "Retake the photo (flat, well lit, all four corners visible).")
        k, warped = int(order[0]), warps[order[0]]
        warnings.append("QR code not read: orientation taken from the bubble pattern. "
                        "The exam version must be entered manually before grading.")
    else:
        warped = warp(k)

    dark = darkness_map(warped)
    flat = bubble_scores(dark, bubbles)
    rows, i = [], 0
    for n in choices_per_item:
        rows.append(flat[i:i + n])
        i += n
    items, stats = classify(rows, choices_per_item)
    stats["ring_score"] = round(ring_score(dark, bubbles), 4)
    if stats["noise_sigma"] > 0.05:
        warnings.append("High background noise: the photo may be blurry or poorly lit.")
    return SheetResult(qr is not None, qr[0] if qr else None, qr[1] if qr else None,
                       k, items, stats, warnings, warped)


# ------------------------------------------------------------------ helpers
def code_of(r: ItemResult) -> str:
    """Compact text form: letter, '-' blank, 'AB' multiple, '?' ambiguous."""
    return {"selected": r.answer or "", "blank": "-", "ambiguous": "?"}.get(
        r.status, "".join(r.marked))


def compare_to_truth(items: list, truth: list) -> dict:
    """truth entries: 'A', '-', or 'AB'. Confident-wrong is the dangerous error."""
    out = {"correct": 0, "flagged": 0, "confident_wrong": 0}
    for r, t in zip(items, truth):
        got = code_of(r)
        if got == t:
            out["correct"] += 1
        elif r.status in ("ambiguous", "multiple"):
            out["flagged"] += 1     # caught for manual review: acceptable
        else:
            out["confident_wrong"] += 1
    return out


def draw_debug(result: SheetResult, choices_per_item: list, path: str) -> None:
    img = cv2.cvtColor(result.warped, cv2.COLOR_GRAY2BGR)
    colors = {"selected": (0, 170, 0), "blank": (160, 160, 160),
              "multiple": (0, 0, 220), "ambiguous": (0, 140, 255)}
    for b in L.all_bubbles(choices_per_item):
        item = result.items[b.item - 1]
        cx, cy = L.to_pixel(b.cx, b.cy, SCALE)
        on = b.label in item.marked or b.label in item.faint
        cv2.circle(img, (int(cx), int(cy)), int(b.r * SCALE) + 3,
                   colors[item.status], 3 if on else 1, cv2.LINE_AA)
    cv2.imwrite(path, img)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("image")
    ap.add_argument("--items", type=int, required=True, help="number of items on the sheet")
    ap.add_argument("--tf", default="", help="comma list of True/False item numbers, e.g. 7,14")
    ap.add_argument("--truth", default="", help="optional comma list of expected answers (A, -, AB)")
    ap.add_argument("--debug", default="", help="write an annotated straightened image here")
    ap.add_argument("--json", default="", help="write full results here")
    a = ap.parse_args(argv)

    image = cv2.imread(a.image)
    if image is None:
        raise SystemExit(f"Cannot read image: {a.image}")
    tf = {int(x) for x in a.tf.split(",") if x.strip()}
    choices = [2 if i in tf else 4 for i in range(1, a.items + 1)]
    try:
        res = read_sheet(image, choices)
    except OMRError as e:
        raise SystemExit(f"UNREADABLE: {e}")

    print(f"QR: {'OK ' + str(res.version_code) + ' sheet ' + str(res.serial) if res.qr_ok else 'NOT READ'}"
          f"   rotation steps: {res.rotation_steps}")
    print(f"levels: {res.stats}")
    for w in res.warnings:
        print("WARNING:", w)
    for r in res.items:
        print(f"{r.item:>3}  {r.status:<9} {code_of(r):<5} ratios={r.ratios}")
    counts = {s: sum(1 for r in res.items if r.status == s)
              for s in ("selected", "blank", "multiple", "ambiguous")}
    print("summary:", counts)
    if a.truth:
        truth = [t.strip() for t in a.truth.split(",")]
        print("vs truth:", compare_to_truth(res.items, truth))
    if a.debug:
        draw_debug(res, choices, a.debug)
        print("debug image:", a.debug)
    if a.json:
        slim = {"qr_ok": res.qr_ok, "version": res.version_code, "serial": res.serial,
                "stats": res.stats, "warnings": res.warnings,
                "items": [r.__dict__ for r in res.items]}
        with open(a.json, "w") as fh:
            json.dump(slim, fh, indent=2)


if __name__ == "__main__":
    main()