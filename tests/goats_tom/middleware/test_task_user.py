"""Tests for the dramatiq middleware that carries the user into the worker."""

import pytest
from dramatiq import Message
from dramatiq.brokers.stub import StubBroker
from goats_tom.context.user_context import get_current_user_id, user_id_context
from goats_tom.middleware import TaskUserContextMiddleware


@pytest.fixture
def broker() -> StubBroker:
    """A broker to hand the middleware hooks; they never read from it."""
    return StubBroker()


@pytest.fixture
def middleware() -> TaskUserContextMiddleware:
    """The middleware under test."""
    return TaskUserContextMiddleware()


def make_message() -> Message:
    """A bare message, as the broker would hand it to the middleware."""
    return Message(
        queue_name="default",
        actor_name="run_dragons_reduce",
        args=(),
        kwargs={},
        options={},
    )


def test_enqueue_stamps_the_current_user(broker, middleware) -> None:
    """The ID of the user enqueuing the task is written to the message."""
    message = make_message()

    with user_id_context(42):
        middleware.before_enqueue(broker, message, None)

    assert message.options[middleware.option_key] == 42


def test_enqueue_stamps_nothing_without_a_user(broker, middleware) -> None:
    """A task enqueued with no user carries no ID at all."""
    message = make_message()

    middleware.before_enqueue(broker, message, None)

    assert middleware.option_key not in message.options


def test_the_stamp_survives_encoding(broker, middleware) -> None:
    """The ID reaches the worker, which only ever sees the encoded payload."""
    message = make_message()

    with user_id_context(42):
        middleware.before_enqueue(broker, message, None)

    assert Message.decode(message.encode()).options[middleware.option_key] == 42


def test_processing_binds_and_releases_the_user(broker, middleware) -> None:
    """The stamped user is current while the message runs, and only then."""
    message = make_message()
    with user_id_context(42):
        middleware.before_enqueue(broker, message, None)

    assert get_current_user_id() is None

    middleware.before_process_message(broker, message)
    assert get_current_user_id() == 42

    middleware.after_process_message(broker, message)
    assert get_current_user_id() is None


def test_a_failed_message_still_releases_the_user(broker, middleware) -> None:
    """An actor that raises must not leave its user bound to the worker."""
    message = make_message()
    with user_id_context(42):
        middleware.before_enqueue(broker, message, None)

    middleware.before_process_message(broker, message)
    middleware.after_process_message(broker, message, exception=RuntimeError("boom"))

    assert get_current_user_id() is None


def test_a_skipped_message_releases_the_user(broker, middleware) -> None:
    """A skipped message takes the same path as a processed one."""
    message = make_message()
    with user_id_context(42):
        middleware.before_enqueue(broker, message, None)

    middleware.before_process_message(broker, message)
    middleware.after_skip_message(broker, message)

    assert get_current_user_id() is None


def test_an_unstamped_message_binds_no_user(broker, middleware) -> None:
    """A task with no user must not inherit whoever ran the previous message."""
    stamped, bare = make_message(), make_message()
    with user_id_context(42):
        middleware.before_enqueue(broker, stamped, None)

    middleware.before_process_message(broker, stamped)
    middleware.after_process_message(broker, stamped)

    middleware.before_process_message(broker, bare)
    assert get_current_user_id() is None
    middleware.after_process_message(broker, bare)
