from django.test import TestCase

# Create your tests here.
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.banks.models import QuestionBank, Topic
from apps.exams.models import Exam, ExamTopicRequirement, ExamVersion, VersionQuestion
from apps.exams.services import generate_exam_versions
from apps.exams.test_services import make_question

from .test_pdf import pages


class DocumentViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("prof", password="x")
        User.objects.create_user("intruder", password="x")
        bank = QuestionBank.objects.create(owner=self.user, name="Bank")
        for name in "ABC":
            topic = Topic.objects.create(bank=bank, name=name)
            for diff in ("Easy", "Moderate", "Difficult"):
                for i in range(4):
                    make_question(bank, topic, diff, i, correct_pos=(i % 4) + 1)
        self.exam = Exam.objects.create(
            owner=self.user, bank=bank, title="Midterm", subject="Math",
            num_students=30, num_versions=2, total_questions=9,
            easy_count=3, moderate_count=3, difficult_count=3, points_per_question=1,
        )
        for name in "ABC":
            ExamTopicRequirement.objects.create(exam=self.exam, topic_name=name, count=3)
        generate_exam_versions(self.exam)
        self.version = ExamVersion.objects.filter(exam=self.exam).first()
        self.client.login(username="prof", password="x")

    def urls(self):
        return [
            reverse("documents:paper", args=[self.version.pk]),
            reverse("documents:sheets", args=[self.version.pk]),
            reverse("documents:key", args=[self.exam.pk]),
        ]

    def finalize(self):
        self.exam.finalize()

    def test_draft_exam_pdfs_are_forbidden(self):
        for url in self.urls():
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_finalized_exam_pdfs_download(self):
        self.finalize()
        for url in self.urls():
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertEqual(resp["Content-Type"], "application/pdf")
            self.assertTrue(resp.content.startswith(b"%PDF"), url)

    def test_answer_key_is_not_cached(self):
        self.finalize()
        self.assertEqual(self.client.get(self.urls()[2])["Cache-Control"], "no-store")

    def test_other_users_get_404(self):
        self.finalize()
        self.client.logout()
        self.client.login(username="intruder", password="x")
        for url in self.urls():
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_anonymous_users_are_redirected_to_login(self):
        self.finalize()
        self.client.logout()
        for url in self.urls():
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302, url)
            self.assertIn("login", resp.url)

    def test_sheet_copies_default_and_bad_values(self):
        self.finalize()
        base = reverse("documents:sheets", args=[self.version.pk])
        # 30 students / 2 versions = 15 sheets by default
        self.assertEqual(pages(self.client.get(base).content), 15)
        self.assertEqual(pages(self.client.get(base + "?copies=4").content), 4)
        self.assertEqual(pages(self.client.get(base + "?copies=0").content), 1)
        self.assertEqual(pages(self.client.get(base + "?copies=abc").content), 15)

    def test_special_characters_in_saved_text_do_not_break_the_paper(self):
        VersionQuestion.objects.filter(version=self.version).update(text="Is 3 < 5 & 2 > 1 <b>?")
        self.finalize()
        resp = self.client.get(reverse("documents:paper", args=[self.version.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b"%PDF"))