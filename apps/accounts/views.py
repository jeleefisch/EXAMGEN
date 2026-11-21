from django import forms
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from apps.banks.models import QuestionBank

from .forms import LoginForm, ProfileForm, RegistrationForm


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ("first_name", "last_name", "email")
        widgets = {f: forms.TextInput(attrs={"class": "form-control"})
                   for f in ("first_name", "last_name")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs["class"] = "form-control"


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        banks = QuestionBank.objects.filter(owner=self.request.user)
        context.update({
            'bank_count': banks.count(),
            'question_count': sum(bank.questions.count() for bank in banks),
            'active_question_count': sum(
                bank.questions.filter(is_active=True).count() for bank in banks
            ),
        })
        return context


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully.')
            return redirect('dashboard')
    else:
        form = RegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile saved.')
            return redirect('accounts:profile')
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, 'accounts/profile.html', {'form': form})


class FacultyLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm


class FacultyLogoutView(LogoutView):
    pass