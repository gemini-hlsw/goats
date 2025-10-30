"""Class to manage processes."""

__all__ = ["ProcessManager"]

import os
import signal
import subprocess

import goats_cli.utils as utils

from .processes import ProcessName


class ProcessManager:
    """Manages named subprocesses to ensure clean startup and strict shutdown sequence.

    Parameters
    ----------
    timeout : `int`
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

    def stop_all(self) -> None:
        """Stops all managed processes in a specific order."""
        utils.display_message("Stopping all processes for GOATS, please wait.")
        for name in ProcessName.shutdown_order():
            self.stop_process(name)
        utils.display_message("GOATS successfully stopped.")

    def stop_process(self, name: ProcessName) -> bool:
        """Stops a named process gracefully with a timeout.

        Parameters
        ----------
        name : ProcessName
            The name of the process to stop.

        Returns
        -------
        `bool`
            `True` if process was able to be stopped, else `False`.

        """
        process = self.processes.pop(name, None)

        if process is None:
            utils.display_warning(f"No process found for {name.value}, skipping.")
            return False

        utils.display_message(f"Stopping {name.value}.")
        process.terminate()

        try:
            process.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            utils.display_warning(
                f"Could not stop {name.value} in time, killing {name.value}."
            )
            # Kill the entire group.
            # Handles the children.
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal.SIGKILL)
            process.wait()

        return_code = process.poll()
        if return_code is not None:
            utils.display_message(f"{name.value} exited with code {return_code}.")
        else:
            utils.display_warning(f"{name.value} may still be running...")

        return True
