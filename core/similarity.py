"""Overlap between exam versions using the Jaccard coefficient.

J(A, B) = |A intersect B| / |A union B|
Pure Python. No Django imports.
"""
from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class OverlapResult:
    label_a: str
    label_b: str
    shared: int
    union: int
    jaccard: float

    @property
    def percent(self):
        return round(self.jaccard * 100, 2)


def jaccard(a, b):
    """Jaccard similarity of two collections of question IDs (0.0 to 1.0).

    Two empty sets are defined as identical (1.0).
    """
    a, b = set(a), set(b)
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def compare(label_a, ids_a, label_b, ids_b):
    """Full overlap details for one pair of versions."""
    a, b = set(ids_a), set(ids_b)
    union = a | b
    shared = a & b
    score = 1.0 if not union else len(shared) / len(union)
    return OverlapResult(label_a, label_b, len(shared), len(union), score)


def pairwise_overlaps(versions):
    """Compare every pair. versions: dict of version_code -> question IDs."""
    codes = sorted(versions)
    return [compare(x, versions[x], y, versions[y])
            for x, y in combinations(codes, 2)]


def summarize(results):
    """Mean and max Jaccard over a list of OverlapResult (None if empty)."""
    if not results:
        return None
    scores = [r.jaccard for r in results]
    return {
        "pairs": len(scores),
        "mean_jaccard": sum(scores) / len(scores),
        "max_jaccard": max(scores),
    }