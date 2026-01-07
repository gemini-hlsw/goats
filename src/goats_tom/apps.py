"""
Django app configuration for the GOATS-TOM application.
"""

__all__ = ["GOATSTomConfig"]

import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class GOATSTomConfig(AppConfig):
    name = "goats_tom"

    _has_run = False

    def ready(self) -> None:
        """
        Apply necessary patches and middleware when the app is ready.
        """
        # Ensure patches and middleware are only applied once.
        if GOATSTomConfig._has_run:
            logger.warning("GOATS ready() called multiple times; skipping")
            return
        GOATSTomConfig._has_run = True

        from goats_tom.bootstrap import setup_dramatiq_abort  # noqa: PLC0415
        from goats_tom.patches import apply_all_patches  # noqa: PLC0415

        setup_dramatiq_abort()
        apply_all_patches()
