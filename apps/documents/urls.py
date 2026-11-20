from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("paper/<int:pk>/", views.paper_pdf, name="paper"),
    path("sheets/<int:pk>/", views.sheets_pdf, name="sheets"),
    path("key/<int:exam_pk>/", views.key_pdf, name="key"),
]