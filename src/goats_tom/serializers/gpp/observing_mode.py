"""
Serializer for observing mode input data.
"""

__all__ = ["ObservingModeSerializer"]

from typing import Any

from gpp_client.api.enums import ObservingModeType
from gpp_client.api.input_types import ObservingModeInput
from rest_framework import serializers

from ._base_gpp import _BaseGPPSerializer
from .instruments import InstrumentRegistry


class ObservingModeSerializer(_BaseGPPSerializer):
    """
    Serializer for GPP observing mode input data.
    """

    hiddenObservingModeInput = serializers.ChoiceField(
        choices=[m.value for m in ObservingModeType],
        required=True,
        allow_blank=False,
        allow_null=False,
    )

    pydantic_model = ObservingModeInput

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Deserialize the input data and validate the instrument-specific fields.

        Parameters
        ----------
        data : dict[str, Any]
            The raw input data.

        Returns
        -------
        dict[str, Any]
            The validated and deserialized instrument data.
        """
        internal = super().to_internal_value(data)
        self._instrument = None

        observing_mode = internal["hiddenObservingModeInput"]
        instrument_serializer_class = InstrumentRegistry.get_serializer(observing_mode)

        instrument = instrument_serializer_class(data=data)
        instrument.is_valid(raise_exception=True)
        self._instrument = instrument

        return internal

    def format_gpp(self) -> dict[str, Any] | None:
        """
        Format the observing mode input for GPP.

        Returns
        -------
        dict[str, Any] | None
            The formatted observing mode data, or ``None`` if not available.
        """
        instrument_data = self.instrument.format_gpp()

        if instrument_data is not None:
            # Wrap the instrument data under the appropriate key.
            instrument_key = self.validated_data["hiddenObservingModeInput"].lower()
            instrument_data = {instrument_key: instrument_data}

        return instrument_data if instrument_data else None

    @property
    def instrument(self) -> _BaseGPPSerializer | None:
        """
        Get the validated instrument serializer instance.

        Returns
        -------
        _BaseGPPSerializer | None
            The instrument-specific serializer instance, or ``None`` if not set.
        """
        return getattr(self, "_instrument", None)
