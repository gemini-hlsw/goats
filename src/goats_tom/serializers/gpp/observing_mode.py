"""
Serializer for observing mode input data.
"""

__all__ = ["ObservingModeSerializer"]

from gpp_client.api.enums import ObservingModeType
from rest_framework import serializers

from goats_tom.serializers.gpp.instruments.registry import InstrumentRegistry


class ObservingModeSerializer(serializers.Serializer):
    """
    Serializer for observing mode input data.
    """

    hiddenObservingModeInput = serializers.ChoiceField(
        choices=[c.value for c in ObservingModeType], required=True
    )

    def validate(self, data: dict[str, str]) -> dict[str, str]:
        """
        Validate and structure the observing mode data.

        Parameters
        ----------
        data : dict[str, str]
            The input data containing the observing mode type.

        Returns
        -------
        dict[str, str]
            The structured observing mode data.
        """
        # Observing mode is always provided.
        observing_mode = data["hiddenObservingModeInput"]

        # Get the appropriate instrument serializer from the registry.
        instrument_serializer_class = InstrumentRegistry.get_serializer(observing_mode)
        instrument_serializer = instrument_serializer_class(data=self.initial_data)
        instrument_serializer.is_valid(raise_exception=True)

        # Return the structured data from the instrument serializer.
        return instrument_serializer.validated_data
