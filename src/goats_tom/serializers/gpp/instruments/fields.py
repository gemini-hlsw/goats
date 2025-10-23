"""
Module defining custom serializer fields.
"""

__all__ = ["CommaSeparatedFloatField"]


from rest_framework import serializers


class CommaSeparatedFloatField(serializers.Field):
    """Parses a comma-separated list of floats from a string input."""

    def to_internal_value(self, data: str | None) -> list[float] | None:
        """
        Parse a comma-separated string into a list of floats.

        Parameters
        ----------
        data : str | None
            A comma-separated string of float values or ``None``.

        Returns
        -------
        list[float] | None
            Parsed list of floats, or ``None`` if input is ``None``.

        Raises
        ------
        serializers.ValidationError
            If any value cannot be parsed as float.
        """
        if data is None:
            return None

        try:
            return [float(x.strip()) for x in data.split(",") if x.strip()]
        except ValueError as exc:
            raise serializers.ValidationError(f"Invalid float value: {exc}")
