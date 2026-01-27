"""
Utilities for parsing FITS files in the SpectroscopyProcessor.
"""

from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
from astropy import units as u
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS
from tom_dataproducts.models import DataProduct
from tom_observations.facility import get_service_class, get_service_classes

logger = logging.getLogger(__name__)

# --- Aliases to normalize CUNIT1-like text to astropy Units
_UNIT_ALIASES = {
    "angstrom": "Angstrom",
    "ang": "Angstrom",
    "a": "Angstrom",
    "aa": "Angstrom",
    "å": "Angstrom",
    "nm": "nm",
    "nanometer": "nm",
    "micron": "um",
    "micrometer": "um",
    "um": "um",
}

# --- Lightweight mapping from TELESCOP -> facility class name (adjust as needed)
_TELESCOP_TO_FACILITY = {
    "SOAR 4.1M": "SOARFacility",
    "SOAR": "SOARFacility",
    "SOAR 4.1m": "SOARFacility",
    "LCOGT": "LCOFacility",
    "LCO": "LCOFacility",
    "GEMINI-SOUTH": "GeminiSouthFacility",
    "GEMINI-NORTH": "GeminiNorthFacility",
}


# ---------------------------- header utilities ---------------------------- #


def _normalize_cunit1(hdr: fits.Header) -> None:
    """
    Normalize CUNIT1 in-place:
      - If CUNIT1 is recognizable alias (angstrom, um, nm), fix it.
      - If CUNIT1 is missing/deg and WAT*_001 contains 'units=...', use it.
    """
    cu = (hdr.get("CUNIT1") or "").strip()
    if cu:
        key = cu.lower().replace(" ", "")
        cu_norm = _UNIT_ALIASES.get(key)
        if cu_norm:
            hdr["CUNIT1"] = cu_norm
            return

    # If CUNIT1 is missing or deg (bad), try WAT* 'units=' hint
    if not cu or cu.lower() == "deg":
        for k, v in hdr.items():
            if k.startswith("WAT") and isinstance(v, str) and "units=" in v:
                after = v.split("units=")[-1].strip().lower()
                after = after.rstrip("s")  # angstroms -> angstrom
                cu_norm = _UNIT_ALIASES.get(after)
                if cu_norm:
                    hdr["CUNIT1"] = cu_norm
                else:
                    try:
                        u.Unit(after)
                        hdr["CUNIT1"] = after
                    except Exception:
                        pass
                break


def _default_wave_unit(hdr: fits.Header) -> u.Unit:
    """Choose a safe default spectral unit based on CTYPE1, defaulting to Angstrom."""
    ctype = (hdr.get("CTYPE1") or "").upper()
    if "FREQ" in ctype:
        return u.Hz
    if "ENER" in ctype:
        return u.J
    if "WAVN" in ctype or "WAVENUM" in ctype:
        return 1 / u.m
    if "VELO" in ctype or "VRAD" in ctype:
        return u.km / u.s
    return u.Angstrom


def _guess_wave_unit_from_header(hdr: fits.Header) -> u.Unit | None:
    """Try CUNIT1; if absent, infer from CTYPE1; otherwise None."""
    cu = hdr.get("CUNIT1")
    if cu:
        try:
            return u.Unit(cu)
        except Exception:
            pass
    ctype = (hdr.get("CTYPE1") or "").upper()
    if any(
        k in ctype for k in ("WAVE", "FREQ", "ENER", "WAVN", "VELO", "VRAD", "LINEAR")
    ):
        return _default_wave_unit(hdr)
    return None


def _guess_flux_unit_from_header(hdr: fits.Header, fallback: u.Unit) -> u.Unit:
    """Use BUNIT if valid; else a provided fallback."""
    bu = hdr.get("BUNIT")
    if bu:
        try:
            return u.Unit(bu)
        except Exception:
            pass
    return fallback


# ------------------------------ HDU discovery ----------------------------- #


def _ensure_1d_flux_array(data: np.ndarray) -> np.ndarray:
    """Coerce common shapes to 1D numeric array."""
    if data is None:
        raise ValueError("Empty data array")

    a = np.asarray(data)

    # If table-like record array sneaks in here, raise
    if hasattr(a.dtype, "fields") and a.dtype.fields:
        raise TypeError("Structured (record) array not allowed as flux")

    if a.ndim == 1:
        return a.astype(float, copy=False)

    # Common image shapes (e.g., (1, 1, N), (2, N), (N, 1))
    if a.ndim == 2:
        # prefer first row/col when it looks like a single spectrum
        if a.shape[0] == 1:
            return a[0, :].astype(float, copy=False)
        if a.shape[1] == 1:
            return a[:, 0].astype(float, copy=False)
        # (2, N) sometimes carries multi-extension info; pick first row as spectrum
        if a.shape[0] == 2:
            return a[0, :].astype(float, copy=False)

    if a.ndim == 3 and 1 in (a.shape[0], a.shape[1]):
        # Squeeze leading singleton dims until 1D
        a2 = np.squeeze(a)
        if a2.ndim == 1:
            return a2.astype(float, copy=False)

    raise ValueError(f"Unsupported flux array shape: {a.shape}")


def _first_1d_hdu(path: str) -> tuple[np.ndarray, fits.Header]:
    """
    Find the first IMAGE HDU that can be coerced to 1D flux. Returns (flux1d, header).
    Raises if none found.
    """
    with fits.open(path, memmap=False) as hdul:
        for hdu in hdul:
            if not hasattr(hdu, "data"):
                continue
            data = hdu.data
            if data is None:
                continue
            try:
                flux = _ensure_1d_flux_array(data)
                return flux, hdu.header
            except Exception:
                continue
    raise ValueError("No 1D IMAGE HDU found in FITS")


def _column_name_like(names: list[str], *candidates: str) -> str | None:
    """Return the first column name that case-insensitively matches
    any candidate substrings."""

    low = [n.lower() for n in names]
    for cand in candidates:
        c = cand.lower()
        for i, n in enumerate(low):
            if c in n:
                return names[i]
    return None


def _column_unit(hdu: fits.BinTableHDU, name: str) -> u.Unit | None:
    """Extract astropy Unit from a table column's TUNIT keyword, if present."""
    try:
        idx = list(hdu.columns.names).index(name)
    except Exception:
        return None
    key = f"TUNIT{idx + 1}"
    val = hdu.header.get(key)
    if not val:
        return None
    try:
        return u.Unit(val)
    except Exception:
        return None


def _scan_bintable_for_spectrum(
    hdul: fits.HDUList,
) -> tuple[np.ndarray, u.Quantity, fits.Header] | None:
    """
    If a BINTABLE with spectral columns is present,
    return (flux1d, spectral_axis(quantity), header).
    Looks for columns like wavelength/frequency/energy and flux/ivar/error.
    """
    for hdu in hdul:
        if (
            not isinstance(hdu, (fits.BinTableHDU, fits.FITS_rec))
            and hdu.header.get("XTENSION", "") != "BINTABLE"
        ):
            continue
        if not hasattr(hdu, "data") or hdu.data is None:
            continue
        cols = list(hdu.columns.names or [])
        if not cols:
            continue

        wcol = _column_name_like(
            cols,
            "wavelength",
            "wave",
            "freq",
            "frequency",
            "energy",
            "wavenumber",
            "vel",
            "vrad",
        )
        fcol = _column_name_like(
            cols, "flux", "f_lambda", "fnu", "flam", "spectrum", "intensity"
        )

        if not wcol or not fcol:
            continue

        w = np.asarray(hdu.data[wcol])
        f = np.asarray(hdu.data[fcol])

        # Handle structured/record dtypes in flux (common in 1D reduced products)
        if hasattr(f.dtype, "fields") and f.dtype.fields:
            # Heuristic: pick the first numeric field that matches flux-ish names
            for subname in f.dtype.names:
                if any(
                    k in subname.lower() for k in ("flux", "flam", "fnu", "intensity")
                ):
                    f = f[subname]
                    break

        f = np.asarray(f, dtype=float)
        if f.ndim != 1 or w.ndim != 1 or f.size != w.size:
            continue

        # Units
        wunit = (
            _column_unit(hdu, wcol)
            or _guess_wave_unit_from_header(hdu.header)
            or _default_wave_unit(hdu.header)
        )
        return f, (w * wunit), hdu.header

    return None


# -------------------------- spectral axis construction -------------------- #


def _build_linear_axis_from_wcs_like(hdr: fits.Header, n: int) -> np.ndarray | None:
    """
    Build a linear axis using CRVAL1/CRPIX1/CDELT1; returns float array or None.
    """
    try:
        crval = float(hdr.get("CRVAL1"))
        crpix = float(hdr.get("CRPIX1", 1.0))
        cdelt = float(hdr.get("CDELT1", hdr.get("CD1_1")))
        if not np.isfinite(crval) or not np.isfinite(crpix) or not np.isfinite(cdelt):
            return None
        pix = np.arange(n, dtype=float) + 1.0
        return crval + (pix - crpix) * cdelt
    except Exception:
        return None


def _build_wcs_or_axis(hdr: fits.Header, n: int) -> tuple[str, WCS | u.Quantity]:
    """
    Try WCS first (only if CUNIT1 is present/normalized).
    Otherwise, build a linear axis with a safe unit.
    Returns ("wcs", WCS) or ("axis", spectral_axis: Quantity).
    """
    _normalize_cunit1(hdr)

    if not hdr.get("CUNIT1"):
        arr = _build_linear_axis_from_wcs_like(hdr, n) or np.arange(n, dtype=float)
        unit = _guess_wave_unit_from_header(hdr) or _default_wave_unit(hdr)
        return "axis", arr * unit

    try:
        wcs = WCS(header=hdr, naxis=1)
        # sanity check: convert endpoints
        world = wcs.pixel_to_world_values([0, n - 1])
        if world is not None and np.all(np.isfinite(world)):
            return "wcs", wcs
    except Exception:
        pass

    arr = _build_linear_axis_from_wcs_like(hdr, n) or np.arange(n, dtype=float)
    unit = _guess_wave_unit_from_header(hdr) or _default_wave_unit(hdr)
    return "axis", arr * unit


# ------------------------- facility/date inference ------------------------ #


def _infer_facility_and_date(
    dataproduct: DataProduct,
    primary_header: fits.Header,
    flux_unit_hint: u.Unit | None,
) -> tuple[datetime, str, u.Unit | None]:
    """
    Iterate over HDUs to detect the facility (via `is_fits_facility`) and
    observation date.
    Also tries a quick TELESCOP mapping, and to retrieve a canonical flux unit
    if the facility exposes it.
    Returns: (date_obs, facility_name, flux_unit or None)
    """
    facility_name = "UNKNOWN"
    date_obs = datetime.now()

    # quick mapping via TELESCOP
    tele = (primary_header.get("TELESCOP") or "").strip()
    if tele:
        mapped = _TELESCOP_TO_FACILITY.get(tele.upper())
        if mapped:
            facility_name = mapped

    # walk HDUs to confirm/refine
    with fits.open(dataproduct.data.path, memmap=False) as hdul:
        for hdu in hdul:
            hdr = hdu.header
            for fac_name in get_service_classes():
                fac_cls = get_service_class(fac_name)
                fac = fac_cls()
                try:
                    if fac.is_fits_facility(hdr):
                        facility_name = fac_name
                        try:
                            date_obs = fac.get_date_obs_from_fits_header(hdr)
                        except Exception:
                            if "DATE-OBS" in hdr:
                                date_obs = Time(hdr["DATE-OBS"]).to_datetime()
                        if flux_unit_hint is None:
                            for attr in ("get_data_flux_constant", "get_flux_constant"):
                                if hasattr(fac, attr):
                                    try:
                                        flux_unit_hint = getattr(fac, attr)()
                                        break
                                    except Exception:
                                        pass
                        return date_obs, facility_name, flux_unit_hint
                except Exception:
                    continue

    # fallback DATE-OBS if not found while scanning
    if "DATE-OBS" in primary_header:
        try:
            date_obs = Time(primary_header["DATE-OBS"]).to_datetime()
        except Exception:
            pass

    return date_obs, facility_name, flux_unit_hint
