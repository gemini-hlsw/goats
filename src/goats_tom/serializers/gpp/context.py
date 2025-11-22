"""
Serializer for extracting important information for creating, updating and saving
an observation in GPP and GOATS.
"""

__all__ = ["ContextSerializer"]
from typing import Any

from gpp_client.api.enums import ObservingModeType
from rest_framework import serializers
from tom_targets.models import BaseTarget as Target

from ._base_gpp import _BaseGPPSerializer


class ContextSerializer(_BaseGPPSerializer):
    """
    Serializer for extracting important information for creating, updating and saving
    an observation in GPP and GOATS.
    """

    hiddenGoatsTargetIdInput = serializers.PrimaryKeyRelatedField(
        required=True, allow_null=False, queryset=Target.objects.all()
    )

    hiddenTargetIdInput = serializers.CharField(
        required=True, allow_null=False, allow_blank=False
    )
    hiddenObservationIdInput = serializers.CharField(
        required=True, allow_blank=False, allow_null=False
    )
    hiddenObservingModeInput = serializers.ChoiceField(
        choices=[m.value for m in ObservingModeType],
        required=True,
        allow_blank=False,
        allow_null=False,
    )
    hiddenReferenceLabelInput = serializers.CharField(
        required=True, allow_blank=False, allow_null=False
    )

    @property
    def gpp_observation_reference_label(self) -> str:
        """
        Get the GPP observation reference label.

        Returns
        -------
        str
            The GPP observation reference label.
        """
        return self.validated_data["hiddenReferenceLabelInput"]

    @property
    def goats_target(self) -> Target:
        """
        Get the Target instance.

        Returns
        -------
        Target
            The Target instance.
        """
        return self.validated_data["hiddenGoatsTargetIdInput"]

    @property
    def gpp_target_id(self) -> str:
        """
        Get the GPP target ID.

        Returns
        -------
        str
            The GPP target ID.
        """
        return self.validated_data["hiddenTargetIdInput"]

    @property
    def gpp_observation_id(self) -> str:
        """
        Get the GPP observation ID.

        Returns
        -------
        str
            The GPP observation ID.
        """
        return self.validated_data["hiddenObservationIdInput"]

    @property
    def instrument(self) -> str:
        """
        Get the instrument from the observing mode.

        Returns
        -------
        str
            The instrument name.
        """
        return self.validated_data["hiddenObservingModeInput"]

    def format_observation(self) -> dict[str, Any]:
        """
        Format the observation context data for saving to GOATS.

        Returns
        -------
        dict[str, Any]
            The formatted observation context data.
        """
        return {
            "instrument": self.instrument,
            "reference": {
                "label": self.gpp_observation_reference_label,
            },
            "id": self.gpp_observation_id,
        }
