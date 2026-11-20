"""Counting helpers: how many exams could a question bank produce?

Pure Python. No Django imports (see docs/DECISIONS.md, D-004).
"""
import math


def combinations(n, r):
    """C(n, r): ways to choose r items from n, order ignored.

    Returns 0 when r > n (you cannot choose more than you have).
    """
    _check_non_negative_ints(n, r)
    return math.comb(n, r)


def permutations(n, r=None):
    """P(n, r): ordered arrangements of r items taken from n.

    With r omitted this is n!, the number of ways to arrange all n items.
    """
    if r is None:
        r = n
    _check_non_negative_ints(n, r)
    return math.perm(n, r)


def selection_count(groups):
    """Ways to pick questions when each group is chosen independently.

    groups: list of (available, needed) pairs, e.g. one pair per
    topic/difficulty cell. The answer is the product of C(available, needed).
    """
    total = 1
    for available, needed in groups:
        total *= combinations(available, needed)
    return total


def format_big_number(n):
    """Readable text for huge integers: 1,234 or 1.23 x 10^25."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n < 1_000_000:
        return f"{n:,}"
    digits = str(n)
    return f"{digits[0]}.{digits[1:3]} x 10^{len(digits) - 1}"


def _check_non_negative_ints(*values):
    for v in values:
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ValueError(f"expected a non-negative integer, got {v!r}")