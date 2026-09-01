"""Module to override the TOMToolkit `DataProductViewSet` for DRAGONS-specific data
product management.
This module customizes the `DataProductViewSet` to integrate with the DRAGONS run
system, adapting the way data products are created to accommodate file paths instead of
direct file uploads.
"""

__all__ = ["DataProductsViewSet", "GOATSDataProductViewSet"]
from datetime import datetime

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
from goats_tom.permissions import (
    DataProductObjectPermissions,
    has_assigned_perm,
)
from goats_tom.serializers import DataProductSerializer


class GOATSDataProductViewSet(BaseDataProductViewSet):
    """Upstream's data product API, with the missing permission check.

    Notes
    -----
    Registered under the ``dataproducts`` basename so that it, and not
    `tom_dataproducts.api_views.DataProductViewSet`, serves
    ``/api/dataproducts/``. `SharedAPIRootRouter` refuses a second
    registration of a basename it already holds, and `goats_tom.urls` is
    included before `tom_common.urls`, so registering here wins and
    upstream's registration is declined.

    Upstream's viewset carries `DestroyModelMixin` and declares only
    ``view_dataproduct``, which `PermissionListMixin` uses to filter the
    *list*. Nothing checked the object on delete, and GOATS sets
    ``DEFAULT_PERMISSION_CLASSES`` to an empty list, so the endpoint had no
    permission check at all: any authenticated user could destroy any file
    they could see, and a superuser can see everything. This was the reason
    the delete guardrail added to `DataProductDeleteView` and
    `DeleteObservationDataProductsView` had no effect on the live instance
    -- the ban was never in this path.

    Everything else -- create, list, serializer, filters -- is upstream's,
    unchanged.
    """

    permission_classes = [DataProductObjectPermissions]


class DataProductsViewSet(BaseDataProductViewSet):
    """Overrides the TOMToolkit view set to handle custom creation."""

    parser_classes = [JSONParser]
    # Same hole as `GOATSDataProductViewSet` closes: this subclass inherits
    # `DestroyModelMixin` too, and is routed at `dragonsdataproducts`.
    permission_classes = [DataProductObjectPermissions]

    def get_serializer_class(self):
        if self.action == "create":
            return DataProductSerializer
        return super().get_serializer_class()

    def create(self, request, *args, **kwargs):
        file_status = request.data.get("file_status")

        if file_status == "new":
            # Directly invoke CreateModelMixin's create method to avoid the custom logic
            mixin_method = CreateModelMixin.create.__get__(self, self.__class__)
            response = mixin_method(request, *args, **kwargs)

            if response.status_code == status.HTTP_201_CREATED:
                response.data["message"] = "Data product successfully uploaded."
                dp = DataProduct.objects.get(pk=response.data["id"])

                # Add the metadata.
                # NOTE: Instead of opening with astrodata and checking for prepared or
                # processed tags, we assume it is processed. This api endpoint is for
                # DRAGONS reduction, only Gemini data will be here and only processed
                # files will appear in the run directory.
                DataProductMetadata.objects.create(dataproduct=dp, processed=True)

                try:
                    run_hook("data_product_post_upload", dp)
                    reduced_data = run_data_processor(dp)
                    if not settings.TARGET_PERMISSIONS_ONLY:
                        for group in response.data.get("group", []):
                            assign_perm("tom_dataproducts.view_dataproduct", group, dp)
                            assign_perm(
                                "tom_dataproducts.delete_dataproduct", group, dp
                            )
                            assign_perm(
                                "tom_dataproducts.view_reduceddatum",
                                group,
                                reduced_data,
                            )

                except Exception:
                    ReducedDatum.objects.filter(data_product=dp).delete()
                    dp.delete()
                    return Response(
                        {
                            "error": "Data processing error",
                            "detail": "There was an error in processing your "
                            "DataProduct into individual ReducedDatum objects.",
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

            return response
        elif file_status == "updated":
            try:
                product_id = request.data.get("productId")
                last_modified = request.data.get("last_modified")
                dp = DataProduct.objects.get(product_id=product_id)

                # `product_id` comes from the request body and was looked up
                # across the whole table with nothing checked, while the
                # branch below deletes every `ReducedDatum` derived from the
                # file and re-runs the processor. Any authenticated user
                # could therefore wipe another PI's reduced data by naming
                # their product_id.
                #
                # Change rather than delete, matching
                # `DataProductTypeViewSet`: this is a write to the file's
                # derived data, and destroying it follows from the write the
                # same way retagging away from photometry does. Full access
                # grants change, so a collaborator trusted to reduce the
                # observation can still refresh its files.
                if not settings.TARGET_PERMISSIONS_ONLY and not has_assigned_perm(
                    request.user, dp, ["change_dataproduct"]
                ):
                    return Response(
                        {
                            "error": "Permission denied",
                            "detail": "You do not have permission to update "
                            "this data product.",
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

                if last_modified:
                    try:
                        dp.modified = datetime.fromisoformat(
                            last_modified.replace("Z", "+00:00")
                        )
                        dp.save(update_fields=["modified"])
                    except Exception:
                        pass

                try:
                    ReducedDatum.objects.filter(data_product=dp).delete()
                    run_hook("data_product_post_upload", dp)
                    run_data_processor(dp)

                except Exception:
                    ReducedDatum.objects.filter(data_product=dp).delete()
                    return Response(
                        {"error": "Data processing error"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                return Response(
                    {"message": "Data product successfully updated."},
                    status=status.HTTP_200_OK,
                )

            except DataProduct.DoesNotExist:
                return Response(
                    {"error": "DataProduct not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            except Exception as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        else:
            return Response(
                {"error": f"Invalid file_status: {file_status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
