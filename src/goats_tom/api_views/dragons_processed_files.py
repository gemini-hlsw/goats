"""Module that handles the DRAGONS processed files."""

__all__ = ["DRAGONSProcessedFilesViewSet"]

import datetime
from pathlib import Path

import astrodata
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from rest_framework import mixins, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from tom_dataproducts.models import DataProduct

from goats_tom import storage
from goats_tom.models import DRAGONSRun
from goats_tom.permissions import undeletable_dataproducts
from goats_tom.scoping import ScopedQuerySetMixin
from goats_tom.serializers import DRAGONSProcessedFilesSerializer, HeaderSerializer
from goats_tom.utils import delete_associated_data_products


class DRAGONSProcessedFilesViewSet(
    ScopedQuerySetMixin,
    mixins.RetrieveModelMixin, GenericViewSet, mixins.UpdateModelMixin
):
    """A viewset for displaying the processed files of a `DRAGONSRun`."""

    # Scoped by the data products being reduced, not by the target.
    # Observation records are shared with collaborators on a target so
    # everyone can see what was triggered; the files stay private to
    # whoever triggered them, and a reduction belongs with its files.
    # See `goats_tom.scoping`.
    dataproduct_path = "observation_record__dataproduct"

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
                        # Scoped to the files this run reduced, not looked up
                        # across the whole table.
                        #
                        # `product_id` arrives in the request body while the
                        # permission check lives on the URL's `DRAGONSRun`,
                        # so the two were never connected: any authenticated
                        # user who could reach any run could name another
                        # PI's product_id here and have it destroyed, files
                        # and reduced data included. Nothing in the UI does
                        # that, which is why it went unseen -- but the
                        # queryset is the only thing standing between a
                        # crafted payload and somebody else's data.
                        dataproduct = DataProduct.objects.get(
                            product_id=product_id,
                            observation_record=serializer.instance.observation_record,
                        )
                        if undeletable_dataproducts(
                            self.request.user, [dataproduct]
                        ):
                            # Belongs to this run and still not the caller's
                            # to destroy -- a read-only recipient of a shared
                            # observation, or an administrator. Sharing
                            # grants view and, at full access, change; never
                            # delete.
                            raise PermissionDenied(
                                "You do not have permission to delete this "
                                "data product."
                            )
                        delete_associated_data_products(dataproduct)
                        # Need to remove from caldb if it is there as well.
                        serializer.instance.check_and_remove_caldb_file(filename)
                    except ObjectDoesNotExist:
                        # Use the instance to remove the file.
                        f = Path(filepath) / filename
                        serializer.instance.remove_file(f)
            except PermissionDenied:
                # Must not be swallowed by the bare `except` below, which
                # returns silently and would turn a refusal into what looks
                # like a successful removal.
                raise
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
        full_path = storage.working_root() / filepath
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
