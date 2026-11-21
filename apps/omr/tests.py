from django.test import TestCase

# Create your tests here.
import shutil
import tempfile

import cv2
import numpy as np
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.exams.models import Exam, ExamVersion, VersionQuestion
from spike.synth import photograph, render_sheet, shade

from .models import SheetScan

TMP = tempfile.mkdtemp()
LETTERS = "ABCD"


def make_exam(owner, finalized=True):
    return Exam.objects.create(
        owner=owner, title="Quiz", subject="S", total_questions=6, easy_count=6,
        status=Exam.Status.FINALIZED if finalized else Exam.Status.DRAFT,
        finalized_at=timezone.now() if finalized else None)


def add_version(exam, code, seq, types):
    v = ExamVersion.objects.create(exam=exam, code=code, sequence=seq, seed="1")
    for pos, t in enumerate(types, start=1):
        VersionQuestion.objects.create(
            version=v, position=pos, text=f"Q{pos}", qtype=t, topic_name="T",
            difficulty="easy", points=1, correct_label="A")
    return v


def photo_file(code, serial, types, marks, seed=3):
    """marks: list of (item, 'AB', fill). Returns an uploadable JPEG of a synthetic photo."""
    rng = np.random.default_rng(seed)
    choices = [2 if t == "TF" else 4 for t in types]
    page = render_sheet(choices, code, serial)
    for item, letters, fill in marks:
        for ch in letters:
            shade(page, item, LETTERS.index(ch), fill, rng)
    photo = photograph(page, rng, tilt=0.5, rotate_deg=2.0, light=0.1, noise=2.0, blur=0.8)
    ok, buf = cv2.imencode(".jpg", photo)
    assert ok
    return SimpleUploadedFile("sheet.jpg", buf.tobytes(), "image/jpeg")


@override_settings(MEDIA_ROOT=TMP)
class ScanTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("u1", password="x")
        self.other = User.objects.create_user("u2", password="x")
        self.client.force_login(self.user)
        self.types = ["MC", "MC", "TF", "MC", "MC", "MC"]
        self.exam = make_exam(self.user)
        self.v1 = add_version(self.exam, "T1-A", 1, self.types)

    def upload(self, f):
        return self.client.post(reverse("omr:upload", args=[self.exam.pk]), {"photos": f})

    def test_upload_reads_marks_and_shows_page(self):
        marks = [(1, "A", 0.85), (3, "B", 0.85), (4, "CD", 0.85)]
        resp = self.upload(photo_file("T1-A", 5, self.types, marks))
        scan = SheetScan.objects.get()
        self.assertRedirects(resp, reverse("omr:detail", args=[scan.pk]))
        self.assertEqual(scan.status, SheetScan.Status.READ)
        self.assertEqual((scan.version, scan.serial), (self.v1, 5))
        got = {i.item: (i.status, i.detected) for i in scan.items.all()}
        self.assertEqual(got[1], ("selected", "A"))
        self.assertEqual(got[2], ("blank", "-"))
        self.assertEqual(got[3], ("selected", "B"))
        self.assertEqual(got[4], ("multiple", "CD"))
        page = self.client.get(reverse("omr:detail", args=[scan.pk]))
        self.assertContains(page, "Read as")   # fails if base.html's block name differs

    def test_second_pass_uses_true_false_layout_of_the_qr_version(self):
        types2 = ["MC", "MC", "MC", "TF", "MC", "MC"]
        v2 = add_version(self.exam, "T1-B", 2, types2)
        self.upload(photo_file("T1-B", 7, types2, [(4, "B", 0.85)]))
        scan = SheetScan.objects.get()
        self.assertEqual(scan.version, v2)
        item4 = scan.items.get(item=4)
        self.assertEqual(item4.choices_count, 2)
        self.assertEqual(item4.detected, "B")

    def test_unknown_version_needs_manual_choice_then_rereads(self):
        self.upload(photo_file("ZZ-9", 3, self.types, [(1, "A", 0.85)]))
        scan = SheetScan.objects.get()
        self.assertEqual(scan.status, SheetScan.Status.NEEDS_VERSION)
        self.client.post(reverse("omr:detail", args=[scan.pk]),
                         {"action": "version", "version": self.v1.pk, "serial": "5"})
        scan.refresh_from_db()
        self.assertEqual(scan.status, SheetScan.Status.READ)
        self.assertEqual((scan.version, scan.serial), (self.v1, 5))

    def test_resolving_uncertain_rows_makes_scan_ready(self):
        self.upload(photo_file("T1-A", 5, self.types, [(1, "A", 0.85), (4, "CD", 0.85)]))
        scan = SheetScan.objects.get()
        self.assertFalse(scan.is_ready)
        url = reverse("omr:detail", args=[scan.pk])
        self.client.post(url, {"action": "resolve", "item_4": "Z"})   # invalid: rejected
        self.assertFalse(scan.items.get(item=4).resolved)
        self.client.post(url, {"action": "resolve", "item_4": "C"})
        scan = SheetScan.objects.get()
        self.assertEqual(scan.items.get(item=4).final, "C")
        self.assertEqual(scan.items.get(item=4).detected, "CD")   # machine reading untouched
        self.assertTrue(scan.is_ready)

    def test_garbage_upload_is_reported_not_crashed(self):
        self.upload(SimpleUploadedFile("x.jpg", b"not an image", "image/jpeg"))
        scan = SheetScan.objects.get()
        self.assertEqual(scan.status, SheetScan.Status.UNREADABLE)
        self.assertIn("Could not open", scan.error)

    def test_other_users_get_404(self):
        self.upload(photo_file("T1-A", 5, self.types, [(1, "A", 0.85)]))
        scan = SheetScan.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("omr:detail", args=[scan.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("omr:image", args=[scan.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("omr:list", args=[self.exam.pk])).status_code, 404)

    def test_draft_exam_cannot_receive_scans(self):
        draft = make_exam(self.user, finalized=False)
        self.client.post(reverse("omr:upload", args=[draft.pk]),
                         {"photos": SimpleUploadedFile("x.jpg", b"x", "image/jpeg")})
        self.assertEqual(SheetScan.objects.count(), 0)

    def test_list_page_renders(self):
        self.upload(photo_file("T1-A", 5, self.types, [(1, "A", 0.85)]))
        resp = self.client.get(reverse("omr:list", args=[self.exam.pk]))
        self.assertContains(resp, "sheet.jpg")    