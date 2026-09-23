"""Class that sends DRAGONS recipe progress."""

__all__ = ["DRAGONSProgress"]

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from goats_tom.context.user_context import get_current_user_id
from goats_tom.models import DRAGONSReduce

from .groups import DRAGONS_PREFIX, user_group

logger = logging.getLogger(__name__)


class DRAGONSProgress:
    """Class responsible for updating DRAGONS recipe progress.

    Progress reaches only the user who started the reduction, resolved from the
    request or task context.
    """

    func_type = "recipe.progress.message"

    @classmethod
    def create_and_send(cls, reduce: DRAGONSReduce) -> None:
        """Creates and sends the progress status of a DRAGONS recipe.

        Parameters
        ----------
        reduce : `DRAGONSReduce`
            The model instance for recipe reduce.

        """
        cls._send(
            reduce.status,
            reduce.recipe.dragons_run.id,
            reduce.recipe.id,
            reduce.id,
        )

    @classmethod
    def _send(cls, status: str, run_id: int, recipe_id: int, reduce_id: int) -> None:
        """Sends a progress update to the specified group channel.

        Parameters
        ----------
        status : `str`
            The current status of the recipe run.
        run_id : `int`
            The identifier for the run instance.
        recipe_id : `int`
            The identifier for the recipe being executed.
        reduce_id : `int`
            The identifier for the reduction process within the recipe.

        """
        group = user_group(DRAGONS_PREFIX, get_current_user_id())
        if group is None:
            # Dropped rather than broadcast: better lost than shown to all.
            logger.warning(
                "Dropping progress for reduce %s: no user to address it to.", reduce_id
            )
            return

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            group,
            {
                "type": cls.func_type,
                "status": status,
                "run_id": run_id,
                "recipe_id": recipe_id,
                "reduce_id": reduce_id,
            },
        )
