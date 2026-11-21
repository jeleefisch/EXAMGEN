"""Synthetic OMR benchmark.

ALL FIGURES FROM THIS MODULE ARE DIGITAL/SYNTHETIC: sheets are rendered by
spike.synth and given simulated camera effects. They are NOT measurements of
printed, hand-marked paper.

Run:  python -m core.benchmark --sheets 10 --seed 1 [--markdown]
"""
from __future__ import annotations

import argparse

import cv2
import numpy as np

from core import sheet_layout as L
from core.omr_erasure import flag_erasures
from core.omr_reader import OMRError, code_of, read_sheet

CONDITIONS = {
    "mild":     dict(tilt=0.5, rot_range=3,  rot90=False, light=0.10, noise=2.0, blur=0.8),
    "moderate": dict(tilt=1.0, rot_range=15, rot90=True,  light=0.25, noise=4.0, blur=1.0),
    "harsh":    dict(tilt=1.6, rot_range=25, rot90=True,  light=0.40, noise=8.0, blur=1.8),
}
MARK_KINDS = ["solid", "faint", "double", "blank"]
MARK_PROBS = [0.60, 0.15, 0.10, 0.15]
COUNT_KEYS = ("sheets", "read", "unreadable", "crashed", "qr_unread", "id_wrong",
              "items", "correct", "flagged", "confident_wrong")


def _make_sheet(rng, n_items):
    """Return (page, choices, truth, version, serial). Marks: solid, faint, double, blank."""
    from spike.synth import render_sheet, shade
    tf = {i for i in range(1, n_items + 1) if rng.uniform() < 0.15}
    choices = [2 if i in tf else 4 for i in range(1, n_items + 1)]
    version = f"E{int(rng.integers(1, 9))}-{'ABC'[int(rng.integers(0, 3))]}"
    serial = int(rng.integers(1, 200))
    page = render_sheet(choices, version, serial)
    truth = []
    for item, n in enumerate(choices, start=1):
        kind = str(rng.choice(MARK_KINDS, p=MARK_PROBS))
        if kind == "blank":
            truth.append("-")
        elif kind == "double":
            a, b = sorted(int(x) for x in rng.choice(n, size=2, replace=False))
            shade(page, item, a, 0.85, rng)
            shade(page, item, b, 0.85, rng)
            truth.append(L.LABELS[a] + L.LABELS[b])
        else:
            c = int(rng.integers(0, n))
            shade(page, item, c, 0.85 if kind == "solid" else rng.uniform(0.2, 0.4), rng)
            truth.append(L.LABELS[c])
    return page, choices, truth, version, serial


def _outcome(result, truth):
    """correct | flagged (sent to manual review: acceptable) | confident_wrong (dangerous)."""
    if code_of(result) == truth:
        return "correct"
    if result.status in ("ambiguous", "multiple"):
        return "flagged"
    return "confident_wrong"


def _run_condition(name, cfg, sheets, rng, items_range, offenders):
    from spike.synth import photograph
    counts = {k: 0 for k in COUNT_KEYS}
    lo, hi = items_range
    for s in range(sheets):
        counts["sheets"] += 1
        n_items = int(rng.integers(lo, hi + 1))
        page, choices, truth, version, serial = _make_sheet(rng, n_items)
        photo = photograph(
            page, rng, tilt=cfg["tilt"],
            rotate_deg=float(rng.uniform(-cfg["rot_range"], cfg["rot_range"])),
            rot90=int(rng.integers(0, 4)) if cfg["rot90"] else 0,
            light=cfg["light"], noise=cfg["noise"], blur=cfg["blur"])
        image = cv2.cvtColor(photo, cv2.COLOR_GRAY2BGR)
        try:
            res = read_sheet(image, choices)
        except OMRError:
            counts["unreadable"] += 1
            continue
        except Exception:                      # keep the run going, count it
            counts["crashed"] += 1
            continue
        flag_erasures(res)
        counts["read"] += 1
        if not res.qr_ok:
            counts["qr_unread"] += 1           # the app would ask the teacher to pick the version
        elif res.version_code != version or res.serial != serial:
            counts["id_wrong"] += 1            # QR decoded but gave the wrong identity
        for r, t in zip(res.items, truth):
            counts["items"] += 1
            outcome = _outcome(r, t)
            counts[outcome] += 1
            if outcome == "confident_wrong":
                offenders.append({"condition": name, "sheet": s, "item": r.item,
                                  "truth": t, "got": code_of(r), "ratios": r.ratios})
    return counts


def run_benchmark(sheets=10, seed=1, conditions=None, items_range=(10, 50)):
    names = list(conditions) if conditions else list(CONDITIONS)
    unknown = [n for n in names if n not in CONDITIONS]
    if unknown:
        raise ValueError(f"Unknown condition(s): {', '.join(unknown)}")
    rng = np.random.default_rng(seed)
    offenders, per = [], {}
    for name in names:
        per[name] = _run_condition(name, CONDITIONS[name], sheets, rng, items_range, offenders)
    total = {k: sum(c[k] for c in per.values()) for k in COUNT_KEYS}
    return {"seed": seed, "sheets_per_condition": sheets, "conditions": per,
            "total": total, "offenders": offenders}


def _pct(n, d):
    return f"{100 * n / d:.1f}%" if d else "n/a"


def format_report(result, markdown=False):
    header = ["condition", "sheets", "unreadable", "crashed", "items",
              "correct", "flagged", "confident wrong", "QR not read", "ID wrong"]
    rows = []
    for name, c in {**result["conditions"], "TOTAL": result["total"]}.items():
        rows.append([name, c["sheets"], c["unreadable"], c["crashed"], c["items"],
                     f"{c['correct']} ({_pct(c['correct'], c['items'])})",
                     c["flagged"], c["confident_wrong"], c["qr_unread"], c["id_wrong"]])
    lines = [
        "DIGITAL/SYNTHETIC results: rendered sheets with simulated camera effects, "
        "not printed paper.",
        f"Seed {result['seed']}, {result['sheets_per_condition']} sheets per condition.",
        "",
    ]
    if markdown:
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "|".join("---" for _ in header) + "|")
        lines += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    else:
        table = [header] + [[str(x) for x in r] for r in rows]
        widths = [max(len(r[i]) for r in table) for i in range(len(header))]
        for r in table:
            lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)))
    lines += ["", "confident wrong = a wrong answer the reader did NOT flag (the dangerous error).",
              "flagged = sent to manual review (acceptable).",
              "QR not read = the teacher must pick the version by hand.",
              "ID wrong = a QR decoded but gave the wrong version or serial."]
    if result["offenders"] and not markdown:
        lines.append("")
        lines.append(f"confident-wrong rows: {len(result['offenders'])}")
        for o in result["offenders"][:10]:
            lines.append(f"  {o['condition']} sheet#{o['sheet']} item {o['item']}: "
                         f"truth={o['truth']} got={o['got']} ratios={o['ratios']}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Synthetic OMR benchmark")
    ap.add_argument("--sheets", type=int, default=10, help="sheets per condition")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--markdown", action="store_true", help="print a Markdown table for the docs")
    a = ap.parse_args(argv)
    print(format_report(run_benchmark(a.sheets, a.seed), markdown=a.markdown))


if __name__ == "__main__":
    main()