"""
Scheduler registry and decorator for registering Dramatiq actors with APScheduler.

This module provides a `cron` decorator to register Dramatiq actors as scheduled tasks
via APScheduler's `CronTrigger`. Registered jobs are stored in the `SCHEDULED_JOBS` list
for discovery by the task scheduler command.
"""

__all__ = ["SCHEDULED_JOBS", "cron"]

from typing import Any, Callable

from apscheduler.triggers.cron import CronTrigger
from dramatiq.actor import Actor

SCHEDULED_JOBS: list[dict[str, Any]] = []
"""List of all scheduled Dramatiq jobs to be registered with APScheduler."""


def cron(
    *,
    coalesce: bool = True,
    max_instances: int = 1,
    replace_existing: bool = True,
    **cron_kwargs: Any,
) -> Callable[[Actor], Actor]:
    """
    Register a Dramatiq actor as a scheduled job using a ``CronTrigger``.

    This decorator should be used on Dramatiq actors to register them for execution
    via APScheduler at a specified `cron` interval. Jobs are collected into the
    ``SCHEDULED_JOBS`` list for registration by the task scheduler.

    Parameters
    ----------
    coalesce : bool=True
        If ``True``, run only one job if multiple executions are pending.
    max_instances : int=1
        Maximum number of concurrently running job instances. Default is 1.
    replace_existing : bool=True
        If ``True``, replaces any existing job with the same name.
    **cron_kwargs : Any
        Keyword arguments passed to ``CronTrigger``, such as ``minute=0``,
        ``hour='*'``, etc.

    Returns
    -------
    Callable[[Actor], Actor]
        A decorator that wraps and returns the original Dramatiq actor.

    Examples
    --------
    >>> @cron(second="*")
    >>> @dramatiq.actor
    >>> def my_task():
    >>>     print("Runs every second.")
    """

    def decorator(actor: Actor) -> Actor:
        module_path = actor.fn.__module__
        func_name = actor.fn.__name__
        module_func = f"{module_path}:{func_name}"

        SCHEDULED_JOBS.append(
            {
                "name": func_name,
                "job_path": f"{module_path}:{func_name}.send",
                "trigger": CronTrigger(**cron_kwargs),
                "coalesce": coalesce,
                "max_instances": max_instances,
                "replace_existing": replace_existing,
                "module_func": module_func,
            }
        )
        return actor

    return decorator
