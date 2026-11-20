"""Generate individualized exam versions under faculty-defined constraints."""
import random
import time
from collections import Counter

from core.combinatorics import selection_count
from core.similarity import compare, pairwise_overlaps, summarize

from .entities import GeneratedItem, GeneratedVersion, GenerationReport
from .feasibility import check_feasibility
from .selection import select_questions
from .shuffle import choice_order, correct_label, fisher_yates


def letter_code(index):
    """0 -> A, 25 -> Z, 26 -> AA, 27 -> AB ..."""
    code = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        code = chr(65 + rem) + code
    return code


def generate_versions(questions, topic_required, difficulty_required,
                      total_questions, num_versions, *,
                      shuffle_question_order=True, shuffle_answer_choices=True,
                      base_seed=0, code_prefix="", max_similarity=None,
                      max_attempts=20):
    """Build `num_versions` exam versions. Returns a GenerationReport."""
    started = time.perf_counter()
    if num_versions < 1:
        raise ValueError("num_versions must be at least 1")
    ids = [q.id for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate question ids in the bank")

    report = GenerationReport(requested=num_versions)
    pools = {}
    for q in questions:
        pools.setdefault((q.topic, q.difficulty), []).append(q)
    available = {cell: len(pool) for cell, pool in pools.items()}

    first = check_feasibility(available, topic_required, difficulty_required,
                              total_questions)
    if not first.feasible:
        report.feasible = False
        report.problems = first.problems
        report.duration_ms = _ms(started)
        return report
    report.selection_estimate = selection_count(
        [(available.get(cell, 0), n) for cell, n in first.allocation.items()])

    usage = Counter()
    accepted = []
    for v in range(num_versions):
        best, best_sim, attempts = None, None, 0
        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            seed = f"{base_seed}:{v}:{attempt}"
            candidate = _build_version(
                seed, pools, topic_required, difficulty_required,
                total_questions, usage, num_versions - v,
                shuffle_question_order, shuffle_answer_choices)
            sim = max((compare("", candidate.question_ids, "", a.question_ids)
                       .jaccard for a in accepted), default=0.0)
            if best is None or sim < best_sim:
                best, best_sim = candidate, sim
            if max_similarity is None or sim <= max_similarity:
                break
        best.code = code_prefix + letter_code(v)
        best.attempts = attempts
        accepted.append(best)
        usage.update(best.question_ids)

    report.versions = accepted
    report.overlaps = pairwise_overlaps(
        {v.code: v.question_ids for v in accepted})
    report.summary = summarize(report.overlaps)
    report.warnings = _warnings(report, pools, topic_required,
                                difficulty_required, total_questions,
                                num_versions, max_similarity)
    report.duration_ms = _ms(started)
    return report


def check_constraints(version, bank_by_id, topic_required, difficulty_required,
                      total_questions):
    """Independently verify a version. Returns a list of violations (empty = OK)."""
    problems = []
    items = version.items
    if len(items) != total_questions:
        problems.append(f"{len(items)} questions, expected {total_questions}")
    ids = [i.question_id for i in items]
    if len(ids) != len(set(ids)):
        problems.append("a question appears more than once")
    topics = Counter(bank_by_id[i].topic for i in ids)
    diffs = Counter(bank_by_id[i].difficulty for i in ids)
    for t, n in topic_required.items():
        if topics[t] != n:
            problems.append(f"topic {t}: {topics[t]} questions, expected {n}")
    for d, n in difficulty_required.items():
        if diffs[d] != n:
            problems.append(f"difficulty {d}: {diffs[d]} questions, expected {n}")
    for item in items:
        q = bank_by_id[item.question_id]
        slot = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".index(item.correct_label)
        if item.choice_order[slot] != q.correct_index:
            problems.append(f"item {item.position}: answer key does not match")
    return problems


def _build_version(seed, pools, topic_required, difficulty_required,
                   total, usage, versions_left, shuffle_order, shuffle_choices):
    rng = random.Random(seed)

    # Least-reuse-first: find the lowest level L such that the configuration
    # can still be met using only questions used at most L times so far.
    # L = 0 means "only brand-new questions"; the top level is the whole bank.
    # At each level we first try BALANCED allocation: no cell may give more than
    # its fair share (ceil(count / versions_left)), so later versions do not
    # find a cell already emptied. If that is infeasible, we allow any cell.
    top_level = max(usage.values(), default=0)
    result = None
    for level in range(top_level + 1):
        level_pools = {cell: [q for q in pool if usage.get(q.id, 0) <= level]
                       for cell, pool in pools.items()}
        counts = {cell: len(p) for cell, p in level_pools.items()}
        attempts = []
        if versions_left > 1:
            attempts.append({cell: -(-n // versions_left)       # ceil division
                             for cell, n in counts.items()})
        attempts.append(counts)
        for cell_limits in attempts:
            result = check_feasibility(cell_limits, topic_required,
                                       difficulty_required, total, rng=rng)
            if result.feasible:
                break
        if result.feasible:
            break
    chosen = select_questions(level_pools, result.allocation, usage, rng)
    if shuffle_order:
        chosen = fisher_yates(chosen, rng)
    items = []
    for position, q in enumerate(chosen, start=1):
        # True/False keeps its natural order (True, False); only MC is shuffled.
        order = choice_order(q.n_choices, rng,
                             enabled=shuffle_choices and q.qtype == "MC")
        items.append(GeneratedItem(position, q.id, q.topic, q.difficulty,
                                   order, correct_label(order, q.correct_index)))
    return GeneratedVersion(code="", seed=seed, attempts=0, items=items)


def _warnings(report, pools, topic_required, difficulty_required, total,
              num_versions, max_similarity):
    warnings = []
    usable = sum(len(p) for (t, d), p in pools.items()
                 if t in topic_required and d in difficulty_required)
    slots = total * num_versions
    if usable < slots:
        warnings.append(
            f"The bank has {usable} usable questions but {num_versions} versions "
            f"need {slots} question slots, so at least {slots - usable} slots "
            f"must repeat a question. Versions cannot be completely different.")
    for o in report.overlaps:
        if o.jaccard == 1.0:
            warnings.append(f"Versions {o.label_a} and {o.label_b} contain "
                            f"exactly the same questions (only the order and "
                            f"choices differ).")
    if max_similarity is not None:
        over = [o for o in report.overlaps if o.jaccard > max_similarity]
        if over:
            warnings.append(
                f"{len(over)} version pair(s) exceed the similarity limit of "
                f"{max_similarity:.0%}. The best attempt was kept. A larger "
                f"question bank would reduce overlap.")
    return warnings


def _ms(started):
    return round((time.perf_counter() - started) * 1000, 2)