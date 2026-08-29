"""Encrypt stored third-party credentials at rest.

Converts every secret credential field from a plaintext `CharField` to
`goats_tom.encryption.EncryptedField`, which stores Fernet ciphertext
in a `BinaryField` keyed from ``settings.SECRET_KEY``.

Why three steps rather than one `AlterField`
--------------------------------------------
The column type changes from text to binary *and* the existing values need
transforming. A bare `AlterField` would hand Postgres a column full of
plaintext and ask it to reinterpret those bytes as ciphertext; every
subsequent read would raise `InvalidToken`, and every PI's stored credentials
would be silently unusable until they noticed and re-entered them.

So: add the new column, copy each value through `encrypt()`, then drop the
old column and rename. Nobody has to re-enter anything.

Reversibility
-------------
The reverse migration decrypts back to plaintext. It exists so a bad deploy
can be rolled back rather than stranding the database on a schema the
previous release cannot read. It is genuinely destructive of the security
property, which is the point of a rollback.

**Take a backup before running this.** If ``SECRET_KEY`` changes between the
forward migration and the next read, the credentials are unrecoverable --
there is no fallback to plaintext once the old column is dropped. See the
deployment note in STATUS.md.
"""

from django.db import migrations, models
from goats_tom.encryption import EncryptedField, decrypt, encrypt

#: ``(model, field)`` pairs to convert.
#:
#: Secrets only. Usernames and bot identifiers stay plaintext: they are not
#: secret, the credential page displays them, and encrypted columns cannot be
#: filtered on.
ENCRYPTED_FIELDS = [
    ("astrodatalablogin", "password"),
    ("astrodatalablogin", "jupyter_token"),
    ("goalogin", "password"),
    ("gpplogin", "token"),
    ("lcologin", "token"),
    ("tnslogin", "token"),
    ("antareskafkalogin", "api_key"),
    ("antareskafkalogin", "api_secret"),
    ("rsptaplogin", "access_token"),
]


def encrypt_values(apps, schema_editor):
    """Copy each plaintext credential into its encrypted column.

    Notes
    -----
    Uses `encrypt` directly rather than assigning through the model field,
    because a historical model in a migration does not carry the custom
    field class -- `apps.get_model` rebuilds it from the migration state,
    where the new column is a plain `BinaryField`.

    Empty and null values are left null rather than encrypted. Encrypting
    the empty string produces a ciphertext that decrypts to `""`, which is
    indistinguishable from "a credential was set to nothing" and would make
    "has this PI linked their account?" answerable only by decrypting every
    row.
    """
    for model_name, field in ENCRYPTED_FIELDS:
        model = apps.get_model("goats_tom", model_name)
        for row in model.objects.all().iterator():
            plaintext = getattr(row, field, None)
            if not plaintext:
                continue
            setattr(row, f"{field}_encrypted", encrypt(plaintext))
            row.save(update_fields=[f"{field}_encrypted"])


def decrypt_values(apps, schema_editor):
    """Copy each encrypted credential back to plaintext, for rollback.

    Notes
    -----
    A row that cannot be decrypted -- because ``SECRET_KEY`` changed after
    the forward migration -- is left empty rather than raising. Blocking a
    rollback on one unreadable credential would be the wrong trade: the PI
    can re-enter it, but an unrollbackable deploy is a much worse position
    to be in.
    """
    for model_name, field in ENCRYPTED_FIELDS:
        model = apps.get_model("goats_tom", model_name)
        for row in model.objects.all().iterator():
            ciphertext = getattr(row, f"{field}_encrypted", None)
            if not ciphertext:
                continue
            if isinstance(ciphertext, memoryview):
                ciphertext = ciphertext.tobytes()
            try:
                setattr(row, field, decrypt(ciphertext))
            except Exception:
                setattr(row, field, "")
            row.save(update_fields=[field])


class Migration(migrations.Migration):
    dependencies = [
        ("goats_tom", "0016_antaresstreamsubscription_last_handler_warning_is_error"),
    ]

    operations = (
        # 1. Add the encrypted columns alongside the plaintext ones.
        [
            migrations.AddField(
                model_name=model_name,
                name=f"{field}_encrypted",
                field=models.BinaryField(blank=True, null=True),
            )
            for model_name, field in ENCRYPTED_FIELDS
        ]
        # 2. Move the data across.
        + [migrations.RunPython(encrypt_values, decrypt_values)]
        # 3. Drop the plaintext columns and take their names.
        + [
            migrations.RemoveField(model_name=model_name, name=field)
            for model_name, field in ENCRYPTED_FIELDS
        ]
        + [
            migrations.RenameField(
                model_name=model_name,
                old_name=f"{field}_encrypted",
                new_name=field,
            )
            for model_name, field in ENCRYPTED_FIELDS
        ]
        # 4. Restore the real field class, so the model's Python interface is
        #    `str` again and `rotate_credential_key` can find these columns.
        + [
            migrations.AlterField(
                model_name=model_name,
                name=field,
                field=EncryptedField(
                    blank=(model_name == "astrodatalablogin" and field == "jupyter_token"),
                    null=True,
                ),
            )
            for model_name, field in ENCRYPTED_FIELDS
        ]
    )
