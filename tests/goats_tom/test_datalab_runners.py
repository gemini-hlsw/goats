"""Tests for the runners that execute on Astro Data Lab.

**These runners cannot be tested where they run.** They are detached
processes inside somebody else's Jupyter server, against a real account. What
is testable here is their pure logic: the tar and bz2 streaming, the status
protocol the VM depends on, and the naming that has to agree with
`VOSpaceStorage`.

Imported as standalone modules rather than through `goats_tom`, because that
is how they run: staged as a single file with no GOATS package available. If
either grows a `goats_tom` import, these tests stop working -- which is the
point.
"""

import bz2
import importlib.util
import io
import json
import tarfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

RUNNER_DIR = Path(__file__).resolve().parents[2] / "src" / "goats_tom" / "remote"


def _load(name):
    """Import a runner the way Data Lab does: as a lone file."""
    spec = importlib.util.spec_from_file_location(name, RUNNER_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


download = _load("download_runner")
reduction = _load("reduction_runner")


def _tarball(members):
    """Build an in-memory tarball of ``{name: bytes}``."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, payload in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    buffer.seek(0)
    return buffer


class TestNoGoatsImports:
    """The runners must stand alone.

    Notes
    -----
    They are staged onto Data Lab as single files, where the `goats_tom`
    package does not exist. An import added here would fail at runtime in a
    detached process, reported an hour later as a job that never started.
    """

    @pytest.mark.parametrize("name", ["download_runner", "reduction_runner"])
    def test_runner_imports_no_goats(self, name):
        """Checked by parsing imports, not by searching the text.

        Notes
        -----
        A substring search matches the docstrings, which legitimately name
        `goats_tom.astro_data_lab.headless` as the thing that launches
        these. Only actual import statements matter.
        """
        import ast

        tree = ast.parse((RUNNER_DIR / f"{name}.py").read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        assert "goats_tom" not in imported
        assert "django" not in imported


class TestDecompression:
    """Members arrive as `.fits.bz2` and must come out as FITS."""

    def test_decompresses_bz2_members(self):
        payload = b"FITS-CONTENT" * 100
        member = io.BytesIO(bz2.compress(payload))
        assert b"".join(download._decompress(member, "x.fits.bz2")) == payload

    def test_passes_through_plain_members(self):
        """Not everything in a GOA tarball is compressed.

        Notes
        -----
        Refusing uncompressed members would silently drop data the caller
        asked for.
        """
        payload = b"PLAIN"
        assert b"".join(download._decompress(io.BytesIO(payload), "x.fits")) == payload

    def test_reads_compressed_input_in_chunks(self):
        """Large files must not be held whole in memory.

        Notes
        -----
        A decompressed FITS file is routinely hundreds of megabytes, and
        several concurrent jobs on one notebook server would exhaust it.
        `bz2.decompress` would do exactly that.

        Uses **incompressible** data on purpose. A payload of repeated bytes
        compresses to a few kilobytes, fits in one `CHUNK_BYTES` read, and
        yields a single chunk however incremental the code is -- so it would
        pass against a `bz2.decompress` implementation too, and prove
        nothing.
        """
        import os as _os

        payload = _os.urandom(4 * 1024 * 1024)
        compressed = bz2.compress(payload)
        assert len(compressed) > download.CHUNK_BYTES, "payload must not compress"

        reader = io.BytesIO(compressed)
        chunks = list(download._decompress(reader, "x.bz2"))
        assert b"".join(chunks) == payload
        assert len(chunks) > 1


class TestDownloadRun:
    """One pass over a tarball, writing each member to VOSpace."""

    @pytest.fixture
    def spec(self, tmp_path):
        return {
            "datalab_base_url": "https://example.invalid",
            "datalab_token": "token",
            "vospace_root": "vos://users/alice/goats",
            "destination_prefix": "M31/GEM/GS-2026A-Q-1-1",
            "goa_url": "https://archive.gemini.edu/download/x",
        }

    def _run(self, monkeypatch, tmp_path, spec, members):
        uploads = {}

        class FakeVOSpace:
            def __init__(self, **kwargs):
                pass

            def put(self, destination, data):
                uploads[destination] = data.read() if hasattr(data, "read") else b"".join(data)

        monkeypatch.setattr(download, "VOSpace", FakeVOSpace)
        response = MagicMock()
        response.raw = _tarball(members)
        monkeypatch.setattr(download, "open_goa_stream", lambda spec: response)

        result = download.run_download(spec, str(tmp_path))
        return result, uploads

    def test_writes_each_member(self, monkeypatch, tmp_path, spec):
        payload = b"FITS"
        result, uploads = self._run(
            monkeypatch, tmp_path, spec, {"a.fits.bz2": bz2.compress(payload)}
        )
        assert result["state"] == "finished"
        assert result["seen"] == 1 and result["kept"] == 1
        assert uploads == {"M31/GEM/GS-2026A-Q-1-1/a.fits": payload}

    def test_strips_the_bz2_suffix(self, monkeypatch, tmp_path, spec):
        """The stored name must be what the VM will look for.

        Notes
        -----
        The VM builds `DataProduct.data` names without `.bz2`, so a member
        stored with the suffix intact produces a row pointing at a file that
        does not exist -- and nothing errors, because the write succeeded.
        """
        _, uploads = self._run(
            monkeypatch, tmp_path, spec, {"deep/dir/b.fits.bz2": bz2.compress(b"X")}
        )
        assert list(uploads) == ["M31/GEM/GS-2026A-Q-1-1/b.fits"]

    def test_one_bad_member_does_not_lose_the_rest(self, monkeypatch, tmp_path, spec):
        """199 good files should not be lost to one bad one.

        Notes
        -----
        The failure is recorded by name, so the VM can see exactly what is
        missing -- more useful than an aborted job that leaves the PI
        guessing.
        """
        calls = {"n": 0}

        class FlakyVOSpace:
            def __init__(self, **kwargs):
                pass

            def put(self, destination, data):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise RuntimeError("upload failed")

        monkeypatch.setattr(download, "VOSpace", FlakyVOSpace)
        response = MagicMock()
        response.raw = _tarball(
            {"a.fits.bz2": bz2.compress(b"A"), "b.fits.bz2": bz2.compress(b"B")}
        )
        monkeypatch.setattr(download, "open_goa_stream", lambda spec: response)

        result = download.run_download(spec, str(tmp_path))
        assert result["seen"] == 2
        assert result["kept"] == 1
        assert [f["name"] for f in result["failures"]] == ["a.fits"]

    def test_reports_names_and_sizes_only(self, monkeypatch, tmp_path, spec):
        """Nothing about content, so there is nothing new to trust.

        Notes
        -----
        Headers are read on the VM through the storage seam with the same
        astrodata code the local path uses. A runner that reported headers
        could write a false `DataProductMetadata` row that no later check
        would catch.
        """
        result, _ = self._run(
            monkeypatch, tmp_path, spec, {"a.fits.bz2": bz2.compress(b"FITS")}
        )
        assert set(result["files"][0]) == {"name", "size"}

    def test_no_temporary_file_is_left_behind(self, monkeypatch, tmp_path, spec):
        """Proprietary bytes must not survive the run.

        Notes
        -----
        The buffered upload path writes a temporary file and removes it in
        `finally`, so a failure part-way through cannot leave data on the
        notebook server.
        """
        self._run(monkeypatch, tmp_path, spec, {"a.fits.bz2": bz2.compress(b"X")})
        assert not (tmp_path / ".upload.tmp").exists()


class TestStatusProtocol:
    """`status.json` is the only channel a detached job has."""

    @pytest.mark.parametrize("module", [download, reduction])
    def test_status_is_written_atomically(self, module, tmp_path):
        """A torn read looks identical to a crash.

        Notes
        -----
        The VM polls this through the contents API while the runner writes
        it. `os.replace` is atomic, so a reader sees either the old file or
        the new one.
        """
        module.write_status(str(tmp_path), "running", stage="test", seen=1)
        payload = json.loads((tmp_path / "status.json").read_text())
        assert payload["state"] == "running"
        assert payload["stage"] == "test"
        assert "pid" in payload and "ts" in payload
        assert not (tmp_path / "status.json.tmp").exists()

    @pytest.mark.parametrize("module", [download, reduction])
    def test_events_are_ndjson(self, module, tmp_path):
        """One JSON object per line, so `tail_ndjson` can resume."""
        module.log_event(str(tmp_path), event="a")
        module.log_event(str(tmp_path), event="b")
        lines = (tmp_path / "events.ndjson").read_text().strip().split("\n")
        assert [json.loads(line)["event"] for line in lines] == ["a", "b"]

    @pytest.mark.parametrize("module", [download, reduction])
    def test_scrub_removes_secrets_and_tolerates_absence(self, module, tmp_path):
        """The spec holds a Data Lab token and a GOA session cookie.

        Notes
        -----
        Anyone holding that cookie can access the PI's archive account, so
        it is deleted the moment it is in memory. Scrubbing must also
        tolerate files that are not there, since it runs again in `finally`.
        """
        (tmp_path / "job_spec.json").write_text("{}")
        module.scrub(str(tmp_path), module.SECRET_FILES)
        assert not (tmp_path / "job_spec.json").exists()
        module.scrub(str(tmp_path), module.SECRET_FILES)


class TestReductionPreflight:
    """DRAGONS being present is the assumption Phase 4 rests on."""

    def test_reports_missing_packages_by_name(self, monkeypatch):
        """"No module named gempy" an hour later is not debuggable.

        Notes
        -----
        Run before anything else and reported stickily, so its answer
        survives whatever fails afterwards.
        """
        report = reduction.preflight()
        assert set(report) == {"ok", "missing", "versions"}
        if not report["ok"]:
            assert report["missing"]


class TestVOSpacePaths:
    """URIs the runners build must match what `VOSpaceStorage` reads."""

    @pytest.mark.parametrize("module", [download, reduction])
    def test_uri_joins_under_the_root(self, module):
        client = module.VOSpace.__new__(module.VOSpace)
        client.root = "vos://users/alice/goats"
        assert client.uri("M31/f.fits") == "vos://users/alice/goats/M31/f.fits"

    @pytest.mark.parametrize("module", [download, reduction])
    def test_uri_tolerates_stray_separators(self, module):
        client = module.VOSpace.__new__(module.VOSpace)
        client.root = "vos://users/alice/goats"
        assert client.uri("/M31/f.fits/") == "vos://users/alice/goats/M31/f.fits"
