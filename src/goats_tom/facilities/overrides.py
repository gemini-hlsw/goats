"""
Facility overrides for TOMToolkit to support per-user API keys (ContextVar-based).

This version ONLY uses request-scoped ContextVar user resolution (ASGI-safe).
It does NOT support legacy set_user(user) injection.
"""

__all__ = ["LCOFacility", "SOARFacility", "BLANCOFacility"]

import logging
from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.utils.functional import cached_property
from tom_observations.facilities.blanco import BLANCOFacility as BaseBLANCOFacility
from tom_observations.facilities.blanco import BLANCOSettings
from tom_observations.facilities.lco import LCOFacility as BaseLCOFacility
from tom_observations.facilities.lco import LCOSettings
from tom_observations.facilities.soar import SOARFacility as BaseSOARFacility
from tom_observations.facilities.soar import SOARSettings

from goats_tom.context.user_context import get_current_user_id

logger = logging.getLogger(__name__)


class UserTokenMixin:
    """
    Inject per-user API keys into a facility settings class using ContextVar uid.

    Resolution for api_key:
    - Request-scoped user id via ContextVar (set by middleware).
    """

    credential_attr: str = ""
    """Name of the attribute on ``User`` pointing to the credential model."""

    token_field: str = "token"
    """Field name on the credential model that stores the API token."""

    def __init__(self, facility_name: str):
        super().__init__(facility_name)

        # Per-request cache to avoid repeated DB hits when api_key
        # is requested many times.
        self._token_cache_uid = object()  # sentinel
        self._token_cache_value: Optional[str] = None

    def get_setting(self, key: str) -> Any:
        """
        Return the requested setting, overriding ``api_key`` per user.
        """
        if key == "api_key":
            token = self._current_user_token
            if token:
                logger.debug(
                    "Using per-user API token (uid=%s, relation=%s.%s)",
                    get_current_user_id(),
                    self.credential_attr,
                    self.token_field,
                )
                return token

            logger.debug(
                "No per-user API token found (uid=%s, relation=%s.%s)",
                get_current_user_id(),
                self.credential_attr,
                self.token_field,
            )

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

        Uses request-scoped ContextVar uid set by middleware.
        """
        uid = get_current_user_id()
        if uid is None:
            return None

        relation, field = self._credential_accessors
        if not relation or not field:
            return None

        # Cache hit for this request/user.
        if uid == self._token_cache_uid:
            return self._token_cache_value

        UserModel = get_user_model()
        try:
            user = UserModel.objects.select_related(relation).get(pk=uid)
        except UserModel.DoesNotExist:
            self._token_cache_uid = uid
            self._token_cache_value = None
            return None

        credential_obj = getattr(user, relation, None)
        token = getattr(credential_obj, field, None) if credential_obj else None

        # Cache for remainder of request.
        self._token_cache_uid = uid
        self._token_cache_value = token

        return token


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


class UserAwareBLANCOSettings(UserTokenMixin, BLANCOSettings):
    """
    Settings wrapper that pulls API keys from ``user.lcologin.token``.
    """

    credential_attr = "lcologin"


class UserAwareFacilityMixin:
    """
    Mixin for facility classes that ensures user-aware facility settings
    are injected into all observation forms.

    This covers both code paths used by TOMToolkit:
    - ``get_form`` (direct form construction)
    - ``get_form_classes_for_display`` (used by the observation create view)
    """

    settings_cls = None

    def __init__(self, *args, **kwargs):
        # Ensure a user-aware settings instance is always created
        kwargs.setdefault("facility_settings", self.settings_cls(self.name))
        super().__init__(*args, **kwargs)

        base_settings = getattr(self, "facility_settings", None)
        if base_settings is None:
            raise RuntimeError(
                f"{self.__class__.__name__} has no facility_settings after init"
            )

        # Re-wrap using the same facility name to guarantee our settings class
        self.facility_settings = self.settings_cls(base_settings.facility_name)

    def _wrap_form_class(self, base_form_cls):
        """
        Wrap a base observation form class so that it always receives
        the user-aware facility_settings instance.
        """
        settings_obj = getattr(self, "facility_settings", None)

        class UserAwareForm(base_form_cls):
            def __init__(self, *args, **kwargs):
                # Do not override explicitly provided facility_settings
                kwargs.setdefault("facility_settings", settings_obj)
                super().__init__(*args, **kwargs)

        UserAwareForm.__name__ = f"UserAware{base_form_cls.__name__}"
        UserAwareForm.__qualname__ = UserAwareForm.__name__
        return UserAwareForm

    def get_form(self, observation_type):
        """
        Handle the code path where TOMToolkit directly requests a form
        class via ``get_form``.
        """
        base_form_cls = super().get_form(observation_type)
        return self._wrap_form_class(base_form_cls)

    def get_form_classes_for_display(self, **kwargs):
        """
        Handle the code path used by the observation creation view
        (``tom_observations.views``), which builds forms via
        ``get_form_classes_for_display``.
        """
        base_map = super().get_form_classes_for_display(**kwargs)
        return {key: self._wrap_form_class(cls) for key, cls in base_map.items()}


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


class BLANCOFacility(UserAwareFacilityMixin, BaseBLANCOFacility):
    """
    BLANCO facility with per-user API keys.
    """

    settings_cls = UserAwareBLANCOSettings
