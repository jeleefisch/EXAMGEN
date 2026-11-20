from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import Choice, Question, QuestionBank, Topic


class QuestionBankForm(forms.ModelForm):
    class Meta:
        model = QuestionBank
        fields = ('name', 'description')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class TopicForm(forms.ModelForm):
    class Meta:
        model = Topic
        fields = ('name',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ('topic', 'text', 'qtype', 'difficulty', 'points', 'is_active')

    def __init__(self, *args, bank=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['topic'].queryset = Topic.objects.filter(bank=bank)
        for name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-check-input' if name == 'is_active' else 'form-control'
            })

    def clean(self):
        cleaned = super().clean()
        topic = cleaned.get('topic')
        if topic and self.instance.bank_id and topic.bank_id != self.instance.bank_id:
            raise forms.ValidationError('Choose a topic from this question bank.')
        qtype = cleaned.get('qtype')
        if self.instance.pk and qtype and qtype != self.instance.qtype:
            if self.instance.choices.exists():
                raise forms.ValidationError(
                    'Question type cannot be changed after choices are saved.'
                )
        return cleaned


class ChoiceForm(forms.ModelForm):
    class Meta:
        model = Choice
        fields = ('text', 'is_correct')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['text'].widget.attrs.update({'class': 'form-control'})
        self.fields['is_correct'].widget.attrs.update({'class': 'form-check-input'})


class ChoiceInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(form.errors for form in self.forms):
            return

        question = getattr(self.instance, 'qtype', None)
        expected = 4 if question == Question.QuestionType.MC else 2
        filled = [form.cleaned_data for form in self.forms
                  if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
                  and form.cleaned_data.get('text')]

        if len(filled) != expected:
            raise forms.ValidationError(
                f'This {question} question requires exactly {expected} choices.'
            )
        if sum(bool(choice.get('is_correct')) for choice in filled) != 1:
            raise forms.ValidationError('Exactly one choice must be marked correct.')

    def save_new(self, form, commit=True):
        choice = super().save_new(form, commit=False)
        choice.position = form.prefix.split('-')[-1]
        choice.position = int(choice.position) + 1
        if commit:
            choice.save()
        return choice


ChoiceFormSet = inlineformset_factory(
    Question,
    Choice,
    form=ChoiceForm,
    formset=ChoiceInlineFormSet,
    extra=0,
    can_delete=False,
    max_num=4,
)
