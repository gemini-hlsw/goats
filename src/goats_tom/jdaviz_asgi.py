"""ASGI helpers that mount the embedded jdaviz Solara app under ``/jdaviz``.

See :mod:`goats_tom.jdaviz_app` for the Solara component. :func:`init_solara`
imports and initializes Solara as early as possible, and :func:`mount_jdaviz`
wraps the GOATS Channels application so that requests under the ``/jdaviz``
prefix (both HTTP and their websocket connections) are dispatched to Solara --
gated behind an authenticated Django session -- while everything else continues
to the Channels router unchanged. If the jdaviz/Solara stack cannot be imported,
GOATS still boots and only the ``/jdaviz`` viewer is disabled.
"""

from __future__ import annotations

import http.cookies
import logging
import os
import threading
from typing import Any, Awaitable, Callable, MutableMapping

__all__ = ["JDAVIZ_PREFIX", "init_solara", "mount_jdaviz"]

logger = logging.getLogger(__name__)

#: URL prefix the embedded jdaviz viewer is served under.
JDAVIZ_PREFIX = "/jdaviz"

#: Solara's frontend (in jupyter-extension mode) probes readiness at
#: ``<prefix>/solara/readyz``, but the mounted Starlette app serves it at
#: ``<prefix>/readyz``; we rewrite the former to the latter to avoid a benign 404.
READYZ_PROBE_PATH = JDAVIZ_PREFIX + "/solara/readyz"
READYZ_TARGET_PATH = JDAVIZ_PREFIX + "/readyz"

#: Dotted path of the Solara component module Solara serves (the ``SOLARA_APP``).
SOLARA_APP_MODULE = "goats_tom.jdaviz_app"

#: Max websocket message size (bytes) for the dev server's daphne transport.
#: daphne defaults to 1 MiB per message; the embedded jdaviz kernel streams much
#: larger binary widget state (a 2D spectrum, a long 1D, bqplot marks), which
#: trips daphne's ``PayloadExceededError`` and closes the kernel socket mid-load
#: (the viewer then reconnects in a loop). Raised in :func:`init_solara`.
WEBSOCKET_MAX_MESSAGE_SIZE = 64 * 1024 * 1024

#: Third-party loggers (the jdaviz/glue/solara stack) raised to WARNING so their
#: INFO chatter -- glue hub "Subscribing"/"Broadcasting", settings loading,
#: Solara "Executing ..." -- stays out of the GOATS server logs.
# NOISY_LOGGERS = ("glue", "jdaviz", "solara", "reacton", "bqplot")
NOISY_LOGGERS = ("glue", "solara")

# ASGI typing aliases (kept lightweight to avoid a Starlette typing dependency).
Scope = MutableMapping[str, Any]
ASGIApp = Callable[[Scope, Callable, Callable], Awaitable[None]]

# Cache for the one-time Solara initialization: ``tried`` guards re-attempts,
# ``app`` is the Solara ASGI app or ``None`` when the stack is unavailable.
_state: dict[str, Any] = {}
_init_lock = threading.Lock()


def _quiet_jdaviz_logging() -> None:
    """Raise the jdaviz/glue/solara stack loggers to WARNING to cut log noise."""
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def _raise_daphne_ws_message_limit() -> None:
    """Raise daphne's per-message websocket size cap for the embedded viewer.

    daphne's ``runserver`` hardcodes ``Server(...)`` with a 1 MiB
    ``websocket_max_message_size`` and exposes no flag to change it, so the jdaviz
    kernel's larger binary messages get the socket closed mid-load. We patch
    ``daphne.server.Server.__init__`` in place to default the message and frame
    sizes to :data:`WEBSOCKET_MAX_MESSAGE_SIZE`. Patching the class (rather than
    the runserver's ``server_cls``, which daphne resolves before our ASGI module
    is imported) is what actually takes effect at ``Server`` construction time.
    Best-effort: if daphne is absent or its internals differ, GOATS still boots
    (the viewer may then hit the old cap).
    """
    try:
        import daphne.server  # noqa: PLC0415
    except Exception:
        return
    server_cls = daphne.server.Server
    if getattr(server_cls, "_goats_ws_limit_patched", False):
        return
    original_init = server_cls.__init__

    def _init(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("websocket_max_message_size", WEBSOCKET_MAX_MESSAGE_SIZE)
        kwargs.setdefault("websocket_max_frame_size", WEBSOCKET_MAX_MESSAGE_SIZE)
        original_init(self, *args, **kwargs)

    server_cls.__init__ = _init
    server_cls._goats_ws_limit_patched = True
    logger.debug(
        "Raised daphne websocket message limit to %d bytes for %s.",
        WEBSOCKET_MAX_MESSAGE_SIZE,
        JDAVIZ_PREFIX,
    )


def init_solara() -> ASGIApp | None:
    """Import and initialize the embedded Solara stack, returning its ASGI app.

    Call this at the very top of the ASGI module, *before* the Django, Channels
    and GOATS imports. Importing Solara runs reacton's display patching, which
    constructs an IPython ``InteractiveShell``. Doing that first -- at process
    start, in a clean single-threaded context, before any other IPython
    machinery is imported -- avoids an intermittent race that crashes with
    ``module 'IPython' has no attribute 'core'`` (reacton reads ``IPython.core``
    while it is still mid-import elsewhere). Idempotent and thread-safe.

    Returns
    -------
    ASGIApp or None
        The Solara Starlette ASGI application, or ``None`` if the jdaviz/Solara
        stack could not be imported (so GOATS can boot without the viewer).
    """
    if _state.get("tried"):
        return _state.get("app")
    with _init_lock:
        if not _state.get("tried"):
            app = None
            try:
                # Quiet the noisy stack loggers before anything imports glue/jdaviz.
                _quiet_jdaviz_logging()
                os.environ.setdefault("SOLARA_APP", SOLARA_APP_MODULE)
                os.environ.setdefault("SOLARA_ROOT_PATH", JDAVIZ_PREFIX)
                # Serve front-end assets locally (proxied) instead of from a
                # public CDN so the viewer works offline and asset URLs stay
                # under /jdaviz.
                os.environ.setdefault("SOLARA_ASSETS_PROXY", "True")
                # Imported here, not at module top, on purpose: this must run
                # before any other IPython machinery so reacton's display
                # patching wins the race (see the docstring). IPython.core.hooks
                # is forced first so the attribute exists before reacton reads it.
                import IPython.core.hooks  # noqa: PLC0415, F401
                import solara.server.starlette  # noqa: PLC0415

                app = solara.server.starlette.app
                # The viewer is available, so make daphne's websocket able to
                # carry the kernel's large binary messages (see the function).
                _raise_daphne_ws_message_limit()
                logger.debug("Initialized embedded Solara stack at %s", JDAVIZ_PREFIX)
            except Exception:
                logger.exception(
                    "Embedded jdaviz/Solara stack unavailable; the /jdaviz viewer "
                    "is disabled (GOATS continues to run normally)."
                )
                app = None
            _state["app"] = app
            _state["tried"] = True
    return _state.get("app")


def _session_key_from_scope(scope: Scope) -> str | None:
    """Return the Django session key from the request cookies, if present."""
    from django.conf import settings  # noqa: PLC0415

    headers = dict(scope.get("headers") or [])
    cookie_header = headers.get(b"cookie", b"").decode("latin-1")
    if not cookie_header:
        return None
    jar = http.cookies.SimpleCookie()
    try:
        jar.load(cookie_header)
    except http.cookies.CookieError:
        return None
    morsel = jar.get(settings.SESSION_COOKIE_NAME)
    return morsel.value if morsel else None


def _session_has_user(session_key: str) -> bool:
    """Return whether ``session_key`` maps to an authenticated Django session."""
    from importlib import import_module  # noqa: PLC0415

    from django.conf import settings  # noqa: PLC0415
    from django.contrib.auth import SESSION_KEY  # noqa: PLC0415

    engine = import_module(settings.SESSION_ENGINE)
    session = engine.SessionStore(session_key)
    return session.get(SESSION_KEY) is not None


async def _is_authenticated(scope: Scope) -> bool:
    """Return whether the request carries an authenticated Django session."""
    from asgiref.sync import sync_to_async  # noqa: PLC0415

    session_key = _session_key_from_scope(scope)
    if not session_key:
        return False
    try:
        return await sync_to_async(_session_has_user)(session_key)
    except Exception:
        logger.exception("Session lookup failed for a /jdaviz request")
        return False


def _requires_auth(scope_type: str, path: str) -> bool:
    """Return whether a ``/jdaviz`` request must be authenticated.

    The viewer page and every websocket (the kernel that loads the data) are
    gated; static assets are left open so they can be cached normally.
    """
    if scope_type == "websocket":
        return True
    return path in (JDAVIZ_PREFIX, JDAVIZ_PREFIX + "/")


async def _deny(scope_type: str, receive: Callable, send: Callable) -> None:
    """Reject an unauthenticated ``/jdaviz`` request (403 / websocket close)."""
    if scope_type == "websocket":
        await receive()  # consume websocket.connect before closing
        await send({"type": "websocket.close", "code": 4403})
        return
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        }
    )
    await send({"type": "http.response.body", "body": b"Forbidden: please log in."})


def mount_jdaviz(channels_app: ASGIApp) -> ASGIApp:
    """Wrap ``channels_app`` so ``/jdaviz`` is served by Solara.

    Parameters
    ----------
    channels_app : ASGIApp
        The GOATS Channels ``ProtocolTypeRouter`` application.

    Returns
    -------
    ASGIApp
        The ASGI callable to expose as the module-level ``application``. If the
        jdaviz/Solara stack is unavailable, ``channels_app`` is returned
        unchanged so GOATS still serves everything except ``/jdaviz``.
    """
    solara_app = init_solara()
    if solara_app is None:
        logger.warning("Serving GOATS without the embedded /jdaviz viewer.")
        return channels_app
    logger.info(
        "Embedded jdaviz viewer mounted at %s (http+ws -> Solara, auth required).",
        JDAVIZ_PREFIX,
    )

    def _with_root_path(scope: Scope) -> Scope:
        """Return a scope copy declaring ``JDAVIZ_PREFIX`` as the ASGI root_path.

        ``scope["path"]`` is left intact (the full ``/jdaviz/...`` path) and only
        ``root_path`` is set. Starlette's routing strips ``root_path`` from the
        path itself (``get_route_path``), and Solara's ``Mount`` handlers then
        receive the correct sub-path. Stripping the prefix ourselves breaks that
        and makes the CDN proxy build malformed asset URLs.
        """
        new_scope = dict(scope)
        new_scope["root_path"] = JDAVIZ_PREFIX
        return new_scope

    async def application(scope: Scope, receive: Callable, send: Callable) -> None:
        scope_type = scope["type"]
        if scope_type in ("http", "websocket"):
            path = scope.get("path", "")
            if path == JDAVIZ_PREFIX or path.startswith(JDAVIZ_PREFIX + "/"):
                if _requires_auth(scope_type, path) and not await _is_authenticated(
                    scope
                ):
                    await _deny(scope_type, receive, send)
                    return
                forward_scope = _with_root_path(scope)
                if path == READYZ_PROBE_PATH:
                    forward_scope["path"] = READYZ_TARGET_PATH
                    forward_scope["raw_path"] = READYZ_TARGET_PATH.encode()
                await solara_app(forward_scope, receive, send)
                return
        await channels_app(scope, receive, send)

    return application
