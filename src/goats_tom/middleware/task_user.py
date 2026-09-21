"""
Dramatiq middleware that carries the enqueuing user into the worker.

``UserContextMiddleware`` only covers HTTP requests, and a ``ContextVar`` does
not cross into the worker process. Without this, every notification emitted
from a background task has no user to address.
"""

import logging
from contextvars import Token

from dramatiq import Broker, Message
from dramatiq.middleware import Middleware

from goats_tom.context.user_context import (
    get_current_user_id,
    reset_current_user_id,
    set_current_user_id,
)

__all__ = ["TaskUserContextMiddleware"]

logger = logging.getLogger(__name__)


class TaskUserContextMiddleware(Middleware):
    """Bind the user who enqueued a task while the worker runs it."""

    option_key = "goats_user_id"
    """Key the user ID travels under in the message options."""

    def __init__(self) -> None:
        # Keyed by message: worker threads must restore their own context.
        self._tokens: dict[str, Token[int | None]] = {}

    def before_enqueue(
        self, broker: Broker, message: Message, delay: int | None
    ) -> None:
        """Stamp the current user's ID on the message.

        Parameters
        ----------
        broker : `Broker`
            The broker the message is enqueued on.
        message : `Message`
            The message being enqueued.
        delay : `int | None`
            Milliseconds to delay the message by.
        """
        uid = get_current_user_id()
        if uid is None:
            # Nothing to carry: a task enqueued by the scheduler or a command.
            return

        # Runs before ``message.encode()``, so the ID travels with the payload.
        message.options[self.option_key] = uid
        logger.debug("Stamped uid=%s on message %s.", uid, message.message_id)

    def before_process_message(self, broker: Broker, message: Message) -> None:
        """Bind the stamped user for as long as the message is processed.

        Parameters
        ----------
        broker : `Broker`
            The broker the message came from.
        message : `Message`
            The message about to be processed.
        """
        uid = message.options.get(self.option_key)
        self._tokens[message.message_id] = set_current_user_id(uid)
        logger.debug("Bound uid=%s for message %s.", uid, message.message_id)

    def after_process_message(
        self,
        broker: Broker,
        message: Message,
        *,
        result: object = None,
        exception: BaseException | None = None,
    ) -> None:
        """Release the user bound for this message.

        Parameters
        ----------
        broker : `Broker`
            The broker the message came from.
        message : `Message`
            The message that was processed.
        result : `object`, optional
            The value the actor returned.
        exception : `BaseException | None`, optional
            The error the actor raised, if it raised one.
        """
        self._release(message)

    def after_skip_message(self, broker: Broker, message: Message) -> None:
        """Release the user bound for a message that was skipped.

        Parameters
        ----------
        broker : `Broker`
            The broker the message came from.
        message : `Message`
            The message that was skipped.
        """
        self._release(message)

    def _release(self, message: Message) -> None:
        """Restore the user ID that was current before this message.

        Parameters
        ----------
        message : `Message`
            The message whose token to release.
        """
        token = self._tokens.pop(message.message_id, None)
        if token is not None:
            reset_current_user_id(token)
