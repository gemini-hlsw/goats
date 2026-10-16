import json

import pytest
from gpp_client.generated.enums import SchedulingMode, TooActivation
from gpp_client.generated.input_types import SchedulingConstraintsInput

from goats_tom.serializers.gpp.scheduling_constraints import (
    SchedulingConstraintsSerializer,
)

WINDOW = {"inclusion": "INCLUDE", "startUtc": "2025-01-01T10:00:00Z"}


def make_data(**overrides) -> dict:
    data = {"timingWindows": json.dumps([WINDOW])}
    data.update(overrides)
    return data


def test_format_gpp_includes_every_constraint() -> None:
    serializer = SchedulingConstraintsSerializer(
        data=make_data(
            tooActivationSelect=TooActivation.NONE.value,
            schedulingModeSelect=SchedulingMode.NO_SPLITTING.value,
        )
    )
    assert serializer.is_valid(), serializer.errors

    formatted = serializer.format_gpp()

    assert formatted["tooActivation"] == "NONE"
    assert formatted["schedulingMode"] == "NO_SPLITTING"
    assert len(formatted["timingWindows"]) == 1
    assert isinstance(serializer.to_pydantic(), SchedulingConstraintsInput)


def test_format_gpp_leaves_out_what_was_not_submitted() -> None:
    serializer = SchedulingConstraintsSerializer(
        data={"timingWindows": "[]"}
    )
    assert serializer.is_valid(), serializer.errors

    assert serializer.format_gpp() == {"timingWindows": []}


@pytest.mark.parametrize("activation", ["RAPID", "INTERRUPTING"])
def test_uninterruptible_activation_rejects_another_mode(activation: str) -> None:
    serializer = SchedulingConstraintsSerializer(
        data=make_data(
            tooActivationSelect=activation,
            schedulingModeSelect=SchedulingMode.UNCONSTRAINED.value,
        )
    )

    assert not serializer.is_valid()
    assert "schedulingModeSelect" in serializer.errors


@pytest.mark.parametrize("mode", [None, "UNINTERRUPTIBLE"])
def test_uninterruptible_activation_accepts_its_mode(mode: str | None) -> None:
    data = make_data(tooActivationSelect=TooActivation.RAPID.value)
    if mode is not None:
        data["schedulingModeSelect"] = mode
    serializer = SchedulingConstraintsSerializer(data=data)

    assert serializer.is_valid(), serializer.errors


def test_invalid_choice_is_rejected() -> None:
    serializer = SchedulingConstraintsSerializer(
        data=make_data(tooActivationSelect="SOMETIMES")
    )

    assert not serializer.is_valid()
    assert "tooActivationSelect" in serializer.errors
