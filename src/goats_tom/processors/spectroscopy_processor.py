"""Module that overrides spectroscopy processor for GOATS."""

from __future__ import annotations

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

    def process_data(
        self, data_product: DataProduct
    ) -> list[tuple[datetime, dict, str]]:
        """Route processing based on file type and serialize the resulting spectrum.

        Returns
        -------
        list[tuple[datetime, dict, str]]
            (obs_date, serialized_spectrum, source_id)
        """
        mimetype = mimetypes.guess_type(data_product.data.path)[0]
        logger.debug(
            "process_data: path=%s mimetype=%r", data_product.data.path, mimetype
        )

        if mimetype in self.FITS_MIMETYPES:
            spectrum, obs_date, source_id = self._process_spectrum_from_fits(
                data_product
            )
        elif mimetype in self.PLAINTEXT_MIMETYPES:
            spectrum, obs_date, source_id = self._process_spectrum_from_plaintext(
                data_product
            )
        else:
            raise InvalidFileFormatException("Unsupported file type")

        serialized_spectrum = SpectrumSerializer().serialize(spectrum)
        logger.debug(
            "process_data: serialized keys=%s source_id=%s",
            list(serialized_spectrum.keys()),
            source_id,
        )
        return [(obs_date, serialized_spectrum, source_id)]

    def _process_spectrum_from_fits(
        self, data_product: DataProduct
    ) -> tuple[Spectrum1D, datetime, str]:
        """Extract a 1D spectrum (flux + wavelength) from a FITS file."""
        path = data_product.data.path
        data, header = fits.getdata(path, header=True)

        dtype_names = getattr(getattr(data, "dtype", None), "names", None)
        is_table = bool(dtype_names)

        flux_unit = fits_utils.get_flux_unit_from_header(header, dtype_names)

        if is_table:
            if ("flux" not in dtype_names) or ("wavelength" not in dtype_names):
                raise InvalidFileFormatException(self.PLOT_ERROR_MESSAGE)

            wavelength = np.asarray(data["wavelength"], dtype=float)
            flux_vals = np.asarray(data["flux"], dtype=float)

            wavelength_unit = fits_utils.fix_header_cunit1(header)
            wcs = None
        else:
            flux_vals = fits_utils.reduce_flux_array(data, header)

            header = fits_utils.fix_header_cunit1(header)
            wcs = WCS(header=header, naxis=1)

            wavelength = None
            wavelength_unit = None

        source_id, obs_date, facility_flux_unit = fits_utils.detect_facility(path)

        if source_id is None:
            source_id = self.DEFAULT_SOURCE_ID

        if flux_unit is None and facility_flux_unit is not None:
            flux_unit = facility_flux_unit

        if flux_unit is None:
            flux_unit = self.DEFAULT_FLUX_CONSTANT

        flux_q = np.asarray(flux_vals, dtype=float) * flux_unit

        if is_table:
            spectrum = Spectrum1D(
                flux=flux_q,
                spectral_axis=wavelength * wavelength_unit,
            )
        else:
            spectrum = Spectrum1D(flux=flux_q, wcs=wcs)

        try:
            if spectrum.flux.unit.is_equivalent(self.DEFAULT_FLUX_CONSTANT):
                spectrum = spectrum.with_flux_unit(self.DEFAULT_FLUX_CONSTANT)
        except Exception:
            logger.exception("Flux normalization failed")

        return spectrum, obs_date, source_id
