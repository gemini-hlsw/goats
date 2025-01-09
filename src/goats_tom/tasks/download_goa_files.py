"""Downloads data from GOA in background."""

__all__ = ["download_goa_files"]

import logging
import tarfile
import time

# Now import the DRAGONS libraries
import dramatiq
from django.conf import settings
from django.core import serializers
from django.db import IntegrityError
from dramatiq.middleware import TimeLimitExceeded
from requests.exceptions import HTTPError
from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationRecord

from goats_tom.astroquery import Observations as GOA
from goats_tom.models import Download, GOALogin
from goats_tom.realtime import DownloadState, NotificationInstance
from goats_tom.utils import create_name_reduction_map

logger = logging.getLogger(__name__)


@dramatiq.actor(
    max_retries=0, time_limit=getattr(settings, "DRAMATIQ_ACTOR_TIME_LIMIT", 86400000)
)
def download_goa_files(
    serialized_observation_record: str,
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
    serialized_observation_record : `str`
        A JSON serialized string of the observation record object.
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
        print("Running background task.")
        time.sleep(2)

        download_state = DownloadState()

        # Only ever one observation record passed.
        observation_record = list(
            serializers.deserialize("json", serialized_observation_record),
        )[0].object
        target = observation_record.target
        facility = observation_record.facility
        observation_id = observation_record.observation_id

        # Create Download record at the start
        download = Download.objects.create(
            observation_id=observation_id,
            status="Running",
            unique_id=download_state.unique_id,
        )

        NotificationInstance.create_and_send(
            message="Download started.",
            label=f"{observation_id}",
        )
        download_state.update_and_send(label=observation_id, status="Starting...")

        # Have to handle logging in for each task.
        prop_data_msg = "Proprietary data will not be downloaded."
        try:
            goa_credentials = GOALogin.objects.get(user=user)
            # Login to GOA.
            GOA.login(goa_credentials.username, goa_credentials.password)

            if not GOA.authenticated():
                raise PermissionError
        except GOALogin.DoesNotExist:
            logger.warning(f"GOA login credentials not found. {prop_data_msg}")
        except PermissionError:
            logger.warning(
                f"GOA login failed. Re-enter login credentials. {prop_data_msg}"
            )

        # Get target path.
        target_facility_path = (
            settings.MEDIA_ROOT / target.name / facility / observation_id
        )

        # Set default args and kwargs if not provided in query_params.
        args = query_params.get("args", ())
        kwargs = query_params.get("kwargs", {})

        # Determine what to do with calibration data.
        download_calibration = kwargs.pop("download_calibrations", None)

        # Create blank mapping.
        name_reduction_map = {}
        num_files_omitted = 0
        sci_files = []
        cal_files = []

        # Query GOA for science tarfile.
        if download_calibration != "only":
            try:
                print(f"{observation_id}: Downloading science files...")

                download_state.update_and_send(
                    status="Downloading science files...",
                    downloaded_bytes=0,
                )
                file_list = GOA.query_criteria(*args, **kwargs)
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
            except tarfile.ReadError:
                print("Error unpacking downloaded science files, skipping.")
                NotificationInstance.create_and_send(
                    label=f"{observation_id}",
                    message="Error unpacking science tar file. Try again.",
                    color="warning",
                )

        if download_calibration != "no":
            try:
                if kwargs.get("progid"):
                    print(f"{observation_id}: Downloading calibration files...")
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
                else:
                    print("No observation ID provided, skipping calibration.")
            except tarfile.ReadError:
                print("Error unpacking downloaded calibration files, skipping.")
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
            download.finish()
            return

        downloaded_files = set(sci_files + cal_files)
        num_files_downloaded = len(downloaded_files)

        # Now lead by the files in the folder.
        for file_name in downloaded_files:
            file_path = target_facility_path / file_name
            if file_path.suffix != ".fits":
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
                    logger.info("Saved new dataproduct from tarfile: %s", dp.data)
                except IntegrityError:
                    logger.error(
                        "There already exists a data product '%s', skipping.",
                        file_path.name,
                    )

        GOA.logout()

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
        print("Done.")
    except TimeLimitExceeded:
        download.finish(message="Background task time limit hit.", error=True)
        download_state.update_and_send(status="Failed.", error=True)
        NotificationInstance.create_and_send(
            label=f"{observation_id}",
            message="Background task time limit hit. Consider increasing timeout.",
            color="danger",
        )
        raise
    except HTTPError as e:
        download.finish(message=str(e), error=True)
        download_state.update_and_send(status="Failed.", error=True)
        NotificationInstance.create_and_send(
            label=f"{observation_id}",
            message=f"Connection to GOA failed, cannot download files: {e!s}",
            color="danger",
        )
        raise
    except Exception as e:
        # Catch all other exceptions.
        download.finish(message=str(e), error=True)
        download_state.update_and_send(status="Failed.", error=True)
        NotificationInstance.create_and_send(
            label=f"{observation_id}",
            message=f"Error during download from GOA: {e!s}",
            color="danger",
        )
        raise


def _generate_product_id(filename: str, observation_record: ObservationRecord) -> str:
    """Generates the product ID.

    Parameters
    ----------
    filename : `str`
        The name of the file, no extension.
    observation_record : `ObservationRecord`
        The observation record for this product.

    Returns
    -------
    `str`
        The detailed product ID.
    """
    product_id = f"{observation_record.target.name}__"
    product_id += f"{observation_record.observation_id}__"
    product_id += f"{filename}"
    return product_id
