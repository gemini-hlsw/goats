from unittest import mock

import pytest
import requests

from goats_tom.astroquery import Observations, goa_session

COOKIE = "gemini_archive_session"


def test_sessions_do_not_share_logins():
    with goa_session() as first, goa_session() as second:
        first._session.cookies.set(COOKIE, "first-user")

        assert first is not Observations
        assert first._session is not second._session
        assert COOKIE not in second._session.cookies


@pytest.mark.parametrize("error", [None, RuntimeError])
def test_logs_out_and_closes_on_exit(error):
    with mock.patch.object(requests.Session, "close") as close:
        try:
            with goa_session() as goa:
                goa._session.cookies.set(COOKIE, "user")
                goa._authenticated = True
                if error:
                    raise error
        except RuntimeError:
            pass

    close.assert_called_once()
    assert COOKIE not in goa._session.cookies
    assert goa.authenticated() is False
