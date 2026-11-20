from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    institution_name = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.user.get_username()} - {self.institution_name}"
