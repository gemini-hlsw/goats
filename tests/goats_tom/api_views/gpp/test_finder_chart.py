import asyncio
from types import SimpleNamespace

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from goats_tom.api_views.gpp.finder_chart import GPPFinderChartViewSet


@pytest.fixture
def rf():
    return APIRequestFactory()


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(username="u", password="x")


@pytest.fixture
def view_download_url():
    return GPPFinderChartViewSet.as_view({"get": "download_url"})


@pytest.fixture(autouse=True)
def clear_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


def test_get_gpp_token_returns_token(mocker, rf, user):
    view = GPPFinderChartViewSet()
    creds = SimpleNamespace(token="abc123")

    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.GPPLogin.objects.filter"
    ).return_value.first.return_value = creds

    request = rf.get("/x/")
    request.user = user

    token = view._get_gpp_token(request)

    assert token == "abc123"


def test_get_gpp_token_missing_raises_and_notifies(mocker, rf, user):
    view = GPPFinderChartViewSet()
    notify = mocker.patch.object(view, "_notify")

    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.GPPLogin.objects.filter"
    ).return_value.first.return_value = None

    request = rf.get("/x/")
    request.user = user

    with pytest.raises(RuntimeError, match="Missing GPP token."):
        view._get_gpp_token(request)

    notify.assert_called_once_with(
        label="GPP authentication",
        message="Missing GPP token.",
        color="danger",
    )


def test_run_with_client_returns_result_and_closes_client(mocker):
    view = GPPFinderChartViewSet()
    fake_client = mocker.Mock()
    fake_client.close = mocker.AsyncMock()

    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.GPPClient",
        return_value=fake_client,
    )
    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.settings",
        SimpleNamespace(GPP_ENV="test"),
    )

    def fake_async_to_sync(async_fn):
        def runner():
            return asyncio.run(async_fn())

        return runner

    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.async_to_sync",
        side_effect=fake_async_to_sync,
    )

    async def coro(client):
        assert client is fake_client
        return "ok"

    result = view._run_with_client(token="tok", coro=coro)

    assert result == "ok"
    fake_client.close.assert_awaited_once()


def test_run_with_client_ignores_close_error(mocker):
    view = GPPFinderChartViewSet()
    fake_client = mocker.Mock()
    fake_client.close = mocker.AsyncMock(side_effect=RuntimeError("close failed"))

    logger_debug = mocker.patch("goats_tom.api_views.gpp.finder_chart.logger.debug")

    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.GPPClient",
        return_value=fake_client,
    )
    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.settings",
        SimpleNamespace(GPP_ENV="test"),
    )

    def fake_async_to_sync(async_fn):
        def runner():
            return asyncio.run(async_fn())

        return runner

    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.async_to_sync",
        side_effect=fake_async_to_sync,
    )

    async def coro(client):
        return "ok"

    result = view._run_with_client(token="tok", coro=coro)

    assert result == "ok"
    logger_debug.assert_called_once()


def test_download_url_missing_pk_returns_500_and_notifies(
    mocker, rf, user, view_download_url
):
    notify = mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.NotificationInstance.create_and_send"
    )

    request = rf.get("/x/")
    force_authenticate(request, user=user)

    response = view_download_url(request, pk=None)

    assert response.status_code == 500
    assert response.data["detail"] == "Missing attachment id."
    notify.assert_called_once()


def test_download_url_cache_hit_returns_cached_url(mocker, rf, user, view_download_url):
    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.cache.get",
        return_value="http://cached.example/file.png",
    )
    get_token = mocker.patch.object(
        GPPFinderChartViewSet,
        "_get_gpp_token",
    )

    request = rf.get("/x/")
    force_authenticate(request, user=user)

    response = view_download_url(request, pk="att-1")

    assert response.status_code == 200
    assert response.data["url"] == "http://cached.example/file.png"
    get_token.assert_not_called()


def test_download_url_missing_token_returns_500(mocker, rf, user, view_download_url):
    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.cache.get",
        return_value=None,
    )
    mocker.patch.object(
        GPPFinderChartViewSet,
        "_get_gpp_token",
        side_effect=RuntimeError("Missing GPP token."),
    )
    notify = mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.NotificationInstance.create_and_send"
    )

    request = rf.get("/x/")
    force_authenticate(request, user=user)

    response = view_download_url(request, pk="att-1")

    assert response.status_code == 500
    assert response.data["detail"] == "Missing GPP token."
    notify.assert_called_once()


def test_download_url_empty_url_returns_500(mocker, rf, user, view_download_url):
    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.cache.get",
        return_value=None,
    )
    mocker.patch.object(
        GPPFinderChartViewSet,
        "_get_gpp_token",
        return_value="tok",
    )
    mocker.patch.object(
        GPPFinderChartViewSet,
        "_run_with_client",
        return_value="",
    )
    notify = mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.NotificationInstance.create_and_send"
    )

    request = rf.get("/x/")
    force_authenticate(request, user=user)

    response = view_download_url(request, pk="att-1")

    assert response.status_code == 500
    assert response.data["detail"] == "Download URL not available."
    notify.assert_called_once()


def test_download_url_success_sets_cache(mocker, rf, user, view_download_url):
    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.cache.get",
        return_value=None,
    )
    cache_set = mocker.patch("goats_tom.api_views.gpp.finder_chart.cache.set")
    mocker.patch.object(
        GPPFinderChartViewSet,
        "_get_gpp_token",
        return_value="tok",
    )
    mocker.patch.object(
        GPPFinderChartViewSet,
        "_run_with_client",
        return_value="http://fresh.example/file.png",
    )

    request = rf.get("/x/")
    force_authenticate(request, user=user)

    response = view_download_url(request, pk="att-1")

    assert response.status_code == 200
    assert response.data["url"] == "http://fresh.example/file.png"
    cache_set.assert_called_once_with(
        f"gpp:finderchart:url:att-1:{user.id}",
        "http://fresh.example/file.png",
        timeout=120,
    )


def test_download_url_run_with_client_exception_returns_500_and_notifies(
    mocker, rf, user, view_download_url
):
    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.cache.get",
        return_value=None,
    )
    mocker.patch.object(
        GPPFinderChartViewSet,
        "_get_gpp_token",
        return_value="tok",
    )
    mocker.patch.object(
        GPPFinderChartViewSet,
        "_run_with_client",
        side_effect=RuntimeError("boom"),
    )
    notify = mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.NotificationInstance.create_and_send"
    )

    request = rf.get("/x/")
    force_authenticate(request, user=user)

    response = view_download_url(request, pk="att-1")

    assert response.status_code == 500
    assert response.data["detail"] == "boom"
    notify.assert_called_once()
