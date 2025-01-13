"""Module to serialize DRAGONSRun processed files."""

__all__ = ["DRAGONSProcessedFilesSerializer"]

from pathlib import Path

from django.core.files.storage import default_storage
from rest_framework import serializers

from goats_tom.models import DRAGONSRun


class DRAGONSProcessedFilesSerializer(serializers.ModelSerializer):
    """Serializer for the processed files from a DRAGONS run.

    Attributes
    ----------
    files : `serializers.SerializerMethodField`
        A field that gets a list of processed files from the `DRAGONSRun` instance.
    """

    files = serializers.SerializerMethodField()
    filename = serializers.CharField(
        write_only=True,
        max_length=255,
        help_text="Filename of the file to remove.",
        required=True,
    )
    filepath = serializers.CharField(
        write_only=True,
        max_length=255,
        help_text="Filepath of the file to remove.",
        required=True,
    )
    action = serializers.ChoiceField(
        choices=["remove"],
        write_only=True,
        help_text="Actions to perform to the processed files.",
        required=True,
    )
    product_id = serializers.CharField(
        write_only=True,
        max_length=255,
        help_text="Product ID of the file.",
        required=True,
    )

    def get_files(self, obj: DRAGONSRun) -> list[dict[str, str]]:
        """Retrieves a list of files from the processed directory.

        Parameters
        ----------
        obj : `DRAGONSRun`
            The instance of `DRAGONSRun` from which to retrieve files.

        Returns
        -------
        `list[dict[str, str]]`
            A list of dictionaries of information about a file.
        """
        return obj.get_processed_files()

    def validate(self, data):
        f = Path(data["filepath"]) / data["filename"]
        if not default_storage.exists(f):
            raise serializers.ValidationError("File does not exist.")
        return data

    class Meta:
        model = DRAGONSRun
        fields = (
            "files",
            "action",
            "filename",
            "product_id",
            "filepath",
        )
        read_only_fields = ("files",)
