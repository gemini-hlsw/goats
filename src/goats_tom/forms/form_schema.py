"""Describes a Django form as data, so a front end can render it.

A form built in Python already knows its fields, their types, their choices
and their limits. Handing that description to the browser keeps a JavaScript
interface from restating any of it: the form stays the single definition of
what can be asked for, and of what is accepted.
"""

__all__ = ["FULL", "HALF", "FieldType", "describe_field", "describe_form"]

from enum import StrEnum
from typing import Any

from django import forms

#: The only two widths a field is drawn at: half a row, or all of it.
HALF = 6
FULL = 12


class FieldType(StrEnum):
    """The kinds of control a described field maps to."""

    BOOLEAN = "boolean"
    CHOICE = "choice"
    DATETIME = "datetime"
    FLOAT = "float"
    INTEGER = "integer"
    TEXT = "text"


def _field_type(field: forms.Field) -> FieldType:
    """Classify a form field into the control that should render it."""
    if isinstance(field, forms.SplitDateTimeField):
        return FieldType.DATETIME
    if isinstance(field, forms.ChoiceField):
        return FieldType.CHOICE
    if isinstance(field, forms.BooleanField):
        return FieldType.BOOLEAN
    # FloatField and DecimalField both subclass IntegerField, so they have to
    # be ruled out first, or a decimal is described as a whole number and the
    # browser refuses the 1.05 the form itself offers.
    if isinstance(field, forms.FloatField | forms.DecimalField):
        return FieldType.FLOAT
    if isinstance(field, forms.IntegerField):
        return FieldType.INTEGER
    return FieldType.TEXT


def describe_field(name: str, field: forms.Field, width: int = HALF) -> dict[str, Any]:
    """Describe one form field.

    Parameters
    ----------
    name : str
        The field's name on the form, which the interface must post back.
    field : django.forms.Field
        The field to describe.
    width : int, optional
        ``HALF`` or ``FULL``, the columns the field is drawn across.

    Returns
    -------
    dict
        The name, type, label, help text, initial value, bounds and, for a
        choice field, its options.
    """
    field_type = _field_type(field)
    described: dict[str, Any] = {
        "name": name,
        "type": str(field_type),
        "label": field.label or name.replace("_", " ").capitalize(),
        # Some vendored help is a block of whitespace; that is no help.
        "help_text": str(field.help_text or "").strip(),
        "required": field.required,
        "hidden": field.widget.is_hidden,
        "initial": field.initial,
        "width": width,
    }
    if field_type is FieldType.CHOICE:
        described["choices"] = [
            {"value": value, "label": str(label)} for value, label in field.choices
        ]
    for attribute, key in (("min_value", "min"), ("max_value", "max")):
        value = getattr(field, attribute, None)
        if value is not None:
            described[key] = value
    placeholder = field.widget.attrs.get("placeholder")
    if placeholder:
        described["placeholder"] = placeholder
    unit = field.widget.attrs.get("data-unit")
    if unit:
        described["unit"] = unit
    return described


def describe_form(
    form: forms.Form,
    names: list[str] | None = None,
    widths: dict[str, int] | None = None,
) -> list[dict]:
    """Describe a form's fields, in the given order.

    Parameters
    ----------
    form : django.forms.Form
        The form to describe.
    names : list of str, optional
        Which fields to describe, in order. Unknown names are skipped. By
        default every field, in the form's own order.
    widths : dict, optional
        Field names mapped to ``FULL`` for the ones that take a whole row.

    Returns
    -------
    list of dict
        One description per field.
    """
    if names is None:
        names = list(form.fields)
    widths = widths or {}
    return [
        describe_field(name, form.fields[name], widths.get(name, HALF))
        for name in names
        if name in form.fields
    ]
