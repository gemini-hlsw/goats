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

    DEFAULT_FLUX_CONSTANT = u.erg / u.angstrom / u.cm**2 / u.second
    PLOT_ERROR_MESSAGE: Final[str] = (
        "This FITS file does not contain a plottable spectrum."
    )

    def process_data(
        self, data_product: DataProduct
    ) -> list[tuple[datetime, dict, str]]:
        """Route processing based on file type and serialize the resulting spectrum.

        Parameters
        ----------
        data_product : DataProduct
            Data product to process.

        Returns
        -------
        list[tuple[datetime, dict, str]]
            List with a single tuple: (
                observation_datetime,
                serialized_spectrum,
                source_id
            ).
        """
        mimetype = mimetypes.guess_type(data_product.data.path)[0]
        logger.debug(
            "process_data: path=%s mimetype=%r", data_product.data.path, mimetype
        )

        spectrum: Spectrum1D
        obs_date: datetime
        source_id: str

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
        self, dataproduct: DataProduct
    ) -> tuple[Spectrum1D, datetime, str]:
        """Extract a 1D spectrum (flux + wavelength) from a FITS file.

        Uses helper functions from fits_utils.
        """
        path = dataproduct.data.path
        flux, primary_header = fits.getdata(path, header=True)

        flux_unit = None
        wavelength = None
        wcs = None
        is_table = False

        # Check if table
        dtype_names = getattr(getattr(flux, "dtype", None), "names", None)

        # Get flux unit from header/table first check
        flux_unit = fits_utils.get_flux_unit_from_header(primary_header, dtype_names)

        if dtype_names:
            is_table = True
            if ("flux" not in dtype_names) or ("wavelength" not in dtype_names):
                raise ValueError(self.PLOT_ERROR_MESSAGE)

            wavelength = np.asarray(flux["wavelength"], dtype=float)
            flux = np.asarray(flux["flux"], dtype=float)

            # For tables, get wavelength unit
            wave_unit = fits_utils.fix_header_cunit1(primary_header)

        else:
            # Array path
            flux = fits_utils.reduce_flux_array(flux, primary_header)

            # Fix header CUNIT1 before creating WCS!
            _ = fits_utils.fix_header_cunit1(primary_header)

            wcs = WCS(header=primary_header, naxis=1)

        # Detect facility info
        facility_name, date_obs, facility_flux_unit = fits_utils.detect_facility(path)

        # Fix explicit boolean check for Quantity truthiness
        if flux_unit is None and facility_flux_unit is not None:
            flux_unit = facility_flux_unit

        if flux_unit is None:
            flux_unit = self.DEFAULT_FLUX_CONSTANT

        # Build Spectrum
        flux_q = np.asarray(flux, dtype=float) * flux_unit

        if is_table:
            spectrum = Spectrum1D(flux=flux_q, spectral_axis=wavelength * wave_unit)
        else:
            spectrum = Spectrum1D(flux=flux_q, wcs=wcs)

        # Normalize
        try:
            if spectrum.flux.unit.is_equivalent(self.DEFAULT_FLUX_CONSTANT):
                spectrum = spectrum.with_flux_unit(self.DEFAULT_FLUX_CONSTANT)
        except Exception:
            logger.exception("Flux normalization failed")

        return spectrum, date_obs, facility_name
