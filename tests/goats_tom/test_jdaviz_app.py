"""Tests for :mod:`goats_tom.jdaviz_app`.

Focuses on the data-resolution layer (query parsing, the DRAGONS ``SCI`` FITS
reader and ``_resolve_spectra``) that decides what gets handed to jdaviz. The
Solara ``Page`` component and the ``Specviz`` helpers are not constructed here:
they need a live jdaviz kernel and a browser, so they are out of scope for unit
tests.
"""

import types
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from goats_tom import jdaviz_app
from goats_tom.jdaviz_app import (
    SCIENCE_EXTENSION,
    UNSUPPORTED_MESSAGE,
    _build_specviz,
    _call_off_event_loop,
    _dragons_hdu_to_spectrum,
    _hide_popout,
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


class TestSpectraAre2d:
    def test_none_is_not_2d(self):
        assert _spectra_are_2d(None) is False

    def test_empty_is_not_2d(self):
        assert _spectra_are_2d([]) is False

    def test_all_1d_is_not_2d(self):
        assert _spectra_are_2d([("a", _spectrum(1)), ("b", _spectrum(1))]) is False

    def test_any_2d_is_2d(self):
        assert _spectra_are_2d([("a", _spectrum(1)), ("b", _spectrum(2))]) is True



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

    def test_unreadable_sci_extension_is_skipped(self, tmp_path, monkeypatch):
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

        real = jdaviz_app._dragons_hdu_to_spectrum
        monkeypatch.setattr(
            jdaviz_app,
            "_dragons_hdu_to_spectrum",
            lambda hdu: None if hdu.ver == 2 else real(hdu),
        )

        spectra = _read_dragons_spectra(path)
        assert spectra is not None
        assert [label for label, _ in spectra] == ["multi [SCI,1]"]

    def test_all_sci_extensions_unreadable_returns_none(self, tmp_path, monkeypatch):
        path = tmp_path / "spec.fits"
        data = np.arange(5, dtype="float64")
        sci = fits.ImageHDU(
            data=data, header=_linear_wcs_header(data), name=SCIENCE_EXTENSION
        )
        fits.HDUList([fits.PrimaryHDU(), sci]).writeto(path)

        monkeypatch.setattr(jdaviz_app, "_dragons_hdu_to_spectrum", lambda hdu: None)
        assert _read_dragons_spectra(path) is None



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
        Path(dp.data.path).unlink()
        path, spectra, error = _resolve_spectra(str(dp.pk))
        assert path is None and spectra is None
        assert "missing on disk" in error

    @pytest.mark.django_db
    def test_dataproduct_without_file_returns_error(self):
        from goats_tom.tests.factories import DataProductFactory

        dp = DataProductFactory()
        dp.data = ""
        dp.save()
        path, spectra, error = _resolve_spectra(str(dp.pk))
        assert path is None and spectra is None
        assert "no associated file" in error

    @pytest.mark.django_db
    def test_processor_error_falls_back_to_path(self, monkeypatch):
        from goats_tom.tests.factories import DataProductFactory

        dp = DataProductFactory()
        monkeypatch.setattr(jdaviz_app, "_read_dragons_spectra", lambda p: None)

        def boom(dp):
            raise RuntimeError("corrupt file")

        monkeypatch.setattr(jdaviz_app, "_read_processor_spectra", boom)

        path, spectra, error = _resolve_spectra(str(dp.pk))
        # A processor crash is not fatal: jdaviz's own loaders get to try path.
        assert error is None
        assert spectra is None
        assert path is not None

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



class TestCallOffEventLoop:
    def test_returns_result(self):
        assert _call_off_event_loop(lambda: 42) == 42

    def test_propagates_exception(self):
        def boom():
            raise ValueError("nope")

        with pytest.raises(ValueError, match="nope"):
            _call_off_event_loop(boom)

    def test_closes_db_connections_after_call(self, monkeypatch):
        from django.db import connections

        closed = []
        monkeypatch.setattr(connections, "close_all", lambda: closed.append(True))
        _call_off_event_loop(lambda: None)
        assert closed == [True]

    def test_closes_db_connections_even_on_error(self, monkeypatch):
        from django.db import connections

        closed = []
        monkeypatch.setattr(connections, "close_all", lambda: closed.append(True))

        def boom():
            raise RuntimeError("db exploded")

        with pytest.raises(RuntimeError):
            _call_off_event_loop(boom)
        assert closed == [True]



class TestHidePopout:
    def test_hides_popout_button(self):
        layout = types.SimpleNamespace(display=None)
        viz = types.SimpleNamespace(
            app=types.SimpleNamespace(
                popout_button=types.SimpleNamespace(layout=layout)
            )
        )
        _hide_popout(viz)
        assert layout.display == "none"

    def test_missing_popout_button_is_noop(self):
        viz = types.SimpleNamespace(app=types.SimpleNamespace())
        _hide_popout(viz)



class _FakeSpecviz:
    """Stand-in for a ``Specviz`` helper recording ``load`` calls."""

    def __init__(self, fail=False):
        self.loads = []
        self._fail = fail

    def load(self, spectrum, data_label=None):
        if self._fail:
            raise RuntimeError("cannot load")
        self.loads.append((spectrum, data_label))


class _FakeSpecviz2d:
    """Stand-in for a ``Specviz2d`` helper recording ``load_data`` calls."""

    def __init__(self, fail=False):
        self.loads = []
        self._fail = fail

    def load_data(self, **kwargs):
        if self._fail:
            raise RuntimeError("cannot load")
        self.loads.append(kwargs)


class TestBuildSpecviz:
    PATH = Path("spec.fits")

    def test_1d_spectra_load_into_specviz(self, monkeypatch):
        fake = _FakeSpecviz()
        monkeypatch.setattr(jdaviz_app, "_create_specviz", lambda: fake)
        s1, s2 = _spectrum(1), _spectrum(1)

        viz, load_error = _build_specviz(self.PATH, [("a", s1), ("b", s2)])
        assert viz is fake
        assert load_error is None
        assert fake.loads == [(s1, "a"), (s2, "b")]

    def test_no_spectra_uses_jdaviz_loader_on_path(self, monkeypatch):
        fake = _FakeSpecviz()
        monkeypatch.setattr(jdaviz_app, "_create_specviz", lambda: fake)

        viz, load_error = _build_specviz(self.PATH, None)
        assert viz is fake
        assert load_error is None
        assert fake.loads == [(str(self.PATH), None)]

    def test_2d_spectrum_routes_to_specviz2d(self, monkeypatch):
        fake = _FakeSpecviz2d()
        monkeypatch.setattr(jdaviz_app, "_create_specviz2d", lambda: fake)
        s2d = _spectrum(2)

        viz, load_error = _build_specviz(self.PATH, [("img", s2d)])
        assert viz is fake
        assert load_error is None
        assert fake.loads == [{"spectrum_2d": s2d, "spectrum_2d_label": "img"}]

    def test_mixed_spectra_route_1d_and_2d_into_specviz2d(self, monkeypatch):
        fake = _FakeSpecviz2d()
        monkeypatch.setattr(jdaviz_app, "_create_specviz2d", lambda: fake)
        s2d, s1d = _spectrum(2), _spectrum(1)

        viz, load_error = _build_specviz(self.PATH, [("img", s2d), ("trace", s1d)])
        assert load_error is None
        assert fake.loads == [
            {"spectrum_2d": s2d, "spectrum_2d_label": "img"},
            {"spectrum_1d": s1d, "spectrum_1d_label": "trace"},
        ]

    def test_1d_load_failure_keeps_viewer_and_reports(self, monkeypatch):
        fake = _FakeSpecviz(fail=True)
        monkeypatch.setattr(jdaviz_app, "_create_specviz", lambda: fake)

        viz, load_error = _build_specviz(self.PATH, None)
        assert viz is fake
        assert load_error == UNSUPPORTED_MESSAGE.format(name=self.PATH.name)

    def test_2d_load_failure_keeps_viewer_and_reports(self, monkeypatch):
        fake = _FakeSpecviz2d(fail=True)
        monkeypatch.setattr(jdaviz_app, "_create_specviz2d", lambda: fake)

        viz, load_error = _build_specviz(self.PATH, [("img", _spectrum(2))])
        assert viz is fake
        assert load_error == UNSUPPORTED_MESSAGE.format(name=self.PATH.name)
