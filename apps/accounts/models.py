from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """
    Custom user model for the Unmad Digital Archive.

    Extends Django's AbstractUser so we keep the default username,
    email, and password handling while adding archive-specific fields.
    """

    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Optional contact number.",
    )

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self) -> str:
        return self.username
