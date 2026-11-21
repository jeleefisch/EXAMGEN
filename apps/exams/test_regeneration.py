from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.banks.models import Choice, Question, QuestionBank, Topic

from .models import Exam, ExamTopicRequirement
from .services import generate_exam_versions

User = get_user_model()


def make_bank(owner, per_difficulty=4):
    """One topic, MC questions in every difficulty, correct answer = choice 1."""
    bank = QuestionBank.objects.create(owner=owner, name='Bank')
    topic = Topic.objects.create(bank=bank, name='Algebra')
    for difficulty in ('Easy', 'Moderate', 'Difficult'):
        for n in range(per_difficulty):
            question = Question.objects.create(
                bank=bank, topic=topic, text=f'{difficulty} {n}',
                qtype='MC', difficulty=difficulty)
            for position in range(1, 5):
                Choice.objects.create(
                    question=question, text=f'choice {position}',
                    is_correct=(position == 1), position=position)
    return bank


def make_exam(owner, bank, with_topics=True):
    exam = Exam.objects.create(
        owner=owner, bank=bank, title='Quiz', subject='Math',
        num_versions=2, total_questions=6,
        easy_count=2, moderate_count=2, difficult_count=2)
    if with_topics:
        ExamTopicRequirement.objects.create(
            exam=exam, topic_name='Algebra', count=6)
    return exam


class RegenerationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('prof', password='pw-12345-x')
        self.bank = make_bank(self.user)
        self.exam = make_exam(self.user, self.bank)

    def test_each_generation_uses_a_fresh_seed(self):
        self.assertTrue(generate_exam_versions(self.exam).success)
        self.exam.refresh_from_db()
        first_seed = self.exam.base_seed

        self.assertTrue(generate_exam_versions(self.exam).success)
        self.exam.refresh_from_db()
        self.assertNotEqual(self.exam.base_seed, first_seed)

    def test_generating_does_not_make_the_exam_look_stale(self):
        generate_exam_versions(self.exam)
        self.exam.refresh_from_db()
        run = self.exam.generation_runs.order_by('-created_at').first()
        self.assertLessEqual(self.exam.updated_at, run.created_at)

    def test_a_failed_generation_keeps_the_old_seed_and_saves_nothing(self):
        broken = make_exam(self.user, self.bank, with_topics=False)
        before = broken.base_seed
        outcome = generate_exam_versions(broken)
        self.assertFalse(outcome.success)
        broken.refresh_from_db()
        self.assertEqual(broken.base_seed, before)
        self.assertEqual(broken.versions.count(), 0)