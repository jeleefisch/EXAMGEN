from django.urls import path

from . import views

app_name = "grading"

urlpatterns = [
    path("exam/<int:exam_pk>/", views.results, name="results"),
    path("exam/<int:exam_pk>/csv/", views.results_csv, name="csv"),
    path("<int:pk>/", views.result_detail, name="result"),
]