"""Module that creates the view for system-level operations."""

__all__ = ["SystemViewSet"]

import os
import pathlib
import signal
import tempfile

from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet


class SystemViewSet(ViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=["post"])
    def shutdown(self, request):
        pid_file = pathlib.Path(tempfile.gettempdir()) / "goats.pid"

        if not pid_file.exists():
            return Response(
                {"error": "Could not find the GOATS CLI process."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            pid = int(pid_file.read_text().strip())
        except (FileNotFoundError, ValueError):
            return Response(
                {"error": "GOATS PID file is missing or corrupted."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            os.kill(pid, signal.SIGINT)
        except ProcessLookupError:
            return Response(
                {"error": "GOATS process is no longer running."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except PermissionError:
            return Response(
                {"error": "Insufficient permissions to shut down GOATS process."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response({"status": "shutdown initiated"})
