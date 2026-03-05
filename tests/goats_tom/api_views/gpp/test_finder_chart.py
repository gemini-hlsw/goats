import pytest
from dramatiq.results.errors import ResultFailure, ResultMissing
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from goats_tom.api_views.gpp.finder_chart import GPPFinderChartViewSet


@pytest.fixture
def rf():
    return APIRequestFactory()


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(username="u", password="x")


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


def _view(action_map):
    return GPPFinderChartViewSet.as_view(action_map)


def test_upload_validation_error_returns_400(mocker, rf, user):
    view = _view({"post": "upload"})
    request = rf.post("/upload/", data={}, format="multipart")
    force_authenticate(request, user=user)

    resp = view(request)
    assert resp.status_code == 400


import pytest
from dramatiq.results.errors import ResultFailure, ResultMissing
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from goats_tom.api_views.gpp.finder_chart import GPPFinderChartViewSet


@pytest.fixture
def rf():
    return APIRequestFactory()


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(username="u", password="x")


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


def _view(action_map):
    return GPPFinderChartViewSet.as_view(action_map)


# -------------------------
# upload
# -------------------------


def test_upload_validation_error_returns_400(mocker, rf, user):
    view = _view({"post": "upload"})
    request = rf.post("/upload/", data={}, format="multipart")
    force_authenticate(request, user=user)

    resp = view(request)
    assert resp.status_code == 400


def test_upload_tmp_persist_failure_returns_500_and_notifies(mocker, rf, user):
    view = GPPFinderChartViewSet.as_view({"post": "upload"})

    class DummyTmpDir:
        def mkdir(self, *args, **kwargs):
            raise OSError("nope")

    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart._TMP_UPLOAD_DIR",
        DummyTmpDir(),
    )

    notify = mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.NotificationInstance.create_and_send"
    )

    file = SimpleUploadedFile("test.png", b"abc", content_type="image/png")
    request = rf.post(
        "/upload/",
        data={"programId": "p", "observationId": "o", "file": file},
        format="multipart",
    )
    force_authenticate(request, user=user)

    resp = view(request)

    assert resp.status_code == 500
    notify.assert_called()


def test_upload_success_starts_dramatiq_task(mocker, rf, user, tmp_path):
    view = _view({"post": "upload"})

    # Use real tmp dir in test sandbox
    mocker.patch("goats_tom.api_views.gpp.finder_chart._TMP_UPLOAD_DIR", tmp_path)

    msg = mocker.Mock(message_id="task123")
    send = mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.upload_finder_chart.send",
        return_value=msg,
    )

    file = SimpleUploadedFile("test.png", b"abc", content_type="image/png")
    request = rf.post(
        "/upload/",
        data={"programId": "p", "observationId": "o", "file": file},
        format="multipart",
    )
    force_authenticate(request, user=user)

    resp = view(request)
    assert resp.status_code == 202
    assert "upload_id" in resp.data
    assert resp.data["task_id"] == "task123"
    send.assert_called_once()
    # ensure we wrote the tmp file
    kwargs = send.call_args.kwargs
    assert tmp_path in __import__("pathlib").Path(kwargs["tmp_path"]).parents


# -------------------------
# status
# -------------------------


def test_status_missing_task_id_returns_400(rf, user):
    view = _view({"get": "status"})
    request = rf.get("/status/")
    force_authenticate(request, user=user)

    resp = view(request)
    assert resp.status_code == 400
    assert "Missing task_id" in resp.data["detail"]


@pytest.mark.parametrize(
    "side_effect, expected_state",
    [
        (ResultMissing("missing result"), "PENDING"),
        (ResultFailure("boom"), "FAILED"),
    ],
)
def test_status_handles_dramatiq_result_errors(
    mocker, rf, user, side_effect, expected_state
):
    view = _view({"get": "status"})

    msg = mocker.Mock()
    msg.get_result.side_effect = side_effect

    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.dramatiq.Message",
        return_value=msg,
    )

    request = rf.get("/status/?task_id=123")
    force_authenticate(request, user=user)

    resp = view(request)
    assert resp.status_code == 200
    assert resp.data["state"] == expected_state


def test_status_done_state_triggers_success_notify(mocker, rf, user):
    view = _view({"get": "status"})
    notify = mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.NotificationInstance.create_and_send"
    )

    msg = mocker.Mock()
    msg.get_result.return_value = {"state": "DONE", "id": "a-1"}

    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.dramatiq.Message",
        return_value=msg,
    )

    request = rf.get("/status/?task_id=123")
    force_authenticate(request, user=user)

    resp = view(request)
    assert resp.status_code == 200
    assert resp.data["state"] == "DONE"
    notify.assert_called()  # Uploaded successfully


def test_status_error_state_returns_failed_with_message(mocker, rf, user):
    view = _view({"get": "status"})

    msg = mocker.Mock()
    msg.get_result.return_value = {"state": "ERROR", "message": "bad news"}

    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.dramatiq.Message",
        return_value=msg,
    )

    request = rf.get("/status/?task_id=123")
    force_authenticate(request, user=user)

    resp = view(request)
    assert resp.status_code == 200
    assert resp.data["state"] == "FAILED"
    assert resp.data["error"] == "bad news"


# -------------------------
# download_url
# -------------------------


def test_download_url_missing_pk_returns_400(rf, user):
    view = _view({"get": "download_url"})
    request = rf.get("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk=None)
    assert resp.status_code == 400


def test_download_url_cache_hit_returns_cached(mocker, rf, user):
    view = _view({"get": "download_url"})

    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.cache.get", return_value="http://cached"
    )
    get_token = mocker.patch.object(GPPFinderChartViewSet, "_get_gpp_token")

    request = rf.get("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 200
    assert resp.data["url"] == "http://cached"
    get_token.assert_not_called()


def test_download_url_missing_token_returns_400(mocker, rf, user):
    view = _view({"get": "download_url"})

    mocker.patch("goats_tom.api_views.gpp.finder_chart.cache.get", return_value=None)
    mocker.patch.object(
        GPPFinderChartViewSet,
        "_get_gpp_token",
        return_value=Response({"detail": "Missing GPP token."}, status=400),
    )

    request = rf.get("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 400


def test_download_url_success_sets_cache_and_notifies(mocker, rf, user):
    view = _view({"get": "download_url"})

    mocker.patch("goats_tom.api_views.gpp.finder_chart.cache.get", return_value=None)
    cache_set = mocker.patch("goats_tom.api_views.gpp.finder_chart.cache.set")
    notify = mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.NotificationInstance.create_and_send"
    )

    mocker.patch.object(GPPFinderChartViewSet, "_get_gpp_token", return_value="tok")
    mocker.patch.object(
        GPPFinderChartViewSet, "_run_with_client", return_value="http://fresh"
    )

    request = rf.get("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 200
    assert resp.data["url"] == "http://fresh"
    cache_set.assert_called_once()
    notify.assert_called()


def test_download_url_empty_url_returns_502(mocker, rf, user):
    view = _view({"get": "download_url"})

    mocker.patch("goats_tom.api_views.gpp.finder_chart.cache.get", return_value=None)
    mocker.patch.object(GPPFinderChartViewSet, "_get_gpp_token", return_value="tok")
    mocker.patch.object(GPPFinderChartViewSet, "_run_with_client", return_value="")

    request = rf.get("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 502


def test_download_url_exception_returns_500(mocker, rf, user):
    view = _view({"get": "download_url"})

    mocker.patch("goats_tom.api_views.gpp.finder_chart.cache.get", return_value=None)
    mocker.patch.object(GPPFinderChartViewSet, "_get_gpp_token", return_value="tok")
    mocker.patch.object(
        GPPFinderChartViewSet, "_run_with_client", side_effect=RuntimeError("boom")
    )

    request = rf.get("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 500


# -------------------------
# destroy
# -------------------------


def test_destroy_missing_pk_returns_400(rf, user):
    view = _view({"delete": "destroy"})
    request = rf.delete("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk=None)
    assert resp.status_code == 400


def test_destroy_missing_token_returns_400(mocker, rf, user):
    view = _view({"delete": "destroy"})

    mocker.patch.object(
        GPPFinderChartViewSet,
        "_get_gpp_token",
        return_value=Response({"detail": "Missing GPP token."}, status=400),
    )

    request = rf.delete("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 400


def test_destroy_success_calls_client_and_notifies(mocker, rf, user):
    view = _view({"delete": "destroy"})
    notify = mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.NotificationInstance.create_and_send"
    )

    mocker.patch.object(GPPFinderChartViewSet, "_get_gpp_token", return_value="tok")
    mocker.patch.object(GPPFinderChartViewSet, "_run_with_client", return_value=None)

    request = rf.delete("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 200
    assert resp.data["id"] == "a-1"
    notify.assert_called()


def test_destroy_exception_returns_500_and_notifies(mocker, rf, user):
    view = _view({"delete": "destroy"})
    notify = mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.NotificationInstance.create_and_send"
    )

    mocker.patch.object(GPPFinderChartViewSet, "_get_gpp_token", return_value="tok")
    mocker.patch.object(
        GPPFinderChartViewSet, "_run_with_client", side_effect=RuntimeError("boom")
    )

    request = rf.delete("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 500
    notify.assert_called()


def test_upload_success_starts_dramatiq_task(mocker, rf, user, tmp_path):
    view = _view({"post": "upload"})

    # Use real tmp dir in test sandbox
    mocker.patch("goats_tom.api_views.gpp.finder_chart._TMP_UPLOAD_DIR", tmp_path)

    msg = mocker.Mock(message_id="task123")
    send = mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.upload_finder_chart.send",
        return_value=msg,
    )

    file = SimpleUploadedFile("test.png", b"abc", content_type="image/png")
    request = rf.post(
        "/upload/",
        data={"programId": "p", "observationId": "o", "file": file},
        format="multipart",
    )
    force_authenticate(request, user=user)

    resp = view(request)
    assert resp.status_code == 202
    assert "upload_id" in resp.data
    assert resp.data["task_id"] == "task123"
    send.assert_called_once()
    # ensure we wrote the tmp file
    kwargs = send.call_args.kwargs
    assert tmp_path in __import__("pathlib").Path(kwargs["tmp_path"]).parents


def test_status_missing_task_id_returns_400(rf, user):
    view = _view({"get": "status"})
    request = rf.get("/status/")
    force_authenticate(request, user=user)

    resp = view(request)
    assert resp.status_code == 400
    assert "Missing task_id" in resp.data["detail"]


@pytest.mark.parametrize(
    "side_effect, expected_state",
    [
        (ResultMissing("missing result"), "PENDING"),
        (ResultFailure("boom"), "FAILED"),
    ],
)
def test_status_handles_dramatiq_result_errors(
    mocker, rf, user, side_effect, expected_state
):
    view = _view({"get": "status"})

    msg = mocker.Mock()
    msg.get_result.side_effect = side_effect

    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.dramatiq.Message",
        return_value=msg,
    )

    request = rf.get("/status/?task_id=123")
    force_authenticate(request, user=user)

    resp = view(request)
    assert resp.status_code == 200
    assert resp.data["state"] == expected_state


def test_status_done_state_triggers_success_notify(mocker, rf, user):
    view = _view({"get": "status"})
    notify = mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.NotificationInstance.create_and_send"
    )

    msg = mocker.Mock()
    msg.get_result.return_value = {"state": "DONE", "id": "a-1"}

    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.dramatiq.Message",
        return_value=msg,
    )

    request = rf.get("/status/?task_id=123")
    force_authenticate(request, user=user)

    resp = view(request)
    assert resp.status_code == 200
    assert resp.data["state"] == "DONE"
    notify.assert_called()  # Uploaded successfully


def test_status_error_state_returns_failed_with_message(mocker, rf, user):
    view = _view({"get": "status"})

    msg = mocker.Mock()
    msg.get_result.return_value = {"state": "ERROR", "message": "bad news"}

    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.dramatiq.Message",
        return_value=msg,
    )

    request = rf.get("/status/?task_id=123")
    force_authenticate(request, user=user)

    resp = view(request)
    assert resp.status_code == 200
    assert resp.data["state"] == "FAILED"
    assert resp.data["error"] == "bad news"


def test_download_url_missing_pk_returns_400(rf, user):
    view = _view({"get": "download_url"})
    request = rf.get("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk=None)
    assert resp.status_code == 400


def test_download_url_cache_hit_returns_cached(mocker, rf, user):
    view = _view({"get": "download_url"})

    mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.cache.get", return_value="http://cached"
    )
    get_token = mocker.patch.object(GPPFinderChartViewSet, "_get_gpp_token")

    request = rf.get("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 200
    assert resp.data["url"] == "http://cached"
    get_token.assert_not_called()


def test_download_url_missing_token_returns_400(mocker, rf, user):
    view = _view({"get": "download_url"})

    mocker.patch("goats_tom.api_views.gpp.finder_chart.cache.get", return_value=None)
    mocker.patch.object(
        GPPFinderChartViewSet,
        "_get_gpp_token",
        return_value=Response({"detail": "Missing GPP token."}, status=400),
    )

    request = rf.get("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 400


def test_download_url_success_sets_cache_and_notifies(mocker, rf, user):
    view = _view({"get": "download_url"})

    mocker.patch("goats_tom.api_views.gpp.finder_chart.cache.get", return_value=None)
    cache_set = mocker.patch("goats_tom.api_views.gpp.finder_chart.cache.set")
    notify = mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.NotificationInstance.create_and_send"
    )

    mocker.patch.object(GPPFinderChartViewSet, "_get_gpp_token", return_value="tok")
    mocker.patch.object(
        GPPFinderChartViewSet, "_run_with_client", return_value="http://fresh"
    )

    request = rf.get("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 200
    assert resp.data["url"] == "http://fresh"
    cache_set.assert_called_once()
    notify.assert_called()


def test_download_url_empty_url_returns_502(mocker, rf, user):
    view = _view({"get": "download_url"})

    mocker.patch("goats_tom.api_views.gpp.finder_chart.cache.get", return_value=None)
    mocker.patch.object(GPPFinderChartViewSet, "_get_gpp_token", return_value="tok")
    mocker.patch.object(GPPFinderChartViewSet, "_run_with_client", return_value="")

    request = rf.get("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 502


def test_download_url_exception_returns_500(mocker, rf, user):
    view = _view({"get": "download_url"})

    mocker.patch("goats_tom.api_views.gpp.finder_chart.cache.get", return_value=None)
    mocker.patch.object(GPPFinderChartViewSet, "_get_gpp_token", return_value="tok")
    mocker.patch.object(
        GPPFinderChartViewSet, "_run_with_client", side_effect=RuntimeError("boom")
    )

    request = rf.get("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 500


def test_destroy_missing_pk_returns_400(rf, user):
    view = _view({"delete": "destroy"})
    request = rf.delete("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk=None)
    assert resp.status_code == 400


def test_destroy_missing_token_returns_400(mocker, rf, user):
    view = _view({"delete": "destroy"})

    mocker.patch.object(
        GPPFinderChartViewSet,
        "_get_gpp_token",
        return_value=Response({"detail": "Missing GPP token."}, status=400),
    )

    request = rf.delete("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 400


def test_destroy_success_calls_client_and_notifies(mocker, rf, user):
    view = _view({"delete": "destroy"})
    notify = mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.NotificationInstance.create_and_send"
    )

    mocker.patch.object(GPPFinderChartViewSet, "_get_gpp_token", return_value="tok")
    mocker.patch.object(GPPFinderChartViewSet, "_run_with_client", return_value=None)

    request = rf.delete("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 200
    assert resp.data["id"] == "a-1"
    notify.assert_called()


def test_destroy_exception_returns_500_and_notifies(mocker, rf, user):
    view = _view({"delete": "destroy"})
    notify = mocker.patch(
        "goats_tom.api_views.gpp.finder_chart.NotificationInstance.create_and_send"
    )

    mocker.patch.object(GPPFinderChartViewSet, "_get_gpp_token", return_value="tok")
    mocker.patch.object(
        GPPFinderChartViewSet, "_run_with_client", side_effect=RuntimeError("boom")
    )

    request = rf.delete("/x/")
    force_authenticate(request, user=user)
    resp = view(request, pk="a-1")

    assert resp.status_code == 500
    notify.assert_called()
