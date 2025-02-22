from django.test import TestCase
from pathlib import Path
from astropy.io import fits
from specutils import Spectrum1D
from goats_tom.processors import SpectroscopyProcessor
from goats_tom.tests.factories import DataProductFactory
from datetime import datetime
from django.conf import settings
import shutil

class TestSpectroscopyProcessor(TestCase):
    """Tests for the `SpectroscopyProcessor` class."""

    def setUp(self):
        """Set up test environment."""
        # Path to the test FITS file within the temporary MEDIA_ROOT.
        self.test_fits_path = Path(__file__).parent.parent.parent / "data" / "test_files" / "S20210219S0075_1D.fits"

        # Copy the test FITS file to the temporary media root.
        self.temp_fits_path = Path(settings.MEDIA_ROOT) / "S20210219S0075_1D.fits"
        shutil.copy(self.test_fits_path, self.temp_fits_path)

        # Use the factory to create a DataProduct with the copied FITS file.
        self.data_product = DataProductFactory(data=str(self.temp_fits_path))

        # Initialize the `SpectroscopyProcessor`.
        self.processor = SpectroscopyProcessor()

    def test_process_spectrum_from_fits(self):
        """Test `_process_spectrum_from_fits` processes the FITS file correctly."""
        # Run the `_process_spectrum_from_fits` method.
        spectrum, date_obs, facility_name = self.processor._process_spectrum_from_fits(self.data_product)

        # Load the FITS header for validation.
        with fits.open(self.temp_fits_path) as hdul:
            header = hdul[0].header
            expected_flux_unit = header.get("BUNIT")
        print(facility_name)
        # Assert the returned values.
        self.assertIsInstance(spectrum, Spectrum1D, "Spectrum should be a Spectrum1D instance.")
        self.assertIsInstance(date_obs, datetime, "Date observation should be a datetime instance.")
        self.assertIsInstance(facility_name, str, "Facility name should be a string.")
        self.assertNotEqual(facility_name, "UNKNOWN", "Facility name should not be UNKNOWN if a match is found.")

        # Validate the flux unit.
        if expected_flux_unit:
            self.assertEqual(spectrum.flux.unit.to_string(), expected_flux_unit, "Flux unit mismatch.")