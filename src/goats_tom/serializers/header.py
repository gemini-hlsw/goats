__all__ = ["HeaderSerializer"]

from pathlib import Path

from django.conf import settings
from rest_framework import serializers


class HeaderSerializer(serializers.Serializer):
    """Serializer for validating file header retrieval requests."""

    filepath = serializers.CharField(
        max_length=255,
        required=True,
        allow_blank=True,
        help_text="Relative filepath to the FITS file.",
    )

    def validate_filepath(self, value: str) -> str:
        """Validate that the provided filepath exists."""
        full_path = Path(settings.MEDIA_ROOT) / value
        if not full_path.exists():
            raise serializers.ValidationError("The specified file does not exist.")
        return value
