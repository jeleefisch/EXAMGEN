from django.urls import path

from . import views

app_name = "omr"

urlpatterns = [
    path("exam/<int:exam_pk>/", views.scan_list, name="list"),
    path("exam/<int:exam_pk>/upload/", views.scan_upload, name="upload"),
    path("<int:pk>/", views.scan_detail, name="detail"),
    path("<int:pk>/image/", views.scan_image, name="image"),
]