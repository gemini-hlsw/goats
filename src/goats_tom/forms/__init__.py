from goats_tom.forms.antares_join_request import AntaresJoinRequestForm
from goats_tom.forms.registration import RegistrationForm
from goats_tom.forms.user import GOATSUserCreationForm, selectable_groups
from goats_tom.forms.antares_stream_subscribe import AntaresStreamSubscribeForm
from goats_tom.forms.goa_query import GOAQueryForm
from goats_tom.forms.logins import (
    AntaresKafkaLoginForm,
    AstroDatalabLoginForm,
    GOALoginForm,
    GPPLoginForm,
    LCOLoginForm,
    RSPTapLoginForm,
    TNSLoginForm,
)

__all__ = [
    "AntaresJoinRequestForm",
    "RegistrationForm",
    "GOATSUserCreationForm",
    "selectable_groups",
    "AntaresStreamSubscribeForm",
    "AntaresKafkaLoginForm",
    "GOAQueryForm",
    "TNSLoginForm",
    "AstroDatalabLoginForm",
    "GOALoginForm",
    "GPPLoginForm",
    "LCOLoginForm",
    "RSPTapLoginForm",
]
