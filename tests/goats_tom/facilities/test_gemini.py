from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests

from goats_tom.facilities import GEMObservationForm, GOATSGEMFacility
from goats_tom.tests.factories import GPPLoginFactory, UserFactory


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

    def test_get_observation_status_gpp_success(self, mocker):
        user = UserFactory()
        GPPLoginFactory(user=user, token="tok")

        mocker.patch(
            "goats_tom.facilities.gemini.get_current_user_id",
            return_value=user.id,
        )

        workflow_response = Mock()
        workflow_response.model_dump.return_value = {
            "observation": {
                "id": "o-123",
                "program": {"id": "p-456"},
                "workflow": {"value": {"state": "ONGOING"}},
            }
        }
        mock_client = mocker.patch("goats_tom.facilities.gemini.GPPClient")
        mock_client.return_value.workflow_state.get_by_reference = AsyncMock(
            return_value=workflow_response
        )

        result = self.facility.get_observation_status("G-2024A-Q-100-1")

        assert result["state"] == "Ongoing"
        assert result["parameters"]["gpp_id"] == "o-123"
        assert result["parameters"]["gpp_program_id"] == "p-456"
        mock_client.return_value.workflow_state.get_by_reference.assert_called_once_with(
            observation_reference="G-2024A-Q-100-1"
        )

    def test_get_observation_status_gpp_no_user_context(self, mocker):
        mocker.patch(
            "goats_tom.facilities.gemini.get_current_user_id",
            return_value=None,
        )

        result = self.facility.get_observation_status("G-2024A-Q-100-1")

        assert result["state"] == "Error"
        assert result["parameters"] == {}

    def test_get_observation_status_gpp_no_workflow_falls_back_to_archive(
        self, mocker
    ):
        """When GPP returns no workflow state, fall back to the archive."""
        user = UserFactory()
        GPPLoginFactory(user=user, token="tok")

        mocker.patch(
            "goats_tom.facilities.gemini.get_current_user_id",
            return_value=user.id,
        )

        workflow_response = Mock()
        workflow_response.model_dump.return_value = {"observation": None}
        mock_client = mocker.patch("goats_tom.facilities.gemini.GPPClient")
        mock_client.return_value.workflow_state.get_by_reference = AsyncMock(
            return_value=workflow_response
        )

        archive_mock = mocker.patch.object(
            self.facility, "_state_from_archive", return_value="Observed"
        )

        result = self.facility.get_observation_status("G-2024A-Q-100-1")

        assert result["state"] == "Observed"
        assert result["parameters"] == {}
        archive_mock.assert_called_once_with("G-2024A-Q-100-1")

    def test_state_from_archive_with_data(self, mocker):
        """Archive returns data products, so the state is observed."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = [{"filename": "S20240101.fits"}]
        mock_get = mocker.patch(
            "goats_tom.facilities.gemini.requests.get", return_value=response
        )

        state = self.facility._state_from_archive("G-2024A-Q-100-1")

        assert state == "Observed"
        mock_get.assert_called_once()

    def test_state_from_archive_without_data(self, mocker):
        """Archive returns no data products, so the state is Error."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = []
        mocker.patch(
            "goats_tom.facilities.gemini.requests.get", return_value=response
        )

        state = self.facility._state_from_archive("G-2024A-Q-100-1")

        assert state == "Error"

    def test_state_from_archive_request_error(self, mocker):
        """A failed archive lookup returns Error."""
        mocker.patch(
            "goats_tom.facilities.gemini.requests.get",
            side_effect=requests.RequestException("boom"),
        )

        state = self.facility._state_from_archive("G-2024A-Q-100-1")

        assert state == "Error"
