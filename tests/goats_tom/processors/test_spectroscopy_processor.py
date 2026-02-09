"""Tests for goats_tom.processors.spectroscopy_processor."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
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
def mock_dataproduct():
    dp = MagicMock(spec=DataProduct)
    dp.data.path = "/path/to/test.fits"
    return dp


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

        mock_fits_open.assert_called_once_with("/path/to/test.fits")
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
