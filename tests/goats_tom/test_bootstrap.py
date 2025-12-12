import pytest

from goats_tom.bootstrap import setup_dramatiq_abort


@pytest.mark.django_db
def test_setup_dramatiq_abort_adds_abortable_middleware(mocker, settings):
    """
    Test that setup_dramatiq_abort adds the Abortable middleware to the broker.
    """
    settings.DRAMATIQ_REDIS_URL = "redis://test.test:1234/0"

    broker = mocker.Mock()
    mocker.patch("dramatiq.get_broker", return_value=broker)

    backend = mocker.Mock()
    redis_backend_cls = mocker.Mock()
    redis_backend_cls.from_url.return_value = backend
    mocker.patch("dramatiq_abort.backends.RedisBackend", redis_backend_cls)

    abortable = mocker.Mock()
    mocker.patch("dramatiq_abort.Abortable", return_value=abortable)

    setup_dramatiq_abort()

    redis_backend_cls.from_url.assert_called_once_with(settings.DRAMATIQ_REDIS_URL)
    broker.add_middleware.assert_called_once_with(abortable)
