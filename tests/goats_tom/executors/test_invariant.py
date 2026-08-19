"""Guards on the hard invariant of the Data Lab offload.

With ``GOATS_STREAM_EXECUTOR`` unset, a desktop install must behave exactly
as it did before this work existed. These tests are cheap and unglamorous
and are the whole reason the seam can be trusted: the failure they catch is
silent -- a desktop user's stream quietly routing somewhere it cannot reach,
or an ``ImportError`` at startup from a dependency they were never asked to
install.
"""

import os
import subprocess
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from goats_tom.executors import DATALAB, LOCAL, get_executor, resolve_executor_name
from goats_tom.executors.local import LocalExecutor


class TestExecutorDefault:
    """The setting must default to local, not merely usually be local."""

    def test_resolves_to_local_when_setting_absent(self, settings):
        """An older `generated.py` has no such key and must not raise."""
        if hasattr(settings, "GOATS_STREAM_EXECUTOR"):
            del settings.GOATS_STREAM_EXECUTOR
        assert resolve_executor_name() == LOCAL
        assert isinstance(get_executor(), LocalExecutor)

    @override_settings(GOATS_STREAM_EXECUTOR="")
    def test_empty_string_is_local(self):
        """An unset-but-present env var must not be treated as invalid."""
        assert resolve_executor_name() == LOCAL

    @override_settings(GOATS_STREAM_EXECUTOR="  LOCAL  ")
    def test_value_is_normalised(self):
        """Whitespace and case must not change routing."""
        assert resolve_executor_name() == LOCAL

    @override_settings(GOATS_STREAM_EXECUTOR="datalabb")
    def test_unrecognised_value_raises(self):
        """A typo must fail loudly rather than silently running locally.

        The asymmetry is deliberate: absence is a supported configuration,
        a misspelling is not. Silently falling back would strand a server
        deployment on the local path with no signal.
        """
        with pytest.raises(ImproperlyConfigured):
            resolve_executor_name()

    @override_settings(GOATS_STREAM_EXECUTOR=DATALAB)
    def test_datalab_is_a_recognised_value(self):
        """Guards the constant itself against drift."""
        assert resolve_executor_name() == DATALAB


class TestNoRemoteImportOnDesktop:
    """Importing GOATS must not drag in the optional server dependencies."""

    def test_importing_goats_tom_does_not_import_datalab_executor(self):
        """The lazy resolution in `executors.__init__` must actually be lazy.

        Run in a subprocess rather than inspecting `sys.modules` in-process:
        by the time this test runs, the rest of the suite has imported a
        great deal, and an assertion about the current interpreter's module
        table would prove nothing about a fresh desktop start-up.
        """
        code = (
            "import sys\n"
            "import goats_tom.executors\n"
            "goats_tom.executors.get_executor()\n"
            "leaked = [m for m in sys.modules if 'executors.datalab' in m "
            "or 'astro_data_lab.headless' in m or 'goats_tom.remote' in m]\n"
            "print(','.join(leaked))\n"
        )
        # Inherit the environment rather than replacing it. A bare env loses
        # PYTHONPATH and the virtualenv, so the subprocess fails to import
        # goats_tom at all -- which would look like a guard failure while
        # actually testing nothing.
        env = {**os.environ, "DJANGO_SETTINGS_MODULE": "goats_tom.tests.settings"}
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "", (
            f"Desktop import path pulled in server-only modules: {result.stdout}"
        )
