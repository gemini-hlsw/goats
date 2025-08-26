__all__ = ["LCOFacility", "SOARFacility"]
import logging
from typing import Any, Optional

from django.contrib.auth.models import User
from django.utils.functional import cached_property
from tom_observations.facilities.lco import LCOFacility as BaseLCOFacility
from tom_observations.facilities.lco import LCOSettings
from tom_observations.facilities.soar import SOARFacility as BaseSOARFacility
from tom_observations.facilities.soar import SOARSettings

log = logging.getLogger(__name__)


class UserTokenMixin:
    """
    Inject per-user API keys into a facility settings class.
    """

    credential_attr: str = ""
    """Name of the attribute on ``User`` pointing to the credential model."""

    token_field: str = "token"
    """Field name on the credential model that stores the API token."""

    def __init__(self, facility_name: str):
        super().__init__(facility_name)
        self._user = None

    def set_user(self, user: User) -> None:
        """
        Store the current request user for subsequent token look-ups.
        """
        self._user = user

    def get_setting(self, key: str) -> Any:
        """
        Return the requested setting, overriding ``api_key`` per user.
        """
        if key == "api_key":
            token = self._current_user_token
            if token:
                return token

        # Otherwise, do the default.
        return super().get_setting(key)

    @cached_property
    def _credential_accessors(self) -> tuple[Optional[str], Optional[str]]:
        """
        Cached tuple ``(relation_name, token_field_name)``.
        """
        if not self.credential_attr:
            return None, None
        return self.credential_attr, self.token_field

    @property
    def _current_user_token(self) -> Optional[str]:
        """
        Return the per-user token or ``None`` when unavailable.
        """
        if not (self._user and self._user.is_authenticated):
            return None

        relation, field = self._credential_accessors
        credential_obj = getattr(self._user, relation, None)
        if credential_obj is None:
            return None

        return getattr(credential_obj, field, None)


class UserAwareLCOSettings(UserTokenMixin, LCOSettings):
    """
    Settings wrapper that pulls API keys from ``user.lcologin.token``.
    """

    credential_attr = "lcologin"


class UserAwareSOARSettings(UserTokenMixin, SOARSettings):
    """
    Settings wrapper that pulls API keys from ``user.lcologin.token``.
    """

    credential_attr = "lcologin"


class UserAwareFacilityMixin:
    """
    Mixin for a facility class that wires `request.user` into its
    user-aware settings instance.
    """

    settings_cls = None

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("facility_settings", self.settings_cls(self.name))
        super().__init__(*args, **kwargs)

    def set_user(self, user) -> None:
        super().set_user(user)
        settings_obj = getattr(self, "facility_settings", None)
        if settings_obj and hasattr(settings_obj, "set_user"):
            settings_obj.set_user(user)


class LCOFacility(UserAwareFacilityMixin, BaseLCOFacility):
    """
    LCO facility with per-user API keys.
    """

    settings_cls = UserAwareLCOSettings


class SOARFacility(UserAwareFacilityMixin, BaseSOARFacility):
    """
    SOAR facility with per-user API keys.
    """

    settings_cls = UserAwareSOARSettings
