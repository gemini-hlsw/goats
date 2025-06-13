import pytest

from goats_tom.astro_data_lab import AstroDataLabClient, AstroDataLabConfig


@pytest.fixture
def config():
    return AstroDataLabConfig()


@pytest.fixture
def client(config):
    return AstroDataLabClient("test_user", "test_pass", token="abc123", config=config)


def test_login_success(mocker, config):
    client = AstroDataLabClient("test_user", "test_pass", config=config)
    mock_get = mocker.patch.object(client._session, "get")
    mock_get.return_value = mocker.MagicMock(
        status_code=200, text="mock_token", raise_for_status=mocker.MagicMock()
    )
    token = client.login()
    assert token == "mock_token"
    assert client.token == "mock_token"


def test_is_logged_in_true(mocker, client):
    mock_get = mocker.patch.object(client._session, "get")
    mock_get.return_value = mocker.MagicMock(text="True", raise_for_status=mocker.MagicMock())
    assert client.is_logged_in()


def test_is_logged_in_false(mocker, client):
    mock_get = mocker.patch.object(client._session, "get")
    mock_get.return_value = mocker.MagicMock(text="False", raise_for_status=mocker.MagicMock())
    assert not client.is_logged_in()


def test_mkdir_success(mocker, client):
    mock_get = mocker.patch.object(client._session, "get")
    mock_get.return_value = mocker.MagicMock(status_code=200, raise_for_status=mocker.MagicMock())
    client.mkdir()


def test_mkdir_exists(mocker, client):
    mock_get = mocker.patch.object(client._session, "get")
    mock_get.return_value = mocker.MagicMock(status_code=409)
    with pytest.raises(FileExistsError):
        client.mkdir()


def test_lsdir_success(mocker, client):
    mock_get = mocker.patch.object(client._session, "get")
    mock_get.return_value = mocker.MagicMock(
        status_code=200,
        json=lambda: {"contents": ["a.fits", "b.fits"]},
        raise_for_status=mocker.MagicMock(),
    )
    assert client.lsdir() == ["a.fits", "b.fits"]


def test_lsdir_404(mocker, client):
    mock_get = mocker.patch.object(client._session, "get")
    mock_get.return_value = mocker.MagicMock(status_code=404)
    with pytest.raises(FileNotFoundError):
        client.lsdir()


def test_check_file_exists_true(mocker, client):
    mocker.patch.object(client, "lsdir", return_value=["exists.fits"])
    assert client.check_file_exists("exists.fits")


def test_check_file_exists_false(mocker, client):
    mocker.patch.object(client, "lsdir", return_value=[])
    assert not client.check_file_exists("missing.fits")


def test_delete_file_success(mocker, client):
    mock_get = mocker.patch.object(client._session, "get")
    mock_get.return_value = mocker.MagicMock(status_code=200, raise_for_status=mocker.MagicMock())
    client.delete_file("x.fits")


def test_delete_file_not_found(mocker, client):
    mock_get = mocker.patch.object(client._session, "get")
    mock_get.return_value = mocker.MagicMock(status_code=404)
    with pytest.raises(FileNotFoundError):
        client.delete_file("x.fits")


def test_upload_file_success(mocker, client, tmp_path):
    file_path = tmp_path / "data.fits"
    file_path.write_bytes(b"data")

    mocker.patch.object(client, "check_file_exists", return_value=False)
    mocker.patch.object(client, "_create_empty", return_value="http://upload")
    mock_put = mocker.patch.object(client._session, "put")
    mock_put.return_value = mocker.MagicMock(status_code=200, raise_for_status=mocker.MagicMock())

    client.upload_file(file_path)


def test_upload_file_overwrite(mocker, client, tmp_path):
    file_path = tmp_path / "overwrite.fits"
    file_path.write_bytes(b"overwrite")

    mocker.patch.object(client, "check_file_exists", return_value=True)
    mocker.patch.object(client, "delete_file")
    mocker.patch.object(client, "_create_empty", return_value="http://upload")
    mock_put = mocker.patch.object(client._session, "put")
    mock_put.return_value = mocker.MagicMock(status_code=200, raise_for_status=mocker.MagicMock())

    client.upload_file(file_path, overwrite=True)


def test_upload_file_exists_no_overwrite(mocker, client, tmp_path):
    file_path = tmp_path / "conflict.fits"
    file_path.write_bytes(b"content")

    mocker.patch.object(client, "check_file_exists", return_value=True)

    with pytest.raises(FileExistsError):
        client.upload_file(file_path)


def test_upload_file_not_found(client):
    with pytest.raises(FileNotFoundError):
        client.upload_file("/non/existent/file.fits")