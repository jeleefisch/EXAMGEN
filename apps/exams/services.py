"""Generation service: connects the Django-free core engine to the database.

Flow: load eligible questions -> run the engine -> verify -> write snapshots.
Everything is written inside one transaction, so it is all-or-nothing.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from django.db import transaction

from apps.banks.models import Choice, Question
from apps.banks.services import eligible_core_questions
from core.generation.generator import check_constraints, generate_versions

from .models import (
    Exam,
    ExamVersion,
    GenerationRun,
    VersionChoice,
    VersionQuestion,
    new_seed,
)


class ExamFinalizedError(Exception):
    """Raised when someone tries to regenerate a finalized exam."""


@dataclass
class GenerationOutcome:
    success: bool
    problems: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    excluded: list = field(default_factory=list)  # [(question_pk, reason)]
    run: GenerationRun | None = None
    versions: list = field(default_factory=list)


def _count(value):
    """Overlap fields may be a number or a collection; return a number."""
    return value if isinstance(value, (int, float)) else len(value)


def _overlaps_to_json(overlaps):
    return [
        {
            "a": o.label_a,
            "b": o.label_b,
            "shared": _count(o.shared),
            "union": _count(o.union),
            "jaccard": round(o.jaccard, 4),
        }
        for o in overlaps
    ]


def _save_version(exam, core_version, sequence, db_questions, choices_by_q):
    """Write one version and its question/choice snapshots."""
    ev = ExamVersion.objects.create(
        exam=exam,
        code=core_version.code,
        sequence=sequence,
        seed=core_version.seed,
        attempts=core_version.attempts,
    )
    for item in core_version.items:
        src = db_questions[item.question_id]
        originals = choices_by_q[src.pk]  # already sorted by position
        vq = VersionQuestion.objects.create(
            version=ev,
            position=item.position,
            source_question=src,
            text=src.text,
            qtype=src.qtype,
            topic_name=src.topic.name,
            difficulty=src.difficulty,
            points=exam.points_per_question,  # exam value overrides bank value
            correct_label=item.correct_label,
        )
        rows = []
        key_label = None
        for slot, original_index in enumerate(item.choice_order):
            original = originals[original_index]
            label = chr(ord("A") + slot)
            if original.is_correct:
                key_label = label
            rows.append(
                VersionChoice(
                    question=vq,
                    display_label=label,
                    text=original.text,
                    is_correct=original.is_correct,
                )
            )
        # Safety net: the engine's key must match the snapshot we just built.
        if key_label != item.correct_label:
            raise RuntimeError(
                f"Key mismatch for question {src.pk}: "
                f"engine says {item.correct_label}, snapshot says {key_label}"
            )
        VersionChoice.objects.bulk_create(rows)
    return ev


def generate_exam_versions(exam: Exam) -> GenerationOutcome:
    """Generate (or regenerate) all versions of a draft exam."""
    if exam.status == "finalized":
        raise ExamFinalizedError("A finalized exam cannot be regenerated.")
    if exam.bank is None:
        return GenerationOutcome(
            success=False,
            problems=["This exam's question bank no longer exists."],
        )

    # 1. Load only usable questions; report the rest.
    usable, excluded = eligible_core_questions(exam.bank)
    topic_required = exam.topic_required()
    difficulty_required = exam.difficulty_required()

    # 2. Run the engine (pure Python, nothing written yet).
    report = generate_versions(
        usable,
        topic_required,
        difficulty_required,
        exam.total_questions,
        exam.num_versions,
        shuffle_question_order=exam.shuffle_questions,
        shuffle_answer_choices=exam.shuffle_choices,
        base_seed=exam.base_seed,
        code_prefix=f"E{exam.pk}-",
        max_similarity=exam.max_similarity,
    )
    if not report.feasible or not report.versions:
        return GenerationOutcome(
            success=False,
            problems=list(report.problems),
            warnings=list(report.warnings),
            excluded=list(excluded),
        )

    # 3. Independent verification before anything is saved.
    bank_by_id = {q.id: q for q in usable}
    violations = []
    for v in report.versions:
        for msg in check_constraints(
            v, bank_by_id, topic_required, difficulty_required, exam.total_questions
        ):
            violations.append(f"Version {v.code}: {msg}")
    if violations:
        return GenerationOutcome(
            success=False, problems=violations, excluded=list(excluded)
        )

    # 4. Load the original DB rows needed to build snapshots.
    ids = {item.question_id for v in report.versions for item in v.items}
    db_questions = Question.objects.select_related("topic").in_bulk(ids)
    choices_by_q = defaultdict(list)
    for c in Choice.objects.filter(question_id__in=ids).order_by("question_id", "position"):
        choices_by_q[c.question_id].append(c)

    # 5. Write everything atomically.
    with transaction.atomic():
        exam.refresh_from_db(fields=["status"])
        if exam.status == "finalized":
            raise ExamFinalizedError("A finalized exam cannot be regenerated.")

        ExamVersion.objects.filter(exam=exam).delete()  # draft only (checked above)

        saved = [
            _save_version(exam, v, seq, db_questions, choices_by_q)
            for seq, v in enumerate(report.versions, start=1)
        ]

        summary = report.summary or {}
        run = GenerationRun.objects.create(
            exam=exam,
            requested=report.requested,
            succeeded=report.success_count,
            duration_ms=report.duration_ms,
            mean_jaccard=summary.get("mean_jaccard"),
            max_jaccard=summary.get("max_jaccard"),
            warnings=list(report.warnings),
            overlaps=_overlaps_to_json(report.overlaps),
            selection_estimate=str(report.selection_estimate),
        )

    return GenerationOutcome(
        success=True,
        warnings=list(report.warnings),
        excluded=list(excluded),
        run=run,
        versions=saved,
    )