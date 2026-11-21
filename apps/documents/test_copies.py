from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.banks.models import QuestionBank, Topic
from apps.exams.models import Exam, ExamTopicRequirement, ExamVersion
from apps.exams.services import generate_exam_versions
from apps.exams.test_services import make_question

from .test_pdf import pages


class StudentCopiesViewTests(TestCase):
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
            num_students=6, num_versions=2, total_questions=9,
            easy_count=3, moderate_count=3, difficult_count=3, points_per_question=1,
        )
        for name in "ABC":
            ExamTopicRequirement.objects.create(exam=self.exam, topic_name=name, count=3)
        generate_exam_versions(self.exam)
        self.version = ExamVersion.objects.filter(exam=self.exam).first()
        self.url = reverse("documents:copies", args=[self.version.pk])
        self.client.login(username="prof", password="x")

    def test_draft_is_forbidden(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_finalized_downloads_a_pdf(self):
        self.exam.finalize()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_copies_parameter_scales_the_page_count(self):
        self.exam.finalize()
        one = pages(self.client.get(self.url + "?copies=1").content)
        three = pages(self.client.get(self.url + "?copies=3").content)
        default = pages(self.client.get(self.url).content)  # 6 students / 2 versions = 3
        self.assertEqual(three, 3 * one)
        self.assertEqual(default, three)

    def test_other_users_get_404_and_anonymous_is_redirected(self):
        self.exam.finalize()
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.login(username="intruder", password="x")
        self.assertEqual(self.client.get(self.url).status_code, 404)