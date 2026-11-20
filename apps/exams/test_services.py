from collections import Counter
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.banks.models import Choice, Question, QuestionBank, Topic

from .models import (
    Exam,
    ExamTopicRequirement,
    ExamVersion,
    VersionChoice,
    VersionQuestion,
)
from .services import ExamFinalizedError, generate_exam_versions


def make_question(bank, topic, difficulty, n, correct_pos=1, correct_count=1):
    q = Question.objects.create(
        bank=bank, topic=topic, text=f"{topic.name}-{difficulty}-{n}?",
        qtype="MC", difficulty=difficulty, points=1, is_active=True,
    )
    for pos in range(1, 5):
        Choice.objects.create(
            question=q, text=f"choice {pos} of {q.pk}",
            is_correct=(pos <= correct_count) if correct_count != 1 else (pos == correct_pos),
            position=pos,
        )
    return q


class GenerationServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("prof", password="x")
        self.bank = QuestionBank.objects.create(owner=self.user, name="Bank")
        self.topics = {n: Topic.objects.create(bank=self.bank, name=n) for n in "ABC"}
        for name, topic in self.topics.items():
            for diff in ("Easy", "Moderate", "Difficult"):
                for i in range(4):
                    make_question(self.bank, topic, diff, i, correct_pos=(i % 4) + 1)
        self.exam = Exam.objects.create(
            owner=self.user, bank=self.bank, title="Midterm", subject="Math",
            num_students=30, num_versions=3, total_questions=9,
            easy_count=3, moderate_count=3, difficult_count=3,
            points_per_question=2,
        )
        for name in "ABC":
            ExamTopicRequirement.objects.create(exam=self.exam, topic_name=name, count=3)

    def test_success_creates_versions_that_satisfy_constraints(self):
        out = generate_exam_versions(self.exam)
        self.assertTrue(out.success, out.problems)
        self.assertEqual(ExamVersion.objects.filter(exam=self.exam).count(), 3)
        for v in ExamVersion.objects.filter(exam=self.exam):
            items = list(VersionQuestion.objects.filter(version=v))
            self.assertEqual(len(items), 9)
            self.assertEqual(Counter(i.topic_name for i in items), {"A": 3, "B": 3, "C": 3})
            self.assertEqual(
                Counter(i.difficulty for i in items),
                {"Easy": 3, "Moderate": 3, "Difficult": 3},
            )
            self.assertEqual(len({i.source_question_id for i in items}), 9)  # no duplicates
            self.assertTrue(all(i.points == 2 for i in items))

    def test_saved_key_matches_saved_choices(self):
        generate_exam_versions(self.exam)
        for vq in VersionQuestion.objects.filter(version__exam=self.exam):
            choices = list(VersionChoice.objects.filter(question=vq))
            self.assertEqual(sorted(c.display_label for c in choices), ["A", "B", "C", "D"])
            correct = [c for c in choices if c.is_correct]
            self.assertEqual(len(correct), 1)
            self.assertEqual(correct[0].display_label, vq.correct_label)

    def test_finalized_exam_cannot_be_regenerated(self):
        self.exam.status = "finalized"
        self.exam.save()
        with self.assertRaises(ExamFinalizedError):
            generate_exam_versions(self.exam)
        self.assertEqual(ExamVersion.objects.filter(exam=self.exam).count(), 0)

    def test_infeasible_config_saves_nothing_and_keeps_old_versions(self):
        generate_exam_versions(self.exam)
        old_ids = set(ExamVersion.objects.filter(exam=self.exam).values_list("id", flat=True))
        # Ask for 9 Easy questions all from topic A (A has only 4 Easy).
        ExamTopicRequirement.objects.filter(exam=self.exam, topic_name__in=["B", "C"]).delete()
        ExamTopicRequirement.objects.filter(exam=self.exam, topic_name="A").update(count=9)
        self.exam.easy_count, self.exam.moderate_count, self.exam.difficult_count = 9, 0, 0
        self.exam.save()
        out = generate_exam_versions(self.exam)
        self.assertFalse(out.success)
        self.assertTrue(out.problems)
        new_ids = set(ExamVersion.objects.filter(exam=self.exam).values_list("id", flat=True))
        self.assertEqual(old_ids, new_ids)

    def test_failure_while_saving_rolls_back_everything(self):
        generate_exam_versions(self.exam)
        old_ids = set(ExamVersion.objects.filter(exam=self.exam).values_list("id", flat=True))
        with patch("apps.exams.services._save_version", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                generate_exam_versions(self.exam)
        new_ids = set(ExamVersion.objects.filter(exam=self.exam).values_list("id", flat=True))
        self.assertEqual(old_ids, new_ids)

    def test_invalid_questions_are_excluded_and_reported(self):
        bad = make_question(self.bank, self.topics["A"], "Easy", 99, correct_count=2)
        out = generate_exam_versions(self.exam)
        self.assertTrue(out.success, out.problems)
        self.assertIn(bad.pk, [pk for pk, _ in out.excluded])
        used = VersionQuestion.objects.filter(version__exam=self.exam, source_question=bad)
        self.assertEqual(used.count(), 0)

    def test_snapshot_is_independent_of_later_bank_edits(self):
        generate_exam_versions(self.exam)
        vq = VersionQuestion.objects.filter(version__exam=self.exam).first()
        original_text = vq.text
        original_key = vq.correct_label
        src = vq.source_question
        src.text = "CHANGED"
        src.save()
        Choice.objects.filter(question=src).update(is_correct=False)
        vq.refresh_from_db()
        self.assertEqual(vq.text, original_text)
        self.assertEqual(vq.correct_label, original_key)
        self.assertEqual(VersionChoice.objects.filter(question=vq, is_correct=True).count(), 1)

    def test_deleting_the_bank_keeps_generated_versions(self):
        generate_exam_versions(self.exam)
        before = VersionQuestion.objects.filter(version__exam=self.exam).count()
        self.bank.delete()
        self.assertEqual(VersionQuestion.objects.filter(version__exam=self.exam).count(), before)

    def test_regenerating_a_draft_replaces_old_versions(self):
        generate_exam_versions(self.exam)
        generate_exam_versions(self.exam)
        self.assertEqual(ExamVersion.objects.filter(exam=self.exam).count(), 3)