import pytest
import typer

from goats_cli.commands.common import (
    check_version,
    run_migrations,
    validate_project_structure,
)


def test_validate_project_structure_success(mocker, tmp_path):
    """validate_project_structure returns manage.py when present."""
    mock_section = mocker.patch("goats_cli.commands.common.output.section")
    mock_status = mocker.patch("goats_cli.commands.common.output.status")
    mock_success = mocker.patch("goats_cli.commands.common.output.success")

    project = tmp_path / "GOATS"
    project.mkdir()
    manage_py = project / "manage.py"
    manage_py.write_text("# dummy manage.py")

    result = validate_project_structure(project)

    assert result == manage_py
    mock_section.assert_called_once()
    mock_status.assert_called_once()
    mock_success.assert_called_once_with("GOATS project structure validated.")


def test_validate_project_structure_missing(mocker, tmp_path):
    """validate_project_structure raises Exit(1) if manage.py does not exist."""
    mock_fail = mocker.patch("goats_cli.commands.common.output.fail")
    mocker.patch("goats_cli.commands.common.output.section")
    mocker.patch("goats_cli.commands.common.output.status")

    project = tmp_path / "GOATS"
    project.mkdir()

    with pytest.raises(typer.Exit) as excinfo:
        validate_project_structure(project)

    assert excinfo.value.exit_code == 1
    mock_fail.assert_called_once()


def test_run_migrations_success_with_output(mocker, tmp_path):
    """run_migrations prints subprocess output and success on success."""
    mock_section = mocker.patch("goats_cli.commands.common.output.section")
    mock_status = mocker.patch("goats_cli.commands.common.output.status")
    mock_info = mocker.patch(
        "goats_cli.commands.common.output.subprocess_info_and_padding"
    )
    mock_success = mocker.patch("goats_cli.commands.common.output.success")

    manage = tmp_path / "manage.py"
    manage.write_text("x")

    mock_subprocess = mocker.patch(
        "goats_cli.commands.common.subprocess.run",
        return_value=type(
            "MockProc", (), {"stdout": "Migration OK\n", "returncode": 0}
        )(),
    )

    run_migrations(manage)

    mock_section.assert_called_once()
    mock_status.assert_called_once()
    mock_subprocess.assert_called_once()
    mock_info.assert_called_once()  # because stdout was non-empty
    mock_success.assert_called_once_with("Database migrations applied")


def test_run_migrations_success_no_output(mocker, tmp_path):
    """run_migrations should not print info if stdout is empty."""
    mock_section = mocker.patch("goats_cli.commands.common.output.section")
    mock_status = mocker.patch("goats_cli.commands.common.output.status")
    mock_info = mocker.patch(
        "goats_cli.commands.common.output.subprocess_info_and_padding"
    )
    mock_success = mocker.patch("goats_cli.commands.common.output.success")

    manage = tmp_path / "manage.py"
    manage.write_text("x")

    mocker.patch(
        "goats_cli.commands.common.subprocess.run",
        return_value=type("MockProc", (), {"stdout": "", "returncode": 0})(),
    )

    run_migrations(manage)

    mock_info.assert_not_called()
    mock_success.assert_called_once_with("Database migrations applied")


def test_run_migrations_failure(mocker, tmp_path):
    """run_migrations logs error, prints exception, and raises Exit(1)."""
    mock_fail = mocker.patch("goats_cli.commands.common.output.fail")
    mock_print_exc = mocker.patch("goats_cli.commands.common.output.print_exception")
    mocker.patch("goats_cli.commands.common.output.section")
    mocker.patch("goats_cli.commands.common.output.status")

    manage = tmp_path / "manage.py"
    manage.write_text("x")

    mocker.patch(
        "goats_cli.commands.common.subprocess.run",
        side_effect=Exception("boom"),
    )

    with pytest.raises(typer.Exit) as excinfo:
        run_migrations(manage)

    assert excinfo.value.exit_code == 1
    mock_fail.assert_called_once()
    mock_print_exc.assert_called_once()


@pytest.fixture()
def mock_version_checker(mocker):
    """Mock VersionChecker and make check_version use this instance."""
    checker = mocker.MagicMock()

    mocker.patch(
        "goats_cli.commands.common.VersionChecker",
        return_value=checker,
    )
    return checker


@pytest.fixture()
def mock_output(mocker):
    """Patch all output helpers used in check_version."""
    return {
        "section": mocker.patch("goats_cli.commands.common.output.section"),
        "warning": mocker.patch("goats_cli.commands.common.output.warning"),
        "info": mocker.patch("goats_cli.commands.common.output.info"),
        "space": mocker.patch("goats_cli.commands.common.output.space"),
        "procedure": mocker.patch("goats_cli.commands.common.output.procedure"),
        "steps": mocker.patch("goats_cli.commands.common.output.procedure_steps"),
        "dim": mocker.patch("goats_cli.commands.common.output.dim_info"),
        "confirm": mocker.patch(
            "goats_cli.commands.common.output.confirm_prompt",
            return_value=True,
        ),
        "success": mocker.patch("goats_cli.commands.common.output.success"),
    }


def test_check_version_outdated_continue(mock_output, mock_version_checker):
    """When outdated and user continues, warnings + steps printed."""
    mock_version_checker.is_outdated = True
    mock_version_checker.latest_version = "25.11.4"
    mock_version_checker.current_version = "25.10.1"

    check_version()

    assert mock_output["warning"].call_count >= 1
    assert mock_output["info"].call_count >= 1
    assert mock_output["steps"].called
    assert mock_output["dim"].called
    assert mock_output["confirm"].called
    assert not mock_output["success"].call_args_list


def test_check_version_outdated_aborts(mock_output, mock_version_checker):
    """When outdated and user declines, it raises Abort."""
    mock_version_checker.is_outdated = True
    mock_output["confirm"].return_value = False

    with pytest.raises(typer.Abort):
        check_version()


def test_check_version_unknown(mock_output, mock_version_checker):
    """If version status is None, show warning and continue."""
    mock_version_checker.is_outdated = None

    check_version()

    mock_output["warning"].assert_called_once()


def test_check_version_up_to_date(mock_output, mock_version_checker):
    """If version is up to date, success message is printed."""
    mock_version_checker.is_outdated = False

    check_version()

    mock_output["success"].assert_called_once_with("GOATS is up to date.")
