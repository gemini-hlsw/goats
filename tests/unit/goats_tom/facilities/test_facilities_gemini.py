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

    @patch("goats_tom.facilities.gemini.get_key_info")
    @patch("goats_tom.facilities.gemini.make_request")
    def test_submit_observation_with_user_key(
        self, mock_make_request, mock_get_key_info,
    ):
        mock_get_key_info.return_value = {
            "email": "user@test.com",
            "password": "userkey123",
        }
        mock_make_request.return_value.text = "GS-2024A-Q-123-001"

        obsids = self.facility.submit_observation(self.observation_payload)

        assert mock_get_key_info.called
        assert mock_make_request.called
        assert len(obsids) == 1
        assert obsids[0] == "001"

        # Check the payload sent to make_request
        sent_payload = mock_make_request.call_args[1]["params"]
        expected_payload = self.observation_payload[0].copy()
        expected_payload.update({"email": "user@test.com", "password": "userkey123"})
        assert sent_payload == expected_payload

    @patch("goats_tom.facilities.gemini.get_key_info")
    @patch("goats_tom.facilities.gemini.make_request")
    def test_submit_observation_with_program_key(
        self, mock_make_request, mock_get_key_info,
    ):
        mock_get_key_info.return_value = {"password": "programkey123"}
        mock_make_request.return_value.text = "GS-2024A-Q-123-001"

        obsids = self.facility.submit_observation(self.observation_payload)

        assert mock_get_key_info.called
        assert mock_make_request.called
        assert len(obsids) == 1
        assert obsids[0] == "001"

        # Check the payload sent to make_request
        sent_payload = mock_make_request.call_args[1]["params"]
        expected_payload = self.observation_payload[0].copy()
        # TODO: Have to test with this hardcoded email while we wait for OCS
        # to make changes to accept without email.
        expected_payload.update({"password": "programkey123", "email": "ocs@test.com"})
        assert sent_payload == expected_payload
