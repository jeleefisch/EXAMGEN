"""Exam configuration form.

One form handles both creating and editing. It adds one number field per
topic in the bank ("topic_<id>"), and rejects impossible configurations by
running the same feasibility check the generator uses.
"""
from collections import Counter

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.banks.models import Topic
from apps.banks.services import eligible_core_questions
from core.generation.feasibility import check_feasibility

from .models import Exam, ExamTopicRequirement

DIFFICULTIES = ("Easy", "Moderate", "Difficult")
MAX_ITEMS = 50  # MVP answer sheet limit


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = [
            "title", "subject", "institution_name", "num_students",
            "num_versions", "total_questions", "easy_count",
            "moderate_count", "difficult_count", "points_per_question",
            "shuffle_choices", "shuffle_questions", "max_similarity",
        ]
        labels = {
            "num_students": "Number of students",
            "num_versions": "Number of versions",
            "total_questions": "Total questions per exam",
            "easy_count": "Easy questions",
            "moderate_count": "Moderate questions",
            "difficult_count": "Difficult questions",
            "points_per_question": "Points per question",
            "shuffle_choices": "Shuffle answer choices",
            "shuffle_questions": "Shuffle question order",
            "max_similarity": "Max overlap between versions (0 to 1, optional)",
        }

    def __init__(self, *args, bank, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank = bank
        self.topics = list(Topic.objects.filter(bank=bank).order_by("name"))
        self.fields["institution_name"].required = False
        self.fields["max_similarity"].required = False

        existing = {}
        if self.instance.pk:
            existing = {r.topic_name: r.count for r in self.instance.topic_requirements.all()}
        for t in self.topics:
            self.fields[f"topic_{t.pk}"] = forms.IntegerField(
                label=f"Questions from topic: {t.name}",
                min_value=0, initial=existing.get(t.name, 0),
            )
        for field in self.fields.values():
            css = "form-check-input" if field.widget.input_type == "checkbox" else "form-control"
            field.widget.attrs["class"] = css

        # Question pool available to this exam (used for display and checks).
        self.usable, self.excluded = eligible_core_questions(bank)
        self.available = Counter((q.topic, q.difficulty) for q in self.usable)

    # --- helpers for the template ---
    def main_fields(self):
        return [f for f in self if not f.name.startswith("topic_")]

    def topic_fields(self):
        return [self[f"topic_{t.pk}"] for t in self.topics]

    def pool_rows(self):
        rows = []
        for t in self.topics:
            counts = [self.available.get((t.name, d), 0) for d in DIFFICULTIES]
            rows.append((t.name, *counts, sum(counts)))
        return rows

    # --- validation ---
    def clean_num_versions(self):
        n = self.cleaned_data["num_versions"]
        if not 1 <= n <= MAX_ITEMS:
            raise ValidationError(f"Use between 1 and {MAX_ITEMS} versions.")
        return n

    def clean_total_questions(self):
        n = self.cleaned_data["total_questions"]
        if not 1 <= n <= MAX_ITEMS:
            raise ValidationError(f"Use between 1 and {MAX_ITEMS} questions (answer sheet limit).")
        return n

    def clean_max_similarity(self):
        v = self.cleaned_data.get("max_similarity")
        if v is not None and not 0 <= v <= 1:
            raise ValidationError("Enter a number from 0 to 1 (for example 0.3 means 30%).")
        return v

    def clean(self):
        cleaned = super().clean()
        total = cleaned.get("total_questions")
        diff_required = {
            "Easy": cleaned.get("easy_count"),
            "Moderate": cleaned.get("moderate_count"),
            "Difficult": cleaned.get("difficult_count"),
        }
        topic_required = {}
        for t in self.topics:
            n = cleaned.get(f"topic_{t.pk}")
            if n is None:
                return cleaned  # a field error is already showing
            if n > 0:
                topic_required[t.name] = n
        if total is None or any(v is None for v in diff_required.values()):
            return cleaned

        problems = []
        if sum(diff_required.values()) != total:
            problems.append(
                f"Easy + Moderate + Difficult = {sum(diff_required.values())}, "
                f"but total questions is {total}."
            )
        if sum(topic_required.values()) != total:
            problems.append(
                f"Topic quotas add up to {sum(topic_required.values())}, "
                f"but total questions is {total}."
            )
        if problems:
            raise ValidationError(problems)

        result = check_feasibility(dict(self.available), topic_required, diff_required, total)
        if not result.feasible:
            raise ValidationError([str(p) for p in result.problems])
        return cleaned

    @transaction.atomic
    def save(self, owner=None):
        exam = super().save(commit=False)
        if exam.pk is None:
            exam.owner = owner
            exam.bank = self.bank
        exam.save()
        ExamTopicRequirement.objects.filter(exam=exam).delete()
        ExamTopicRequirement.objects.bulk_create([
            ExamTopicRequirement(exam=exam, topic_name=t.name, count=self.cleaned_data[f"topic_{t.pk}"])
            for t in self.topics if self.cleaned_data[f"topic_{t.pk}"] > 0
        ])
        return exam