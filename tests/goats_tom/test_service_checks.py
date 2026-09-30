from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

from goats_tom import service_checks
from goats_tom.service_checks import (
    CheckResult,
    check_astro_datalab,
    check_goa,
    check_gpp,
    check_lco,
    check_gpp_reachable,
    check_reachable,
)


@pytest.fixture
def server_answers():
    """Failed checks ask the server if it is up; say it is, without the network."""
    with patch(
        "goats_tom.service_checks.check_reachable",
        return_value=CheckResult(True, "X is available."),
    ) as mock:
        yield mock


class TestFailedChecksTellRejectedFromDown:
    @patch("goats_tom.service_checks.check_reachable")
    @patch("goats_tom.service_checks.ObservationsClass")
    def test_public_page_does_not_prove_authentication_rejection(self, mock_cls, mock_reachable):
        mock_cls.return_value.authenticated.return_value = False
        mock_reachable.return_value = CheckResult(True, "X is available.")

        result = check_goa("user", "bad")

        assert not result.ok
        assert not result.verified
        assert result.reachable is True

    @patch("goats_tom.service_checks.check_reachable")
    @patch("goats_tom.service_checks.ObservationsClass")
    def test_unreachable_when_server_is_silent(self, mock_cls, mock_reachable):
        mock_cls.return_value.authenticated.return_value = False
        mock_reachable.return_value = CheckResult(
            False, "GOA is not available.", reachable=False
        )

        result = check_goa("user", "pass")

        assert result == CheckResult(False, "GOA is not available.", reachable=False)

    @patch("goats_tom.service_checks.check_reachable")
    @patch("goats_tom.service_checks.GPPClient")
    def test_gpp_asks_its_base_url(self, mock_client_cls, mock_reachable):
        client = mock_client_cls.return_value
        client.close = AsyncMock()
        client.graphql.__aenter__.return_value = client.graphql
        client.graphql.ping = AsyncMock(side_effect=RuntimeError("network"))
        from gpp_client.settings import GPPSettings
        expected_url = GPPSettings().environment.base_url
        mock_reachable.return_value = CheckResult(False, "x", reachable=False)

        assert check_gpp("token").reachable is False
        mock_reachable.assert_called_once_with(expected_url, "GPP")


@pytest.mark.usefixtures("server_answers")
class TestCheckGPP:
    @patch("goats_tom.service_checks.GPPClient")
    def test_reachable(self, mock_client_cls):
        mock_client_cls.return_value.close = AsyncMock()
        mock_client_cls.return_value.graphql.__aenter__.return_value = mock_client_cls.return_value.graphql
        mock_client_cls.return_value.graphql.ping = AsyncMock(return_value=None)

        assert check_gpp("token") == CheckResult(True, "GPP accepted the token.")
        mock_client_cls.assert_called_once_with(token="token", debug=False)

    @patch("goats_tom.service_checks.GPPClient")
    def test_unreachable(self, mock_client_cls):
        mock_client_cls.return_value.close = AsyncMock()
        mock_client_cls.return_value.graphql.__aenter__.return_value = mock_client_cls.return_value.graphql
        mock_client_cls.return_value.graphql.ping = AsyncMock(side_effect=RuntimeError("network"))

        result = check_gpp("token")

        assert not result.ok
        assert not result.verified

    @patch("goats_tom.service_checks.GPPClient")
    def test_raises(self, mock_client_cls):
        mock_client_cls.return_value.close = AsyncMock()
        mock_client_cls.return_value.graphql.__aenter__.return_value = mock_client_cls.return_value.graphql
        mock_client_cls.return_value.graphql.ping = AsyncMock(side_effect=RuntimeError("network"))

        assert check_gpp("token").ok is False


@pytest.mark.usefixtures("server_answers")
class TestCheckGOA:
    @patch("goats_tom.service_checks.ObservationsClass")
    def test_accepted_uses_private_session(self, mock_cls):
        goa = mock_cls.return_value
        goa.authenticated.return_value = True

        assert check_goa("user", "pass").ok is True
        goa.login.assert_called_once_with("user", "pass")
        goa.logout.assert_called_once()

    @patch("goats_tom.service_checks.ObservationsClass")
    def test_rejected(self, mock_cls):
        mock_cls.return_value.authenticated.return_value = False

        assert check_goa("user", "bad").ok is False


@pytest.mark.usefixtures("server_answers")
class TestCheckAstroDatalab:
    @patch("goats_tom.service_checks.AstroDataLabClient")
    def test_accepted(self, mock_cls):
        client = mock_cls.return_value.__enter__.return_value
        client.is_logged_in.return_value = True

        assert check_astro_datalab("user", "pass").ok is True

    @patch("goats_tom.service_checks.AstroDataLabClient")
    def test_token_not_valid(self, mock_cls):
        client = mock_cls.return_value.__enter__.return_value
        client.is_logged_in.return_value = False

        assert check_astro_datalab("user", "pass").ok is False

    @patch("goats_tom.service_checks.AstroDataLabClient")
    def test_login_raises(self, mock_cls):
        client = mock_cls.return_value.__enter__.return_value
        client.login.side_effect = requests.HTTPError("401", response=MagicMock(status_code=401))

        result = check_astro_datalab("user", "bad")

        assert result == CheckResult(False, "Astro Data Lab rejected the credentials.")


@pytest.mark.usefixtures("server_answers")
class TestCheckLCO:
    @patch("goats_tom.service_checks.requests.get")
    def test_accepted(self, mock_get):
        assert check_lco("key").ok is True
        _, kwargs = mock_get.call_args
        assert kwargs["headers"] == {"Authorization": "Token key"}
        assert kwargs["timeout"] == service_checks.TIMEOUT

    @patch("goats_tom.service_checks.requests.get")
    def test_rejected(self, mock_get):
        mock_get.return_value.raise_for_status.side_effect = requests.HTTPError("403", response=MagicMock(status_code=403))

        assert check_lco("bad").ok is False


class TestCheckReachable:
    @patch("goats_tom.service_checks.requests.get")
    def test_client_error_is_inconclusive(self, mock_get):
        mock_get.return_value = MagicMock(status_code=404)

        result = check_reachable("https://x", "X")
        assert not result.ok and result.reachable and not result.verified

    @patch("goats_tom.service_checks.requests.get")
    def test_server_error_is_down(self, mock_get):
        mock_get.return_value = MagicMock(status_code=503)

        assert check_reachable("https://x", "X").ok is False

    @patch("goats_tom.service_checks.requests.get")
    def test_connection_error_is_down(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("refused")

        result = check_reachable("https://x", "X")

        assert result.ok is False
        assert result.reachable is False
        # The error itself is only logged.
        assert result.message == "X is not available."


@pytest.mark.parametrize("code", [429, 500, 503])
def test_api_errors_do_not_reject_credentials_when_homepage_works(code):
    api = MagicMock(status_code=code)
    api.raise_for_status.side_effect = requests.HTTPError(response=api)
    homepage = MagicMock(status_code=200)
    with patch("goats_tom.service_checks.requests.get", side_effect=[api, homepage]):
        result = check_lco("token")
    assert not result.ok
    assert result.reachable
    assert not result.verified
    assert "rejected" not in result.message


@pytest.mark.parametrize("code", [401, 403])
def test_explicit_authentication_rejection_needs_no_public_probe(code):
    response = MagicMock(status_code=code)
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    with patch("goats_tom.service_checks.requests.get", return_value=response) as get:
        result = check_lco("token")
    assert result == CheckResult(False, "LCO rejected the API key.")
    assert get.call_count == 1


def test_api_timeout_with_working_homepage_is_inconclusive():
    with patch("goats_tom.service_checks.requests.get", side_effect=[
        requests.Timeout(), MagicMock(status_code=200)
    ]):
        result = check_lco("token")
    assert not result.ok and not result.verified


def test_datalab_failures_never_log_tokens(caplog, server_answers):
    import logging
    with patch("goats_tom.service_checks.AstroDataLabClient") as cls:
        client = cls.return_value.__enter__.return_value
        client.is_logged_in.side_effect = requests.HTTPError(
            "503 at https://example.test/check?token=PRIVATE_TEST_TOKEN",
            response=MagicMock(status_code=503),
        )
        with caplog.at_level(logging.INFO, logger="goats_tom.service_checks"):
            result = check_astro_datalab("user", "password")
    assert not result.ok
    assert "PRIVATE_TEST_TOKEN" not in caplog.text
    assert "HTTP 503" in caplog.text


@pytest.mark.parametrize("code", [401, 403, 404, 429])
def test_public_client_errors_are_not_claimed_as_available(code):
    with patch("goats_tom.service_checks.requests.get", return_value=MagicMock(status_code=code)):
        result = check_reachable("https://example.test", "Example")
    assert not result.ok and result.reachable and not result.verified


def test_gpp_retains_http_rejection_and_closes_connections():
    from gpp_client.generated.exceptions import GraphQLClientHttpError
    with patch("goats_tom.service_checks.GPPClient") as cls:
        client = cls.return_value
        client.graphql.__aenter__.return_value = client.graphql
        client.close = AsyncMock()
        client.graphql.ping = AsyncMock(side_effect=GraphQLClientHttpError(401, MagicMock(status_code=401)))
        result = check_gpp("token")
    assert result == CheckResult(False, "GPP rejected the token.")
    client.close.assert_awaited_once()
    client.graphql.__aexit__.assert_awaited_once()


@pytest.mark.parametrize("http_code, body, rejected", [
    (200, "Log-in did not succeed", True),
    (401, "denied", True),
    (503, "maintenance", False),
])
def test_goa_retains_authentication_outcome_and_uses_timeout(http_code, body, rejected, server_answers):
    from goats_tom.astroquery import ObservationsClass
    goa = ObservationsClass()
    with patch.object(goa._session, "post", return_value=MagicMock(status_code=http_code, text=body)) as post:
        assert goa._login("user", "password") is False
    assert goa.login_rejected is rejected
    assert post.call_args.kwargs["timeout"] == 10
    goa._session.close()


def test_goa_explicit_rejection_needs_no_public_probe(server_answers):
    with patch("goats_tom.service_checks.ObservationsClass") as cls:
        cls.return_value.authenticated.return_value = False
        cls.return_value.login_rejected = True
        assert check_goa("user", "password") == CheckResult(False, "GOA rejected the credentials.")
    server_answers.assert_not_called()


@patch("goats_tom.service_checks.requests.get")
def test_check_reachable_sends_extra_headers(mock_get):
    mock_get.return_value = MagicMock(status_code=200)

    check_reachable("https://x", "X", {"User-Agent": "bot"})

    assert mock_get.call_args.kwargs["headers"] == {"User-Agent": "bot"}


class TestCheckGPPReachable:
    """Without a token, a GraphQL error from GPP still shows it is up."""

    @patch("goats_tom.service_checks.requests.post")
    def test_graphql_error_means_up(self, mock_post):
        mock_post.return_value = MagicMock(status_code=422)
        mock_post.return_value.json.return_value = {
            "errors": [{"message": "Field 'programs' requires authentication."}]
        }

        assert check_gpp_reachable() == CheckResult(True, "GPP is available.")
        assert "query ping" in mock_post.call_args.kwargs["json"]["query"]

    @patch("goats_tom.service_checks.requests.post")
    def test_server_error_means_down(self, mock_post):
        mock_post.return_value = MagicMock(status_code=503)

        assert check_gpp_reachable().reachable is False

    @patch("goats_tom.service_checks.requests.post")
    def test_non_graphql_answer_means_down(self, mock_post):
        mock_post.return_value = MagicMock(status_code=404)
        mock_post.return_value.json.side_effect = ValueError("html")

        assert check_gpp_reachable().reachable is False

    @patch("goats_tom.service_checks.requests.post")
    def test_no_answer_means_down(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("refused")

        assert check_gpp_reachable() == CheckResult(
            False, "GPP is not available.", reachable=False
        )
