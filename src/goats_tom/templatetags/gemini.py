from typing import Any

from django import template

from ..forms import GOAQueryForm

register = template.Library()


@register.inclusion_tag("partials/goa_query.html", takes_context=True)
def render_goa_query_form(context: template.context.RequestContext) -> dict[str, Any]:
    """Render the GOAQueryForm.

    Parameters
    ----------
    context : `template.context.RequestContext`
        Additional context to provide to the view.

    Returns
    -------
    `dict`
        Dictionary containing the form to render.

    """
    form = GOAQueryForm()
    # Need to pass in the context of the object for partial to work.
    observationrecord = context.get("object", {})
    return {
        "form": form,
        "observationrecord": observationrecord,
        "object": observationrecord,
        "target": observationrecord.target,
    }


@register.inclusion_tag("partials/launch_dragons.html", takes_context=True)
def render_launch_dragons(context: template.context.RequestContext) -> dict[str, Any]:
    """Render the launch_dragons page.

    Parameters
    ----------
    context : `template.context.RequestContext`
        Additional context to provide to the view.

    Returns
    -------
    `dict`
        Dictionary containing the form to render.

    """
    return {"object": context.get("object", {})}
