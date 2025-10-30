"""
Enums for known subprocesses managed by GOATS CLI.
"""

__all__ = ["ProcessName"]

from enum import Enum


class ProcessName(str, Enum):
    """Known subprocesses managed by GOATS CLI."""

    TASK_SCHEDULER = "Task Scheduler"
    BACKGROUND_WORKERS = "Dramatiq Workers"
    DJANGO = "Django"
    REDIS = "Redis"

    @classmethod
    def shutdown_order(cls) -> list["ProcessName"]:
        """Defines shutdown order."""
        return [
            cls.TASK_SCHEDULER,
            cls.BACKGROUND_WORKERS,
            cls.DJANGO,
            cls.REDIS,
        ]
