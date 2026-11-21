"""Synthetic answer-sheet photos for testing the OMR reader (no printer needed).

render_sheet() draws a clean sheet from core/sheet_layout.py, shade() adds pencil marks,
photograph() turns it into a believable phone photo (tilt, rotation, uneven light, noise).
"""
from __future__ import annotations

import cv2
import numpy as np

from core import sheet_layout as L
from spike.omr_spike import SCALE, WARP_H, WARP_W


def _px(x, y):
    px, py = L.to_pixel(x, y, SCALE)
    return int(round(px)), int(round(py))


def render_sheet(choices_per_item, version_code="E1-A", serial=1) -> np.ndarray:
    img = np.full((WARP_H, WARP_W), 255, np.uint8)
    for m in L.markers():
        cv2.rectangle(img, _px(m.x, m.y + m.h), _px(m.x + m.w, m.y), 0, -1)
    q = L.qr_box()
    code = cv2.QRCodeEncoder.create().encode(L.encode_payload(version_code, serial))
    code = cv2.copyMakeBorder(code, 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=255)
    (x0, y1), (x1, y0) = _px(q.x, q.y), _px(q.x + q.w, q.y + q.h)
    img[y0:y1, x0:x1] = cv2.resize(code, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
    for b in L.all_bubbles(list(choices_per_item)):
        c = _px(b.cx, b.cy)
        cv2.circle(img, c, int(round(b.r * SCALE)), 0, 2, cv2.LINE_AA)
        cv2.putText(img, b.label, (c[0] - 5, c[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.42, 140, 1, cv2.LINE_AA)
    return img


def shade(img, item, choice, fill, rng) -> None:
    """Draw one pencil mark. fill: 0..1 darkness (0.85 solid, 0.3 faint)."""
    b = L.bubble(item, choice)
    cx, cy = _px(b.cx, b.cy)
    cx += int(round(rng.uniform(-1.2, 1.2) * SCALE))
    cy += int(round(rng.uniform(-1.2, 1.2) * SCALE))
    ax = int(b.r * SCALE * rng.uniform(0.75, 0.95))
    ay = int(b.r * SCALE * rng.uniform(0.75, 0.95))
    cv2.ellipse(img, (cx, cy), (ax, ay), rng.uniform(0, 180), 0, 360,
                int(255 * (1 - fill)), -1, cv2.LINE_AA)


def photograph(page, rng, *, tilt=1.0, rotate_deg=0.0, rot90=0, light=0.25, noise=4.0,
               blur=1.0, canvas=(1800, 2400)) -> np.ndarray:
    cw, ch = canvas
    h, w = page.shape
    base = np.float32([[150, 140], [cw - 150, 140], [cw - 150, ch - 140], [150, ch - 140]])
    dst = base + rng.uniform(-70, 70, base.shape).astype(np.float32) * tilt
    a = np.deg2rad(rotate_deg)
    rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]], np.float32)
    centre = np.float32([cw / 2, ch / 2])
    dst = (dst - centre) @ rot.T + centre
    m = cv2.getPerspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]), dst.astype(np.float32))
    out = cv2.warpPerspective(page, m, canvas, borderValue=110).astype(np.float32)
    yy, xx = np.mgrid[0:ch, 0:cw].astype(np.float32)
    gradient = 1.0 - light * (xx / cw * 0.7 + yy / ch * 0.3)
    vignette = 1.0 - 0.15 * (((xx - cw / 2) / cw) ** 2 + ((yy - ch / 2) / ch) ** 2) * 4
    out = out * gradient * vignette + rng.normal(0, noise, out.shape)
    out = np.clip(out, 0, 255).astype(np.uint8)
    if blur > 0:
        out = cv2.GaussianBlur(out, (0, 0), blur)
    _, enc = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 80])
    out = cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE)
    return np.ascontiguousarray(np.rot90(out, rot90))