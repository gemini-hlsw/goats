import json
from unittest.mock import AsyncMock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from goats_tom.api_views import GPPObservationViewSet
from goats_tom.api_views.gpp.observations import (
    MessageStatus,
    ResponseStatus,
    Stage,
    StageMessage,
    build_failure_response,
)
from goats_tom.tests.factories import GPPLoginFactory, UserFactory


@pytest.mark.parametrize(
    "stage, error, previous_messages, data, http_status, overall_status, expected_response",
    [
        (
            Stage.VALIDATION,
            "Validation error occurred",
            [],
            None,
            status.HTTP_400_BAD_REQUEST,
            ResponseStatus.FAILURE,
            {
                "status": "Failure",
                "messages": [
                    {
                        "stage": "Data Validation",
                        "status": "Error",
                        "message": "Validation error occurred",
                    }
                ],
                "data": {},
            },
        ),
        (
            Stage.CREATE_OBSERVATION,
            Exception("Unexpected error"),
            [
                StageMessage(
                    stage=Stage.CREDENTIALS_CHECK,
                    status=MessageStatus.SUCCESS,
                    message="Credentials verified successfully.",
                )
            ],
            {"key": "value"},
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            ResponseStatus.FAILURE,
            {
                "status": "Failure",
                "messages": [
                    {
                        "stage": "Credentials Check",
                        "status": "Success",
                        "message": "Credentials verified successfully.",
                    },
                    {
                        "stage": "Create Observation",
                        "status": "Error",
                        "message": "Unexpected error",
                    },
                ],
                "data": {"key": "value"},
            },
        ),
        (
            Stage.UPDATE_TARGET,
            "Target update failed",
            [
                StageMessage(
                    stage=Stage.VALIDATION,
                    status=MessageStatus.SUCCESS,
                    message="Validation passed.",
                )
            ],
            None,
            status.HTTP_400_BAD_REQUEST,
            ResponseStatus.PARTIAL_SUCCESS,
            {
                "status": "Partial Success",
                "messages": [
                    {
                        "stage": "Data Validation",
                        "status": "Success",
                        "message": "Validation passed.",
                    },
                    {
                        "stage": "Update Sidereal Target",
                        "status": "Error",
                        "message": "Target update failed",
                    },
                ],
                "data": {},
            },
        ),
    ],
)
def test_build_failure_response(
    stage,
    error,
    previous_messages,
    data,
    http_status,
    overall_status,
    expected_response,
):
    response = build_failure_response(
        stage=stage,
        error=error,
        previous_messages=previous_messages,
        data=data,
        http_status=http_status,
        overall_status=overall_status,
    )

    assert isinstance(response, Response)
    assert response.status_code == http_status
    assert response.data == expected_response


@pytest.mark.django_db
class TestGPPObservationViewSet:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.viewset = GPPObservationViewSet()
        self.list_view = GPPObservationViewSet.as_view({"get": "list"})
        self.retrieve_view = GPPObservationViewSet.as_view({"get": "retrieve"})
        self.create_and_save_view = GPPObservationViewSet.as_view(
            {"post": "create_and_save_observation"}
        )

        self.observation_id = "o-23e1"
        self.observation_data = {"observation_id": self.observation_id, "name": "m27"}
        self.observations_url = "/api/gpp/observations/"
        self.observation_detail_url = f"/api/gpp/observations/{self.observation_id}/"
        self.observation_save_only_url = f"{self.observations_url}save-only/"
        self.observation_create_and_save_url = (
            f"{self.observations_url}create-and-save/"
        )
        self.observation_update_and_save_url = (
            f"{self.observations_url}update-and-save/"
        )

        # Setup users.
        self.user_with_login = UserFactory()
        GPPLoginFactory(user=self.user_with_login)
        self.user_without_login = UserFactory()

    def test_create_and_save_missing_gpplogin(self) -> None:
        """Return 400 if the user has no GPP credentials."""
        request = self.factory.post(self.observation_create_and_save_url, {})
        force_authenticate(request, user=self.user_without_login)

        response = self.create_and_save_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_observations_success(self, mocker):
        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        mock_client.return_value.observation.get_all = AsyncMock(
            return_value=[self.observation_data]
        )

        request = self.factory.get(self.observations_url)
        force_authenticate(request, user=self.user_with_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == [self.observation_data]
        mock_client.return_value.observation.get_all.assert_called_once()

    def test_list_observations_missing_gpplogin(self):
        request = self.factory.get(self.observations_url)
        force_authenticate(request, user=self.user_without_login)

        response = self.list_view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.data["detail"]
            == "GPP login credentials are not configured for this user."
        )

    def test_retrieve_observation_success(self, mocker):
        mock_client = mocker.patch("goats_tom.api_views.gpp.observations.GPPClient")
        mock_client.return_value.observation.get_by_id = AsyncMock(
            return_value=self.observation_data
        )

        request = self.factory.get(self.observation_detail_url)
        force_authenticate(request, user=self.user_with_login)

        response = self.retrieve_view(request, pk=self.observation_id)

        assert response.status_code == status.HTTP_200_OK
        assert response.data == self.observation_data
        mock_client.return_value.observation.get_by_id.assert_called_once_with(
            observation_id=self.observation_id
        )

    def test_retrieve_observation_missing_gpplogin(self):
        request = self.factory.get(self.observation_detail_url)
        force_authenticate(request, user=self.user_without_login)

        response = self.retrieve_view(request, pk=self.observation_id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.data["detail"]
            == "GPP login credentials are not configured for this user."
        )

    def test_too_observation(self):
        obs = {
            "targetEnvironment": {
                "asterism": [
                    {"id": "t-1", "opportunity": {"__typename": "Opportunity"}}
                ]
            }
        }
        assert self.viewset.is_too(obs) is True

    def test_normal_observation_opportunity_none(self):
        obs = {"targetEnvironment": {"asterism": [{"id": "t-2", "opportunity": None}]}}
        assert self.viewset.is_too(obs) is False

    def test_empty_asterism_list(self):
        obs = {"targetEnvironment": {"asterism": []}}
        assert self.viewset.is_too(obs) is False

    def test_missing_asterism_key(self):
        obs = {"targetEnvironment": {}}
        assert self.viewset.is_too(obs) is False

    def test_asterism_none(self):
        obs = {"targetEnvironment": {"asterism": None}}
        assert self.viewset.is_too(obs) is False

    def test_missing_target_environment(self):
        obs = {}
        assert self.viewset.is_too(obs) is False

    def test_target_environment_none(self):
        obs = {"targetEnvironment": None}
        assert self.viewset.is_too(obs) is False

    def test_normalize_finder_charts_without_payload_returns_empty_structure(self):
        data = {}

        out = self.viewset._normalize_finder_charts(data)

        assert out["finderCharts"] == {"toAdd": [], "toDelete": []}

    def test_normalize_finder_charts_builds_to_add_and_to_delete(self):
        file1 = SimpleUploadedFile("fc1.png", b"abc", content_type="image/png")
        file2 = SimpleUploadedFile("fc2.jpg", b"def", content_type="image/jpeg")

        data = {
            "finderCharts": json.dumps(
                {
                    "toAdd": [
                        {"fileKey": "fileA", "description": "first"},
                        {"fileKey": "fileB", "description": "second"},
                    ],
                    "toDelete": ["att-1", "att-2"],
                }
            ),
            "fileA": file1,
            "fileB": file2,
        }

        out = self.viewset._normalize_finder_charts(data)

        assert "fileA" not in out
        assert "fileB" not in out
        assert out["finderCharts"]["toDelete"] == ["att-1", "att-2"]

        to_add = out["finderCharts"]["toAdd"]
        assert len(to_add) == 2
        assert to_add[0]["description"] == "first"
        assert to_add[0]["file"] == file1
        assert to_add[1]["description"] == "second"
        assert to_add[1]["file"] == file2

    def test_normalize_finder_charts_skips_missing_file_objects(self):
        file1 = SimpleUploadedFile("fc1.png", b"abc", content_type="image/png")

        data = {
            "finderCharts": json.dumps(
                {
                    "toAdd": [
                        {"fileKey": "fileA", "description": "first"},
                        {"fileKey": "missingFile", "description": "missing"},
                    ],
                    "toDelete": [],
                }
            ),
            "fileA": file1,
        }

        out = self.viewset._normalize_finder_charts(data)

        to_add = out["finderCharts"]["toAdd"]
        assert len(to_add) == 1
        assert to_add[0]["description"] == "first"
        assert to_add[0]["file"] == file1

    def test_process_finder_charts_delete_only_returns_remaining_ids(self, mocker):
        client = mocker.Mock()

        def fake_async_to_sync(fn):
            return fn

        mocker.patch(
            "goats_tom.api_views.gpp.observations.async_to_sync",
            side_effect=fake_async_to_sync,
        )

        client.attachment.delete_by_id = mocker.Mock()
        client.attachment.get_all_by_observation = mocker.Mock(
            return_value={"attachments": [{"id": "a1"}, {"id": "a2"}]}
        )
        client.attachment.upload = mocker.Mock()

        out = self.viewset._process_finder_charts(
            client=client,
            observation_id="obs-1",
            program_id="prog-1",
            finder_charts={
                "toDelete": ["old-1", "old-2"],
                "toAdd": [],
            },
        )

        assert client.attachment.delete_by_id.call_count == 2
        client.attachment.delete_by_id.assert_any_call(attachment_id="old-1")
        client.attachment.delete_by_id.assert_any_call(attachment_id="old-2")
        client.attachment.get_all_by_observation.assert_called_once_with(
            observation_id="obs-1",
            observation_reference=None,
        )
        assert out == ["a1", "a2"]

    def test_process_finder_charts_add_only_uploads_and_appends_ids(self, mocker):
        file1 = SimpleUploadedFile("fc1.png", b"abc", content_type="image/png")
        file2 = SimpleUploadedFile("fc2.jpg", b"def", content_type="image/jpeg")

        client = mocker.Mock()

        def fake_async_to_sync(fn):
            return fn

        mocker.patch(
            "goats_tom.api_views.gpp.observations.async_to_sync",
            side_effect=fake_async_to_sync,
        )

        client.attachment.delete_by_id = mocker.Mock()
        client.attachment.get_all_by_observation = mocker.Mock(
            return_value={"attachments": [{"id": "existing-1"}]}
        )
        client.attachment.upload = mocker.Mock(side_effect=["new-1", "new-2"])

        out = self.viewset._process_finder_charts(
            client=client,
            observation_id="obs-1",
            program_id="prog-1",
            finder_charts={
                "toDelete": [],
                "toAdd": [
                    {"description": "first", "file": file1},
                    {"description": "second", "file": file2},
                ],
            },
        )

        assert client.attachment.upload.call_count == 2

        first_call = client.attachment.upload.call_args_list[0]
        second_call = client.attachment.upload.call_args_list[1]

        assert first_call.kwargs["program_id"] == "prog-1"
        assert first_call.kwargs["file_name"] == "fc1.png"
        assert first_call.kwargs["description"] == "first"
        assert first_call.kwargs["content"] == b"abc"

        assert second_call.kwargs["file_name"] == "fc2.jpg"
        assert second_call.kwargs["description"] == "second"
        assert second_call.kwargs["content"] == b"def"

        assert out == ["existing-1", "new-1", "new-2"]

    def test_process_finder_charts_skips_items_without_file(self, mocker):
        client = mocker.Mock()

        def fake_async_to_sync(fn):
            return fn

        mocker.patch(
            "goats_tom.api_views.gpp.observations.async_to_sync",
            side_effect=fake_async_to_sync,
        )

        client.attachment.delete_by_id = mocker.Mock()
        client.attachment.get_all_by_observation = mocker.Mock(
            return_value={"attachments": [{"id": "existing-1"}]}
        )
        client.attachment.upload = mocker.Mock()

        out = self.viewset._process_finder_charts(
            client=client,
            observation_id="obs-1",
            program_id="prog-1",
            finder_charts={
                "toDelete": [],
                "toAdd": [
                    {"description": "missing", "file": None},
                ],
            },
        )

        client.attachment.upload.assert_not_called()
        assert out == ["existing-1"]

    @pytest.mark.parametrize(
        "finder_charts, setup_attr, expected_pattern",
        [
            (
                {"toDelete": ["bad-id"], "toAdd": []},
                "delete_error",
                "Failed to delete finder chart 'bad-id'",
            ),
            (
                {"toDelete": [], "toAdd": []},
                "fetch_error",
                "Failed to fetch current finder charts",
            ),
            (
                {
                    "toDelete": [],
                    "toAdd": [
                        {
                            "description": "first",
                            "file": SimpleUploadedFile(
                                "fc1.png", b"abc", content_type="image/png"
                            ),
                        }
                    ],
                },
                "upload_error",
                "Failed to upload finder chart 'fc1.png'",
            ),
        ],
    )
    def test_process_finder_charts_raises_value_error(
        self, mocker, finder_charts, setup_attr, expected_pattern
    ):
        client = mocker.Mock()

        def fake_async_to_sync(fn):
            return fn

        mocker.patch(
            "goats_tom.api_views.gpp.observations.async_to_sync",
            side_effect=fake_async_to_sync,
        )

        client.attachment.delete_by_id = mocker.Mock()
        client.attachment.get_all_by_observation = mocker.Mock(
            return_value={"attachments": []}
        )
        client.attachment.upload = mocker.Mock()

        if setup_attr == "delete_error":
            client.attachment.delete_by_id.side_effect = RuntimeError("boom")
        elif setup_attr == "fetch_error":
            client.attachment.get_all_by_observation.side_effect = RuntimeError(
                "fetch failed"
            )
        elif setup_attr == "upload_error":
            client.attachment.upload.side_effect = RuntimeError("upload failed")

        with pytest.raises(ValueError, match=expected_pattern):
            self.viewset._process_finder_charts(
                client=client,
                observation_id="obs-1",
                program_id="prog-1",
                finder_charts=finder_charts,
            )
