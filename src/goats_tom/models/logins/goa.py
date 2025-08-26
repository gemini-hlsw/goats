__all__ = ["GOALogin"]

from .base import UsernamePasswordLogin


class GOALogin(UsernamePasswordLogin):
    """Extends `UsernamePasswordLogin` to store GOA user credentials."""

    pass
