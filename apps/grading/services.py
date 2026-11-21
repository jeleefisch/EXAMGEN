"""Score a scanned sheet against its own version's key. Never guesses."""
from django.db import transaction

from .models import GradeResult


class GradingError(Exception):
    pass


def grade_scan(scan, student_label=None):
    if scan.version_id is None or not scan.is_ready:
        raise GradingError("Choose the version and resolve every uncertain item first.")
    questions = list(scan.version.items.order_by("position"))
    answers = {i.item: i.final for i in scan.items.all()}
    if len(questions) != len(answers):
        raise GradingError(
            f"The sheet has {len(answers)} items but version {scan.version.code} has {len(questions)}.")

    details, score, max_score = [], 0, 0
    correct = wrong = blank = 0
    for q in questions:
        got = answers.get(q.position, "")
        ok = got == q.correct_label
        if got == "-":
            blank += 1
        elif ok:
            correct += 1
        else:
            wrong += 1
        earned = q.points if ok else 0
        score += earned
        max_score += q.points
        details.append({"item": q.position, "answer": got, "key": q.correct_label,
                        "correct": ok, "points": earned})

    values = {"score": score, "max_score": max_score, "correct_count": correct,
              "wrong_count": wrong, "blank_count": blank, "details": details}
    if student_label is not None:
        values["student_label"] = student_label.strip()[:120]
    with transaction.atomic():
        grade, _ = GradeResult.objects.update_or_create(scan=scan, defaults=values)
    return grade