import pytest
from unittest.mock import MagicMock, patch

from goats_tom.context.user_context import user_id_context, get_current_user_id
from goats_tom.facilities.overrides import (
    InferDataProductTypeMixin,
    UserAwareLCOSettings,
    UserAwareFacilityMixin,
)

pytestmark = pytest.mark.django_db


class DummySettings:
    def __init__(self, facility_name):
        self.facility_name = facility_name

    def get_setting(self, key):
        return None


class DummyBaseFacility:
    """
    Minimal stub of a TOMToolkit Facility to test the mixin behavior
    without depending on tom_observations internals.
    """
    name = "DUMMY"
    observation_forms = {"A": object, "B": object}

    def __init__(self, *args, **kwargs):
        self.facility_settings = kwargs.get("facility_settings")

    def get_form(self, observation_type):
        class BaseForm:
            def __init__(self, *args, **kwargs):
                self.facility_settings = kwargs.get("facility_settings")

        return BaseForm

    def get_form_classes_for_display(self, **kwargs):
        class FormA:
            def __init__(self, *args, **kwargs):
                self.facility_settings = kwargs.get("facility_settings")

        class FormB:
            def __init__(self, *args, **kwargs):
                self.facility_settings = kwargs.get("facility_settings")

        return {"A": FormA, "B": FormB}


class DummyFacility(UserAwareFacilityMixin, DummyBaseFacility):
    settings_cls = DummySettings


def test_user_id_context_sets_and_restores_uid():
    assert get_current_user_id() is None

    with user_id_context(42):
        assert get_current_user_id() == 42

    assert get_current_user_id() is None


def test_api_key_none_when_no_context():
    settings = UserAwareLCOSettings("LCO")
    assert settings.get_setting("api_key") is ""


def test_api_key_resolved_from_contextvar_and_user_token():
    """
    api_key is resolved using ContextVar uid -> User -> credential relation.
    """
    settings = UserAwareLCOSettings("LCO")

    fake_user = MagicMock()
    fake_cred = MagicMock()
    fake_cred.token = "TOKEN-123"
    setattr(fake_user, "lcologin", fake_cred)

    qs = MagicMock()
    qs.get.return_value = fake_user

    with (
        patch("goats_tom.facilities.overrides.get_user_model") as get_user_model,
        user_id_context(1),
    ):
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value = qs
        get_user_model.return_value = UserModel

        token = settings.get_setting("api_key")
        assert token == "TOKEN-123"


def test_api_key_cached_per_request():
    """
    Repeated calls to get_setting('api_key') in the same request
    should not hit the DB more than once.
    """
    settings = UserAwareLCOSettings("LCO")

    fake_user = MagicMock()
    fake_cred = MagicMock()
    fake_cred.token = "TOKEN-CACHED"
    setattr(fake_user, "lcologin", fake_cred)

    qs = MagicMock()
    qs.get.return_value = fake_user

    with (
        patch("goats_tom.facilities.overrides.get_user_model") as get_user_model,
        user_id_context(99),
    ):
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value = qs
        get_user_model.return_value = UserModel

        assert settings.get_setting("api_key") == "TOKEN-CACHED"
        assert settings.get_setting("api_key") == "TOKEN-CACHED"

        # DB queried only once
        assert qs.get.call_count == 1


def test_get_form_injects_facility_settings():
    """
    get_form() must return a wrapped form class that injects facility_settings.
    """
    facility = DummyFacility()

    form_cls = facility.get_form("A")
    form = form_cls()

    assert isinstance(form.facility_settings, DummySettings)
    assert form.facility_settings.facility_name == "DUMMY"


def test_get_form_classes_for_display_wraps_all_forms():
    """
    get_form_classes_for_display() must wrap *all* forms
    so they receive user-aware facility_settings.
    """
    facility = DummyFacility()

    forms_map = facility.get_form_classes_for_display()
    assert set(forms_map.keys()) == {"A", "B"}

    form_a = forms_map["A"]()
    form_b = forms_map["B"]()

    assert form_a.facility_settings.facility_name == "DUMMY"
    assert form_b.facility_settings.facility_name == "DUMMY"


def test_explicit_facility_settings_not_overridden():
    """
    If facility_settings is explicitly passed, the wrapper must NOT override it.
    """
    facility = DummyFacility()
    custom_settings = DummySettings("CUSTOM")

    form_cls = facility.get_form("A")
    form = form_cls(facility_settings=custom_settings)

    assert form.facility_settings is custom_settings


class DummySaveDataProductsBase:
    """
    Minimal stub of a Facility whose save_data_products returns preset products.
    """

    def __init__(self, products):
        self.products = products

    def save_data_products(self, observation_record, product_id=None):
        return self.products


class DummyTypedFacility(InferDataProductTypeMixin, DummySaveDataProductsBase):
    pass


def _dp(name, data_product_type=""):
    dp = MagicMock()
    dp.data.name = name
    dp.data_product_type = data_product_type
    return dp


@pytest.mark.parametrize(
    "name, preset, expected_type, expect_save",
    [
        ("obs.fits", "", "fits_file", True),
        ("obs.fits.fz", "", "fits_file", True),
        ("lightcurve.csv", "", "", False),
        ("obs.fits", "spectroscopy", "spectroscopy", False),
    ],
)
def test_infer_data_product_type_mixin(name, preset, expected_type, expect_save):
    """
    Untyped FITS products get tagged and saved; anything else is untouched.
    """
    dp = _dp(name, preset)
    facility = DummyTypedFacility([dp])

    result = facility.save_data_products(observation_record=None)

    assert result == [dp]
    assert dp.data_product_type == expected_type
    assert dp.save.called is expect_save
