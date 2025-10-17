"""
Black body SED serializer.
"""

__all__ = ["BlackBodySerializer"]

from typing import Any

from rest_framework import serializers

from goats_tom.serializers.gpp.utils import normalize


class BlackBodySerializer(serializers.Serializer):
    sedBlackBodyTempK = serializers.CharField(required=False, allow_blank=True)

    def validate_sedBlackBodyTempK(self, value: str | None) -> int | None:
        """
        Validate black body temperature input.

        Parameters
        ----------
        value : str | None
            The input value to validate.

        Returns
        -------
        int | None
            The validated temperature in Kelvin, or None if not provided.

        Raises
        ------
        serializers.ValidationError
            If the value is not a positive integer.
        """
        # Normalize input.
        value = normalize(value)
        # If normalization returns None, treat it as missing.
        if value is None:
            return None

        try:
            temp = int(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError("Must be a valid integer.")

        if temp <= 0:
            raise serializers.ValidationError("Must be a positive integer (Kelvin).")

        return temp

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate and structure SED fields.

        Parameters
        ----------
        data : dict[str, Any]
            The raw form input data.

        Returns
        -------
        dict[str, Any]
            The structured GraphQL-ready data for SED input.

        Raises
        ------
        serializers.ValidationError
            If any values are invalid or incorrectly formatted.
        """
        return {"blackBodyTempK": data.get("sedBlackBodyTempK")}
