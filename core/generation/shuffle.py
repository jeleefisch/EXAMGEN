"""Shuffling with Fisher-Yates, and answer-key remapping."""
import string


def fisher_yates(items, rng):
    """Return a shuffled copy. Every ordering is equally likely.

    Walk from the last position down to 1; swap each position with a random
    position at or before it.
    """
    result = list(items)
    for i in range(len(result) - 1, 0, -1):
        j = rng.randint(0, i)
        result[i], result[j] = result[j], result[i]
    return result


def choice_order(n_choices, rng, enabled=True):
    """Original choice indexes in the order they will be displayed."""
    order = list(range(n_choices))
    return tuple(fisher_yates(order, rng) if enabled else order)


def correct_label(order, correct_index):
    """Letter (A, B, ...) where the correct choice lands after shuffling."""
    return string.ascii_uppercase[order.index(correct_index)]