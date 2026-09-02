"""Tests for goats_tom.processors.spectroscopy_processor."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
from pathlib import Path

import pytest
from astropy import units as u
from astropy.io import fits

from goats_tom.processors.spectroscopy_processor import SpectroscopyProcessor
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.models import DataProduct


class _FakeHDUList(list):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _hdu(data, header=None):
    h = MagicMock()
    h.data = data
    h.header = fits.Header(header or {})
    return h


@pytest.fixture
def mock_dataproduct(tmp_path):
    """A data product whose file really exists under the test storage.

    Notes
    -----
    Used to set ``dp.data.path`` on a mock, which stopped meaning anything
    when the processor moved to `goats_tom.storage`. The seam asks the
    storage backend for the file and refuses a name it does not hold, so a
    fabricated path now fails where a mocked attribute used to pass -- which
    is the point of the seam, and worth keeping rather than mocking around.

    ``data.name`` is a storage-relative name and the file is written under
    ``MEDIA_ROOT``, so `local_path` resolves it exactly as it would in
    production.
    """
    dp = MagicMock(spec=DataProduct)
    dp.data.name = "spectra/test.fits"
    (tmp_path / "spectra").mkdir(parents=True, exist_ok=True)
    (tmp_path / "spectra" / "test.fits").write_bytes(b"")
    return dp


@pytest.fixture(autouse=True)
def _media_root(tmp_path, settings):
    """Point storage at the per-test directory `mock_dataproduct` writes to."""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def processor():
    return SpectroscopyProcessor()


class TestSpectroscopyProcessor:
    @patch("goats_tom.processors.spectroscopy_processor.mimetypes.guess_type")
    @patch("goats_tom.processors.spectroscopy_processor.fits.open")
    @patch("goats_tom.processors.spectroscopy_processor.fits_utils")
    @patch("goats_tom.processors.spectroscopy_processor.SpectrumSerializer")
    def test_process_fits_array(
        self,
        mock_serializer_cls,
        mock_utils,
        mock_fits_open,
        mock_guess,
        processor,
        mock_dataproduct,
    ):
        mock_guess.return_value = ("application/fits", None)

        primary = _hdu(None, {"EXTNAME": "PRIMARY"})
        sci = _hdu(
            np.ones((10,), dtype=float), {"EXTNAME": "SCI", "CUNIT1": "Angstrom"}
        )
        mock_fits_open.return_value = _FakeHDUList([primary, sci])

        mock_utils.detect_facility.return_value = (
            "TestFacility",
            datetime(2023, 1, 1),
            u.Jy,
        )
        mock_utils.get_flux_unit_from_header.return_value = None
        mock_utils.reduce_flux_array.return_value = np.ones((10,), dtype=float)
        mock_utils.fix_header_cunit1.return_value = u.Angstrom

        serializer = MagicMock()
        serializer.serialize.return_value = {"ok": True}
        mock_serializer_cls.return_value = serializer

        out = processor.process_data(mock_dataproduct)

        assert len(out) == 1
        assert out[0][0] == datetime(2023, 1, 1)
        assert out[0][1] == {"ok": True}
        assert out[0][2] == "TestFacility:hdu=1:SCI"

        # Resolved through `goats_tom.storage`, so the path is wherever the
        # backend put the file rather than a literal. Asserting the filename
        # keeps what this test was checking -- that the file it was handed is
        # the one opened -- without pinning it to a local layout that no
        # longer holds under a remote backend.
        (opened,), _ = mock_fits_open.call_args
        assert Path(opened).name == "test.fits"
        assert Path(opened).exists()
        mock_utils.reduce_flux_array.assert_called_once()
        mock_utils.fix_header_cunit1.assert_called_once()

    @patch("goats_tom.processors.spectroscopy_processor.mimetypes.guess_type")
    @patch("goats_tom.processors.spectroscopy_processor.fits.open")
    @patch("goats_tom.processors.spectroscopy_processor.fits_utils")
    @patch("goats_tom.processors.spectroscopy_processor.SpectrumSerializer")
    def test_process_fits_table(
        self,
        mock_serializer_cls,
        mock_utils,
        mock_fits_open,
        mock_guess,
        processor,
        mock_dataproduct,
    ):
        mock_guess.return_value = ("application/fits", None)

        dt = np.dtype([("wavelength", "f8"), ("flux", "f8")])
        table = np.zeros((10,), dtype=dt)
        table["wavelength"] = np.arange(10)
        table["flux"] = np.ones(10)

        sci = _hdu(table, {"EXTNAME": "SCI"})
        mock_fits_open.return_value = _FakeHDUList([sci])

        mock_utils.detect_facility.return_value = (
            "TableFacility",
            datetime(2023, 2, 1),
            None,
        )
        mock_utils.get_flux_unit_from_header.return_value = u.erg / u.cm**2 / u.s / u.AA
        mock_utils.fix_header_cunit1.return_value = u.Angstrom

        serializer = MagicMock()
        serializer.serialize.return_value = {"ok": True}
        mock_serializer_cls.return_value = serializer

        out = processor.process_data(mock_dataproduct)

        assert len(out) == 1
        assert out[0][0] == datetime(2023, 2, 1)
        assert out[0][2] == "TableFacility:hdu=0:SCI"

        mock_utils.fix_header_cunit1.assert_called_once()

    @patch("goats_tom.processors.spectroscopy_processor.mimetypes.guess_type")
    @patch("goats_tom.processors.spectroscopy_processor.fits.open")
    @patch("goats_tom.processors.spectroscopy_processor.fits_utils")
    def test_missing_required_columns(
        self,
        mock_utils,
        mock_fits_open,
        mock_guess,
        processor,
        mock_dataproduct,
    ):
        mock_guess.return_value = ("application/fits", None)

        dt = np.dtype([("random_col", "f8")])
        bad = np.zeros((5,), dtype=dt)
        sci = _hdu(bad, {"EXTNAME": "SCI"})
        mock_fits_open.return_value = _FakeHDUList([sci])

        mock_utils.detect_facility.return_value = (
            "Facility",
            datetime(2023, 3, 1),
            None,
        )
        mock_utils.get_flux_unit_from_header.return_value = None

        with pytest.raises(InvalidFileFormatException, match="plottable spectrum"):
            processor.process_data(mock_dataproduct)
