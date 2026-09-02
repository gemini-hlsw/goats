"""The single seam between GOATS and where data product files actually live.

Everything in GOATS that touches a data product's bytes goes through this
module. Today it resolves to `MEDIA_ROOT` on the GOATS host and behaves
exactly as the code it replaces. In ``datalab`` mode a later change swaps
`default_storage` for a VOSpace backend and nothing above this module has to
know.

Why this exists
---------------
The plan recorded in ``STATUS.md`` assumed the swap would be free, because
"everything already goes through ``product.data.url``, ``.open()`` and
``.path``". It does not. Two shapes were in the way:

- **`FieldFile.path`**, in ten places. Django raises `NotImplementedError`
  for `path` on any storage that is not a local filesystem, and says so in
  its own docs. Every one of those call sites would have died on the first
  request in ``datalab`` mode.
- **Hand-built `settings.MEDIA_ROOT / …` joins**, in eight more. These never
  touch the storage API at all, so swapping the backend would not have
  changed them -- they would have gone on quietly reading and writing the
  control-plane disk, which is the exact failure ``datalab`` mode exists to
  prevent, and it would have been silent.

The second shape is the dangerous one. A `NotImplementedError` is loud. A
file written to the wrong disk is not.

The two helpers
---------------
`local_path` is for code that genuinely needs a file on a filesystem --
astrodata, DRAGONS, jdaviz, anything handing a path to a C library. Locally
it yields the real file and copies nothing. Remotely it will fetch to a
temporary file and clean up after. Callers do not change.

`working_root` is for code that builds a *directory* to write into. Django's
storage API has no notion of a directory, so this cannot be expressed
through it, and pretending otherwise would be worse than naming the problem.
Those call sites are still local today and are Phase 3 and 4 work. Routing
them through one named function means there is one place to change and one
thing to grep for, rather than eight joins that look like ordinary path
arithmetic.

Notes
-----
`local_path` yields a **read-only** view. Locally that is the real file, so a
write would land; remotely it would be a temporary copy discarded on exit.
Nothing may rely on writing through it, because the two modes would differ
silently -- which is the failure this module is here to make impossible.
Code that needs to write goes through `default_storage.save` or, for a whole
working directory, `working_root`.
"""

__all__ = [
    "local_path",
    "name_of",
    "storage_name",
    "supports_local_path",
    "working_root",
]

import contextlib
import logging
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Iterator, Union

from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

#: A data product's file, the storage name of one, or anything with a
#: ``data`` attribute holding either.
FileLike = Union[str, os.PathLike, "object"]


def supports_local_path(storage=None) -> bool:
    """Whether `storage` can hand out a real filesystem path.

    Parameters
    ----------
    storage : optional
        Storage backend to test. Defaults to Django's `default_storage`.

    Returns
    -------
    bool
        True for `FileSystemStorage` and anything else implementing `path`.

    Notes
    -----
    Asked by calling `path` rather than by checking the class, so a
    subclass or a wrapper is judged on what it does rather than on what it
    inherits from.
    """
    storage = storage or default_storage
    try:
        storage.path("probe")
    except NotImplementedError:
        return False
    except Exception:
        # Any other failure -- a suspicious-name check, a misconfigured
        # location -- means the backend does implement `path` and simply
        # disliked the probe. That still answers the question asked.
        return True
    return True


def name_of(target: FileLike) -> str:
    """Return the storage-relative name for `target`.

    Parameters
    ----------
    target : str, `os.PathLike`, `FieldFile` or `DataProduct`
        A storage name, a file field, or a model instance carrying one in
        ``data``.

    Returns
    -------
    str
        The name as the storage backend understands it.

    Raises
    ------
    ValueError
        If `target` holds no file.

    Notes
    -----
    Accepts a `DataProduct` directly because most call sites have one, and
    making each of them reach for ``.data`` is how ``.data.path`` spread in
    the first place.
    """
    data = getattr(target, "data", None)
    if data is not None and hasattr(data, "name"):
        target = data

    name = getattr(target, "name", target)
    if not name:
        raise ValueError("No file is associated with this data product.")

    return str(name)


def storage_name(*parts: Union[str, os.PathLike]) -> str:
    """Join `parts` into a storage-relative name.

    Returns
    -------
    str
        Forward-slash separated, with no leading separator.

    Notes
    -----
    Replaces ``settings.MEDIA_ROOT / a / b`` wherever the result was only
    ever used as a *name* -- an existence check, a ``product_id``, a value
    stored on a model. Those joins produced an absolute local path and then
    handed it to code expecting a relative one, which worked by accident:
    `FileSystemStorage` calls `safe_join(location, name)`, and an absolute
    name that happens to sit under the location survives the check. It
    would not survive a backend with a different root.

    Always POSIX separators, because a storage name is not a filesystem
    path and must not become one on Windows.
    """
    joined = PurePosixPath(*[str(p).replace(os.sep, "/") for p in parts if p != ""])
    return str(joined).lstrip("/")


def working_root() -> Path:
    """Return the local directory GOATS builds working trees under.

    Returns
    -------
    `pathlib.Path`
        ``settings.MEDIA_ROOT`` today, on every mode.

    Notes
    -----
    **This is deliberately still local, and deliberately still one
    function.** GOA downloads and DRAGONS run folders create real
    directories, unpack tarfiles into them and hand them to code that walks
    them. Django's storage API cannot express any of that, so there is no
    honest way to route it through `default_storage`.

    Moving this work off the control-plane VM is Phase 3 and Phase 4 -- the
    download and the reduction both run on Data Lab, and neither needs a
    directory here at all. Until then, every caller that needs a directory
    goes through this function, so the set is enumerable by grep rather
    than by memory. That is the whole value of it existing today.
    """
    return Path(settings.MEDIA_ROOT)


@contextlib.contextmanager
def local_path(target: FileLike) -> Iterator[Path]:
    """Yield a real filesystem path to `target`'s bytes.

    Parameters
    ----------
    target : str, `os.PathLike`, `FieldFile` or `DataProduct`
        The file to make locally readable.

    Yields
    ------
    `pathlib.Path`
        A path that exists on this machine for the duration of the block.

    Raises
    ------
    FileNotFoundError
        If the storage backend holds no such file.

    Notes
    -----
    Replaces `FieldFile.path`, which raises `NotImplementedError` on any
    non-filesystem backend.

    Copies nothing when the backend is local: the real file is yielded, so
    the desktop install does exactly what it did before and pays nothing.
    The temporary-file branch only runs under a remote backend.

    The filename is reused verbatim inside a fresh temporary directory.
    astrodata and `mimetypes` both dispatch on the suffix, so a temporary
    file that lost or doubled it would change behaviour between modes in a
    way that would surface far from here -- and a compound suffix like
    ``.fits.bz2`` makes the obvious ``stem + suffixes`` reconstruction
    wrong, because the stem still carries the first one. The directory is
    unique, so nothing is gained by renaming the file.

    Read-only. See the module docstring.
    """
    name = name_of(target)

    if supports_local_path():
        path = Path(default_storage.path(name))
        if not path.exists():
            raise FileNotFoundError(f"File missing from storage: {name}")
        yield path
        return

    tmp_dir = tempfile.mkdtemp(prefix="goats-")
    tmp_path = Path(tmp_dir) / PurePosixPath(name).name

    try:
        logger.debug("Fetching %s from remote storage to %s.", name, tmp_path)
        with default_storage.open(name, "rb") as remote, open(tmp_path, "wb") as local:
            shutil.copyfileobj(remote, local)
        yield tmp_path
    finally:
        # Proprietary data. Remove it even if the block raised, and do not
        # let a cleanup failure mask the original exception.
        shutil.rmtree(tmp_dir, ignore_errors=True)
