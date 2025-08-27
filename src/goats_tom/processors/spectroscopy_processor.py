"""Module that overrides spectroscopy processor for GOATS."""

__all__ = ["SpectroscopyProcessor"]

from datetime import datetime

from astropy import units as u
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS
from specutils import Spectrum1D
from tom_dataproducts.models import DataProduct
from tom_dataproducts.processors.spectroscopy_processor import (
    SpectroscopyProcessor as BaseSpectroscopyProcessor,
)
from tom_observations.facility import get_service_class, get_service_classes


class SpectroscopyProcessor(BaseSpectroscopyProcessor):
    """Custom logic for GOATS processing. This is taken from TOMToolkit."""

    def _process_spectrum_from_fits(
        self, dataproduct: DataProduct
    ) -> tuple[Spectrum1D, datetime, str]:
        """Processes a FITS file to extract the spectrum.

        Parameters
        ----------
        dataproduct : `DataProduct`
            The data product object containing the path to the FITS file.

        Returns
        -------
        `tuple[Spectrum1D, Time, str]`
            A tuple containing the spectrum object, observation date and time, and the
            name of the facility that processed the FITS file.
        """
        # Get flux and primary header using fits.getdata.
        flux, primary_header = fits.getdata(dataproduct.data.path, header=True)
        dim = len(flux.shape)
        if dim == 3:
            flux = flux[0, 0, :]
        elif flux.shape[0] == 2:
            flux = flux[0, :]
        if primary_header["CUNIT1"] == "deg":
            # Loop through header keywords.
            for key, value in primary_header.items():
                if "WAT" in key and value is not None:
                    if "label=Wavelength units=" in value:
                        primary_header["CUNIT1"] = value.split("units=")[-1].strip()
                        break

        wcs = WCS(header=primary_header, naxis=1)

        # Get the flux unit and convert to astropy unit.
        flux_unit = primary_header.get("BUNIT")
        if flux_unit is not None:
            flux_unit = u.Unit(flux_unit)

        # Initialize facility information.
        facility_name = "UNKNOWN"
        date_obs = datetime.now()

        # Open the FITS file to check all headers for the facility.
        with fits.open(dataproduct.data.path) as hdul:
            for hdu in hdul:
                header = hdu.header
                for facility_class in get_service_classes():
                    facility = get_service_class(facility_class)()
                    if facility.is_fits_facility(header):
                        facility_name = facility_class
                        if flux_unit is None:
                            flux_unit = facility.get_flux_constant()
                        date_obs = facility.get_date_obs_from_fits_header(header)
                        break
                if facility_name != "UNKNOWN":
                    break  # Stop checking if a valid facility is found.

        # Use a default flux unit if none was determined.
        if flux_unit is None:
            flux_unit = self.DEFAULT_FLUX_CONSTANT

        # Create a Spectrum1D object with the flux and WCS.
        spectrum = Spectrum1D(flux=flux * flux_unit, wcs=wcs)

        return spectrum, Time(date_obs).to_datetime(), facility_name
