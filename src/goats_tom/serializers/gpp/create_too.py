"""
Serializer for extracting important information for creating a TOO (Target of
Opportunity) in GPP.
"""

__all__ = ["CreateTooSerializer"]

from rest_framework import serializers
from tom_targets.models import BaseTarget as Target

from ._base_gpp import _BaseGPPSerializer


class CreateTooSerializer(_BaseGPPSerializer):
    """
    Serializer for extracting important information for creating a TOO in GPP.
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

    @property
    def goats_target(self) -> Target:
        """
        Get the Target instance for the clone operation.

        Returns
        -------
        Target
            The Target instance.
        """
        return self.validated_data["hiddenGoatsTargetIdInput"]

    @property
    def gpp_target_id(self) -> str:
        """
        Get the GPP target ID for the clone operation.

        Returns
        -------
        str
            The GPP target ID.
        """
        return self.validated_data["hiddenTargetIdInput"]

    @property
    def gpp_observation_id(self) -> str:
        """
        Get the GPP observation ID for the clone operation.

        Returns
        -------
        str
            The GPP observation ID.
        """
        return self.validated_data["hiddenObservationIdInput"]
