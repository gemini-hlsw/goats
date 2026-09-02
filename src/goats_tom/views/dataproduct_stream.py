"""Serving a data product's bytes when they are not on this machine's disk.

`VOSpaceStorage.url` returns ``/dataproducts/stream/<name>``, and this is
what answers it. Locally nothing routes here at all: `FileSystemStorage`
returns a ``MEDIA_URL`` path and the file is served straight off disk, as it
always has been.

Why not link straight to Data Lab
---------------------------------
Two reasons, either sufficient.

Their download URLs are **one-shot and expire**, so one written into a
template is dead by the time anybody clicks it -- and a link that leaked
would carry the caller's token with it.

More importantly, a direct link **bypasses the permission check entirely**.
Anyone holding the URL gets the bytes, with no reference to who shared what
with whom. Routing through GOATS keeps `view_dataproduct` in front of the
data, which given the history in *The delete ban* is not a check to hand
away.
"""

__all__ = ["DataProductStreamView"]

import logging

from django.core.exceptions import PermissionDenied, SuspiciousFileOperation
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.views.generic import View
from tom_dataproducts.models import DataProduct

from goats_tom.permissions import has_assigned_perm

logger = logging.getLogger(__name__)


class DataProductStreamView(View):
    """Stream a data product's bytes from wherever they are stored.

    Notes
    -----
    Looks the product up **by its stored name**, not by primary key. The
    name is what the storage backend understands and what
    `VOSpaceStorage.url` had to encode; taking a pk would mean a second
    lookup to recover the name and a second chance for the two to disagree
    about which file is being served.

    Not `LoginRequiredMixin`. Authentication is implied by the permission
    check below -- an anonymous user holds no assigned rows, so
    `has_assigned_perm` refuses them -- and the refusal reaches the Access
    Denied page through `PermissionDeniedMiddleware`, which is where
    refusals are supposed to land.
    """

    def get(self, request: HttpRequest, name: str) -> HttpResponse:
        """Return the file at `name`, if the caller may see it.

        Parameters
        ----------
        request : `django.http.HttpRequest`
            The request.
        name : str
            The data product's storage name, from the URL.

        Returns
        -------
        `django.http.FileResponse`

        Raises
        ------
        `django.http.Http404`
            If no data product has that name, or the bytes are missing.
        `django.core.exceptions.PermissionDenied`
            If the caller lacks `view_dataproduct` on it.
        """
        product = DataProduct.objects.filter(data=name).first()
        if product is None:
            # A 404 rather than a 403, deliberately: the caller has not been
            # told whether a file with this name exists elsewhere, only that
            # GOATS has no record of it.
            logger.info("No data product named %s.", name)
            raise Http404("No such data product.")

        # Codenames without the app label -- guardian's form, and what
        # `has_assigned_perm` expects.
        if not has_assigned_perm(request.user, product, ["view_dataproduct"]):
            # `has_assigned_perm`, not `has_perm`, so a superuser needs an
            # assigned row like anyone else. That matches how the rest of
            # the data product paths behave and keeps one rule rather than
            # two -- see `goats_tom.permissions`.
            logger.warning(
                "%s was refused a stream of data product %s.",
                getattr(request.user, "username", request.user),
                product.pk,
            )
            raise PermissionDenied("You do not have permission to view this file.")

        try:
            handle = default_storage.open(name, "rb")
        except (FileNotFoundError, SuspiciousFileOperation) as exc:
            # A row without bytes. Reachable if a file was removed out of
            # band, or if the name predates the owner prefix that
            # `custom_data_product_path` now adds.
            logger.warning("Data product %s has no file at %s: %s", product.pk, name, exc)
            raise Http404("The file for this data product is missing.") from exc

        # `FileResponse` streams in chunks rather than reading the whole
        # file into memory. FITS files run to hundreds of megabytes, and a
        # handful of concurrent downloads read into memory would take the
        # process down.
        response = FileResponse(handle, as_attachment=True, filename=name.split("/")[-1])
        logger.info(
            "Streaming data product %s to %s.",
            product.pk,
            getattr(request.user, "username", request.user),
        )
        return response
