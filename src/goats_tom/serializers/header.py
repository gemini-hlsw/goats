__all__ = ["HeaderSerializer"]

from django.core.files.storage import default_storage
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
        """Validate that the provided filepath exists.

        Notes
        -----
        Asks the storage backend rather than joining onto
        ``settings.MEDIA_ROOT`` and calling `Path.exists`. The value is
        already a storage-relative name, which is what `exists` wants; the
        old form built an absolute local path and so could only ever have
        answered for the control-plane disk.
        """
        if not default_storage.exists(value):
            raise serializers.ValidationError("The specified file does not exist.")
        return value
