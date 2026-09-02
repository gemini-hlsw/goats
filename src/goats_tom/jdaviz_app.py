"""Solara app that embeds a jdaviz spectral viewer for a GOATS DataProduct.

This module is served by Solara and mounted into the GOATS ASGI application
under the ``/jdaviz`` prefix (see the project ``asgi.py``). A request to
``/jdaviz/?dataproduct=<pk>`` loads that DataProduct's file into jdaviz's
top-level ("deconfigged") app for interactive analysis, as a 1D or a 2D
spectrum. It backs the "Analyze" button in the data product visualizer.

Solara selects this module through the ``SOLARA_APP`` environment variable,
which :func:`goats_tom.jdaviz_asgi.init_solara` sets to ``"goats_tom.jdaviz_app"``.

.. note::
    Access is gated on an authenticated Django session: the dispatcher in
    :func:`goats_tom.jdaviz_asgi.mount_jdaviz` rejects the viewer page and every
    websocket unless the request carries a logged-in session cookie. There is no
    per-object permission check, so any authenticated user can load any data
    product's file by primary key -- add an object-level check before exposing
    this to untrusted users.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from concurrent.futures import TimeoutError as _FuturesTimeoutError
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs

import astropy.units as u
import ipygoldenlayout
import ipysplitpanes
import ipyvue
import jdaviz
import solara
from astropy.io import fits
from astropy.wcs import WCS
from jdaviz.app import custom_components
from specutils import Spectrum

from goats_tom import storage

__all__ = ["Page"]

logger = logging.getLogger(__name__)

#: Query parameter carrying the DataProduct primary key (``/jdaviz/?dataproduct=<pk>``).
DATAPRODUCT_PARAM = "dataproduct"

#: FITS extension holding the science flux in DRAGONS/Gemini MEF spectra.
SCIENCE_EXTENSION = "SCI"

#: User-facing message when a file cannot be loaded as a spectrum (1D or 2D).
UNSUPPORTED_MESSAGE = (
    "Could not load {name} as a spectrum. It may not be spectroscopic data "
    "(e.g. a calibration frame, or a format jdaviz does not recognise)."
)

#: Unit the spectral axis is displayed in, matching the TOM spectrum plots.
#: Without this jdaviz shows the WCS unit, which wcslib normalises to SI metres.
SPECTRAL_DISPLAY_UNIT = "Angstrom"

#: jdaviz loader formats. The top-level app resolves the loader from the input,
#: so an ambiguous ``Spectrum`` (1D and 2D both match) must say which one it is.
FORMAT_1D = "1D Spectrum"
FORMAT_2D = "2D Spectrum"

#: Environment variable overriding the worker pool size (see :func:`_pool_size`).
MAX_WORKERS_ENV = "GOATS_JDAVIZ_MAX_WORKERS"

#: Maximum seconds a single FITS file open/read may take before it is abandoned.
#: Generous enough for a large MEF on a slow disk, short enough that the fallback
#: still gets a turn within :data:`_WORKER_TIMEOUT`.
_FITS_TIMEOUT = 45.0

#: Maximum seconds the overall data-resolution worker may run before giving up.
#: Budgeted to nest the stages: ``_FITS_TIMEOUT`` for the DRAGONS reader plus a
#: comparable slice for the ``SpectroscopyProcessor`` fallback. Kept well under
#: two minutes because the caller blocks a Solara render thread while waiting.
_WORKER_TIMEOUT = 90.0


def _pool_size() -> int:
    """Return the worker-pool size, honouring :data:`MAX_WORKERS_ENV`.

    Defaults to ``2x`` the CPU count, capped at 16.

    The cap is about the *work*, not the database: GOATS runs on SQLite, which
    serialises access to one file, so extra threads never multiply query
    throughput. What they do parallelise is the expensive part -- reading FITS and
    running the ``SpectroscopyProcessor`` -- which is CPU- and disk-bound, hence a
    modest multiple of the CPU count rather than a large I/O-style pool.

    Deployments that need a different trade-off can override it via the
    environment.
    """
    override = os.environ.get(MAX_WORKERS_ENV)
    if override:
        try:
            return max(1, int(override))
        except ValueError:
            logger.warning(
                "Ignoring invalid %s=%r; falling back to the default pool size.",
                MAX_WORKERS_ENV,
                override,
            )
    return min(16, (os.cpu_count() or 4) * 2)


#: Shared worker pool for off-event-loop DB/file reads (reused across requests).
_executor = ThreadPoolExecutor(
    max_workers=_pool_size(),
    thread_name_prefix="goats-jdaviz",
)

#: Dedicated pool for blocking FITS reads, kept separate from :data:`_executor`
#: so a stalled file read cannot consume the slots shared with DB queries. Sized
#: to match :data:`_executor` because every ``_executor`` worker can be waiting on
#: one of these -- a smaller pool here would just move the bottleneck. These
#: threads touch no ORM, so they cost no database connections.
#:
#: Note that a read that exceeds :data:`_FITS_TIMEOUT` is only *abandoned*: the
#: thread cannot be killed and keeps its slot until the read returns. A stalled
#: mount can therefore exhaust this pool for the life of the process, after which
#: every DRAGONS read times out and the viewer falls back to the processor.
_io_executor = ThreadPoolExecutor(
    max_workers=_pool_size(),
    thread_name_prefix="goats-jdaviz-io",
)


def _call_off_event_loop(
    func: Callable[[], Any], timeout: float = _WORKER_TIMEOUT
) -> Any:
    """Run a synchronous, DB-touching callable in a loop-free worker thread.

    Solara renders inside an asyncio event loop, where Django refuses synchronous
    ORM access (``SynchronousOnlyOperation``). Running ``func`` on the shared
    worker pool gives it a context with no running event loop.

    Parameters
    ----------
    func : callable
        Zero-argument callable to run off the event loop.
    timeout : float
        Maximum seconds to wait for ``func`` to complete. Raises
        ``concurrent.futures.TimeoutError`` if the deadline is exceeded.

    Returns
    -------
    Any
        Whatever ``func`` returns. Exceptions raised by ``func`` propagate to the
        caller.
    """
    # Imported lazily so this module stays importable without Django configured.
    from django.db import connections  # noqa: PLC0415

    def worker() -> Any:
        try:
            return func()
        finally:
            # Close this thread's database connections so they are not leaked.
            connections.close_all()

    return _executor.submit(worker).result(timeout=timeout)


def _query_param(search: str | None, name: str) -> str | None:
    """Return the first value of query parameter ``name`` from a search string."""
    if not search:
        return None
    values = parse_qs(search).get(name)
    return values[0] if values else None


def _read_processor_spectra(dataproduct: Any) -> list:
    """Reduce a DataProduct to 1D spectra via TOM's ``SpectroscopyProcessor``.

    This is the same pipeline the "Plot" button uses (``fits.getdata`` + slicing
    2D/multi-row data down to 1D + the facility flux constant), so any spectrum
    that can be plotted can also be analyzed. The serialized output is rebuilt
    into ``specutils.Spectrum`` objects with ``SpectrumSerializer.deserialize``.

    Parameters
    ----------
    dataproduct : tom_dataproducts.models.DataProduct
        The data product to process.

    Returns
    -------
    list of specutils.Spectrum
        One spectrum per serialized result (usually a single element).
    """
    # Imported lazily so this module stays importable without Django configured.
    from tom_dataproducts.processors.data_serializers import (  # noqa: PLC0415
        SpectrumSerializer,
    )
    from tom_dataproducts.processors.spectroscopy_processor import (  # noqa: PLC0415
        SpectroscopyProcessor,
    )

    results = SpectroscopyProcessor().process_data(dataproduct)
    serializer = SpectrumSerializer()
    return [serializer.deserialize(serialized) for _, serialized, _ in results]


def _resolve_spectra(
    pk: str | None,
    stack: ExitStack,
) -> tuple[Path | None, list | None, str | None]:
    """Resolve a DataProduct primary key to spectra (or a path) for jdaviz.

    Tries, in order: the DRAGONS ``SCI`` reader (keeps the real nm WCS), then
    TOM's ``SpectroscopyProcessor`` (parity with the "Plot" button). If both
    decline, the file path is returned so the caller can fall back to jdaviz's
    own loaders (which cover the many specutils formats: JWST, SDSS, ECSV, ...).

    Parameters
    ----------
    pk : str or None
        The DataProduct primary key from the URL.
    stack : `contextlib.ExitStack`
        Owns the file for as long as the caller needs it. The returned path
        stays valid until this stack is closed.

        Required because the path outlives this function: `Page` builds the
        viewer in a `use_effect`, a render later. A `with` block here would
        be correct locally -- the file is the real one and deleting nothing
        -- and would delete the fetched copy out from under jdaviz under a
        remote backend. Passing the stack in makes the lifetime the
        caller's, which is where it belongs and where it can be tied to
        unmount.

    Returns
    -------
    tuple
        A ``(path, spectra, error)`` triple. ``spectra`` is a list of
        ``(label, specutils.Spectrum)`` when our readers handled the file, else
        ``None`` (the caller should try jdaviz's loaders with ``path``).
        ``error`` is set only for hard failures (missing data product/file). All
        three are ``None`` when no primary key was supplied.
    """
    # Imported lazily so this module stays importable without Django configured.
    from tom_dataproducts.models import DataProduct  # noqa: PLC0415

    if not pk:
        return None, None, None

    try:
        dataproduct = DataProduct.objects.get(pk=pk)
    except (DataProduct.DoesNotExist, ValueError, TypeError):
        return None, None, f"Data product {pk!r} not found."

    if not dataproduct.data:
        return None, None, f"Data product {pk} has no associated file."

    try:
        path = stack.enter_context(storage.local_path(dataproduct))
    except FileNotFoundError:
        return None, None, f"File for data product {pk} is missing on disk."

    # DRAGONS MEF: read every SCI extension directly to keep its real (nm)
    # wavelength WCS. Handles multi-aperture/multi-order 1D spectra (several SCI
    # extensions) and 2D spectra (a 2D SCI image), which the processor cannot.
    dragons = _read_dragons_spectra(path)
    if dragons:
        return path, dragons, None

    # Otherwise reduce to 1D the same way the "Plot" button does.
    try:
        spectra = _read_processor_spectra(dataproduct)
    except Exception as exc:
        logger.info("Processor could not read %s: %s", path.name, exc)
        spectra = None

    if not spectra:
        # Let jdaviz try its own loaders (specutils formats) on the raw file.
        return path, None, None

    multiple = len(spectra) > 1
    labelled = [
        (f"{path.stem} [{index}]" if multiple else path.stem, spectrum)
        for index, spectrum in enumerate(spectra)
    ]
    return path, labelled, None


def _dragons_hdu_to_spectrum(hdu: Any) -> Any | None:
    """Build a specutils ``Spectrum`` from a single DRAGONS ``SCI`` HDU.

    Works for both 1D (extracted) and 2D (rectified) ``SCI`` images: the flux
    keeps the HDU's WCS, so its real wavelength axis (nm for DRAGONS) survives.

    Parameters
    ----------
    hdu : astropy.io.fits.ImageHDU
        A ``SCI`` image HDU (1D or 2D data).

    Returns
    -------
    specutils.Spectrum or None
        The spectrum, or ``None`` if the HDU could not be turned into one.
    """
    header = hdu.header
    try:
        flux_unit = u.Unit(header["BUNIT"]) if header.get("BUNIT") else u.count
    except (ValueError, KeyError):
        flux_unit = u.count
    try:
        flux = hdu.data.astype("float64") * flux_unit
        wcs = WCS(header)
        return Spectrum(flux=flux, wcs=wcs)
    except Exception as exc:  # noqa: BLE001 -- malformed WCS/data: fall back.
        logger.info("Could not read SCI extension as a spectrum: %s", exc)
        return None


def _read_dragons_spectra(path: Path) -> list | None:
    """Read every DRAGONS/Gemini MEF ``SCI`` extension into specutils ``Spectrum``s.

    DRAGONS-reduced spectra are multi-extension FITS with the flux in one or more
    ``SCI`` image extensions carrying a linear wavelength WCS (plus ``VAR``/``DQ``
    and bookkeeping extensions). A file may hold several ``SCI`` extensions
    (multiple apertures/orders) and each may be 1D (extracted) or 2D (rectified).
    jdaviz's auto-loader does not recognise that layout, so the ``SCI`` extensions
    are read explicitly.

    The actual ``fits.open`` call runs in :data:`_io_executor` under a
    :data:`_FITS_TIMEOUT` deadline so a stalled network mount or corrupt file
    cannot hold a :data:`_executor` slot indefinitely.

    Parameters
    ----------
    path : Path
        Path to the FITS file.

    Returns
    -------
    list of tuple or None
        ``(label, specutils.Spectrum)`` pairs, one per usable ``SCI`` extension
        (the label carries the ``SCI`` version when there is more than one). Spectra
        may be 1D or 2D (see :func:`_build_specviz`). ``None`` if the file is not a
        DRAGONS ``SCI`` spectrum (a non-FITS file such as CSV, or a FITS without a
        usable ``SCI`` extension), so the caller can fall back to the processor.
    """

    def _fits_read() -> list | None:
        try:
            with fits.open(path) as hdul:
                sci_hdus = [
                    hdu
                    for hdu in hdul
                    if hdu.name == SCIENCE_EXTENSION
                    and hdu.data is not None
                    and hdu.data.ndim in (1, 2)
                ]
                if not sci_hdus:
                    return None
                multiple = len(sci_hdus) > 1
                spectra = []
                for hdu in sci_hdus:
                    spectrum = _dragons_hdu_to_spectrum(hdu)
                    if spectrum is None:
                        continue
                    label = f"{path.stem} [SCI,{hdu.ver}]" if multiple else path.stem
                    spectra.append((label, spectrum))
            return spectra or None
        except OSError:
            # Not a FITS file (e.g. CSV) -- fall back to the processor.
            return None

    try:
        return _io_executor.submit(_fits_read).result(timeout=_FITS_TIMEOUT)
    except _FuturesTimeoutError:
        logger.warning(
            "FITS read timed out after %.0fs for %s; skipping DRAGONS reader.",
            _FITS_TIMEOUT,
            path.name,
        )
        return None


def _widget(viz: Any) -> Any:
    """Return the ipywidget to display for a jdaviz helper.

    The helper's public ``app`` attribute is deprecated in favour of the private
    ``_app``; prefer the latter and fall back so both keep working.
    """
    private = getattr(viz, "_app", None)
    return private if private is not None else viz.app


def _forget_app(viz: Any) -> None:
    """Drop ``viz`` from jdaviz's process-wide app registry.

    ``jdaviz.new_app`` appends every app it builds to a module-level list that is
    never pruned, so each opened viewer would stay alive for the life of the
    server process. Matching is by identity, and the whole thing is best-effort:
    the registry is private API, so failing to prune must never break the viewer.

    Parameters
    ----------
    viz : Any
        The jdaviz app to remove from the registry.
    """
    try:
        apps = jdaviz.get_all_apps()
        for index, existing in enumerate(apps):
            if existing is viz:
                del apps[index]
                return
    except Exception as exc:  # noqa: BLE001 -- pruning must never break the page.
        logger.debug("Could not drop the jdaviz app from its registry: %s", exc)


def _create_app() -> Any:
    """Create a jdaviz app configured for embedding in GOATS.

    Returns
    -------
    jdaviz.configs.deconfigged.helper.App
        The configured, empty app.
    """
    # Never set as current: the module-level jdaviz API acts on the "current"
    # app, which is process-wide state shared by every user session here.
    return jdaviz.new_app(set_as_current=False)


def _replace_failed_app(viz: Any) -> Any:
    """Return a fresh app to show instead of ``viz``, discarding the failed one.

    A failed load can leave half-resolved data behind (jdaviz's own loaders may
    import a file as the wrong thing before erroring), so the user gets an empty
    app rather than one showing whatever it managed to read. The discarded app is
    dropped from the registry so a failed load does not retain two apps.

    Parameters
    ----------
    viz : Any
        The app whose load failed.

    Returns
    -------
    Any
        A new, empty jdaviz app.
    """
    _forget_app(viz)
    return _create_app()


def _spectra_are_2d(spectra: list | None) -> bool:
    """Return whether any spectrum in ``spectra`` carries 2D flux."""
    return bool(spectra) and any(spectrum.flux.ndim == 2 for _, spectrum in spectra)


def _with_display_spectral_axis(spectrum: Any) -> Any:
    """Return ``spectrum`` with its spectral axis in :data:`SPECTRAL_DISPLAY_UNIT`.

    Non-wavelength axes (pixel, frequency) are returned untouched.

    Parameters
    ----------
    spectrum : specutils.Spectrum
        Spectrum as read from the file.

    Returns
    -------
    specutils.Spectrum
        The converted spectrum, or the original one if it could not be converted.
    """
    try:
        axis = spectrum.spectral_axis
        if not axis.unit.is_equivalent(u.m):
            return spectrum
        converted = {
            "flux": spectrum.flux,
            "spectral_axis": axis.to(SPECTRAL_DISPLAY_UNIT),
            "uncertainty": spectrum.uncertainty,
            "mask": spectrum.mask,
            "meta": spectrum.meta,
        }
        if spectrum.flux.ndim > 1:
            converted["spectral_axis_index"] = spectrum.spectral_axis_index
        return Spectrum(**converted)
    except Exception as exc:  # noqa: BLE001 -- cosmetic: never block the viewer.
        logger.info("Could not convert the spectral axis: %s", exc)
        return spectrum


def _build_specviz(path: Path, spectra: list | None) -> tuple[Any, str | None]:
    """Create the jdaviz app with the spectra (or file) loaded.

    Routing:

    * 2D spectra (a DRAGONS rectified ``SCI`` image) are loaded as ``2D
      Spectrum``, which shows the 2D frame and auto-extracts a 1D trace.
    * everything else is loaded as ``1D Spectrum``. If ``spectra`` is provided
      (from our DRAGONS/processor readers) those are loaded; otherwise jdaviz's
      own loaders are tried on ``path`` so any specutils format jdaviz supports
      (JWST, SDSS, ECSV, tabular-fits, ...) works.

    Parameters
    ----------
    path : Path
        Path to the spectrum file.
    spectra : list of tuple or None
        ``(label, specutils.Spectrum)`` pairs, or ``None`` to use jdaviz's loaders.

    Returns
    -------
    tuple
        A ``(viz, load_error)`` pair. A viewer is always returned (so the user
        keeps the tools); ``load_error`` carries a short message if the file could
        not be loaded, instead of crashing the render.
    """
    viz = _create_app()

    if _spectra_are_2d(spectra):
        try:
            for label, spectrum in spectra:
                converted = _with_display_spectral_axis(spectrum)
                # A Spectrum matches both loaders, so the format is explicit.
                fmt = FORMAT_2D if converted.flux.ndim == 2 else FORMAT_1D
                viz.load(converted, format=fmt, data_label=label)
        except Exception as exc:
            logger.info("Could not load %s as a 2D spectrum: %s", path.name, exc)
            return _replace_failed_app(viz), UNSUPPORTED_MESSAGE.format(name=path.name)
        return viz, None

    try:
        if spectra:
            for label, spectrum in spectra:
                viz.load(
                    _with_display_spectral_axis(spectrum),
                    format=FORMAT_1D,
                    data_label=label,
                )
        else:
            viz.load(str(path))
    except Exception as exc:
        logger.info("Could not load %s as a spectrum: %s", path.name, exc)
        return _replace_failed_app(viz), UNSUPPORTED_MESSAGE.format(name=path.name)
    return viz, None


def _register_jdaviz_components() -> None:
    """Register the vue components jdaviz needs to render inside Solara.

    Deliberately duplicates ``create_shared_widgets`` from jdaviz's own
    ``jdaviz/solara.py`` instead of importing it: that module registers a global
    ``@solara.lab.on_kernel_start`` hook whose kernel-close callback calls
    ``os._exit(0)``. That is right for the standalone ``jdaviz`` app (closing the
    tab shuts its server down) but fatal here, where the process is the whole
    GOATS ASGI server -- leaving the viewer would kill GOATS for every user.
    **Do not replace this with an import of jdaviz.solara.**

    Registration is per Solara kernel, so the caller runs this once per kernel
    via ``solara.use_memo(..., [])`` -- a new kernel (e.g. reopening the viewer on
    another spectrum) re-mounts the component and runs it again, while re-renders
    within a kernel skip it (re-registering every render is wasted work).
    """
    ipysplitpanes.SplitPanes()
    ipygoldenlayout.GoldenLayout()
    jdaviz_dir = os.path.dirname(jdaviz.__file__)
    for name, relative_path in custom_components.items():
        ipyvue.register_component_from_file(
            None, name, os.path.join(jdaviz_dir, relative_path)
        )
    ipyvue.register_component_from_file(
        "g-viewer-tab", "container.vue", jdaviz.__file__
    )


def _inject_jdaviz_styles() -> None:
    """Inject the stylesheets jdaviz needs inside Solara (called every render).

    ``solara.Style`` is a component and must run in the render body; Solara
    reconciles repeated calls so re-renders do not stack duplicate ``<style>``
    tags.
    """
    jdaviz_dir = os.path.dirname(jdaviz.__file__)
    solara.Style(Path(jdaviz_dir) / "solara.css")


def _resolve_spectra_timed(
    pk: str | None,
    stack: ExitStack,
) -> tuple[Path | None, list | None, str | None]:
    """Run :func:`_resolve_spectra` under a timeout, degrading to a message.

    Two failure modes are turned into a user-facing message instead of a broken
    render: the worker deadline expiring, and SQLite refusing the read because the
    database is locked. The latter is not hypothetical -- GOATS stores its data on
    SQLite, whose writers take a database-wide lock, so a background download or
    reduction writing DataProducts can stall this read until the configured busy
    timeout elapses and the driver raises.

    Returns
    -------
    tuple
        The ``(path, spectra, error)`` triple from :func:`_resolve_spectra`, or a
        triple carrying a user-facing message if the read could not be completed.
    """
    # Imported lazily so this module stays importable without Django configured.
    from django.db import OperationalError  # noqa: PLC0415

    try:
        return _call_off_event_loop(lambda: _resolve_spectra(pk, stack))
    except _FuturesTimeoutError:
        logger.warning("Data resolution timed out for data product %r.", pk)
        return None, None, "Timed out loading the data product — please try again."
    except OperationalError as exc:
        logger.warning(
            "Database unavailable while loading data product %r: %s", pk, exc
        )
        return (
            None,
            None,
            "The database is busy right now — please try again in a moment.",
        )


@solara.component
def Page() -> None:
    """Render the jdaviz app for the data product identified in the URL."""
    solara.Title("GOATS · Analyze")
    _inject_jdaviz_styles()
    # Register jdaviz's shared vue components once per kernel (not every render).
    solara.use_memo(_register_jdaviz_components, [])

    # All hooks must run unconditionally (rules of hooks). The primary key is
    # passed as a query param (/jdaviz/?dataproduct=<pk>) so the Solara route
    # stays "/" -- dynamic path segments are not registered routes and would be
    # rejected by the router.
    router = solara.use_router()
    pk = _query_param(router.search, DATAPRODUCT_PARAM)

    # Resolve the spectra (data only, no widgets) during render. This touches the
    # Django ORM and the file system, so it runs off the event loop under a timeout.
    # One stack per data product, closed when the viewer unmounts. Nothing
    # is copied under local storage, so the desktop path is unchanged; under
    # a remote backend this is what keeps the fetched file alive from
    # resolution until jdaviz has finished with it.
    stack = solara.use_memo(ExitStack, [pk])
    path, spectra, error = solara.use_memo(
        lambda: _resolve_spectra_timed(pk, stack), [pk]
    )

    # Build the jdaviz app *after* the initial render, in a use_effect. jdaviz
    # instantiates internal Solara components (file_drop, file_browser) when its
    # app is constructed; building it during render makes Solara detect and mount
    # those at the top level -- the duplicated file browser / drag-and-drop seen
    # outside the viewer. Deferring construction to an effect lets the first
    # render complete so they stay inside the app. This mirrors jdaviz's own
    # ``Jdaviz`` Solara component.
    viz_state, set_viz_state = solara.use_state((None, None))  # (viz, load_error)

    def build_viewer() -> Callable[[], None] | None:
        if path is None:
            return None
        viz, load_error = _build_specviz(path, spectra)
        set_viz_state((viz, load_error))
        # Unmounting (closing the tab, or the kernel being culled) is the only
        # chance to prune jdaviz's registry -- see :func:`_forget_app`. It is
        # also the only chance to release the file: proprietary data must not
        # outlive the viewer that fetched it.
        def cleanup() -> None:
            _forget_app(viz)
            stack.close()

        return cleanup

    solara.use_effect(build_viewer, [pk])

    viz, load_error = viz_state

    # Always render a single stable container and only swap its children -- this
    # mirrors jdaviz's own ``Jdaviz`` Solara component. Changing the *shape* of
    # the tree between renders (early returns + ``solara.display``) makes Solara
    # tear down and remount the heavy jdaviz widget tree, which crashes
    # ipypopout's ``beforeDestroy`` ("Cannot read properties of null").
    with solara.Column():
        if error is not None:
            solara.Error(error)
        elif path is None:
            solara.Warning("No data product specified in the URL.")
        elif viz is None:
            # The effect that builds the viewer has not run yet (first render).
            solara.ProgressLinear(True)
        else:
            if load_error is not None:
                solara.Error(load_error)
            solara.display(_widget(viz))
