import asyncio
import logging

from asgiref.sync import async_to_sync
from django.core.cache import cache
from gpp_client import GPPClient
from gpp_client.generated.enums import AttachmentType
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from goats_tom.models import GPPLogin
from goats_tom.realtime import NotificationInstance

logger = logging.getLogger(__name__)


class GPPFinderChartViewSet(GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = None

    def _notify(self, *, label: str, message: str, color: str) -> None:
        """Send a UI notification."""
        NotificationInstance.create_and_send(
            label=label,
            message=message,
            color=color,
        )

    def _get_gpp_token(self, request) -> str:
        """
        Retrieve the GPP token for the current user.

        Raises
        ------
        RuntimeError
            If the user does not have a valid GPP token.

        Returns
        -------
        str
            Valid GPP token.
        """
        creds = GPPLogin.objects.filter(user_id=request.user.id).first()
        token = getattr(creds, "token", None) if creds else None

        if not token:
            self._notify(
                label="GPP authentication",
                message="Missing GPP token.",
                color="danger",
            )
            raise RuntimeError("Missing GPP token.")

        return token

    def _run_with_client(self, *, token: str, coro):
        """
        Execute an async coroutine using a GPPClient instance.

        Ensures the client connection is properly closed.

        Parameters
        ----------
        token : str
            GPP authentication token.
        coro : Callable
            Coroutine that receives a GPPClient.

        Returns
        -------
        Any
            Result returned by the coroutine.
        """

        async def _runner():
            client = GPPClient(token=token)
            try:
                return await coro(client)
            finally:
                try:
                    await client.close()
                except Exception:
                    logger.debug("Failed to close GPP client.", exc_info=True)

        return async_to_sync(_runner)()

    def list(self, request):
        """
        Return the finder charts stored in a program.

        Parameters
        ----------
        request : Request
            Incoming authenticated request carrying a ``program_id`` query param.

        Returns
        -------
        Response
            Response containing the program finder charts.
        """
        program_id = request.query_params.get("program_id")

        try:
            if not program_id:
                raise ValueError("Missing program id.")

            token = self._get_gpp_token(request)

            async def _get_charts(client: GPPClient) -> dict:
                attachments, observations = await asyncio.gather(
                    client.attachment.get_all_by_program_id(program_id=program_id),
                    client.goats.get_observations_by_program_id(program_id=program_id),
                )

                program = attachments.model_dump(by_alias=True).get("program") or {}
                matched = (
                    observations.model_dump(by_alias=True).get("observations") or {}
                )

                # Which observations reference each attachment. Paginated results
                # make this a lower bound, flagged to the caller via hasMore.
                references: dict[str, list[str]] = {}
                for observation in matched.get("matches") or []:
                    for attachment in observation.get("attachments") or []:
                        references.setdefault(str(attachment["id"]), []).append(
                            str(observation["id"])
                        )

                results = [
                    {
                        "id": str(a["id"]),
                        "fileName": a.get("fileName"),
                        "fileSize": a.get("fileSize"),
                        "description": a.get("description"),
                        "updatedAt": a.get("updatedAt"),
                        "observationIds": references.get(str(a["id"]), []),
                    }
                    for a in program.get("attachments") or []
                    if a.get("attachmentType") == AttachmentType.FINDER
                ]

                return {
                    "results": results,
                    "hasMore": bool(matched.get("hasMore", False)),
                }

            payload = self._run_with_client(token=token, coro=_get_charts)

            return Response(payload, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.exception("Finder chart list failed program_id=%s", program_id)

            self._notify(
                label="Finder charts",
                message=str(exc),
                color="danger",
            )

            return Response(
                {"detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"], url_path="download-url")
    def download_url(self, request, pk=None):
        """
        Return a temporary download URL for a finder chart attachment.

        Parameters
        ----------
        request : Request
            Incoming authenticated request.
        pk : str
            Finder chart attachment id.

        Returns
        -------
        Response
            Response containing the temporary download URL.

        Raises
        ------
        RuntimeError
            If token is missing or URL cannot be retrieved.
        """
        try:
            if not pk:
                raise ValueError("Missing attachment id.")

            cache_key = f"gpp:finderchart:url:{pk}:{request.user.id}"
            cached = cache.get(cache_key)
            if cached:
                return Response({"url": cached}, status=status.HTTP_200_OK)

            token = self._get_gpp_token(request)

            async def _get_url(client: GPPClient) -> str:
                return await client.attachment.get_download_url_by_id(str(pk))

            url = self._run_with_client(token=token, coro=_get_url)

            if not url:
                raise RuntimeError("Download URL not available.")

            cache.set(cache_key, url, timeout=120)

            return Response({"url": url}, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.exception("Finder chart download-url failed id=%s", pk)

            self._notify(
                label="Finder chart download",
                message=str(exc),
                color="danger",
            )

            return Response(
                {"detail": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
