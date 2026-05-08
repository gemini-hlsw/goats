"""
Manages subprocesses for GOATS CLI with clean startup and shutdown sequences.
"""

__all__ = ["ProcessManager", "ProcessName", "ProcessResult", "StartResult"]

import os
import signal
import subprocess
from dataclasses import dataclass
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

    @classmethod
    def startup_order(cls) -> list["ProcessName"]:
        """Defines startup order."""
        return list(reversed(cls.shutdown_order()))


@dataclass(frozen=True)
class StartResult:
    """Result of attempting to start a GOATS subprocess."""

    existed: bool
    started: bool
    error: str | None = None

    def ok(self) -> bool:
        """
        Checks if the process started successfully.

        Returns
        -------
        bool
            ``True`` if the process started successfully, ``False`` otherwise.
        """
        return self.started and self.error is None


@dataclass(frozen=True)
class ProcessResult:
    """
    Result of stopping a process.

    Attributes
    ----------
    existed : bool
        Whether the process existed in the manager.
    terminated : bool
        Whether the process was terminated gracefully.
    killed : bool
        Whether the process was killed forcefully.
    return_code : int | None
        The return code of the process, if it existed.
    """

    existed: bool
    terminated: bool
    killed: bool
    return_code: int | None = None

    def ok(self) -> bool:
        """
        Checks if the process exited cleanly (no kill, return code 0).

        A process is considered to have stopped cleanly if:
        - it existed,
        - it was not SIGKILLed,
        - and its return code is 0 or -SIGTERM.

        Returns
        -------
        bool
            ``True`` if the process exited cleanly, ``False`` otherwise.
        """
        if not self.existed or self.killed:
            return False

        if self.return_code in (0, -signal.SIGTERM):
            return True

        return False


class ProcessManager:
    """Manages named subprocesses to ensure clean startup and strict shutdown sequence.

    Parameters
    ----------
    timeout : int, default=15
        Timeout in seconds for stopping a process.

    """

    def __init__(self, timeout: int = 15):
        self.processes: dict[ProcessName, subprocess.Popen] = {}
        self.timeout = timeout

    def add_process(self, name: ProcessName, process: subprocess.Popen) -> None:
        """Adds a named process to the manager.

        Parameters
        ----------
        name : ProcessName
            The name of the process.
        process : subprocess.Popen
            The process.
        """
        self.processes[name] = process

    def stop_all(self) -> dict[ProcessName, ProcessResult]:
        """
        Stops all managed processes in a specific order.

        Returns
        -------
        dict[ProcessName, ProcessResult]
            A dictionary mapping process names to their stop results.
        """
        results: dict[ProcessName, ProcessResult] = {}

        for name in ProcessName.shutdown_order():
            results[name] = self.stop_process(name)

        return results

    def stop_process(self, name: ProcessName) -> ProcessResult:
        """Stops a named process gracefully with a timeout.

        Parameters
        ----------
        name : ProcessName
            The name of the process to stop.

        Returns
        -------
        ProcessResult
            Result of the stop operation.

        """
        process = self.processes.pop(name, None)

        if process is None:
            return ProcessResult(
                existed=False,
                terminated=False,
                killed=False,
                return_code=None,
            )

        # Attempt graceful termination.
        terminated = True
        killed = False

        process.terminate()

        try:
            process.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            # Escalate to SIGKILL.
            killed = True
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal.SIGKILL)
            process.wait()

        return ProcessResult(
            existed=True,
            terminated=terminated,
            killed=killed,
            return_code=process.poll(),
        )
