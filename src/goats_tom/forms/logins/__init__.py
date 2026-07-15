from .antares_kafka import AntaresKafkaLoginForm
from .astro_datalab import AstroDatalabLoginForm
from .goa import GOALoginForm
from .gpp import GPPLoginForm
from .lco import LCOLoginForm
from .tns import TNSLoginForm

__all__ = [
    "AntaresKafkaLoginForm",
    "AstroDatalabLoginForm",
    "TNSLoginForm",
    "GOALoginForm",
    "GPPLoginForm",
    "LCOLoginForm",
]
