"""Utility functions for GPP serializers."""

__all__ = ["normalize"]


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
