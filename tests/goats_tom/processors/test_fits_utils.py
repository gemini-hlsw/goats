import numpy as np
import pytest
from astropy import units as u
from astropy.io import fits
from astropy.wcs import WCS
from goats_tom.processors.fits_utils import (
    _build_wcs_or_axis,
    _ensure_1d_flux_array,
    _guess_flux_unit_from_header,
    _guess_wave_unit_from_header,
    _normalize_cunit1,
)


class TestFitsUtils:
    """Tests for the fits_utils module."""

    def test_normalize_cunit1(self):
        """Test _normalize_cunit1 normalizes units correctly."""
        # Standard alias
        hdr = fits.Header({"CUNIT1": "angstrom"})
        _normalize_cunit1(hdr)
        assert hdr["CUNIT1"] == "Angstrom"

        # Singular form support for known keys
        hdr = fits.Header({"CUNIT1": "micron"})
        _normalize_cunit1(hdr)
        assert hdr["CUNIT1"] == "um"

        # WAT hint fallback
        hdr = fits.Header({"CUNIT1": "deg", "WAT1_001": "wtype=linear label=Wavelength units=angstroms"})
        _normalize_cunit1(hdr)
        assert hdr["CUNIT1"] == "Angstrom"

    def test_guess_wave_unit_from_header(self):
        """Test _guess_wave_unit_from_header."""
        # CUNIT1 present
        hdr = fits.Header({"CUNIT1": "nm"})
        unit = _guess_wave_unit_from_header(hdr)
        assert unit == u.nm

        # Fallback to CTYPE1
        hdr = fits.Header({"CTYPE1": "WAVELENGTH"})
        unit = _guess_wave_unit_from_header(hdr)
        assert unit == u.Angstrom

        # Frequency
        hdr = fits.Header({"CTYPE1": "FREQ"})
        unit = _guess_wave_unit_from_header(hdr)
        assert unit == u.Hz

    def test_ensure_1d_flux_array(self):
        """Test _ensure_1d_flux_array coercions."""
        # 1D
        data = np.array([1, 2, 3])
        assert np.array_equal(_ensure_1d_flux_array(data), data)

        # 2D (1, N)
        data = np.array([[1, 2, 3]])
        assert np.array_equal(_ensure_1d_flux_array(data), [1, 2, 3])

        # 2D (N, 1)
        data = np.array([[1], [2], [3]])
        assert np.array_equal(_ensure_1d_flux_array(data), [1, 2, 3])

        # 3D (1, 1, N)
        data = np.array([[[1, 2, 3]]])
        assert np.array_equal(_ensure_1d_flux_array(data), [1, 2, 3])

        # Error
        with pytest.raises(ValueError):
            _ensure_1d_flux_array(np.zeros((3, 3)))

    def test_build_wcs_or_axis(self):
        """Test _build_wcs_or_axis logic."""
        # Valid WCS (CUNIT1 present)
        hdr = fits.Header({
            "NAXIS": 1, "NAXIS1": 10,
            "CRVAL1": 4000, "CRPIX1": 1, "CDELT1": 10,
            "CUNIT1": "Angstrom", "CTYPE1": "WAVE"
        })
        n = 10
        mode, res = _build_wcs_or_axis(hdr, n)
        
        if mode == "wcs":
            assert isinstance(res, WCS)
        else:
            # Fallback
            assert isinstance(res, u.Quantity)
            assert res.unit == u.Angstrom
            assert res[0].value == 4000

    def test_guess_flux_unit_from_header(self):
        """Test scanning for BUNIT."""
        hdr = fits.Header({"BUNIT": "erg/s/cm2/Angstrom"})
        unit = _guess_flux_unit_from_header(hdr, u.one)
        # astropy might parse this string differently or as a composite
        assert unit.is_equivalent(u.erg / u.s / u.cm**2 / u.Angstrom)

        # Fallback
        hdr = fits.Header({})
        unit = _guess_flux_unit_from_header(hdr, u.one)
        assert unit == u.one
