"""Tests for `VOSpaceStorage`, the Phase 2 backend.

The name parsing tests carry the weight here. Django hands a storage backend
a name and nothing else, so that string is the only thing telling this class
whose VOSpace to touch -- and a name that parses wrongly does not fail, it
writes a PI's proprietary data into somebody else's account.

The client is mocked throughout. These tests are about the backend's
contract with Django and its handling of names; whether the Data Lab HTTP
API behaves is `test_client.py`'s problem, and neither can be checked here
without a live account.
"""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile

from goats_tom import storage as seam
from goats_tom.astro_data_lab import AstroDataLabConfig, VOSpaceStorage
from goats_tom.tests.factories import UserFactory

VALID = "users/alice/goats/obs/target/file.fits"


@pytest.fixture
def storage():
    """A backend with default configuration."""
    return VOSpaceStorage()


@pytest.fixture
def client(monkeypatch):
    """Replace `_client` with a mock, and hand back the mock."""
    fake = MagicMock()
    fake.__enter__ = MagicMock(return_value=fake)
    fake.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(VOSpaceStorage, "_client", lambda self, username: fake)
    return fake


class TestNameParsing:
    """The security boundary: which names are allowed to reach VOSpace."""

    def test_parses_owner_and_relative_path(self, storage):
        assert storage._split(VALID) == ("alice", "obs/target/file.fits")

    def test_tolerates_surrounding_separators(self, storage):
        assert storage._split(f"/{VALID}/") == ("alice", "obs/target/file.fits")

    @pytest.mark.parametrize(
        "name",
        [
            "",
            "   ",
            None,
            "file.fits",
            "obs/target/file.fits",
            "users/alice/file.fits",
            "users/alice/goats",
            "notusers/alice/goats/file.fits",
            "users//goats/file.fits",
            "users/alice/notgoats/file.fits",
        ],
    )
    def test_refuses_a_name_with_no_identifiable_owner(self, storage, name):
        """A name that does not name an owner must never be guessed at.

        Notes
        -----
        Refusing is safe; guessing is not. A rejected write fails loudly and
        stops a download. A guessed one puts proprietary data in the wrong
        PI's storage, and nothing downstream would notice.
        """
        with pytest.raises(SuspiciousFileOperation):
            storage._split(name)

    @pytest.mark.parametrize(
        "name",
        [
            "users/alice/goats/../../bob/goats/file.fits",
            "users/alice/goats/..",
            "users/../alice/goats/file.fits",
        ],
    )
    def test_refuses_traversal(self, storage, name):
        """``..`` is rejected, not normalized.

        Notes
        -----
        Normalizing would silently accept a name written to escape the
        root, and the only reason to write one is to try.
        """
        with pytest.raises(SuspiciousFileOperation):
            storage._split(name)


class TestStorageAPI:
    """The methods Django and `goats_tom.storage` actually call."""

    def test_open_returns_the_bytes(self, storage, client):
        client.read.return_value = b"FITS-BYTES"
        assert storage._open(VALID).read() == b"FITS-BYTES"
        client.read.assert_called_once_with("obs/target/file.fits")

    def test_open_refuses_write_modes(self, storage, client):
        """A writable handle would silently discard everything written.

        Notes
        -----
        VOSpace has no partial writes, so there is nothing to hand back that
        would behave like a file opened for writing. Failing here is far
        better than accepting the write and losing it.
        """
        for mode in ("wb", "ab", "rb+"):
            with pytest.raises(ValueError):
                storage._open(VALID, mode)

    def test_save_writes_and_returns_the_name(self, storage, client):
        assert storage._save(VALID, ContentFile(b"DATA")) == VALID
        relative_path, payload = client.write.call_args[0]
        assert relative_path == "obs/target/file.fits"
        assert payload.read() == b"DATA"

    def test_save_reads_from_the_start(self, storage, client):
        """Content already read from must still be stored whole.

        Notes
        -----
        Django may have inspected the content before handing it over --
        sniffing a content type, for instance -- leaving the cursor at the
        end. Without a seek this writes an empty file and reports success.
        """
        content = ContentFile(b"DATA")
        content.read()
        storage._save(VALID, content)
        assert client.write.call_args[0][1].read() == b"DATA"

    def test_delete_removes_the_file(self, storage, client):
        storage.delete(VALID)
        client.delete.assert_called_once_with("obs/target/file.fits")

    def test_exists_asks_the_client(self, storage, client):
        client.exists.return_value = True
        assert storage.exists(VALID) is True

    def test_size_measures_the_content(self, storage, client):
        client.read.return_value = b"12345"
        assert storage.size(VALID) == 5

    def test_listdir_returns_everything_as_files(self, storage, client):
        client.listdir.return_value = ["a.fits", "b.fits"]
        assert storage.listdir(VALID) == ([], ["a.fits", "b.fits"])

    def test_url_points_at_goats_not_vospace(self, storage):
        """The URL must not be a Data Lab link.

        Notes
        -----
        Data Lab download URLs are one-shot and expire, so one written into
        a template is broken by the time anybody clicks it -- and a link
        that leaked would carry the token with it. Routing through GOATS
        also keeps the permission check in front of the bytes.
        """
        url = storage.url(VALID)
        assert "vos://" not in url
        assert "datalab" not in url
        assert url.startswith("/dataproducts/stream/")

    def test_every_operation_refuses_an_unparseable_name(self, storage, client):
        """The boundary holds on every entry point, not only `_split`."""
        for call in (
            lambda: storage._open("bad/name.fits"),
            lambda: storage._save("bad/name.fits", ContentFile(b"x")),
            lambda: storage.delete("bad/name.fits"),
            lambda: storage.exists("bad/name.fits"),
            lambda: storage.size("bad/name.fits"),
            lambda: storage.listdir("bad/name.fits"),
        ):
            with pytest.raises(SuspiciousFileOperation):
                call()


class TestUnsupportedOperations:
    """What this backend cannot do, and must say so loudly."""

    def test_path_raises_not_implemented(self, storage):
        """The exception Phase 1 existed to make survivable.

        Notes
        -----
        Ten call sites used to reach `FieldFile.path` directly and every one
        would have died here on the first request in `datalab` mode. They
        now go through `goats_tom.storage.local_path`, which fetches to a
        temporary file when the backend cannot answer this.
        """
        with pytest.raises(NotImplementedError):
            storage.path(VALID)

    def test_timestamps_raise_not_implemented(self, storage):
        for getter in (
            storage.get_created_time,
            storage.get_modified_time,
            storage.get_accessed_time,
        ):
            with pytest.raises(NotImplementedError):
                getter(VALID)


@pytest.mark.django_db
class TestCredentialResolution:
    """Turning a username in a name into a Data Lab account."""

    def test_refuses_an_unknown_user(self, storage):
        with pytest.raises(SuspiciousFileOperation):
            storage._client("nobody-by-that-name")

    def test_refuses_a_user_with_no_linked_account(self, storage):
        user = UserFactory(username="unlinked")
        assert not hasattr(user, "astrodatalablogin")
        with pytest.raises(SuspiciousFileOperation):
            storage._client("unlinked")

    @patch("goats_tom.astro_data_lab.storage.AstroDataLabClient")
    def test_uses_the_datalab_username_for_the_root(self, client_cls, storage):
        """The GOATS username and the Data Lab username may differ.

        Notes
        -----
        The name identifies the *GOATS* user; their linked account supplies
        the Data Lab one, and the VOSpace root is built from that. Assuming
        the two match works for everyone who registered both with the same
        handle and fails for the first PI who did not -- by writing into
        whichever Data Lab account happens to hold that name.
        """
        from goats_tom.tests.factories import AstroDatalabLoginFactory

        user = UserFactory(username="goats_name")
        AstroDatalabLoginFactory(user=user, username="datalab_name")

        storage._client("goats_name")

        assert client_cls.call_args.kwargs["root"] == "vos://users/datalab_name/goats"


class TestSeamIntegration:
    """Phase 1's seam against the real Phase 2 backend.

    Notes
    -----
    Every other remote test in the codebase runs against a hand-written fake
    `Storage`. This is the one that puts the two halves together, and it is
    the check that matters: `local_path` was written before `VOSpaceStorage`
    existed, against an assumption about how a non-filesystem backend would
    behave.
    """

    def test_local_path_fetches_and_cleans_up(self, monkeypatch, client):
        backend = VOSpaceStorage()
        client.read.return_value = b"REMOTE"
        monkeypatch.setattr(seam, "default_storage", backend)

        assert seam.supports_local_path(backend) is False

        with seam.local_path("users/alice/goats/obs/t/f.fits.bz2") as path:
            seen = path
            assert path.read_bytes() == b"REMOTE"
            # Compound suffix intact: `spectroscopy_processor` routes on the
            # mimetype, so a mangled one misroutes bz2 files in datalab mode
            # only.
            assert path.name == "f.fits.bz2"

        assert not seen.exists()
        assert not seen.parent.exists()


class TestConfig:
    """Per-user roots, which are the point of the whole exercise."""

    def test_builds_a_per_user_root(self):
        assert (
            AstroDataLabConfig().user_root("alice") == "vos://users/alice/goats"
        )

    def test_user_root_is_not_the_shared_directory(self):
        """One folder shared by every PI is what this mode replaces.

        Notes
        -----
        `remote_directory` stays as the default for the "Send to Data Lab"
        button, whose behaviour is unchanged. The storage backend must not
        inherit it.
        """
        config = AstroDataLabConfig()
        assert config.user_root("alice") != config.remote_directory


class TestClientPaths:
    """`remote_uri`, which decides what the HTTP layer is handed."""

    def _client(self):
        from goats_tom.astro_data_lab import AstroDataLabClient

        return AstroDataLabClient(
            username="alice", password="x", root="vos://users/alice/goats"
        )

    def test_joins_a_relative_path(self):
        assert (
            self._client().remote_uri("obs/f.fits")
            == "vos://users/alice/goats/obs/f.fits"
        )

    def test_empty_path_is_the_root(self):
        assert self._client().remote_uri("") == "vos://users/alice/goats"

    def test_strips_stray_separators(self):
        assert (
            self._client().remote_uri("/obs/f.fits/")
            == "vos://users/alice/goats/obs/f.fits"
        )

    def test_write_creates_parent_directories(self):
        """Django backends are expected to create directories silently.

        Notes
        -----
        `FileSystemStorage` does, so code written against it never creates
        them first. ``/storage/mkdir`` does not make intermediate
        directories, so each level has to be walked.
        """
        client = self._client()
        client.token = "t"
        with patch.object(client, "makedirs") as makedirs, patch.object(
            client._session, "get"
        ) as get, patch.object(client._session, "put") as put:
            get.return_value = MagicMock(status_code=200, text="https://upload")
            put.return_value = MagicMock(status_code=200)
            client.write("obs/target/f.fits", BytesIO(b"x"))

        makedirs.assert_called_once_with("obs/target")
