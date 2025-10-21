"""
Base serializer for GPP serializers.
"""

__all__ = ["_BaseSerializer"]

from typing import Any

from rest_framework import serializers

from .utils import normalize


class _BaseSerializer(serializers.Serializer):
    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize blank strings to ``None`` before standard processing because this is
        form data.

        Parameters
        ----------
        data : dict[str, Any]
            The input data from the form.

        Returns
        -------
        dict[str, Any]
            The normalized internal value dictionary.
        """
        normalized_data = {key: normalize(value) for key, value in data.items()}
        return super().to_internal_value(normalized_data)
