"""
Serializer for GPP scheduling windows constraint data.
"""

__all__ = ["SchedulingWindowsSerializer"]

import json
from typing import Any

from gpp_client.api.enums import TimingWindowInclusion
from gpp_client.api.input_types import TimingWindowInput
from rest_framework import serializers

from ._base_gpp import _BaseGPPSerializer


class TimingWindowAfterSerializer(serializers.Serializer):
    """
    Serializer for the 'after' component of a timing window end.
    """

    seconds = serializers.FloatField()

    def validate_seconds(self, value: float) -> float:
        """
        Ensure seconds is strictly positive.
        """
        if value <= 0:
            raise serializers.ValidationError("must be a positive number.")
        return value


class TimingWindowRepeatPeriodSerializer(serializers.Serializer):
    """
    Serializer for the 'period' component inside 'repeat'.
    """

    seconds = serializers.FloatField()

    def validate_seconds(self, value: float) -> float:
        """
        Ensure period seconds is strictly positive.
        """
        if value <= 0:
            raise serializers.ValidationError("must be a positive number.")
        return value


class TimingWindowRepeatSerializer(serializers.Serializer):
    """
    Serializer for the 'repeat' component of a timing window end.
    """

    period = TimingWindowRepeatPeriodSerializer()
    times = serializers.IntegerField(required=False, min_value=1, allow_null=True)

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate the repeat structure.
        """
        # Nothing special beyond field-level validation at the moment.
        # This hook is here for future semantics if needed.
        return data


class TimingWindowEndSerializer(serializers.Serializer):
    """
    Serializer for the 'end' component of a timing window.
    """

    atUtc = serializers.DateTimeField(required=False)
    after = TimingWindowAfterSerializer(required=False)
    repeat = TimingWindowRepeatSerializer(
        required=False,
        allow_null=True,
    )

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Ensure either 'atUtc' or 'after' is present (but not both),
        and that 'repeat', if present, is semantically consistent.
        """
        has_at = "atUtc" in data
        has_after = "after" in data

        if has_at and has_after:
            raise serializers.ValidationError(
                "Specify either 'atUtc' or 'after', not both."
            )

        if not has_at and not has_after:
            raise serializers.ValidationError(
                "End must contain either 'atUtc' or 'after'."
            )
        # If repeat is present (not null), it only makes sense with 'after'
        repeat = data.get("repeat")
        if repeat is not None and not has_after:
            raise serializers.ValidationError(
                "Repeat can only be used together with 'after'."
            )

        return data


class TimingWindowSerializer(serializers.Serializer):
    """
    Serializer for a single GPP timing window entry.
    """

    inclusion = serializers.ChoiceField(
        choices=[c.value for c in TimingWindowInclusion],
        required=True,
        allow_blank=False,
        allow_null=False,
    )
    startUtc = serializers.DateTimeField(required=True)
    end = TimingWindowEndSerializer(required=False, allow_null=True)

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Cross-field validation for a single timing window.
        Enforces consistency between 'startUtc' and 'end.atUtc'.
        """
        start_utc = data.get("startUtc")
        end = data.get("end")

        if end is None:
            return data

        at_utc = end.get("atUtc")
        if start_utc is not None and at_utc is not None:
            if at_utc <= start_utc:
                raise serializers.ValidationError(
                    {"end": {"atUtc": "End must be after the start time."}}
                )

        return data


class SchedulingWindowsSerializer(_BaseGPPSerializer):
    """
    Serializer for the collection of GPP scheduling windows constraint data.
    """

    timingWindows = TimingWindowSerializer(many=True, required=False)

    pydantic_model = TimingWindowInput

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize 'timingWindows' so that DRF always sees a list, even if
        it comes as a JSON string from FormData.

        Parameters
        ----------
        data : dict[str, Any]
            Raw input data (e.g., from request.data).

        Returns
        -------
        dict[str, Any]
            Normalized data ready for standard DRF processing.
        """

        timing_windows_str = data.get("timingWindows")

        try:
            timing_windows_list = json.loads(timing_windows_str)
        except json.JSONDecodeError:
            raise serializers.ValidationError(
                {"timingWindows": "Invalid JSON for timing Windows."}
            )

        data["timingWindows"] = timing_windows_list

        return super().to_internal_value(data)

    def format_gpp(self) -> list[dict[str, Any]] | None:
        """
        Format the validated scheduling windows data for GPP.

        Returns
        -------
        list[dict[str, Any]] | None
            The formatted scheduling windows payload for GPP, or ``None`` if
            there are no windows.
        """
        windows_data = self.validated_data.get("timingWindows")
        if not windows_data:
            return []

        windows_for_gpp: list[dict[str, Any]] = []

        for win in windows_data:
            tw = TimingWindowInput(
                inclusion=TimingWindowInclusion(win["inclusion"]),
                startUtc=win["startUtc"],
                end=win.get("end"),
            )
            windows_for_gpp.append(tw.model_dump(exclude_none=True))

        return windows_for_gpp
