import shutil
import tempfile
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.banks.models import Question, QuestionBank, Topic
from apps.exams.models import Exam
from apps.omr.models import SheetScan
from apps.omr.tests import add_version, make_exam, photo_file

from .models import GradeResult

TMP = tempfile.mkdtemp()


def make_question(user):
    bank = QuestionBank.objects.create(owner=user, name="B")
    topic = Topic.objects.create(bank=bank, name="T")
    q = Question.objects.create(bank=bank, topic=topic, text="Q?")
    return bank, q


@override_settings(MEDIA_ROOT=TMP)
class Phase9Tests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("p1", password="x")
        self.other = User.objects.create_user("p2", password="x")
        self.client.force_login(self.user)

    def test_delete_question_needs_post_and_owner(self):
        bank, q = make_question(self.user)
        url = reverse("banks:question_delete", args=[q.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(Question.objects.filter(pk=q.pk).exists())   # GET never deletes
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(Question.objects.filter(pk=q.pk).exists())
        self.client.force_login(self.user)
        self.client.post(url)
        self.assertFalse(Question.objects.filter(pk=q.pk).exists())

    def test_delete_bank_keeps_existing_exams(self):
        bank, q = make_question(self.user)
        exam = make_exam(self.user)
        Exam.objects.filter(pk=exam.pk).update(bank=bank)
        url = reverse("banks:bank_delete", args=[bank.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.user)
        self.client.post(url)
        self.assertFalse(QuestionBank.objects.filter(pk=bank.pk).exists())
        exam.refresh_from_db()
        self.assertIsNone(exam.bank)

    def test_profile_saves_and_requires_login(self):
        url = reverse("accounts:profile")
        self.client.post(url, {"first_name": "Ana", "last_name": "Cruz", "email": "a@x.com"})
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.email), ("Ana", "a@x.com"))
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def _two_graded_sheets(self):
        types = ["MC", "MC", "TF", "MC"]
        exam = make_exam(self.user)
        add_version(exam, "P9-A", 1, types)
        up = reverse("omr:upload", args=[exam.pk])
        for serial in (1, 2):
            self.client.post(up, {"photos": photo_file("P9-A", serial, types,
                                                       [(1, "A", 0.85)], seed=serial)})
        url = reverse("grading:results", args=[exam.pk])
        self.client.post(url, {"action": "grade_all"})
        return exam, url

    def test_search_filters_rows_but_not_statistics(self):
        exam, url = self._two_graded_sheets()
        g = GradeResult.objects.order_by("scan__serial").first()
        self.client.post(reverse("grading:result", args=[g.pk]), {"student_label": "Ana Cruz"})
        ctx = self.client.get(url + "?q=ana").context
        self.assertEqual(len(ctx["rows"]), 1)
        self.assertEqual(ctx["graded_count"], 2)          # statistics ignore the search
        self.assertEqual(len(self.client.get(url + "?q=zzz").context["rows"]), 0)
        self.assertEqual(len(self.client.get(url + "?q=P9-A").context["rows"]), 2)
        self.assertEqual(len(self.client.get(url).context["rows"]), 2)

    def test_purge_is_dry_run_without_yes(self):
        exam, _ = self._two_graded_sheets()
        call_command("purge_user_data", "p1", stdout=StringIO())
        self.assertEqual(SheetScan.objects.count(), 2)

    def test_purge_deletes_only_that_users_data(self):
        self._two_graded_sheets()
        make_question(self.user)
        other_exam = make_exam(self.other)
        call_command("purge_user_data", "p1", "--yes", stdout=StringIO())
        self.assertEqual(SheetScan.objects.count(), 0)
        self.assertEqual(GradeResult.objects.count(), 0)
        self.assertEqual(QuestionBank.objects.filter(owner=self.user).count(), 0)
        self.assertTrue(Exam.objects.filter(pk=other_exam.pk).exists())
        self.assertTrue(get_user_model().objects.filter(username="p1").exists())