__all__ = ["BaseLogin"]

from django.contrib.auth.models import User
from django.db import models
from django_cryptography.fields import encrypt


class BaseLogin(models.Model):
    """A base login model used for storing user credentials.

    Attributes
    ----------
    user : `OneToOneField`
        Reference to the Django User who owns these credentials.
    username : `str`
        The username for this login.
    password : `str`
        The password for this login, stored in encrypted form.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="%(class)s"
    )
    username = models.CharField(max_length=100, blank=False, null=False)
    password = encrypt(models.CharField(max_length=128, blank=False, null=False))

    class Meta:
        abstract = True
