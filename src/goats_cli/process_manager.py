"""Class to manage processes."""
__all__ = ["ProcessManager"]

import subprocess

from goats_cli.utils import display_message, display_warning


class ProcessManager:
    """Manages named subprocesses to ensure clean startup and strict shutdown sequence.

    Parameters
    ----------
    timeout : `int`
        Timeout in seconds for stopping a process.

    """

    shutdown_order: list[str] = ["background_workers", "django", "redis"]
    """Fixed order in which subprocesses are to be shut down."""

    def __init__(self, timeout: int = 10):
        self.processes: dict[str, subprocess.Popen] = {}
        self.timeout = timeout

    def add_process(self, name: str, process: subprocess.Popen) -> None:
        """Adds a named process to the manager.

        Parameters
        ----------
        name : `str`
            The name of the process.
        process : `subprocess.Popen`
            The process.

        """
        self.processes[name] = process

    def stop_all(self) -> None:
        """Stops all managed processes in a specific order."""
        display_message("Stopping all processes for GOATS, please wait.")
        for name in self.shutdown_order:
            _ = self.stop_process(name)
        display_message("GOATS successfully stopped.")

    def stop_process(self, name: str) -> bool:
        """Stops a named process gracefully with a timeout.

        Parameters
        ----------
        name : `str`
            The name of the process to stop.

        Returns
        -------
        `bool`
            `True` if process was able to be stopped, else `False`.

        """
        process = self.processes.pop(name, None)
        display_message(f"Stopping {name}.")

        if process:
            process.terminate()
            try:
                process.wait(timeout=self.timeout)
            except Exception:
                display_warning(f"Could not stop {name} in time, killing {name}.")
                process.kill()

        else:
            display_warning(f"No process found for {name}, skipping.")
            return False
        return True
