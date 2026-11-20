from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class RegistrationTests(TestCase):
    def test_registration_creates_profile_and_logs_in(self):
        response = self.client.post(reverse('accounts:register'), {
            'username': 'faculty',
            'first_name': 'Ada',
            'last_name': 'Lovelace',
            'email': 'ada@example.com',
            'institution_name': 'Analytical College',
            'password1': 'StrongPass!842',
            'password2': 'StrongPass!842',
        })
        self.assertRedirects(response, reverse('dashboard'))
        user = User.objects.get(username='faculty')
        self.assertEqual(user.profile.institution_name, 'Analytical College')
        self.assertTrue('_auth_user_id' in self.client.session)
