from pathlib import Path

import pytest
import typer

from goats_cli import cli
from goats_cli.commands.run import (
    _start_process,
    start_background_workers,
    start_django_server,
    start_redis_server,
    start_task_scheduler,
    sync_goats_files,
)
from goats_cli.config import config
from goats_cli.process import ProcessManager, ProcessName, StartResult


@pytest.fixture()
def mock_process_manager(mocker) -> ProcessManager:
    """Provide a ProcessManager with its stop_all method patched."""
    manager = ProcessManager(timeout=5)
    # We patch stop_all at the class level in run tests; here we just return instance.
    return manager


@pytest.fixture()
def mock_popen(mocker):
    """Provide a mock subprocess.Popen-like object."""
    proc = mocker.MagicMock()
    proc.pid = 1234
    proc.wait.return_value = 0
    proc.poll.return_value = 0
    return proc


@pytest.fixture()
def base_mocks(mocker):
    manager_mock = mocker.MagicMock(spec=ProcessManager)
    mocker.patch("goats_cli.commands.run.ProcessManager", return_value=manager_mock)

    return {
        "manager": manager_mock,
        "get_version": mocker.patch(
            "goats_cli.commands.run.utils.get_version", return_value="25.11.4"
        ),
        "parse_addrport": mocker.patch(
            "goats_cli.commands.run.utils.parse_addrport",
            side_effect=[("localhost", 6379), ("127.0.0.1", 8000)],
        ),
        "check_version": mocker.patch("goats_cli.commands.run.check_version"),
        "validate_project_structure": mocker.patch(
            "goats_cli.commands.run.validate_project_structure",
            return_value=Path("/fake/manage.py"),
        ),
        "sync_files": mocker.patch("goats_cli.commands.run.sync_goats_files"),
        "subprocess_run": mocker.patch("goats_cli.commands.run.subprocess.run"),
        "check_port_not_in_use": mocker.patch(
            "goats_cli.commands.run.utils.check_port_not_in_use"
        ),
        "wait_until": mocker.patch(
            "goats_cli.commands.run.utils.wait_until_responsive"
        ),
        "open_browser": mocker.patch("goats_cli.commands.run.utils.open_browser"),
        "wait": mocker.patch("goats_cli.commands.run.utils.wait"),
        "panel": mocker.patch("goats_cli.commands.run.output.panel"),
        "section": mocker.patch("goats_cli.commands.run.output.section"),
        "success": mocker.patch("goats_cli.commands.run.output.success"),
        "warning": mocker.patch("goats_cli.commands.run.output.warning"),
        "fail": mocker.patch("goats_cli.commands.run.output.fail"),
        "print_exception": mocker.patch(
            "goats_cli.commands.run.output.print_exception"
        ),
        "start_table": mocker.patch(
            "goats_cli.commands.run.output.start_summary_table"
        ),
        "stop_table": mocker.patch("goats_cli.commands.run.output.stop_summary_table"),
        "status_ctx": mocker.patch("goats_cli.commands.run.output.status"),
        "start_redis": mocker.patch("goats_cli.commands.run.start_redis_server"),
        "start_django": mocker.patch("goats_cli.commands.run.start_django_server"),
        "start_workers": mocker.patch(
            "goats_cli.commands.run.start_background_workers"
        ),
        "start_scheduler": mocker.patch("goats_cli.commands.run.start_task_scheduler"),
    }


@pytest.mark.parametrize(
    "raises, expected_started, expected_error",
    [
        (None, True, None),
        (Exception("boom"), False, "boom"),
    ],
)
def test__start_process_behaviour(mocker, raises, expected_started, expected_error):
    """_start_process stores StartResult and registers process or fails with error."""
    mock_manager = mocker.MagicMock(spec=ProcessManager)
    startup: dict[ProcessName, StartResult] = {}
    fake_proc = mocker.MagicMock()

    def starter():
        if raises is None:
            return fake_proc
        raise raises

    if raises is not None:
        mock_fail = mocker.patch("goats_cli.commands.run.output.fail")

        with pytest.raises(Exception):
            _start_process(ProcessName.DJANGO, startup, starter, mock_manager)

        mock_fail.assert_called_once()
        assert startup[ProcessName.DJANGO].started is expected_started
        assert startup[ProcessName.DJANGO].error == expected_error
        mock_manager.add_process.assert_not_called()
    else:
        _start_process(ProcessName.DJANGO, startup, starter, mock_manager)

        assert startup[ProcessName.DJANGO].started is expected_started
        assert startup[ProcessName.DJANGO].error is expected_error
        mock_manager.add_process.assert_called_once_with(ProcessName.DJANGO, fake_proc)


@pytest.mark.parametrize(
    "disable_rdb, expect_extra_args",
    [
        (True, ["--save", "''", "--appendonly", "no"]),
        (False, []),
    ],
)
def test_start_redis_server_builds_correct_command(
    mocker, disable_rdb, expect_extra_args
):
    """start_redis_server constructs the correct redis-server command line."""
    mock_popen = mocker.patch("goats_cli.commands.run.subprocess.Popen")
    mock_match = mocker.MagicMock()
    mock_match.group.return_value = "6379"
    mocker.patch("goats_cli.commands.run.re.match", return_value=mock_match)

    start_redis_server("localhost:6379", disable_rdb=disable_rdb)

    expected_cmd_prefix = ["redis-server", "--port", "6379"]
    expected_cmd = expected_cmd_prefix + expect_extra_args

    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    assert args[0] == expected_cmd
    assert kwargs.get("start_new_session") is True


def test_start_django_server_invokes_popen(mocker):
    """start_django_server runs manage.py runserver with addrport."""
    mock_popen = mocker.patch("goats_cli.commands.run.subprocess.Popen")
    manage_file = Path("/fake/manage.py")

    start_django_server(manage_file, "127.0.0.1:8000")

    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    assert args[0] == [str(manage_file), "runserver", "127.0.0.1:8000"]
    assert kwargs.get("start_new_session") is True


def test_start_background_workers_invokes_popen(mocker):
    """start_background_workers runs rundramatiq with correct args."""
    mock_popen = mocker.patch("goats_cli.commands.run.subprocess.Popen")
    manage_file = Path("/fake/manage.py")

    start_background_workers(manage_file, workers=4)

    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    cmd = args[0]
    assert cmd[0] == str(manage_file)
    assert "rundramatiq" in cmd
    assert "--threads" in cmd and "4" in cmd
    assert "--path" in cmd and str(manage_file.parent) in cmd
    assert "--worker-shutdown-timeout" in cmd
    assert kwargs.get("start_new_session") is True


def test_start_task_scheduler_invokes_popen(mocker):
    """start_task_scheduler runs run_scheduler management command."""
    mock_popen = mocker.patch("goats_cli.commands.run.subprocess.Popen")
    manage_file = Path("/fake/manage.py")

    start_task_scheduler(manage_file)

    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    assert args[0] == [str(manage_file), "run_scheduler"]
    assert kwargs.get("start_new_session") is True


def test_sync_goats_files_normal_mode_uses_normal_excludes(mocker, tmp_path):
    mock_recopy = mocker.patch("goats_cli.commands.run.run_recopy")
    mocker.patch("goats_cli.commands.run.output.section")
    mocker.patch("goats_cli.commands.run.output.status")
    mocker.patch("goats_cli.commands.run.output.success")
    mocker.patch("goats_cli.commands.run.utils.wait")

    sync_goats_files(tmp_path, "25.11.4", full_recopy=False)

    exclude = mock_recopy.call_args.kwargs["exclude"]

    # First entries must match normal mode list
    assert exclude[: len(list(config.recopy_exclude_normal))] == list(
        config.recopy_exclude_normal
    )

    # Never-overwrite must be appended
    for pat in list(config.never_overwrite):
        assert pat in exclude


def test_sync_goats_files_full_mode_uses_full_excludes(mocker, tmp_path):
    mock_recopy = mocker.patch("goats_cli.commands.run.run_recopy")
    mocker.patch("goats_cli.commands.run.output.section")
    mocker.patch("goats_cli.commands.run.output.status")
    mocker.patch("goats_cli.commands.run.output.success")
    mocker.patch("goats_cli.commands.run.utils.wait")

    sync_goats_files(tmp_path, "25.11.4", full_recopy=True)

    exclude = mock_recopy.call_args.kwargs["exclude"]

    # First entries must match full mode list
    assert exclude[: len(list(config.recopy_exclude_full))] == list(
        config.recopy_exclude_full
    )

    # Never-overwrite must be appended
    for pat in list(config.never_overwrite):
        assert pat in exclude


def test_sync_goats_files_failure_raises_exit(mocker, base_mocks, tmp_path):
    """sync_goats_files prints failure and raises typer.Exit on error."""
    mock_recopy = mocker.patch(
        "goats_cli.commands.run.run_recopy",
        side_effect=Exception("copy failed"),
    )
    mock_fail = mocker.patch("goats_cli.commands.run.output.fail")
    mocker.patch("goats_cli.commands.run.output.section")
    mocker.patch("goats_cli.commands.run.output.status")
    mocker.patch("goats_cli.commands.run.utils.wait")

    project_path = tmp_path / "GOATS"
    project_path.mkdir()

    with pytest.raises(typer.Exit) as excinfo:
        sync_goats_files(project_path, "25.11.4")

    assert excinfo.value.exit_code == 1
    mock_recopy.assert_called_once()
    mock_fail.assert_called_once()


@pytest.mark.parametrize("responsive", [True, False])
def test_run_cli_basic_flow(mocker, cli_runner, base_mocks, responsive):
    """run command performs full startup sequence with expected calls."""
    base_mocks["wait_until"].return_value = responsive

    # Break the infinite loop on first iteration.
    mocker.patch("goats_cli.commands.run.time.sleep", side_effect=KeyboardInterrupt)

    result = cli_runner.invoke(
        cli,
        [
            "run",
            "--project-name",
            "GOATS",
            "--directory",
            str(Path("/fake")),
            "--workers",
            "2",
            "--addrport",
            "127.0.0.1:8000",
            "--redis",
            "localhost:6379",
            "--browser",
            "default",
        ],
    )

    # Command should exit cleanly with KeyboardInterrupt handled.
    assert result.exit_code == 0

    # Version / project checks / sync should all be called.
    base_mocks["check_version"].assert_called_once()
    base_mocks["validate_project_structure"].assert_called_once()
    base_mocks["sync_files"].assert_called_once()

    # Redis version check.
    base_mocks["subprocess_run"].assert_called_once()

    # Ports checked twice (Redis + Django).
    assert base_mocks["check_port_not_in_use"].call_count == 2

    # All four start_* helpers called.
    base_mocks["start_redis"].assert_called_once()
    base_mocks["start_django"].assert_called_once()
    base_mocks["start_workers"].assert_called_once()
    base_mocks["start_scheduler"].assert_called_once()

    # Browser only opens if server is responsive.
    if responsive:
        base_mocks["open_browser"].assert_called_once()
    else:
        base_mocks["open_browser"].assert_not_called()

    # Startup/shutdown summaries printed.
    base_mocks["start_table"].assert_called_once()
    base_mocks["stop_table"].assert_called_once()
    base_mocks["success"].assert_any_call("GOATS has shut down. Goodbye!")


def test_run_cli_redis_missing(mocker, cli_runner, base_mocks):
    """run exits with non-zero status if redis-server is not installed."""
    base_mocks["subprocess_run"].side_effect = FileNotFoundError()

    result = cli_runner.invoke(cli, ["run"])

    # Typer Exit(1) from Redis check.
    assert result.exit_code == 1
    base_mocks["fail"].assert_any_call("Redis is not installed on this system.")


def test_run_cli_copier_failure(mocker, cli_runner, base_mocks):
    """run exits with non-zero status if sync_goats_files raises Exit."""
    base_mocks["sync_files"].side_effect = typer.Exit(1)

    result = cli_runner.invoke(cli, ["run"])

    assert result.exit_code == 1
    # No processes should be started.
    base_mocks["start_redis"].assert_not_called()
    base_mocks["start_django"].assert_not_called()


def test_run_cli_startup_failure(mocker, cli_runner, base_mocks):
    """run logs failure and prints exception if a subprocess fails to start."""
    base_mocks["start_redis"].side_effect = Exception("redis boom")
    # Avoid infinite loop even if it somehow reaches there.

    result = cli_runner.invoke(cli, ["run"])

    # Exit code should be non-zero (Typer returns 0 if no explicit Exit).
    # Here we only assert it is not a crash during collection.
    assert result.exit_code != 0
    base_mocks["fail"].assert_any_call("GOATS failed to start properly.")
    base_mocks["print_exception"].assert_called_once()
