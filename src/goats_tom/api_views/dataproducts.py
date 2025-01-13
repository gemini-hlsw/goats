"""Module to override the TOMToolkit `DataProductViewSet` for DRAGONS-specific data
product management.

This module customizes the `DataProductViewSet` to integrate with the DRAGONS run
system, adapting the way data products are created to accommodate file paths instead of
direct file uploads.
"""

__all__ = ["DataProductsViewSet"]
from django.conf import settings
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.mixins import CreateModelMixin
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from tom_common.hooks import run_hook
from tom_dataproducts.api_views import DataProductViewSet as BaseDataProductViewSet
from tom_dataproducts.data_processor import run_data_processor
from tom_dataproducts.models import DataProduct, ReducedDatum

from goats_tom.models import DataProductMetadata
from goats_tom.serializers import DataProductSerializer


class DataProductsViewSet(BaseDataProductViewSet):
    """Overrides the TOMToolkit view set to handle custom creation."""

    parser_classes = [JSONParser]

    def get_serializer_class(self):
        if self.action == "create":
            return DataProductSerializer
        return super().get_serializer_class()

    def create(self, request, *args, **kwargs):
        # Directly invoke CreateModelMixin's create method to avoid the custom logic.
        mixin_method = CreateModelMixin.create.__get__(self, self.__class__)
        response = mixin_method(request, *args, **kwargs)
        if response.status_code == status.HTTP_201_CREATED:
            response.data["message"] = "Data product successfully uploaded."
            dp = DataProduct.objects.get(pk=response.data["id"])
            # Add the metadata.
            # NOTE: Instead of opening with astrodata and checking for prepared or
            # processed tags, we assume it is processed. This api endpoint is for
            # DRAGONS reduction, only Gemini data will be here and only processed files
            # will appear in the run directory.
            DataProductMetadata.objects.create(dataproduct=dp, processed=True)
            try:
                run_hook("data_product_post_upload", dp)
                reduced_data = run_data_processor(dp)
                if not settings.TARGET_PERMISSIONS_ONLY:
                    for group in response.data["group"]:
                        assign_perm("tom_dataproducts.view_dataproduct", group, dp)
                        assign_perm("tom_dataproducts.delete_dataproduct", group, dp)
                        assign_perm(
                            "tom_dataproducts.view_reduceddatum", group, reduced_data
                        )
            except Exception:
                ReducedDatum.objects.filter(data_product=dp).delete()
                dp.delete()
                return Response(
                    {
                        "Data processing error": (
                            "There was an error in processing your DataProduct into "
                            "individual ReducedDatum objects."
                        )
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        return response
