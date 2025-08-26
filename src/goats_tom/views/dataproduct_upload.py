__all__ = ["DataProductUploadView"]
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from guardian.shortcuts import assign_perm
from tom_common.hooks import run_hook
from tom_dataproducts.data_processor import run_data_processor
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.models import DataProduct, ReducedDatum, data_product_path
from tom_dataproducts.views import DataProductUploadView as BaseDataProductUploadView


class DataProductUploadView(BaseDataProductUploadView):
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
