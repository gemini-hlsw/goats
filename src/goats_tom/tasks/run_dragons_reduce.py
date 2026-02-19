"""
Run DRAGONS reduction in background.
"""

__all__ = ["run_dragons_reduce"]

import ast
import logging
import os
import sys
import time
import types
import uuid
from typing import Any

import dramatiq
import matplotlib
from django.conf import settings
from dramatiq.middleware import TimeLimitExceeded
from gempy.utils import logutils
from recipe_system.reduction.coreReduce import Reduce

from goats_tom.context.user_context import get_current_user_id
from goats_tom.logging_extensions.handlers import DRAGONSHandler
from goats_tom.models import DRAGONSFile, DRAGONSReduce
from goats_tom.realtime import DRAGONSProgress, NotificationInstance

matplotlib.use("Agg", force=True)


def _safe_literal(value: str, label: str, expected_type: type | None = None) -> Any:
    """
    Safely parse a string literal to a specified type.

    Parameters
    ----------
    value : str
        The string representation of the value to parse.
    label : str
        A label for the value, used in error messages.
    expected_type : type, optional
        The expected type of the parsed value. If provided, the function
        will check that the parsed value matches this type.

    Returns
    -------
    Any
        The parsed value of the expected type."""
    try:
        parsed = ast.literal_eval(value)
    except Exception:
        raise Exception(f"Failed to parse {label}.")
    if expected_type is not None and not isinstance(parsed, expected_type):
        raise Exception(f"{label} must be {expected_type.__name__}.")
    return parsed


@dramatiq.actor(
    max_retries=0, time_limit=getattr(settings, "DRAMATIQ_ACTOR_TIME_LIMIT", 86400000)
)
def run_dragons_reduce(reduce_id: int, file_ids: list[int]) -> None:
    """
    Executes a reduction process in the background.

    This function handles the entire process of setting up and executing a reduction,
    including notification handling, file management, and executing the reduction logic.

    Parameters
    ----------
    reduce_id : int
        The ID of the DRAGONSReduce instance to be processed.
    file_ids : list[int]
        A list of file IDs to limit to. If empty, use all files.

    Raises
    ------
    DoesNotExist
        Raised if the DRAGONSReduce instance does not exist.
    """
    try:
        logger = logging.getLogger(__name__)
        user_id = get_current_user_id()
        logger.debug(
            "Starting DRAGONS reduction with DRAGONSReduce id=%s and uid=%s",
            reduce_id,
            user_id,
        )

        reduce: DRAGONSReduce | None = None
        module_name: str | None = None
        # Get the reduction to run in the background.
        # Generate a unique module name to avoid conflicts in sys.modules.
        unique_id = uuid.uuid4()
        module_name = f"dynamic_recipes_{unique_id}"

        # Get the recipe instance.
        reduce = DRAGONSReduce.objects.get(id=reduce_id)
        logger.debug("Loaded DRAGONSReduce id=%s status=%s", reduce.id, reduce.status)

        run = reduce.recipe.dragons_run
        recipe = reduce.recipe
        # Send start notification.
        NotificationInstance.create_and_send(
            message="Reduction started.",
            label=reduce.get_label(),
        )
        reduce.mark_initializing()
        DRAGONSProgress.create_and_send(reduce)

        time.sleep(2)

        # Create an instance of the custom handler.
        dragons_handler = DRAGONSHandler(
            recipe_id=recipe.id,
            reduce_id=reduce.id,
            run_id=run.id,
        )
        dragons_handler.setLevel(21)

        # Change the working directory to save outputs.
        os.chdir(run.get_output_dir())

        # Filter the files based on the associated DRAGONS run and file ids.
        files = DRAGONSFile.objects.filter(dragons_run=run, id__in=file_ids)
        # Sort files to ensure the first file matches the recipe's observation type.
        # DRAGONS is highly dependent on the order of input files, especially the first
        # file, when performing operations like creating a BPM (Bad Pixel Mask) with
        # `makeLampFlat` in the F2 instrument. If the first file does not match the
        # required observation type, the recipe may attempt to access tags and
        # primitives not relevant to that file type, leading to crashes.
        files = sorted(
            files, key=lambda file: file.observation_type != recipe.observation_type
        )
        file_paths = [file.file_path for file in files]

        # Setup the logger.
        logutils.config(
            mode="standard",
            file_name=run.log_filename,
            additional_handlers=dragons_handler,
        )

        r = Reduce()

        # Get error if passing in Path.
        r.config_file = str(run.get_config_file())

        # Set the recipe parameters if provided.
        if recipe.uparms is not None:
            parsed_uparms = _safe_literal(recipe.uparms, "uparms")
            r.uparms = parsed_uparms

        if recipe.reduction_mode is not None:
            r.mode = recipe.reduction_mode

        if recipe.drpkg is not None:
            r.drpkg = recipe.drpkg

        if recipe.suffix is not None:
            r.suffix = recipe.suffix

        if recipe.ucals is not None:
            parsed_ucals = _safe_literal(recipe.ucals, "ucals", dict)
            # Update paths to be absolute.
            for cal_type, path in parsed_ucals.items():
                full_path = str(settings.MEDIA_ROOT / path)
                parsed_ucals[cal_type] = full_path
            r.ucals = parsed_ucals

        if recipe.additional_files is not None:
            parsed_files = _safe_literal(
                recipe.additional_files, "additional_files", list
            )
            # Convert each to an absolute path.
            additional_file_paths = [
                str(settings.MEDIA_ROOT / path) for path in parsed_files
            ]
            file_paths.extend(additional_file_paths)

        r.files.extend(file_paths)

        # Prepare a namespace to execute the user-provided function definition safely.
        function_definition_namespace = {}

        # Execute the function definition provided by the user.
        exec(recipe.active_function_definition, {}, function_definition_namespace)

        # Search through the namespace to find any callable defined therein.
        function_definition = None
        for _, obj in function_definition_namespace.items():
            if callable(obj):
                function_definition = obj
                break

        # Ensure a function was successfully defined and retrieved.
        if function_definition is None:
            raise ValueError("No recipe was defined in the provided recipe.")

        # Create a new module and add it to `sys.modules`.
        recipe_module = types.ModuleType(module_name)
        sys.modules[module_name] = recipe_module

        # Add the user-defined function to the newly created module.
        setattr(recipe_module, function_definition.__name__, function_definition)

        # Format the recipename to be recognized by DRAGONS which expects
        # "<module_name>.<function_name>".
        r.recipename = f"{module_name}.{function_definition.__name__}"

        reduce.mark_running()
        DRAGONSProgress.create_and_send(reduce)

        r.runr()

        # Send finished notification.
        NotificationInstance.create_and_send(
            message="Reduction finished.",
            label=reduce.get_label(),
            color="success",
        )
        reduce.mark_done()
        DRAGONSProgress.create_and_send(reduce)
    except TimeLimitExceeded:
        reduce.mark_error()
        DRAGONSProgress.create_and_send(reduce)
        NotificationInstance.create_and_send(
            label=reduce.get_label(),
            message="Background task time limit hit. Consider increasing timeout.",
            color="danger",
        )
        raise
    except DRAGONSReduce.DoesNotExist:
        # Send error to frontend.
        NotificationInstance.create_and_send(
            message="Reduction not found.",
            color="danger",
        )
        raise
    except Exception as e:
        # Catch all other exceptions.
        reduce.mark_error()
        DRAGONSProgress.create_and_send(reduce)
        NotificationInstance.create_and_send(
            label=reduce.get_label(),
            message=f"Error during reduction: {e!s}",
            color="danger",
        )
        raise
    finally:
        # Remove handler so it can’t emit more log records.
        # This would cause coroutines to be unawaited.
        logger = logging.getLogger()
        for h in logger.handlers[:]:
            if isinstance(h, DRAGONSHandler):
                logger.removeHandler(h)
        # Cleanup dynamically created module.
        if module_name in sys.modules:
            del sys.modules[module_name]
