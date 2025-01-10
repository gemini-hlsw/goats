"""Module that handles the DRAGONS processed files."""

__all__ = ["DRAGONSProcessedFilesViewSet"]

from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from rest_framework import mixins, permissions
from rest_framework.viewsets import GenericViewSet
from tom_dataproducts.models import DataProduct

from goats_tom.models import DRAGONSRun
from goats_tom.serializers import DRAGONSProcessedFilesSerializer
from goats_tom.utils import delete_associated_data_products


class DRAGONSProcessedFilesViewSet(
    mixins.RetrieveModelMixin, GenericViewSet, mixins.UpdateModelMixin
):
    """A viewset for displaying the processed files of a `DRAGONSRun`."""

    queryset = DRAGONSRun.objects.all()
    serializer_class = DRAGONSProcessedFilesSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_serializer_class = None

    def perform_update(self, serializer: DRAGONSProcessedFilesSerializer) -> None:
        action = serializer.validated_data["action"]
        if action == "remove":
            filename = serializer.validated_data["filename"]
            filepath = serializer.validated_data["filepath"]
            product_id = serializer.validated_data["product_id"]

            # Delete the dataproduct if it exists if not use the remove_processed_file.
            try:
                with transaction.atomic():
                    # Check if there is a dataproduct.
                    try:
                        dataproduct = DataProduct.objects.get(product_id=product_id)
                        delete_associated_data_products(dataproduct)
                        # Need to remove from caldb if it is there as well.
                        serializer.instance.check_and_remove_caldb_file(filename)
                    except ObjectDoesNotExist:
                        # Use the instance to remove the file.
                        f = Path(filepath) / filename
                        serializer.instance.remove_file(f)
            except Exception:
                # TODO: Should I return something better?
                return
