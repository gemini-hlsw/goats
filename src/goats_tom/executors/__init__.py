"""Executor selection for ANTARES stream consumption.

The ``GOATS_STREAM_EXECUTOR`` setting chooses where consumption runs. It
resolves to ``"local"`` when unset, which is the hard invariant of the Data
Lab offload work: an existing desktop `generated.py` has no such key, must
not raise, and must behave exactly as it does today.

Notes
-----
`DataLabExecutor` is resolved lazily and deliberately not imported here.
Importing `goats_tom.executors` must never pull in `goats_tom.remote` or
`goats_tom.astro_data_lab.headless`, because those depend on the optional
``goats[server]`` extra that a desktop install does not have. A CI guard
asserts this: importing `goats_tom` must not import the Data Lab executor
module.
"""

__all__ = ["LOCAL", "DATALAB", "get_executor", "resolve_executor_name"]

import functools
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import ExecutorHandle, StreamExecutor
from .local import LocalExecutor

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from .datalab import DataLabExecutor

LOCAL = "local"
DATALAB = "datalab"
VALID = frozenset({LOCAL, DATALAB})


def resolve_executor_name() -> str:
    """Return the configured executor name, defaulting to ``"local"``.

    Returns
    -------
    str
        Either ``"local"`` or ``"datalab"``.

    Raises
    ------
    ImproperlyConfigured
        If the setting is present but not a recognised value. Only an
        explicit wrong value raises; absence never does.

    Notes
    -----
    Uses `getattr` with a default rather than attribute access, which is the
    whole point: settings modules generated before this work exists have no
    such attribute, and reading one directly would raise on every desktop
    install.
    """
    name = str(getattr(settings, "GOATS_STREAM_EXECUTOR", "") or LOCAL).strip().lower()
    if name not in VALID:
        raise ImproperlyConfigured(
            f"GOATS_STREAM_EXECUTOR must be one of {sorted(VALID)}, got {name!r}."
        )
    return name


@functools.lru_cache(maxsize=None)
def _build(name: str) -> StreamExecutor:
    """Construct the named executor, importing remote code only if asked."""
    if name == LOCAL:
        return LocalExecutor()
    # Imported here, never at module scope: this is the line that keeps the
    # optional server dependencies off the desktop install path.
    from .datalab import DataLabExecutor  # noqa: PLC0415

    return DataLabExecutor()


def get_executor() -> StreamExecutor:
    """Return the executor selected by ``GOATS_STREAM_EXECUTOR``.

    Returns
    -------
    `StreamExecutor`
        `LocalExecutor` unless the setting explicitly selects ``datalab``.
    """
    return _build(resolve_executor_name())
