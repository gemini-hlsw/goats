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
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["post"])
    def shutdown(self, request):
        pid_file = pathlib.Path(tempfile.gettempdir()) / "goats.pid"

        if not pid_file.exists():
            return Response(
                {"error": "Could not find the GOATS CLI process."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        pid = int(pid_file.read_text().strip())

        os.kill(pid, signal.SIGINT)
        return Response({"status": "shutdown initiated"})
