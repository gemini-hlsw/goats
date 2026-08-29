__all__ = ["DataProductUploadView"]
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from guardian.shortcuts import assign_perm
from tom_common.hooks import run_hook
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.models import DataProduct, ReducedDatum, data_product_path
from tom_dataproducts.views import DataProductUploadView as BaseDataProductUploadView

from goats_tom.processors import run_data_processor
from goats_tom.visibility import visible_observation_records, visible_targets


class DataProductUploadView(BaseDataProductUploadView):
    def get_form(self, *args, **kwargs):
        """Restrict what an upload may be attached to.

        Notes
        -----
        `DataProductUploadForm` declares ``observation_record`` and
        ``target`` as `ModelChoiceField` over ``objects.all()``. Both are
        rendered as hidden inputs, which is why they are easy to overlook --
        but hidden is a statement about rendering, not about what a client
        may post, and for a `ModelChoiceField` the queryset *is* the
        validator. Left unscoped, a crafted POST attaches a file to another
        PI's observation record or target.

        Scoped to view rather than change: uploading a data product does not
        modify the observation record it hangs off, and requiring change
        would stop a collaborator with view access from contributing to a
        shared target -- which is the point of sharing one.
        """
        form = super().get_form(*args, **kwargs)
        if settings.TARGET_PERMISSIONS_ONLY:
            return form
        user = self.request.user
        if "observation_record" in form.fields:
            form.fields["observation_record"].queryset = visible_observation_records(
                user
            )
        if "target" in form.fields:
            form.fields["target"].queryset = visible_targets(user)
        return form

    def form_valid(self, form):
        """
        Override for assigning a product ID to the uploaded data.
        """
        target = form.cleaned_data["target"]
        if not target:
            observation_record = form.cleaned_data["observation_record"]
            target = observation_record.target
        else:
            observation_record = None
        dp_type = form.cleaned_data["data_product_type"]
        data_product_files = self.request.FILES.getlist("files")
        successful_uploads = []
        for f in data_product_files:
            dp = DataProduct(
                target=target,
                observation_record=observation_record,
                data=f,
                data_product_type=dp_type,
            )
            product_id = data_product_path(dp, f)
            dp.product_id = product_id
            dp.save()

            # TODO: Do I need to handle uploading files here with metadata?

            try:
                run_hook("data_product_post_upload", dp)
                reduced_data = run_data_processor(dp)
                if not settings.TARGET_PERMISSIONS_ONLY:
                    # The uploader first, before any group they chose.
                    #
                    # Upstream assigns permissions *only* to the selected
                    # groups, so uploading without picking one produced a file
                    # with no permissions at all -- present on disk and in the
                    # database, and invisible to everyone including the person
                    # who had just uploaded it. That is how photometry
                    # uploaded from the target page vanished from its own
                    # Manage Data tab.
                    for action in ("view", "change", "delete"):
                        assign_perm(
                            f"tom_dataproducts.{action}_dataproduct",
                            self.request.user,
                            dp,
                        )
                    if reduced_data is not None:
                        assign_perm(
                            "tom_dataproducts.view_reduceddatum",
                            self.request.user,
                            reduced_data,
                        )

                    for group in form.cleaned_data["groups"]:
                        assign_perm("tom_dataproducts.view_dataproduct", group, dp)
                        assign_perm("tom_dataproducts.delete_dataproduct", group, dp)
                        assign_perm(
                            "tom_dataproducts.view_reduceddatum", group, reduced_data
                        )
                successful_uploads.append(str(dp))
            except InvalidFileFormatException as iffe:
                dp_name = str(dp)
                ReducedDatum.objects.filter(data_product=dp).delete()
                dp.data.delete(save=False)
                dp.delete()
                messages.error(
                    self.request,
                    f"File format invalid for file {dp_name} -- error was {iffe}",
                )
            except Exception as e:
                dp_name = str(dp)
                ReducedDatum.objects.filter(data_product=dp).delete()
                dp.data.delete(save=False)
                dp.delete()
                messages.error(
                    self.request,
                    (
                        f"There was a problem processing your file: {dp_name} -- Error:"
                        f" {e}"
                    ),
                )
        if successful_uploads:
            messages.success(
                self.request,
                "Successfully uploaded: {0}".format(
                    "\n".join([p for p in successful_uploads])
                ),
            )

        return redirect(form.cleaned_data.get("referrer", "/"))
