from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from apps.banks.models import QuestionBank

from .forms import LoginForm, ProfileForm, RegistrationForm


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


class FacultyLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm


class FacultyLogoutView(LogoutView):
    pass
