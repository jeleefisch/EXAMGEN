from django.urls import path

from . import views

app_name = "exams"

urlpatterns = [
    path("", views.exam_list, name="list"),
    path("new/<int:bank_pk>/", views.exam_create, name="create"),
    path("<int:pk>/", views.exam_detail, name="detail"),
    path("<int:pk>/edit/", views.exam_edit, name="edit"),
    path("<int:pk>/generate/", views.exam_generate, name="generate"),
    path("<int:pk>/finalize/", views.exam_finalize, name="finalize"),
    path("versions/<int:pk>/", views.version_detail, name="version"),
]