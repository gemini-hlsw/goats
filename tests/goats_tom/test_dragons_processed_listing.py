"""Tests for `DRAGONSRun.get_processed_files` under both storage backends.

This is the panel a PI uses to pick which reduction outputs become data
products. That choice is deliberately manual: the local reduction records
nothing itself and neither does the remote one, so nothing here may promote
a file automatically.

It used to glob a local directory, which returns nothing for a run executed
on Data Lab -- the panel would sit empty after a reduction that worked
perfectly, with no error anywhere.
"""

from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from goats_tom.tests.factories import DRAGONSRunFactory


@pytest.fixture
def run(db, tmp_path, settings):
    """A DRAGONS run whose output directory is under the test storage."""
    settings.MEDIA_ROOT = tmp_path
    return DRAGONSRunFactory()


def _write_output(run, name, content=b"FITS"):
    """Put a file where the run's outputs live."""
    return default_storage.save(f"{run.get_output_prefix()}/{name}", ContentFile(content))


@pytest.mark.django_db
class TestLocalBackend:
    """The desktop path, which must behave exactly as before."""

    def test_lists_output_files(self, run):
        _write_output(run, "reduced.fits")
        names = [entry["name"] for entry in run.get_processed_files()]
        assert "reduced.fits" in names

    def test_skips_files_with_unrecognised_extensions(self, run):
        """`is_valid_file` gates the list, and still does.

        Notes
        -----
        A reduction leaves logs and intermediates behind; offering a `.log`
        as a candidate data product would be noise.
        """
        _write_output(run, "reduced.fits")
        _write_output(run, "reduce.log")
        names = [entry["name"] for entry in run.get_processed_files()]
        assert "reduced.fits" in names
        assert "reduce.log" not in names

    def test_new_files_are_marked_new(self, run):
        _write_output(run, "reduced.fits")
        entry = next(
            e for e in run.get_processed_files() if e["name"] == "reduced.fits"
        )
        assert entry["status"] == "new"
        assert entry["is_dataproduct"] is False

    def test_nothing_is_promoted_automatically(self, run):
        """Listing an output must not create a `DataProduct`.

        Notes
        -----
        The local reduction records nothing and the PI chooses from this
        panel. Auto-promoting every intermediate would fill Manage Data with
        files nobody asked for and diverge from local behaviour.
        """
        from tom_dataproducts.models import DataProduct

        _write_output(run, "reduced.fits")
        before = DataProduct.objects.count()
        run.get_processed_files()
        assert DataProduct.objects.count() == before

    def test_missing_output_directory_is_not_an_error(self, run):
        """The normal state before a run has produced anything.

        Notes
        -----
        The panel should show whatever data products exist rather than
        raising because no reduction has run yet.
        """
        assert run.get_processed_files() == []

    def test_url_comes_from_the_backend(self, run):
        """Not built from `MEDIA_URL`.

        Notes
        -----
        `MEDIA_URL` is a local path that serves nothing in `datalab` mode.
        The data-product branch of this method always asked the backend;
        the output branch did not, and the two disagreed.
        """
        _write_output(run, "reduced.fits")
        entry = next(
            e for e in run.get_processed_files() if e["name"] == "reduced.fits"
        )
        assert entry["url"] == default_storage.url(entry["product_id"])


@pytest.mark.django_db
class TestRemoteBackend:
    """A run executed on Data Lab has no local output directory."""

    def test_lists_files_the_backend_reports(self, run):
        """Where `Path.glob` would have returned nothing.

        Notes
        -----
        This is the whole reason for the change: after a remote reduction
        the files exist in VOSpace, the local directory does not, and the
        panel silently showed nothing.
        """
        with patch.object(
            default_storage, "listdir", return_value=([], ["reduced.fits"])
        ), patch.object(default_storage, "url", return_value="/stream/x"):
            names = [entry["name"] for entry in run.get_processed_files()]
        assert names == ["reduced.fits"]

    def test_uses_the_time_the_runner_recorded(self, run):
        """`VOSpaceStorage` cannot report modification times, so the runner does.

        Notes
        -----
        ``/storage/ls`` returns no timestamps, and nothing can recover one
        afterwards. Falling back to "unchanged" was wrong rather than merely
        imprecise: a file the reduction had just overwritten would be
        labelled unchanged, which tells the PI something false. So the
        runner records the moment it wrote each file.
        """
        import datetime as _dt

        name = f"{run.get_output_prefix()}/reduced.fits"
        written = _dt.datetime(2026, 6, 1, tzinfo=_dt.timezone.utc)
        run.output_written_at = {name: written.timestamp()}
        run.save(update_fields=["output_written_at"])

        with patch.object(
            default_storage, "listdir", return_value=([], ["reduced.fits"])
        ), patch.object(
            default_storage, "get_modified_time", side_effect=NotImplementedError
        ), patch.object(default_storage, "url", return_value="/stream/x"):
            entry = run.get_processed_files()[0]

        assert entry["last_modified"] == "2026-06-01 00:00:00"

    def test_falls_back_to_none_when_nothing_recorded_it(self, run):
        """Only when there is genuinely no record.

        Notes
        -----
        An empty field is honest. Inventing a time would make every file
        look freshly written each time the panel is opened.
        """
        with patch.object(
            default_storage, "listdir", return_value=([], ["reduced.fits"])
        ), patch.object(
            default_storage, "get_modified_time", side_effect=NotImplementedError
        ), patch.object(default_storage, "url", return_value="/stream/x"):
            entry = run.get_processed_files()[0]

        assert entry["last_modified"] is None

    def test_a_rewritten_output_is_marked_updated(self, run, db):
        """The label this whole mechanism exists for.

        Notes
        -----
        A reduction that overwrites a file the PI already saved must show as
        `updated`, so they know to re-save it. Under the old fallback this
        read `unchanged` -- the one answer that is actively misleading.
        """
        import datetime as _dt

        from tom_dataproducts.models import DataProduct

        name = f"{run.get_output_prefix()}/reduced.fits"
        product = DataProduct.objects.create(
            target=run.observation_record.target,
            observation_record=run.observation_record,
            product_id=name,
            data=name,
        )
        DataProduct.objects.filter(pk=product.pk).update(
            modified=_dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc)
        )
        from goats_tom.models import DataProductMetadata

        DataProductMetadata.objects.update_or_create(
            dataproduct=product, defaults={"processed": True}
        )

        # Rewritten after the product was last saved.
        run.output_written_at = {
            name: _dt.datetime(2026, 6, 1, tzinfo=_dt.timezone.utc).timestamp()
        }
        run.save(update_fields=["output_written_at"])

        with patch.object(
            default_storage, "listdir", return_value=([], ["reduced.fits"])
        ), patch.object(
            default_storage, "get_modified_time", side_effect=NotImplementedError
        ), patch.object(default_storage, "url", return_value="/stream/x"):
            entry = run.get_processed_files()[0]

        assert entry["status"] == "updated"

    def test_product_ids_are_storage_names(self, run):
        """What the panel POSTs back must be a name the backend understands.

        Notes
        -----
        `dragons_processed_files.py` takes this value and asks storage for
        the file. A local absolute path would not resolve under a remote
        backend.
        """
        with patch.object(
            default_storage, "listdir", return_value=([], ["reduced.fits"])
        ), patch.object(default_storage, "url", return_value="/stream/x"):
            entry = run.get_processed_files()[0]

        assert entry["product_id"] == f"{run.get_output_prefix()}/reduced.fits"
        assert not entry["product_id"].startswith("/")
