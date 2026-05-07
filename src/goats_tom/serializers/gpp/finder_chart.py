from rest_framework import serializers

__all__ = [
    "FinderChartsSerializer",
]


class FinderChartFileSerializer(serializers.Serializer):
    """
    Serializer for a single finder chart file.

    Validates basic metadata and enforces file constraints such as size and
    allowed extensions.
    """

    description = serializers.CharField(required=False, allow_blank=True, default="")
    file = serializers.FileField()

    MAX_BYTES = 10 * 1024 * 1024
    ALLOWED_EXT = {"png", "jpg", "jpeg"}

    def validate_file(self, f):
        """
        Validate uploaded file.

        Parameters
        ----------
        f : File
            Uploaded finder chart file.

        Returns
        -------
        File
            The validated file.

        Raises
        ------
        serializers.ValidationError
            If file size exceeds limit or extension is invalid.
        """
        size = getattr(f, "size", None)

        if size is not None and size > self.MAX_BYTES:
            size_mb = size / (1024 * 1024)
            max_mb = self.MAX_BYTES / (1024 * 1024)

            raise serializers.ValidationError(
                f"File too large ({size_mb:.2f} MB). "
                f"Maximum allowed size is {max_mb:.0f} MB."
            )

        name = (getattr(f, "name", "") or "").lower()
        ext = name.rsplit(".", 1)[-1] if "." in name else "unknown"

        if ext not in self.ALLOWED_EXT:
            raise serializers.ValidationError(
                f"Invalid file type '.{ext}'. "
                f"Allowed formats: {', '.join(sorted(self.ALLOWED_EXT))}."
            )

        return f


class FinderChartsSerializer(serializers.Serializer):
    """
    Serializer for grouped finder chart operations.

    This serializer validates a batch of finder chart changes, including
    new uploads and deletions, ensuring the payload structure is correct
    before processing.

    Parameters
    ----------
    toAdd : list of dict, optional
        Finder charts to upload. Each item must include:
        - description : str
        - file : UploadedFile

    toDelete : list of str, optional
        Attachment IDs to delete.
    """

    toAdd = FinderChartFileSerializer(many=True, required=False, default=list)
    toDelete = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )

    def to_internal_value(self, data):
        """
        Extract and deserialize finder chart data.

        Parameters
        ----------
        data : dict
            Raw input data. It may be either the full observation payload or
            the ``finderCharts`` object itself.

        Returns
        -------
        dict
            Validated finder chart data.
        """
        if "finderCharts" in data:
            data = data.get("finderCharts") or {}

        return super().to_internal_value(data)
