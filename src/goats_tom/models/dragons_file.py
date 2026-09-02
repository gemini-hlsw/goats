"""Module for `DRAGONSFile` model."""

__all__ = ["DRAGONSFile"]

import inspect
from typing import Any

import astrodata
from django.db import models
from gempy.scripts import showpars
from numpydoc.docscrape import NumpyDocString
from tom_dataproducts.models import DataProduct

from goats_tom import storage


class DRAGONSFile(models.Model):
    """Represents a file associated with a DRAGONS run.

    Attributes
    ----------
    dragons_run : `models.ForeignKey`
        A foreign key linking to the `DRAGONSRun` instance.
    data_product : `models.ForeignKey`
        A foreign key to the `DataProduct` model that details the data
        product associated with this file.
    modified : `models.DateTimeField`
        The date and time the file was last modified, automatically set to
        the current timestamp when the file object is updated.
    recipes_module : `models.ForeignKey`
        An optional foreign key to the `RecipesModule`, indicating which
        recipes module is associated with this file.
    observation_type : `models.CharField`
        A character field storing the type of the file.
    object_name : `models.CharField`
        An optional character field storing the name of the object related to
        the file, if applicable.

    """

    dragons_run = models.ForeignKey(
        "goats_tom.DRAGONSRun",
        on_delete=models.CASCADE,
        related_name="dragons_run_files",
    )
    data_product = models.ForeignKey(DataProduct, on_delete=models.CASCADE)
    modified = models.DateTimeField(auto_now=True)
    recipes_module = models.ForeignKey(
        "goats_tom.RecipesModule",
        on_delete=models.CASCADE,
        null=True,
        related_name="files",
    )
    observation_type = models.CharField(max_length=50, null=True, blank=True)
    object_name = models.CharField(max_length=100, null=True, blank=True)
    astrodata_descriptors = models.JSONField(default=dict)
    url = models.CharField(max_length=255, null=False, blank=False)
    product_id = models.CharField(max_length=100, null=False, blank=False)
    observation_class = models.CharField(max_length=50, null=False, blank=False)

    class Meta:
        unique_together = ("dragons_run", "data_product")

    @property
    def file_path(self) -> str:
        """Gets the local file path from the data product.

        Returns
        -------
        `str`
            The file path on this machine.

        Raises
        ------
        NotImplementedError
            If the storage backend is not a local filesystem.

        Notes
        -----
        **Local-only, and the last such caller.** Reduction hands this to
        `Reduce.files`, which needs every input present on one filesystem
        for the length of the run -- not one file at a time, which is all
        `local_path` can promise. Moving reduction to Data Lab compute is
        what removes the need, so this stays as it is until then and is
        listed in *Remaining Data Lab work*.

        Anything reading a single file should use `local_path` instead.
        """
        return storage.default_storage.path(storage.name_of(self.data_product))

    def local_path(self):
        """Yield a real filesystem path to this file's bytes.

        Returns
        -------
        context manager yielding `pathlib.Path`
            Valid for the duration of the ``with`` block.

        Notes
        -----
        The single-file counterpart to `file_path`, and the one to reach
        for. Works under any storage backend.
        """
        return storage.local_path(self.data_product)

    @property
    def observation_id(self) -> str:
        """Returns the observation ID for the file.

        Returns
        -------
        `str`
            The observation ID.
        """
        return self.data_product.observation_record.observation_id

    def list_primitives_and_docstrings(self) -> dict[str, Any]:
        """Lists all available primitives and their documentation for the file type
        associated with this DRAGONS file object.

        Returns
        -------
        `dict[str, Any]`
            A dictionary containing method names as keys and another dictionary as
            values, which includes parameters and their documentation, as well as the
            method's docstring parsed according to the numpy documentation standard.

        """
        data = {}
        with self.local_path() as path:
            primitive_obj, _ = showpars.get_pars(str(path))

        for item in dir(primitive_obj):
            if not item.startswith("_") and inspect.ismethod(
                getattr(primitive_obj, item),
            ):
                method = getattr(primitive_obj, item)
                params = primitive_obj.params.get(item)
                if params is not None:
                    data[item] = {
                        "params": {
                            # Filter and store parameters that do not start with
                            # "debug".
                            k: {"value": f"{v}", "doc": f"{params.doc(k)}"}
                            for k, v in params.items()
                            if not k.startswith("debug")
                        },
                        "docstring": {},
                    }
                    try:
                        docstring = NumpyDocString(method.__doc__)
                        # Parse and store the docstring content, transforming section
                        # titles to lowercase and replacing spaces with underscores.
                        data[item]["docstring"] = {
                            section.lower().replace(" ", "_"): content
                            for section, content in docstring._parsed_data.items()
                        }
                    except (ValueError, TypeError) as e:
                        print(f"Error processing docstring for {item}: {str(e)}")
                        continue
                else:
                    print(f"Error getting {item} from params, does not exist.")
                    continue

        return data

    def list_groups(self) -> list[str]:
        """Returns a list of groups for the file.

        Returns
        -------
        `list[str]`
            A list of groups aka descriptors for the file.

        """
        with self.local_path() as path:
            ad = astrodata.open(path)
            return list(ad.descriptors)
