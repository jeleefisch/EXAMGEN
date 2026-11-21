from collections import Counter

from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.banks.models import QuestionBank

from .forms import ExamForm
from .models import Exam, ExamVersion, VersionChoice
from .services import (
    ExamFinalizedError,
    SnapshotMismatchError,
    generate_exam_versions,
)

FLASH_KEY = "exam_flash"


def _flash(request, *, ok, notice="", problems=(), warnings=(), excluded=()):
    """Store a one-time message in the session; the detail page shows it once."""
    request.session[FLASH_KEY] = {
        "ok": ok,
        "notice": notice,
        "problems": [str(p) for p in problems],
        "warnings": [str(w) for w in warnings],
        "excluded": [{"pk": pk, "reason": str(r)} for pk, r in excluded],
    }


def _own_exam(request, pk):
    # Ownership check: the exam must belong to the logged-in user, else 404.
    return get_object_or_404(Exam.objects.select_related("bank"), pk=pk, owner=request.user)


def _is_final(exam):
    return exam.status == Exam.Status.FINALIZED


@login_required
def exam_list(request):
    exams = Exam.objects.filter(owner=request.user).select_related("bank").order_by("-created_at")
    banks = QuestionBank.objects.filter(owner=request.user).order_by("name")
    return render(request, "exams/exam_list.html", {"exams": exams, "banks": banks})


@login_required
def exam_create(request, bank_pk):
    bank = get_object_or_404(QuestionBank, pk=bank_pk, owner=request.user)
    data = request.POST if request.method == "POST" else None
    form = ExamForm(data, bank=bank)
    if data is not None and form.is_valid():
        exam = form.save(owner=request.user)
        _flash(request, ok=True, notice="Exam saved. Now generate its versions.")
        return redirect("exams:detail", pk=exam.pk)
    return render(request, "exams/exam_form.html", {"form": form, "bank": bank, "title": "New exam"})


@login_required
def exam_edit(request, pk):
    exam = _own_exam(request, pk)
    if _is_final(exam):
        _flash(request, ok=False, notice="This exam is finalized and cannot be edited.")
        return redirect("exams:detail", pk=exam.pk)
    if exam.bank is None:
        _flash(request, ok=False, notice="Its question bank was deleted, so it cannot be edited.")
        return redirect("exams:detail", pk=exam.pk)
    data = request.POST if request.method == "POST" else None
    form = ExamForm(data, instance=exam, bank=exam.bank)
    if data is not None and form.is_valid():
        form.save()
        _flash(request, ok=True, notice="Settings saved. Regenerate the versions to apply them.")
        return redirect("exams:detail", pk=exam.pk)
    return render(request, "exams/exam_form.html",
                  {"form": form, "bank": exam.bank, "title": f"Edit: {exam.title}"})


@login_required
def exam_detail(request, pk):
    exam = _own_exam(request, pk)
    flash = request.session.pop(FLASH_KEY, None)
    run = exam.generation_runs.order_by("-created_at").first()
    versions = list(exam.versions.order_by("sequence"))
    finalized = _is_final(exam)
    # Stale = settings were saved after the last generation.
    stale = bool(versions) and (run is None or exam.updated_at > run.created_at)

    overlap_rows, mean_pct, max_pct = [], None, None
    if run:
        overlap_rows = [
            {**o, "pct": round(o["jaccard"] * 100, 1)} for o in (run.overlaps or [])
        ]
        if run.mean_jaccard is not None:
            mean_pct = round(run.mean_jaccard * 100, 1)
        if run.max_jaccard is not None:
            max_pct = round(run.max_jaccard * 100, 1)

    return render(request, "exams/exam_detail.html", {
        "exam": exam, "flash": flash, "run": run, "versions": versions,
        "requirements": exam.topic_requirements.order_by("topic_name"),
        "difficulty": exam.difficulty_required(),
        "finalized": finalized, "stale": stale,
        "can_finalize": bool(versions) and not stale and not finalized,
        "overlap_rows": overlap_rows, "mean_pct": mean_pct, "max_pct": max_pct,
    })


@login_required
@require_POST
def exam_generate(request, pk):
    exam = _own_exam(request, pk)
    try:
        outcome = generate_exam_versions(exam)
    except ExamFinalizedError:
        _flash(request, ok=False, notice="This exam is finalized and cannot be regenerated.")
        return redirect("exams:detail", pk=exam.pk)
    except SnapshotMismatchError:
        _flash(request, ok=False,
               notice="The question bank changed while generating. Nothing was changed. Please try again.")
        return redirect("exams:detail", pk=exam.pk)
    if outcome.success:
        _flash(request, ok=True, notice=f"Generated {len(outcome.versions)} version(s).",
               warnings=outcome.warnings, excluded=outcome.excluded)
    else:
        _flash(request, ok=False, notice="Nothing was changed.",
               problems=outcome.problems, warnings=outcome.warnings, excluded=outcome.excluded)
    return redirect("exams:detail", pk=exam.pk)


@login_required
@require_POST
def exam_finalize(request, pk):
    exam = _own_exam(request, pk)
    if _is_final(exam):
        return redirect("exams:detail", pk=exam.pk)
    run = exam.generation_runs.order_by("-created_at").first()
    if not exam.versions.exists():
        _flash(request, ok=False, notice="Generate versions before finalizing.")
    elif run is None or exam.updated_at > run.created_at:
        _flash(request, ok=False, notice="Settings changed since the last generation. Regenerate first.")
    else:
        exam.finalize()
        _flash(request, ok=True, notice="Exam finalized. Its versions and keys are now locked.")
    return redirect("exams:detail", pk=exam.pk)


@login_required
def version_detail(request, pk):
    version = get_object_or_404(
        ExamVersion.objects.select_related("exam"), pk=pk, exam__owner=request.user)
    items = list(
        version.items.order_by("position").prefetch_related(
            Prefetch("choices", queryset=VersionChoice.objects.order_by("display_label"))
        )
    )
    return render(request, "exams/version_detail.html", {
        "version": version, "exam": version.exam, "items": items,
        "show_key": request.GET.get("key") == "1",
        "topic_dist": sorted(Counter(i.topic_name for i in items).items()),
        "difficulty_dist": sorted(Counter(i.difficulty for i in items).items()),
    })