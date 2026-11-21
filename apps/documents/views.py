import math

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404

from apps.exams.models import Exam, ExamVersion

from . import booklet, loaders, pdf

MAX_COPIES = 500
MAX_START_SERIAL = 100000
NOT_FINAL = "Finalize the exam before downloading PDFs, so printed papers always match the saved key."


def _pdf(data, filename, private=False):
    response = HttpResponse(data, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    if private:
        response["Cache-Control"] = "no-store"
    return response


def _owned_version(request, pk):
    # Ownership check: the version's exam must belong to the logged-in user.
    return get_object_or_404(
        ExamVersion.objects.select_related("exam"), pk=pk, exam__owner=request.user
    )


def _is_final(exam):
    return exam.status == Exam.Status.FINALIZED


def _positive_int(request, name, default):
    try:
        value = int(request.GET.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(value, 1)


def _copies(request, exam):
    default = max(1, math.ceil(exam.num_students / exam.num_versions))
    return min(_positive_int(request, "copies", default), MAX_COPIES)


def _start_serial(request):
    return min(_positive_int(request, "start", 1), MAX_START_SERIAL)


@login_required
def paper_pdf(request, pk):
    version = _owned_version(request, pk)
    if not _is_final(version.exam):
        return HttpResponseForbidden(NOT_FINAL)
    data = pdf.build_exam_paper(loaders.exam_doc(version.exam), loaders.version_doc(version))
    return _pdf(data, f"exam-{version.code}.pdf")


@login_required
def sheets_pdf(request, pk):
    version = _owned_version(request, pk)
    exam = version.exam
    if not _is_final(exam):
        return HttpResponseForbidden(NOT_FINAL)
    data = pdf.build_answer_sheets(
        loaders.exam_doc(exam), loaders.version_doc(version),
        _copies(request, exam), start_serial=_start_serial(request),
    )
    return _pdf(data, f"answer-sheets-{version.code}.pdf")


@login_required
def key_pdf(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk, owner=request.user)
    if not _is_final(exam):
        return HttpResponseForbidden(NOT_FINAL)
    versions = [loaders.version_doc(v) for v in exam.versions.order_by("sequence")]
    data = pdf.build_answer_key(loaders.exam_doc(exam), versions)
    return _pdf(data, f"answer-key-exam-{exam.pk}.pdf", private=True)

@login_required
def copies_pdf(request, pk):
    version = _owned_version(request, pk)
    exam = version.exam
    if not _is_final(exam):
        return HttpResponseForbidden(NOT_FINAL)
    data = booklet.build_student_copies(
        loaders.exam_doc(exam), loaders.version_doc(version), _copies(request, exam)
    )
    return _pdf(data, f"student-copies-{version.code}.pdf")