# tests/test_scheduling_windows_serializers.py
import json
import pytest
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp.scheduling_windows import (
    TimingWindowAfterSerializer,
    TimingWindowRepeatPeriodSerializer,
    TimingWindowRepeatSerializer,
    TimingWindowEndSerializer,
    TimingWindowSerializer,
    SchedulingWindowsSerializer,
)
from gpp_client.api.enums import TimingWindowInclusion


# --- Helpers -----------------------------------------------------------------

def make_window(*, inclusion="INCLUDE", start="2025-01-01T10:00", end=None):
    data = {"inclusion": inclusion, "startUtc": start}
    if end is not None:
        data["end"] = end
    return data


# --- TimingWindowAfterSerializer ---------------------------------------------

@pytest.mark.parametrize("seconds, valid", [
    (10, True),
    (1, True),
    (0, False),
    (-1, False),
])
def test_after_seconds(seconds, valid):
    s = TimingWindowAfterSerializer(data={"seconds": seconds})
    assert s.is_valid() is valid
    if valid:
        assert s.validated_data["seconds"] == seconds
    else:
        assert "seconds" in s.errors


# --- TimingWindowRepeatPeriodSerializer --------------------------------------

@pytest.mark.parametrize("seconds, valid", [
    (3, True),
    (1, True),
    (0, False),
    (-1, False),
])
def test_repeat_period(seconds, valid):
    s = TimingWindowRepeatPeriodSerializer(data={"seconds": seconds})
    assert s.is_valid() is valid
    if valid:
        assert s.validated_data["seconds"] == seconds
    else:
        assert "seconds" in s.errors


# --- TimingWindowRepeatSerializer --------------------------------------------

@pytest.mark.parametrize("payload, valid, err_field", [
    ({"period": {"seconds": 10}}, True, None),
    ({"period": {"seconds": 10}, "times": None}, True, None),
    ({"period": {"seconds": 10}, "times": 0}, False, "times"),
    ({"period": {"seconds": -5}}, False, "period"),
])
def test_repeat(payload, valid, err_field):
    s = TimingWindowRepeatSerializer(data=payload)
    assert s.is_valid() is valid
    if not valid and err_field:
        # could be nested under period -> seconds depending on your validation
        assert err_field in json.dumps(s.errors)


# --- TimingWindowEndSerializer -----------------------------------------------

@pytest.mark.parametrize("payload, valid, err_key", [
    ({"atUtc": "2025-01-01T00:00"}, True, None),
    ({"after": {"seconds": 10}}, True, None),
    ({"after": {"seconds": 10}, "repeat": {"period": {"seconds": 5}}}, True, None),
    ({"after": {"seconds": 10}, "repeat": None}, True, None),
    ({"atUtc": "2025-01-01T00:00", "repeat": None}, True, None),
    ({"atUtc": "2025-01-01T00:00", "after": {"seconds": 10}}, False, "non_field_errors"),
    ({}, False, "non_field_errors"),
    ({"repeat": {"period": {"seconds": 10}}}, False, "non_field_errors"),
])
def test_end(payload, valid, err_key):
    s = TimingWindowEndSerializer(data=payload)
    assert s.is_valid() is valid
    if not valid:
        assert err_key in s.errors


# --- TimingWindowSerializer ---------------------------------------------------

@pytest.mark.parametrize("end, valid, err_field", [
    ({"atUtc": "2025-01-01T11:00"}, True, None),
    (None, True, None),
    ({"atUtc": "2025-01-01T09:59"}, False, "end"),
])
def test_window(end, valid, err_field):
    data = make_window(
        inclusion=TimingWindowInclusion.INCLUDE.value,
        start="2025-01-01T10:00",
        end=end,
    )
    s = TimingWindowSerializer(data=data)
    assert s.is_valid() is valid
    if valid:
        # presence/absence of end
        if end is None:
            assert s.validated_data.get("end") in (None, {})
        else:
            assert "end" in s.validated_data
    else:
        assert err_field in s.errors


# --- SchedulingWindowsSerializer.to_internal_value ---------------------------

@pytest.mark.parametrize("payload, valid", [
    ('[{"inclusion":"INCLUDE","startUtc":"2025-01-01T00:00","end":{"atUtc":"2025-01-01T01:00"}}]', True),
    ("[not-json", False),
])
def test_to_internal_value_json(payload, valid):
    serializer = SchedulingWindowsSerializer(data={"timingWindows": payload})
    if valid:
        assert serializer.is_valid(), serializer.errors
        tw = serializer.validated_data["timingWindows"]
        assert isinstance(tw, list) and len(tw) == 1
    else:
        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)


# --- SchedulingWindowsSerializer.format_gpp ----------------------------------

def test_format_gpp_basic():
    payload = (
        '[{"inclusion":"INCLUDE","startUtc":"2025-01-01T00:00",'
        '"end":{"atUtc":"2025-01-01T01:00"}}]'
    )
    serializer = SchedulingWindowsSerializer(data={"timingWindows": payload})
    serializer.is_valid(raise_exception=True)

    out = serializer.format_gpp()
    assert isinstance(out, list) and len(out) == 1
    item = out[0]
    assert item["inclusion"] == "INCLUDE"
    assert "start_utc" in item
    assert "end" in item
