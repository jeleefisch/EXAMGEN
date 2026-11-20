import secrets

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.banks.models import Question, QuestionBank


def new_seed():
    """Random base seed for a new exam (kept so generation is reproducible)."""
    return secrets.randbelow(2 ** 31)


class Exam(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        FINALIZED = 'finalized', 'Finalized'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exams',
    )
    # SET_NULL: deleting a bank must never destroy exams that were already made.
    bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exams',
    )
    title = models.CharField(max_length=200)
    subject = models.CharField(max_length=200)
    institution_name = models.CharField(max_length=200, blank=True)

    num_students = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)])
    num_versions = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1)])
    total_questions = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)])
    easy_count = models.PositiveSmallIntegerField(default=0)
    moderate_count = models.PositiveSmallIntegerField(default=0)
    difficult_count = models.PositiveSmallIntegerField(default=0)
    points_per_question = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)])

    shuffle_choices = models.BooleanField(default=True)
    shuffle_questions = models.BooleanField(default=True)
    # Optional ceiling on Jaccard similarity between versions (0.0 to 1.0).
    max_similarity = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    base_seed = models.PositiveIntegerField(default=new_seed)

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.CheckConstraint(
                condition=Q(total_questions=(
                    F('easy_count') + F('moderate_count') + F('difficult_count')
                )),
                name='exam_difficulty_counts_match_total',
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def is_finalized(self):
        return self.status == self.Status.FINALIZED

    def difficulty_required(self):
        """Difficulty counts in the form the generation engine expects."""
        return {
            Question.Difficulty.EASY.value: self.easy_count,
            Question.Difficulty.MODERATE.value: self.moderate_count,
            Question.Difficulty.DIFFICULT.value: self.difficult_count,
        }

    def topic_required(self):
        """Topic quotas in the form the generation engine expects."""
        return {r.topic_name: r.count for r in self.topic_requirements.all()}

    def finalize(self):
        self.status = self.Status.FINALIZED
        self.finalized_at = timezone.now()
        self.save(update_fields=['status', 'finalized_at', 'updated_at'])


class ExamTopicRequirement(models.Model):
    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name='topic_requirements')
    # Stored as text on purpose: a snapshot, not a live link to the topic.
    topic_name = models.CharField(max_length=150)
    count = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ('topic_name',)
        constraints = [
            models.UniqueConstraint(
                fields=('exam', 'topic_name'),
                name='unique_topic_requirement_per_exam',
            ),
        ]

    def __str__(self):
        return f'{self.topic_name}: {self.count}'


class ExamVersion(models.Model):
    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name='versions')
    code = models.CharField(max_length=30, unique=True)   # e.g. "E12-A"
    sequence = models.PositiveSmallIntegerField()
    seed = models.CharField(max_length=60)
    attempts = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('sequence',)
        constraints = [
            models.UniqueConstraint(
                fields=('exam', 'sequence'),
                name='unique_version_sequence_per_exam',
            ),
        ]

    def __str__(self):
        return self.code


class VersionQuestion(models.Model):
    """One numbered question on one version, copied from the bank (snapshot)."""
    version = models.ForeignKey(
        ExamVersion, on_delete=models.CASCADE, related_name='items')
    position = models.PositiveSmallIntegerField()
    source_question = models.ForeignKey(
        Question,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    text = models.TextField()
    qtype = models.CharField(max_length=2)
    topic_name = models.CharField(max_length=150)
    difficulty = models.CharField(max_length=10)
    points = models.PositiveIntegerField()
    correct_label = models.CharField(max_length=1)   # letter on THIS paper

    class Meta:
        ordering = ('position',)
        constraints = [
            models.UniqueConstraint(
                fields=('version', 'position'),
                name='unique_item_position_per_version',
            ),
        ]

    def __str__(self):
        return f'{self.version.code} #{self.position}'


class VersionChoice(models.Model):
    question = models.ForeignKey(
        VersionQuestion, on_delete=models.CASCADE, related_name='choices')
    display_label = models.CharField(max_length=1)   # A, B, C, D as printed
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ('display_label',)
        constraints = [
            models.UniqueConstraint(
                fields=('question', 'display_label'),
                name='unique_choice_label_per_item',
            ),
        ]

    def __str__(self):
        return f'{self.display_label}. {self.text}'


class GenerationRun(models.Model):
    """The report from one generation, kept for evaluation and auditing."""
    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name='generation_runs')
    requested = models.PositiveSmallIntegerField()
    succeeded = models.PositiveSmallIntegerField()
    duration_ms = models.FloatField()
    mean_jaccard = models.FloatField(null=True, blank=True)
    max_jaccard = models.FloatField(null=True, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    overlaps = models.JSONField(default=list, blank=True)
    # Can exceed 64-bit integers, so stored as text.
    selection_estimate = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.exam} run at {self.created_at:%Y-%m-%d %H:%M}'