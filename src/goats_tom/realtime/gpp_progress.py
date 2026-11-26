"""Sends the progress of a request to GPP, one step at a time, to the page that
made it."""

__all__ = ["GPPProgress"]

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .groups import UPDATES_PREFIX, user_group

logger = logging.getLogger(__name__)


class GPPProgress:
    """Progress of one request to GPP, as its steps end.

    The page names the request with an id it sends along, so that it can tell
    its own progress from that of a request made in another tab. The progress
    only shows each step as it happens: the response still carries the result, so
    a lost update changes nothing but when a step is shown.

    Parameters
    ----------
    user_id : `int | None`
        The user who made the request; only they receive its progress.
    progress_id : `str | None`
        The id the page gave the request; without one, nothing is sent.
    """

    func_type = "gpp.progress"

    def __init__(self, user_id: int | None, progress_id: str | None) -> None:
        self.user_id = user_id
        self.progress_id = progress_id

    def send(self, stage: str, status: str, message: str) -> None:
        """Sends that a stage of the request ended.

        Parameters
        ----------
        stage : `str`
            The stage that ended, e.g. ``"Update Observation"``.
        status : `str`
            How it ended, e.g. ``"Success"`` or ``"Error"``.
        message : `str`
            What there is to say about it.
        """
        if not self.progress_id:
            return
        group = user_group(UPDATES_PREFIX, self.user_id)
        if group is None:
            # Dropped rather than broadcast: better lost than shown to all.
            return
        try:
            async_to_sync(get_channel_layer().group_send)(
                group,
                {
                    "type": self.func_type,
                    "progress_id": self.progress_id,
                    "stage": stage,
                    "status": status,
                    "message": message,
                },
            )
        except Exception:
            # The response carries the result; progress is not worth failing for.
            logger.warning("Could not send GPP progress for %s.", stage, exc_info=True)
