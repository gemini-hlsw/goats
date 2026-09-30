from unittest.mock import Mock, patch

import pytest
from rest_framework.request import Request

from goats_tom.api_views.status.mixins.astro_datalab import AstroDatalabStatusMixin
from goats_tom.api_views.status.mixins.base import (
    Credentials,
    MissingCredentialsError,
    Status,
)
from goats_tom.api_views.status.mixins.goa import GOAStatusMixin
from goats_tom.api_views.status.mixins.gpp import GPPStatusMixin
from goats_tom.api_views.status.mixins.lco import LCOStatusMixin
from goats_tom.api_views.status.mixins.tns import TNSStatusMixin
from goats_tom.service_checks import CheckResult


@pytest.fixture
def mock_request():
    request = Mock(spec=Request)
    request.user = Mock()
    request.query_params = {}
    return request


@pytest.mark.parametrize(
    ("mixin_cls", "attr", "stored", "expected", "check"),
    [
        (
            GOAStatusMixin,
            "goalogin",
            Mock(username="u", password="p"),
            {"username": "u", "password": "p"},
            "check_goa",
        ),
        (
            AstroDatalabStatusMixin,
            "astrodatalablogin",
            Mock(username="u", password="p"),
            {"username": "u", "password": "p"},
            "check_astro_datalab",
        ),
        (LCOStatusMixin, "lcologin", Mock(token="t"), {"token": "t"}, "check_lco"),
    ],
)
def test_account_mixins_use_the_shared_check(
    mock_request, mixin_cls, attr, stored, expected, check
):
    """Stored credentials are passed to the shared check, whose result is returned."""
    setattr(mock_request.user, attr, stored)
    mixin = mixin_cls()

    credentials = mixin.get_credentials(mock_request)
    assert credentials == expected

    result = CheckResult(False, "nope")
    with patch(f"{mixin_cls.__module__}.{check}", return_value=result) as mock_check:
        assert mixin.check_service(credentials) is result
    mock_check.assert_called_once_with(**expected)


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (CheckResult(True, "ok"), (Status.OK, Credentials.VERIFIED)),
        (CheckResult(False, "no"), (Status.OK, Credentials.REJECTED)),
        (
            CheckResult(False, "GOA is not available.", reachable=False),
            (Status.DOWN, Credentials.UNCHECKED),
        ),
        (CheckResult(True, "?", verified=False), (Status.OK, Credentials.UNVERIFIABLE)),
    ],
)
def test_availability_and_credentials_are_reported_apart(
    mock_request, result, expected
):
    """Rejected credentials do not make the service look down."""
    mock_request.user.goalogin = Mock(username="u", password="p")

    with patch("goats_tom.api_views.status.mixins.goa.check_goa", return_value=result):
        data = GOAStatusMixin().get(mock_request).data

    assert (data["status"], data["credentials"]) == (expected[0].value, expected[1].value)
    assert data["message"] == result.message


@pytest.mark.parametrize(
    ("mixin_cls", "attr"),
    [
        (GOAStatusMixin, "goalogin"),
        (AstroDatalabStatusMixin, "astrodatalablogin"),
        (LCOStatusMixin, "lcologin"),
        (TNSStatusMixin, "tnslogin"),
        (GPPStatusMixin, "gpplogin"),
    ],
)
def test_account_mixins_missing_credentials(mock_request, mixin_cls, attr):
    delattr(mock_request.user, attr)

    with pytest.raises(MissingCredentialsError):
        mixin_cls().get_credentials(mock_request)


@pytest.mark.parametrize(
    ("reachable", "expected"), [(True, "ok"), (False, "down")]
)
def test_tns_saved_credentials_are_unverifiable(mock_request, reachable, expected):
    mock_request.user.tnslogin = Mock()
    reach = CheckResult(reachable, "TNS is not available.", reachable=reachable)

    with patch(
        "goats_tom.api_views.status.mixins.base.check_reachable", return_value=reach
    ):
        data = TNSStatusMixin().get(mock_request).data

    assert data["status"] == expected
    if reachable:
        assert data["credentials"] == Credentials.UNVERIFIABLE.value
        assert data["message"] == "GOATS does not verify TNS credentials automatically."
    else:
        assert data["credentials"] == Credentials.UNCHECKED.value


@pytest.mark.parametrize(
    ("mixin_cls", "attr"),
    [
        (GOAStatusMixin, "goalogin"),
        (AstroDatalabStatusMixin, "astrodatalablogin"),
        (LCOStatusMixin, "lcologin"),
        (TNSStatusMixin, "tnslogin"),
    ],
)
@pytest.mark.parametrize(
    ("reachable", "status", "message"),
    [(True, "ok", "No credentials stored."), (False, "down", "X is not available.")],
)
def test_missing_credentials_still_reports_availability(
    mock_request, mixin_cls, attr, reachable, status, message
):
    """One row per service: without credentials, it reports if the service is up."""
    delattr(mock_request.user, attr)
    reach = CheckResult(reachable, "X is not available.", reachable=reachable)

    with patch(
        "goats_tom.api_views.status.mixins.base.check_reachable", return_value=reach
    ) as mock_check:
        data = mixin_cls().get(mock_request).data

    mock_check.assert_called_once_with(
        mixin_cls().get_public_url(),
        mixin_cls.service_name,
        mixin_cls().get_public_headers(),
    )
    assert data["status"] == status
    assert data["credentials"] == Credentials.MISSING.value
    assert data["message"] == message


def test_tns_identifies_as_a_bot():
    """TNS answers 403 to any client that is not a tns_marker bot."""
    headers = TNSStatusMixin().get_public_headers()

    assert headers["User-Agent"].startswith("tns_marker{")
    assert '"type": "bot"' in headers["User-Agent"]


@pytest.mark.parametrize(
    ("reachable", "status"), [(True, "ok"), (False, "down")]
)
def test_gpp_without_token_asks_the_ping_query(mock_request, reachable, status):
    """Without a token GPP is asked the client's ping query, not its 404 root."""
    delattr(mock_request.user, "gpplogin")
    reach = CheckResult(reachable, "GPP is not available.", reachable=reachable)

    with patch(
        "goats_tom.api_views.status.mixins.gpp.check_gpp_reachable", return_value=reach
    ) as mock_check:
        data = GPPStatusMixin().get(mock_request).data

    mock_check.assert_called_once_with()
    assert data["status"] == status
    assert data["credentials"] == Credentials.MISSING.value
