"""Downloads data from GOA in background."""

__all__ = ["download_goa_files"]

import logging
import tarfile
import time

# Now import the DRAGONS libraries
import astrodata
import dramatiq
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from dramatiq.middleware import TimeLimitExceeded
from requests.exceptions import HTTPError
from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationRecord

from goats_tom.astroquery import Observations as GOA
from goats_tom.models import DataProductMetadata, Download, GOALogin
from goats_tom.realtime import DownloadState, NotificationInstance
from goats_tom.utils import create_name_reduction_map

logger = logging.getLogger(__name__)


@dramatiq.actor(
    max_retries=0, time_limit=getattr(settings, "DRAMATIQ_ACTOR_TIME_LIMIT", 86400000)
)
def download_goa_files(
    observation_record_pk: int,
    query_params: dict,
    user: int,
) -> None:
    """Downloads observation files associated with a given observation record from the
    GOA.

    This task logs in to the GOA, queries for relevant files based on the provided
    observation record, and handles the download and metadata extraction for each file.
    Notifications are sent at various stages of the process to update the user on the
    task status.

    Parameters
    ----------
    observation_record_pk : `int`
        The primary key of the observation record.
    query_params : `dict`
        A dictionary containing additional parameters for querying and downloading
        files.
    user : `int`
        The user ID used to retrieve credentials for accessing the GOA.

    Raises
    ------
    `PermissionError`
        Raised if the GOA login fails due to incorrect credentials.
    `HTTPError`
        Raised if an HTTP error occurs during the download process.

    """
    try:
        # Allow page to refresh before displaying notification.
        logger.info("Starting background GOA download task.")
        time.sleep(2)

        download_state = DownloadState()

        # Only ever one observation record passed.
        try:
            observation_record = ObservationRecord.objects.get(pk=observation_record_pk)
        except ObjectDoesNotExist:
            logger.error(
                "Observation record with pk=%s not found. Aborting GOA download.",
                observation_record_pk,
            )
            download_state.update_and_send(status="Failed.", error=True)
            NotificationInstance.create_and_send(
                label="Observation record not found.",
                message="Observation record not found. Cannot start download.",
                color="danger",
            )
            raise
        target = observation_record.target
        facility = observation_record.facility
        observation_id = observation_record.observation_id
        logger.debug(
            "Using Observation record: target=%s, facility=%s, observation id=%s",
            target,
            facility,
            observation_id,
        )

        # Create Download record at the start
        download = Download.objects.create(
            observation_id=observation_id,
            status="Running",
            unique_id=download_state.unique_id,
        )
        logger.debug("Created new Download record: %s", download.pk)

        NotificationInstance.create_and_send(
            message="Download started.",
            label=f"{observation_id}",
        )
        download_state.update_and_send(label=observation_id, status="Starting...")

        # Have to handle logging in for each task.
        prop_data_msg = "Proprietary data will not be downloaded."
        try:
            goa_credentials = GOALogin.objects.get(user=user)
            logger.debug("Found GOA credentials for user=%s", user)

            # Login to GOA.
            GOA.login(goa_credentials.username, goa_credentials.password)
            if not GOA.authenticated():
                raise PermissionError
            logger.info("Successfully authenticated with GOA.")
        except GOALogin.DoesNotExist:
            logger.warning("GOA login credentials not found. %s", prop_data_msg)
        except PermissionError:
            logger.warning(
                "GOA login failed. Re-enter login credentials. %s", prop_data_msg
            )

        # Get target path.
        target_facility_path = (
            settings.MEDIA_ROOT / target.name / facility / observation_id
        )
        logger.debug("Target facility path: %s", target_facility_path)

        # Set default args and kwargs if not provided in query_params.
        args = query_params.get("args", ())
        kwargs = query_params.get("kwargs", {})

        # Determine what to do with calibration data.
        download_calibration = kwargs.pop("download_calibrations", None)
        logger.debug("Download calibration mode: %s", download_calibration)

        # Create blank mapping.
        name_reduction_map = {}
        num_files_omitted = 0
        sci_files = []
        cal_files = []

        # Query GOA for science tarfile.
        if download_calibration != "only":
            try:
                logger.info("[%s] Downloading science files...", observation_id)

                download_state.update_and_send(
                    status="Downloading science files...",
                    downloaded_bytes=0,
                )
                file_list = GOA.query_criteria(*args, **kwargs)
                logger.debug(
                    "[%s] GOA query returned %d files.", observation_id, len(file_list)
                )
                # Create the mapping.
                name_reduction_map = create_name_reduction_map(file_list)
                sci_out = GOA.get_files(
                    target_facility_path,
                    *args,
                    decompress_fits=True,
                    download_state=download_state,
                    **kwargs,
                )
                sci_files = sci_out["downloaded_files"]
                num_files_omitted += sci_out["num_files_omitted"]
                logger.info(
                    "[%s] Downloaded %d science files (%d omitted).",
                    observation_id,
                    len(sci_files),
                    sci_out["num_files_omitted"],
                )
            except tarfile.ReadError:
                logger.exception(
                    "[%s] Error unpacking downloaded science files: ",
                    observation_id,
                )
                NotificationInstance.create_and_send(
                    label=f"{observation_id}",
                    message="Error unpacking science tar file. Try again.",
                    color="warning",
                )

        if download_calibration != "no":
            try:
                if kwargs.get("progid"):
                    logger.info("[%s] Downloading calibration files...", observation_id)
                    download_state.update_and_send(
                        status="Downloading calibration files...",
                        downloaded_bytes=0,
                    )
                    cal_out = GOA.get_calibration_files(
                        target_facility_path,
                        *args,
                        decompress_fits=True,
                        download_state=download_state,
                        **kwargs,
                    )
                    cal_files = cal_out["downloaded_files"]
                    num_files_omitted += cal_out["num_files_omitted"]
                    logger.info(
                        "[%s] Downloaded %d calibration files (%d omitted).",
                        observation_id,
                        len(cal_files),
                        cal_out["num_files_omitted"],
                    )
                else:
                    logger.debug(
                        "[%s] No progid in kwargs; skipping calibration.",
                        observation_id,
                    )
            except tarfile.ReadError:
                logger.exception(
                    "[%s] Error unpacking downloaded calibration files: ",
                    observation_id,
                )
                NotificationInstance.create_and_send(
                    label=f"{observation_id}",
                    message="Error unpacking calibration tar file. Try again.",
                    color="warning",
                )
        download_state.update_and_send(
            status="Finished downloads...",
            downloaded_bytes=None,
        )

        # Handle case if GOA found nothing and did not create folder.
        if not target_facility_path.exists():
            logger.warning(
                "[%s] Target path not created; no files downloaded.", observation_id
            )
            download.finish()
            return

        downloaded_files = set(sci_files + cal_files)
        num_files_downloaded = len(downloaded_files)
        logger.info(
            "[%s] Processing %d downloaded files.", observation_id, num_files_downloaded
        )

        # Now lead by the files in the folder.
        for file_name in downloaded_files:
            file_path = target_facility_path / file_name
            if file_path.suffix != ".fits":
                logger.debug(
                    "[%s] Skipping non-FITS file: %s", observation_id, file_path
                )
                continue

            product_id = str(file_path.relative_to(settings.MEDIA_ROOT))

            # Use the mapping to get the data product type.
            # If not found, return default for calibration.
            data_product_type = name_reduction_map.get(file_path.name, "fits_file")
            # Query DataProduct by product_id.
            candidates = DataProduct.objects.filter(
                product_id=product_id,
                observation_record=observation_record,
                target=target,
            )

            if candidates.exists():
                # If we have candidates, just grab the first one.
                logger.debug(
                    "[%s] Existing DataProduct found for %s", observation_id, product_id
                )
                dp = candidates.first()
            else:
                # Otherwise, create a new DataProduct.
                try:
                    dp = DataProduct.objects.create(
                        product_id=product_id,
                        target=target,
                        observation_record=observation_record,
                        data_product_type=data_product_type,
                    )
                    dp.data.name = product_id
                    dp.save()
                    # TODO: Do we need to add the hook after?
                    # Now create the metadata.
                    ad = astrodata.open(dp.data.path)
                    tags = ad.tags
                    processed = False
                    if "PREPARED" in tags or "PROCESSED" in tags:
                        processed = True
                    DataProductMetadata.objects.create(
                        dataproduct=dp, processed=processed
                    )
                    logger.info(
                        "[%s] Created new DataProduct: %s (processed=%s)",
                        observation_id,
                        dp.data.name,
                        processed,
                    )
                except IntegrityError:
                    logger.warning(
                        "[%s] DataProduct already exists for %s, skipping.",
                        observation_id,
                        file_path.name,
                    )

        GOA.logout()
        logger.debug("[%s] Logged out of GOA.", observation_id)

        # Update downloaded and omitted data.
        download.num_files_downloaded = num_files_downloaded
        download.num_files_omitted = num_files_omitted
        download.finish()
        download_state.update_and_send(status="Done.", done=True)

        # Build message for notificaiton.
        message = f"Downloaded {num_files_downloaded} files."
        if num_files_omitted > 0:
            message += f" {num_files_omitted} proprietary files were omitted."

        NotificationInstance.create_and_send(
            message=f"{message}",
            label=f"{observation_id}",
            color="success",
        )
        logger.info("[%s] Download complete. %s", observation_id, message)
    except TimeLimitExceeded:
        logger.exception("[%s] Task time limit exceeded.", observation_id)
        download.finish(message="Background task time limit hit.", error=True)
        download_state.update_and_send(status="Failed.", error=True)
        NotificationInstance.create_and_send(
            label=f"{observation_id}",
            message="Background task time limit hit. Consider increasing timeout.",
            color="danger",
        )
        raise
    except HTTPError as e:
        logger.exception("[%s] HTTP error during GOA download: ", observation_id)
        download.finish(message=str(e), error=True)
        download_state.update_and_send(status="Failed.", error=True)
        NotificationInstance.create_and_send(
            label=f"{observation_id}",
            message=f"Connection to GOA failed, cannot download files: {e!s}",
            color="danger",
        )
        raise
    except Exception as e:
        logger.exception("[%s] Unexpected error during GOA download: ", observation_id)
        # Catch all other exceptions.
        download.finish(message=str(e), error=True)
        download_state.update_and_send(status="Failed.", error=True)
        NotificationInstance.create_and_send(
            label=f"{observation_id}",
            message=f"Error during download from GOA: {e!s}",
            color="danger",
        )
        raise
