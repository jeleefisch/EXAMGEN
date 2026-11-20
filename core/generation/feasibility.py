"""Can this exam configuration be built from this question bank?

The hard part: topic quotas and difficulty counts must hold at the SAME time.
We look for a grid x[topic][difficulty] where
    - every cell is at most the number of questions the bank has there,
    - each topic row adds up to that topic's quota,
    - each difficulty column adds up to that difficulty's count.
That is a small max-flow problem, solved here with Edmonds-Karp (BFS).

Pure Python. No Django imports (see docs/DECISIONS.md, D-004).
"""
from collections import deque
from dataclasses import dataclass, field

_SOURCE = ("source",)
_SINK = ("sink",)


@dataclass
class FeasibilityResult:
    feasible: bool
    allocation: dict = field(default_factory=dict)  # (topic, difficulty) -> count
    problems: list = field(default_factory=list)    # plain-English messages
    bottleneck: dict = None  # {"topics": [...], "need": int, "max_supply": int}


def check_feasibility(available, topic_required, difficulty_required,
                      total_questions, rng=None):
    """Decide feasibility and, if possible, return one valid cell allocation.

    available:           {(topic, difficulty): questions in the bank}
    topic_required:      {topic: questions wanted}
    difficulty_required: {difficulty: questions wanted}
    total_questions:     questions per exam
    rng:                 optional random.Random; varies WHICH valid allocation
                         is returned (not uniformly random, see docs).
    """
    _validate_numbers(available, topic_required, difficulty_required,
                      total_questions)
    problems = []

    # Layer 1: the configuration must agree with itself.
    if total_questions < 1:
        problems.append("The exam must have at least 1 question.")
    topic_sum = sum(topic_required.values())
    if topic_sum != total_questions:
        problems.append(f"The topic quotas add up to {topic_sum}, but the exam "
                        f"has {total_questions} questions. They must match.")
    diff_sum = sum(difficulty_required.values())
    if diff_sum != total_questions:
        problems.append(f"The difficulty counts add up to {diff_sum}, but the "
                        f"exam has {total_questions} questions. They must match.")
    if problems:
        return FeasibilityResult(False, problems=problems)

    # Layer 2: simple shortages, one topic or one difficulty at a time.
    for topic, need in topic_required.items():
        have = sum(available.get((topic, d), 0) for d in difficulty_required)
        if have < need:
            problems.append(f"Topic '{topic}' needs {need} questions but the "
                            f"bank has only {have}.")
    for diff, need in difficulty_required.items():
        have = sum(available.get((t, diff), 0) for t in topic_required)
        if have < need:
            problems.append(f"The exam needs {need} {diff} questions but the "
                            f"bank has only {have}.")
    if problems:
        return FeasibilityResult(False, problems=problems)

    # Layer 3: the two kinds of requirement together (max-flow).
    capacity = _build_capacity(available, topic_required, difficulty_required)
    flow_value, residual, reachable = _max_flow(capacity, rng)

    if flow_value == total_questions:
        allocation = {}
        for t in topic_required:
            for d in difficulty_required:
                cap = capacity.get(("T", t), {}).get(("D", d), 0)
                left = residual[("T", t)].get(("D", d), 0) if cap else 0
                allocation[(t, d)] = cap - left
        return FeasibilityResult(True, allocation=allocation)

    message, bottleneck = _explain_bottleneck(
        available, topic_required, difficulty_required, reachable)
    return FeasibilityResult(False, problems=[message], bottleneck=bottleneck)


# ---------------------------------------------------------------- internals

def _validate_numbers(available, topic_required, difficulty_required, total):
    values = (list(available.values()) + list(topic_required.values())
              + list(difficulty_required.values()) + [total])
    for v in values:
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ValueError(f"expected non-negative integers, got {v!r}")


def _build_capacity(available, topic_required, difficulty_required):
    cap = {_SOURCE: {}}
    for t, need in topic_required.items():
        if need > 0:
            cap[_SOURCE][("T", t)] = need
        for d in difficulty_required:
            have = available.get((t, d), 0)
            if have > 0:
                cap.setdefault(("T", t), {})[("D", d)] = have
    for d, need in difficulty_required.items():
        if need > 0:
            cap.setdefault(("D", d), {})[_SINK] = need
    return cap


def _bfs(residual, rng):
    """Breadth-first search from the source. Returns the parent map."""
    parent = {_SOURCE: None}
    queue = deque([_SOURCE])
    while queue:
        u = queue.popleft()
        neighbours = [v for v, c in residual.get(u, {}).items()
                      if c > 0 and v not in parent]
        if rng is not None:
            rng.shuffle(neighbours)
        for v in neighbours:
            parent[v] = u
            queue.append(v)
    return parent


def _max_flow(capacity, rng):
    residual = {u: dict(vs) for u, vs in capacity.items()}
    for u, vs in capacity.items():          # add reverse edges (capacity 0)
        for v in vs:
            residual.setdefault(v, {}).setdefault(u, 0)
    total = 0
    while True:
        parent = _bfs(residual, rng)
        if _SINK not in parent:
            return total, residual, set(parent)   # parent keys = reachable
        path_edges, node = [], _SINK
        while parent[node] is not None:
            path_edges.append((parent[node], node))
            node = parent[node]
        push = min(residual[u][v] for u, v in path_edges)
        for u, v in path_edges:
            residual[u][v] -= push
            residual[v][u] += push
        total += push


def _explain_bottleneck(available, topic_required, difficulty_required,
                        reachable):
    """Name a group of topics that cannot be satisfied, and say why.

    Topics still reachable from the source in the final residual graph form a
    violated 'Hall condition': together they need more questions than they can
    possibly supply once the difficulty counts are respected.
    """
    topics = [t for t in topic_required if ("T", t) in reachable]
    need = sum(topic_required[t] for t in topics)
    parts, max_supply = [], 0
    for d, wanted in difficulty_required.items():
        in_bank = sum(available.get((t, d), 0) for t in topics)
        supply = min(wanted, in_bank)
        max_supply += supply
        reason = (f"the exam asks for only {wanted}" if wanted <= in_bank
                  else f"only {in_bank} in the bank")
        parts.append(f"{d}: up to {supply} ({reason})")
    names = ", ".join(f"'{t}'" for t in topics)
    label, verb = ("Topic", "needs") if len(topics) == 1 else ("Topics", "need")
    message = (f"{label} {names} {verb} {need} questions in total, but at most "
               f"{max_supply} can be selected. Per difficulty: "
               + "; ".join(parts) + ". Add questions to the bank, lower the "
               "topic quota, or change the difficulty counts.")
    return message, {"topics": topics, "need": need, "max_supply": max_supply}