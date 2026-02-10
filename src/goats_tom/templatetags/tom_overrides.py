from datetime import datetime

import plotly.graph_objs as go
from django import template
from django.conf import settings
from django.core.paginator import Paginator
from guardian.shortcuts import get_objects_for_user
from plotly import offline
from tom_dataproducts.models import ReducedDatum
from tom_dataproducts.processors.data_serializers import SpectrumSerializer

register = template.Library()


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
    page = request.GET.get("page_saved")
    paginator = Paginator(data_products["saved"], 25)
    products_page = _define_data_product_type(paginator.get_page(page))
    return {
        "products_page": products_page,
        "observation_record": observation_record,
    }


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
