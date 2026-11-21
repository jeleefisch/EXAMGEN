from django.urls import path

from .views import FacultyLoginView, FacultyLogoutView, profile, register

app_name = 'accounts'

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', FacultyLoginView.as_view(), name='login'),
    path('logout/', FacultyLogoutView.as_view(), name='logout'),
    path('profile/', profile, name='profile'),
]