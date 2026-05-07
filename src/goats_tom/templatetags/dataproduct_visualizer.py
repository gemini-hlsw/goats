"""Module for providing the dataproudcts to visualize."""

__all__ = ["dataproduct_visualizer"]

from typing import Any

from django import template
from django.db.models import Q
from django.template.context import RequestContext
from tom_dataproducts.models import DataProduct
from tom_targets.models import BaseTarget

register = template.Library()


@register.inclusion_tag("partials/dataproduct_visualizer.html", takes_context=True)
def dataproduct_visualizer(
    context: RequestContext, target: BaseTarget, data_type: str = "spectroscopy"
) -> dict[str, Any]:
    """Returns the dataproducts available to plot for a specific data type.

    Parameters
    ----------
    context : `RequestContext`
        The template context, including the user and request information.
    target : `BaseTarget`
        The target object for which to retrieve data products.
    data_type : `str`, optional
        The type of data product to filter by, by default "spectroscopy".

    Returns
    -------
    dict[str, Any]
        A dictionary containing the target, the filtered data products, and the data
        type.
    """
    # Get all the dataproducts.
    # FIXME: Add in permission check to only get appropriate dataproducts

    active_filter = Q(data_product_type=data_type)

    if data_type == "spectroscopy":
        active_filter |= Q(data_product_type="fits_file")
        active_filter |= Q(data__iendswith="fits.fz")

    dataproducts = DataProduct.objects.filter(target=target).filter(active_filter)

    return {"target": target, "dataproducts": dataproducts, "data_type": data_type}
