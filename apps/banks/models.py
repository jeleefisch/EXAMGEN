from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class QuestionBank(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='question_banks',
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class Topic(models.Model):
    bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.CASCADE,
        related_name='topics',
    )
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ('name',)
        constraints = [
            models.UniqueConstraint(
                fields=('bank', 'name'),
                name='unique_topic_per_bank',
            )
        ]

    def __str__(self):
        return self.name


class Question(models.Model):
    class QuestionType(models.TextChoices):
        MC = 'MC', 'Multiple Choice'
        TF = 'TF', 'True / False'

    class Difficulty(models.TextChoices):
        EASY = 'Easy', 'Easy'
        MODERATE = 'Moderate', 'Moderate'
        DIFFICULT = 'Difficult', 'Difficult'

    bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.CASCADE,
        related_name='questions',
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.PROTECT,
        related_name='questions',
    )
    text = models.TextField()
    qtype = models.CharField(
        max_length=2,
        choices=QuestionType.choices,
        default=QuestionType.MC,
    )
    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
        default=Difficulty.MODERATE,
    )
    points = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('topic__name', 'pk')

    def clean(self):
        super().clean()
        if self.topic_id and self.bank_id and self.topic.bank_id != self.bank_id:
            raise ValidationError({'topic': 'The topic must belong to this question bank.'})

    def __str__(self):
        return self.text[:80]

    def choice_count(self):
        return 4 if self.qtype == self.QuestionType.MC else 2


class Choice(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='choices',
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ('position',)
        constraints = [
            models.UniqueConstraint(
                fields=('question', 'position'),
                name='unique_choice_position_per_question',
            )
        ]

    def clean(self):
        super().clean()
        if self.question_id:
            expected = self.question.choice_count()
            if self.position < 1 or self.position > expected:
                raise ValidationError({
                    'position': f'This question requires positions 1 through {expected}.'
                })

    def __str__(self):
        return f"{self.position}. {self.text}"
