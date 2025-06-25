__all__ = ["UsernamePasswordLogin", "TokenLogin"]

from django.contrib.auth.models import User
from django.db import models


class BaseLogin(models.Model):
    """A base login model used for storing user credentials.

    Attributes
    ----------
    user : OneToOneField
        Reference to the Django User who owns these credentials.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="%(class)s"
    )

    class Meta:
        abstract = True


class UsernamePasswordLogin(BaseLogin):
    """A login model for credentials that require a username and password.

    Attributes
    ----------
    username : str
        The username for this login.
    password : str
        The password for this login, stored in encrypted form.
    """

    username = models.CharField(max_length=100, blank=False, null=False)
    password = models.CharField(max_length=128, blank=False, null=False)

    class Meta:
        abstract = True


class TokenLogin(BaseLogin):
    """A login model for credentials that use a single token instead of a username and
    password.

    Attributes
    ----------
    token : str
        The token used for authentication or API access.
    """

    token = models.CharField(max_length=128, blank=False, null=False)

    class Meta:
        abstract = True
