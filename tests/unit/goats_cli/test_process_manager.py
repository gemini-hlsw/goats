"""Tests the `ProcessManager` class."""
import subprocess
from unittest.mock import Mock, call, patch
import signal
import pytest
from goats_cli.process_manager import ProcessManager


@pytest.fixture()
def manager():
    """Fixture to provide a fresh ProcessManager for each test."""
    return ProcessManager(timeout=2)


@pytest.fixture()
def mock_process():
    """Fixture to create a mock subprocess.Popen object."""
    process = Mock(spec=subprocess.Popen)
    process.terminate = Mock()
    process.wait = Mock()
    process.kill = Mock()
    process.pid = 1234
    return process


def test_add_process(manager, mock_process):
    """Test adding a process."""
    manager.add_process("test", mock_process)
    assert "test" in manager.processes
    assert manager.processes["test"] == mock_process


def test_stop_process_existing(manager, mock_process):
    """Test stopping an existing process."""
    manager.add_process("test", mock_process)
    mock_process.wait.return_value = None
    assert manager.stop_process("test") is True
    mock_process.terminate.assert_called_once()
    mock_process.wait.assert_called_once_with(timeout=2)


@patch("os.killpg")
@patch("os.getpgid", return_value=9999)
def test_stop_process_timeout(
    mock_getpgid,
    mock_killpg,
    manager,
    mock_process,
):
    """
    Test stopping a process that times out, ensuring we call
    killpg() to terminate all child processes.
    """
    manager.add_process("test", mock_process)

    # First .wait() call raises TimeoutExpired (triggering killpg),
    # second call returns None (normal exit).
    mock_process.wait.side_effect = [
        subprocess.TimeoutExpired(cmd="test", timeout=2),
        None
    ]

    result = manager.stop_process("test")
    assert result is True

    mock_process.terminate.assert_called_once()

    # Confirm killpg was called with the fake PGID (9999) and the SIGKILL signal.
    mock_killpg.assert_called_once_with(9999, signal.SIGKILL)

def test_stop_process_non_existent(manager):
    """Test trying to stop a process that does not exist."""
    assert manager.stop_process("nonexistent") is False


def test_stop_all_processes_in_correct_order(manager, mock_process):
    """Test that all processes are stopped in the correct order."""
    # Setup processes in the manager.
    processes = {"background_workers": mock_process, "django": mock_process, "redis": mock_process}
    for name, process in processes.items():
        manager.add_process(name, process)

    # Patch the stop_process method to check call order.
    with patch.object(manager, "stop_process", wraps=manager.stop_process) as mocked_stop_process:
        manager.stop_all()

        # Expected order is from the class attribute `shutdown_order`.
        expected_call_order = [call(name) for name in ProcessManager.shutdown_order]
        mocked_stop_process.assert_has_calls(expected_call_order, any_order=False)

        # Check that each process was stopped correctly.
        assert mocked_stop_process.call_count == len(ProcessManager.shutdown_order), "All processes should be stopped."
