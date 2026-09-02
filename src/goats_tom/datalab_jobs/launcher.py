"""Launching GOA downloads and DRAGONS reductions on Astro Data Lab.

The VM side of Phases 3 and 4. Builds a job spec, stages the matching runner
through `DataLabHeadlessClient`, and records a `DataLabJob` row.

Separate from `goats_tom.executors`, which is the ANTARES stream's executor
interface and is about starting and stopping a *subscription*. Nothing here
is a `StreamExecutor` and it should not be made into one -- see *Keep ANTARES
out of Phases 3 and 4* in ``STATUS.md``.
"""

__all__ = ["DataLabJobLauncher", "LaunchError"]

import json
import logging
import posixpath
from pathlib import Path
from typing import Optional

from django.conf import settings

from goats_tom.astro_data_lab import AstroDataLabClient, AstroDataLabConfig
from goats_tom.astro_data_lab.headless import DataLabHeadlessClient, HeadlessConfig
from goats_tom.models import DataLabJob

logger = logging.getLogger(__name__)

#: Where the runner scripts live on the GOATS host.
RUNNER_DIR = Path(__file__).resolve().parent.parent / "remote"

#: Name of the GOA session cookie. See `_goa_cookie`.
GOA_COOKIE_NAME = "gemini_archive_session"


class LaunchError(RuntimeError):
    """Raised when a job cannot be started on Data Lab."""


def _datalab_credentials(user):
    """Return `user`'s linked Astro Data Lab login.

    Raises
    ------
    LaunchError
        If there is no linked account.
    """
    credentials = getattr(user, "astrodatalablogin", None)
    if credentials is None or not credentials.username:
        raise LaunchError(
            f"{user.username} has no linked Astro Data Lab account, so nothing "
            "can be run on their behalf. Link one in Settings."
        )
    return credentials


def _goa_cookie(user) -> Optional[str]:
    """Log into GOA on the VM and return the session cookie.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        Whose archive account to use.

    Returns
    -------
    str or None
        The cookie value, or `None` when the user has no GOA credentials --
        in which case the download proceeds and returns public data only,
        exactly as it does today on the VM.

    Notes
    -----
    **The password never leaves this machine.** What authorizes a download is
    the `gemini_archive_session` cookie, not the credentials; Gemini's own
    API documentation recommends extracting it and referencing it from a
    script. So the VM logs in as it always has and passes only the cookie.

    The cookie is a bearer credential for the PI's whole archive account, so
    it is written into the job spec and scrubbed by the runner the moment it
    is loaded. A PI logging out of the archive in a browser invalidates every
    session including a running job's, which is a real failure mode and worth
    knowing when a download fails mid-flight for no visible reason.
    """
    from goats_tom.astroquery import Observations as GOA  # noqa: PLC0415
    from goats_tom.models import GOALogin  # noqa: PLC0415

    try:
        credentials = GOALogin.objects.get(user=user)
    except GOALogin.DoesNotExist:
        logger.warning(
            "No GOA credentials for %s; proprietary data will not be downloaded.",
            user.username,
        )
        return None

    GOA.login(credentials.username, credentials.password)
    if not GOA.authenticated():
        logger.warning(
            "GOA login failed for %s; proprietary data will not be downloaded.",
            user.username,
        )
        return None

    return GOA._session.cookies.get(GOA_COOKIE_NAME)


class DataLabJobLauncher:
    """Stage and start a runner on a PI's Data Lab account.

    Parameters
    ----------
    user : `django.contrib.auth.models.User`
        Whose account the job runs on.

    Notes
    -----
    One instance per launch. It holds a Data Lab token, and tokens expire --
    a cached launcher would fail in the way `AstroDatalabLogin` documents as
    the worst case, where the client reports success whatever the service
    said.
    """

    def __init__(self, user) -> None:
        self.user = user
        self.credentials = _datalab_credentials(user)
        self.config = AstroDataLabConfig()

    def _token(self) -> str:
        """Return a fresh Data Lab auth token."""
        with AstroDataLabClient(
            username=self.credentials.username,
            password=self.credentials.password,
            config=self.config,
        ) as client:
            token = client.login()
            if not client.is_logged_in():
                raise LaunchError("Astro Data Lab credentials are not valid.")
            return token

    def _headless(self) -> DataLabHeadlessClient:
        """Return a headless client for this user's notebook server."""
        return DataLabHeadlessClient(
            username=self.credentials.username,
            password=self.credentials.password,
            config=HeadlessConfig(
                **getattr(settings, "GOATS_DATALAB_HEADLESS", {}),
            ),
        )

    def _launch(self, runner_name: str, spec: dict) -> dict:
        """Stage `runner_name` with `spec` and start it.

        Returns
        -------
        dict
            Identifiers from the `JobHandle`.
        """
        script = (RUNNER_DIR / runner_name).read_text()

        client = self._headless()
        try:
            client.ensure_server()
            handle = client.launch(
                script=script,
                script_name=runner_name,
                extra_files={"job_spec.json": json.dumps(spec)},
            )
        finally:
            client.close()

        return {
            "job_id": handle.job_id,
            "session_id": handle.session_id,
            "kernel_id": handle.kernel_id,
            "remote_pid": handle.pid,
        }

    def launch_download(self, observation_record, goa_url: str) -> DataLabJob:
        """Start a GOA download for `observation_record`.

        Parameters
        ----------
        observation_record : `tom_observations.models.ObservationRecord`
            What is being downloaded.
        goa_url : str
            The archive URL to fetch, built by the caller exactly as the
            local task builds it.

        Returns
        -------
        `DataLabJob`

        Notes
        -----
        `destination_prefix` matches what `custom_data_product_path` produces
        on the VM, minus the `users/<username>/goats/` prefix that the
        VOSpace root already supplies. The two must agree: the runner writes
        under one name and `VOSpaceStorage` looks under the other, and a
        mismatch produces files nothing can find rather than an error.
        """
        target = observation_record.target
        prefix = posixpath.join(
            target.name,
            observation_record.facility,
            observation_record.observation_id,
        )

        spec = {
            "datalab_base_url": self.config.base_url,
            "datalab_token": self._token(),
            "vospace_root": self.config.user_root(self.credentials.username),
            "destination_prefix": prefix,
            "goa_url": goa_url,
            "goa_cookie": _goa_cookie(self.user),
        }

        identifiers = self._launch("download_runner.py", spec)
        job = DataLabJob.objects.create(
            kind=DataLabJob.Kind.DOWNLOAD,
            observation_record=observation_record,
            user=self.user,
            datalab_username=self.credentials.username,
            status=DataLabJob.Status.RUNNING,
            **identifiers,
        )
        logger.info(
            "Launched Data Lab download %s for observation %s.",
            job.job_id,
            observation_record.pk,
        )
        return job

    def launch_reduction(
        self,
        dragons_run,
        input_paths: list[str],
        calibration_paths: Optional[list[str]] = None,
        recipe_name: Optional[str] = None,
        uparms: Optional[list] = None,
        upload_caldb: bool = False,
    ) -> DataLabJob:
        """Start a DRAGONS reduction for `dragons_run`.

        Parameters
        ----------
        dragons_run : `goats_tom.models.DRAGONSRun`
            The run being executed.
        input_paths : list of str
            Paths **on the Data Lab notebook server**, under the read-only
            `~/vospace/` mount. Not GOATS storage names: the runner passes
            these straight to `Reduce.files`.
        calibration_paths : list of str, optional
            Calibrations to register in the run's caldb before reducing.
        recipe_name : str, optional
            Recipe to run, if not the default for the data.
        uparms : list, optional
            User parameter overrides.
        upload_caldb : bool, optional
            Whether to upload `cal_manager.db` with the outputs. False by
            default: it is derived, rebuilt by the next run, and copying a
            live SQLite file risks catching it mid-write.

        Returns
        -------
        `DataLabJob`
        """
        spec = {
            "datalab_base_url": self.config.base_url,
            "datalab_token": self._token(),
            "vospace_root": self.config.user_root(self.credentials.username),
            "destination_prefix": dragons_run.run_id,
            "input_paths": list(input_paths),
            "calibration_paths": list(calibration_paths or []),
            "recipe_name": recipe_name,
            "uparms": uparms or [],
            "upload_caldb": upload_caldb,
        }

        identifiers = self._launch("reduction_runner.py", spec)
        job = DataLabJob.objects.create(
            kind=DataLabJob.Kind.REDUCTION,
            dragons_run=dragons_run,
            user=self.user,
            datalab_username=self.credentials.username,
            status=DataLabJob.Status.RUNNING,
            **identifiers,
        )
        logger.info(
            "Launched Data Lab reduction %s for run %s.", job.job_id, dragons_run.pk
        )
        return job
