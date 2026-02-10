"""Tests for goats_tom.processors.fits_utils."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from astropy.io import fits
from astropy import units as u
from datetime import datetime

from goats_tom.processors import fits_utils


@pytest.fixture
def mock_header():
    return fits.Header()


class TestGetFluxUnit:
    def test_from_bunit(self, mock_header):
        mock_header["BUNIT"] = "Jy"
        unit = fits_utils.get_flux_unit_from_header(mock_header)
        assert unit == u.Jy

    def test_invalid_unit(self, mock_header):
        mock_header["BUNIT"] = "invalid_unit"
        unit = fits_utils.get_flux_unit_from_header(mock_header)
        assert unit is None


class TestFixHeaderCunit1:
    def test_existing_valid(self, mock_header):
        mock_header["CUNIT1"] = "nm"
        unit = fits_utils.fix_header_cunit1(mock_header)
        assert unit == u.nm
        assert mock_header["CUNIT1"] == "nm"

    def test_deg_with_wat(self, mock_header):
        mock_header["CUNIT1"] = "deg"
        mock_header["WAT1_001"] = "wtype=linear label=Wavelength units=Angstrom"
        unit = fits_utils.fix_header_cunit1(mock_header)
        assert unit == u.Angstrom
        assert mock_header["CUNIT1"] == "Angstrom"

    def test_missing_sets_default(self, mock_header):
        unit = fits_utils.fix_header_cunit1(mock_header)
        assert unit == u.Angstrom
        assert mock_header["CUNIT1"] == "Angstrom"


class TestReduceFluxArray:
    def test_1d(self, mock_header):
        flux = np.ones((10,))
        reduced = fits_utils.reduce_flux_array(flux, mock_header)
        assert reduced.shape == (10,)

    def test_3d_reduction(self, mock_header):
        flux = np.ones((1, 1, 10))
        reduced = fits_utils.reduce_flux_array(flux, mock_header)
        assert reduced.shape == (10,)

    def test_2xN_reduction(self, mock_header):
        flux = np.ones((2, 10))
        reduced = fits_utils.reduce_flux_array(flux, mock_header)
        assert reduced.shape == (10,)

    def test_image_rejection(self, mock_header):
        mock_header["NAXIS"] = 2
        flux = np.ones((10, 10))
        with pytest.raises(ValueError, match="plottable spectrum"):
            fits_utils.reduce_flux_array(flux, mock_header)


class TestDetectFacility:
    @patch("goats_tom.processors.fits_utils.fits.open")
    @patch("goats_tom.processors.fits_utils.get_service_classes")
    @patch("goats_tom.processors.fits_utils.get_service_class")
    def test_detect_known_facility(
        self, mock_get_cls, mock_get_classes, mock_fits_open
    ):
        mock_hdul = MagicMock()
        mock_header = fits.Header({"TELESCOP": "TEST_TELESCOPE"})
        mock_hdul.__enter__.return_value = [MagicMock(header=mock_header)]
        mock_fits_open.return_value = mock_hdul

        mock_get_classes.return_value = ["TestFacility"]
        mock_facility = MagicMock()
        mock_facility.is_fits_facility.return_value = True
        mock_facility.get_flux_constant.return_value = u.Jy
        mock_facility.get_date_obs_from_fits_header.return_value = datetime(2022, 1, 1)

        mock_get_cls.return_value = lambda: mock_facility

        name, date, unit = fits_utils.detect_facility("dummy.fits")

        assert name == "TestFacility"
        assert date == datetime(2022, 1, 1)
        assert unit == u.Jy
