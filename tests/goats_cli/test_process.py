import signal
import subprocess

import pytest

from goats_cli.process import (
    ProcessManager,
    ProcessName,
    ProcessResult,
    StartResult,
)


def test_processname_startup_and_shutdown_order():
    """Validate startup/shutdown orders."""
    shutdown = ProcessName.shutdown_order()
    startup = ProcessName.startup_order()
    assert startup == list(reversed(shutdown))
    assert len(startup) == len(shutdown) == 4


@pytest.mark.parametrize(
    "existed, started, error, expected",
    [
        (True, True, None, True),
        (True, False, None, False),
        (True, True, "boom", False),
        (False, False, None, False),
    ],
)
def test_startresult_ok(existed, started, error, expected):
    """Check StartResult.ok correctness."""
    r = StartResult(existed=existed, started=started, error=error)
    assert r.ok() is expected


@pytest.mark.parametrize(
    "existed, killed, return_code, expected",
    [
        (False, False, None, False),
        (True, True, 0, False),
        (True, False, 0, True),
        (True, False, -signal.SIGTERM, True),
        (True, False, 1, False),
    ],
)
def test_processresult_ok(existed, killed, return_code, expected):
    """Check ProcessResult.ok correctness."""
    r = ProcessResult(
        existed=existed,
        terminated=True,
        killed=killed,
        return_code=return_code,
    )
    assert r.ok() is expected


@pytest.fixture
def manager():
    """Provide a fresh ProcessManager instance."""
    return ProcessManager(timeout=5)


@pytest.fixture
def mock_popen(mocker):
    """Provide a mock subprocess.Popen with reasonable defaults."""
    proc = mocker.MagicMock()
    proc.pid = 1234
    proc.wait.return_value = 0
    proc.poll.return_value = 0
    return proc


def test_add_process(manager, mock_popen):
    """Ensure add_process stores subprocesses by name."""
    manager.add_process(ProcessName.DJANGO, mock_popen)
    assert manager.processes[ProcessName.DJANGO] is mock_popen


def test_stop_process_not_exists(manager):
    """stop_process returns expected non-existent ProcessResult."""
    result = manager.stop_process(ProcessName.REDIS)
    assert result.existed is False
    assert result.killed is False
    assert result.terminated is False
    assert result.return_code is None


def test_stop_process_clean_exit(manager, mock_popen):
    """stop_process handles a graceful termination."""
    manager.add_process(ProcessName.DJANGO, mock_popen)

    mock_popen.wait.return_value = 0
    mock_popen.poll.return_value = 0

    result = manager.stop_process(ProcessName.DJANGO)

    mock_popen.terminate.assert_called_once()
    mock_popen.wait.assert_called_once()
    assert result.existed is True
    assert result.killed is False
    assert result.return_code == 0


def test_stop_process_timeout_and_kill(manager, mocker, mock_popen):
    """stop_process escalates to SIGKILL on timeout."""
    manager.add_process(ProcessName.DJANGO, mock_popen)

    # First wait() then timeout, second wait() then return normally.
    mock_popen.wait.side_effect = [
        subprocess.TimeoutExpired(cmd="X", timeout=5),
        0,
    ]

    mock_popen.poll.return_value = 1

    mocker.patch("os.getpgid", return_value=777)
    mock_killpg = mocker.patch("os.killpg")

    result = manager.stop_process(ProcessName.DJANGO)

    mock_popen.terminate.assert_called_once()
    mock_killpg.assert_called_once_with(777, signal.SIGKILL)
    assert result.existed is True
    assert result.killed is True
    assert result.return_code == 1


def test_stop_all_calls_each_in_order(manager, mocker):
    """stop_all stops processes in shutdown order."""
    shutdown_order = ProcessName.shutdown_order()

    # Setup mocks in shutdown order.
    mock_procs = {}
    for name in shutdown_order:
        proc = mocker.MagicMock()
        proc.wait.return_value = 0
        proc.poll.return_value = 0
        mock_procs[name] = proc
        manager.add_process(name, proc)

    results = manager.stop_all()

    # Ensure terminate called once for each process.
    for name in shutdown_order:
        mock_procs[name].terminate.assert_called_once()

    assert set(results.keys()) == set(shutdown_order)
    assert all(isinstance(r, ProcessResult) for r in results.values())


@pytest.mark.parametrize(
    "present",
    [
        [],
        [ProcessName.REDIS],
        [ProcessName.DJANGO, ProcessName.REDIS],
    ],
)
def test_stop_all_missing_processes(manager, mocker, present):
    """stop_all returns existed=False for missing processes."""
    for name in present:
        proc = mocker.MagicMock()
        proc.wait.return_value = 0
        proc.poll.return_value = 0
        manager.add_process(name, proc)

    results = manager.stop_all()

    expected_names = set(ProcessName.shutdown_order())
    assert set(results.keys()) == expected_names

    for name, res in results.items():
        if name not in present:
            assert res.existed is False
