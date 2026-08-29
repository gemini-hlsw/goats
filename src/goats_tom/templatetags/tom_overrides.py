from datetime import datetime

import plotly.graph_objs as go
from django import forms, template
from django.conf import settings
from django.core.paginator import Paginator
from guardian.shortcuts import get_objects_for_user
from plotly import offline
from tom_dataproducts.forms import DataShareForm
from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_dataproducts.templatetags.dataproduct_extras import (
    dataproduct_list_for_target as tom_dataproduct_list_for_target,
)
from tom_dataproducts.processors.data_serializers import SpectrumSerializer



register = template.Library()


@register.inclusion_tag("partials/dataproduct_type_dropdown.html", takes_context=True)
def dataproduct_type_dropdown(context, product):
    """
    Render an editable dropdown for a product's `data_product_type`, backed by
    `PATCH /api/dataproducttype/<id>/` (see static/js/dataproduct_type.js).
    `data_product_type` has no Django field `choices`, so the label is resolved
    from `settings.DATA_PRODUCT_TYPES`. Products ingested without a type (e.g.
    non-Gemini data) get an empty label so they can still be retagged.
    """
    choices = list(settings.DATA_PRODUCT_TYPES.values())
    labels = dict(choices)
    label = labels.get(product.data_product_type, product.data_product_type) or ""
    # Retagging requires `change_dataproduct`, because moving a file away
    # from photometry deletes the photometry points derived from it. A
    # read-only recipient sees the type as text rather than a dropdown that
    # would 403 -- the API enforces it either way, this is so the interface
    # does not offer an action the user cannot take.
    user = getattr(context.get("request"), "user", None)
    if settings.TARGET_PERMISSIONS_ONLY:
        can_retag = True
    elif user is None:
        can_retag = False
    else:
        can_retag = user.is_superuser or user.has_perm(
            "tom_dataproducts.change_dataproduct", product
        )
    return {
        "product": product,
        "choices": choices,
        "label": label,
        "can_retag": can_retag,
    }


def _define_data_product_type(products):
    """
    Set `data_product_type` on products that do not have one, based on the URL.

    This mutates the product objects in-place and returns the same iterable/page.
    """
    for product in products:
        if getattr(product, "data_product_type", None):
            continue

        url = getattr(getattr(product, "data", None), "url", "")
        if isinstance(url, str) and url.endswith(".fits.fz"):
            product.data_product_type = "fits_file"

    return products


@register.simple_tag
def define_data_product_type(products):
    """
    Template tag helper to pre-compute data_product_type for products in a template.

    Intended for side effects only; renders nothing.
    """
    _define_data_product_type(products)
    return ""


@register.inclusion_tag(
    "tom_dataproducts/partials/saved_dataproduct_list_for_observation.html"
)
def goats_dataproduct_list_for_observation_saved(
    data_products, request, observation_record
):
    """Render the saved data product table for an observation.

    Notes
    -----
    An `inclusion_tag` renders its template against **only** the dictionary
    returned here -- the surrounding page's context is not inherited unless
    the tag declares ``takes_context``. Django then resolves any missing
    variable to the empty string rather than raising, so a control guarded
    by a name this dictionary omits disappears silently, with no error
    anywhere. That is what blocked the sharing UI for so long, and it is
    why `can_edit_observation` is returned here rather than relied upon
    from the page.

    The product list is filtered by view permission. Upstream builds it
    from ``DataProduct.objects.filter(observation_record=...)`` with no
    permission check at all, so anyone who could see the observation could
    see -- and, through the filename links, download -- every file on it.
    Sharing grants the record and its files together, so in normal use this
    filter changes nothing; it matters for records shared before that was
    true, and for any future path that grants sight of an observation
    without its data.
    """
    page = request.GET.get("page_saved")
    user = request.user
    saved = [
        product
        for product in data_products["saved"]
        if user.has_perm("tom_dataproducts.view_dataproduct", product)
    ]
    paginator = Paginator(saved, 25)
    products_page = _define_data_product_type(paginator.get_page(page))
    return {
        "products_page": products_page,
        "observation_record": observation_record,
        # Passed down so nested tags can reach it. An inclusion tag renders
        # against only the dictionary its function returns, so
        # `dataproduct_type_dropdown` -- which needs the user to decide
        # whether to offer a dropdown or plain text -- would otherwise find
        # no request and fall back to read-only for everybody, silently.
        "request": request,
        "can_edit_observation": user.is_superuser
        or user.has_perm(
            "tom_observations.change_observationrecord", observation_record
        ),
    }


@register.inclusion_tag(
    "tom_dataproducts/partials/dataproduct_list_for_target.html", takes_context=True
)
def goats_dataproduct_list_for_target(context, target):
    """Render the Manage Data table for a target.

    Notes
    -----
    Wraps upstream's `dataproduct_list_for_target`, which already scopes the
    product list by `view_dataproduct`, and adds the one thing the template
    needs and upstream does not supply: which of those files the user may
    delete.

    Sharing grants view and, at full access, change -- never delete.
    Destruction stays with the owning PI. Without this, a read-only
    recipient saw a Delete button on every file they had been shared. The
    button did not work -- `DataProductDeleteView` carries guardian's
    `Raise403PermissionRequiredMixin`, which checks the object -- but
    offering an action that 403s is its own kind of wrong, and it invited
    exactly the question of whether the check was there at all.

    Deletable ids are resolved in one query rather than a permission check
    per row, so a target with hundreds of files does not turn the table
    into hundreds of queries.
    """
    result = tom_dataproduct_list_for_target(context, target)
    user = context["request"].user
    products = result["products"]
    if settings.TARGET_PERMISSIONS_ONLY:
        deletable = {product.pk for product in products}
    else:
        deletable = set(
            get_objects_for_user(
                user,
                "tom_dataproducts.delete_dataproduct",
                klass=DataProduct.objects.filter(
                    pk__in=[product.pk for product in products]
                ),
            ).values_list("pk", flat=True)
        )
    if user.is_superuser:
        deletable = {product.pk for product in products}
    result["products"] = [
        (product, product.pk in deletable) for product in products
    ]
    # Nested tags render against this dictionary alone, so the request has
    # to travel with it -- see the note in
    # `goats_dataproduct_list_for_observation_saved`.
    result["request"] = context["request"]
    return result


@register.inclusion_tag(
    "tom_dataproducts/partials/spectroscopy_for_target.html", takes_context=True
)
def spectroscopy_for_target(context, target, dataproduct=None):
    """
    Override for TOMToolkit method. Drives using the reduceddatum instead of
    dataproduct.
    Renders a spectroscopic plot for a ``Target``. If a ``DataProduct`` is specified,
    it will only render a plot with data associated with that DataProduct.
    """
    # Determine the base queryset of ReducedDatum objects.
    base_query = ReducedDatum.objects.filter(target=target, data_type="spectroscopy")
    if dataproduct:
        # If a specific DataProduct is given, filter by that product.
        base_query = base_query.filter(data_product=dataproduct)

    # Apply permissions if necessary.
    if settings.TARGET_PERMISSIONS_ONLY:
        datums = base_query
    else:
        datums = get_objects_for_user(
            context["request"].user,
            "tom_dataproducts.view_reduceddatum",
            klass=base_query,
        )

    plot_data = []
    for datum in datums:
        deserialized = SpectrumSerializer().deserialize(datum.value)
        plot_data.append(
            go.Scatter(
                x=deserialized.wavelength.value,
                y=deserialized.flux.value,
                name=datetime.strftime(datum.timestamp, "%Y%m%d-%H:%M:%s"),
            )
        )

    layout = go.Layout(
        height=600, width=700, xaxis=dict(tickformat="d"), yaxis=dict(tickformat=".1g")
    )

    return {
        "target": target,
        "plot": offline.plot(
            go.Figure(data=plot_data, layout=layout), output_type="div", show_link=False
        ),
    }


@register.inclusion_tag("tom_dataproducts/partials/recent_photometry.html")
def goats_recent_photometry(target, limit=1):
    """
    Override for TOMToolkit method.
    Displays a table of the most recent photometric points for a target.
    """
    photometry = ReducedDatum.objects.filter(
        data_type="photometry", target=target
    ).order_by("-timestamp")[:limit]
    data = []
    for reduced_datum in photometry:
        rd_data = {"timestamp": reduced_datum.timestamp}
        rd_data["filter"] = reduced_datum.value["filter"]
        if "limit" in reduced_datum.value.keys():
            rd_data["magnitude"] = reduced_datum.value["limit"]
            rd_data["limit"] = True
        else:
            rd_data["magnitude"] = reduced_datum.value["magnitude"]
            rd_data["limit"] = False
        data.append(rd_data)
    target.is_antares = any(n.upper().startswith("ANT") for n in target.names)
    context = {"target": target, "data": data}
    return context


@register.inclusion_tag(
    "tom_dataproducts/partials/photometry_datalist_for_target.html",
    takes_context=True,
)
def get_photometry_data(context, target, target_share=False):
    """
    Displays a table of the all photometric points for a target.
    """
    photometry = ReducedDatum.objects.filter(
        data_type="photometry", target=target
    ).order_by("-timestamp")

    data = []
    for reduced_datum in photometry:
        rd_data = {
            "id": reduced_datum.pk,
            "timestamp": reduced_datum.timestamp,
            "source": reduced_datum.source_name,
            "filter": reduced_datum.value.get("filter", ""),
            "mjd": reduced_datum.value.get("time", ""),
            "telescope": reduced_datum.value.get("telescope", ""),
            "error": reduced_datum.value.get(
                "error", reduced_datum.value.get("magnitude_error", "")
            ),
        }

        if "limit" in reduced_datum.value.keys():
            rd_data["magnitude"] = reduced_datum.value["limit"]
            rd_data["limit"] = True
        else:
            rd_data["magnitude"] = reduced_datum.value["magnitude"]
            rd_data["limit"] = False
        data.append(rd_data)

    initial = {
        "submitter": context["request"].user,
        "target": target,
        "data_type": "photometry",
        "share_title": f"Updated data for {target.name} from "
        f"{getattr(settings, 'TOM_NAME', 'TOM Toolkit')}.",
    }
    form = DataShareForm(initial=initial)
    form.fields["data_type"].widget = forms.HiddenInput()

    sharing = getattr(settings, "DATA_SHARING", None)
    hermes_sharing = sharing and sharing.get("hermes", {}).get("HERMES_API_KEY")

    context = {
        "data": data,
        "target": target,
        "target_data_share_form": form,
        "sharing_destinations": form.fields["share_destination"].choices,
        "hermes_sharing": hermes_sharing,
        "target_share": target_share,
    }
    return context
