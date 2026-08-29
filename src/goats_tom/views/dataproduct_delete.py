"""Deleting a data product, including for superusers.

Superusers are **not** exempt from the delete permission here, which is a
deliberate departure from how they behave everywhere else in GOATS and TOM.

The reasoning is narrow and worth stating so it is not "fixed" later.
Administrators still read everything: `targets_for_user` and guardian both
return every row to a superuser, and that is unchanged. The concern this
addresses is not an administrator seeing too much, it is an administrator
*making a mistake* -- one click on "Delete All" against the wrong
observation, destroying a PI's reduced data with no undo and, for
proprietary GOA data, possibly no way to fetch it again.

This is a guardrail, not a control. Anyone with a Django shell or filesystem
access can still delete anything, and no permission model changes that. What
it removes is the easy, one-click path to destroying somebody else's data by
accident.

When an administrator genuinely needs to delete a PI's data, they run
``python manage.py grant_delete``, which grants the permission per object and
logs who granted what. The extra step is the feature: deletion becomes a
deliberate act with a record, rather than something that can happen by
misreading a page.
"""

__all__ = ["DataProductDeleteView"]

import logging

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import (
    HttpRequest,
    HttpResponseRedirect,
)
from guardian.shortcuts import get_users_with_perms
from tom_dataproducts.views import DataProductDeleteView as BaseDataProductDeleteView

from goats_tom.utils import delete_associated_data_products

logger = logging.getLogger(__name__)


class DataProductDeleteView(BaseDataProductDeleteView):
    def check_permissions(self, request: HttpRequest) -> bool:
        """Check the delete permission, without a superuser bypass.

        Parameters
        ----------
        request : `HttpRequest`
            The request whose user is being checked.

        Returns
        -------
        `bool`
            Falsy when the request may proceed. Guardian's convention for
            this method is inverted -- it returns the 403 *response* on
            failure and `None` on success -- so this returns whatever the
            superclass would.

        Notes
        -----
        `user.has_perm` cannot express this. Django's `ModelBackend` returns
        `True` for any superuser before guardian is ever consulted, so every
        ordinary permission call is already a bypass. The assigned rows have
        to be read directly, which `get_users_with_perms` does without
        special-casing anybody.

        `with_group_users=True` so a grant made to a group counts, matching
        how sharing works everywhere else.

        Left untouched in target-only mode: a desktop install has one user
        who owns everything, and a guardrail against deleting somebody
        else's data has nobody to protect.
        """
        if settings.TARGET_PERMISSIONS_ONLY:
            return super().check_permissions(request)

        obj = self.get_permission_object()
        holders = get_users_with_perms(
            obj,
            only_with_perms_in=["delete_dataproduct"],
            with_group_users=True,
        )
        if request.user.is_authenticated and holders.filter(pk=request.user.pk).exists():
            return None

        if request.user.is_superuser:
            logger.warning(
                "Superuser %s was refused deletion of data product %s. Deletion "
                "is not granted by superuser status; use `manage.py "
                "grant_delete` if this is intended.",
                request.user.username,
                getattr(obj, "product_id", getattr(obj, "pk", obj)),
            )
        # Reuse the superclass to build the 403/redirect, so the response
        # matches every other permission failure in the application.
        return super().check_permissions(request) or PermissionDenied()

    def form_valid(self, form):
        """Method that handles DELETE requests for this view. It performs the
        following actions in order:
        1. Deletes all ``ReducedDatum`` objects associated with the
        ``DataProduct``.
        2. Deletes the file referenced by the ``DataProduct``.
        3. Deletes the ``DataProduct`` object from the database.

        :param form: Django form instance containing the data for the DELETE
        request.
        :type form: django.forms.Form
        :return: HttpResponseRedirect to the success URL.
        :rtype: HttpResponseRedirect
        """
        # Fetch the DataProduct object
        data_product = self.get_object()
        delete_associated_data_products(data_product)

        return HttpResponseRedirect(self.get_success_url())
