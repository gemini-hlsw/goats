import signal
import subprocess
from unittest.mock import Mock, call, patch

import pytest

from goats_cli.process_manager import ProcessManager
from goats_cli.processes import ProcessName


@pytest.fixture()
def manager():
    """Fixture to provide a fresh ProcessManager for each test."""
    return ProcessManager(timeout=2)


@pytest.fixture()
def mock_process():
    """Fixture to create a mock subprocess.Popen object."""
    process = Mock(spec=subprocess.Popen)
    process.terminate.return_value = None
    process.wait.return_value = None
    process.kill.return_value = None
    process.pid = 1234
    return process


def test_add_process(manager, mock_process):
    """Test adding a process (keys are ProcessName, not str)."""
    manager.add_process(ProcessName.DJANGO, mock_process)
    assert ProcessName.DJANGO in manager.processes
    assert manager.processes[ProcessName.DJANGO] is mock_process


def test_stop_process_existing(manager, mock_process):
    """Test stopping an existing process."""
    manager.add_process(ProcessName.DJANGO, mock_process)
    mock_process.wait.return_value = None

    assert manager.stop_process(ProcessName.DJANGO) is True
    mock_process.terminate.assert_called_once()
    mock_process.wait.assert_called_once_with(timeout=2)


@patch("goats_cli.process_manager.os.killpg")
@patch("goats_cli.process_manager.os.getpgid", return_value=9999)
def test_stop_process_timeout(
    mock_getpgid,
    mock_killpg,
    manager,
    mock_process,
):
    """
    If wait() times out, we should kill the process group.
    """
    manager.add_process(ProcessName.DJANGO, mock_process)
    mock_process.wait.side_effect =[subprocess.TimeoutExpired(cmd="django", timeout=2),None]

    result = manager.stop_process(ProcessName.DJANGO)
    assert result is True

    mock_process.terminate.assert_called_once()
    mock_killpg.assert_called_once_with(9999, signal.SIGKILL)


def test_stop_process_non_existent(manager):
    """Trying to stop a non-existent process returns False."""
    assert manager.stop_process(ProcessName.REDIS) is False


def test_stop_all_processes_in_correct_order(manager, mock_process):
    """stop_all() should follow ProcessName.shutdown_order()."""
    for member in ProcessName.shutdown_order():
        manager.add_process(member, mock_process)

    with patch.object(manager, "stop_process", wraps=manager.stop_process) as sp:
        manager.stop_all()

        expected_call_order = [call(member) for member in ProcessName.shutdown_order()]
        sp.assert_has_calls(expected_call_order, any_order=False)
        assert sp.call_count == len(expected_call_order)
