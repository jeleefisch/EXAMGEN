from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.banks.models import QuestionBank, Topic

from .models import Exam, ExamTopicRequirement, ExamVersion
from .services import generate_exam_versions
from .test_services import make_question


class ExamViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("prof", password="x")
        User.objects.create_user("intruder", password="x")
        self.bank = QuestionBank.objects.create(owner=self.user, name="Bank")
        self.topics = {n: Topic.objects.create(bank=self.bank, name=n) for n in "ABC"}
        for topic in self.topics.values():
            for diff in ("Easy", "Moderate", "Difficult"):
                for i in range(4):
                    make_question(self.bank, topic, diff, i, correct_pos=(i % 4) + 1)
        self.exam = Exam.objects.create(
            owner=self.user, bank=self.bank, title="Midterm", subject="Math",
            num_students=30, num_versions=2, total_questions=9,
            easy_count=3, moderate_count=3, difficult_count=3, points_per_question=1,
        )
        for n in "ABC":
            ExamTopicRequirement.objects.create(exam=self.exam, topic_name=n, count=3)
        self.client.login(username="prof", password="x")

    def valid_post(self, **overrides):
        data = {
            "title": "Final", "subject": "Math", "institution_name": "",
            "num_students": 30, "num_versions": 2, "total_questions": 9,
            "easy_count": 3, "moderate_count": 3, "difficult_count": 3,
            "points_per_question": 1, "shuffle_choices": "on",
            "shuffle_questions": "on", "max_similarity": "",
        }
        for t in self.topics.values():
            data[f"topic_{t.pk}"] = 3
        data.update(overrides)
        return data

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()
        resp = self.client.get(reverse("exams:list"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_create_valid_exam_saves_exam_and_topic_requirements(self):
        resp = self.client.post(reverse("exams:create", args=[self.bank.pk]), self.valid_post())
        exam = Exam.objects.get(title="Final")
        self.assertRedirects(resp, reverse("exams:detail", args=[exam.pk]))
        self.assertEqual(exam.owner, self.user)
        self.assertEqual(exam.bank, self.bank)
        self.assertEqual(exam.topic_requirements.count(), 3)

    def test_create_rejects_topic_quotas_that_do_not_sum_to_total(self):
        before = Exam.objects.count()
        data = self.valid_post()
        data[f"topic_{self.topics['A'].pk}"] = 4  # 4+3+3 = 10, total is 9
        resp = self.client.post(reverse("exams:create", args=[self.bank.pk]), data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Exam.objects.count(), before)

    def test_create_rejects_impossible_config_with_explanation(self):
        before = Exam.objects.count()
        data = self.valid_post(total_questions=15, easy_count=5, moderate_count=5, difficult_count=5)
        data[f"topic_{self.topics['A'].pk}"] = 15  # topic A only has 12 questions
        data[f"topic_{self.topics['B'].pk}"] = 0
        data[f"topic_{self.topics['C'].pk}"] = 0
        resp = self.client.post(reverse("exams:create", args=[self.bank.pk]), data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Exam.objects.count(), before)
        self.assertContains(resp, "not possible")

    def test_edit_updates_settings_and_requirements(self):
        resp = self.client.post(reverse("exams:edit", args=[self.exam.pk]), self.valid_post(title="Renamed"))
        self.assertRedirects(resp, reverse("exams:detail", args=[self.exam.pk]))
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.title, "Renamed")
        self.assertEqual(self.exam.topic_requirements.count(), 3)

    def test_other_users_get_404_everywhere(self):
        generate_exam_versions(self.exam)
        version = ExamVersion.objects.filter(exam=self.exam).first()
        self.client.logout()
        self.client.login(username="intruder", password="x")
        for name, arg in [("detail", self.exam.pk), ("edit", self.exam.pk), ("version", version.pk)]:
            self.assertEqual(self.client.get(reverse(f"exams:{name}", args=[arg])).status_code, 404, name)
        for name in ("generate", "finalize"):
            self.assertEqual(self.client.post(reverse(f"exams:{name}", args=[self.exam.pk])).status_code, 404, name)
        self.assertEqual(self.client.get(reverse("exams:create", args=[self.bank.pk])).status_code, 404)

    def test_generate_button_creates_versions(self):
        resp = self.client.post(reverse("exams:generate", args=[self.exam.pk]))
        self.assertRedirects(resp, reverse("exams:detail", args=[self.exam.pk]))
        self.assertEqual(ExamVersion.objects.filter(exam=self.exam).count(), 2)

    def test_finalize_needs_versions_then_locks_the_exam(self):
        url = reverse("exams:finalize", args=[self.exam.pk])
        self.client.post(url)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.status, Exam.Status.DRAFT)  # nothing generated yet
        generate_exam_versions(self.exam)
        self.client.post(url)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.status, Exam.Status.FINALIZED)

    def test_finalized_exam_cannot_be_edited_or_regenerated(self):
        generate_exam_versions(self.exam)
        self.client.post(reverse("exams:finalize", args=[self.exam.pk]))
        before = set(ExamVersion.objects.filter(exam=self.exam).values_list("id", flat=True))
        self.client.post(reverse("exams:edit", args=[self.exam.pk]), self.valid_post(title="Hacked"))
        self.client.post(reverse("exams:generate", args=[self.exam.pk]))
        self.exam.refresh_from_db()
        after = set(ExamVersion.objects.filter(exam=self.exam).values_list("id", flat=True))
        self.assertEqual(self.exam.title, "Midterm")
        self.assertEqual(before, after)

    def test_answer_key_only_shown_when_requested(self):
        generate_exam_versions(self.exam)
        version = ExamVersion.objects.filter(exam=self.exam).first()
        url = reverse("exams:version", args=[version.pk])
        self.assertNotContains(self.client.get(url), 'id="answer-key"')
        self.assertContains(self.client.get(url + "?key=1"), 'id="answer-key"')