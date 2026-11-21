import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.exams.models import Exam

from .models import GradeResult
from .services import GradingError, grade_scan


def _safe(value):
    """Stop spreadsheet formulas: text starting with = + - @ gets a leading apostrophe."""
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def _exam(request, pk):
    return get_object_or_404(Exam, pk=pk, owner=request.user)


@login_required
def results(request, exam_pk):
    exam = _exam(request, exam_pk)
    scans = list(
        exam.scans.select_related("version", "grade").prefetch_related("items")
        .order_by("version__sequence", "serial", "id"))

    if request.method == "POST" and request.POST.get("action") == "grade_all":
        done = skipped = 0
        for s in scans:
            if getattr(s, "grade", None) is not None:
                continue
            try:
                grade_scan(s)
                done += 1
            except GradingError:
                skipped += 1
        if done:
            messages.success(request, f"Graded {done} sheet(s).")
        if skipped:
            messages.warning(request, f"{skipped} sheet(s) are not ready (open them to resolve).")
        return redirect("grading:results", exam_pk=exam.pk)

    rows = [{"scan": s, "grade": getattr(s, "grade", None), "ready": s.is_ready} for s in scans]
    grades = [r["grade"] for r in rows if r["grade"] is not None]
    mean = round(sum(g.percent for g in grades) / len(grades), 1) if grades else None
    return render(request, "grading/results.html", {
        "exam": exam, "rows": rows, "graded_count": len(grades), "mean_percent": mean})


@login_required
def result_detail(request, pk):
    grade = get_object_or_404(
        GradeResult.objects.select_related("scan__exam", "scan__version"),
        pk=pk, scan__exam__owner=request.user)
    if request.method == "POST":
        grade.student_label = request.POST.get("student_label", "").strip()[:120]
        grade.save(update_fields=["student_label", "graded_at"])
        messages.success(request, "Saved.")
        return redirect("grading:result", pk=grade.pk)
    return render(request, "grading/result_detail.html", {"grade": grade, "scan": grade.scan})


@login_required
def results_csv(request, exam_pk):
    exam = _exam(request, exam_pk)
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="exam-{exam.pk}-results.csv"'
    resp["Cache-Control"] = "private, no-store"
    resp.write("\ufeff")   # so Excel reads UTF-8 names correctly
    w = csv.writer(resp)
    w.writerow(["Exam", "Version", "Sheet", "Student", "Score", "Max", "Percent",
                "Correct", "Wrong", "Blank"])
    grades = (GradeResult.objects.filter(scan__exam=exam)
              .select_related("scan__version").order_by("scan__version__sequence", "scan__serial", "id"))
    for g in grades:
        w.writerow([_safe(exam.title), _safe(g.scan.version.code if g.scan.version else ""),
                    g.scan.serial or "", _safe(g.student_label), g.score, g.max_score,
                    g.percent, g.correct_count, g.wrong_count, g.blank_count])
    return resp