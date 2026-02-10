"""Utility (helper) functions for processing FITS files."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Final

import numpy as np
from astropy import units as u
from astropy.io import fits
from astropy.time import Time
from tom_observations.facility import get_service_class, get_service_classes

logger = logging.getLogger(__name__)

PLOT_ERROR_MESSAGE: Final[str] = "This FITS file does not contain a plottable spectrum."


def get_flux_unit_from_header(
    header: fits.Header, table_dtype_names: tuple[str, ...] | None = None
) -> u.UnitBase | None:
    """Attempt to determine the flux unit from the header or table columns."""
    flux_unit = None

    # Check TUNITn if it's a table
    if table_dtype_names:
        for i, name in enumerate(table_dtype_names, start=1):
            if str(name).strip().lower() == "flux":
                tunit_key = f"TUNIT{i}"
                tunit_val = header.get(tunit_key)
                if tunit_val:
                    try:
                        flux_unit = u.Unit(tunit_val)
                        logger.debug(
                            "get_flux_unit: parsed %s -> %s", tunit_key, flux_unit
                        )
                    except Exception:
                        logger.exception(
                            "get_flux_unit: failed to parse %s=%r", tunit_key, tunit_val
                        )
                return flux_unit

    # Check BUNIT (arrays)
    bunit = header.get("BUNIT")
    if bunit:
        try:
            flux_unit = u.Unit(bunit)
            logger.debug("get_flux_unit: parsed BUNIT -> %s", flux_unit)
        except Exception:
            logger.exception("get_flux_unit: failed to parse BUNIT=%r", bunit)

    return flux_unit


def fix_header_cunit1(header: fits.Header) -> u.UnitBase:
    """Ensure CUNIT1 exists in header and return the wavelength unit.

    Modifies the header in-place if CUNIT1 is missing or needs parsing from WAT.
    """
    cunit1 = header.get("CUNIT1")

    if cunit1:
        if cunit1 == "deg":
            # Check WAT keywords
            for key, value in header.items():
                value_str = str(value) if value is not None else ""
                if "WAT" in key and "label=Wavelength units=" in value_str:
                    new_cunit1 = value_str.split("units=")[-1].strip()
                    header["CUNIT1"] = new_cunit1
                    logger.debug(
                        "fix_header_cunit1: CUNIT1 updated from WAT key=%s -> %r",
                        key,
                        new_cunit1,
                    )
                    try:
                        return u.Unit(new_cunit1)
                    except Exception:
                        pass
                    break
        else:
            try:
                return u.Unit(cunit1)
            except Exception:
                pass
    else:
        header["CUNIT1"] = "Angstrom"
        logger.debug("fix_header_cunit1: CUNIT1 missing -> defaulting to 'Angstrom'")

    # Final attempt to return unit from (possibly updated) CUNIT1
    cunit1 = header.get("CUNIT1", "Angstrom")
    try:
        return u.Unit(cunit1)
    except Exception:
        return u.Unit("Angstrom")


def reduce_flux_array(flux: np.ndarray, header: fits.Header) -> np.ndarray:
    """Reduce dimensionality of flux array to 1D."""
    naxis = header.get("NAXIS")
    dim = len(flux.shape)

    if naxis == 2 and dim == 2:
        logger.error("reduce_flux_array: rejecting image-like primary (NAXIS=2)")
        raise ValueError(PLOT_ERROR_MESSAGE)

    if dim == 3:
        return flux[0, 0, :]
    elif flux.shape[0] == 2:
        return flux[0, :]

    return flux


def detect_facility(path: str) -> tuple[str, datetime, u.UnitBase | None]:
    """Scan HDUs to detect facility, observation date, and potential flux unit."""
    facility_name = "LCO"
    date_obs = datetime.now()
    flux_unit = None

    with fits.open(path) as hdul:
        for hdu_index, hdu in enumerate(hdul):
            header = hdu.header
            telescop_upper = str(header.get("TELESCOP", "")).upper()

            for facility_class in get_service_classes():
                facility = get_service_class(facility_class)()
                try:
                    match = facility.is_fits_facility(header) or (
                        facility_class.upper() in telescop_upper
                    )
                except Exception:
                    continue

                if match:
                    facility_name = facility_class

                    try:
                        flux_unit = facility.get_flux_constant()
                    except Exception:
                        pass

                    try:
                        date_obs_val = facility.get_date_obs_from_fits_header(header)
                        # Ensure date_obs is datetime
                        date_obs = Time(date_obs_val).to_datetime()
                    except Exception:
                        pass

                    return facility_name, date_obs, flux_unit

    return facility_name, date_obs, flux_unit
