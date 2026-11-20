from django.urls import path

from .views import (
    BankCreateView,
    BankListView,
    BankUpdateView,
    question_create,
    question_edit,
    question_list,
    topic_create,
)

app_name = 'banks'

urlpatterns = [
    path('', BankListView.as_view(), name='bank_list'),
    path('create/', BankCreateView.as_view(), name='bank_create'),
    path('<int:pk>/edit/', BankUpdateView.as_view(), name='bank_edit'),
    path('<int:bank_pk>/topics/create/', topic_create, name='topic_create'),
    path('questions/', question_list, name='question_list'),
    path('<int:bank_pk>/questions/create/', question_create, name='question_create'),
    path('questions/<int:pk>/edit/', question_edit, name='question_edit'),
]
