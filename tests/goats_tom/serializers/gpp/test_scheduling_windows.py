import pytest
from rest_framework.exceptions import ValidationError

from goats_tom.serializers.gpp.schedulingWindows import (
    TimingWindowAfterSerializer,
    TimingWindowRepeatPeriodSerializer,
    TimingWindowRepeatSerializer,
    TimingWindowEndSerializer,
    TimingWindowSerializer,
    SchedulingWindowsSerializer,
)
from gpp_client.api.enums import TimingWindowInclusion


#
# TimingWindowAfterSerializer
#

def test_after_seconds_valid():
    s = TimingWindowAfterSerializer(data={"seconds": 10})
    assert s.is_valid()
    assert s.validated_data["seconds"] == 10


def test_after_seconds_invalid_zero():
    s = TimingWindowAfterSerializer(data={"seconds": 0})
    assert not s.is_valid()
    assert "seconds" in s.errors


#
# TimingWindowRepeatPeriodSerializer
#

def test_repeat_period_valid():
    s = TimingWindowRepeatPeriodSerializer(data={"seconds": 3})
    assert s.is_valid()
    assert s.validated_data["seconds"] == 3


def test_repeat_period_invalid_negative():
    s = TimingWindowRepeatPeriodSerializer(data={"seconds": -1})
    assert not s.is_valid()
    assert "seconds" in s.errors


#
# TimingWindowRepeatSerializer
#

def test_repeat_without_times_valid():
    s = TimingWindowRepeatSerializer(
        data={"period": {"seconds": 10}}
    )
    assert s.is_valid()
    assert "times" not in s.validated_data


def test_repeat_times_null_valid():
    s = TimingWindowRepeatSerializer(
        data={"period": {"seconds": 10}, "times": None}
    )
    assert s.is_valid()
    assert s.validated_data["times"] is None


def test_repeat_times_zero_invalid():
    s = TimingWindowRepeatSerializer(
        data={"period": {"seconds": 10}, "times": 0}
    )
    assert not s.is_valid()
    assert "times" in s.errors


#
# TimingWindowEndSerializer
#

def test_end_invalid_both_at_and_after():
    s = TimingWindowEndSerializer(
        data={
            "atUtc": "2025-01-01T00:00",
            "after": {"seconds": 10},
        }
    )
    assert not s.is_valid()
    assert "non_field_errors" in s.errors


def test_end_invalid_neither_at_nor_after():
    s = TimingWindowEndSerializer(data={})
    assert not s.is_valid()
    assert "non_field_errors" in s.errors


def test_end_invalid_repeat_without_after():
    s = TimingWindowEndSerializer(
        data={"repeat": {"period": {"seconds": 10}}}
    )
    assert not s.is_valid()
    assert "non_field_errors" in s.errors


def test_end_valid_with_atUtc():
    s = TimingWindowEndSerializer(
        data={"atUtc": "2025-01-01T00:00"}
    )
    assert s.is_valid()


def test_end_valid_after_and_repeat():
    s = TimingWindowEndSerializer(
        data={
            "after": {"seconds": 10},
            "repeat": {"period": {"seconds": 5}},
        }
    )
    assert s.is_valid()


def test_end_valid_repeat_null_with_after():
    s = TimingWindowEndSerializer(
        data={"after": {"seconds": 10}, "repeat": None}
    )
    assert s.is_valid()


def test_end_valid_repeat_null_without_after():
    s = TimingWindowEndSerializer(
        data={"atUtc": "2025-01-01T00:00", "repeat": None}
    )
    assert s.is_valid()


#
# TimingWindowSerializer
#

def test_window_invalid_end_before_start():
    s = TimingWindowSerializer(
        data={
            "inclusion": TimingWindowInclusion.INCLUDE.value,
            "startUtc": "2025-01-01T10:00",
            "end": {"atUtc": "2025-01-01T09:59"},
        }
    )
    assert not s.is_valid()
    assert "end" in s.errors


def test_window_valid():
    s = TimingWindowSerializer(
        data={
            "inclusion": TimingWindowInclusion.INCLUDE.value,
            "startUtc": "2025-01-01T10:00",
            "end": {"atUtc": "2025-01-01T11:00"},
        }
    )
    assert s.is_valid()
    assert "end" in s.validated_data


def test_window_valid_without_end():
    s = TimingWindowSerializer(
        data={
            "inclusion": TimingWindowInclusion.INCLUDE.value,
            "startUtc": "2025-01-01T10:00",
        }
    )
    assert s.is_valid()
    assert s.validated_data.get("end") in (None, {})


#
# SchedulingWindowsSerializer.to_internal_value
#

def test_to_internal_value_parses_json_string():
    payload = (
        '[{"inclusion": "INCLUDE", '
        '"startUtc": "2025-01-01T00:00", '
        '"end": {"atUtc": "2025-01-01T01:00"}}]'
    )
    serializer = SchedulingWindowsSerializer(
        data={"timingWindows": payload}
    )

    # If this fails, check the DateTimeField input formats.
    assert serializer.is_valid()
    assert isinstance(serializer.validated_data["timingWindows"], list)
    assert len(serializer.validated_data["timingWindows"]) == 1


def test_to_internal_value_invalid_json():
    serializer = SchedulingWindowsSerializer(
        data={"timingWindows": "[not-json"}
    )
    with pytest.raises(ValidationError):
        serializer.is_valid(raise_exception=True)


#
# SchedulingWindowsSerializer.format_gpp
#

def test_format_gpp_basic():
    payload = (
        '[{"inclusion": "INCLUDE", '
        '"startUtc": "2025-01-01T00:00", '
        '"end": {"atUtc": "2025-01-01T01:00"}}]'
    )
    serializer = SchedulingWindowsSerializer(
        data={"timingWindows": payload}
    )

    serializer.is_valid(raise_exception=True)
    out = serializer.format_gpp()

    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0]["inclusion"] == "INCLUDE"
    assert "start_utc" in out[0]
    assert "end" in out[0]

