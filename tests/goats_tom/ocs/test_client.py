from pathlib import Path

import pytest

from goats_tom.ocs import OCSClient


@pytest.fixture()
def client():
    """Fixture to create an OCSClient instance."""
    return OCSClient()


@pytest.fixture()
def odb_xml():
    file_path = Path(__file__).parent.parent.parent / "data" / "odb.xml"
    with open(file_path) as file:
        return file.read()


@pytest.fixture()
def coordinates_xml():
    file_path = Path(__file__).parent.parent.parent / "data" / "coordinates.xml"
    with open(file_path) as file:
        return file.read()


@pytest.fixture()
def sequence_xml():
    file_path = Path(__file__).parent.parent.parent / "data" / "sequence.xml"
    with open(file_path) as file:
        return file.read()


@pytest.fixture()
def observation_id():
    return "GS-2023B-Q-102-3"


@pytest.fixture()
def program_id():
    return "GS-2023B-Q-102"


def test_get_program_summary_with_observation_id(
    client, odb_xml, observation_id, mocker
):
    mock_send = mocker.patch.object(client, "_send_request", return_value={"success": True, "raw_data": odb_xml})

    result = client.get_program_summary(observation_id)

    mock_send.assert_called_once_with(observation_id)
    assert isinstance(result, dict)
    assert result["success"]


def test_get_program_summary_with_program_id(client, odb_xml, program_id, mocker):
    mock_send = mocker.patch.object(client, "_send_request", return_value={"success": True, "raw_data": odb_xml})

    result = client.get_program_summary(program_id)
    assert isinstance(result, dict)
    assert result["success"]


def test_get_observation_summary(client, odb_xml, observation_id, mocker):
    mock_send = mocker.patch.object(client, "_send_request", return_value={"success": True, "raw_data": odb_xml})

    result = client.get_observation_summary(observation_id)
    assert isinstance(result, dict)
    assert result["success"]

@pytest.mark.remote_data()
def test_get_coordinates_remote(client, observation_id):
    coordinates_response = client.get_coordinates(observation_id)
    assert coordinates_response["data"]
    assert coordinates_response["success"]


@pytest.mark.remote_data()
def test_get_sequence_remote(client, observation_id):
    sequence_response = client.get_sequence(observation_id)
    assert sequence_response["data"]
    assert sequence_response["success"]


@pytest.mark.remote_data()
def test_get_observation_summary_remote(client, observation_id):
    observation_id_response = client.get_observation_summary(observation_id)
    assert observation_id_response["data"]
    assert observation_id_response["success"]


@pytest.mark.remote_data()
def test_get_program_summary_with_observation_id_remote(client, observation_id):
    program_id_response = client.get_program_summary(observation_id)
    assert program_id_response["data"]
    assert program_id_response["success"]


@pytest.mark.remote_data()
def test_get_program_summary_with_program_id_remote(client, program_id):
    program_id_response = client.get_program_summary(program_id)
    assert program_id_response["data"]
    assert program_id_response["success"]
