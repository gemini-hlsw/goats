from pathlib import Path

import pytest

from goats_tom.ocs import OCSParser


@pytest.fixture()
def ocs_parser():
    return OCSParser()


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


def test_parse_odb_response(ocs_parser, odb_xml):
    result = ocs_parser.parse_odb_response(odb_xml)
    assert isinstance(result, dict)
    assert result


def test_parse_coordinates_response(ocs_parser, coordinates_xml):
    result = ocs_parser.parse_coordinates_response(coordinates_xml)
    assert isinstance(result, dict)
    assert result


def test_parse_sequence_response(ocs_parser, sequence_xml):
    result = ocs_parser.parse_sequence_response(sequence_xml)
    assert isinstance(result, dict)
    assert result
