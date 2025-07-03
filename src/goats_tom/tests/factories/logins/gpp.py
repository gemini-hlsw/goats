from goats_tom.models import (
    GPPLogin,
)

from .base import TokenLoginFactory


class GPPLoginFactory(TokenLoginFactory):
    """Factory for GPPLogin."""

    class Meta:
        model = GPPLogin
