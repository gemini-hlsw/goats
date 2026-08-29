"""Viewset for retagging the `data_product_type` of an existing `DataProduct`."""

__all__ = ["DataProductTypeViewSet"]

from django.conf import settings
from django.contrib import messages
from guardian.shortcuts import get_objects_for_user
from rest_framework import mixins, permissions
from rest_framework.viewsets import GenericViewSet
from tom_targets.models import Target
from tom_dataproducts.models import DataProduct, ReducedDatum

from goats_tom.serializers import DataProductTypeUpdateSerializer


class DataProductTypeViewSet(mixins.UpdateModelMixin, GenericViewSet):
    """Allows updating just the `data_product_type` of a `DataProduct`.

    Restricted to the data products the requesting user may **change**.

    Notes
    -----
    Change rather than view, because retagging is a write with consequences
    beyond a label: moving a file away from photometry deletes every
    photometry `ReducedDatum` derived from it, which is destructive and not
    obviously so from the dropdown. A read-only recipient of a shared
    observation can read and download the file; they cannot retag it and
    silently drop the owning PI's photometry points.

    Full access does grant change, so a collaborator trusted to edit the
    observation can retag its files.
    """

    queryset = DataProduct.objects.all()
    serializer_class = DataProductTypeUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]
    # Only PATCH is used by the frontend; don't expose an untested PUT.
    http_method_names = ["patch", "head", "options"]

    def get_queryset(self):
        """Restrict to the data products the requesting user may view.

        Notes
        -----
        The `TARGET_PERMISSIONS_ONLY` branch previously returned the queryset
        **unscoped**, so with that setting at its default any user could
        retag any data product in the database by its id. That mirrors
        `tom_dataproducts.api_views.DataProductViewSet`, which filters by the
        target's view permission in the same branch -- the setting chooses
        *which* permission governs a data product, not whether one does.

        In target-only mode the governing permission is `change_target`:
        there are no per-object data product permissions to consult, and
        somebody who may edit the target may edit what hangs off it.
        """
        if settings.TARGET_PERMISSIONS_ONLY:
            return (
                super()
                .get_queryset()
                .filter(
                    target__in=get_objects_for_user(
                        self.request.user,
                        f"{Target._meta.app_label}.change_target",
                    )
                )
            )
        return get_objects_for_user(
            self.request.user,
            "tom_dataproducts.change_dataproduct",
            klass=super().get_queryset(),
        )

    def perform_update(self, serializer: DataProductTypeUpdateSerializer) -> None:
        """Save the retag, clean up orphaned photometry points, and queue a
        confirmation message.

        Parameters
        ----------
        serializer : DataProductTypeUpdateSerializer
            Validated serializer wrapping the data product being retagged.
        """
        previous_type = serializer.instance.data_product_type
        instance = serializer.save()

        # Retagging away from photometry orphans any photometry ReducedDatum
        # points already derived from this file, so drop them along with the
        # retag rather than leaving stale points behind.
        if previous_type == "photometry" and instance.data_product_type != "photometry":
            ReducedDatum.objects.filter(data_product=instance).delete()

        labels = dict(settings.DATA_PRODUCT_TYPES.values())
        label = labels.get(instance.data_product_type, instance.data_product_type)
        # Rendered by `{% bootstrap_messages %}` after the frontend reloads.
        messages.success(
            self.request, f'Type changed to "{label}".', fail_silently=True
        )
