"""Viewset for retagging the `data_product_type` of an existing `DataProduct`."""

__all__ = ["DataProductTypeViewSet"]

from django.conf import settings
from guardian.shortcuts import get_objects_for_user
from rest_framework import mixins, permissions
from rest_framework.viewsets import GenericViewSet
from tom_dataproducts.models import DataProduct

from goats_tom.serializers import DataProductTypeUpdateSerializer


class DataProductTypeViewSet(mixins.UpdateModelMixin, GenericViewSet):
    """Allows updating just the `data_product_type` of a `DataProduct`.

    Restricted to the data products the requesting user already has permission
    to view, matching `tom_dataproducts.api_views.DataProductViewSet`.
    """

    queryset = DataProduct.objects.all()
    serializer_class = DataProductTypeUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]
    # Only PATCH is used by the frontend; don't expose an untested PUT.
    http_method_names = ["patch", "head", "options"]

    def get_queryset(self):
        if settings.TARGET_PERMISSIONS_ONLY:
            return super().get_queryset()
        return get_objects_for_user(
            self.request.user,
            "tom_dataproducts.view_dataproduct",
            klass=super().get_queryset(),
        )
