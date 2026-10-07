from datetime import datetime, timezone
from operator import attrgetter

import numpy as np
import plotly.graph_objs as go
from astroplan import moon_illumination
from astropy import units as u
from astropy.coordinates import SkyCoord, get_body
from astropy.time import Time
from django import forms, template
from django.conf import settings
from django.core.paginator import Paginator
from guardian.shortcuts import get_objects_for_user
from plotly import offline
from tom_common.templatetags.user_extras import user_list
from tom_dataproducts.forms import DataShareForm
from tom_dataproducts.models import ReducedDatum
from tom_dataproducts.processors.data_serializers import SpectrumSerializer
from tom_dataproducts.templatetags.dataproduct_extras import dataproduct_list_for_target
from tom_observations.templatetags.observation_extras import observation_list
from tom_targets.models import Target
from tom_targets.templatetags.targets_extras import target_table

from goats_tom.views.ordering import date_ordering, resolve_date_order

register = template.Library()


def _photometry_sort_key(row: dict, field: str, descending: bool) -> tuple:
    """Sort key for a photometry row, keeping rows without a value last."""
    value = row.get(field)
    if field == "mjd":
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = None
    present = value is not None and value != ""
    # ``sorted(reverse=True)`` flips the ranks, so missing rows stay last either
    # way; ``id`` keeps rows with the same value in a stable order.
    return (present if descending else not present, value if present else 0, row["id"])


@register.inclusion_tag("partials/dataproduct_type_dropdown.html")
def dataproduct_type_dropdown(product):
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
    return {"product": product, "choices": choices, "label": label}


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
    order = resolve_date_order(request, ("created",), "-created", param="order_saved")
    # ``all_data_products`` returns a plain list, so sort in Python.
    saved = sorted(
        data_products["saved"],
        key=attrgetter(order.removeprefix("-"), "pk"),
        reverse=order.startswith("-"),
    )
    paginator = Paginator(saved, 25)
    products_page = _define_data_product_type(paginator.get_page(page))
    return {
        "products_page": products_page,
        "observation_record": observation_record,
        "request": request,
        "current_order_saved": order,
    }


@register.inclusion_tag(
    "tom_dataproducts/partials/dataproduct_list_for_target.html", takes_context=True
)
def goats_dataproduct_list_for_target(context, target):
    """
    Override for TOMToolkit method. Lists a target's data products newest first.
    """
    context_data = dataproduct_list_for_target(context, target)
    context_data["products"] = context_data["products"].order_by("-created", "-pk")
    # Upstream leaves it out, and the template links to the reader's own
    # credentials page.
    context_data["request"] = context["request"]
    return context_data


@register.inclusion_tag(
    "tom_observations/partials/observation_list.html", takes_context=True
)
def goats_observation_list(context, target=None):
    """
    Override for TOMToolkit method. Lists observations newest first.
    """
    context_data = observation_list(context, target)
    context_data["observations"] = context_data["observations"].order_by(
        "-created", "-pk"
    )
    return context_data


@register.inclusion_tag("tom_targets/partials/target_table.html", takes_context=True)
def goats_target_table(context, targets, all_checked=False):
    """Keep the effective order available inside TOMToolkit's target table."""
    context_data = target_table(context, targets, all_checked)
    context_data["request"] = context["request"]
    context_data["current_order"] = context.get("current_order", "")
    return context_data


@register.inclusion_tag("auth/partials/user_list.html", takes_context=True)
def goats_user_list(context):
    """
    Override for TOMToolkit method. Orders users by join date via ``?order=``,
    and shows an ordinary account only its own row.
    """
    context_data = user_list(context)
    users = context_data["users"]

    # Upstream shows every account's name and email to any logged-in user.
    viewer = getattr(context["request"], "user", None)
    if viewer is None or not viewer.is_authenticated:
        users = users.none()
    elif not viewer.is_superuser:
        users = users.filter(pk=viewer.pk)

    ordering = date_ordering(context["request"], ("date_joined",), "-date_joined")
    context_data["users"] = users.order_by(*ordering)
    context_data["current_order"] = resolve_date_order(
        context["request"], ("date_joined",), "-date_joined"
    )
    return context_data


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
    order = resolve_date_order(
        context["request"], ("timestamp", "mjd"), "-timestamp", param="order_photometry"
    )
    field = order.removeprefix("-")
    descending = order.startswith("-")
    photometry = ReducedDatum.objects.filter(data_type="photometry", target=target)
    if field == "timestamp":
        photometry = photometry.order_by(order, "-pk" if descending else "pk")
    else:
        # MJD values can be strings or numbers; normalize and sort them in Python.
        photometry = photometry.order_by()

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

    if field == "mjd":
        data.sort(
            key=lambda row: _photometry_sort_key(row, field, descending),
            reverse=descending,
        )

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
        "request": context["request"],
        "current_order_photometry": order,
    }
    return context


#: Trace colours, matching the airmass plot next to it (plotly's default colorway).
SEPARATION_COLOR = "#636EFA"
ILLUMINATION_COLOR = "#EF553B"


@register.inclusion_tag("tom_targets/partials/moon_distance.html")
def moon_distance(
    target: Target,
    day_range: int = 30,
    width: int | None = 600,
    height: int = 400,
    background: str | None = None,
    label_color: str | None = None,
    grid: bool = True,
) -> dict[str, str | None]:
    """Plot the Moon's separation from a sidereal target and its illumination.

    Overrides TOM Toolkit's tag of the same name, keeping its signature: real UTC
    dates, labelled traces with a legend and a unified hover.

    Parameters
    ----------
    target : `Target`
        The target to plot.
    day_range : `int`, optional
        Days to plot, starting today (UTC).
    width : `int | None`, optional
        Unused; the plot fills its container. Kept for TOM's signature.
    height : `int`, optional
        Plot height in pixels.
    background : `str | None`, optional
        Background colour; the theme's when not given.
    label_color : `str | None`, optional
        Axis and label colour; the theme's when not given.
    grid : `bool`, optional
        Whether to draw grid lines.

    Returns
    -------
    `dict[str, str | None]`
        The plot's HTML under ``plot``; `None` for non-sidereal targets.
    """
    if target.type != Target.SIDEREAL:
        return {"plot": None}

    start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    times = Time(start) + np.arange(0, day_range, 0.2) * u.day
    dates = times.to_datetime(timezone=timezone.utc)
    separation = (
        get_body("moon", times)
        .separation(SkyCoord(target.ra, target.dec, unit=u.deg))
        .deg
    )
    illumination = moon_illumination(times) * 100

    fig = go.Figure(
        [
            go.Scatter(
                x=dates,
                y=separation,
                name="Moon separation",
                line={"color": SEPARATION_COLOR},
                hovertemplate="%{y:.0f}°",
            ),
            go.Scatter(
                x=dates,
                y=illumination,
                name="Moon illumination",
                yaxis="y2",
                line={"color": ILLUMINATION_COLOR},
                hovertemplate="%{y:.0f}%",
            ),
        ]
    )
    now = datetime.now(timezone.utc)
    fig.add_vline(x=now, line={"dash": "dot", "width": 1}, opacity=0.6)
    fig.add_annotation(
        x=now, y=1, yref="paper", text="Now", showarrow=False, yanchor="bottom"
    )
    fig.update_layout(
        xaxis={"title": "Date (UTC)", "showgrid": grid},
        yaxis={
            "title": "Separation (°)",
            "range": [0, 180],
            "dtick": 30,
            "showgrid": grid,
        },
        yaxis2={
            "title": "Illumination (%)",
            "range": [0, 100],
            "dtick": 25,
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
        },
        hovermode="x unified",
        legend={"orientation": "h", "x": 0, "y": -0.25},
        margin={"l": 50, "r": 50, "b": 40, "t": 30},
        height=height,
        autosize=True,
        paper_bgcolor=background,
        plot_bgcolor=background,
    )
    fig.update_xaxes(color=label_color)
    fig.update_yaxes(color=label_color)
    return {"plot": offline.plot(fig, output_type="div", show_link=False)}
