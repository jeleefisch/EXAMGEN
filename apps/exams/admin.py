from django.contrib import admin

from .models import (
    Exam,
    ExamTopicRequirement,
    ExamVersion,
    GenerationRun,
    VersionChoice,
    VersionQuestion,
)

for model in (
    Exam, ExamTopicRequirement, ExamVersion,
    VersionQuestion, VersionChoice, GenerationRun,
):
    admin.site.register(model)