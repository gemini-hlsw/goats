"""Module that handles the DRAGONS processed files."""

__all__ = ["DRAGONSProcessedFilesViewSet"]

import datetime
from pathlib import Path

import astrodata
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from rest_framework import mixins, permissions, status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from tom_dataproducts.models import DataProduct

from goats_tom.models import DRAGONSRun
from goats_tom.serializers import DRAGONSProcessedFilesSerializer, HeaderSerializer
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
        """Performs the update action, such as removing a processed file.

        Parameters
        ----------
        serializer : `DRAGONSProcessedFilesSerializer`
            The serializer containing validated data for the update action.

        Raises
        ------
        Exception
            Raised if the file removal process fails.
        """
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

    @action(detail=False, methods=["post"], url_path="header")
    def header(self, request: Request, *args, **kwargs) -> Response:
        """Retrieve the header information of a FITS file.

        Parameters
        ----------
        request : `Request`
            The incoming HTTP request containing the file path.

        Returns
        -------
        `Response`
            A response containing the filename and astrodata descriptors, or an error
            message.
        """
        serializer = HeaderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        filepath = serializer.validated_data["filepath"]
        full_path = Path(settings.MEDIA_ROOT) / filepath
        filename = full_path.name

        try:
            ad = astrodata.open(str(full_path))
        except Exception as e:
            return Response(
                {"error": f"Failed to open FITS file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        descriptors = ad.descriptors
        # Build the astrodata descriptors to save.
        astrodata_descriptors = {}
        for descriptor in descriptors:
            if hasattr(ad, descriptor):
                try:
                    value = getattr(ad, descriptor)()
                    # Check for unsupported types and convert them.
                    if isinstance(value, (datetime.date, datetime.datetime)):
                        # Convert datetime or date to ISO formatted string.
                        value = value.isoformat()
                    elif not isinstance(value, (str, int, float, bool, type(None))):
                        # Convert any other unsupported types to string.
                        value = str(value)
                    astrodata_descriptors[descriptor] = value
                except Exception:
                    pass

        return Response(
            {"filename": filename, "astrodata_descriptors": astrodata_descriptors},
            status=status.HTTP_200_OK,
        )
