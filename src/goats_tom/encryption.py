"""Encryption at rest for stored third-party credentials.

Why this lives in GOATS
-----------------------
TOM Toolkit gained a `tom_common.encryption` module with an
`EncryptedModelField` in 3.0. GOATS pins ``tomtoolkit==2.32.2``, which does
not have it. Upgrading TOM to get one field would pull in a major release
across the whole application -- new view signatures, new templates, a new
target model -- which is not a change to make alongside a security fix, and
would put the desktop invariant at risk for no reason.

So this is a small, self-contained implementation of the same idea. It is
deliberately written to match TOM 3.0's semantics (Fernet, key derived from
``SECRET_KEY`` via HKDF, ciphertext in a `BinaryField`, `str` on the Python
side) so that if GOATS ever moves to TOM 3, the field class can be swapped
for the upstream one and the stored data will still decrypt.

What this protects, and what it does not
----------------------------------------
**Protects:** a stolen database dump or backup. That was the stated risk --
every PI's Data Lab password, Jupyter token, ANTARES key and RSP token
sitting in plain text in Postgres, inherited by every backup. Those columns
are now ciphertext.

**Does not protect:** an attacker who reaches the application server. That
host holds ``SECRET_KEY`` by necessity, because background jobs must decrypt
without a user present. Keeping `SECRET_KEY` out of version control, and out
of any backup that travels with the database, is what makes this worth
anything. If the two are stored together, this achieves nothing.

Why not TOM's session-based scheme
----------------------------------
TOM 2.32.2 *does* ship `tom_common.session_utils`, which derives a key from
the user's password and holds it in their session. It is a stronger property
and it is unusable here. Every credential in `goats_tom.models.logins` is
read by code running with no session:

- `executors/datalab.py` reads a subscription owner's Data Lab login from the
  supervisor.
- `tasks/download_goa_files.py` reads GOA credentials in a background task.
- `tasks/ingest_antares_stream.py` reads Kafka keys in the stream consumer.

Under a password-derived key all of those fail whenever the PI is not sitting
at their browser, which is most of the time and the entire point of the
offload. That scheme also *clears* a user's encrypted fields when an
administrator resets their password while they are logged out, which would
mean silent credential loss for every PI whose password IT ever resets.

Key rotation
------------
`decrypt` tries ``SECRET_KEY`` first and then each entry in
``SECRET_KEY_FALLBACKS``, so a key can be rotated without downtime: put the
new key in ``SECRET_KEY``, move the old one into ``SECRET_KEY_FALLBACKS``,
then run ``python manage.py rotate_credential_key`` to re-encrypt everything
under the new key and drop the fallback.
"""

__all__ = [
    "EncryptedField",
    "decrypt",
    "encrypt",
    "iter_encrypted_fields",
]

import base64
from typing import Any, Iterator

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.apps import apps
from django.conf import settings
from django.core.exceptions import FieldError
from django.db import models

#: Domain separation for the key derivation.
#:
#: Changing this invalidates every stored value, so it is fixed. It exists so
#: that a key derived here cannot collide with one Django derives from the
#: same `SECRET_KEY` for signing cookies or password resets -- reusing one
#: secret for several purposes is how a weakness in one becomes a weakness in
#: all of them.
_HKDF_INFO = b"goats-credential-encryption-v1"


def _derive_key(secret: str) -> bytes:
    """Derive a Fernet key from a Django secret.

    Parameters
    ----------
    secret : `str`
        A ``SECRET_KEY`` or one of ``SECRET_KEY_FALLBACKS``.

    Returns
    -------
    `bytes`
        A urlsafe-base64 32-byte key, which is the format Fernet requires.

    Notes
    -----
    HKDF rather than using the secret directly: `SECRET_KEY` is an arbitrary
    string of arbitrary length and entropy, and Fernet needs exactly 32
    bytes. Hashing it also means the raw signing key is not the encryption
    key, so the two uses stay separated.

    No salt. A random salt would have to be stored next to the ciphertext to
    decrypt it later, and with a single high-entropy input the domain
    separation in ``info`` is what matters here.
    """
    kdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_HKDF_INFO,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret.encode()))


def _active_secrets() -> list[str]:
    """Every secret a stored value might have been encrypted under.

    Notes
    -----
    Primary first, then fallbacks in order, so the common case is one
    attempt. Only the primary is ever used to *encrypt* -- a fallback exists
    to read old data during a rotation, not to write new.
    """
    secrets = [settings.SECRET_KEY]
    secrets.extend(getattr(settings, "SECRET_KEY_FALLBACKS", []) or [])
    return [s for s in secrets if s]


def encrypt(plaintext: str) -> bytes:
    """Encrypt a string under the current `SECRET_KEY`.

    Parameters
    ----------
    plaintext : `str`
        The value to protect.

    Returns
    -------
    `bytes`
        Fernet ciphertext, safe to store in a `BinaryField`.
    """
    return Fernet(_derive_key(settings.SECRET_KEY)).encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    """Decrypt a stored value, trying the primary key then each fallback.

    Parameters
    ----------
    ciphertext : `bytes`
        A value produced by `encrypt`.

    Returns
    -------
    `str`
        The original plaintext.

    Raises
    ------
    `cryptography.fernet.InvalidToken`
        If no active key can decrypt the value. This is deliberately loud:
        a credential that cannot be read is a credential the PI must
        re-enter, and silently returning an empty string would turn that
        into a mysterious authentication failure somewhere far away.
    """
    if isinstance(ciphertext, memoryview):
        # psycopg hands back a memoryview where sqlite3 gives bytes.
        ciphertext = ciphertext.tobytes()
    for secret in _active_secrets():
        try:
            return Fernet(_derive_key(secret)).decrypt(bytes(ciphertext)).decode()
        except InvalidToken:
            continue
    raise InvalidToken(
        "Could not decrypt with SECRET_KEY or any SECRET_KEY_FALLBACKS entry."
    )


class EncryptedField(models.BinaryField):
    """A `str`-valued field whose contents are encrypted in the database.

    Assigning a string encrypts it on save; reading it after a load returns
    the plaintext. The column is binary.

    Notes
    -----
    `editable=True` by default. `BinaryField` sets it `False`, on the
    reasonable assumption that raw bytes do not belong in a form -- but the
    Python-side value here is a string that users type into the credential
    page, so the ordinary `ModelForm` machinery needs to see it.

    Filtering is refused rather than silently returning nothing. Fernet
    ciphertext is non-deterministic, so ``filter(password="x")`` can never
    match even when the value is right; an exception at the point of the
    mistake is much easier to understand than an empty queryset somewhere
    downstream.
    """

    description = "Encrypted text"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Build the field, defaulting to editable."""
        kwargs.setdefault("editable", True)
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection) -> str | None:
        """Decrypt on load."""
        if value is None:
            return None
        return decrypt(value)

    def to_python(self, value) -> str | None:
        """Coerce to the canonical Python type."""
        if value is None or isinstance(value, str):
            return value
        if isinstance(value, (bytes, memoryview)):
            return decrypt(value)
        return str(value)

    def get_prep_value(self, value) -> bytes | None:
        """Encrypt on save.

        Notes
        -----
        Empty and `None` both store as `NULL`. Encrypting the empty string
        would produce a ciphertext that decrypts to ``""`` -- so "this PI
        has not linked an account" and "this PI stored a blank password"
        would be indistinguishable without decrypting every row.
        """
        if value is None or value == "":
            return None
        if isinstance(value, (bytes, memoryview)):
            # Already ciphertext: a value that came from the database and is
            # being written back untouched.
            return bytes(value)
        return encrypt(str(value))

    def get_lookup(self, lookup_name):
        """Refuse lookups, which cannot work on non-deterministic ciphertext."""
        if lookup_name in ("isnull",):
            return super().get_lookup(lookup_name)
        raise FieldError(
            f"Cannot filter on {self.name!r}: it is encrypted, and Fernet "
            "ciphertext differs every time the same value is stored. Filter "
            "on the owning user instead."
        )

    def formfield(self, **kwargs):
        """Render as a normal text input rather than a binary widget."""
        from django import forms  # noqa: PLC0415

        defaults = {"form_class": forms.CharField, "required": not self.blank}
        defaults.update(kwargs)
        return super().formfield(**defaults)


def iter_encrypted_fields() -> Iterator[tuple[Any, "EncryptedField"]]:
    """Yield ``(model, field)`` for every `EncryptedField` in the project.

    Notes
    -----
    Discovered from the app registry rather than listed by hand, so a
    credential added later is picked up by key rotation without anyone
    remembering to register it.
    """
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if isinstance(field, EncryptedField):
                yield model, field
