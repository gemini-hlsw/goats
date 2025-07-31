__all__ = ["TargetUpdateView"]

import logging

from django.db import transaction
from django.shortcuts import redirect
from tom_targets.forms import (
    TargetExtraFormset,
    TargetNamesFormset,
)
from tom_targets.views import TargetUpdateView as BaseTargetUpdateView

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TargetUpdateView(BaseTargetUpdateView):
    """
    View that doesn't allow changing the name. Overrides the tomtoolkit view.
    """

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not hasattr(self, "original_name"):
            self.original_name = obj.name
        return obj

    @transaction.atomic
    def form_valid(self, form):
        """
        Runs after form validation. Validates and saves the ``TargetExtra`` and
        ``TargetName`` formsets, then calls the superclass implementation of
        ``form_valid``, which saves the ``Target``. If any forms are invalid, rolls back
        the changes.

        Saving is done in this order to ensure that new names/extras are available in
        the ``target_post_save`` hook.
        """
        # Force the name to stay the same
        if form.instance.name != self.original_name:
            print("Attempted name change, reverting back.")
            form.instance.name = self.original_name
        super().form_valid(form)
        extra = TargetExtraFormset(self.request.POST, instance=self.object)
        names = TargetNamesFormset(self.request.POST, instance=self.object)
        if extra.is_valid() and names.is_valid():
            extra.save()
            names.save()
        else:
            form.add_error(None, extra.errors)
            form.add_error(None, extra.non_form_errors())
            form.add_error(None, names.errors)
            form.add_error(None, names.non_form_errors())
            return super().form_invalid(form)
        return redirect(self.get_success_url())
