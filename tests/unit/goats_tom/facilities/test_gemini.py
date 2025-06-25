from unittest.mock import patch

import pytest
from goats_tom.facilities import GEMObservationForm, GOATSGEMFacility


@pytest.mark.django_db()
class TestGOATSGEMFacility:
    """Test cases for the GOATSGEMFacility class."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.facility = GOATSGEMFacility()
        self.observation_payload = [
            {
                "prog": "GS-2024A-T-101",
                "obsnum": "01",
                "target": "ZTF19aamjwjc",
                "ra": 92.577,
                "dec": -4.960577777777778,
                "ready": "false",
                "mags": "12.0/r/AB",
                "exptime": 400,
                "elevationType": "none",
                "elevationMin": "1.0",
                "elevationMax": "2.0",
                "posangle": "0.0",
            },
        ]

    def test_get_form(self):
        form = self.facility.get_form("OBSERVATION")
        assert form is GEMObservationForm

    def test_validate_observation_valid_payload(self):
        valid_payload = [
            {
                "prog": "GN-2024A-Q-1",
                "obsnum": "1",
                "elevationType": "airmass",
                "elevationMin": "1.2",
                "elevationMax": "2.0",
                "exptime": 600,
            },
        ]
        errors = self.facility.validate_observation(valid_payload)
        assert len(errors) == 0

    def test_validate_observation_invalid_airmass(self):
        invalid_payload = [
            {
                "prog": "GN-2024A-Q-1",
                "obsnum": "1",
                "elevationType": "airmass",
                "elevationMin": "0.9",
                "elevationMax": "2.6",
                "exptime": 600,
            },
        ]
        errors = self.facility.validate_observation(invalid_payload)
        assert "elevationMin" in errors
        assert "elevationMax" in errors

    def test_validate_observation_invalid_exptime(self):
        invalid_payload = [
            {
                "prog": "GN-2024A-Q-1",
                "obsnum": "1",
                "elevationType": "airmass",
                "elevationMin": "1.2",
                "elevationMax": "2.0",
                "exptime": -1,
            },
            {
                "prog": "GN-2024A-Q-1",
                "obsnum": "2",
                "elevationType": "airmass",
                "elevationMin": "1.2",
                "elevationMax": "2.0",
                "exptime": 1300,
            },
        ]
        errors = self.facility.validate_observation(invalid_payload)
        assert "exptimes" in errors

    def test_validate_observation_invalid_obs_id(self):
        invalid_payload = [
            {
                "prog": "invalid-id",
                "obsnum": "1",
                "elevationType": "airmass",
                "elevationMin": "1.2",
                "elevationMax": "2.0",
                "exptime": 600,
            },
        ]
        errors = self.facility.validate_observation(invalid_payload)
        assert "obs" in errors
