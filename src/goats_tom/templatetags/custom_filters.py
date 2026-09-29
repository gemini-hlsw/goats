__all__ = [
    "add_class",
    "display_name",
    "select_fields",
    "starts_with",
    "with_widget_class",
]
# Standard library imports.

# Related third party imports.
from django import template
from django.forms import BaseForm, BoundField
from django.utils.safestring import SafeString

# Local application/library specific imports.

register = template.Library()


def _merged_classes(field: BoundField, css: str) -> str:
    """Returns the widget's classes plus `css`, without repeating any."""
    return " ".join(
        dict.fromkeys(field.field.widget.attrs.get("class", "").split() + css.split())
    )


@register.filter(name="starts_with")
def starts_with(text: str, look_for: str) -> bool:
    """Checks to see if string starts with provided text.

    Parameters
    ----------
    text : `str`
        The text to analyze.
    starts : `str`
        The string to look for at the beginning of the text.

    Returns
    -------
    `bool`
        `True` if text starts with string, `False` if not.

    """
    if isinstance(text, str):
        return text.startswith(look_for)

    return False


@register.filter(name="add_class")
def add_class(field: BoundField, css: str) -> SafeString:
    """Renders a form field with extra CSS classes on its widget.

    Parameters
    ----------
    field : `BoundField`
        The field to render.
    css : `str`
        The classes to add to the ones the widget already carries. Classes
        already present are not repeated.

    Returns
    -------
    `SafeString`
        The rendered widget.

    """
    return field.as_widget(attrs={"class": _merged_classes(field, css)})


@register.filter(name="select_fields")
def select_fields(form: BaseForm, names: str) -> list[BoundField]:
    """Picks the named fields out of a form, in the order given.

    Parameters
    ----------
    form : `BaseForm`
        The form to read.
    names : `str`
        Comma-separated field names. Names the form does not have are
        skipped, so a field a view removes per user needs no special case.

    Returns
    -------
    `list[BoundField]`
        The fields that exist, in the order named.

    """
    return [form[name] for name in names.split(",") if name in form.fields]


@register.filter(name="with_widget_class")
def with_widget_class(field: BoundField, css: str) -> BoundField:
    """Adds CSS classes to a field's widget and hands the field back.

    Unlike `add_class` this renders nothing, so the caller can iterate the
    field to lay its checkboxes out itself.

    Parameters
    ----------
    field : `BoundField`
        The field whose widget to mark.
    css : `str`
        The classes to add. Classes already present are not repeated.

    Returns
    -------
    `BoundField`
        The same field. Its widget belongs to this form instance, which
        Django copies per request, so nothing leaks between requests.

    """
    field.field.widget.attrs["class"] = _merged_classes(field, css)
    return field


@register.filter(name="display_name")
def display_name(user) -> str:
    """Names a person the way GOATS shows them to another user.

    Parameters
    ----------
    user : `django.contrib.auth.models.User` or `None`
        The person to name. `None` is accepted because a stored record can
        outlive the account that made it.

    Returns
    -------
    `str`
        Their full name, failing that their email address, failing that an em
        dash.

    Notes
    -----
    Never the username: it is half of a login credential and names nobody to
    a colleague. The email address is the fallback rather than the first
    choice because a real name is what a colleague recognises -- but an unset
    name is common enough that without a fallback the dash would be most of
    the column.
    """
    if user is None:
        return "—"
    full = (user.get_full_name() or "").strip()
    return full or (user.email or "").strip() or "—"
