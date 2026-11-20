from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import Choice, Question, QuestionBank, Topic


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'created_at')


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'bank')
    list_filter = ('bank',)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'bank', 'topic', 'qtype', 'difficulty', 'points', 'is_active')
    list_filter = ('bank', 'topic', 'qtype', 'difficulty', 'is_active')
    inlines = (ChoiceInline,)
