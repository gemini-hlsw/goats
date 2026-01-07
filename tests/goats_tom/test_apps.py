import importlib

import pytest

from goats_tom.apps import GOATSTomConfig


@pytest.fixture
def reset__has_run():
    """Reset GOATSTomConfig._has_run."""
    GOATSTomConfig._has_run = False
    yield
    GOATSTomConfig._has_run = False


@pytest.mark.django_db
def test_ready_calls_bootstrap_and_patches_once(
    mocker,
    reset__has_run,
):
    """
    Test that GOATSTomConfig.ready() calls setup and patches only once.
    """
    setup = mocker.patch("goats_tom.bootstrap.setup_dramatiq_abort")
    apply_all = mocker.patch("goats_tom.patches.apply_all_patches")

    module = importlib.import_module("goats_tom")
    app = GOATSTomConfig("goats_tom", module)

    app.ready()
    app.ready()

    setup.assert_called_once()
    apply_all.assert_called_once()


@pytest.mark.django_db
def test_ready_logs_warning_on_second_call(
    mocker,
    caplog,
    reset__has_run,
):
    """
    Test that GOATSTomConfig.ready() logs a warning if called multiple times.
    """
    mocker.patch("goats_tom.bootstrap.setup_dramatiq_abort")
    mocker.patch("goats_tom.patches.apply_all_patches")

    module = importlib.import_module("goats_tom")
    app = GOATSTomConfig("goats_tom", module)
    app.ready()
    app.ready()

    warnings = [
        r
        for r in caplog.records
        if r.levelname == "WARNING" and r.name == "goats_tom.apps"
    ]

    assert any("ready() called multiple times" in r.message for r in warnings)
