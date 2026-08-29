__all__ = ["DeleteObservationDataProductsView"]
import logging

from django.conf import settings
from django.core.exceptions import PermissionDenied
from guardian.shortcuts import get_users_with_perms
from django.contrib import messages
from django.http import (
    HttpRequest,
    HttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import View
from tom_common.mixins import Raise403PermissionRequiredMixin
from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationRecord

from goats_tom.utils import delete_associated_data_products


logger = logging.getLogger(__name__)


class DeleteObservationDataProductsView(Raise403PermissionRequiredMixin, View):
    """A view for handling the deletion of all data products associated with a
    specific observation.

    This view extends `Raise403PermissionRequiredMixin` to include permission
    checks based on the application's settings.
    """

    template_name = (
        "tom_observations/observationrecord_dataproducts_confirm_delete.html"
    )
    # Share same permission since deleting all data products for observation.
    permission_required = "tom_observations.delete_dataproduct"

    def get_required_permissions(
        self,
        request: HttpRequest | None = None,
    ) -> list[str] | None:
        """Get the required permissions for this view.

        Parameters
        ----------
        request : `HttpRequest`, optional
            The `HttpRequest` object.

        Returns
        -------
        `list[str] | None`
            A list of required permission strings, or ``None`` if custom
            settings apply.

        """
        if settings.TARGET_PERMISSIONS_ONLY:
            # Custom logic based on your application's settings
            return None
        return super().get_required_permissions(request)

    def check_permissions(self, request: HttpRequest) -> bool:
        """Require delete on every data product on this observation.

        Parameters
        ----------
        request : `HttpRequest`
            The `HttpRequest` object.

        Returns
        -------
        `bool`
            Falsy when the request may proceed, following guardian's
            inverted convention for this method.

        Notes
        -----
        Two departures from the superclass, both deliberate.

        **Per object, not model-wide.** Upstream checks the permission with
        no object, so it answers "may this user delete data products in
        general?" rather than "may they delete *these*". Every file on the
        observation is checked, and one they may not delete refuses the
        whole request -- a partial "Delete All" that silently skipped some
        files would be worse than a refusal.

        **No superuser bypass.** This is the single most destructive button
        in the application: one click, every file on an observation, no
        undo, and for proprietary GOA data possibly no way to fetch it
        again. Administrators still read everything; what they lose is the
        ability to destroy a PI's data by misreading a page. `manage.py
        grant_delete --observation <pk>` is the deliberate path when it is
        genuinely needed.

        `user.has_perm` cannot express this, because Django's
        `ModelBackend` returns `True` for a superuser before guardian is
        consulted. The assigned rows are read directly instead.
        """
        if settings.TARGET_PERMISSIONS_ONLY:
            # Custom logic based on your application's settings
            return False

        observation_record = get_object_or_404(
            ObservationRecord, pk=self.kwargs["pk"]
        )
        products = DataProduct.objects.filter(
            observation_record=observation_record
        )
        for product in products:
            holders = get_users_with_perms(
                product,
                only_with_perms_in=["delete_dataproduct"],
                with_group_users=True,
            )
            if not (
                request.user.is_authenticated
                and holders.filter(pk=request.user.pk).exists()
            ):
                if request.user.is_superuser:
                    logger.warning(
                        "Superuser %s was refused bulk deletion on observation "
                        "%s: no delete permission on data product %s. Use "
                        "`manage.py grant_delete` if this is intended.",
                        request.user.username,
                        observation_record.pk,
                        getattr(product, "product_id", product.pk),
                    )
                raise PermissionDenied(
                    "You do not have permission to delete all data products "
                    "for this observation."
                )
        return False

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Handle the GET request to show the confirmation page.

        Parameters
        ----------
        request : `HttpRequest`
            The `HttpRequest` object.
        pk : `int`
            The ID of the observation record.

        Returns
        -------
        `HttpResponse`
            The HttpResponse object rendering the confirmation page.

        """
        observation_record = get_object_or_404(ObservationRecord, pk=pk)
        context = {
            "object": observation_record,
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Handle the POST request to delete data products.

        Parameters
        ----------
        request : `HttpRequest`
            The `HttpRequest` object.
        pk : `int`
            The ID of the observation record.

        Returns
        -------
        `HttpResponse`
            Redirects to the observation detail page after deletion.

        """
        observation_record = get_object_or_404(ObservationRecord, pk=pk)
        try:
            delete_associated_data_products(observation_record)
            messages.success(request, "Data products deleted successfully.")
        except Exception as e:
            messages.error(request, f"Error during deletion: {e}")

        return redirect(reverse("tom_observations:detail", args=[pk]))
