"""Tests for the daphne websocket-limit patch in `goats_tom.jdaviz_asgi`.

The patch raises daphne's 1 MiB per-message websocket cap so the embedded
jdaviz viewer can load larger datasets. It does that by injecting keyword
arguments into ``daphne.server.Server.__init__``.

Those arguments only exist in daphne 4.2.2 and later. GOATS gets daphne
transitively through ``channels[daphne]``, which does not constrain its
version, so an older one can be resolved -- conda in particular does its own
solving. Against such a daphne the injection raised
``TypeError: Server.__init__() got an unexpected keyword argument
'websocket_max_message_size'`` at server start, killing the django-main-thread
and taking GOATS down. These tests pin the behaviour on both sides of that
boundary.
"""

import sys
import types

import pytest


@pytest.fixture()
def fake_daphne(monkeypatch):
    """Install a stand-in `daphne.server` module.

    Returns a setter taking a Server class, so each test can supply a
    signature matching the daphne version it cares about.
    """
    module = types.ModuleType("daphne")
    module.__version__ = "0.0.0-test"
    server_module = types.ModuleType("daphne.server")
    module.server = server_module

    monkeypatch.setitem(sys.modules, "daphne", module)
    monkeypatch.setitem(sys.modules, "daphne.server", server_module)

    def _set(server_cls, version="0.0.0-test"):
        module.__version__ = version
        server_module.Server = server_cls
        return server_cls

    return _set


def _patch():
    """Run the patch under test."""
    from goats_tom.jdaviz_asgi import _raise_daphne_ws_message_limit

    _raise_daphne_ws_message_limit()


def test_old_daphne_is_left_alone(fake_daphne):
    """A daphne without the arguments is not patched, and still starts.

    Regression test: this previously raised TypeError at server start-up.
    """

    class OldServer:
        def __init__(self, application, endpoints=None, signal_handlers=True):
            self.application = application

    fake_daphne(OldServer, version="4.2.1")
    _patch()

    assert not getattr(OldServer, "_goats_ws_limit_patched", False)
    # The real failure mode: constructing the server must not raise.
    OldServer(application=None, endpoints=[], signal_handlers=False)


def test_new_daphne_gets_raised_limit(fake_daphne):
    """A daphne that supports the arguments has its limit raised."""
    from goats_tom.jdaviz_asgi import WEBSOCKET_MAX_MESSAGE_SIZE

    class NewServer:
        def __init__(
            self,
            application,
            endpoints=None,
            websocket_max_message_size=1024 * 1024,
            websocket_max_frame_size=1024 * 1024,
        ):
            self.message_size = websocket_max_message_size
            self.frame_size = websocket_max_frame_size

    fake_daphne(NewServer, version="4.2.2")
    _patch()

    server = NewServer(application=None)
    assert server.message_size == WEBSOCKET_MAX_MESSAGE_SIZE
    assert server.frame_size == WEBSOCKET_MAX_MESSAGE_SIZE


def test_explicit_arguments_win(fake_daphne):
    """Caller-supplied values are not overridden.

    The patch sets a default; it must not clobber an explicit choice.
    """

    class NewServer:
        def __init__(
            self,
            application,
            websocket_max_message_size=1024 * 1024,
            websocket_max_frame_size=1024 * 1024,
        ):
            self.message_size = websocket_max_message_size

    fake_daphne(NewServer)
    _patch()

    assert NewServer(application=None, websocket_max_message_size=42).message_size == 42


def test_partial_support(fake_daphne):
    """Only the arguments that exist are injected."""
    from goats_tom.jdaviz_asgi import WEBSOCKET_MAX_MESSAGE_SIZE

    class PartialServer:
        def __init__(self, application, websocket_max_message_size=1024 * 1024):
            self.message_size = websocket_max_message_size

    fake_daphne(PartialServer)
    _patch()

    assert PartialServer(application=None).message_size == WEBSOCKET_MAX_MESSAGE_SIZE


def test_patch_is_idempotent(fake_daphne):
    """Patching twice does not stack wrappers."""

    class NewServer:
        def __init__(self, application, websocket_max_message_size=1024 * 1024):
            self.message_size = websocket_max_message_size

    fake_daphne(NewServer)
    _patch()
    first = NewServer.__init__
    _patch()
    assert NewServer.__init__ is first


def test_missing_daphne_is_tolerated(monkeypatch):
    """No daphne at all is not an error."""
    monkeypatch.setitem(sys.modules, "daphne", None)
    monkeypatch.setitem(sys.modules, "daphne.server", None)
    _patch()


def test_var_keyword_signature_is_supported(fake_daphne):
    """A ``**kwargs`` catch-all counts as accepting the arguments.

    Such a signature accepts any name, so skipping it would leave the limit
    unraised for no reason.
    """
    from goats_tom.jdaviz_asgi import WEBSOCKET_MAX_MESSAGE_SIZE

    class KwargsServer:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

    fake_daphne(KwargsServer)
    _patch()

    server = KwargsServer()
    assert server.kwargs["websocket_max_message_size"] == WEBSOCKET_MAX_MESSAGE_SIZE
    assert server.kwargs["websocket_max_frame_size"] == WEBSOCKET_MAX_MESSAGE_SIZE
