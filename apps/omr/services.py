"""Read an uploaded sheet photo and store what the reader saw. No grading here."""
import cv2
import numpy as np
from django.db import transaction

from core import sheet_layout as L
from core.omr_erasure import flag_erasures
from core.omr_reader import OMRError, code_of, read_sheet

from apps.grading.models import GradeResult

from .models import ScanItem, SheetScan


def _choices(version):
    return [L.choices_for(i.qtype) for i in version.items.order_by("position")]


def _load_image(scan):
    scan.image.open("rb")
    try:
        data = scan.image.read()
    finally:
        scan.image.close()
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def _fail(scan, message):
    with transaction.atomic():
        scan.items.all().delete()
        GradeResult.objects.filter(scan=scan).delete()
        scan.status = SheetScan.Status.UNREADABLE
        scan.error = message[:300]
        scan.version = None
        scan.serial = None
        scan.qr_ok = False
        scan.warnings = []
        scan.save()
    return scan


def process_scan(scan, version=None, serial=None):
    """Read scan.image and (re)write its items.

    version/serial are only passed when a person chose them by hand
    (the QR could not be used).
    """
    versions = list(scan.exam.versions.order_by("sequence"))
    if not versions:
        return _fail(scan, "This exam has no versions.")
    by_code = {v.code: v for v in versions}

    image = _load_image(scan)
    if image is None:
        return _fail(scan, "Could not open this file as an image. "
                           "Use JPEG or PNG (HEIC is not supported).")
    try:
        if version is not None:
            chosen = version
            used = _choices(chosen)
            res = read_sheet(image, used)
        else:
            used = _choices(versions[0])        # pass 1: just to find the QR
            res = read_sheet(image, used)
            chosen = by_code.get(res.version_code) if res.qr_ok else None
            if chosen is not None:
                wanted = _choices(chosen)
                if wanted != used:              # pass 2: the right bubble layout
                    used = wanted
                    res = read_sheet(image, used)
    except (OMRError, ValueError) as e:
        return _fail(scan, f"Sheet could not be read: {e}")

    flag_erasures(res)                           # D-016
    warnings = [str(w) for w in res.warnings]
    if version is not None:
        if res.qr_ok and res.version_code != version.code:
            warnings.append(f"The QR says {res.version_code}, but you chose {version.code}.")
        sheet_serial = serial
    else:
        sheet_serial = res.serial if res.qr_ok else None
    if chosen is not None and sheet_serial is not None:
        dup = SheetScan.objects.filter(
            exam=scan.exam, version=chosen, serial=sheet_serial).exclude(pk=scan.pk).exists()
        if dup:
            warnings.append(f"Another scan of {chosen.code} sheet {sheet_serial} already exists.")

    with transaction.atomic():
        scan.items.all().delete()
        GradeResult.objects.filter(scan=scan).delete()
        scan.version = chosen
        scan.serial = sheet_serial
        scan.qr_ok = bool(res.qr_ok)
        scan.rotation_steps = res.rotation_steps
        scan.warnings = warnings
        scan.error = ""
        scan.status = SheetScan.Status.READ if chosen else SheetScan.Status.NEEDS_VERSION
        scan.save()
        ScanItem.objects.bulk_create([
            ScanItem(
                scan=scan, item=r.item, choices_count=used[r.item - 1],
                status=r.status, detected=code_of(r)[:10],
                ratios=[round(float(x), 3) for x in r.ratios])
            for r in res.items
        ])
    return scan


def apply_resolutions(scan, mapping):
    """mapping: {item_number: code}. Empty codes are skipped. Returns a list of error texts."""
    errors = []
    for it in scan.items.all():
        if it.item not in mapping:
            continue
        code = (mapping[it.item] or "").strip().upper()
        if not code:
            continue
        if code not in it.valid_codes():
            errors.append(f"Item {it.item}: '{code}' is not a valid answer.")
            continue
        it.resolved = code
        it.save(update_fields=["resolved"])
        GradeResult.objects.filter(scan=scan).delete()
    return errors