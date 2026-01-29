"""Tests for goats_tom.processors.spectroscopy_processor."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import numpy as np
from astropy.io import fits
from astropy import units as u
from datetime import datetime

from goats_tom.processors.spectroscopy_processor import SpectroscopyProcessor
from tom_dataproducts.models import DataProduct

@pytest.fixture
def mock_dataproduct():
    dp = MagicMock(spec=DataProduct)
    dp.data.path = "/path/to/test.fits"
    return dp

@pytest.fixture
def processor():
    return SpectroscopyProcessor()

class TestSpectroscopyProcessor:
    
    @patch("goats_tom.processors.spectroscopy_processor.mimetypes.guess_type")
    @patch("goats_tom.processors.spectroscopy_processor.fits.getdata")
    @patch("goats_tom.processors.spectroscopy_processor.fits_utils")
    @patch("goats_tom.processors.spectroscopy_processor.SpectrumSerializer")
    def test_process_fits_array(self, mock_serializer, mock_utils, mock_getdata, mock_guess, processor, mock_dataproduct):
        # Setup
        mock_guess.return_value = ("application/fits", None)
        
        flux_data = np.ones((10,))
        header = fits.Header({"CUNIT1": "Angstrom"})
        mock_getdata.return_value = (flux_data, header)
        
        # Mock utils
        mock_utils.get_flux_unit_from_header.return_value = None
        mock_utils.reduce_flux_array.return_value = flux_data
        mock_utils.fix_header_cunit1.return_value = u.Angstrom
        mock_utils.detect_facility.return_value = ("TestFacility", datetime(2023, 1, 1), u.Jy)
        
        # Run
        result = processor.process_data(mock_dataproduct)
        
        # Verify
        assert len(result) == 1
        obs_date, params, source_id = result[0]
        assert obs_date == datetime(2023, 1, 1)
        assert source_id == "TestFacility"
        
        # Verify calls
        mock_utils.reduce_flux_array.assert_called_once()
        mock_utils.fix_header_cunit1.assert_called_once() # Called before WCS creation in array path
        
    
    @patch("goats_tom.processors.spectroscopy_processor.mimetypes.guess_type")
    @patch("goats_tom.processors.spectroscopy_processor.fits.getdata")
    @patch("goats_tom.processors.spectroscopy_processor.fits_utils")
    @patch("goats_tom.processors.spectroscopy_processor.SpectrumSerializer")
    def test_process_fits_table(self, mock_serializer, mock_utils, mock_getdata, mock_guess, processor, mock_dataproduct):
        # Setup
        mock_guess.return_value = ("application/fits", None)
        
        # Create structured array for table
        dt = np.dtype([('wavelength', 'f8'), ('flux', 'f8')])
        table_data = np.zeros((10,), dtype=dt)
        table_data['wavelength'] = np.arange(10)
        table_data['flux'] = np.ones(10)
        header = fits.Header()
        
        mock_getdata.return_value = (table_data, header)
        
        mock_utils.get_flux_unit_from_header.return_value = u.erg / u.cm**2 / u.s / u.AA
        mock_utils.fix_header_cunit1.return_value = u.Angstrom
        mock_utils.detect_facility.return_value = ("TableFacility", datetime(2023, 2, 1), None)
        
        # Run
        result = processor.process_data(mock_dataproduct)
        
        assert result[0][0] == datetime(2023, 2, 1)
        assert result[0][2] == "TableFacility"
        
        # Verify fix_header_cunit1 called for wavelength unit
        mock_utils.fix_header_cunit1.assert_called()

    @patch("goats_tom.processors.spectroscopy_processor.mimetypes.guess_type")
    @patch("goats_tom.processors.spectroscopy_processor.fits.getdata")
    def test_missing_required_columns(self, mock_getdata, mock_guess, processor, mock_dataproduct):
        mock_guess.return_value = ("application/fits", None)
        
        dt = np.dtype([('random_col', 'f8')])
        data = np.zeros((5,), dtype=dt)
        mock_getdata.return_value = (data, fits.Header())
        
        with pytest.raises(ValueError, match="plottable spectrum"):
            processor.process_data(mock_dataproduct)
