from rest_framework import serializers

__all__ = ["FinderChartUploadSerializer"]


class FinderChartUploadSerializer(serializers.Serializer):
    """
    Serializer for uploading finder chart files.

    This serializer validates the metadata and file associated with a finder
    chart upload request. It enforces constraints on file size and allowed
    file types before the upload is processed.

    Parameters
    ----------
    programId : str
        Identifier of the GPP program associated with the observation.

    observationId : str
        Identifier of the observation where the finder chart will be attached.

    description : str, optional
        Optional text description for the finder chart attachment.

    file : File
        Finder chart file to upload.

    Attributes
    ----------
    MAX_BYTES : int
        Maximum allowed file size in bytes (default: 5 MB).

    ALLOWED_EXT : set of str
        Allowed file extensions for finder chart uploads.

    Raises
    ------
    serializers.ValidationError
        If the uploaded file exceeds the maximum allowed size or if the file
        extension is not among the supported formats.
    """

    programId = serializers.CharField()
    observationId = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True, default="")
    file = serializers.FileField()

    MAX_BYTES = 5 * 1024 * 1024
    ALLOWED_EXT = {"png", "jpg", "jpeg"}

    def validate_file(self, f):
        """
        Validate uploaded finder chart file.

        Ensures that the uploaded file size does not exceed the configured
        limit and that the file extension is among the supported formats.

        Parameters
        ----------
        f : File
            Uploaded finder chart file.

        Returns
        -------
        File
            The validated file object.

        Raises
        ------
        serializers.ValidationError
            If the file exceeds the maximum size or the extension is invalid.
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
