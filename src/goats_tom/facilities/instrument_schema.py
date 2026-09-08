"""Instrument parameters, read from the portal's ``validation_schema``.

Every OCS instrument publishes what it accepts. For BLANCO the two differ
sharply: DECam takes a ``detector_centering`` of ``central_gap``, ``N4`` or
``S4`` and dithers not at all, while NEWFIRM dithers through a sequence and
centres on one of its four detectors. The vendored form ignores this and
sends NEWFIRM's parameters whatever the instrument, so DECam is asked for a
``det_1`` it rejects. Reading the schema keeps each request to what its own
instrument takes.
"""

__all__ = [
    "EXTRA",
    "base_bounds",
    "build_field",
    "cast",
    "check",
    "configuration_parameters",
    "exposure_parameters",
    "label_for",
    "merge",
    "narrowing",
    "readable",
]

from typing import Any

from django import forms

#: Marks the form fields that carry instrument ``extra_params``.
EXTRA = "extra"


def configuration_parameters(instrument: dict[str, Any]) -> dict[str, dict]:
    """Return the ``extra_params`` an instrument's configuration accepts.

    Parameters
    ----------
    instrument : dict
        One entry of the portal's instrument listing.

    Returns
    -------
    dict
        Parameter name to its specification; empty when none are declared.
    """
    schema = (instrument.get("validation_schema") or {}).get("extra_params") or {}
    return schema.get("schema") or {}


def _exposure_schema(instrument: dict[str, Any]) -> dict[str, Any]:
    """The per-exposure branch of an instrument's schema."""
    branch = (instrument.get("validation_schema") or {}).get("instrument_configs") or {}
    return (branch.get("schema") or {}).get("schema") or {}


def exposure_parameters(instrument: dict[str, Any]) -> dict[str, dict]:
    """Return the ``extra_params`` an instrument's exposures accept.

    NEWFIRM coadds and repeats its dither sequence; DECam declares nothing.
    """
    return (_exposure_schema(instrument).get("extra_params") or {}).get("schema") or {}


def base_bounds(instrument: dict[str, Any]) -> dict[str, dict]:
    """Return the limits an instrument puts on ordinary exposure fields.

    NEWFIRM caps an exposure at 40 seconds, for one, where the form offers
    them unbounded.
    """
    return {
        name: spec
        for name, spec in _exposure_schema(instrument).items()
        if name != "extra_params" and isinstance(spec, dict)
    }


def _codes(modes: list[dict]) -> list[str]:
    return [mode["code"] for mode in modes if mode.get("code")]


def narrowing(instrument: dict[str, Any]) -> dict[str, dict]:
    """Everything one instrument accepts, keyed by the field it belongs to.

    The interface matches a field by what its name ends in -- ``filter``,
    ``exposure_time``, ``extra_coadds`` -- so this is keyed the same way. A
    parameter missing from the map is one the instrument does not take.
    """
    entry: dict[str, dict] = {}
    for name, spec in configuration_parameters(instrument).items():
        entry[f"{EXTRA}_{name}"] = spec
    for name, spec in exposure_parameters(instrument).items():
        entry[f"{EXTRA}_{name}"] = spec
    entry.update(base_bounds(instrument))

    entry["configuration_type"] = {
        "allowed": [
            kind["code"]
            for kind in (instrument.get("configuration_types") or {}).values()
            if kind.get("schedulable") and kind.get("code")
        ]
    }
    entry["readout_mode"] = {
        "allowed": _codes(
            (instrument.get("modes") or {}).get("readout", {}).get("modes", [])
        )
    }
    for group, elements in (instrument.get("optical_elements") or {}).items():
        entry[group.rstrip("s")] = {
            "allowed": [
                element["code"] for element in elements if element.get("schedulable")
            ]
        }
    return entry


def merge(schemas: list[dict[str, dict]]) -> dict[str, dict]:
    """Merge several instruments' parameters into one set of fields.

    The form offers several instruments but only one is chosen, so a
    parameter two of them share becomes a single field: the values they allow
    are unioned, and a bound survives only if every instrument that declares
    the parameter sets one. Whether a value is really acceptable is decided
    against the chosen instrument, in :func:`check`.
    """
    merged: dict[str, dict] = {}
    for schema in schemas:
        for name, spec in schema.items():
            if name not in merged:
                merged[name] = dict(spec)
                continue
            current = merged[name]
            allowed = list(current.get("allowed") or [])
            allowed += [
                value for value in spec.get("allowed") or [] if value not in allowed
            ]
            if allowed:
                current["allowed"] = allowed
            for bound in ("min", "max"):
                if bound in spec and bound in current:
                    pick = min if bound == "min" else max
                    current[bound] = pick(current[bound], spec[bound])
                else:
                    current.pop(bound, None)
    return merged


def label_for(name: str, spec: dict[str, Any]) -> str:
    """What the portal calls a parameter, or a readable version of its name."""
    # Titled, as the fields the toolkit names are: "Exposure Count" above and
    # "Dither value" below would be two forms in one.
    return spec.get("label") or name.replace("_", " ").title()


def readable(value: Any) -> str:
    """A value the schema allows, written the way a person would write it."""
    words = str(value).replace("_", " ")
    # Capitals in a code are there for a reason: `N4` is a detector, not a
    # sentence, and `KXs` is a filter.
    return words.capitalize() if words.islower() else words


def build_field(name: str, spec: dict[str, Any]) -> forms.Field:
    """Build the form field one parameter describes.

    Fields are optional: which ones a request needs depends on the instrument
    chosen for it, which is enforced when the form is cleaned.
    """
    options: dict[str, Any] = {
        "required": False,
        "label": label_for(name, spec),
        "help_text": spec.get("description", ""),
        "initial": spec.get("default"),
    }
    allowed = spec.get("allowed")
    kind = spec.get("type")

    if kind == "boolean":
        return forms.BooleanField(**options)
    if allowed:
        options["choices"] = [(value, readable(value)) for value in allowed]
        return forms.ChoiceField(**options)
    if kind == "integer":
        return forms.IntegerField(
            min_value=spec.get("min"), max_value=spec.get("max"), **options
        )
    if kind == "float":
        return forms.FloatField(
            min_value=spec.get("min"), max_value=spec.get("max"), **options
        )
    return forms.CharField(**options)


def cast(value: Any, spec: dict[str, Any]) -> Any:
    """Put a cleaned value in the shape the portal expects."""
    kind = spec.get("type")
    if kind == "boolean":
        return bool(value)
    if kind == "integer":
        return int(value)
    if kind == "float":
        return float(value)
    return value


def check(value: Any, spec: dict[str, Any]) -> str | None:
    """Check a value against a parameter, returning why it is refused."""
    allowed = spec.get("allowed")
    if allowed is not None:
        if str(value) not in [str(option) for option in allowed]:
            options = ", ".join(str(option) for option in allowed)
            return f"{value} is not accepted by this instrument. Allowed: {options}."
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if "min" in spec and number < spec["min"]:
        return f"This instrument does not accept less than {spec['min']}."
    if "max" in spec and number > spec["max"]:
        return f"This instrument does not accept more than {spec['max']}."
    return None
