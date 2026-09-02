"""A Django storage backend that keeps data product files in VOSpace.

Phase 2 of *Remaining Data Lab work*. Sits behind the seam Phase 1 built, so
nothing above `goats_tom.storage` changes when it is switched on.

Whose VOSpace
-------------
Django hands a storage backend a **name and nothing else** -- no request, no
user, no way to ask. So the owner has to be readable from the name itself,
and every name this backend accepts looks like::

    users/<username>/goats/<anything>/<file.fits>

`_split` parses the username out and refuses anything that does not match.
That refusal is the whole security boundary of this class: a name that does
not parse must never reach VOSpace, because the alternative is guessing whose
account to write to.

Refusing is safe in a way that guessing is not. A rejected write fails loudly
and stops a download; a guessed one puts a PI's proprietary data in somebody
else's storage, silently, and nothing in GOATS would notice.

What this does not do
---------------------
**Downloads still land on the VM.** `astroquery/gemini.py` streams a tarball
to local disk, untars it, decompresses each member and opens the results with
astrodata -- every step needs a filesystem, and no storage backend changes
that. Moving the download onto Data Lab is Phase 3.

**Reduction still needs local files.** `Reduce.files` wants every input
present on one filesystem at once, which `local_path` cannot promise. Phase 4.

**So this ships inert.** Enabling it while reduction is local also breaks the
calibration database: `cal_db.add_cal` records a path that outlives the block
it came from, and under this backend that path is a temporary file already
deleted -- reductions would then fail to find their calibrations, with no
error naming the cause. Phase 4 moves the caldb to the remote run folder,
where the path is durable, and that is what resolves it. Until then this
class is built, tested and switched off.
"""

__all__ = ["VOSpaceStorage"]

import logging
from io import BytesIO
from typing import Optional
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

from .client import AstroDataLabClient
from .config import AstroDataLabConfig

logger = logging.getLogger(__name__)

#: The path segment between the username and the rest of the name.
GOATS_PREFIX = "goats"

#: The path segment every name starts with.
USERS_PREFIX = "users"


@deconstructible
class VOSpaceStorage(Storage):
    """Store data product files in each user's Astro Data Lab VOSpace.

    Parameters
    ----------
    config : `AstroDataLabConfig`, optional
        Client configuration. Defaults to `AstroDataLabConfig()`.

    Notes
    -----
    `deconstructible` because `FileField(storage=...)` is serialized into
    migrations. Without it, adding this backend to a field would write a
    repr Django cannot reconstruct and every subsequent migration would
    fail to load.

    One client is built per operation rather than held open. Data Lab
    science tokens expire, and a cached client would fail in the way
    `AstroDatalabLogin` documents as the worst case -- ``queryClient``
    reporting ``'OK'`` whatever the service said, so a stale token reads as
    a silent no-op instead of an authentication error. Minting per call
    trades a login round trip for failures that say what went wrong.
    """

    def __init__(self, config: Optional[AstroDataLabConfig] = None) -> None:
        self.config = config or AstroDataLabConfig()

    # -- Name handling ----------------------------------------------------

    def _split(self, name: str) -> tuple[str, str]:
        """Split `name` into its owner and the path under their GOATS root.

        Parameters
        ----------
        name : str
            A storage name.

        Returns
        -------
        tuple of (str, str)
            ``(username, relative_path)``.

        Raises
        ------
        SuspiciousFileOperation
            If `name` does not identify an owner, escapes the root, or is
            empty.

        Notes
        -----
        `SuspiciousFileOperation` rather than `ValueError` because that is
        what Django raises for a name it will not touch, and what the rest
        of the stack -- `FileField`, the admin, DRF -- already handles.

        ``..`` is rejected outright rather than normalized away. Normalizing
        would silently accept a name written to escape the root, and the
        only reason to write one is to try.
        """
        cleaned = str(name or "").strip().strip("/")
        if not cleaned:
            raise SuspiciousFileOperation("Empty storage name.")

        parts = cleaned.split("/")
        if ".." in parts:
            raise SuspiciousFileOperation(
                f"Storage name attempts to escape its root: {name!r}"
            )

        if len(parts) < 4 or parts[0] != USERS_PREFIX or parts[2] != GOATS_PREFIX:
            raise SuspiciousFileOperation(
                f"Storage name {name!r} does not identify an owner. Names must "
                f"look like '{USERS_PREFIX}/<username>/{GOATS_PREFIX}/<path>' "
                "so this backend can tell whose VOSpace to write to."
            )

        username = parts[1]
        if not username:
            raise SuspiciousFileOperation(f"Storage name {name!r} has no username.")

        return username, "/".join(parts[3:])

    # -- Credentials ------------------------------------------------------

    def _client(self, username: str) -> AstroDataLabClient:
        """Build a logged-in client for `username`'s VOSpace.

        Parameters
        ----------
        username : str
            The **GOATS** username parsed out of the storage name.

        Returns
        -------
        `AstroDataLabClient`

        Raises
        ------
        SuspiciousFileOperation
            If the user does not exist or has not linked a Data Lab account.

        Notes
        -----
        The GOATS username and the Data Lab username are **not** assumed to
        match. The name identifies the GOATS user; their `AstroDatalabLogin`
        supplies the Data Lab account, and the VOSpace root is built from
        *that*. Assuming they match would work for every developer who
        registered both with the same handle and fail for the first PI who
        did not -- by writing into another Data Lab account's storage, if one
        happens to hold that name.
        """
        user_model = get_user_model()
        try:
            user = user_model.objects.get(username=username)
        except user_model.DoesNotExist as exc:
            raise SuspiciousFileOperation(
                f"Storage name names a user who does not exist: {username!r}"
            ) from exc

        credentials = getattr(user, "astrodatalablogin", None)
        if credentials is None or not credentials.username:
            raise SuspiciousFileOperation(
                f"{username} has no linked Astro Data Lab account, so their "
                "files have nowhere to live. Link one in Settings."
            )

        client = AstroDataLabClient(
            username=credentials.username,
            password=credentials.password,
            config=self.config,
            root=self.config.user_root(credentials.username),
        )
        client.login()
        return client

    # -- Django's Storage API ---------------------------------------------

    def _open(self, name: str, mode: str = "rb"):
        """Return the file at `name` as an in-memory Django `File`.

        Raises
        ------
        ValueError
            For any write mode. VOSpace has no partial writes, so a
            writable handle would silently discard everything written to it.
        """
        if "w" in mode or "a" in mode or "+" in mode:
            raise ValueError(
                f"VOSpaceStorage cannot open files for writing (mode {mode!r}). "
                "Use `save` instead."
            )
        username, relative_path = self._split(name)
        with self._client(username) as client:
            return ContentFile(client.read(relative_path), name=name)

    def _save(self, name: str, content) -> str:
        """Write `content` to `name` and return the name stored."""
        username, relative_path = self._split(name)
        content.seek(0)
        payload = content.read()
        with self._client(username) as client:
            client.write(relative_path, BytesIO(payload))
        logger.info("Wrote %s to %s's VOSpace.", relative_path, username)
        return name

    def delete(self, name: str) -> None:
        """Remove `name` from its owner's VOSpace.

        Notes
        -----
        **This destroys the file, not a database row**, and GOATS cannot
        restore it. Every path that reaches here is one of the ten in *The
        delete ban*; that section is the guard on this method, not a
        neighbouring concern.
        """
        username, relative_path = self._split(name)
        with self._client(username) as client:
            client.delete(relative_path)
        logger.info("Deleted %s from %s's VOSpace.", relative_path, username)

    def exists(self, name: str) -> bool:
        """Whether `name` is present in its owner's VOSpace."""
        username, relative_path = self._split(name)
        with self._client(username) as client:
            return client.exists(relative_path)

    def listdir(self, path: str) -> tuple[list, list]:
        """List `path`.

        Notes
        -----
        Returns everything as files with no directories. The ``/storage/ls``
        response does not reliably distinguish the two, and guessing from
        the presence of a suffix would misfile any directory containing a
        dot. Nothing in GOATS calls `listdir`; it is implemented so the
        backend satisfies Django's interface rather than raising somewhere
        surprising.
        """
        username, relative_path = self._split(path)
        with self._client(username) as client:
            return [], client.listdir(relative_path)

    def size(self, name: str) -> int:
        """Return the size of `name` in bytes.

        Notes
        -----
        Reads the file to measure it, because ``/storage/ls`` does not
        return a size. Expensive, and worth knowing before calling it on a
        FITS file -- but Django uses `size` in places that would otherwise
        raise, so an expensive answer beats none.
        """
        username, relative_path = self._split(name)
        with self._client(username) as client:
            return len(client.read(relative_path))

    def url(self, name: str) -> str:
        """Return a GOATS URL that streams `name`.

        Notes
        -----
        Deliberately **not** a VOSpace URL. Data Lab download links are
        one-shot and expire, so one written into a template would be broken
        by the time anybody clicked it, and a link that leaked would carry
        the token with it. Routing through GOATS also keeps the permission
        check in front of the bytes, which a direct link would bypass
        entirely.
        """
        return f"/dataproducts/stream/{quote(name.strip('/'))}"

    def path(self, name: str):
        """Not supported.

        Raises
        ------
        NotImplementedError
            Always. VOSpace is not a filesystem.

        Notes
        -----
        This is the exception Phase 1 existed to make survivable: ten call
        sites used to reach `FieldFile.path` directly and every one of them
        would have died here on the first request. They now go through
        `goats_tom.storage.local_path`, which fetches to a temporary file
        when the backend cannot answer this.
        """
        raise NotImplementedError("VOSpace does not support absolute paths.")

    def get_created_time(self, name: str):
        """Not supported.

        Raises
        ------
        NotImplementedError
            Always. ``/storage/ls`` does not report timestamps.
        """
        raise NotImplementedError("VOSpace does not report file timestamps.")

    get_modified_time = get_created_time
    get_accessed_time = get_created_time
