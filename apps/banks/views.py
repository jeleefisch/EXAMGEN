from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import CreateView, ListView, UpdateView

from .forms import (
    ChoiceInlineFormSet,
    ChoiceForm,
    QuestionBankForm,
    QuestionForm,
    TopicForm,
)
from .models import Choice, Question, QuestionBank, Topic


class FacultyOwnedMixin(LoginRequiredMixin):
    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)


class BankListView(FacultyOwnedMixin, ListView):
    model = QuestionBank
    template_name = 'banks/bank_list.html'
    context_object_name = 'banks'

    def get_queryset(self):
        return super().get_queryset().annotate(
            question_count=Count('questions', distinct=True),
            topic_count=Count('topics', distinct=True),
        )


class BankCreateView(FacultyOwnedMixin, CreateView):
    model = QuestionBank
    form_class = QuestionBankForm
    template_name = 'banks/bank_form.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, 'Question bank created.')
        return super().form_valid(form)

    def get_success_url(self):
        return '/banks/'


class BankUpdateView(FacultyOwnedMixin, UpdateView):
    model = QuestionBank
    form_class = QuestionBankForm
    template_name = 'banks/bank_form.html'

    def get_success_url(self):
        return '/banks/'


@login_required
def topic_create(request, bank_pk):
    bank = get_object_or_404(QuestionBank, pk=bank_pk, owner=request.user)
    if request.method == 'POST':
        form = TopicForm(request.POST)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.bank = bank
            topic.save()
            messages.success(request, 'Topic created.')
            return redirect('banks:question_list')
    else:
        form = TopicForm()
    return render(request, 'banks/topic_form.html', {'form': form, 'bank': bank})


@login_required
def question_list(request):
    banks = QuestionBank.objects.filter(owner=request.user)
    qs = Question.objects.filter(bank__owner=request.user).select_related(
        'bank', 'topic'
    )
    bank_id = request.GET.get('bank')
    topic_id = request.GET.get('topic')
    difficulty = request.GET.get('difficulty')
    qtype = request.GET.get('qtype')
    if bank_id:
        qs = qs.filter(bank_id=bank_id)
    if topic_id:
        qs = qs.filter(topic_id=topic_id)
    if difficulty:
        qs = qs.filter(difficulty=difficulty)
    if qtype:
        qs = qs.filter(qtype=qtype)
    if request.GET.get('active') == '1':
        qs = qs.filter(is_active=True)

    return render(request, 'banks/question_list.html', {
        'questions': qs,
        'banks': banks,
        'topics': Topic.objects.filter(bank__owner=request.user),
        'difficulty_choices': Question.Difficulty.choices,
        'type_choices': Question.QuestionType.choices,
    })


def make_choice_formset(question, data=None):
    expected = 4 if question.qtype == Question.QuestionType.MC else 2
    FormSet = inlineformset_factory(
        Question,
        Choice,
        form=ChoiceForm,
        formset=ChoiceInlineFormSet,
        extra=0 if question.pk else expected,
        max_num=expected,
        validate_max=True,
        can_delete=False,
    )
    return FormSet(
        data=data,
        instance=question,
        prefix='choices',
    )


@login_required
def question_create(request, bank_pk):
    bank = get_object_or_404(QuestionBank, pk=bank_pk, owner=request.user)
    qtype = request.POST.get('qtype', request.GET.get('qtype', Question.QuestionType.MC))
    question = Question(bank=bank, qtype=qtype)

    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question, bank=bank)
        formset = make_choice_formset(question, request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                question = form.save()
                formset.instance = question
                formset.save()
            messages.success(request, 'Question created.')
            return redirect('banks:question_list')
    else:
        form = QuestionForm(instance=question, bank=bank)
        formset = make_choice_formset(question)

    return render(request, 'banks/question_form.html', {
        'form': form,
        'formset': formset,
        'bank': bank,
        'object': None,
    })


@login_required
def question_edit(request, pk):
    question = get_object_or_404(
        Question.objects.select_related('bank'),
        pk=pk,
        bank__owner=request.user,
    )
    if request.method == 'POST':
        question.qtype = request.POST.get('qtype', question.qtype)
        form = QuestionForm(request.POST, instance=question, bank=question.bank)
        formset = make_choice_formset(question, request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                saved = form.save()
                formset.instance = saved
                formset.save()
            messages.success(request, 'Question updated.')
            return redirect('banks:question_list')
    else:
        form = QuestionForm(instance=question, bank=question.bank)
        formset = make_choice_formset(question)

    return render(request, 'banks/question_form.html', {
        'form': form,
        'formset': formset,
        'bank': question.bank,
        'object': question,
    })