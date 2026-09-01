__all__ = ["TargetDeleteView"]
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.forms import Form
from django.http import (
    HttpResponse,
)
from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationRecord
from tom_targets.views import TargetDeleteView as BaseTargetDeleteView

from goats_tom.antares_target_save import target_saver_usernames
from goats_tom.permissions import (
    may_delete_target,
    target_is_public,
    undeletable_dataproducts,
)
from goats_tom.utils import delete_associated_data_products


class TargetDeleteView(BaseTargetDeleteView):
    def form_valid(self, form: Form) -> HttpResponse:
        """Handle deletion of associated observation records upon valid form
        submission.

        Parameters
        ----------
        form : `Form`
            The form object.

        Returns
        -------
        `HttpResponse`
            HTTP response indicating the outcome of the deletion process.

        """
        target = self.get_object()

        # Checked before anything is torn down. A shared target is refused by
        # `goats_tom.signals.block_shared_target_deletion` as a backstop, but
        # that fires at delete time -- by which point the loop below has
        # already destroyed the observation records. Refusing here keeps them.
        savers = target_saver_usernames(target)
        if len(savers) > 1:
            # Refused the same way as the two checks below, even though the
            # reason differs: this one is not about what the user may do --
            # they may well hold delete on the target -- but about what
            # deleting it would do to the other teams holding it.
            #
            # Consistency wins over that distinction. Three refusals on one
            # button that behave three ways teach nobody anything, and a
            # user who is stopped needs to know they were stopped and why,
            # which the banner on the Access Denied page carries either way.
            reason = (
                f"{target.name} is shared by {len(savers)} teams "
                f"({', '.join(savers)}) and cannot be deleted. Deleting it "
                f"would remove it from all of them."
            )
            messages.error(self.request, reason)
            raise PermissionDenied(reason)

        # Asked about the target, not about the files hanging off it.
        #
        # This previously refused only when the target carried data products
        # the user could not delete, which was the wrong question in the
        # wrong words: a target with no files was deletable by anyone, and
        # the refusal that did fire talked about data product counts on a
        # page where somebody had asked to delete a target. Upstream scopes
        # this view with `targets_for_user(..., 'delete_target')`, which
        # returns everything to a superuser, so there was no target-level
        # check at all.
        #
        # See `may_delete_target` for the public-target exception.
        if not may_delete_target(self.request.user, target):
            if target_is_public(target):
                reason = (
                    f"{target.name} is a public target and can only be "
                    "deleted by an administrator."
                )
            else:
                reason = (
                    f"{target.name} belongs to another user and cannot be "
                    "deleted."
                )
            # Raised rather than redirected with a message, so this lands on
            # the same Access Denied page as a refused data product or
            # observation. A refusal that returns you to the object with a
            # red banner reads as a validation error -- something you might
            # correct and retry -- when what happened is that you may not do
            # this at all.
            #
            # The message goes out alongside it because `403.html` extends
            # the base template, which renders the message queue: the page
            # says access was denied, and the banner says which target and
            # why.
            messages.error(self.request, reason)
            raise PermissionDenied(reason)

        # Fetch the ObservationRecord object.
        observation_records = ObservationRecord.objects.filter(target=target)

        # Same guardrail as the Delete and Delete All buttons, applied here
        # because this is the widest cascade in the application: deleting a
        # target destroys every observation on it and every file on those
        # observations, across every PI who has one.
        #
        # Upstream scopes this view with `targets_for_user(..., 'delete_target')`,
        # which returns everything to a superuser -- so without this an
        # administrator refused at the per-file and per-observation buttons
        # could still take the lot in one click, which is the exact mistake
        # the guardrail exists to prevent.
        #
        # Filtered on `target`, not on the observation records below.
        # `DataProduct.observation_record` is nullable while
        # `DataProduct.target` is not, and both are `CASCADE` -- so a product
        # with no observation record (an upload with none selected, an
        # ANTARES light curve) is still destroyed by the database when the
        # target goes, and filtering by observation record would have walked
        # straight past exactly the products that have no owner to infer.
        refused = undeletable_dataproducts(
            self.request.user,
            DataProduct.objects.filter(target=target),
        )
        if refused:
            # Also a permission refusal, so also the Access Denied page.
            reason = (
                f"{target.name} holds data belonging to another user, which "
                "deleting it would destroy. Ask them to remove their data "
                "first, or use `manage.py grant_delete`."
            )
            messages.error(self.request, reason)
            raise PermissionDenied(reason)

        for observation_record in observation_records:
            # Delete the observation data products.
            delete_associated_data_products(observation_record)
            # Delete the observation record itself.
            observation_record.delete()

        # Proceed with deletion of the object.
        return super().form_valid(form)
