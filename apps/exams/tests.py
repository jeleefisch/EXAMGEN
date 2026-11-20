from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.db.models import RestrictedError

from apps.banks.models import Question, QuestionBank, Topic

from .models import (Exam, ExamTopicRequirement, ExamVersion, VersionQuestion)

User = get_user_model()


def make_exam(owner, **overrides):
    values = dict(owner=owner, title='Midterm', subject='Math',
                  total_questions=10, easy_count=4, moderate_count=4,
                  difficult_count=2)
    values.update(overrides)
    return Exam.objects.create(**values)


class ExamModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('prof', password='pw-12345-x')

    def test_new_exam_defaults(self):
        exam = make_exam(self.user)
        self.assertEqual(exam.status, Exam.Status.DRAFT)
        self.assertFalse(exam.is_finalized)
        self.assertIsNotNone(exam.base_seed)

    def test_difficulty_counts_must_add_up_to_total(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_exam(self.user, easy_count=1)

    def test_engine_dictionaries(self):
        exam = make_exam(self.user)
        ExamTopicRequirement.objects.create(
            exam=exam, topic_name='Algebra', count=6)
        ExamTopicRequirement.objects.create(
            exam=exam, topic_name='Geometry', count=4)
        self.assertEqual(exam.difficulty_required(),
                         {'Easy': 4, 'Moderate': 4, 'Difficult': 2})
        self.assertEqual(exam.topic_required(),
                         {'Algebra': 6, 'Geometry': 4})

    def test_finalize_sets_status_and_timestamp(self):
        exam = make_exam(self.user)
        exam.finalize()
        exam.refresh_from_db()
        self.assertTrue(exam.is_finalized)
        self.assertIsNotNone(exam.finalized_at)

    def test_version_codes_are_globally_unique(self):
        first = make_exam(self.user)
        second = make_exam(self.user, title='Final')
        ExamVersion.objects.create(exam=first, code='E1-A', sequence=1, seed='x')
        with self.assertRaises(IntegrityError), transaction.atomic():
            ExamVersion.objects.create(
                exam=second, code='E1-A', sequence=1, seed='y')


class SnapshotIntegrityTests(TestCase):
    """Changing the bank must never change an exam that was already made."""

    def setUp(self):
        self.user = User.objects.create_user('prof', password='pw-12345-x')
        self.bank = QuestionBank.objects.create(owner=self.user, name='Bank')
        self.topic = Topic.objects.create(bank=self.bank, name='Algebra')
        self.question = Question.objects.create(
            bank=self.bank, topic=self.topic, text='2 + 2 = 4',
            qtype='TF', difficulty='Easy')
        self.exam = make_exam(self.user, bank=self.bank)
        self.version = ExamVersion.objects.create(
            exam=self.exam, code='E1-A', sequence=1, seed='1:0:1')
        self.item = VersionQuestion.objects.create(
            version=self.version, position=1, source_question=self.question,
            text=self.question.text, qtype='TF', topic_name='Algebra',
            difficulty='Easy', points=1, correct_label='A')

    def test_editing_the_bank_question_does_not_change_the_snapshot(self):
        self.question.text = 'CHANGED'
        self.question.save()
        self.item.refresh_from_db()
        self.assertEqual(self.item.text, '2 + 2 = 4')

    def test_deleting_the_bank_question_keeps_the_snapshot(self):
        self.question.delete()
        self.item.refresh_from_db()
        self.assertIsNone(self.item.source_question)
        self.assertEqual(self.item.text, '2 + 2 = 4')

    def test_deleting_the_bank_keeps_the_exam(self):
        self.bank.delete()
        self.exam.refresh_from_db()
        self.assertIsNone(self.exam.bank)
        self.assertEqual(self.exam.versions.count(), 1)