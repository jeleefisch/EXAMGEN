from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import Choice, Question, QuestionBank, Topic
from .services import question_to_core


class BankModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('faculty', password='StrongPass!842')
        self.bank = QuestionBank.objects.create(owner=self.user, name='Math')
        self.topic = Topic.objects.create(bank=self.bank, name='Algebra')

    def test_topic_name_is_unique_per_bank(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Topic.objects.create(bank=self.bank, name='Algebra')

    def test_mc_maps_to_core_with_correct_original_index(self):
        question = Question.objects.create(
            bank=self.bank,
            topic=self.topic,
            text='Which value is 2 + 2?',
            qtype=Question.QuestionType.MC,
            difficulty=Question.Difficulty.EASY,
        )
        for position, (text, correct) in enumerate([
            ('3', False),
            ('4', True),
            ('5', False),
            ('6', False),
        ], start=1):
            Choice.objects.create(
                question=question,
                text=text,
                is_correct=correct,
                position=position,
            )

        core_question = question_to_core(question)
        self.assertEqual(core_question.correct_index, 1)
        self.assertEqual(core_question.n_choices, 4)

    def test_question_list_requires_login(self):
        response = self.client.get(reverse('banks:question_list'))
        self.assertEqual(response.status_code, 302)
