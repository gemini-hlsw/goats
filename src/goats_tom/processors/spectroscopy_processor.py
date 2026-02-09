"""Module that overrides spectroscopy processor for GOATS."""

__all__ = ["SpectroscopyProcessor"]

import logging
import mimetypes
from datetime import datetime
from typing import Final

import numpy as np
from astropy import units as u
from astropy.io import fits
from astropy.wcs import WCS
from specutils import Spectrum1D
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.models import DataProduct
from tom_dataproducts.processors.spectroscopy_processor import (
    SpectroscopyProcessor as BaseSpectroscopyProcessor,
)

from goats_tom.processors import fits_utils
from goats_tom.serializers import SpectrumSerializer

logger = logging.getLogger(__name__)


class SpectroscopyProcessor(BaseSpectroscopyProcessor):
    """Custom logic for GOATS spectroscopy processing."""

    DEFAULT_SOURCE_ID: Final[str] = "DEFAULT"
    DEFAULT_FLUX_CONSTANT = u.erg / u.angstrom / u.cm**2 / u.second
    PLOT_ERROR_MESSAGE: Final[str] = (
        "This FITS file does not contain a plottable spectrum."
    )

    SKIP_EXTNAMES: Final[set[str]] = {"VAR", "ERR", "DQ", "BPM", "MASK"}

    def process_data(
        self, data_product: DataProduct
    ) -> list[tuple[datetime, dict, str]]:
        """Route processing based on file type and serialize resulting spectrum(s)."""
        path = data_product.data.path
        mimetype = mimetypes.guess_type(path)[0]
        logger.debug("process_data: path=%s mimetype=%r", path, mimetype)

        if mimetype in self.FITS_MIMETYPES:
            extracted = self._process_spectrum_from_fits(
                data_product
            )  # [(obs_date, spectrum, source_id), ...]
        elif mimetype in self.PLAINTEXT_MIMETYPES:
            spectrum, obs_date, source_id = self._process_spectrum_from_plaintext(
                data_product
            )
            extracted = [(obs_date, spectrum, source_id)]
        else:
            raise InvalidFileFormatException("Unsupported file type")

        serializer = SpectrumSerializer()
        out: list[tuple[datetime, dict, str]] = []

        for obs_date, spectrum, source_id in extracted:
            serialized = serializer.serialize(spectrum)
            logger.debug(
                "process_data: serialized keys=%s source_id=%s",
                list(serialized.keys()),
                source_id,
            )
            out.append((obs_date, serialized, source_id))

        return out

    def _process_spectrum_from_fits(
        self, data_product: DataProduct
    ) -> list[tuple[datetime, Spectrum1D, str]]:
        """Extract one or more 1D spectra (flux + wavelength) from a FITS file."""
        path = data_product.data.path

        file_source_id, obs_date, facility_flux_unit = fits_utils.detect_facility(path)
        if not file_source_id:
            file_source_id = self.DEFAULT_SOURCE_ID

        results: list[tuple[datetime, Spectrum1D, str]] = []

        with fits.open(path) as hdul:
            extnames = [str(h.header.get("EXTNAME", "")).strip().upper() for h in hdul]
            has_sci = "SCI" in extnames

            logger.debug(
                "FITS scan: hdus=%d has_sci=%s extnames=%s",
                len(hdul),
                has_sci,
                extnames,
            )

            for hdu_index, hdu in enumerate(hdul):
                data = hdu.data
                header = hdu.header

                extname = str(header.get("EXTNAME", "")).strip().upper() or "NOEXTNAME"

                if data is None:
                    logger.debug(
                        "FITS scan: skip hdu=%d ext=%s (no data)", hdu_index, extname
                    )
                    continue

                if extname in self.SKIP_EXTNAMES:
                    logger.debug(
                        "FITS scan: skip hdu=%d ext=%s (non-science)",
                        hdu_index,
                        extname,
                    )
                    continue

                if has_sci and extname != "SCI":
                    logger.debug(
                        "FITS scan: skip hdu=%d ext=%s (SCI preferred)",
                        hdu_index,
                        extname,
                    )
                    continue

                dtype_names = getattr(getattr(data, "dtype", None), "names", None)
                is_table = bool(dtype_names)

                try:
                    flux_unit = fits_utils.get_flux_unit_from_header(
                        header, dtype_names
                    )
                    if flux_unit is None and facility_flux_unit is not None:
                        flux_unit = facility_flux_unit
                    if flux_unit is None:
                        flux_unit = self.DEFAULT_FLUX_CONSTANT

                    if is_table:
                        dtype_names = dtype_names or ()
                        # Map lowercase -> actual column name, so we can index safely
                        colmap = {
                            str(n).strip().lower(): str(n).strip() for n in dtype_names
                        }
                        flux_col = colmap.get("flux")
                        wave_col = colmap.get("wavelength")

                        if not flux_col or not wave_col:
                            logger.debug(
                                "FITS scan: skip hdu=%d ext=%s (missing columns)."
                                "dtype_names=%s",
                                hdu_index,
                                extname,
                                dtype_names,
                            )
                            continue

                        wavelength = np.asarray(data[wave_col], dtype=float)
                        flux_vals = np.asarray(data[flux_col], dtype=float)

                        wavelength_unit = fits_utils.fix_header_cunit1(header)
                        flux_q = np.asarray(flux_vals, dtype=float) * flux_unit

                        spectrum = Spectrum1D(
                            flux=flux_q, spectral_axis=wavelength * wavelength_unit
                        )

                    else:
                        flux_vals = fits_utils.reduce_flux_array(
                            np.asarray(data), header
                        )

                        _ = fits_utils.fix_header_cunit1(header)
                        wcs = WCS(header=header, naxis=1)

                        flux_q = np.asarray(flux_vals, dtype=float) * flux_unit
                        spectrum = Spectrum1D(flux=flux_q, wcs=wcs)

                    try:
                        if spectrum.flux.unit.is_equivalent(self.DEFAULT_FLUX_CONSTANT):
                            spectrum = spectrum.with_flux_unit(
                                self.DEFAULT_FLUX_CONSTANT
                            )
                    except Exception:
                        logger.exception(
                            "Flux normalization failed (hdu=%d ext=%s)",
                            hdu_index,
                            extname,
                        )

                    hdu_source_id = f"{file_source_id}:hdu={hdu_index}:{extname}"
                    logger.debug(
                        "FITS scan: use hdu=%d ext=%s source_id=%s",
                        hdu_index,
                        extname,
                        hdu_source_id,
                    )

                    results.append((obs_date, spectrum, hdu_source_id))

                except ValueError as e:
                    logger.debug(
                        "FITS scan: skip hdu=%d ext=%s (not plottable): %s",
                        hdu_index,
                        extname,
                        e,
                    )
                    continue
                except Exception:
                    logger.exception(
                        "FITS scan: fail hdu=%d ext=%s", hdu_index, extname
                    )
                    continue

        if not results:
            raise InvalidFileFormatException(self.PLOT_ERROR_MESSAGE)

        return results
