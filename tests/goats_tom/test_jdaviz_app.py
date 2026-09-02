"""Tests for :mod:`goats_tom.jdaviz_app`.

Focuses on the data-resolution layer (query parsing, the DRAGONS ``SCI`` FITS
reader and ``_resolve_spectra``) that decides what gets handed to jdaviz. The
Solara ``Page`` component and the jdaviz app itself are not constructed here:
they need a live jdaviz kernel and a browser, so they are out of scope for unit
tests.
"""

import ast
import types
from pathlib import Path

import astropy.units as u
import numpy as np
from contextlib import ExitStack

import pytest
from astropy.io import fits
from astropy.nddata import StdDevUncertainty
from astropy.wcs import WCS
from specutils import Spectrum

from goats_tom import jdaviz_app
from goats_tom.jdaviz_app import (
    FORMAT_1D,
    FORMAT_2D,
    SCIENCE_EXTENSION,
    SPECTRAL_DISPLAY_UNIT,
    UNSUPPORTED_MESSAGE,
    _build_specviz,
    _call_off_event_loop,
    _dragons_hdu_to_spectrum,
    _query_param,
    _read_dragons_spectra,
    _resolve_spectra,
    _spectra_are_2d,
    _widget,
    _with_display_spectral_axis,
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
    """`_resolve_spectra` now takes the stack that owns the resolved file.

    Notes
    -----
    The path outlives the call -- `Page` builds the viewer a render later
    -- so the lifetime belongs to the caller. `contextlib.ExitStack` is the
    real thing here rather than a mock: under local storage nothing is
    copied and closing it is a no-op, which is the behaviour under test.
    """

    @pytest.fixture
    def stack(self):
        """Own any file the call resolves, and release it afterwards."""
        with ExitStack() as stack:
            yield stack

    def test_no_pk_returns_all_none(self, stack):
        assert _resolve_spectra(None, stack) == (None, None, None)

    @pytest.mark.django_db
    def test_unknown_pk_returns_error(self, stack):
        path, spectra, error = _resolve_spectra("999999", stack)
        assert path is None and spectra is None
        assert "not found" in error

    @pytest.mark.django_db
    def test_non_numeric_pk_returns_error(self, stack):
        path, spectra, error = _resolve_spectra("not-a-pk", stack)
        assert path is None and spectra is None
        assert "not found" in error

    @pytest.mark.django_db
    def test_missing_file_on_disk_returns_error(self, stack, monkeypatch):
        from goats_tom.tests.factories import DataProductFactory

        dp = DataProductFactory()
        # Remove the backing file so the on-disk existence check fails.
        Path(dp.data.path).unlink()
        path, spectra, error = _resolve_spectra(str(dp.pk), stack)
        assert path is None and spectra is None
        assert "missing on disk" in error

    @pytest.mark.django_db
    def test_dataproduct_without_file_returns_error(self, stack):
        from goats_tom.tests.factories import DataProductFactory

        dp = DataProductFactory()
        dp.data = ""
        dp.save()
        path, spectra, error = _resolve_spectra(str(dp.pk), stack)
        assert path is None and spectra is None
        assert "no associated file" in error

    @pytest.mark.django_db
    def test_processor_error_falls_back_to_path(self, stack, monkeypatch):
        from goats_tom.tests.factories import DataProductFactory

        dp = DataProductFactory()
        monkeypatch.setattr(jdaviz_app, "_read_dragons_spectra", lambda p: None)

        def boom(dp):
            raise RuntimeError("corrupt file")

        monkeypatch.setattr(jdaviz_app, "_read_processor_spectra", boom)

        path, spectra, error = _resolve_spectra(str(dp.pk), stack)
        # A processor crash is not fatal: jdaviz's own loaders get to try path.
        assert error is None
        assert spectra is None
        assert path is not None

    @pytest.mark.django_db
    def test_dragons_reader_result_is_returned(self, stack, monkeypatch):
        from goats_tom.tests.factories import DataProductFactory

        dp = DataProductFactory()
        labelled = [("lbl", _spectrum(1))]
        monkeypatch.setattr(jdaviz_app, "_read_dragons_spectra", lambda p: labelled)

        path, spectra, error = _resolve_spectra(str(dp.pk), stack)
        assert error is None
        assert spectra is labelled
        assert path is not None

    @pytest.mark.django_db
    def test_falls_back_to_path_when_no_reader_handles_file(self, stack, monkeypatch):
        from goats_tom.tests.factories import DataProductFactory

        dp = DataProductFactory()
        monkeypatch.setattr(jdaviz_app, "_read_dragons_spectra", lambda p: None)
        monkeypatch.setattr(jdaviz_app, "_read_processor_spectra", lambda dp: [])

        path, spectra, error = _resolve_spectra(str(dp.pk), stack)
        # No reader handled it: caller is told to try jdaviz's own loaders on path.
        assert error is None
        assert spectra is None
        assert path is not None

    @pytest.mark.django_db
    def test_processor_spectra_get_indexed_labels_when_multiple(self, stack, monkeypatch):
        from goats_tom.tests.factories import DataProductFactory

        dp = DataProductFactory()
        monkeypatch.setattr(jdaviz_app, "_read_dragons_spectra", lambda p: None)
        monkeypatch.setattr(
            jdaviz_app,
            "_read_processor_spectra",
            lambda dp: [_spectrum(1), _spectrum(1)],
        )

        path, spectra, error = _resolve_spectra(str(dp.pk), stack)
        assert error is None
        assert len(spectra) == 2
        labels = [label for label, _ in spectra]
        assert labels == [f"{path.stem} [0]", f"{path.stem} [1]"]

    @pytest.mark.django_db
    def test_single_processor_spectrum_uses_stem_label(self, stack, monkeypatch):
        from goats_tom.tests.factories import DataProductFactory

        dp = DataProductFactory()
        monkeypatch.setattr(jdaviz_app, "_read_dragons_spectra", lambda p: None)
        monkeypatch.setattr(
            jdaviz_app, "_read_processor_spectra", lambda dp: [_spectrum(1)]
        )

        path, spectra, error = _resolve_spectra(str(dp.pk), stack)
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



class TestLoaderFormats:
    """The format strings are resolved by jdaviz at runtime, so pin them here."""

    def test_formats_exist_in_jdaviz(self):
        from jdaviz.core.registries import (  # noqa: PLC0415
            loader_importer_registry,
        )

        registered = loader_importer_registry.members
        assert FORMAT_1D in registered
        assert FORMAT_2D in registered


class TestForgetApp:
    def test_removes_the_app_from_the_registry(self, monkeypatch):
        keep, drop = object(), object()
        registry = [keep, drop]
        monkeypatch.setattr(jdaviz_app.jdaviz, "get_all_apps", lambda: registry)

        jdaviz_app._forget_app(drop)

        assert registry == [keep]

    def test_unknown_app_is_a_noop(self, monkeypatch):
        registry = [object()]
        monkeypatch.setattr(jdaviz_app.jdaviz, "get_all_apps", lambda: registry)

        jdaviz_app._forget_app(object())

        assert len(registry) == 1

    def test_registry_failure_is_swallowed(self, monkeypatch):
        def boom():
            raise RuntimeError("no registry")

        monkeypatch.setattr(jdaviz_app.jdaviz, "get_all_apps", boom)

        jdaviz_app._forget_app(object())


class TestJdavizSolaraIsNotImported:
    """``jdaviz.solara`` must never be imported by the embedded viewer.

    It registers a global ``on_kernel_start`` hook whose kernel-close callback
    runs ``os._exit(0)``: leaving the viewer would kill the whole GOATS server.
    """

    def test_module_does_not_import_jdaviz_solara(self):
        tree = ast.parse(Path(jdaviz_app.__file__).read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        assert "jdaviz.solara" not in imported

    def test_no_exiting_kernel_hook_is_registered(self):
        from solara.lifecycle import _on_kernel_start_callbacks  # noqa: PLC0415

        modules = [
            getattr(getattr(entry, "callback", entry), "__module__", "")
            for entry in _on_kernel_start_callbacks
        ]
        assert "jdaviz.solara" not in modules


class TestWidget:
    def test_private_app_is_preferred(self):
        private, public = types.SimpleNamespace(), types.SimpleNamespace()
        viz = types.SimpleNamespace(_app=private, app=public)

        assert _widget(viz) is private

    def test_falls_back_to_public_app(self):
        public = types.SimpleNamespace()
        viz = types.SimpleNamespace(app=public)

        assert _widget(viz) is public



class _FakeApp:
    """Stand-in for the jdaviz app recording ``load`` calls."""

    def __init__(self, fail=False):
        self.loads = []
        self._fail = fail

    def load(self, inp, format=None, data_label=None):  # noqa: A002 -- jdaviz API
        if self._fail:
            raise RuntimeError("cannot load")
        self.loads.append((inp, format, data_label))


class TestWithDisplaySpectralAxis:
    def test_wavelength_axis_is_converted(self):
        spectrum = Spectrum(
            flux=np.arange(5.0) * u.Jy, spectral_axis=np.linspace(400, 500, 5) * u.nm
        )
        converted = _with_display_spectral_axis(spectrum)

        assert converted.spectral_axis.unit == u.Unit(SPECTRAL_DISPLAY_UNIT)
        # 1 nm is 10 Angstrom, so the values scale by ten.
        assert converted.spectral_axis.value[0] == pytest.approx(4000.0)
        assert converted.spectral_axis.value[-1] == pytest.approx(5000.0)

    def test_wcs_axis_in_metres_is_converted(self):
        header = _linear_wcs_header(np.zeros(4), ctype="AWAV")
        header["CUNIT1"] = "nm"
        spectrum = Spectrum(flux=np.zeros(4) * u.count, wcs=WCS(header))
        # astropy normalises the spectral WCS to SI before we ever see it.
        assert spectrum.spectral_axis.unit == u.m

        converted = _with_display_spectral_axis(spectrum)
        assert converted.spectral_axis.unit == u.Unit(SPECTRAL_DISPLAY_UNIT)

    def test_uncalibrated_pixel_axis_is_left_alone(self):
        spectrum = Spectrum(flux=np.zeros(5) * u.count)
        assert _with_display_spectral_axis(spectrum) is spectrum

    def test_frequency_axis_is_left_alone(self):
        spectrum = Spectrum(
            flux=np.zeros(5) * u.Jy, spectral_axis=np.linspace(1e9, 2e9, 5) * u.Hz
        )
        assert _with_display_spectral_axis(spectrum) is spectrum

    def test_uncertainty_mask_and_meta_survive(self):
        spectrum = Spectrum(
            flux=np.arange(5.0) * u.Jy,
            spectral_axis=np.linspace(400, 500, 5) * u.nm,
            uncertainty=StdDevUncertainty(np.full(5, 0.1)),
            mask=np.array([0, 0, 1, 0, 0], dtype=bool),
            meta={"origin": "test"},
        )
        converted = _with_display_spectral_axis(spectrum)

        assert converted.uncertainty.array == pytest.approx(np.full(5, 0.1))
        assert converted.mask.sum() == 1
        assert converted.meta == {"origin": "test"}

    def test_unconvertible_spectrum_is_returned_unchanged(self):
        spectrum = types.SimpleNamespace(flux=np.zeros(3))
        assert _with_display_spectral_axis(spectrum) is spectrum


class TestBuildSpecviz:
    PATH = Path("spec.fits")

    def test_1d_spectra_load_as_1d_format(self, monkeypatch):
        fake = _FakeApp()
        monkeypatch.setattr(jdaviz_app, "_create_app", lambda: fake)
        s1, s2 = _spectrum(1), _spectrum(1)

        viz, load_error = _build_specviz(self.PATH, [("a", s1), ("b", s2)])
        assert viz is fake
        assert load_error is None
        assert fake.loads == [(s1, FORMAT_1D, "a"), (s2, FORMAT_1D, "b")]

    def test_no_spectra_uses_jdaviz_loader_on_path(self, monkeypatch):
        fake = _FakeApp()
        monkeypatch.setattr(jdaviz_app, "_create_app", lambda: fake)

        viz, load_error = _build_specviz(self.PATH, None)
        assert viz is fake
        assert load_error is None
        # No format: jdaviz resolves the loader from the file itself.
        assert fake.loads == [(str(self.PATH), None, None)]

    def test_2d_spectrum_loads_as_2d_format(self, monkeypatch):
        fake = _FakeApp()
        monkeypatch.setattr(jdaviz_app, "_create_app", lambda: fake)
        s2d = _spectrum(2)

        viz, load_error = _build_specviz(self.PATH, [("img", s2d)])
        assert viz is fake
        assert load_error is None
        assert fake.loads == [(s2d, FORMAT_2D, "img")]

    def test_mixed_spectra_keep_their_own_format(self, monkeypatch):
        fake = _FakeApp()
        monkeypatch.setattr(jdaviz_app, "_create_app", lambda: fake)
        s2d, s1d = _spectrum(2), _spectrum(1)

        viz, load_error = _build_specviz(self.PATH, [("img", s2d), ("trace", s1d)])
        assert load_error is None
        assert fake.loads == [
            (s2d, FORMAT_2D, "img"),
            (s1d, FORMAT_1D, "trace"),
        ]

    def _failing_then_clean(self, monkeypatch):
        """Patch ``_create_app`` so the first app fails to load and the next is clean.

        Returns ``(created, forgotten)``: the apps handed out, and the ones passed
        to ``_forget_app``.
        """
        pending = [_FakeApp(fail=True), _FakeApp()]
        created, forgotten = [], []

        def factory():
            app = pending.pop(0)
            created.append(app)
            return app

        monkeypatch.setattr(jdaviz_app, "_create_app", factory)
        monkeypatch.setattr(jdaviz_app, "_forget_app", forgotten.append)
        return created, forgotten

    def test_1d_load_failure_returns_clean_viewer_and_reports(self, monkeypatch):
        created, forgotten = self._failing_then_clean(monkeypatch)

        viz, load_error = _build_specviz(self.PATH, None)
        # The app that failed is discarded: it may hold half-resolved data.
        assert len(created) == 2
        assert viz is created[1]
        # ...and dropped from jdaviz's registry, so a failure retains one app.
        assert forgotten == [created[0]]
        assert load_error == UNSUPPORTED_MESSAGE.format(name=self.PATH.name)

    def test_2d_load_failure_returns_clean_viewer_and_reports(self, monkeypatch):
        created, forgotten = self._failing_then_clean(monkeypatch)

        viz, load_error = _build_specviz(self.PATH, [("img", _spectrum(2))])
        assert len(created) == 2
        assert viz is created[1]
        assert forgotten == [created[0]]
        assert load_error == UNSUPPORTED_MESSAGE.format(name=self.PATH.name)
