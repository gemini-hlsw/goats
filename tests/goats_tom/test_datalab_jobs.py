"""Tests for `DataLabJob` and the supervisor that advances it.

The isolation test matters most. `RemoteJob` and the ANTARES supervisor are
a working system, and the whole reason this is a separate model is that they
should not have been changed for features that did not exist yet. A test
that proves the two do not see each other is what keeps that true.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from tom_observations.tests.factories import ObservingRecordFactory
from tom_targets.tests.factories import SiderealTargetFactory

from goats_tom.models import AntaresStreamSubscription, DataLabJob, RemoteJob
from goats_tom.tasks.supervise_datalab_jobs import (
    STALE_AFTER_SECONDS,
    _apply_status,
    _collect_reduction,
    _reap,
    _stream_logs,
)
from goats_tom.tests.factories import DRAGONSRunFactory, UserFactory


@pytest.fixture
def record(db):
    """An observation record attached to a real target."""
    return ObservingRecordFactory.create(target_id=SiderealTargetFactory.create().id)


@pytest.fixture
def job(db, record):
    """A running download job."""
    return DataLabJob.objects.create(
        kind=DataLabJob.Kind.DOWNLOAD,
        observation_record=record,
        user=UserFactory(),
        datalab_username="alice",
        job_id="job-1",
        status=DataLabJob.Status.RUNNING,
    )


@pytest.mark.django_db
class TestModel:
    """Kinds, links and validation."""

    def test_download_links_an_observation_record(self, job, record):
        assert job.owner == record

    def test_reduction_links_a_dragons_run(self, db):
        run = DRAGONSRunFactory()
        reduction = DataLabJob.objects.create(
            kind=DataLabJob.Kind.REDUCTION,
            dragons_run=run,
            user=UserFactory(),
            datalab_username="alice",
            job_id="job-2",
        )
        assert reduction.owner == run

    @pytest.mark.parametrize(
        "kind,field",
        [
            (DataLabJob.Kind.DOWNLOAD, "observation_record"),
            (DataLabJob.Kind.REDUCTION, "dragons_run"),
        ],
    )
    def test_missing_link_is_rejected(self, db, kind, field):
        """Caught here rather than at a `None` three calls later."""
        candidate = DataLabJob(
            kind=kind, user=UserFactory(), datalab_username="a", job_id="j"
        )
        with pytest.raises(ValidationError) as exc:
            candidate.clean()
        assert field in exc.value.message_dict


@pytest.mark.django_db
class TestAntaresIsolation:
    """The two job systems must not see each other.

    Notes
    -----
    `RemoteJob` was generalized to carry all three kinds and then reverted,
    because it changed a working system for features that did not exist. This
    is what makes the separation an assertion rather than an assumption.
    """

    def test_datalab_jobs_are_invisible_to_remote_job_queries(self, job):
        assert RemoteJob.objects.count() == 0

    def test_remote_jobs_are_invisible_to_datalab_queries(self, db):
        subscription = AntaresStreamSubscription.objects.create(
            owner=UserFactory(), topics=["t"]
        )
        RemoteJob.objects.create(
            subscription=subscription, job_id="antares-1", datalab_username="alice"
        )
        assert DataLabJob.objects.count() == 0


@pytest.mark.django_db
class TestStaleness:
    """Liveness comes from the heartbeat, never from `status`."""

    def test_a_quiet_job_goes_stale(self, job):
        job.last_heartbeat = timezone.now() - timedelta(
            seconds=STALE_AFTER_SECONDS + 60
        )
        job.save(update_fields=["last_heartbeat"])
        assert job.is_stale(STALE_AFTER_SECONDS)

    def test_a_recent_job_does_not(self, job):
        job.last_heartbeat = timezone.now()
        job.save(update_fields=["last_heartbeat"])
        assert not job.is_stale(STALE_AFTER_SECONDS)

    def test_a_job_that_never_reported_still_goes_stale(self, job):
        """Falls back to `launched_at`.

        Notes
        -----
        A runner that dies before writing its first status file has no
        heartbeat at all. Without this fallback it would sit active forever,
        never polled to a conclusion and never reaped.
        """
        assert job.last_heartbeat is None
        DataLabJob.objects.filter(pk=job.pk).update(
            launched_at=timezone.now() - timedelta(seconds=STALE_AFTER_SECONDS + 60)
        )
        job.refresh_from_db()
        assert job.is_stale(STALE_AFTER_SECONDS)

    def test_a_finished_job_is_never_stale(self, job):
        job.status = DataLabJob.Status.FINISHED
        assert not job.is_stale(0)

    def test_reaping_records_why(self, job):
        """`LOST` carries no reason from the runner, so one is written here."""
        _reap(job)
        job.refresh_from_db()
        assert job.status == DataLabJob.Status.LOST
        assert "No progress reported" in job.error


@pytest.mark.django_db
class TestApplyStatus:
    """Copying what the runner reported onto the row."""

    def test_progress_advances_the_heartbeat(self, job):
        _apply_status(job, {"state": "running", "seen": 5, "kept": 3})
        job.refresh_from_db()
        assert (job.files_seen, job.files_kept) == (5, 3)
        assert job.last_heartbeat is not None

    def test_unchanged_counts_do_not_advance_the_heartbeat(self, job):
        """A wedged runner keeps its status file intact.

        Notes
        -----
        Treating a successful *read* as a heartbeat would make a hung job
        look healthy forever. Only a change in what it reports counts.
        """
        _apply_status(job, {"state": "running", "seen": 0, "kept": 0})
        job.refresh_from_db()
        assert job.last_heartbeat is None

    def test_finishing_is_recorded(self, job):
        _apply_status(job, {"state": "finished", "seen": 2, "kept": 2})
        job.refresh_from_db()
        assert job.status == DataLabJob.Status.FINISHED
        assert job.finished_at is not None

    def test_failure_keeps_the_reason(self, job):
        _apply_status(job, {"state": "failed", "reason": "GOA returned HTTP 403"})
        job.refresh_from_db()
        assert job.status == DataLabJob.Status.FAILED
        assert "403" in job.error


@pytest.mark.django_db
class TestLogStreaming:
    """`tail_ndjson` is what replaces `DRAGONSHandler` for remote runs."""

    def test_offset_advances_so_polling_resumes(self, job):
        client = MagicMock()
        client.tail_ndjson.return_value = ([{"event": "a"}, {"event": "b"}], 2)
        with patch(
            "goats_tom.tasks.supervise_datalab_jobs._publish"
        ) as publish:
            _stream_logs(client, job)
        job.refresh_from_db()
        assert job.log_offset == 2
        assert publish.call_count == 2

    def test_previously_read_records_are_not_republished(self, job):
        job.log_offset = 2
        job.save(update_fields=["log_offset"])
        client = MagicMock()
        client.tail_ndjson.return_value = ([], 2)
        with patch("goats_tom.tasks.supervise_datalab_jobs._publish") as publish:
            _stream_logs(client, job)
        client.tail_ndjson.assert_called_once()
        assert client.tail_ndjson.call_args[0][1] == 2
        assert publish.call_count == 0

    def test_a_log_failure_does_not_fail_the_job(self, job):
        """Logs are a nicety; a reduction must not die for one.

        Notes
        -----
        A closed websocket or an unreadable events file is not a reason to
        lose an hour of reduction.
        """
        client = MagicMock()
        client.tail_ndjson.side_effect = RuntimeError("unreadable")
        _stream_logs(client, job)
        job.refresh_from_db()
        assert job.status == DataLabJob.Status.RUNNING


@pytest.mark.django_db
class TestReductionCollection:
    """What a finished reduction leaves behind on the run."""

    @pytest.fixture
    def reduction(self, db):
        return DataLabJob.objects.create(
            kind=DataLabJob.Kind.REDUCTION,
            dragons_run=DRAGONSRunFactory(),
            user=UserFactory(),
            datalab_username="alice",
            job_id="job-red",
            status=DataLabJob.Status.FINISHED,
        )

    def test_creates_no_data_products(self, reduction):
        """The PI chooses; nothing is promoted automatically.

        Notes
        -----
        The local reduction records nothing either. Promoting every
        intermediate would fill Manage Data with files nobody asked for and
        make remote reductions behave unlike local ones.
        """
        from tom_dataproducts.models import DataProduct

        before = DataProduct.objects.count()
        _collect_reduction(
            reduction, {"outputs": [{"name": "a.fits", "written_at": 1000.0}]}
        )
        assert DataProduct.objects.count() == before

    def test_records_when_each_output_was_written(self, reduction):
        _collect_reduction(
            reduction, {"outputs": [{"name": "a.fits", "written_at": 1000.0}]}
        )
        run = reduction.dragons_run
        run.refresh_from_db()
        assert run.output_written_at == {f"{run.get_output_prefix()}/a.fits": 1000.0}

    def test_a_rerun_updates_only_what_it_touched(self, reduction):
        """A run is not one reduction.

        Notes
        -----
        A recipe can be rerun repeatedly within the same run; each rerun
        rewrites some outputs and leaves others alone. Replacing the map
        would restamp every file with the newest job's time and make outputs
        from an earlier rerun look as though this one produced them.
        """
        run = reduction.dragons_run
        prefix = run.get_output_prefix()

        _collect_reduction(
            reduction,
            {
                "outputs": [
                    {"name": "a.fits", "written_at": 1000.0},
                    {"name": "b.fits", "written_at": 1000.0},
                ]
            },
        )
        # A second job for the same run rewrites only one of them.
        rerun = DataLabJob.objects.create(
            kind=DataLabJob.Kind.REDUCTION,
            dragons_run=run,
            user=reduction.user,
            datalab_username="alice",
            job_id="job-red-2",
            status=DataLabJob.Status.FINISHED,
        )
        _collect_reduction(rerun, {"outputs": [{"name": "b.fits", "written_at": 2000.0}]})

        run.refresh_from_db()
        assert run.output_written_at == {
            f"{prefix}/a.fits": 1000.0,
            f"{prefix}/b.fits": 2000.0,
        }
