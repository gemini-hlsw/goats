"""Tests for `goats_tom.storage`, the seam Phase 2 swaps.

The remote tests matter more than the local ones. Local is the desktop
invariant and would fail loudly; the remote branch is code that nothing
exercises yet, and the first thing to run it will be a VOSpace backend
handling somebody's proprietary data.
"""

import io
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import Storage, default_storage

from goats_tom import storage


class FakeRemoteStorage(Storage):
    """A storage backend with no local filesystem, like VOSpace will be.

    Notes
    -----
    Raises `NotImplementedError` from `path` exactly as Django's own
    non-filesystem backends do. That is the behaviour the ten former
    ``.data.path`` call sites would have hit.
    """

    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self.files = dict(files or {})
        self.open_count = 0

    def path(self, name):  # noqa: D102 - matches Django's contract
        raise NotImplementedError("This backend doesn't support absolute paths.")

    def exists(self, name) -> bool:  # noqa: D102
        return name in self.files

    def _open(self, name, mode="rb"):  # noqa: D102
        if name not in self.files:
            raise FileNotFoundError(name)
        self.open_count += 1
        return io.BytesIO(self.files[name])

    def open(self, name, mode="rb"):  # noqa: D102
        return self._open(name, mode)


@pytest.fixture
def remote(monkeypatch):
    """Swap `default_storage` for a backend with no local path."""
    fake = FakeRemoteStorage({"users/alice/goats/x.fits.bz2": b"REMOTE-BYTES"})
    monkeypatch.setattr(storage, "default_storage", fake)
    return fake


class TestNameOf:
    """`name_of` normalises the several things call sites hand it."""

    def test_accepts_a_plain_name(self):
        assert storage.name_of("a/b.fits") == "a/b.fits"

    def test_accepts_a_file_field(self):
        field = type("F", (), {"name": "a/b.fits"})()
        assert storage.name_of(field) == "a/b.fits"

    def test_accepts_a_data_product(self):
        field = type("F", (), {"name": "a/b.fits"})()
        product = type("DP", (), {"data": field})()
        assert storage.name_of(product) == "a/b.fits"

    def test_rejects_a_product_with_no_file(self):
        field = type("F", (), {"name": ""})()
        product = type("DP", (), {"data": field})()
        with pytest.raises(ValueError):
            storage.name_of(product)


class TestStorageName:
    """`storage_name` builds a name, never an absolute path."""

    def test_joins_with_forward_slashes(self):
        assert storage.storage_name("a/b", "c.fits") == "a/b/c.fits"

    def test_strips_a_leading_separator(self):
        assert storage.storage_name("/a", "b") == "a/b"

    def test_skips_empty_parts(self):
        assert storage.storage_name("", "a", "b.fits") == "a/b.fits"


class TestLocalBackend:
    """The desktop invariant: nothing is copied and nothing is deleted."""

    def test_supports_local_path(self):
        assert storage.supports_local_path() is True

    def test_yields_the_real_file_without_copying(self, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        name = default_storage.save("obs/f.fits", ContentFile(b"HELLO"))
        with storage.local_path(name) as path:
            assert path == Path(default_storage.path(name))
            assert path.read_bytes() == b"HELLO"

    def test_does_not_delete_the_real_file_on_exit(self, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        name = default_storage.save("obs/f.fits", ContentFile(b"HELLO"))
        with storage.local_path(name) as path:
            real = path
        assert real.exists(), "the local branch must never delete the real file"

    def test_missing_file_raises(self, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        with pytest.raises(FileNotFoundError):
            with storage.local_path("nope/missing.fits"):
                pass


class TestRemoteBackend:
    """The branch Phase 2 turns on, and that nothing exercises today."""

    NAME = "users/alice/goats/x.fits.bz2"

    def test_does_not_support_local_path(self, remote):
        assert storage.supports_local_path(remote) is False

    def test_fetches_the_bytes(self, remote):
        with storage.local_path(self.NAME) as path:
            assert path.read_bytes() == b"REMOTE-BYTES"

    def test_preserves_a_compound_suffix(self, remote):
        """``.fits.bz2`` must survive intact.

        Notes
        -----
        astrodata and `mimetypes` dispatch on the suffix, and
        `spectroscopy_processor` routes on the mimetype. Reconstructing the
        filename as ``stem + suffixes`` produced ``x.fits.fits.bz2``,
        because the stem of a compound suffix still carries the first part.
        """
        with storage.local_path(self.NAME) as path:
            assert path.name == "x.fits.bz2"

    def test_removes_the_temporary_file_on_exit(self, remote):
        with storage.local_path(self.NAME) as path:
            seen = path
        assert not seen.exists()
        assert not seen.parent.exists()

    def test_removes_the_temporary_file_after_an_exception(self, remote):
        """Proprietary bytes must not survive a failure.

        Notes
        -----
        The whole point of ``datalab`` mode is that science data does not
        rest on the control-plane VM. A temp file left behind by a raised
        exception would be exactly that, in ``/tmp``, unnoticed.
        """
        with pytest.raises(ValueError):
            with storage.local_path(self.NAME) as path:
                seen = path
                raise ValueError("boom")
        assert not seen.exists()

    def test_missing_file_raises(self, remote):
        with pytest.raises(FileNotFoundError):
            with storage.local_path("users/alice/goats/absent.fits"):
                pass
