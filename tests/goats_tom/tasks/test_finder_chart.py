from pathlib import Path

import pytest
from gpp_client.exceptions import GPPResponseError

from goats_tom.tasks.finder_chart import upload_finder_chart
from goats_tom.tests.factories import GPPLoginFactory, UserFactory


@pytest.fixture
def tmp_upload_file(tmp_path):
    f = tmp_path / "fc.png"
    f.write_bytes(b"image-bytes")
    return f


@pytest.mark.django_db
def test_upload_finder_chart_missing_file(mocker, tmp_path):
    user = UserFactory()
    GPPLoginFactory(user=user)

    notify = mocker.patch(
        "goats_tom.tasks.finder_chart.NotificationInstance.create_and_send"
    )

    missing_path = str(tmp_path / "does_not_exist.png")

    result = upload_finder_chart.fn(
        upload_id="upload-1",
        tmp_path=missing_path,
        file_name="fc.png",
        program_id="p-1",
        observation_id="o-1",
        description="desc",
        user_id=user.id,
    )

    assert result["state"] == "ERROR"
    assert result["upload_id"] == "upload-1"
    assert "Temporary file not found" in result["message"]
    notify.assert_called_once()


@pytest.mark.django_db
def test_upload_finder_chart_missing_credentials(mocker, tmp_upload_file):
    user = UserFactory()  # no GPPLogin associated

    notify = mocker.patch(
        "goats_tom.tasks.finder_chart.NotificationInstance.create_and_send"
    )

    result = upload_finder_chart.fn(
        upload_id="upload-1",
        tmp_path=str(tmp_upload_file),
        file_name="fc.png",
        program_id="p-1",
        observation_id="o-1",
        description="desc",
        user_id=user.id,
    )

    assert result["state"] == "ERROR"
    assert "GPP credentials not found" in result["message"]
    notify.assert_called_once()
    assert not Path(tmp_upload_file).exists()


@pytest.mark.django_db
def test_upload_finder_chart_missing_token(mocker, tmp_upload_file):
    user = UserFactory()
    GPPLoginFactory(user=user, token="")

    notify = mocker.patch(
        "goats_tom.tasks.finder_chart.NotificationInstance.create_and_send"
    )

    result = upload_finder_chart.fn(
        upload_id="upload-1",
        tmp_path=str(tmp_upload_file),
        file_name="fc.png",
        program_id="p-1",
        observation_id="o-1",
        description="desc",
        user_id=user.id,
    )

    assert result["state"] == "ERROR"
    assert "Missing GPP token" in result["message"]
    notify.assert_called_once()
    assert not Path(tmp_upload_file).exists()


@pytest.mark.django_db
def test_upload_finder_chart_success(mocker, tmp_upload_file):
    user = UserFactory()
    GPPLoginFactory(user=user, token="tok")

    notify = mocker.patch(
        "goats_tom.tasks.finder_chart.NotificationInstance.create_and_send"
    )

    fake_client = mocker.AsyncMock()
    fake_client.attachment.upload = mocker.AsyncMock(return_value={"id": "new-att"})
    fake_client.attachment.get_all_by_observation = mocker.AsyncMock(
        return_value={"attachments": [{"id": "existing-1"}]}
    )
    fake_client.observation.update_by_id = mocker.AsyncMock(return_value={})
    fake_client.close = mocker.AsyncMock()

    mocker.patch(
        "goats_tom.tasks.finder_chart.GPPClient", return_value=fake_client
    )

    result = upload_finder_chart.fn(
        upload_id="upload-1",
        tmp_path=str(tmp_upload_file),
        file_name="fc.png",
        program_id="p-1",
        observation_id="o-1",
        description="a chart",
        user_id=user.id,
    )

    assert result["state"] == "DONE"
    assert result["id"] == "new-att"
    assert result["upload_id"] == "upload-1"

    fake_client.attachment.upload.assert_awaited_once()
    upload_kwargs = fake_client.attachment.upload.await_args.kwargs
    assert upload_kwargs["program_id"] == "p-1"
    assert upload_kwargs["file_name"] == "fc.png"
    assert upload_kwargs["description"] == "a chart"
    assert upload_kwargs["content"] == b"image-bytes"

    fake_client.observation.update_by_id.assert_awaited_once()
    update_kwargs = fake_client.observation.update_by_id.await_args.kwargs
    assert update_kwargs["observation_id"] == "o-1"
    assert update_kwargs["from_json"] == {
        "attachments": ["existing-1", "new-att"]
    }

    notify.assert_not_called()
    assert not Path(tmp_upload_file).exists()


@pytest.mark.django_db
def test_upload_finder_chart_no_id_returned(mocker, tmp_upload_file):
    user = UserFactory()
    GPPLoginFactory(user=user, token="tok")

    notify = mocker.patch(
        "goats_tom.tasks.finder_chart.NotificationInstance.create_and_send"
    )

    fake_client = mocker.AsyncMock()
    fake_client.attachment.upload = mocker.AsyncMock(return_value={"id": None})
    fake_client.close = mocker.AsyncMock()
    mocker.patch(
        "goats_tom.tasks.finder_chart.GPPClient", return_value=fake_client
    )

    result = upload_finder_chart.fn(
        upload_id="upload-1",
        tmp_path=str(tmp_upload_file),
        file_name="fc.png",
        program_id="p-1",
        observation_id="o-1",
        description="desc",
        user_id=user.id,
    )

    assert result["state"] == "ERROR"
    assert "GPP did not return attachment id" in result["message"]
    # `notify=False` for the internal error, but the wrapper notifies at the end.
    notify.assert_called_once()


@pytest.mark.django_db
def test_upload_finder_chart_duplicate_name(mocker, tmp_upload_file):
    user = UserFactory()
    GPPLoginFactory(user=user, token="tok")

    notify = mocker.patch(
        "goats_tom.tasks.finder_chart.NotificationInstance.create_and_send"
    )

    fake_client = mocker.AsyncMock()
    fake_client.attachment.upload = mocker.AsyncMock(
        side_effect=GPPResponseError(400, "Duplicate file name 'fc.png'")
    )
    fake_client.close = mocker.AsyncMock()
    mocker.patch(
        "goats_tom.tasks.finder_chart.GPPClient", return_value=fake_client
    )

    result = upload_finder_chart.fn(
        upload_id="upload-1",
        tmp_path=str(tmp_upload_file),
        file_name="fc.png",
        program_id="p-1",
        observation_id="o-1",
        description="desc",
        user_id=user.id,
    )

    assert result["state"] == "ERROR"
    assert "already exists in GPP" in result["message"]
    notify.assert_called_once()


@pytest.mark.django_db
def test_upload_finder_chart_other_gpp_error(mocker, tmp_upload_file):
    user = UserFactory()
    GPPLoginFactory(user=user, token="tok")

    notify = mocker.patch(
        "goats_tom.tasks.finder_chart.NotificationInstance.create_and_send"
    )

    fake_client = mocker.AsyncMock()
    fake_client.attachment.upload = mocker.AsyncMock(
        side_effect=GPPResponseError(500, "network down")
    )
    fake_client.close = mocker.AsyncMock()
    mocker.patch(
        "goats_tom.tasks.finder_chart.GPPClient", return_value=fake_client
    )

    result = upload_finder_chart.fn(
        upload_id="upload-1",
        tmp_path=str(tmp_upload_file),
        file_name="fc.png",
        program_id="p-1",
        observation_id="o-1",
        description="desc",
        user_id=user.id,
    )

    assert result["state"] == "ERROR"
    assert "network down" in result["message"]
    notify.assert_called_once()
