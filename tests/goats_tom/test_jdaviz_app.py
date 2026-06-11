"""Tests for :mod:`goats_tom.jdaviz_app`.

Focuses on the data-resolution layer (query parsing, the DRAGONS ``SCI`` FITS
reader and ``_resolve_spectra``) that decides what gets handed to jdaviz. The
Solara ``Page`` component and the ``Specviz`` helpers are not constructed here:
they need a live jdaviz kernel and a browser, so they are out of scope for unit
tests.
"""

import types

import numpy as np
import pytest
from astropy.io import fits

from goats_tom import jdaviz_app
from goats_tom.jdaviz_app import (
    SCIENCE_EXTENSION,
    _dragons_hdu_to_spectrum,
    _query_param,
    _read_dragons_spectra,
    _resolve_spectra,
    _spectra_are_2d,
)


def _spectrum(ndim):
    """A stand-in spectrum exposing just the ``flux.ndim`` the code inspects."""
    return types.SimpleNamespace(flux=np.zeros((2, 3) if ndim == 2 else (3,)))


def _linear_wcs_header(data, ctype="WAVE", bunit="count"):
    """Header with a minimal linear spectral WCS matching ``data``'s shape."""
    hdu = fits.ImageHDU(data=data)
    header = hdu.header
    for axis in range(1, data.ndim + 1):
        header[f"CTYPE{axis}"] = ctype if axis == 1 else "PIXEL"
        header[f"CRVAL{axis}"] = 1.0
        header[f"CRPIX{axis}"] = 1.0
        header[f"CDELT{axis}"] = 1.0
    if bunit is not None:
        header["BUNIT"] = bunit
    return header


# --------------------------------------------------------------------------- #
# _query_param
# --------------------------------------------------------------------------- #
class TestQueryParam:
    def test_none_search_returns_none(self):
        assert _query_param(None, "dataproduct") is None

    def test_empty_search_returns_none(self):
        assert _query_param("", "dataproduct") is None

    def test_returns_value(self):
        assert _query_param("dataproduct=42", "dataproduct") == "42"

    def test_returns_value_among_several_params(self):
        assert _query_param("x=1&dataproduct=42&y=2", "dataproduct") == "42"

    def test_missing_param_returns_none(self):
        assert _query_param("x=1", "dataproduct") is None

    def test_returns_first_when_repeated(self):
        assert _query_param("dataproduct=1&dataproduct=2", "dataproduct") == "1"


# --------------------------------------------------------------------------- #
# _spectra_are_2d
# --------------------------------------------------------------------------- #
class TestSpectraAre2d:
    def test_none_is_not_2d(self):
        assert _spectra_are_2d(None) is False

    def test_empty_is_not_2d(self):
        assert _spectra_are_2d([]) is False

    def test_all_1d_is_not_2d(self):
        assert _spectra_are_2d([("a", _spectrum(1)), ("b", _spectrum(1))]) is False

    def test_any_2d_is_2d(self):
        assert _spectra_are_2d([("a", _spectrum(1)), ("b", _spectrum(2))]) is True


# --------------------------------------------------------------------------- #
# _dragons_hdu_to_spectrum
# --------------------------------------------------------------------------- #
class TestDragonsHduToSpectrum:
    def test_reads_1d_flux_with_bunit(self):
        data = np.arange(5, dtype="float64")
        hdu = fits.ImageHDU(data=data, header=_linear_wcs_header(data, bunit="Jy"))
        spectrum = _dragons_hdu_to_spectrum(hdu)
        assert spectrum is not None
        assert spectrum.flux.ndim == 1
        assert spectrum.flux.unit.to_string() == "Jy"

    def test_defaults_to_count_when_bunit_missing(self):
        data = np.arange(5, dtype="float64")
        hdu = fits.ImageHDU(data=data, header=_linear_wcs_header(data, bunit=None))
        spectrum = _dragons_hdu_to_spectrum(hdu)
        assert spectrum is not None
        assert spectrum.flux.unit == jdaviz_app.u.count

    def test_invalid_bunit_falls_back_to_count(self):
        data = np.arange(5, dtype="float64")
        header = _linear_wcs_header(data, bunit=None)
        header["BUNIT"] = "not-a-real-unit"
        hdu = fits.ImageHDU(data=data, header=header)
        spectrum = _dragons_hdu_to_spectrum(hdu)
        assert spectrum is not None
        assert spectrum.flux.unit == jdaviz_app.u.count

    def test_unreadable_hdu_returns_none(self):
        # ``data is None`` makes the flux conversion raise; the helper swallows it.
        hdu = fits.ImageHDU(data=None)
        assert _dragons_hdu_to_spectrum(hdu) is None


# --------------------------------------------------------------------------- #
# _read_dragons_spectra
# --------------------------------------------------------------------------- #
class TestReadDragonsSpectra:
    def test_non_fits_file_returns_none(self, tmp_path):
        path = tmp_path / "data.csv"
        path.write_text("wavelength,flux\n1,2\n")
        assert _read_dragons_spectra(path) is None

    def test_fits_without_sci_extension_returns_none(self, tmp_path):
        path = tmp_path / "image.fits"
        fits.HDUList([fits.PrimaryHDU(data=np.zeros(5))]).writeto(path)
        assert _read_dragons_spectra(path) is None

    def test_single_sci_extension_uses_stem_label(self, tmp_path):
        path = tmp_path / "spec.fits"
        data = np.arange(5, dtype="float64")
        sci = fits.ImageHDU(
            data=data, header=_linear_wcs_header(data), name=SCIENCE_EXTENSION
        )
        fits.HDUList([fits.PrimaryHDU(), sci]).writeto(path)

        spectra = _read_dragons_spectra(path)
        assert spectra is not None
        assert len(spectra) == 1
        (label, spectrum) = spectra[0]
        assert label == "spec"
        assert spectrum.flux.ndim == 1

    def test_multiple_sci_extensions_get_versioned_labels(self, tmp_path):
        path = tmp_path / "multi.fits"
        data = np.arange(5, dtype="float64")
        hdus = [fits.PrimaryHDU()]
        for ver in (1, 2):
            sci = fits.ImageHDU(
                data=data, header=_linear_wcs_header(data), name=SCIENCE_EXTENSION
            )
            sci.ver = ver
            hdus.append(sci)
        fits.HDUList(hdus).writeto(path)

        spectra = _read_dragons_spectra(path)
        assert spectra is not None
        assert len(spectra) == 2
        labels = {label for label, _ in spectra}
        assert labels == {"multi [SCI,1]", "multi [SCI,2]"}

    def test_2d_sci_extension_is_read(self, tmp_path):
        path = tmp_path / "spec2d.fits"
        data = np.zeros((4, 6), dtype="float64")
        sci = fits.ImageHDU(
            data=data, header=_linear_wcs_header(data), name=SCIENCE_EXTENSION
        )
        fits.HDUList([fits.PrimaryHDU(), sci]).writeto(path)

        spectra = _read_dragons_spectra(path)
        assert spectra is not None
        assert spectra[0][1].flux.ndim == 2


# --------------------------------------------------------------------------- #
# _resolve_spectra
# --------------------------------------------------------------------------- #
class TestResolveSpectra:
    def test_no_pk_returns_all_none(self):
        assert _resolve_spectra(None) == (None, None, None)

    @pytest.mark.django_db
    def test_unknown_pk_returns_error(self):
        path, spectra, error = _resolve_spectra("999999")
        assert path is None and spectra is None
        assert "not found" in error

    @pytest.mark.django_db
    def test_non_numeric_pk_returns_error(self):
        path, spectra, error = _resolve_spectra("not-a-pk")
        assert path is None and spectra is None
        assert "not found" in error

    @pytest.mark.django_db
    def test_missing_file_on_disk_returns_error(self, monkeypatch):
        from goats_tom.tests.factories import DataProductFactory

        dp = DataProductFactory()
        # Remove the backing file so the on-disk existence check fails.
        from pathlib import Path

        Path(dp.data.path).unlink()
        path, spectra, error = _resolve_spectra(str(dp.pk))
        assert path is None and spectra is None
        assert "missing on disk" in error

    @pytest.mark.django_db
    def test_dragons_reader_result_is_returned(self, monkeypatch):
        from goats_tom.tests.factories import DataProductFactory

        dp = DataProductFactory()
        labelled = [("lbl", _spectrum(1))]
        monkeypatch.setattr(jdaviz_app, "_read_dragons_spectra", lambda p: labelled)

        path, spectra, error = _resolve_spectra(str(dp.pk))
        assert error is None
        assert spectra is labelled
        assert path is not None

    @pytest.mark.django_db
    def test_falls_back_to_path_when_no_reader_handles_file(self, monkeypatch):
        from goats_tom.tests.factories import DataProductFactory

        dp = DataProductFactory()
        monkeypatch.setattr(jdaviz_app, "_read_dragons_spectra", lambda p: None)
        monkeypatch.setattr(jdaviz_app, "_read_processor_spectra", lambda dp: [])

        path, spectra, error = _resolve_spectra(str(dp.pk))
        # No reader handled it: caller is told to try jdaviz's own loaders on path.
        assert error is None
        assert spectra is None
        assert path is not None

    @pytest.mark.django_db
    def test_processor_spectra_get_indexed_labels_when_multiple(self, monkeypatch):
        from goats_tom.tests.factories import DataProductFactory

        dp = DataProductFactory()
        monkeypatch.setattr(jdaviz_app, "_read_dragons_spectra", lambda p: None)
        monkeypatch.setattr(
            jdaviz_app,
            "_read_processor_spectra",
            lambda dp: [_spectrum(1), _spectrum(1)],
        )

        path, spectra, error = _resolve_spectra(str(dp.pk))
        assert error is None
        assert len(spectra) == 2
        labels = [label for label, _ in spectra]
        assert labels == [f"{path.stem} [0]", f"{path.stem} [1]"]

    @pytest.mark.django_db
    def test_single_processor_spectrum_uses_stem_label(self, monkeypatch):
        from goats_tom.tests.factories import DataProductFactory

        dp = DataProductFactory()
        monkeypatch.setattr(jdaviz_app, "_read_dragons_spectra", lambda p: None)
        monkeypatch.setattr(
            jdaviz_app, "_read_processor_spectra", lambda dp: [_spectrum(1)]
        )

        path, spectra, error = _resolve_spectra(str(dp.pk))
        assert error is None
        assert len(spectra) == 1
        assert spectra[0][0] == path.stem
