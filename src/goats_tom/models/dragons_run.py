"""Model for DRAGONS runs."""

__all__ = ["DRAGONSRun"]

import datetime
from importlib import metadata
from pathlib import Path

from django.conf import settings
from django.db import models
from recipe_system import cal_service
from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationRecord

from goats_tom.models import DRAGONSRecipe


def get_dragons_version():
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
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        if not self.run_id:
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

    def list_caldb_files(self) -> list[dict[str, str]]:
        """Lists all files in the calibration database.

        Returns
        -------
        `list[dict[str, str]]`
            The list of dicts of all files in the calibration database.
        """
        caldb = self.get_caldb()
        try:
            files = []
            for f in caldb.list_files():
                path = Path(f.path)
                files.append(
                    {
                        "name": f.name,
                        "path": str(path.relative_to(settings.MEDIA_ROOT)),
                        "is_user_uploaded": path.name == "uploaded",
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
                    # Remove files not in database in uploaded.
                    filepath.unlink()
        finally:
            self.close_caldb(caldb)

    def generate_dragons_run_product_id(self, filename) -> str:
        """Generates the run data product ID.

        Parameters
        ----------
        filename : `str`
            The filename.

        Returns
        -------
        `str`
            The product ID with the run ID.
        """
        product_id = ""
        product_id += f"{self.observation_record.target.name}"
        product_id += f"__{self.observation_record.observation_id}"
        product_id += f"__{self.run_id}__{filename}"

        return product_id

    def remove_output_file(self, filename: str) -> None:
        """Removes the filename from the output directory.

        Parameters
        ----------
        filename : `str`
            The filename to remove.

        """
        filepath = self.get_output_dir() / filename
        try:
            filepath.unlink()
        except OSError as e:
            print(f"Failed to remove file {filename}: {e}")

    def get_output_files(self) -> list[dict[str, str]]:
        """Returns all the output files (*.fits) of the output directory.

        Returns
        -------
        `list[dict[str, str]]`
            List of the name and path of the files in the output directory.
        """
        output_dir = self.get_output_dir()

        output_files = []

        # Retrieve all DataProducts associated with the observation_record and map them
        # by product_id.
        data_products = {
            dp.product_id: dp.id
            for dp in DataProduct.objects.filter(
                observation_record=self.observation_record
            )
        }

        for f in output_dir.glob("*.fits"):
            # Get the file's last modified time, convert it to UTC, and format it.
            last_modified_time = datetime.datetime.fromtimestamp(
                f.stat().st_mtime, datetime.timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S")

            # Generate the product ID for the file.
            potential_product_id = str(f.relative_to(settings.MEDIA_ROOT))

            # Check if this file is a data product.
            dataproduct_id = data_products.get(potential_product_id)
            is_dataproduct = dataproduct_id is not None

            # Append the file information to the list as a dictionary.
            output_files.append(
                {
                    "name": f.name,
                    # Don't want to provide full path.
                    "path": str(f.parent.relative_to(settings.MEDIA_ROOT)),
                    "last_modified": last_modified_time,
                    "is_dataproduct": is_dataproduct,
                    "dataproduct_id": dataproduct_id,
                    "product_id": potential_product_id,
                }
            )

        return sorted(output_files, key=lambda x: x["last_modified"], reverse=True)
