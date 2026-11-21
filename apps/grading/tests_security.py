"""Security checks for scans and grading: login, ownership, CSRF, CSV safety."""
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.omr.models import SheetScan
from apps.omr.tests import add_version, make_exam, photo_file

from .models import GradeResult
from .services import grade_scan

TMP = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TMP)
class SecurityTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("s1", password="x")
        self.other = User.objects.create_user("s2", password="x")
        self.client.force_login(self.user)
        self.types = ["MC", "MC", "TF", "MC", "MC", "MC"]
        self.exam = make_exam(self.user)
        add_version(self.exam, "SEC-A", 1, self.types)
        marks = [(1, "A", 0.85), (3, "B", 0.85)]          # nothing uncertain: sheet is ready
        self.client.post(reverse("omr:upload", args=[self.exam.pk]),
                         {"photos": photo_file("SEC-A", 1, self.types, marks)})
        self.scan = SheetScan.objects.get()
        self.grade = grade_scan(self.scan, student_label="Pat")

    def test_anonymous_users_are_sent_to_login(self):
        self.client.logout()
        targets = [
            ("get", reverse("omr:list", args=[self.exam.pk])),
            ("post", reverse("omr:upload", args=[self.exam.pk])),
            ("get", reverse("omr:detail", args=[self.scan.pk])),
            ("get", reverse("omr:image", args=[self.scan.pk])),
            ("get", reverse("grading:results", args=[self.exam.pk])),
            ("post", reverse("grading:results", args=[self.exam.pk])),
            ("get", reverse("grading:csv", args=[self.exam.pk])),
            ("get", reverse("grading:result", args=[self.grade.pk])),
            ("post", reverse("grading:result", args=[self.grade.pk])),
        ]
        for method, url in targets:
            resp = getattr(self.client, method)(url)
            self.assertEqual(resp.status_code, 302, f"{method.upper()} {url}")
            self.assertIn("login", resp["Location"].lower(), f"{method.upper()} {url}")

    def test_other_user_cannot_change_anything(self):
        self.client.force_login(self.other)
        # editing someone else's grade label
        resp = self.client.post(reverse("grading:result", args=[self.grade.pk]),
                                {"student_label": "Hacked"})
        self.assertEqual(resp.status_code, 404)
        self.grade.refresh_from_db()
        self.assertEqual(self.grade.student_label, "Pat")
        # grading someone else's exam
        GradeResult.objects.all().delete()
        resp = self.client.post(reverse("grading:results", args=[self.exam.pk]),
                                {"action": "grade_all"})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(GradeResult.objects.count(), 0)
        # resolving an item on someone else's scan
        resp = self.client.post(reverse("omr:detail", args=[self.scan.pk]),
                                {"action": "resolve", "item_2": "B"})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self.scan.items.get(item=2).resolved, "")
        # uploading into someone else's exam
        resp = self.client.post(reverse("omr:upload", args=[self.exam.pk]),
                                {"photos": photo_file("SEC-A", 2, self.types, [(1, "A", 0.85)])})
        self.assertIn(resp.status_code, (403, 404))
        self.assertEqual(SheetScan.objects.count(), 1)

    def test_post_without_csrf_token_is_rejected(self):
        GradeResult.objects.all().delete()
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        resp = strict.post(reverse("grading:results", args=[self.exam.pk]),
                           {"action": "grade_all"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(GradeResult.objects.count(), 0)

    def test_get_requests_never_change_data(self):
        GradeResult.objects.all().delete()
        self.client.get(reverse("grading:results", args=[self.exam.pk]) + "?action=grade_all")
        self.assertEqual(GradeResult.objects.count(), 0)

    def test_csv_is_private_and_neutralises_formulas(self):
        self.exam.title = "=1+1"
        self.exam.save(update_fields=["title"])
        self.client.post(reverse("grading:result", args=[self.grade.pk]),
                         {"student_label": "+cmd"})
        resp = self.client.get(reverse("grading:csv", args=[self.exam.pk]))
        self.assertIn("no-store", resp["Cache-Control"])
        self.assertIn("attachment", resp["Content-Disposition"])
        body = resp.content.decode()
        self.assertIn("'=1+1", body)
        self.assertIn("'+cmd", body)
        self.assertNotIn(",+cmd", body)

    def test_scan_image_never_served_as_html(self):
        SheetScan.objects.filter(pk=self.scan.pk).update(original_name="evil.html")
        resp = self.client.get(reverse("omr:image", args=[self.scan.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/octet-stream")
        self.assertEqual(resp["X-Content-Type-Options"], "nosniff")