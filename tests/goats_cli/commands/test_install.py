import subprocess
from pathlib import Path
from typing import Any, Dict

import pytest
import typer

from goats_cli import cli
from goats_cli.commands.install import copy_goats_files
from goats_cli.process import ProcessManager


@pytest.fixture()
def mock_process_manager(mocker) -> ProcessManager:
    """Provide a ProcessManager (kept for symmetry with run tests)."""
    manager = ProcessManager(timeout=5)
    return manager


@pytest.fixture()
def base_mocks(mocker) -> Dict[str, Any]:
    return {
        "get_version": mocker.patch(
            "goats_cli.commands.install.utils.get_version",
            return_value="25.11.4",
        ),
        "parse_addrport": mocker.patch(
            "goats_cli.commands.install.utils.parse_addrport",
            return_value=("localhost", 6379),
        ),
        "check_version": mocker.patch("goats_cli.commands.install.check_version"),
        "validate_project_structure": mocker.patch(
            "goats_cli.commands.install.validate_project_structure",
            return_value=Path("/fake/manage.py"),
        ),
        "run_migrations": mocker.patch("goats_cli.commands.install.run_migrations"),
        "copy_goats_files": mocker.patch("goats_cli.commands.install.copy_goats_files"),
        "subprocess_run": mocker.patch("goats_cli.commands.install.subprocess.run"),
        "panel": mocker.patch("goats_cli.commands.install.output.panel"),
        "section": mocker.patch("goats_cli.commands.install.output.section"),
        "success": mocker.patch("goats_cli.commands.install.output.success"),
        "warning": mocker.patch("goats_cli.commands.install.output.warning"),
        "fail": mocker.patch("goats_cli.commands.install.output.fail"),
        "info": mocker.patch("goats_cli.commands.install.output.info"),
        "info_table": mocker.patch("goats_cli.commands.install.output.info_table"),
        "procedure": mocker.patch("goats_cli.commands.install.output.procedure"),
        "procedure_steps": mocker.patch(
            "goats_cli.commands.install.output.procedure_steps",
        ),
        "space": mocker.patch("goats_cli.commands.install.output.space"),
        "status_ctx": mocker.patch("goats_cli.commands.install.output.status"),
        "wait": mocker.patch("goats_cli.commands.install.utils.wait"),
        "rmtree": mocker.patch("goats_cli.commands.install.shutil.rmtree"),
        "get_random_secret_key": mocker.patch(
            "goats_cli.commands.install.get_random_secret_key",
            return_value="TEST_SECRET_KEY",
        ),
    }


def test_copy_goats_files_success(mocker, tmp_path):
    """copy_goats_files runs copier, waits and prints success on success."""
    mock_run_copy = mocker.patch("goats_cli.commands.install.run_copy")
    mock_status = mocker.patch("goats_cli.commands.install.output.status")
    mock_success = mocker.patch("goats_cli.commands.install.output.success")
    mock_wait = mocker.patch("goats_cli.commands.install.utils.wait")

    project_path = tmp_path / "GOATS"
    data = {"project_name": "GOATS"}

    copy_goats_files(project_path, data)

    mock_status.assert_called_once()
    mock_run_copy.assert_called_once()
    mock_wait.assert_called_once()
    mock_success.assert_called_once_with("GOATS template copied.")


def test_copy_goats_files_failure_raises_exit(mocker, tmp_path):
    """copy_goats_files logs error, prints exception, and raises typer.Exit."""
    mock_run_copy = mocker.patch(
        "goats_cli.commands.install.run_copy",
        side_effect=Exception("copy failed"),
    )
    mock_fail = mocker.patch("goats_cli.commands.install.output.fail")
    mock_print_exc = mocker.patch(
        "goats_cli.commands.install.output.print_exception",
    )
    mocker.patch("goats_cli.commands.install.output.status")
    mocker.patch("goats_cli.commands.install.utils.wait")

    project_path = tmp_path / "GOATS"
    data = {"project_name": "GOATS"}

    with pytest.raises(typer.Exit) as excinfo:
        copy_goats_files(project_path, data)

    assert excinfo.value.exit_code == 1
    mock_run_copy.assert_called_once()
    mock_fail.assert_called_once()
    mock_print_exc.assert_called_once()


def _find_fail_call_contains(mock_fail, text: str) -> bool:
    """Helper to check if fail() was called with a message containing text."""
    for call in mock_fail.call_args_list:
        args, _ = call
        if args and text in str(args[0]):
            return True
    return False


def test_install_cli_basic_flow(cli_runner, tmp_path, base_mocks):
    """install performs full flow with default options and succeeds."""
    result = cli_runner.invoke(
        cli,
        [
            "install",
            "--project-name",
            "GOATS",
            "--directory",
            str(tmp_path),
            "--redis",
            "localhost:6379",
        ],
    )

    assert result.exit_code == 0

    # Version and validation checks.
    base_mocks["check_version"].assert_called_once()
    base_mocks["validate_project_structure"].assert_called_once()
    base_mocks["run_migrations"].assert_called_once()

    # Copier wrapper called once with project_path and data.
    base_mocks["copy_goats_files"].assert_called_once()
    (project_path_arg, data_arg), _ = base_mocks["copy_goats_files"].call_args
    assert isinstance(project_path_arg, Path)
    assert data_arg["project_name"] == "GOATS"
    assert data_arg["redis_host"] == "localhost"
    assert data_arg["redis_port"] == 6379
    assert "media_root" not in data_arg

    # Superuser creation called once.
    base_mocks["subprocess_run"].assert_called_once()
    args, kwargs = base_mocks["subprocess_run"].call_args
    assert "createsuperuser" in args[0]
    env = kwargs.get("env", {})
    assert env.get("GOATS_ENV") == "cli"

    # Final info table and next steps printed.
    base_mocks["info_table"].assert_called_once()
    base_mocks["procedure_steps"].assert_called_once()
    base_mocks["success"].assert_any_call("GOATS installed successfully!")


def test_install_cli_project_exists_no_overwrite(cli_runner, tmp_path, base_mocks):
    """install aborts with Exit(1) if project exists and --overwrite not given."""
    project_path = tmp_path / "GOATS"
    project_path.mkdir()

    result = cli_runner.invoke(
        cli,
        [
            "install",
            "--project-name",
            "GOATS",
            "--directory",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert _find_fail_call_contains(
        base_mocks["fail"],
        "A GOATS project already exists",
    )
    # Template copy and migrations should not run.
    base_mocks["copy_goats_files"].assert_not_called()
    base_mocks["run_migrations"].assert_not_called()


def test_install_cli_project_exists_with_overwrite(cli_runner, tmp_path, base_mocks):
    """install removes existing project when --overwrite is used and succeeds."""
    project_path = tmp_path / "GOATS"
    project_path.mkdir()

    result = cli_runner.invoke(
        cli,
        [
            "install",
            "--project-name",
            "GOATS",
            "--directory",
            str(tmp_path),
            "--overwrite",
        ],
    )

    assert result.exit_code == 0

    # Existing project should be removed.
    base_mocks["warning"].assert_any_call(
        f"A GOATS project already exists at: {project_path}\n"
        "  It will be completely removed before creating a new installation.",
    )
    base_mocks["rmtree"].assert_called_once_with(project_path)

    # Normal installation flow should still occur.
    base_mocks["copy_goats_files"].assert_called_once()
    base_mocks["run_migrations"].assert_called_once()
    base_mocks["subprocess_run"].assert_called_once()
    base_mocks["success"].assert_any_call("GOATS installed successfully!")


@pytest.mark.parametrize("media_exists", [True, False])
def test_install_cli_with_media_dir(cli_runner, tmp_path, base_mocks, media_exists):
    """install handles custom media_dir and passes media_root into copier data."""
    media_dir = tmp_path / "media_root"
    if media_exists:
        media_dir.mkdir()

    result = cli_runner.invoke(
        cli,
        [
            "install",
            "--project-name",
            "GOATS",
            "--directory",
            str(tmp_path),
            "--media-dir",
            str(media_dir),
        ],
    )

    assert result.exit_code == 0

    # copy_goats_files is called with media_root in data.
    base_mocks["copy_goats_files"].assert_called_once()
    (_, data_arg), _ = base_mocks["copy_goats_files"].call_args
    assert data_arg["media_root"] == str(media_dir.resolve())

    # Info message about custom media directory.
    base_mocks["info"].assert_any_call(
        f"Using custom media directory: {media_dir.resolve()}",
    )

    # If media dir already existed, we should warn about possible conflicts.
    if media_exists:
        assert _find_fail_call_contains is not None
        assert any(
            "Media root directory already exists" in str(call.args[0])
            for call in base_mocks["warning"].call_args_list
        )


def test_install_cli_superuser_failure(cli_runner, tmp_path, base_mocks, mocker):
    """install logs failure and exits non-zero if superuser creation fails."""
    base_mocks["subprocess_run"].side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=["manage.py", "createsuperuser"],
    )

    result = cli_runner.invoke(
        cli,
        [
            "install",
            "--project-name",
            "GOATS",
            "--directory",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert any(
        "Superuser creation failed" in str(call.args[0])
        for call in base_mocks["fail"].call_args_list
    )
