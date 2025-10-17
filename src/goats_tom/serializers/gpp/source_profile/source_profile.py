"""
Serializers for source profiles used in GPP requests.
"""

__all__ = ["SourceProfileSerializer"]

from enum import Enum
from typing import Any

from rest_framework import serializers

from goats_tom.serializers.gpp.source_profile.seds.registry import SEDRegistry, SEDType
from goats_tom.serializers.gpp.utils import normalize


class SourceProfileType(str, Enum):
    """
    Enumeration of supported source profile types. Currently only 'Point' is
    implemented.
    """

    POINT = "point"
    # UNIFORM = "uniform"
    # GAUSSIAN = "gaussian"


class SourceProfileSerializer(serializers.Serializer):
    sedProfileTypeSelect = serializers.ChoiceField(
        choices=[e.value for e in SourceProfileType], required=True, allow_blank=False
    )
    sedTypeSelect = serializers.ChoiceField(
        choices=[e.value for e in SEDType], required=False, allow_blank=True
    )

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate and structure source profile fields.

        Parameters
        ----------
        data : dict[str, Any]
            The raw form input data.

        Returns
        -------
        dict[str, Any]
            The structured GraphQL-ready data for SourceProfileInput.

        Raises
        ------
        serializers.ValidationError
            If any values are invalid or incorrectly formatted.
        """
        # Profile is always provided.
        profile_type = data["sedProfileTypeSelect"]
        sed_type = normalize(data.get("sedTypeSelect"))

        # If no SED type is provided, return None for the SED.
        if sed_type is None:
            return {profile_type: {"bandNormalized": {"sed": None}}}

        # Get nested SED serializer from registry and validate it.
        serializer_class = SEDRegistry.get_serializer(sed_type)

        # Create nested serializer with the same initial data.
        sed_serializer = serializer_class(data=self.initial_data)
        sed_serializer.is_valid(raise_exception=True)

        # Return structured data.
        return {
            profile_type: {"bandNormalized": {"sed": sed_serializer.validated_data}}
        }
