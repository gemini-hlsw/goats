"""Executor interface for ANTARES stream consumption.

An executor owns *where* a subscription's stream consumption runs. The
`LocalExecutor` enqueues today's Dramatiq actor on the GOATS host; the
`DataLabExecutor` launches a windowed job on Astro Data Lab under the PI's
own account.

Notes
-----
`antares_stream_control` keeps everything an executor must not know about:
`generation` and `run_number` advancement, the abort-then-restart ordering,
and all field updates on the subscription row. An executor is handed an
already-saved row and an already-advanced generation, and is responsible
only for starting and stopping work. This is what lets `datalab` mode reuse
the fencing semantics verbatim instead of reimplementing them.
"""

__all__ = ["ExecutorHandle", "StreamExecutor"]

import abc
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ExecutorHandle:
    """Backend-neutral identifier for started work.

    Attributes
    ----------
    kind : str
        Executor that produced this handle, ``"local"`` or ``"datalab"``.
    message_id : str, optional
        Dramatiq message id. Local mode only.
    remote_job_id : int, optional
        Primary key of a `RemoteJob` row. Datalab mode only.
    detail : dict
        Backend-specific extras, for logging and debugging only.

    Notes
    -----
    Two optional fields rather than one opaque string because the local
    value is already persisted as `AntaresStreamSubscription.dramatiq_message_id`
    and must keep going there unchanged -- the hard invariant forbids
    migrating that column. Remote handles are stored on `RemoteJob` instead,
    leaving `dramatiq_message_id` null in `datalab` mode.
    """

    kind: str
    message_id: Optional[str] = None
    remote_job_id: Optional[int] = None
    detail: dict[str, Any] = field(default_factory=dict)


class StreamExecutor(abc.ABC):
    """Start, stop and inspect stream consumption for a subscription."""

    #: Short name, matching the ``GOATS_STREAM_EXECUTOR`` value.
    name: str = ""

    @abc.abstractmethod
    def start(self, subscription, generation: int) -> ExecutorHandle:
        """Begin consuming for `subscription` at `generation`.

        Parameters
        ----------
        subscription : `AntaresStreamSubscription`
            Row already saved with the current run's configuration.
        generation : int
            Fencing token this run must carry. Any write it attempts after
            the subscription's generation has moved on is rejected.

        Returns
        -------
        `ExecutorHandle`
            Handle identifying the started work.
        """

    @abc.abstractmethod
    def stop(self, subscription) -> None:
        """Best-effort halt of `subscription`'s running work.

        Notes
        -----
        Best-effort in both modes, and deliberately so. Correctness comes
        from the generation fencing token, never from this call -- locally
        because `dramatiq_abort` cannot interrupt a blocking Kafka call, and
        remotely because a detached runner has no process API at all.
        Implementations must not raise on failure to stop.
        """

    @abc.abstractmethod
    def status(self, subscription) -> dict[str, Any]:
        """Return a display-oriented status mapping for `subscription`.

        Returns
        -------
        dict
            At minimum ``{"running": bool}``.
        """
