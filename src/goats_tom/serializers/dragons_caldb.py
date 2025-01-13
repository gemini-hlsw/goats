"""Module to serialize DRAGONSRun calibration database."""

__all__ = ["DRAGONSCaldbSerializer"]

from django.core.files.uploadedfile import UploadedFile
from rest_framework import serializers

from goats_tom.models import DRAGONSRun


class DRAGONSCaldbSerializer(serializers.ModelSerializer):
    """Serializer for handling actions on the calibration database of DRAGONS runs.

    Attributes
    ----------
    files : `serializers.SerializerMethodField`
        A field that gets a list of files from the `DRAGONSRun` instance.
    filename : `serializers.CharField`
        The name of the file to remove.
    action : `serializers.ChoiceField`
        Specifies the action to be performed on the calibration database.
    file : `serializers.FileField`
        The file object to upload to the calibration database.
    """

    files = serializers.SerializerMethodField()
    filename = serializers.CharField(
        write_only=True,
        max_length=255,
        help_text="Filename of the file to remove.",
        required=False,
    )
    action = serializers.ChoiceField(
        choices=["remove", "add"],
        write_only=True,
        help_text="Actions to perform on the calibration database.",
        required=True,
    )
    file = serializers.FileField(
        write_only=True,
        help_text="Upload a new file to add to calibration database.",
        required=False,
    )

    def get_files(self, obj: DRAGONSRun) -> list[dict[str, str]]:
        """Retrieves a list of files from the calibration database.

        Parameters
        ----------
        obj : `DRAGONSRun`
            The instance of `DRAGONSRun` from which to retrieve files.

        Returns
        -------
        `list[dict[str, str]]`
            A list of dictionaries, each containing 'name' and 'path' of a file.
        """
        return obj.list_caldb_files()

    class Meta:
        model = DRAGONSRun
        fields = ("id", "files", "file", "action", "filename")
        read_only_fields = ("files", "id")

    def validate_filename(self, value: str) -> str:
        """Validate the filename for removal action."""
        action = self.initial_data.get("action")
        if action == "remove" and not value:
            raise serializers.ValidationError("Filename is required for removal.")

        if action == "remove":
            existing_files = self.instance.list_caldb_files()
            if not any(value == f["name"] for f in existing_files):
                raise serializers.ValidationError(
                    "File does not exist in the database."
                )
        return value

    def validate_file(self, value: UploadedFile) -> UploadedFile:
        """Validate the file for add action."""
        action = self.initial_data.get("action")
        if action == "add" and not value:
            raise serializers.ValidationError("File upload is required for adding.")
        return value
