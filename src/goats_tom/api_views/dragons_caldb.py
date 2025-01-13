"""Module that handles the DRAGONS caldb API."""

__all__ = ["DRAGONSCaldbViewSet"]

import bz2

from rest_framework import mixins, permissions
from rest_framework.viewsets import GenericViewSet

from goats_tom.models import DRAGONSRun
from goats_tom.serializers import DRAGONSCaldbSerializer


class DRAGONSCaldbViewSet(
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    """A viewset for updating the `DRAGONSRun` calibration database."""

    queryset = DRAGONSRun.objects.all()
    serializer_class = DRAGONSCaldbSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_serializer_class = None

    def perform_update(self, serializer: DRAGONSCaldbSerializer) -> None:
        """Perform an action on the calibration database based on the serializer's
        validated data.

        Parameters
        ----------
        serializer : `DRAGONSCaldbSerializer`
            The serializer containing validated data for the update.
        """
        action = serializer.validated_data["action"]

        if action == "add":
            file_obj = serializer.validated_data["file"]
            cal_dir = serializer.instance.get_calibrations_uploaded_dir()
            filepath = cal_dir / file_obj.name

            try:
                # Handle .bz2 compressed files.
                if file_obj.name.endswith(".bz2"):
                    unpacked_path = filepath.with_suffix("")  # Remove .bz2 suffix
                    with bz2.BZ2File(file_obj, "rb") as compressed_file:
                        with open(unpacked_path, "wb") as decompressed_file:
                            decompressed_file.write(compressed_file.read())
                    # Update filepath to the decompressed file.
                    filepath = unpacked_path
                else:
                    # Write the uploaded file directly if not compressed.
                    with open(filepath, "wb+") as destination:
                        for chunk in file_obj.chunks():
                            destination.write(chunk)
            except (IOError, PermissionError) as e:
                print(f"Error handling file {file_obj.name}: {e}")
                return

            try:
                # Update the database with the new file.
                serializer.instance.add_caldb_file(filepath)
            except Exception as e:
                print(e)
                pass
            # DRAGONS does not raise an error if it's not valid for use, so need to
            # check if in database and remove if not.
            serializer.instance.clean_caldb_uploaded_files()

        elif action == "remove":
            filename = serializer.validated_data["filename"]
            try:
                # Remove the file from the database.
                serializer.instance.remove_caldb_file(filename)
            except Exception:
                return
