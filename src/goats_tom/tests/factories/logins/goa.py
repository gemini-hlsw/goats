from goats_tom.models import (
    GOALogin,
)
from .base import BaseLoginFactory


class GOALoginFactory(BaseLoginFactory):
    """Factory for GOALogin."""
    class Meta:
        model = GOALogin
