import mimetypes

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.exams.models import Exam

from . import services
from .models import SheetScan

MAX_FILES = 40
MAX_BYTES = 15 * 1024 * 1024
SAFE_IMAGE_TYPES = {"image/jpeg", "image/png"}


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _own_scan(request, pk):
    return get_object_or_404(
        SheetScan.objects.select_related("exam", "version"),
        pk=pk, exam__owner=request.user)


@login_required
def scan_list(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk, owner=request.user)
    scans = list(exam.scans.select_related("version").prefetch_related("items"))
    return render(request, "omr/scan_list.html", {"exam": exam, "scans": scans})


@login_required
def scan_upload(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk, owner=request.user)
    if not exam.is_finalized:
        messages.error(request, "Finalize the exam before scanning sheets.")
        return redirect(f"/exams/{exam.pk}/")
    if request.method == "POST":
        files = request.FILES.getlist("photos")
        if not files:
            messages.error(request, "Choose at least one photo.")
        else:
            if len(files) > MAX_FILES:
                messages.warning(request, f"Only the first {MAX_FILES} photos were used.")
            created = []
            for f in files[:MAX_FILES]:
                if f.size > MAX_BYTES:
                    messages.warning(request, f"{f.name} is larger than 15 MB and was skipped.")
                    continue
                scan = SheetScan.objects.create(
                    exam=exam, uploaded_by=request.user, image=f, original_name=f.name[:255])
                services.process_scan(scan)
                created.append(scan)
            if len(created) == 1:
                return redirect("omr:detail", pk=created[0].pk)
            if created:
                return redirect("omr:list", exam_pk=exam.pk)
    return render(request, "omr/scan_upload.html", {"exam": exam})


@login_required
def scan_detail(request, pk):
    scan = _own_scan(request, pk)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "version":
            version = scan.exam.versions.filter(pk=_int(request.POST.get("version")) or 0).first()
            if version is None:
                messages.error(request, "Choose a version.")
            else:
                serial = _int(request.POST.get("serial"))
                if serial is not None and not 1 <= serial <= 100000:
                    serial = None
                services.process_scan(scan, version=version, serial=serial)
                messages.success(request, "Sheet re-read with the version you chose.")
        elif action == "resolve":
            mapping = {}
            for key, val in request.POST.items():
                if key.startswith("item_"):
                    n = _int(key[5:])
                    if n is not None:
                        mapping[n] = val
            errors = services.apply_resolutions(scan, mapping)
            for e in errors:
                messages.error(request, e)
            if not errors:
                messages.success(request, "Review saved.")
        return redirect("omr:detail", pk=scan.pk)

    rows = [{"obj": it, "options": it.valid_codes()} for it in scan.items.all()]
    versions = scan.exam.versions.order_by("sequence")
    return render(request, "omr/scan_detail.html",
                  {"scan": scan, "rows": rows, "versions": versions})


@login_required
def scan_image(request, pk):
    scan = _own_scan(request, pk)
    ctype = mimetypes.guess_type(scan.original_name)[0]
    if ctype not in SAFE_IMAGE_TYPES:
        ctype = "application/octet-stream"
    resp = FileResponse(scan.image.open("rb"), content_type=ctype)
    resp["Cache-Control"] = "private, no-store"
    resp["X-Content-Type-Options"] = "nosniff"
    return resp