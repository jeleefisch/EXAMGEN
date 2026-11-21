import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.omr.models import SheetScan
from apps.omr.tests import add_version, make_exam, photo_file

from .models import GradeResult
from .services import GradingError, grade_scan

TMP = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TMP)
class GradingTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("g1", password="x")
        self.other = User.objects.create_user("g2", password="x")
        self.client.force_login(self.user)
        self.types = ["MC", "MC", "TF", "MC", "MC", "MC"]
        self.exam = make_exam(self.user)
        add_version(self.exam, "G1-A", 1, self.types)   # every key is "A"
        marks = [(1, "A", 0.85), (3, "B", 0.85), (4, "CD", 0.85)]
        self.client.post(reverse("omr:upload", args=[self.exam.pk]),
                         {"photos": photo_file("G1-A", 1, self.types, marks)})
        self.scan = SheetScan.objects.get()

    def resolve(self, code):
        self.client.post(reverse("omr:detail", args=[self.scan.pk]),
                         {"action": "resolve", "item_4": code})

    def test_unresolved_sheet_is_not_graded(self):
        with self.assertRaises(GradingError):
            grade_scan(self.scan)
        self.client.post(reverse("grading:results", args=[self.exam.pk]), {"action": "grade_all"})
        self.assertEqual(GradeResult.objects.count(), 0)

    def test_grades_against_the_sheets_own_key(self):
        self.resolve("A")
        grade = grade_scan(self.scan)
        self.assertEqual((grade.score, grade.max_score), (2, 6))
        self.assertEqual((grade.correct_count, grade.wrong_count, grade.blank_count), (2, 1, 3))

    def test_grade_all_page_detail_and_csv(self):
        self.resolve("A")
        url = reverse("grading:results", args=[self.exam.pk])
        self.client.post(url, {"action": "grade_all"})
        grade = GradeResult.objects.get()
        self.assertEqual(grade.score, 2)
        self.assertContains(self.client.get(url), "G1-A")
        self.assertEqual(self.client.get(reverse("grading:result", args=[grade.pk])).status_code, 200)
        self.client.post(reverse("grading:result", args=[grade.pk]), {"student_label": "=cmd"})
        resp = self.client.get(reverse("grading:csv", args=[self.exam.pk]))
        self.assertTrue(resp["Content-Type"].startswith("text/csv"))
        body = resp.content.decode()
        self.assertIn("G1-A", body)
        self.assertIn("'=cmd", body)
        self.assertNotIn(",=cmd", body)

    def test_changing_a_decision_removes_the_old_grade(self):
        self.resolve("A")
        grade_scan(self.scan)
        self.assertEqual(GradeResult.objects.count(), 1)
        self.resolve("B")
        self.assertEqual(GradeResult.objects.count(), 0)

    def test_other_user_gets_404(self):
        self.resolve("A")
        grade = grade_scan(self.scan)
        self.client.force_login(self.other)
        for name, arg in [("grading:results", self.exam.pk),
                          ("grading:csv", self.exam.pk),
                          ("grading:result", grade.pk)]:
            self.assertEqual(self.client.get(reverse(name, args=[arg])).status_code, 404)