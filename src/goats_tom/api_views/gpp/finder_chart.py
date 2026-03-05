import logging
from pathlib import Path
from uuid import uuid4

import dramatiq
from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.cache import cache
from dramatiq.results.errors import ResultFailure, ResultMissing
from gpp_client import GPPClient
from rest_framework import permissions, serializers, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from goats_tom.models import GPPLogin
from goats_tom.realtime import NotificationInstance
from goats_tom.serializers.gpp import FinderChartUploadSerializer
from goats_tom.tasks.finder_chart import upload_finder_chart

logger = logging.getLogger(__name__)

_TMP_UPLOAD_DIR = Path("/tmp/goats-findercharts")


class GPPFinderChartViewSet(GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FinderChartUploadSerializer
    queryset = None

    def _notify(self, *, label: str, message: str, color: str) -> None:
        """Send a UI notification."""
        NotificationInstance.create_and_send(label=label, message=message, color=color)

    def _get_gpp_token(self, request):
        """
        Retrieve the GPP token for the current user.

        Returns
        -------
        str | Response
            Token string if available, otherwise a DRF error response.
        """
        creds = GPPLogin.objects.filter(user_id=request.user.id).first()
        token = getattr(creds, "token", None) if creds else None

        if token:
            return token

        self._notify(
            label="GPP authentication",
            message="Missing GPP token.",
            color="danger",
        )

        return Response(
            {"detail": "Missing GPP token."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def _run_with_client(self, *, token: str, coro):
        """
        Execute an async coroutine using a GPPClient instance.
        Ensures the client connection is properly closed.
        """

        async def _runner():
            client = GPPClient(env=settings.GPP_ENV, token=token)
            try:
                return await coro(client)
            finally:
                try:
                    await client.close()
                except Exception:
                    logger.debug("Failed to close GPP client.", exc_info=True)

        return async_to_sync(_runner)()

    def _extract_validation_message(self, exc: serializers.ValidationError) -> str:
        """
        Extract a user-friendly validation error message.
        """
        detail = exc.detail

        if isinstance(detail, dict):
            file_errors = detail.get("file")
            if isinstance(file_errors, list) and file_errors:
                return str(file_errors[0])

            for errors in detail.values():
                if isinstance(errors, list) and errors:
                    return str(errors[0])

        elif isinstance(detail, list) and detail:
            return str(detail[0])

        return str(exc)

    @action(
        detail=False,
        methods=["post"],
        url_path="upload",
        parser_classes=(MultiPartParser, FormParser),
    )
    def upload(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as exc:
            msg = self._extract_validation_message(exc)
            self._notify(label="Finder chart upload", message=msg, color="danger")
            return Response({"detail": exc.detail}, status=status.HTTP_400_BAD_REQUEST)

        program_id = serializer.validated_data["programId"]
        observation_id = serializer.validated_data["observationId"]
        description = serializer.validated_data.get("description", "")
        file_obj = serializer.validated_data["file"]

        upload_id = f"fc-{uuid4().hex}"

        try:
            _TMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            tmp_path = _TMP_UPLOAD_DIR / upload_id

            with tmp_path.open("wb") as f:
                for chunk in file_obj.chunks():
                    f.write(chunk)

        except Exception:
            logger.exception("Failed to persist upload file upload_id=%s", upload_id)

            self._notify(
                label="Finder chart upload",
                message="Failed to store uploaded file.",
                color="danger",
            )

            return Response(
                {"detail": "Failed to store uploaded file."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        msg = upload_finder_chart.send(
            upload_id=upload_id,
            tmp_path=str(tmp_path),
            file_name=file_obj.name,
            program_id=program_id,
            observation_id=observation_id,
            description=description,
            user_id=request.user.id,
        )

        return Response(
            {"upload_id": upload_id, "task_id": msg.message_id},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["get"], url_path="status")
    def status(self, request, *args, **kwargs):
        task_id = request.query_params.get("task_id")

        if not task_id:
            return Response(
                {"detail": "Missing task_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        msg = dramatiq.Message(
            queue_name=upload_finder_chart.queue_name,
            actor_name=upload_finder_chart.actor_name,
            args=(),
            kwargs={},
            options={},
            message_id=task_id,
        )

        try:
            result = msg.get_result(block=False)

            if isinstance(result, dict):
                state = result.get("state")

                if state == "ERROR":
                    return Response(
                        {
                            "state": "FAILED",
                            "error": result.get("message", "Upload failed."),
                        }
                    )

                if state == "DONE":
                    self._notify(
                        label="Finder chart upload",
                        message="Uploaded successfully",
                        color="success",
                    )

                    return Response({"state": "DONE", "result": result})

            return Response({"state": "DONE", "result": result})

        except ResultMissing:
            return Response({"state": "PENDING"})

        except ResultFailure as exc:
            err = str(exc)

            logger.warning(
                "[finder-charts.status] task failed user=%s task_id=%s error=%s",
                request.user.id,
                task_id,
                err,
            )

            return Response({"state": "FAILED", "error": err})

    def destroy(self, request, pk=None):
        """
        DELETE /gpp/observations/finder-charts/<pk>/
        """
        attachment_id = pk

        if not attachment_id:
            return Response(
                {"detail": "Missing attachment id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = self._get_gpp_token(request)
        if isinstance(token, Response):
            return token

        try:

            async def _delete(client: GPPClient):
                await client.attachment.delete_by_id(str(attachment_id))

            self._run_with_client(token=token, coro=_delete)

            self._notify(
                label="Finder chart delete",
                message="Deleted successfully.",
                color="success",
            )

            return Response({"id": str(attachment_id)})

        except Exception as exc:
            logger.exception("Finder chart delete failed id=%s", attachment_id)

            self._notify(
                label="Finder chart delete",
                message=str(exc),
                color="danger",
            )

            return Response(
                {"detail": "Delete failed."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"], url_path="download-url")
    def download_url(self, request, pk=None):
        attachment_id = pk
        if not attachment_id:
            return Response(
                {"detail": "Missing attachment id."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cache_key = f"gpp:finderchart:url:{attachment_id}:{request.user.id}"
        cached = cache.get(cache_key)
        if cached:
            return Response({"url": cached})

        token = self._get_gpp_token(request)
        if isinstance(token, Response):
            return token

        try:

            async def _get_url(client: GPPClient) -> str:
                return await client.attachment.get_download_url_by_id(
                    str(attachment_id)
                )

            url = self._run_with_client(token=token, coro=_get_url)

            if not url:
                return Response(
                    {"detail": "Download URL not available."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            self._notify(
                label="Finder chart download",
                message="Download started",
                color="info",
            )

            cache.set(cache_key, url, timeout=120)

            return Response({"url": url}, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.exception("Finder chart download-url failed id=%s", attachment_id)
            return Response(
                {"detail": f"Download URL fetch failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
