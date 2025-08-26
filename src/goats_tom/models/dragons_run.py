"""Model for DRAGONS runs."""

__all__ = ["DRAGONSRun"]

import datetime
import shutil
import subprocess
from importlib import metadata
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models
from recipe_system import cal_service
from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationRecord

from goats_tom.models import DRAGONSRecipe


def get_dragons_version():
    try:
        # FIXME: Remove this conda subprocess when DRAGONS updates.
        # Run 'conda list dragons' and capture the output.
        result = subprocess.run(
            ["conda", "list", "dragons"], capture_output=True, text=True, check=True
        )
        # Parse the output to find the version.
        for line in result.stdout.splitlines():
            if line.startswith("dragons"):
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]
    except subprocess.CalledProcessError:
        pass
    try:
        return metadata.version("dragons")
    except metadata.PackageNotFoundError:
        return "Unknown"


class DRAGONSRun(models.Model):
    """Represents a DRAGONS run setup configuration.

    This model stores configuration data for a DRAGONS run, including
    references to the associated observation record, run identifier,
    configuration filename, output directory, calibration manager filename,
    and log filename.

    Attributes
    ----------
    observation_record : `models.ForeignKey`
        The ObservationRecord this DRAGONS run is associated with.
    run_id : `models.CharField`
        Unique ID for the DRAGONS run, with a default format
        including timestamp.
    config_filename : `models.CharField`
        Filename for the DRAGONS configuration, not editable post-creation.
    output_directory : `models.CharField`
        Directory for output files from the DRAGONS run.
    cal_manager_filename : `models.CharField`
        Filename for the DRAGONS calibration manager, not editable
        post-creation.
    log_filename : `models.CharField`
        Filename for the DRAGONS run log, read-only.
    created : `models.DateTimeField`
        The time at which this object was created.
    modified : `models.DateTimeField`
        The time at which this object was last modified.

    Methods
    -------
    save(*args, **kwargs) -> None:
        Saves the DRAGONSRun instance, applying default value for `run_id` and
        matches `output_directory` with `run_id`.

    get_output_dir() -> Path:
        Constructs and returns the full path to the output directory.

    get_raw_dir() -> Path:
        Constructs and returns the full path to the raw directory based on the
        observation record's properties.

    """

    observation_record = models.ForeignKey(
        ObservationRecord,
        on_delete=models.CASCADE,
        related_name="dragons_runs",
    )
    run_id = models.CharField(
        max_length=255,
        blank=True,
    )
    config_filename = models.CharField(max_length=30, default="dragonsrc")
    output_directory = models.CharField(
        max_length=255,
        blank=True,
        editable=False,
    )
    cal_manager_filename = models.CharField(max_length=30, default="cal_manager.db")
    log_filename = models.CharField(max_length=30, default="log.log", editable=False)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    version = models.CharField(
        max_length=30,
        editable=False,
        blank=False,
        null=False,
        default=get_dragons_version,
    )

    class Meta:
        # Ensure run_id is unique within the scope of each
        # "observation_record".
        constraints = [
            models.UniqueConstraint(
                fields=["observation_record", "run_id"],
                name="unique_observation_run_id",
            ),
        ]
        # Index by "run_id" for easy filtering and getting.
        indexes = [
            models.Index(fields=["run_id"], name="run_id_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.observation_record.observation_id}.{self.run_id}"

    def save(self, *args, **kwargs) -> None:
        """Saves the DRAGONSRun instance.

        Applies default values for "run_id" and assigns `output_directory`.
        """
        # TODO: Do we want to allow spaces in `run_id`?
        if not self.run_id:
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            self.run_id = f"run-{timestamp}"

        # Output directory matches `run_id`.
        self.output_directory = self.run_id

        return super(DRAGONSRun, self).save(*args, **kwargs)

    def get_output_dir(self) -> Path:
        """Returns the full path to the output directory.

        Returns
        -------
        `Path`
            The full path to the output directory.

        """
        return self.get_raw_dir() / self.output_directory

    def remove_output_dir(self) -> None:
        """Removes the output directory and its contents recursively."""
        output_dir = self.get_output_dir()
        if output_dir.exists():
            try:
                shutil.rmtree(output_dir)
            except Exception as e:
                print(f"Error deleting output directory {output_dir}: {e}")

    def get_cal_manager_db_file(self) -> Path:
        """Returns the full path to the calibration manager database file.

        Returns
        -------
        `Path`
            The full path to the calibration manager database file.

        """
        return self.get_output_dir() / self.cal_manager_filename

    def get_caldb(self) -> cal_service.LocalDB:
        """Gets the calibration database instance.

        Returns
        -------
        `cal_service.LocalDB`
            Instance of the calibration database.
        """
        # TODO: Error handling.
        return cal_service.LocalDB(self.get_cal_manager_db_file(), force_init=False)

    def get_calibrations_uploaded_dir(self) -> Path:
        """Retrieves the path to the uploaded calibrations directory within the output
        directory, creating it if it does not exist.

        Returns
        -------
        `Path`
            The path to the uploaded calibrations directory.
        """
        # Define the path to the uploaded calibrations directory.
        uploaded_dir = self.get_output_dir() / "calibrations" / "uploaded"

        # Ensure the directory exists.
        uploaded_dir.mkdir(parents=True, exist_ok=True)

        return uploaded_dir

    def get_log_file(self) -> Path:
        """Returns the full path to the log file.

        Returns
        -------
        `Path`
            The full path to the log file.

        """
        return self.get_output_dir() / self.log_filename

    def get_config_file(self) -> Path:
        """Returns the full path to the configuration file.

        Returns
        -------
        `Path`
            The full path to the configuration file.

        """
        return self.get_output_dir() / self.config_filename

    def get_raw_dir(self) -> Path:
        """Returns the full path to the raw directory.

        Returns
        -------
        `Path`
            The full path to the associated observation ID directory.

        """
        raw_dir = (
            settings.MEDIA_ROOT
            / f"{self.observation_record.target.name}"
            / f"{self.observation_record.facility}"
            / f"{self.observation_record.observation_id}"
        )
        return raw_dir

    def get_recipes(self):
        return DRAGONSRecipe.objects.filter(version=self.version)

    def list_groups(self) -> list[str]:
        """Returns a list of groups aka descriptors from an associated first file.

        Returns
        -------
        `list[str]`
            The list of groups.
        """
        first_file = self.dragons_run_files.first()

        if first_file:
            return first_file.list_groups()

        return []

    def close_caldb(self, caldb: cal_service.LocalDB) -> None:
        """Closes the calibration manager to protect threads.

        Parameters
        ----------
        caldb : `cal_service.LocalDB`
            The instance of the calibration database.
        """
        try:
            caldb._calmgr.session.close()
        except Exception:
            pass

    def add_caldb_file(self, filepath: str | Path) -> None:
        """Adds a file to the calibration database.

        Parameters
        ----------
        filepath : `str | Path`
            The path to the file to add.
        """
        caldb = self.get_caldb()
        try:
            caldb.add_cal(filepath)
        finally:
            self.close_caldb(caldb)

    def remove_caldb_file(self, filename: str) -> None:
        """Removes a file from the calibration database.

        Parameters
        ----------
        filename : `str`
            The file to remove.
        """
        caldb = self.get_caldb()
        try:
            caldb.remove_cal(filename)
        finally:
            self.close_caldb(caldb)

    def check_and_remove_caldb_file(self, filename: str) -> None:
        """Checks if a file is a caldb file, if so, removes it.

        Parameters
        ----------
        filename : `str`
            The name of the file to remove.
        """
        existing_files = self.list_caldb_files()
        if any(filename == f["name"] for f in existing_files):
            self.remove_caldb_file(filename)

    def list_caldb_files(self) -> list[dict[str, str]]:
        """Lists all files in the calibration database.

        Returns
        -------
        `list[dict[str, str]]`
            The list of dicts of all files in the calibration database.
        """
        caldb = self.get_caldb()
        files = []
        try:
            for f in caldb.list_files():
                relative_path = (
                    Path(f.path).joinpath(f.name).relative_to(settings.MEDIA_ROOT)
                )
                files.append(
                    {
                        "name": f.name,
                        "path": str(relative_path.parent),
                        "is_user_uploaded": Path(f.path).name == "uploaded",
                        "url": f"{settings.MEDIA_URL}{relative_path}",
                    }
                )
        finally:
            self.close_caldb(caldb)
        return files

    def clean_caldb_uploaded_files(self) -> None:
        """Removes files in uploaded directory that are not part of the database."""
        caldb = self.get_caldb()
        uploaded_dir = self.get_calibrations_uploaded_dir()

        try:
            files = [Path(f.path) / f.name for f in caldb.list_files()]
            # Iterate over each file in the uploaded directory.
            for filepath in uploaded_dir.iterdir():
                if filepath not in files:
                    print("removing file: ", filepath)
                    # Remove files not in database in uploaded.
                    filepath.unlink()
        finally:
            self.close_caldb(caldb)

    def remove_file(self, filepath: Path) -> None:
        """Removes a file and removes it from caldb if it exists.

        Parameters
        ----------
        filepath : `Path`
            Path to the file.
        """
        try:
            full_path = Path(default_storage.path(str(filepath)))
            filename = filepath.name
            full_path.unlink()
            self.check_and_remove_caldb_file(filename)

        except OSError as e:
            print(f"Failed to remove file {filepath}: {e}")

    def get_processed_files(self) -> list[dict]:
        """Returns all the processed output files of the output directory, combined
        with any additional `DataProducts` that are processed but not in the output
        directory.

        Returns
        -------
        `list[dict]`
            A list of file information dictionaries.
        """
        output_dir = self.get_output_dir()
        output_files = []

        # Query all processed DataProducts.
        data_products_qs = DataProduct.objects.filter(
            observation_record=self.observation_record, metadata__processed=True
        )

        # Create a dict from product_id to the DataProduct instance for quick lookups.
        data_products = {dp.product_id: dp for dp in data_products_qs}

        # Keep a set to record which product_ids we’ve already handled (to avoid
        # duplicates).
        processed_product_ids: set[str] = set()

        # Iterate over files in the output directory.
        for f in output_dir.glob("*.fits"):
            # Get the file's last modified time, convert it to UTC, and format it.
            last_modified = datetime.datetime.fromtimestamp(
                f.stat().st_mtime, datetime.timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S")

            # Generate the product ID from the file path.
            potential_product_id = str(f.relative_to(settings.MEDIA_ROOT))

            # Check if this file is backed by a DataProduct.
            dp = data_products.get(potential_product_id)
            is_dataproduct = dp is not None
            if is_dataproduct:
                # Mark this product_id as processed so we don't add it again later.
                processed_product_ids.add(potential_product_id)

            # Append the file info to output_files.
            output_files.append(
                {
                    "name": f.name,
                    "path": str(f.parent.relative_to(settings.MEDIA_ROOT)),
                    "last_modified": last_modified,
                    "is_dataproduct": is_dataproduct,
                    "dataproduct_id": dp.id if dp else None,
                    "product_id": potential_product_id,
                    "url": f"{settings.MEDIA_URL}{potential_product_id}",
                }
            )

        # Add remaining DataProducts not in the output_dir.
        # These have processed=True but aren't found in output_dir.
        for product_id, dp in data_products.items():
            if product_id not in processed_product_ids:
                dp_path = Path(dp.data.name)
                output_files.append(
                    {
                        "name": dp_path.name,
                        "path": str(dp_path.parent),
                        "is_dataproduct": True,
                        "dataproduct_id": dp.id,
                        "product_id": product_id,
                        "url": dp.data.url,
                        # Match same format as above.
                        "last_modified": dp.modified.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

        return sorted(output_files, key=lambda x: x["product_id"])
