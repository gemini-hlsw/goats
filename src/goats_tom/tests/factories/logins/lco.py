from goats_tom.models import LCOLogin

from .base import TokenLoginFactory


class LCOLoginFactory(TokenLoginFactory):
    """Factory for LCOLogin."""

    class Meta:
        model = LCOLogin
