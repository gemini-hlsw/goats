from goats_tom.models import (
    AstroDatalabLogin,
)
from .base import BaseLoginFactory


class AstroDatalabLoginFactory(BaseLoginFactory):
    """Factory for AstroDatalabLogin."""
    class Meta:
        model = AstroDatalabLogin
