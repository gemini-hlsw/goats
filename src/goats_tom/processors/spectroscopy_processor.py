"""
GOATS spectroscopy processor override.

Robust FITS handling:
- Finds a 1D spectrum from IMAGE or BINTABLE HDUs
- Builds spectral axis from WCS (when valid) or linear params (CRVAL/CRPIX/CDELT)
- Normalizes/infers spectral units; never leaves spectral axis unitless
- Infers flux units; falls back to DEFAULT_FLUX_CONSTANT
- Infers facility and DATE-OBS, with simple TELESCOP-based mapping
"""

from __future__ import annotations

import logging
import mimetypes
from datetime import datetime

from astropy import units as u
from astropy.io import fits
from astropy.time import Time
from specutils import Spectrum1D
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.models import DataProduct
from tom_dataproducts.processors.spectroscopy_processor import (
    SpectroscopyProcessor as BaseSpectroscopyProcessor,
)

from goats_tom.serializers import SpectrumSerializer

from .fits_utils import (
    _build_wcs_or_axis,
    _first_1d_hdu,
    _guess_flux_unit_from_header,
    _infer_facility_and_date,
    _scan_bintable_for_spectrum,
)

logger = logging.getLogger(__name__)


class SpectroscopyProcessor(BaseSpectroscopyProcessor):
    """GOATS override with robust FITS support."""

    def process_data(self, data_product: DataProduct):
        mimetype = mimetypes.guess_type(data_product.data.path)[0]
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
        return [(obs_date, serialized_spectrum, source_id)]

    def _process_spectrum_from_fits(
        self, dataproduct: DataProduct
    ) -> tuple[Spectrum1D, datetime, str]:
        path = dataproduct.data.path

        # 1) If a BINTABLE spectrum exists, prefer it (explicit spectral axis/units)
        with fits.open(path, memmap=False) as hdul:
            bt = _scan_bintable_for_spectrum(hdul)
        if bt is not None:
            flux, spectral_axis, hdr = bt
            flux_unit = _guess_flux_unit_from_header(hdr, u.one)
            # facility/date from the primary header (safer), fallback to table hdr
            with fits.open(path, memmap=False) as hdul:
                primary_header = hdul[0].header if len(hdul) else hdr
            date_obs, source_id, flux_unit = _infer_facility_and_date(
                dataproduct, primary_header, flux_unit
            )
            if flux_unit is None:
                flux_unit = self.DEFAULT_FLUX_CONSTANT
            spec = Spectrum1D(flux=flux * flux_unit, spectral_axis=spectral_axis)
            return spec, Time(date_obs).to_datetime(), source_id

        # 2) Otherwise, find first 1D IMAGE HDU
        flux, primary_header = _first_1d_hdu(path)

        # 3) Spectral axis via WCS or linear reconstruction
        mode, w = _build_wcs_or_axis(primary_header, flux.size)

        # 4) Flux units
        flux_unit = None
        bu = primary_header.get("BUNIT")
        if bu:
            try:
                flux_unit = u.Unit(bu)
            except Exception:
                logger.warning(
                    "Unrecognized BUNIT=%r; falling back to DEFAULT_FLUX_CONSTANT", bu
                )

        # 5) Facility/date and official flux unit if available
        date_obs, source_id, flux_unit = _infer_facility_and_date(
            dataproduct, primary_header, flux_unit
        )
        if flux_unit is None:
            flux_unit = self.DEFAULT_FLUX_CONSTANT

        # 6) Build Spectrum1D
        if mode == "wcs":
            spectrum = Spectrum1D(flux=flux * flux_unit, wcs=w)
        else:
            spectrum = Spectrum1D(flux=flux * flux_unit, spectral_axis=w)

        return spectrum, Time(date_obs).to_datetime(), source_id
