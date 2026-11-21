"""Synthetic stress test for the OMR spike. All results are SYNTHETIC (no real paper).

Builds random sheets with exactly known answers, 'photographs' them under three
conditions, reads them, and counts correct / flagged / confident_wrong with the
same rule as the CLI (compare_to_truth).

Run:  python -m spike.stress_test --sheets 30 --seed 1
"""
from __future__ import annotations

import argparse

import cv2
import numpy as np

from core import sheet_layout as L
from spike.omr_spike import OMRError, code_of, compare_to_truth, read_sheet
from spike.erasure import flag_erasures
from spike.synth import photograph, render_sheet, shade

CONDITIONS = {
    "mild":     dict(tilt=0.5, rot_range=3,  rot90=False, light=0.10, noise=2.0, blur=0.8),
    "moderate": dict(tilt=1.0, rot_range=15, rot90=True,  light=0.25, noise=4.0, blur=1.0),
    "harsh":    dict(tilt=1.6, rot_range=25, rot90=True,  light=0.40, noise=8.0, blur=1.8),
}


def make_sheet(rng, n_items):
    """Return (page, choices, truth). Marks: solid, faint, double, or blank."""
    tf = {i for i in range(1, n_items + 1) if rng.uniform() < 0.15}
    choices = [2 if i in tf else 4 for i in range(1, n_items + 1)]
    version = f"E{int(rng.integers(1, 9))}-{'ABC'[int(rng.integers(0, 3))]}"
    serial = int(rng.integers(1, 200))
    page = render_sheet(choices, version, serial)
    truth = []
    for item, n in enumerate(choices, start=1):
        kind = rng.choice(["solid", "faint", "double", "blank"], p=[0.60, 0.15, 0.10, 0.15])
        if kind == "blank":
            truth.append("-")
        elif kind == "double":
            a, b = sorted(int(x) for x in rng.choice(n, size=2, replace=False))
            shade(page, item, a, 0.85, rng)
            shade(page, item, b, 0.85, rng)
            truth.append(L.LABELS[a] + L.LABELS[b])
        else:
            c = int(rng.integers(0, n))
            fill = 0.85 if kind == "solid" else rng.uniform(0.2, 0.4)
            shade(page, item, c, fill, rng)
            truth.append(L.LABELS[c])
    return page, choices, truth, version, serial


def run_condition(name, cfg, sheets, rng):
    total = {"correct": 0, "flagged": 0, "confident_wrong": 0}
    unreadable, crashed, qr_bad = 0, 0, 0
    offenders = []
    for s in range(sheets):
        n_items = int(rng.integers(10, 51))
        page, choices, truth, version, serial = make_sheet(rng, n_items)
        photo = photograph(
            page, rng, tilt=cfg["tilt"], rotate_deg=float(rng.uniform(-cfg["rot_range"], cfg["rot_range"])),
            rot90=int(rng.integers(0, 4)) if cfg["rot90"] else 0,
            light=cfg["light"], noise=cfg["noise"], blur=cfg["blur"])
        image = cv2.cvtColor(photo, cv2.COLOR_GRAY2BGR)   # same as the CLI (imread gives BGR)
        try:
            res = read_sheet(image, choices)
        except OMRError:
            unreadable += 1
            continue
        except Exception as e:  # keep the run going, report it
            crashed += 1
            print(f"  [{name} #{s}] CRASH: {type(e).__name__}: {e}")
            continue
        flag_erasures(res)
        if not res.qr_ok or res.version_code != version or res.serial != serial:
            qr_bad += 1
        for r, t in zip(res.items, truth):
            c = compare_to_truth([r], [t])
            for k in total:
                total[k] += c[k]
            if c["confident_wrong"]:
                offenders.append((name, s, r.item, t, code_of(r), r.ratios))
    return total, unreadable, crashed, qr_bad, offenders


def main(argv=None):
    ap = argparse.ArgumentParser(description="Synthetic OMR stress test")
    ap.add_argument("--sheets", type=int, default=30, help="sheets per condition")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    rng = np.random.default_rng(a.seed)

    print(f"SYNTHETIC stress test: {a.sheets} sheets per condition, seed {a.seed}\n")
    print(f"{'condition':<10}{'items':>7}{'correct':>9}{'flagged':>9}{'conf_wrong':>12}"
          f"{'unreadable':>12}{'qr_bad':>8}{'crash':>7}")
    all_off = []
    for name, cfg in CONDITIONS.items():
        tot, unread, crashed, qr_bad, off = run_condition(name, cfg, a.sheets, rng)
        n = sum(tot.values())
        print(f"{name:<10}{n:>7}{tot['correct']:>9}{tot['flagged']:>9}{tot['confident_wrong']:>12}"
              f"{unread:>12}{qr_bad:>8}{crashed:>7}")
        all_off += off
    print(f"\nconfident_wrong rows: {len(all_off)}")
    for name, s, item, t, got, ratios in all_off[:40]:
        print(f"  {name} sheet#{s} item {item}: truth={t} got={got} ratios={ratios}")
    if len(all_off) > 40:
        print(f"  ... and {len(all_off) - 40} more")


if __name__ == "__main__":
    main()