"""Pick the actual questions for each topic/difficulty cell."""
from .shuffle import fisher_yates


def select_questions(pools, allocation, usage, rng):
    """Choose questions cell by cell, preferring the least-used ones.

    pools:      {(topic, difficulty): [Question, ...]}
    allocation: {(topic, difficulty): how many to take}
    usage:      {question_id: times already used in accepted versions}
    rng:        random.Random

    Shuffle each pool first, then stable-sort by usage: unused questions come
    first, and ties are broken randomly.
    """
    chosen = []
    for cell, count in allocation.items():
        if count == 0:
            continue
        pool = pools.get(cell, [])
        if len(pool) < count:
            raise ValueError(f"cell {cell} needs {count}, bank has {len(pool)}")
        ordered = fisher_yates(pool, rng)
        ordered.sort(key=lambda q: usage.get(q.id, 0))
        chosen.extend(ordered[:count])
    return chosen