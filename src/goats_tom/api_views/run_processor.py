"""Module that creates the view for running the processor on data."""

__all__ = ["RunProcessorViewSet"]

from django.conf import settings
from django.http import HttpRequest
from guardian.shortcuts import assign_perm
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, mixins
from tom_dataproducts.models import ReducedDatum
from tom_dataproducts.serializers import ReducedDatumSerializer

from goats_tom.processors import run_data_processor
from goats_tom.serializers import RunProcessorSerializer


class RunProcessorViewSet(GenericViewSet, mixins.CreateModelMixin):
    serializer_class = RunProcessorSerializer
    out_serializer_class = ReducedDatumSerializer
    permission_classes = [permissions.IsAuthenticated]

    # FIXME: Hack until tomtoolkit merges in PR
    queryset = ReducedDatum.objects.none()

    def create(self, request: HttpRequest, *args, **kwargs) -> Response:
        """Handle POST request to process a data product and generate reduced data.

        Parameters
        ----------
        request : `HttpRequest`
            The HTTP request object.

        Returns
        -------
        `Response`
            A DRF response object containing the processed data or error information.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data_product = serializer.validated_data["data_product"]
        data_product_type = serializer.validated_data["data_product_type"]
        try:
            reduced_data = run_data_processor(data_product, data_product_type)
            if not settings.TARGET_PERMISSIONS_ONLY:
                # Iterate the groups rather than passing `data_product.group`
                # straight through: it is a many-to-many *manager*, and
                # guardian's `assign_perm` accepts a user, a group, or a
                # queryset of those -- a manager raises. This branch had never
                # run before (GOATS shipped with TARGET_PERMISSIONS_ONLY on),
                # so the error surfaced only as a 400 from the broad
                # `except Exception` below. Matches how
                # `goats_tom.views.dataproduct_upload` already does it.
                for group in data_product.group.all():
                    assign_perm(
                        "tom_dataproducts.view_reduceddatum",
                        group,
                        reduced_data,
                    )
            serialized_reduced_data = self.out_serializer_class(reduced_data, many=True)
            headers = self.get_success_headers(serialized_reduced_data.data)
            return Response(
                serialized_reduced_data.data,
                status=status.HTTP_201_CREATED,
                headers=headers,
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
