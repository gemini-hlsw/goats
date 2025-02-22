"""Tests for parsing Gemini IDs."""

import pytest
from goats_tom.ocs import GeminiID


def test_parse_valid_program_id():
    """Test parsing a valid program ID."""
    parser = GeminiID("GS-2023B-Q-101")
    assert parser.site == "GS"
    assert parser.semester == "2023B"
    assert parser.program_type == "Q"
    assert parser.program_number == 101
    assert parser.observation_number is None
    assert not parser.is_observation_id()


def test_parse_valid_observation_id():
    """Test parsing a valid observation ID."""
    parser = GeminiID("GS-2023B-Q-101-2")
    assert parser.site == "GS"
    assert parser.semester == "2023B"
    assert parser.program_type == "Q"
    assert parser.program_number == 101
    assert parser.observation_number == 2
    assert parser.is_observation_id()


def test_parse_id_with_bad_ids():
    """Test parsing an ID with a wrong format."""
    bad_ids = [
        "GT-2023B-Q-101",  # Invalid site code (GT instead of GN/GS)
        "GS-23B-Q-101",  # Incorrect semester format
        "GS-2023B-123-101",  # Numeric program type
        "GS-2023B-Q-ABC",  # Non-numeric program number
        "GS-2023B-Q-101-XYZ",  # Non-numeric observation number
        "GS2023BQ101",  # Missing hyphens
        "GS-2023B--Q-101",  # Double hyphen
        "GS-2023B-Q-101-2-3",  # Extra segment in observation ID
        "GN-2023A-Q",  # Missing program number
        "GS-2023B-QQ101",  # Missing hyphen between program type and number
        "GS-2023B-Q-101-",  # Trailing hyphen in program ID
        "GS-2023B-Q--101",  # Double hyphen within ID
        "GS-2023B-Q-101-1-2",  # Extra parts in observation ID
        "",  # Empty string
        "GS-2023B-Q-",  # Incomplete ID
    ]

    for bad_id in bad_ids:
        try:
            GeminiID(bad_id)
            assert False, f"ID '{bad_id}' should have raised ValueError"
        except ValueError:
            pass


def test_gemini_id_immutable_properties():
    """Test immutability."""
    gemini_id = GeminiID("GS-2023A-Q-100")

    with pytest.raises(AttributeError):
        gemini_id.site = "GN"
    with pytest.raises(AttributeError):
        gemini_id.semester = "2024B"
    with pytest.raises(AttributeError):
        gemini_id.program_type = "DD"
    with pytest.raises(AttributeError):
        gemini_id.program_number = 101
    with pytest.raises(AttributeError):
        gemini_id.observation_number = 2
    with pytest.raises(AttributeError):
        gemini_id.program_id = "GS-2023A-DD-101"
    with pytest.raises(AttributeError):
        gemini_id.observation_id = "GS-2023A-DD-101-1"


def test_is_valid_program_id():
    """Test the class method for validating program IDs."""
    valid_program_ids = [
        "GS-2023B-Q-101",
        "GN-2024A-DD-1",
        "GS-2025B-FT-42",
    ]
    invalid_program_ids = [
        "GT-2023B-Q-101",
        "GS-2023-FT-101",
        "GS-23B-Q-101",
        "XYZ-2023B-Q-101",
    ]

    for program_id in valid_program_ids:
        assert GeminiID.is_valid_program_id(
            program_id,
        ), f"Program ID '{program_id}' should be valid"

    for program_id in invalid_program_ids:
        assert not GeminiID.is_valid_program_id(
            program_id,
        ), f"Program ID '{program_id}' should be invalid"


def test_is_valid_observation_id():
    """Test the class method for validating observation IDs."""
    valid_observation_ids = [
        "GS-2023B-Q-101-2",
        "GN-2024A-DD-1-1",
        "GS-2025B-FT-42-5",
    ]
    invalid_observation_ids = [
        "GT-2023B-Q-101-2",
        "GS-2023-Q-101-2",
        "GS-23B-Q-101-2",
        "XYZ-2023B-Q-101-2",
    ]

    for observation_id in valid_observation_ids:
        assert GeminiID.is_valid_observation_id(
            observation_id,
        ), f"Observation ID '{observation_id}' should be valid"

    for observation_id in invalid_observation_ids:
        assert not GeminiID.is_valid_observation_id(
            observation_id,
        ), f"Observation ID '{observation_id}' should be invalid"


def test_is_valid():
    """Test the class method for validating either program or observation
    IDs.
    """
    valid_ids = [
        "GS-2023B-Q-101",
        "GN-2024A-DD-1-1",
        "GS-2025B-FT-42-5",
    ]
    invalid_ids = [
        "GT-2023B-Q-101-2",
        "GS-23B-Q-101-2",
        "XYZ-2023B-Q-101-2",
    ]

    for gemini_id in valid_ids:
        assert GeminiID.is_valid(gemini_id), f"ID '{gemini_id}' should be valid"

    for gemini_id in invalid_ids:
        assert not GeminiID.is_valid(gemini_id), f"ID '{gemini_id}' should be invalid"
