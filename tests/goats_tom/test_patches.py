import importlib
from dataclasses import dataclass
from typing import Any

import pytest
from django.contrib.auth.models import AnonymousUser

from goats_tom.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def reset_third_party_modules():
    """
    Ensure each test starts with unpatched third-party implementations.
    """
    import tom_observations.facilities.ocs as ocs_module
    import tom_tns.tns_api as tns_api_module

    importlib.reload(ocs_module)
    importlib.reload(tns_api_module)
    yield


@dataclass(frozen=True)
class DummyFacilitySettings:
    facility_name: str
    default_instrument_config: dict[str, Any]
    _user: Any

    def get_setting(self, key: str) -> str:
        if key == "portal_url":
            return "https://example.test"
        if key == "api_key":
            return "abc123"
        raise KeyError(key)


class DummyOCSForm:
    def __init__(self, facility_settings: DummyFacilitySettings):
        self.facility_settings = facility_settings


def _response(mocker, payload: dict[str, Any]):
    resp = mocker.Mock()
    resp.json.return_value = payload
    return resp


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def dummy_ocs_form_authenticated(user) -> DummyOCSForm:
    settings = DummyFacilitySettings(
        facility_name="FAKE",
        default_instrument_config={"DEFAULT": True},
        _user=user,
    )
    return DummyOCSForm(settings)


@pytest.fixture
def dummy_ocs_form_anon() -> DummyOCSForm:
    settings = DummyFacilitySettings(
        facility_name="FAKE",
        default_instrument_config={"DEFAULT": True},
        _user=AnonymousUser(),
    )
    return DummyOCSForm(settings)


@pytest.mark.django_db
def test_apply_all_patches_calls_both(mocker):
    """
    Test that apply_all_patches calls both patch functions.
    """
    tns = mocker.patch("goats_tom.patches.apply_tns_patches")
    ocs = mocker.patch("goats_tom.patches.apply_ocs_patches")

    from goats_tom.patches import apply_all_patches

    apply_all_patches()

    tns.assert_called_once()
    ocs.assert_called_once()


@pytest.mark.django_db
def test_apply_tns_patches_is_idempotent(mocker):
    """
    Test that applying TNS patches multiple times does not re-patch.
    """
    from tom_tns import tns_api

    from goats_tom.middleware.tns import current_tns_creds
    from goats_tom.patches import apply_tns_patches

    tns_api.get_tns_credentials = mocker.Mock(return_value={"api_key": "orig"})
    tns_api.group_names = mocker.Mock(return_value=["orig-group"])

    token = current_tns_creds.set({"api_key": "ctx"})
    try:
        apply_tns_patches()
        first_get = tns_api.get_tns_credentials
        first_group = tns_api.group_names

        apply_tns_patches()
        assert tns_api.get_tns_credentials is first_get
        assert tns_api.group_names is first_group
    finally:
        current_tns_creds.reset(token)


@pytest.mark.django_db
def test_apply_ocs_patches_is_idempotent():
    """
    Test that applying OCS patches multiple times does not re-patch.
    """
    from tom_observations.facilities.ocs import OCSBaseForm

    from goats_tom.patches import apply_ocs_patches

    assert not getattr(OCSBaseForm, "_goats_patched", False)

    apply_ocs_patches()
    assert getattr(OCSBaseForm, "_goats_patched", False)

    inst1 = OCSBaseForm._get_instruments
    prop1 = OCSBaseForm.proposal_choices

    apply_ocs_patches()
    assert OCSBaseForm._get_instruments is inst1
    assert OCSBaseForm.proposal_choices is prop1


@pytest.mark.parametrize("cached_instruments", [{}, {"GMOS": {"ok": True}}])
@pytest.mark.django_db
def test_ocs_instruments_cache_hit_uses_cache_and_instance_memo(
    mocker,
    dummy_ocs_form_authenticated: DummyOCSForm,
    cached_instruments: dict[str, Any],
):
    """
    Test that cached instruments are used and instance memoization works.
    """
    mocker.patch("django.core.cache.cache.get", return_value=cached_instruments)
    cache_set = mocker.patch("django.core.cache.cache.set")

    # Patch make_request BEFORE apply_ocs_patches so the closure captures it.
    make_request = mocker.patch(
        "tom_observations.facilities.ocs.make_request",
        autospec=True,
    )

    from goats_tom.patches import apply_ocs_patches

    apply_ocs_patches()

    from tom_observations.facilities.ocs import OCSBaseForm

    out1 = OCSBaseForm._get_instruments(dummy_ocs_form_authenticated)
    out2 = OCSBaseForm._get_instruments(dummy_ocs_form_authenticated)

    assert out1 == cached_instruments
    assert out2 == cached_instruments
    assert make_request.call_count == 0
    assert cache_set.call_count == 0


@pytest.mark.django_db
def test_ocs_instruments_cache_miss_fetches_and_caches(
    mocker,
    dummy_ocs_form_authenticated: DummyOCSForm,
):
    """
    Test that missing cached instruments are fetched and then cached.
    """
    mocker.patch("django.core.cache.cache.get", return_value=None)
    cache_set = mocker.patch("django.core.cache.cache.set")

    resp = _response(mocker, {"GMOS": {"ok": True}})
    make_request = mocker.patch(
        "tom_observations.facilities.ocs.make_request",
        return_value=resp,
        autospec=True,
    )

    from goats_tom.patches import apply_ocs_patches

    apply_ocs_patches()

    from tom_observations.facilities.ocs import OCSBaseForm

    out = OCSBaseForm._get_instruments(dummy_ocs_form_authenticated)

    assert out == {"GMOS": {"ok": True}}
    make_request.assert_called_once()
    cache_set.assert_called_once()


@pytest.mark.django_db
def test_ocs_instruments_improper_credentials_returns_default_and_caches(
    mocker,
    dummy_ocs_form_authenticated: DummyOCSForm,
):
    """
    Test that ImproperCredentialsException returns default instruments and caches them.
    """
    from tom_common.exceptions import ImproperCredentialsException

    mocker.patch("django.core.cache.cache.get", return_value=None)
    cache_set = mocker.patch("django.core.cache.cache.set")

    make_request = mocker.patch(
        "tom_observations.facilities.ocs.make_request",
        side_effect=ImproperCredentialsException("nope"),
        autospec=True,
    )

    from goats_tom.patches import apply_ocs_patches

    apply_ocs_patches()

    from tom_observations.facilities.ocs import OCSBaseForm

    out = OCSBaseForm._get_instruments(dummy_ocs_form_authenticated)

    assert out == {"DEFAULT": True}
    make_request.assert_called_once()
    cache_set.assert_called_once()


@pytest.mark.django_db
def test_ocs_instruments_unauthenticated_returns_default_no_cache_no_request(
    mocker,
    dummy_ocs_form_anon: DummyOCSForm,
):
    """
    Test that unauthenticated users get default instruments without cache or request.
    """
    cache_get = mocker.patch("django.core.cache.cache.get")
    cache_set = mocker.patch("django.core.cache.cache.set")
    make_request = mocker.patch("tom_observations.facilities.ocs.make_request")

    from goats_tom.patches import apply_ocs_patches

    apply_ocs_patches()

    from tom_observations.facilities.ocs import OCSBaseForm

    out = OCSBaseForm._get_instruments(dummy_ocs_form_anon)

    assert out == {"DEFAULT": True}
    assert cache_get.call_count == 0
    assert cache_set.call_count == 0
    assert make_request.call_count == 0


@pytest.mark.parametrize("cached_proposals", [[], [("GN-1", "A (GN-1)")]])
@pytest.mark.django_db
def test_ocs_proposals_cache_hit_uses_cache_and_instance_memo(
    mocker,
    dummy_ocs_form_authenticated: DummyOCSForm,
    cached_proposals: list[tuple[str, str]],
):
    """
    Test that cached proposals are used and instance memoization works.
    """
    mocker.patch("django.core.cache.cache.get", return_value=cached_proposals)
    cache_set = mocker.patch("django.core.cache.cache.set")
    make_request = mocker.patch("tom_observations.facilities.ocs.make_request")

    from goats_tom.patches import apply_ocs_patches

    apply_ocs_patches()

    from tom_observations.facilities.ocs import OCSBaseForm

    out1 = OCSBaseForm.proposal_choices(dummy_ocs_form_authenticated)
    out2 = OCSBaseForm.proposal_choices(dummy_ocs_form_authenticated)

    assert out1 == cached_proposals
    assert out2 == cached_proposals
    assert make_request.call_count == 0
    assert cache_set.call_count == 0


@pytest.mark.django_db
def test_ocs_proposals_cache_miss_fetches_filters_current_and_caches(
    mocker,
    dummy_ocs_form_authenticated: DummyOCSForm,
):
    """
    Test that missing cached proposals are fetched, filtered for current, and then
    cached.
    """
    mocker.patch("django.core.cache.cache.get", return_value=None)
    cache_set = mocker.patch("django.core.cache.cache.set")

    resp = _response(
        mocker,
        {
            "proposals": [
                {"id": "GN-1", "title": "A", "current": True},
                {"id": "GN-2", "title": "B", "current": False},
            ],
        },
    )
    make_request = mocker.patch(
        "tom_observations.facilities.ocs.make_request",
        return_value=resp,
        autospec=True,
    )

    from goats_tom.patches import apply_ocs_patches

    apply_ocs_patches()

    from tom_observations.facilities.ocs import OCSBaseForm

    out = OCSBaseForm.proposal_choices(dummy_ocs_form_authenticated)

    assert out == [("GN-1", "A (GN-1)")]
    make_request.assert_called_once()
    cache_set.assert_called_once()


@pytest.mark.django_db
def test_ocs_proposals_improper_credentials_returns_no_proposals_found(
    mocker,
    dummy_ocs_form_authenticated: DummyOCSForm,
):
    """
    Test that ImproperCredentialsException returns default proposals and does not cache.
    """
    from tom_common.exceptions import ImproperCredentialsException

    mocker.patch("django.core.cache.cache.get", return_value=None)
    cache_set = mocker.patch("django.core.cache.cache.set")

    make_request = mocker.patch(
        "tom_observations.facilities.ocs.make_request",
        side_effect=ImproperCredentialsException("nope"),
        autospec=True,
    )

    from goats_tom.patches import apply_ocs_patches

    apply_ocs_patches()

    from tom_observations.facilities.ocs import OCSBaseForm

    out = OCSBaseForm.proposal_choices(dummy_ocs_form_authenticated)

    assert out == [(0, "No proposals found")]
    make_request.assert_called_once()
    assert cache_set.call_count == 0
