__all__ = ["UsernamePasswordLogin", "TokenLogin"]

from django.contrib.auth.models import User
from django.db import models


class BaseLogin(models.Model):
    """A base login model used for storing user credentials.

    Attributes
    ----------
    user : OneToOneField
        Reference to the Django User who owns these credentials.
    created_at : DateTimeField
        When these credentials were first stored.
    updated_at : DateTimeField
        When they were last replaced. Surfaced on the credential page so a
        user returning after a long absence can tell whether anything is
        stored, and how stale it is, without the page having to reveal any
        part of the secret itself -- which it must not, since these values
        are held in plain text.

    Notes
    -----
    Both fields live on the abstract base, so every credential type gets them
    from one definition rather than eight separate ones that could drift.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="%(class)s"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        abstract = True


class UsernamePasswordLogin(BaseLogin):
    """A login model for credentials that require a username and password.

    Attributes
    ----------
    username : str
        The username for this login.
    password : str
        The password for this login. Stored in **plain text**, like every
        other credential here -- see the note on `BaseLogin.updated_at`.
        Encrypting these at rest is required before a shared deployment.
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
