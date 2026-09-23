"""Facility overrides for TOMToolkit to support per-user API keys."""

__all__ = ["LCOFacility", "SOARFacility", "BLANCOFacility"]

import logging
from typing import Any, Optional

from tom_observations.facilities.blanco import BLANCOFacility as BaseBLANCOFacility
from tom_observations.facilities.blanco import BLANCOSettings
from tom_observations.facilities.lco import LCOFacility as BaseLCOFacility
from tom_observations.facilities.lco import LCOSettings
from tom_observations.facilities.soar import SOARFacility as BaseSOARFacility
from tom_observations.facilities.soar import SOARSettings

from goats_tom.credentials import get_credentials
from goats_tom.models import LCOLogin
from goats_tom.models.logins.base import BaseLogin

from .blanco import GOATSBLANCOImagingObservationForm

logger = logging.getLogger(__name__)


class UserTokenMixin:
    """
    Inject the current user's API key into a facility settings class.

    The toolkit's ``set_user()`` stops at the facility and never reaches its
    settings, so this is the only adapter between the two.
    """

    credential_model: type[BaseLogin] | None = None
    """The credential model holding this facility's token."""

    token_field: str = "token"
    """Field name on the credential model that stores the API token."""

    def get_setting(self, key: str) -> Any:
        """
        Return the requested setting, overriding ``api_key`` per user.
        """
        if key == "api_key":
            token = self._current_user_token
            if token:
                logger.debug("Using per-user API token (%s).", self.facility_name)
                return token

            logger.debug("No per-user API token found (%s).", self.facility_name)

        # Otherwise, do the default.
        return super().get_setting(key)

    @property
    def _current_user_token(self) -> Optional[str]:
        """
        Return the per-user token or ``None`` when unavailable.
        """
        if self.credential_model is None:
            return None

        credentials = get_credentials(self.credential_model)
        if credentials is None:
            return None

        return getattr(credentials, self.token_field, None)


class UserAwareLCOSettings(UserTokenMixin, LCOSettings):
    """
    Settings wrapper that pulls API keys from ``user.lcologin.token``.
    """

    credential_model = LCOLogin


class UserAwareSOARSettings(UserTokenMixin, SOARSettings):
    """
    Settings wrapper that pulls API keys from ``user.lcologin.token``.
    """

    credential_model = LCOLogin


class UserAwareBLANCOSettings(UserTokenMixin, BLANCOSettings):
    """
    Settings wrapper that pulls API keys from ``user.lcologin.token``.
    """

    credential_model = LCOLogin


class InferDataProductTypeMixin:
    """
    Infer and persist `data_product_type` for products saved without one.

    TOMToolkit's generic `save_data_products` creates `DataProduct` rows with
    an empty `data_product_type`; views like the visualizer filter on the
    stored value, so tag them at ingestion instead of at display time.
    """

    def save_data_products(self, observation_record, product_id=None):
        products = super().save_data_products(observation_record, product_id)
        for dp in products:
            if not dp.data_product_type and dp.data.name.endswith(
                (".fits", ".fits.fz")
            ):
                dp.data_product_type = "fits_file"
                dp.save(update_fields=["data_product_type"])
        return products


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


class LCOFacility(InferDataProductTypeMixin, UserAwareFacilityMixin, BaseLCOFacility):
    """
    LCO facility with per-user API keys.
    """

    settings_cls = UserAwareLCOSettings


class SOARFacility(InferDataProductTypeMixin, UserAwareFacilityMixin, BaseSOARFacility):
    """
    SOAR facility with per-user API keys.
    """

    settings_cls = UserAwareSOARSettings


class BLANCOFacility(
    InferDataProductTypeMixin, UserAwareFacilityMixin, BaseBLANCOFacility
):
    """
    BLANCO facility with per-user API keys, serving the GOATS form.
    """

    settings_cls = UserAwareBLANCOSettings
    observation_forms = {"IMAGING": GOATSBLANCOImagingObservationForm}
