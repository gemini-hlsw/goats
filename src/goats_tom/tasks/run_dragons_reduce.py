"""Run DRAGONS reduction in background."""

__all__ = ["run_dragons_reduce"]

import ast
import logging
import os
import sys
import time
import types
import uuid

import dramatiq
import matplotlib
from django.conf import settings
from dramatiq.middleware import TimeLimitExceeded
from gempy.utils import logutils
from recipe_system.reduction.coreReduce import Reduce

from goats_tom.logging_extensions.handlers import DRAGONSHandler
from goats_tom.models import DRAGONSFile, DRAGONSReduce
from goats_tom.realtime import DRAGONSProgress, NotificationInstance

matplotlib.use("Agg", force=True)

logger = logging.getLogger(__name__)


@dramatiq.actor(
    max_retries=0, time_limit=getattr(settings, "DRAMATIQ_ACTOR_TIME_LIMIT", 86400000)
)
def run_dragons_reduce(reduce_id: int, file_ids: list[int]) -> None:
    """Executes a reduction process in the background.

    This function handles the entire process of setting up and executing a reduction,
    including notification handling, file management, and executing the reduction logic.

    Parameters
    ----------
    reduce_id : `int`
        The ID of the DRAGONSReduce instance to be processed.
    file_ids : `list[int]`
        A list of file IDs to limit to. If empty, use all files.

    Raises
    ------
    `DoesNotExist`
        Raised if the DRAGONSReduce instance does not exist.

    """
    try:
        # Get the reduction to run in the background.
        print("Running background reduce task.")
        # Generate a unique module name to avoid conflicts in sys.modules.
        unique_id = uuid.uuid4()
        module_name = f"dynamic_recipes_{unique_id}"

        # Get the recipe instance.
        reduce = DRAGONSReduce.objects.get(id=reduce_id)

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

        # Set the recipe uparms.
        if recipe.uparms is not None:
            try:
                r.uparms = ast.literal_eval(recipe.uparms)
            except Exception:
                raise Exception("Failed to parse provided uparms.")

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
            print(f"Module {module_name} removed from sys.modules.")
