"""Module for DRAGONSReduce view set."""

__all__ = ["DRAGONSReduceViewSet"]
from django.db import transaction
from django.db.models import QuerySet
from dramatiq_abort import abort
from rest_framework import mixins, permissions
from rest_framework.viewsets import GenericViewSet

import logging

from goats_tom.scoping import ScopedQuerySetMixin
from goats_tom.models import DRAGONSReduce
from goats_tom.realtime import DRAGONSProgress, NotificationInstance
from goats_tom.serializers import (
    DRAGONSReduceFilterSerializer,
    DRAGONSReduceSerializer,
    DRAGONSReduceUpdateSerializer,
)
from goats_tom import storage
from goats_tom.datalab_jobs import DataLabJobLauncher, datalab_mode_enabled
from goats_tom.models import DRAGONSFile
from goats_tom.tasks import run_dragons_reduce
from goats_tom.tasks.run_dragons_reduce import _safe_literal

logger = logging.getLogger(__name__)


class DRAGONSReduceViewSet(
    ScopedQuerySetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    # Scoped by the data products being reduced, not by the target.
    # Observation records are shared with collaborators on a target so
    # everyone can see what was triggered; the files stay private to
    # whoever triggered them, and a reduction belongs with its files.
    # See `goats_tom.scoping`.
    dataproduct_path = "recipe__dragons_run__observation_record__dataproduct"
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
            if datalab_mode_enabled():
                # Data Lab mode: the reduction runs in the PI's notebook
                # server, reading inputs from the read-only `vospace/` mount
                # and writing its run folder to the notebook home. It cannot
                # run against VOSpace directly -- `Reduce` writes
                # intermediates and a SQLite caldb, neither of which an HTTP
                # object API nor a read-only mount can host.
                self._launch_on_datalab(reduce, file_ids)
                return

            task = run_dragons_reduce.send(reduce.id, file_ids)
            reduce.task_id = task.message_id
            reduce.save()

        transaction.on_commit(_enqueue)

    def _launch_on_datalab(self, reduce, file_ids: list[int]) -> None:
        """Start the reduction as a job on the PI's Data Lab account.

        Parameters
        ----------
        reduce : `goats_tom.models.DRAGONSReduce`
            The reduction being started.
        file_ids : list of int
            `DRAGONSFile` ids to reduce.

        Notes
        -----
        Inputs are translated from storage names into paths on the Data Lab
        notebook server -- `~/vospace/<name>` -- because `Reduce.files` takes
        filesystem paths and the mount is where they appear. This is the one
        place the two namespaces meet, and getting it wrong produces a
        reduction that starts and then reports every input missing, which is
        why the runner checks and names the first absent file.

        Ordering is preserved from the local task: the file matching the
        recipe's observation type goes first, because DRAGONS reads tags
        from the first file and a mismatch crashes recipes such as
        `makeLampFlat` on F2.

        A failure here marks the reduction as errored rather than raising.
        `perform_create` has already committed, so the row exists and a PI
        watching the panel needs to see *why* it stopped, not a request that
        appears to have succeeded.
        """
        recipe = reduce.recipe
        run = recipe.dragons_run
        files = DRAGONSFile.objects.filter(dragons_run=run, id__in=file_ids)
        files = sorted(
            files, key=lambda file: file.observation_type != recipe.observation_type
        )

        input_paths = [
            f"~/vospace/{storage.name_of(file.data_product)}" for file in files
        ]

        try:
            launcher = DataLabJobLauncher(run.observation_record.user)
            job = launcher.launch_reduction(
                dragons_run=run,
                input_paths=input_paths,
                recipe_name=recipe.name,
                # Parsed the same way the local task parses them, so a
                # recipe behaves identically in both modes.
                uparms=_safe_literal(recipe.uparms, "uparms")
                if recipe.uparms is not None
                else None,
            )
            reduce.task_id = job.job_id
            reduce.save()
        except Exception:
            # Logged with a traceback rather than carried on the row:
            # `mark_error` records only that it failed, and a PI seeing the
            # panel go red needs an administrator able to find out why.
            logger.exception(
                "Could not launch Data Lab reduction for run %s.", run.pk
            )
            reduce.mark_error()
            DRAGONSProgress.create_and_send(reduce)

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
