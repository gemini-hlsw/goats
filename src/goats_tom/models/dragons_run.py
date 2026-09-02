"""Model for DRAGONS runs."""

__all__ = ["DRAGONSRun"]

import datetime
import shutil
import subprocess
from importlib import metadata
from pathlib import Path

from django.core.files.storage import default_storage
from django.db import models
from recipe_system import cal_service
from tom_dataproducts.models import DataProduct
from tom_observations.models import ObservationRecord

from goats_tom import storage
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
    #: When each output file was written, as ``{storage name: unix time}``.
    #:
    #: Only used when the storage backend cannot answer the question itself.
    #: `FileSystemStorage` knows a file's mtime, so locally this stays empty
    #: and nothing reads it; `VOSpaceStorage` cannot -- ``/storage/ls`` does
    #: not report timestamps -- and without this a file the reduction had
    #: just rewritten would be labelled "unchanged" in the processed-files
    #: panel. Telling a PI a file is unchanged when it was overwritten is
    #: worse than telling them nothing.
    #:
    #: Per file rather than per run, because a run is not one reduction. A
    #: recipe can be rerun repeatedly within the same run; each rerun
    #: rewrites some outputs and leaves others alone, and entries the newest
    #: job did not touch keep the time they already had.
    output_written_at = models.JSONField(default=dict, blank=True, editable=False)
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
            storage.working_root()
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
                    Path(f.path).joinpath(f.name).relative_to(storage.working_root())
                )
                files.append(
                    {
                        "name": f.name,
                        "path": str(relative_path.parent),
                        "is_user_uploaded": Path(f.path).name == "uploaded",
                        # Through the backend, not MEDIA_URL, which is a
                        # local path that serves nothing in `datalab` mode.
                        "url": default_storage.url(str(relative_path)),
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

    def is_valid_file(self, f) -> bool:
        """
        Validates if the file is FITS, TEXT or ASCII.

        Parameters
        ----------
        f : Path
            Path object of the file

        Returns
        -------
        bool
            True if the file is valid, False otherwise
        """
        # Valid extensions
        valid_extensions = [".txt", ".dat", ".ascii", ".csv", ".fits", ".fit"]

        return f.suffix.lower() in valid_extensions

    def get_output_prefix(self) -> str:
        """Return the storage-relative prefix this run writes outputs under.

        Returns
        -------
        `str`
            e.g. ``"M31/GEM/GS-2026A-Q-1-1/my_run/outputs"``.

        Notes
        -----
        The name counterpart to `get_output_dir`. A storage backend is asked
        for names, not paths, and a remote run has no local directory to
        glob at all.
        """
        return str(self.get_output_dir().relative_to(storage.working_root()))

    def get_processed_files(self) -> list[dict]:
        """Returns all the processed output files of the output directory, combined
        with any additional `DataProducts` that are processed but not in the output
        directory.

        Returns
        -------
        `list[dict]`
            A list of file information dictionaries.

        Notes
        -----
        **Listed through the storage backend, not by globbing a directory.**
        This is the panel a PI uses to choose which reduction outputs become
        data products, and that choice is deliberately manual -- the local
        reduction records nothing itself, and neither does the remote one.
        Nothing here promotes a file automatically.

        A remote run has no local output directory, so `Path.glob` would
        return nothing and the panel would sit empty after a reduction that
        worked. Asking `default_storage` gives the same answer in both modes.

        **Modification times come from the backend when it can answer, and
        from `output_written_at` when it cannot.** `FileSystemStorage` knows
        a file's mtime; `VOSpaceStorage` does not, because ``/storage/ls``
        does not report one. Falling back to "unchanged" there was wrong,
        not merely imprecise: a file the reduction had just overwritten
        would be labelled unchanged, which tells the PI something false.
        So the reduction runner records the time it wrote each file and the
        supervisor merges those into `output_written_at`.
        """
        prefix = self.get_output_prefix()
        output_files = []

        # Query all processed DataProducts
        data_products_qs = DataProduct.objects.filter(
            observation_record=self.observation_record, metadata__processed=True
        )
        data_products = {dp.product_id: dp for dp in data_products_qs}
        processed_product_ids: set[str] = set()

        try:
            _, names = default_storage.listdir(prefix)
        except (FileNotFoundError, NotADirectoryError, OSError):
            # No outputs yet, which is the normal state before a run has
            # produced anything. Not an error, and the panel should show the
            # data products below rather than fail.
            names = []

        for name in names:
            if not self.is_valid_file(Path(name)):
                continue

            potential_product_id = f"{prefix}/{name}"
            dp = data_products.get(potential_product_id)
            is_dataproduct = dp is not None

            file_mtime = None
            try:
                file_mtime = default_storage.get_modified_time(potential_product_id)
            except (NotImplementedError, OSError):
                # The backend cannot answer, so use what the runner recorded
                # when it wrote the file -- the only record that exists.
                recorded = (self.output_written_at or {}).get(potential_product_id)
                if recorded:
                    file_mtime = datetime.datetime.fromtimestamp(
                        recorded, datetime.timezone.utc
                    )

            if is_dataproduct:
                processed_product_ids.add(potential_product_id)
                status = (
                    "updated"
                    if file_mtime is not None and file_mtime > dp.modified
                    else "unchanged"
                )
            else:
                status = "new"

            output_files.append(
                {
                    "name": name,
                    "path": prefix,
                    "last_modified": (
                        file_mtime.strftime("%Y-%m-%d %H:%M:%S")
                        if file_mtime is not None
                        else None
                    ),
                    "is_dataproduct": is_dataproduct,
                    "dataproduct_id": dp.id if dp else None,
                    "product_id": potential_product_id,
                    # Asked of the backend rather than built from MEDIA_URL,
                    # which is a local path that no longer serves anything
                    # in `datalab` mode. The data product branch below
                    # already did this correctly; these two disagreed.
                    "url": default_storage.url(potential_product_id),
                    "status": status,
                }
            )

        # Add remaining DataProducts not in output_dir
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
                        "last_modified": dp.modified.strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "unchanged",
                    }
                )

        return sorted(output_files, key=lambda x: x["product_id"])
