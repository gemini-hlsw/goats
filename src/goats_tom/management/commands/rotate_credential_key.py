"""Re-encrypt stored credentials under the current ``SECRET_KEY``.

Run this after rotating ``SECRET_KEY``, once the new key is primary and the
old one has been moved into ``SECRET_KEY_FALLBACKS``. `decrypt` reads through
the fallbacks, so nothing breaks in the meantime; this command rewrites every
value under the new key so the fallback can then be removed.

Usage::

    # 1. New key in SECRET_KEY, old key in SECRET_KEY_FALLBACKS.
    # 2. Restart, confirm credentials still work.
    python manage.py rotate_credential_key
    # 3. Remove the old key from SECRET_KEY_FALLBACKS.

Notes
-----
Rows are loaded one at a time by primary key. A value that no key can decrypt
raises when the row loads, and loading the table in one queryset would let a
single bad row abort the whole rotation -- leaving some credentials rewritten
and others not, with no report of which. One at a time means a bad row is
reported and the rest still get rotated.
"""

from cryptography.fernet import InvalidToken
from django.core.management.base import BaseCommand

from goats_tom.encryption import iter_encrypted_fields


class Command(BaseCommand):
    help = (
        "Re-encrypt every stored credential under the current SECRET_KEY. "
        "Run after a key rotation, then remove the old key from "
        "SECRET_KEY_FALLBACKS."
    )

    def handle(self, *args, **options):
        rotated = 0
        failures = []

        for model, field in iter_encrypted_fields():
            label = f"{model._meta.label}.{field.name}"
            for pk in list(model._default_manager.values_list("pk", flat=True)):
                try:
                    instance = model._default_manager.get(pk=pk)
                    value = getattr(instance, field.attname)
                except InvalidToken:
                    failures.append(
                        f"{label} (pk={pk}): not decryptable with SECRET_KEY "
                        "or any SECRET_KEY_FALLBACKS entry"
                    )
                    continue
                if value is None:
                    continue
                # Assigning and saving re-encrypts under the primary key,
                # since `encrypt` never uses a fallback.
                setattr(instance, field.attname, value)
                instance.save(update_fields=[field.attname])
                rotated += 1

        self.stdout.write(
            self.style.SUCCESS(f"Re-encrypted {rotated} credential value(s).")
        )
        if failures:
            self.stdout.write(
                self.style.ERROR(
                    f"{len(failures)} value(s) could not be re-encrypted. These "
                    "must be re-entered by their owners:"
                )
            )
            for failure in failures:
                self.stdout.write(f"  {failure}")
        else:
            self.stdout.write(
                "SECRET_KEY_FALLBACKS can now be cleared."
            )
