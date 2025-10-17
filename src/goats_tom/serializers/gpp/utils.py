"""Utility functions for GPP serializers."""

__all__ = ["normalize", "parse_comma_separated_floats"]

from rest_framework import serializers


def normalize(value: str | None) -> str | None:
    """
    Convert empty strings or whitespace to ``None``.

    Parameters
    ----------
    value : str | None
        The input string to normalize.

    Returns
    -------
    str | None
        The normalized string or ``None`` if the input was empty or whitespace.
    """
    return value.strip() if value and value.strip() != "" else None


def parse_comma_separated_floats(
    input_value: str, field_name: str, unit: str
) -> list[dict[str, float]]:
    """Parse a comma-separated string into a list of floats with units.

    Parameters
    ----------
    input_value : str
        The comma-separated string to parse.
    field_name : str
        The name of the field being parsed (for error messages).
    unit : str
        The unit to associate with the parsed float values.

    Returns
    -------
    list[dict[str, float]]
        A list of dictionaries, each containing a single float value with the
        associated unit.

    Raises
    ------
    serializers.ValidationError
        If any value cannot be converted to a float.

    Notes
    -----
    - Right now, the comma separated fields are very lenient in what they accept, as
    long as they can be converted to floats. Extra whitespace and empty entries
    are ignored. This may need to be tightened up in the future.
    """
    try:
        return [
            # Create a dictionary for each valid float value.
            {unit: float(value.strip())}
            for value in input_value.split(",")
            # Ignore empty entries.
            if value.strip()
        ]
    except ValueError:
        raise serializers.ValidationError(
            f"{field_name} must be a comma-separated list of numeric values in {unit}."
        )
