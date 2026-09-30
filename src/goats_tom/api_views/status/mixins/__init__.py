# The mixins must be imported to register them.
from .astro_datalab import AstroDatalabStatusMixin
from .base import status_mixins
from .goa import GOAStatusMixin
from .gpp import GPPStatusMixin
from .lco import LCOStatusMixin
from .public import (
    ALeRCEPublicStatusMixin,
    ANTARESPublicStatusMixin,
    GaiaPublicStatusMixin,
    HorizonsPublicStatusMixin,
    NEDPublicStatusMixin,
    ScoutPublicStatusMixin,
    SIMBADPublicStatusMixin,
)
from .tns import TNSStatusMixin

__all__ = [
    "status_mixins",
    "GPPStatusMixin",
    "GOAStatusMixin",
    "AstroDatalabStatusMixin",
    "LCOStatusMixin",
    "TNSStatusMixin",
    "ALeRCEPublicStatusMixin",
    "ANTARESPublicStatusMixin",
    "GaiaPublicStatusMixin",
    "HorizonsPublicStatusMixin",
    "NEDPublicStatusMixin",
    "ScoutPublicStatusMixin",
    "SIMBADPublicStatusMixin",
]
