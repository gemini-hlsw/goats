"""Utility functions."""

__all__ = [
    "delete_associated_data_products",
    "create_name_reduction_map",
    "custom_data_product_path",
    "build_json_response",
    "extract_metadata",
    "get_short_name",
    "get_astrodata_header",
    "get_recipes_and_primitives",
    "is_gpp_id",
    "is_ocs_id",
]

import importlib
import inspect
import logging
import re
from pathlib import Path
from typing import Any

import astrodata
from astropy.table import Table
from django.core.exceptions import SuspiciousFileOperation
from django.http import JsonResponse
from recipe_system.mappers.recipeMapper import RecipeMapper
from recipe_system.utils.errors import ModeError, RecipeNotFound
from rest_framework import status
from tom_dataproducts.models import DataProduct, ReducedDatum
from tom_observations.models import ObservationRecord

from goats_tom import storage
from goats_tom.context.user_context import get_current_user_id

logger = logging.getLogger(__name__)


def delete_associated_data_products(
    record_or_product: ObservationRecord | DataProduct,
) -> None:
    """Utility function to delete associated DataProducts or a single
    DataProduct.

    Parameters
    ----------
    record_or_product : ObservationRecord | DataProduct
        The ObservationRecord object to find associated DataProducts,
        or a single DataProduct to be deleted.

    """
    if isinstance(record_or_product, ObservationRecord):
        query = DataProduct.objects.filter(observation_record=record_or_product)
    elif isinstance(record_or_product, DataProduct):
        query = [record_or_product]
    else:
        raise ValueError(
            "Invalid argument type. Must be ObservationRecord or DataProduct.",
        )

    for data_product in query:
        # Delete associated ReducedDatum objects.
        ReducedDatum.objects.filter(data_product=data_product).delete()

        # Delete the file from the disk.
        data_product.data.delete()

        # Delete thumbnail from the disk.
        data_product.thumbnail.delete()

        # Delete the `DataProduct` object from the database.
        data_product.delete()


def create_name_reduction_map(file_list: Table) -> dict[str, str]:
    """Create a mapping from file "name" to "reduction" values from GOA.

    Parameters
    ----------
    file_list : `Table`
        Astropy `Table` containing file information.

    Returns
    -------
    `dict[str, str]`
        A dictionary mapping file 'name' to their 'reduction' values.

    """
    # Hardcode 'fits_file' for the reduction type.
    return {row["name"]: "fits_file" for row in file_list}


def _datalab_storage_enabled() -> bool:
    """Whether data product files are stored in VOSpace rather than locally.

    Returns
    -------
    bool

    Notes
    -----
    Asks the configured backend what it *is*, rather than reading a settings
    flag. `custom_data_product_path` and `VOSpaceStorage` have to agree
    about which naming scheme is in force, and two independent reads of a
    flag can disagree -- during a test that overrides one and not the other,
    for instance. The backend is the single fact both depend on.
    """
    from django.core.files.storage import default_storage  # noqa: PLC0415

    from goats_tom.astro_data_lab import VOSpaceStorage  # noqa: PLC0415

    backend = getattr(default_storage, "_wrapped", default_storage)
    return isinstance(backend, VOSpaceStorage)


def _data_product_owner(data_product: DataProduct):
    """Return the user whose storage `data_product` belongs in.

    Parameters
    ----------
    data_product : `DataProduct`
        The product being saved.

    Returns
    -------
    `django.contrib.auth.models.User` or None
        The owner, or `None` when it cannot be determined.

    Notes
    -----
    Two sources, in order.

    The **observation record's owner** is preferred, because it is durable:
    it is stored on the row and gives the same answer whenever it is asked.
    It is populated on every creation path -- see
    `grant_observation_permissions`, which sets it alongside the guardian
    rows.

    The **request user** is the fallback, for manually uploaded products
    that have no observation record. `custom_data_product_path` is called by
    Django during `save()` and receives only the instance and a filename, so
    there is no request to read; `UserContextMiddleware` puts the id in a
    `ContextVar` for exactly this kind of lookup.

    That order matters. Preferring the request user would file a co-I's
    upload into their own storage when the observation belongs to the PI,
    splitting one observation's data across two accounts.

    Returns `None` rather than guessing. The caller decides what to do with
    that, and in `datalab` mode the answer is to refuse.
    """
    record = data_product.observation_record
    if record is not None and getattr(record, "user_id", None) is not None:
        return record.user

    user_id = get_current_user_id()
    if user_id is None:
        return None

    from django.contrib.auth import get_user_model  # noqa: PLC0415

    return get_user_model().objects.filter(pk=user_id).first()


def custom_data_product_path(data_product: DataProduct, filename: str) -> str:
    """Override where data products are saved. This is set in "settings.py"

    Parameters
    ----------
    data_product : `DataProduct`
        The data product to save.
    filename : `str`
        The filename to use.

    Returns
    -------
    `str`
        The path to the data product.

    Raises
    ------
    SuspiciousFileOperation
        In ``datalab`` mode only, when the owner cannot be determined.

    Notes
    -----
    **The local path is unchanged.** With `GOATS_FILE_STORAGE` unset this
    returns exactly what it always did, so a desktop install writes to the
    same places and nothing pays for a feature it does not use.

    In ``datalab`` mode it prefixes ``users/<username>/goats/``, because a
    Django storage backend is handed a name and nothing else -- no request,
    no user -- so `VOSpaceStorage` can only learn whose VOSpace to write to
    by reading it out of the name. Without this prefix that backend refuses
    every file GOATS creates.

    The username is the **Data Lab** one, taken from the owner's linked
    account, not their GOATS username. `VOSpaceStorage` resolves credentials
    the same way, and the two must agree or files would be written under one
    name and looked for under another.

    **Refuses rather than guesses** when there is no owner. A rejected write
    fails loudly and stops a download; a guessed one puts a PI's proprietary
    data in somebody else's Data Lab account, silently, and nothing in GOATS
    would notice.
    """
    if data_product.observation_record is not None:
        suffix = (
            f"{data_product.target.name}/{data_product.observation_record.facility}"
            f"/{data_product.observation_record.observation_id}/{filename}"
        )
    else:
        suffix = f"{data_product.target.name}/none/none/{filename}"

    if not _datalab_storage_enabled():
        return suffix

    owner = _data_product_owner(data_product)
    if owner is None:
        raise SuspiciousFileOperation(
            f"Cannot determine who {filename} belongs to, so there is no "
            "VOSpace to store it in. A data product needs either an "
            "observation record with an owner or an authenticated uploader."
        )

    credentials = getattr(owner, "astrodatalablogin", None)
    if credentials is None or not credentials.username:
        raise SuspiciousFileOperation(
            f"{owner.username} has no linked Astro Data Lab account, so "
            f"{filename} has nowhere to live. Link one in Settings."
        )

    return f"users/{credentials.username}/goats/{suffix}"


def build_json_response(
    error_message: str | None = None,
    error_status: int | None = status.HTTP_200_OK,
) -> JsonResponse:
    """Build a JSON response.

    Parameters
    ----------
    error_message : `str`, optional
        The error message to include in the response. If `None`, the response
        indicates a successful operation.
    error_status : `int`, optional
        The HTTP status code for the response. Defaults to 200 (HTTP_200_OK).

    Returns
    -------
    `JsonResponse`
        A JSON response with either a success or error status.

    """
    if error_message:
        return JsonResponse(
            {"status": "error", "message": error_message},
            status=error_status,
        )

    return JsonResponse({"status": "success", "message": ""}, status=error_status)


def extract_metadata(file_path: Path) -> dict | None:
    """Extract metadata from a file using astrodata.

    Parameters
    ----------
    file_path : `Path`
        The path to the file from which to extract metadata.

    Returns
    -------
    `dict | None`
        A dictionary containing extracted metadata, or `None` if the file is
        marked as "PREPARED" or does not meet criteria for metadata extraction.

    Notes
    -----
    This function utilizes the astrodata library to open and extract relevant
    metadata from files. It identifies the file type based on specific tags
    and observation classes present in the file's metadata.

    """
    # Open the file using astrodata.
    ad = astrodata.open(file_path)

    # Only want unprepared or BPM files.
    if "BPM" in ad.tags or "UNPREPARED" in ad.tags:
        # Skip all prepared and processed files.
        if "PREPARED" in ad.tags or "PROCESSED" in ad.tags:
            return
        # Construct the metadata dictionary.
        metadata_dict = {
            "observation_type": ad.observation_type(),
            # "observation_class", ad.observation_class(),
            "group_id": (
                ad.group_id() if "GNIRS" not in ad.instrument() else None
            ),  # GNIRS not implemented yet with groups.
            "exposure_time": ad.exposure_time(),
            "object_name": ad.object(),
            "central_wavelength": ad.central_wavelength(),
            "wavelength_band": ad.wavelength_band(),
            "observation_date": ad.ut_date().isoformat(),
            "roi_setting": ad.detector_roi_setting(),
            "instrument": ad.instrument(generic=True).lower(),
            "tags": list(ad.tags),
        }

        return metadata_dict
    return


def get_short_name(name: str) -> str | None:
    """Extracts the short name from the recipe's full name.

    Returns
    -------
    `str | None`
        The short name extracted after "::" if present.

    """
    # Regular expression pattern to capture text after "::".
    pattern = r"::(\w+)$"
    # Using re.search to find the match.
    match = re.search(pattern, name)
    if match:
        return match.group(1)
    return None


def get_astrodata_header(data_product: DataProduct) -> dict[str, Any]:
    """Gets the header information from astrodata.

    Parameters
    ----------
    data_product : `DataProduct`
        The data product to extract headers.

    Returns
    -------
    `dict[str, Any]`
        Header payload from astrodata.

    """
    with storage.local_path(data_product) as path:
        ad = astrodata.open(path)
    # Prepare the header information.
    header = {}
    for descriptor in ad.descriptors:
        # Fetch the value of the descriptor.
        value = getattr(ad, descriptor)()

        # Append the descriptor data to the header list.
        header[descriptor] = value

    return header


def get_recipes_and_primitives(tags: set, instrument: str) -> dict[str, Any]:
    """Retrieves all applicable recipes and their associated primitives based on the
    given tags and instrument. It also determines which recipe should be considered the
    default for the given parameters.

    Parameters
    ----------
    tags : `set`
        A set of tags associated with the file, used to identify applicable recipes.
    instrument : `str`
        The instrument type, used to filter recipes specific to the instrument.

    Returns
    -------
    `dict[str, Any]`
        A dictionary containing recipes keyed by their names, each with details such as
        the recipe's function definition, module, and whether it is the default recipe.
    """
    recipes = {}

    # Attempt to get recipes for just "sq" for GOATS.
    for mode in ["sq"]:
        try:
            recipe_mapper = RecipeMapper(tags, instrument, mode=mode)
            applicable_recipe = recipe_mapper.get_applicable_recipe()
            module = importlib.import_module(applicable_recipe.__module__)
            # Loop through and build the recipe function definition from primitives.
            for func_name, func in inspect.getmembers(
                module,
                inspect.isfunction,
            ):
                if func_name == "_default":
                    # Skip the default as this is listed twice if it is included.
                    continue

                recipe_name = f"{func.__module__}::{func.__name__}"
                recipe_module = f"{func.__module__.split('.')[-1]}"
                # Want to skip common as they are just to be shared between recipe
                # modules.
                if recipe_module == "recipes_common":
                    continue

                source_code = inspect.getsource(func)
                is_default = func.__name__ == applicable_recipe.__name__

                recipes[recipe_name] = {
                    "function_definition": source_code,
                    "is_default": is_default,
                    "recipes_module": recipe_module,
                }

        except (RecipeNotFound, ModeError):
            logger.debug(
                "No recipe found for instrument %s: with tags: %s and mode: %s",
                instrument,
                tags,
                mode,
            )
            continue
    return {"recipes": recipes}


def is_gpp_id(obs_id: str) -> bool:
    """
    Return ``True`` if the observation ID is a GPP-style ID (starts with 'G-'),
    and not an OCS-style ID (which starts with 'GS-' or 'GN-').

    Parameters
    ----------
    obs_id : str
        The observation ID to check.

    Returns
    -------
    bool
        ``True`` if it is a GPP ID, ``False`` otherwise.
    """
    return obs_id.startswith("G-")


def is_ocs_id(obs_id: str) -> bool:
    """
    Return ``True`` if the observation ID is a OCS-style ID (starts with 'GS- or GN-')
    Parameters
    ----------
    obs_id : str
        The observation ID to check.

    Returns
    -------
    bool
        ``True`` if it is not a GPP ID, ``False`` otherwise.
    """
    return obs_id.startswith(("GS-", "GN-"))
