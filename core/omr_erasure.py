"""Erasure rule (D-016): a mark beside a white-out/erased patch goes to manual review."""
from __future__ import annotations

ERASURE_RATIO = -0.03   # a bubble this much LIGHTER than an empty one looks erased


def flag_erasures(res) -> int:
    """Turn 'selected' rows with an erasure-like patch into 'ambiguous'. Returns how many."""
    n = 0
    for r in res.items:
        if r.status == "selected" and any(x < ERASURE_RATIO for x in r.ratios):
            r.status = "ambiguous"
            r.answer = None
            n += 1
    if n:
        res.warnings.append(f"{n} item(s) have an erasure-like patch next to a mark; sent to review.")
    return n