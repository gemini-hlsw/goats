"""Module for DRAGONSReduce view set."""

__all__ = ["DRAGONSReduceViewSet"]
from django.db import transaction
from django.db.models import QuerySet
from dramatiq_abort import abort
from rest_framework import mixins, permissions
from rest_framework.viewsets import GenericViewSet

from goats_tom.models import DRAGONSReduce
from goats_tom.realtime import DRAGONSProgress, NotificationInstance
from goats_tom.serializers import (
    DRAGONSReduceFilterSerializer,
    DRAGONSReduceSerializer,
    DRAGONSReduceUpdateSerializer,
)
from goats_tom.tasks import run_dragons_reduce


class DRAGONSReduceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    queryset = DRAGONSReduce.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_serializer_class = DRAGONSReduceFilterSerializer
    serializer_classes = {
        "update": DRAGONSReduceUpdateSerializer,
        "partial_update": DRAGONSReduceUpdateSerializer,
    }
    serializer_class = DRAGONSReduceSerializer

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()

        # Run query parameters through the serializer.
        filter_serializer = self.filter_serializer_class(data=self.request.query_params)

        # Check if any filters provided.
        if filter_serializer.is_valid(raise_exception=False):
            status_filter = filter_serializer.validated_data.get("status")
            not_finished = filter_serializer.validated_data.get("not_finished")
            run = filter_serializer.validated_data.get("run")

            if run is not None:
                queryset = queryset.filter(recipe__dragons_run__pk=run)
            if status_filter is not None:
                queryset = queryset.filter(status__in=status_filter)
            if not_finished is True:
                queryset = queryset.exclude(status__in=["canceled", "done", "error"])

        return queryset

    def get_serializer_class(self):
        """Determine which serializer to use based on the HTTP method."""
        return self.serializer_classes.get(self.action, self.serializer_class)

    def perform_create(self, serializer: DRAGONSReduceSerializer) -> None:
        """Starts the dragons reduce background task for the specified recipe.

        Parameters
        ----------
        serializer : `DRAGONSReduceSerializer`
            The serializer with data loaded.

        """
        # Retrive the file IDs to include.
        file_ids = serializer.validated_data.get("file_ids", [])
        reduce = serializer.save()
        reduce.mark_queued()
        DRAGONSProgress.create_and_send(reduce)

        def _enqueue() -> None:
            task = run_dragons_reduce.send(reduce.id, file_ids)
            reduce.task_id = task.message_id
            reduce.save()

        transaction.on_commit(_enqueue)

    def perform_update(self, serializer: DRAGONSReduceUpdateSerializer) -> None:
        """Cancels a task.

        Parameters
        ----------
        serializer : `DRAGONSReduceUpdateSerializer`.
            The serialized data.

        """
        reduce = serializer.save()
        if reduce.status == "canceled":
            # Cancel the running event.
            abort(reduce.task_id)
            DRAGONSProgress.create_and_send(reduce)
            NotificationInstance.create_and_send(
                label=reduce.get_label(),
                color="warning",
                message="Background task canceled.",
            )
