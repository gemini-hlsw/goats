"""Module overriding the `filterset_class` to allow us to filter results."""

__all__ = ["ReducedDatumViewSet"]

from tom_dataproducts.api_views import ReducedDatumViewSet as BaseReducedDatumViewSet

from goats_tom.filters import ReducedDatumFilter
from goats_tom.permissions import ReducedDatumObjectPermissions


class ReducedDatumViewSet(BaseReducedDatumViewSet):
    """Upstream's reduced datum API, filtered and permission-checked.

    Notes
    -----
    Upstream carries `DestroyModelMixin` and declares only
    ``view_reduceddatum``, which `PermissionListMixin` uses to filter the
    list and which nothing consults on delete. With
    ``DEFAULT_PERMISSION_CLASSES`` empty, ``DELETE
    /api/reduceddatums/<pk>/`` performed no check at all -- so a read-only
    recipient of a shared observation, or any other authenticated user who
    could see the datum, could destroy another PI's photometry points one
    at a time. Nothing in the GOATS frontend calls it, which is why it went
    unnoticed.

    Governed by the parent data product rather than by rows on the datum --
    see `ReducedDatumObjectPermissions`.
    """

    filterset_class = ReducedDatumFilter
    permission_classes = [ReducedDatumObjectPermissions]
