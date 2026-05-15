import datetime
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from tom_observations.tests.factories import ObservingRecordFactory

from goats_tom.tests.factories import DRAGONSRunFactory

MODULE = "goats_tom.models.dragons_run"


def test_get_dragons_version_from_conda():
    from goats_tom.models.dragons_run import get_dragons_version

    result = MagicMock(stdout="dragons  3.1.0  py311\n")
    with patch("subprocess.run", return_value=result):
        assert get_dragons_version() == "3.1.0"


def test_get_dragons_version_falls_back_to_metadata_on_subprocess_error():
    from goats_tom.models.dragons_run import get_dragons_version

    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "conda")):
        with patch("importlib.metadata.version", return_value="3.2.0"):
            assert get_dragons_version() == "3.2.0"


def test_get_dragons_version_returns_unknown_when_both_fail():
    from importlib.metadata import PackageNotFoundError
    from goats_tom.models.dragons_run import get_dragons_version

    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "conda")):
        with patch(
            "importlib.metadata.version", side_effect=PackageNotFoundError("dragons")
        ):
            assert get_dragons_version() == "Unknown"


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("image.fits", True),
        ("image.fit", True),
        ("data.txt", True),
        ("data.dat", True),
        ("data.ascii", True),
        ("data.csv", True),
        ("image.jpg", False),
        ("script.py", False),
        ("archive.tar", False),
        ("noext", False),
        ("IMAGE.FITS", True),
    ],
)
def test_is_valid_file(filename, expected):
    run = DRAGONSRunFactory.build()
    assert run.is_valid_file(Path(filename)) is expected


@pytest.mark.django_db
class TestDRAGONSRunStr:
    def test_str(self):
        run = DRAGONSRunFactory()
        assert str(run) == f"{run.observation_record.observation_id}.{run.run_id}"


@pytest.mark.django_db
class TestDRAGONSRunPaths:
    @pytest.mark.parametrize(
        "method, filename_attr",
        [
            ("get_log_file", "log_filename"),
            ("get_config_file", "config_filename"),
            ("get_cal_manager_db_file", "cal_manager_filename"),
        ],
    )
    def test_path_helpers(self, settings, method, filename_attr):
        settings.MEDIA_ROOT = Path("/media")
        run = DRAGONSRunFactory()
        assert getattr(run, method)() == run.get_output_dir() / getattr(
            run, filename_attr
        )

    def test_get_raw_dir(self, settings):
        settings.MEDIA_ROOT = Path("/media")
        run = DRAGONSRunFactory()
        expected = (
            Path("/media")
            / str(run.observation_record.target.name)
            / str(run.observation_record.facility)
            / str(run.observation_record.observation_id)
        )
        assert run.get_raw_dir() == expected

    def test_get_output_dir(self, settings):
        settings.MEDIA_ROOT = Path("/media")
        run = DRAGONSRunFactory()
        assert run.get_output_dir() == run.get_raw_dir() / run.output_directory

    def test_get_calibrations_uploaded_dir_creates_directory(self, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        run = DRAGONSRunFactory()
        uploaded_dir = run.get_calibrations_uploaded_dir()
        assert uploaded_dir.exists()
        assert uploaded_dir == run.get_output_dir() / "calibrations" / "uploaded"


@pytest.mark.django_db
class TestDRAGONSRunRemoveOutputDir:
    def test_calls_rmtree_when_exists(self, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        run = DRAGONSRunFactory()
        run.get_output_dir().mkdir(parents=True)
        with patch("shutil.rmtree") as mock_rmtree:
            run.remove_output_dir()
            mock_rmtree.assert_called_once_with(run.get_output_dir())

    def test_does_nothing_when_not_exists(self, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        run = DRAGONSRunFactory()
        with patch("shutil.rmtree") as mock_rmtree:
            run.remove_output_dir()
            mock_rmtree.assert_not_called()


@pytest.mark.django_db
class TestDRAGONSRunCaldb:
    def test_add_caldb_file_calls_add_cal_and_closes(self):
        run = DRAGONSRunFactory()
        mock_caldb = MagicMock()
        with patch.object(run, "get_caldb", return_value=mock_caldb):
            with patch.object(run, "close_caldb") as mock_close:
                run.add_caldb_file(Path("/tmp/file.fits"))
                mock_caldb.add_cal.assert_called_once_with(Path("/tmp/file.fits"))
                mock_close.assert_called_once_with(mock_caldb)

    def test_remove_caldb_file_calls_remove_cal_and_closes(self):
        run = DRAGONSRunFactory()
        mock_caldb = MagicMock()
        with patch.object(run, "get_caldb", return_value=mock_caldb):
            with patch.object(run, "close_caldb") as mock_close:
                run.remove_caldb_file("file.fits")
                mock_caldb.remove_cal.assert_called_once_with("file.fits")
                mock_close.assert_called_once_with(mock_caldb)

    def test_close_caldb_closes_session(self):
        run = DRAGONSRunFactory()
        mock_caldb = MagicMock()
        run.close_caldb(mock_caldb)
        mock_caldb._calmgr.session.close.assert_called_once()

    def test_close_caldb_swallows_exceptions(self):
        run = DRAGONSRunFactory()
        mock_caldb = MagicMock()
        mock_caldb._calmgr.session.close.side_effect = Exception("boom")
        run.close_caldb(mock_caldb)  # should not raise

    @pytest.mark.parametrize(
        "existing_files, filename, should_remove",
        [
            ([{"name": "a.fits"}], "a.fits", True),
            ([{"name": "a.fits"}], "b.fits", False),
            ([], "a.fits", False),
        ],
    )
    def test_check_and_remove_caldb_file(self, existing_files, filename, should_remove):
        run = DRAGONSRunFactory()
        with patch.object(run, "list_caldb_files", return_value=existing_files):
            with patch.object(run, "remove_caldb_file") as mock_remove:
                run.check_and_remove_caldb_file(filename)
                if should_remove:
                    mock_remove.assert_called_once_with(filename)
                else:
                    mock_remove.assert_not_called()


@pytest.mark.django_db
class TestDRAGONSRunGetProcessedFiles:
    def test_new_file_not_in_dataproducts_has_status_new(self, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        settings.MEDIA_URL = "/media/"
        run = DRAGONSRunFactory()
        output_dir = run.get_output_dir()
        output_dir.mkdir(parents=True)
        (output_dir / "result.fits").write_bytes(b"FITS")

        with patch(
            f"{MODULE}.DataProduct.objects.filter",
            return_value=MagicMock(
                __iter__=lambda s: iter([]),
                filter=MagicMock(return_value=[]),
            ),
        ):
            files = run.get_processed_files()

        assert any(f["name"] == "result.fits" and f["status"] == "new" for f in files)

    @pytest.mark.parametrize(
        "extension, should_include",
        [
            (".fits", True),
            (".txt", True),
            (".jpg", False),
            (".py", False),
        ],
    )
    def test_filters_by_extension(self, tmp_path, settings, extension, should_include):
        settings.MEDIA_ROOT = tmp_path
        settings.MEDIA_URL = "/media/"
        run = DRAGONSRunFactory()
        run.get_output_dir().mkdir(parents=True)
        (run.get_output_dir() / f"file{extension}").write_bytes(b"data")

        with patch(
            f"{MODULE}.DataProduct.objects.filter",
            return_value=MagicMock(
                __iter__=lambda s: iter([]),
                filter=MagicMock(return_value=[]),
            ),
        ):
            files = run.get_processed_files()

        names = [f["name"] for f in files]
        assert (f"file{extension}" in names) is should_include

    def test_sorted_by_product_id(self, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        settings.MEDIA_URL = "/media/"
        run = DRAGONSRunFactory()
        run.get_output_dir().mkdir(parents=True)
        for name in ["z.fits", "a.fits", "m.fits"]:
            (run.get_output_dir() / name).write_bytes(b"FITS")

        with patch(
            f"{MODULE}.DataProduct.objects.filter",
            return_value=MagicMock(
                __iter__=lambda s: iter([]),
                filter=MagicMock(return_value=[]),
            ),
        ):
            files = run.get_processed_files()

        product_ids = [f["product_id"] for f in files]
        assert product_ids == sorted(product_ids)

    @pytest.mark.parametrize(
        "file_newer_than_dp, expected_status",
        [
            (True, "updated"),
            (False, "unchanged"),
        ],
    )
    def test_existing_dataproduct_status(
        self, tmp_path, settings, file_newer_than_dp, expected_status
    ):
        settings.MEDIA_ROOT = tmp_path
        settings.MEDIA_URL = "/media/"
        run = DRAGONSRunFactory()
        output_dir = run.get_output_dir()
        output_dir.mkdir(parents=True)
        fits_file = output_dir / "result.fits"
        fits_file.write_bytes(b"FITS")

        file_mtime = datetime.datetime.fromtimestamp(
            fits_file.stat().st_mtime, datetime.timezone.utc
        )
        dp_modified = (
            file_mtime - datetime.timedelta(seconds=1)
            if file_newer_than_dp
            else file_mtime + datetime.timedelta(seconds=1)
        )
        product_id = str(fits_file.relative_to(tmp_path))
        mock_dp = MagicMock()
        mock_dp.product_id = product_id
        mock_dp.modified = dp_modified
        mock_dp.id = 1

        with patch(
            f"{MODULE}.DataProduct.objects.filter",
            return_value=MagicMock(
                __iter__=lambda s: iter([mock_dp]),
                filter=MagicMock(return_value=[mock_dp]),
            ),
        ):
            files = run.get_processed_files()

        match = next(f for f in files if f["name"] == "result.fits")
        assert match["status"] == expected_status
        assert match["is_dataproduct"] is True
        assert match["dataproduct_id"] == 1
