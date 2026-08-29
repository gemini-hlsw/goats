"""Stored third-party credentials, with the secret half encrypted at rest.

Which encryption, and why
-------------------------
TOM Toolkit ships **two** unrelated mechanisms, and only one of them can work
here.

`tom_common.session_utils` derives a Fernet key from the user's *password* and
keeps it in their session. It gives the strongest property -- a credential is
unreadable unless that user is logged in -- and it is unusable for GOATS.
Every credential in this module is read by code running with no session at
all: `executors/datalab.py` reads a subscription owner's Data Lab login from
the supervisor, `tasks/download_goa_files.py` reads GOA credentials from a
background task, and `tasks/ingest_antares_stream.py` reads Kafka keys from
the stream consumer. Under the session scheme those all fail whenever the PI
is not at their browser, which is most of the time and the entire point of
the offload. It also *clears* a user's encrypted fields when an administrator
resets their password while they are logged out -- silent credential loss for
every PI whose password IT ever resets.

So these use `goats_tom.encryption.EncryptedField`, whose key derives from
``settings.SECRET_KEY``. Background jobs can decrypt, and
``rotate_credential_key`` handles key rotation.

The field lives in GOATS rather than TOM because ``tomtoolkit==2.32.2`` --
the pinned version -- has no encryption module; that arrived in TOM 3.0.
`goats_tom.encryption` matches TOM 3's semantics deliberately, so a future
upgrade can swap the field class and still read the stored data.

**Be honest about what this protects.** A stolen database dump or backup is
now ciphertext, which was the stated risk: every PI's credentials sitting in
plain text in Postgres and in every backup. It does **not** protect against
an attacker who reaches the application server, because that host holds
``SECRET_KEY`` by necessity. Treating `SECRET_KEY` as a secret -- out of
version control, out of backups that travel with the database -- is what
makes this worth anything.

Which fields are encrypted
--------------------------
The secret half only: passwords, tokens, API keys and secrets. Usernames and
bot identifiers stay plain text. They are not secrets, the credential page
displays them so a PI can tell which account is linked, and
`EncryptedField` cannot be filtered on -- encrypting an identifier would
cost lookups for no gain.
"""

__all__ = ["UsernamePasswordLogin", "TokenLogin"]

from django.contrib.auth.models import User
from django.db import models
from goats_tom.encryption import EncryptedField


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
        part of the secret itself.

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
        The password for this login. Encrypted at rest -- see the module
        docstring for which mechanism and what it does and does not
        protect against.

    Notes
    -----
    `username` is deliberately left unencrypted: it is not a secret, the
    credential page shows it so a PI can confirm which account is linked,
    and encrypted columns cannot be filtered on.
    """

    username = models.CharField(max_length=100, blank=False, null=False)
    password = EncryptedField(blank=False, null=True)

    class Meta:
        abstract = True


class TokenLogin(BaseLogin):
    """A login model for credentials that use a single token instead of a username and
    password.

    Attributes
    ----------
    token : str
        The token used for authentication or API access. Encrypted at rest.
    """

    token = EncryptedField(blank=False, null=True)

    class Meta:
        abstract = True
