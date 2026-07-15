"""Tests for :mod:`goats_tom.jdaviz_asgi`.

Covers the auth gate, request routing and Solara mounting logic that exposes the
embedded jdaviz viewer under ``/jdaviz``. The Solara stack itself is never
constructed here; ``init_solara`` is stubbed so the dispatcher can be exercised
in isolation.
"""

import pytest

from goats_tom import jdaviz_asgi
from goats_tom.jdaviz_asgi import (
    JDAVIZ_PREFIX,
    SOLARA_APP_MODULE,
    WEBSOCKET_MAX_MESSAGE_SIZE,
    READYZ_PROBE_PATH,
    READYZ_TARGET_PATH,
    _deny,
    _is_authenticated,
    _quiet_jdaviz_logging,
    _raise_daphne_ws_message_limit,
    _requires_auth,
    _session_has_user,
    _session_key_from_scope,
    init_solara,
    mount_jdaviz,
)


def _http_scope(path, cookie=None):
    """Build a minimal ASGI HTTP scope, optionally with a Cookie header."""
    headers = []
    if cookie is not None:
        headers.append((b"cookie", cookie.encode("latin-1")))
    return {"type": "http", "path": path, "headers": headers}


class _Recorder:
    """Collects ASGI messages passed to ``send`` and feeds canned ``receive``s."""

    def __init__(self):
        self.sent = []
        self.received = 0

    async def send(self, message):
        self.sent.append(message)

    async def receive(self):
        self.received += 1
        return {"type": "websocket.connect"}



class TestRequiresAuth:
    def test_websocket_always_requires_auth(self):
        assert _requires_auth("websocket", JDAVIZ_PREFIX + "/anything") is True

    def test_viewer_page_requires_auth(self):
        assert _requires_auth("http", JDAVIZ_PREFIX) is True

    def test_viewer_page_with_trailing_slash_requires_auth(self):
        assert _requires_auth("http", JDAVIZ_PREFIX + "/") is True

    def test_static_asset_is_open(self):
        assert _requires_auth("http", JDAVIZ_PREFIX + "/static/app.js") is False



class TestSessionKeyFromScope:
    def test_no_cookie_header_returns_none(self):
        assert _session_key_from_scope(_http_scope(JDAVIZ_PREFIX)) is None

    def test_returns_session_value(self):
        scope = _http_scope(JDAVIZ_PREFIX, cookie="sessionid=abc123")
        assert _session_key_from_scope(scope) == "abc123"

    def test_other_cookies_without_session_returns_none(self):
        scope = _http_scope(JDAVIZ_PREFIX, cookie="csrftoken=zzz")
        assert _session_key_from_scope(scope) is None

    def test_session_among_several_cookies(self):
        scope = _http_scope(
            JDAVIZ_PREFIX, cookie="csrftoken=zzz; sessionid=abc123; theme=dark"
        )
        assert _session_key_from_scope(scope) == "abc123"

    def test_cookie_parse_error_returns_none(self, monkeypatch):
        import http.cookies

        class ExplodingCookie(http.cookies.SimpleCookie):
            def load(self, rawdata):
                raise http.cookies.CookieError("bad cookie")

        monkeypatch.setattr(http.cookies, "SimpleCookie", ExplodingCookie)
        scope = _http_scope(JDAVIZ_PREFIX, cookie="sessionid=abc123")
        assert _session_key_from_scope(scope) is None



class TestSessionHasUser:
    @staticmethod
    def _session_store():
        from importlib import import_module

        from django.conf import settings

        return import_module(settings.SESSION_ENGINE).SessionStore

    @pytest.mark.django_db
    def test_session_with_user_is_true(self):
        from django.contrib.auth import SESSION_KEY

        session = self._session_store()()
        session[SESSION_KEY] = "1"
        session.create()
        assert _session_has_user(session.session_key) is True

    @pytest.mark.django_db
    def test_session_without_user_is_false(self):
        session = self._session_store()()
        session["something-else"] = "x"
        session.create()
        assert _session_has_user(session.session_key) is False

    @pytest.mark.django_db
    def test_unknown_session_key_is_false(self):
        assert _session_has_user("does-not-exist") is False



class TestDeny:
    @pytest.mark.asyncio()
    async def test_http_deny_sends_403(self):
        rec = _Recorder()
        await _deny("http", rec.receive, rec.send)
        start, body = rec.sent
        assert start["type"] == "http.response.start"
        assert start["status"] == 403
        assert body["type"] == "http.response.body"
        assert b"log in" in body["body"]

    @pytest.mark.asyncio()
    async def test_websocket_deny_consumes_connect_then_closes(self):
        rec = _Recorder()
        await _deny("websocket", rec.receive, rec.send)
        # The connect message must be consumed before closing.
        assert rec.received == 1
        assert rec.sent == [{"type": "websocket.close", "code": 4403}]


class TestIsAuthenticated:
    @pytest.mark.asyncio()
    async def test_no_session_key_is_unauthenticated(self, monkeypatch):
        monkeypatch.setattr(jdaviz_asgi, "_session_key_from_scope", lambda scope: None)
        assert await _is_authenticated({}) is False

    @pytest.mark.asyncio()
    async def test_valid_session_with_user_is_authenticated(self, monkeypatch):
        monkeypatch.setattr(jdaviz_asgi, "_session_key_from_scope", lambda scope: "k")
        monkeypatch.setattr(jdaviz_asgi, "_session_has_user", lambda key: True)
        assert await _is_authenticated({}) is True

    @pytest.mark.asyncio()
    async def test_session_without_user_is_unauthenticated(self, monkeypatch):
        monkeypatch.setattr(jdaviz_asgi, "_session_key_from_scope", lambda scope: "k")
        monkeypatch.setattr(jdaviz_asgi, "_session_has_user", lambda key: False)
        assert await _is_authenticated({}) is False

    @pytest.mark.asyncio()
    async def test_lookup_error_is_unauthenticated(self, monkeypatch):
        def boom(key):
            raise RuntimeError("db down")

        monkeypatch.setattr(jdaviz_asgi, "_session_key_from_scope", lambda scope: "k")
        monkeypatch.setattr(jdaviz_asgi, "_session_has_user", boom)
        assert await _is_authenticated({}) is False


class TestInitSolara:
    @pytest.fixture(autouse=True)
    def _reset_state(self):
        """Restore the module-level init cache around each test."""
        saved = dict(jdaviz_asgi._state)
        jdaviz_asgi._state.clear()
        yield
        jdaviz_asgi._state.clear()
        jdaviz_asgi._state.update(saved)

    def test_returns_cached_app_without_reimporting(self):
        sentinel = object()
        jdaviz_asgi._state["tried"] = True
        jdaviz_asgi._state["app"] = sentinel
        assert init_solara() is sentinel

    def test_cached_none_is_returned(self):
        jdaviz_asgi._state["tried"] = True
        jdaviz_asgi._state["app"] = None
        assert init_solara() is None

    def test_failed_initialization_disables_viewer_and_is_cached(self, monkeypatch):
        def boom():
            raise ImportError("solara stack unavailable")

        monkeypatch.setattr(jdaviz_asgi, "_quiet_jdaviz_logging", boom)
        assert init_solara() is None

        # The failure must be cached: a later call may not retry the init.
        monkeypatch.setattr(
            jdaviz_asgi,
            "_quiet_jdaviz_logging",
            lambda: pytest.fail("init must not be retried after a failure"),
        )
        assert init_solara() is None

    def test_successful_initialization_returns_app_and_sets_env(self, monkeypatch):
        import os
        import sys
        import types

        # Fake the solara.server.starlette module chain so no real Solara
        # (kernel manager, asset proxy, ...) is started by the import.
        sentinel = object()
        starlette_mod = types.ModuleType("solara.server.starlette")
        starlette_mod.app = sentinel
        server_mod = types.ModuleType("solara.server")
        server_mod.starlette = starlette_mod
        solara_mod = types.ModuleType("solara")
        solara_mod.server = server_mod
        monkeypatch.setitem(sys.modules, "solara", solara_mod)
        monkeypatch.setitem(sys.modules, "solara.server", server_mod)
        monkeypatch.setitem(sys.modules, "solara.server.starlette", starlette_mod)

        # Keep the daphne patch from mutating the real daphne class.
        patched = []
        monkeypatch.setattr(
            jdaviz_asgi,
            "_raise_daphne_ws_message_limit",
            lambda: patched.append(True),
        )

        # setenv-then-delenv registers the original value for restore, then
        # clears the variable so the setdefaults in init_solara take effect.
        for var in ("SOLARA_APP", "SOLARA_ROOT_PATH", "SOLARA_ASSETS_PROXY"):
            monkeypatch.setenv(var, "sentinel")
            monkeypatch.delenv(var)

        assert init_solara() is sentinel
        assert os.environ["SOLARA_APP"] == SOLARA_APP_MODULE
        assert os.environ["SOLARA_ROOT_PATH"] == JDAVIZ_PREFIX
        assert os.environ["SOLARA_ASSETS_PROXY"] == "True"
        assert patched == [True]


class TestRaiseDaphneWsMessageLimit:
    @pytest.fixture()
    def fake_daphne(self, monkeypatch):
        """Install a fake ``daphne.server`` so the real class is never patched."""
        import sys
        import types

        server_mod = types.ModuleType("daphne.server")

        class Server:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        server_mod.Server = Server
        daphne_mod = types.ModuleType("daphne")
        daphne_mod.server = server_mod
        monkeypatch.setitem(sys.modules, "daphne", daphne_mod)
        monkeypatch.setitem(sys.modules, "daphne.server", server_mod)
        return server_mod

    def test_defaults_message_and_frame_sizes(self, fake_daphne):
        _raise_daphne_ws_message_limit()
        server = fake_daphne.Server()
        assert server.kwargs["websocket_max_message_size"] == (
            WEBSOCKET_MAX_MESSAGE_SIZE
        )
        assert server.kwargs["websocket_max_frame_size"] == WEBSOCKET_MAX_MESSAGE_SIZE

    def test_explicit_kwargs_are_not_overridden(self, fake_daphne):
        _raise_daphne_ws_message_limit()
        server = fake_daphne.Server(websocket_max_message_size=5)
        assert server.kwargs["websocket_max_message_size"] == 5

    def test_patch_is_idempotent(self, fake_daphne):
        _raise_daphne_ws_message_limit()
        patched_init = fake_daphne.Server.__init__
        _raise_daphne_ws_message_limit()
        assert fake_daphne.Server.__init__ is patched_init

    def test_missing_daphne_is_noop(self, monkeypatch):
        import sys

        # A None entry in sys.modules makes ``import daphne.server`` raise.
        monkeypatch.setitem(sys.modules, "daphne", None)
        monkeypatch.setitem(sys.modules, "daphne.server", None)
        _raise_daphne_ws_message_limit()



class TestMountJdaviz:
    @staticmethod
    def _channels_app():
        """A fake downstream Channels app that records the scope it receives."""
        calls = []

        async def app(scope, receive, send):
            calls.append(scope)

        app.calls = calls
        return app

    @staticmethod
    def _solara_app():
        """A fake Solara app that records the scope it receives."""
        calls = []

        async def app(scope, receive, send):
            calls.append(scope)

        app.calls = calls
        return app

    def test_returns_channels_app_unchanged_when_solara_unavailable(self, monkeypatch):
        monkeypatch.setattr(jdaviz_asgi, "init_solara", lambda: None)
        channels = self._channels_app()
        assert mount_jdaviz(channels) is channels

    @pytest.mark.asyncio()
    async def test_non_jdaviz_request_goes_to_channels(self, monkeypatch):
        solara = self._solara_app()
        monkeypatch.setattr(jdaviz_asgi, "init_solara", lambda: solara)
        channels = self._channels_app()
        app = mount_jdaviz(channels)

        rec = _Recorder()
        await app({"type": "http", "path": "/targets/"}, rec.receive, rec.send)

        assert len(channels.calls) == 1
        assert solara.calls == []

    @pytest.mark.asyncio()
    async def test_authenticated_viewer_request_goes_to_solara(self, monkeypatch):
        solara = self._solara_app()
        monkeypatch.setattr(jdaviz_asgi, "init_solara", lambda: solara)

        async def authed(scope):
            return True

        monkeypatch.setattr(jdaviz_asgi, "_is_authenticated", authed)
        channels = self._channels_app()
        app = mount_jdaviz(channels)

        rec = _Recorder()
        await app(_http_scope(JDAVIZ_PREFIX), rec.receive, rec.send)

        assert len(solara.calls) == 1
        assert channels.calls == []
        # The forwarded scope declares the prefix as root_path but keeps the path.
        forwarded = solara.calls[0]
        assert forwarded["root_path"] == JDAVIZ_PREFIX
        assert forwarded["path"] == JDAVIZ_PREFIX

    @pytest.mark.asyncio()
    async def test_unauthenticated_viewer_request_is_denied(self, monkeypatch):
        solara = self._solara_app()
        monkeypatch.setattr(jdaviz_asgi, "init_solara", lambda: solara)

        async def not_authed(scope):
            return False

        monkeypatch.setattr(jdaviz_asgi, "_is_authenticated", not_authed)
        app = mount_jdaviz(self._channels_app())

        rec = _Recorder()
        await app(_http_scope(JDAVIZ_PREFIX), rec.receive, rec.send)

        assert solara.calls == []
        assert rec.sent[0]["status"] == 403

    @pytest.mark.asyncio()
    async def test_unauthenticated_websocket_is_denied(self, monkeypatch):
        solara = self._solara_app()
        monkeypatch.setattr(jdaviz_asgi, "init_solara", lambda: solara)

        async def not_authed(scope):
            return False

        monkeypatch.setattr(jdaviz_asgi, "_is_authenticated", not_authed)
        app = mount_jdaviz(self._channels_app())

        rec = _Recorder()
        scope = {"type": "websocket", "path": JDAVIZ_PREFIX + "/ws", "headers": []}
        await app(scope, rec.receive, rec.send)

        assert solara.calls == []
        assert rec.sent == [{"type": "websocket.close", "code": 4403}]

    @pytest.mark.asyncio()
    async def test_open_static_asset_skips_auth(self, monkeypatch):
        solara = self._solara_app()
        monkeypatch.setattr(jdaviz_asgi, "init_solara", lambda: solara)

        async def fail(scope):
            raise AssertionError("auth must not be checked for static assets")

        monkeypatch.setattr(jdaviz_asgi, "_is_authenticated", fail)
        app = mount_jdaviz(self._channels_app())

        rec = _Recorder()
        await app(_http_scope(JDAVIZ_PREFIX + "/static/app.js"), rec.receive, rec.send)

        assert len(solara.calls) == 1

    @pytest.mark.asyncio()
    async def test_readyz_probe_path_is_rewritten(self, monkeypatch):
        solara = self._solara_app()
        monkeypatch.setattr(jdaviz_asgi, "init_solara", lambda: solara)
        app = mount_jdaviz(self._channels_app())

        rec = _Recorder()
        await app(_http_scope(READYZ_PROBE_PATH), rec.receive, rec.send)

        forwarded = solara.calls[0]
        assert forwarded["path"] == READYZ_TARGET_PATH
        assert forwarded["raw_path"] == READYZ_TARGET_PATH.encode()



def test_quiet_jdaviz_logging_raises_levels_to_warning():
    import logging

    saved = {name: logging.getLogger(name).level for name in jdaviz_asgi.NOISY_LOGGERS}
    try:
        for name in jdaviz_asgi.NOISY_LOGGERS:
            logging.getLogger(name).setLevel(logging.DEBUG)
        _quiet_jdaviz_logging()
        for name in jdaviz_asgi.NOISY_LOGGERS:
            assert logging.getLogger(name).level == logging.WARNING
    finally:
        for name, level in saved.items():
            logging.getLogger(name).setLevel(level)
