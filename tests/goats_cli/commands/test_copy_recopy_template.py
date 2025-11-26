from contextlib import nullcontext
from pathlib import Path

import pytest

from goats_cli.commands.install import copy_goats_files
from goats_cli.commands.run import sync_goats_files


@pytest.fixture(autouse=True)
def silence_cli_output(mocker):
    mocker.patch("goats_cli.commands.install.output.section")
    mocker.patch(
        "goats_cli.commands.install.output.status",
        side_effect=lambda *a, **k: nullcontext(),
    )
    mocker.patch("goats_cli.commands.install.output.success")
    mocker.patch("goats_cli.commands.install.output.fail")
    mocker.patch("goats_cli.commands.install.output.print_exception")
    mocker.patch("goats_cli.commands.install.utils.wait")

    mocker.patch("goats_cli.commands.run.output.section")
    mocker.patch(
        "goats_cli.commands.run.output.status",
        side_effect=lambda *a, **k: nullcontext(),
    )
    mocker.patch("goats_cli.commands.run.output.success")
    mocker.patch("goats_cli.commands.run.output.fail")
    mocker.patch("goats_cli.commands.run.output.print_exception")
    mocker.patch("goats_cli.commands.run.utils.wait")


def _create_test_project(tmp_path, mocker):
    """Helper: create a fresh rendered GOATS project."""
    project_path = tmp_path / "GOATS"
    data = {
        "project_name": "GOATS",
        "secret_key": "TEST",
        "create_date": "2025-01-01T00:00:00Z",
        "goats_version": "25.11.0",
        "redis_host": "localhost",
        "redis_port": 6379,
    }
    copy_goats_files(project_path, data)
    return project_path


def _assert_initial_structure(project_path: Path):
    """Shared checks for initial render correctness."""
    assert project_path.is_dir()
    module_dir = project_path / "GOATS"
    settings_dir = module_dir / "settings"
    env_dir = settings_dir / "environments"

    for f in ["__init__.py", "asgi.py", "urls.py", "wsgi.py"]:
        assert (module_dir / f).is_file()

    for f in ["__init__.py", "base.py", "dynamic.py", "generated.py", "local.py"]:
        assert (settings_dir / f).is_file()

    for f in ["__init__.py", "cli.py", "development.py", "production.py"]:
        assert (env_dir / f).is_file()

    assert (project_path / "static").is_dir()
    assert (project_path / "templates").is_dir()
    assert (project_path / "tmp").exists()
    assert (project_path / ".copier-answers.yml").is_file()

    # No Jinja files left behind
    for f in project_path.rglob("*.jinja"):
        raise AssertionError(f"Template ref not rendered: {f}")


def test_copy_template_full_structure_normal_recopy(tmp_path, mocker):
    """Normal recopy updates only template-config files and preserves scaffolding."""
    project_path = _create_test_project(tmp_path, mocker)
    _assert_initial_structure(project_path)

    module_dir = project_path / "GOATS"
    settings_dir = module_dir / "settings"
    env_dir = settings_dir / "environments"

    must_update = [
        settings_dir / "__init__.py",
        settings_dir / "base.py",
        settings_dir / "dynamic.py",
        env_dir / "__init__.py",
        env_dir / "cli.py",
        env_dir / "development.py",
        env_dir / "production.py",
    ]

    must_preserve = [
        project_path / "manage.py",
        module_dir / "__init__.py",
        module_dir / "asgi.py",
        module_dir / "urls.py",
        module_dir / "wsgi.py",
        settings_dir / "generated.py",
        settings_dir / "local.py",
    ]

    for f in must_update:
        f.write_text("UPDATE_ME\n")

    for f in must_preserve:
        f.write_text("KEEP_ME\n")

    sync_goats_files(project_path, "25.11.1", full_recopy=False, quiet=True)

    for f in must_update:
        assert f.read_text() != "UPDATE_ME\n", f"{f} was not updated"

    for f in must_preserve:
        assert f.read_text() == "KEEP_ME\n", f"{f} changed unexpectedly"


def test_copy_template_full_structure_full_recopy(tmp_path, mocker):
    """Full recopy overwrites scaffolding but still preserves certain settings."""
    project_path = _create_test_project(tmp_path, mocker)
    _assert_initial_structure(project_path)

    module_dir = project_path / "GOATS"
    settings_dir = module_dir / "settings"
    env_dir = settings_dir / "environments"

    must_update = [
        # settings config
        settings_dir / "__init__.py",
        settings_dir / "base.py",
        settings_dir / "dynamic.py",
        env_dir / "__init__.py",
        env_dir / "cli.py",
        env_dir / "development.py",
        env_dir / "production.py",
        # scaffolding allowed to overwrite in full mode:
        module_dir / "__init__.py",
        module_dir / "asgi.py",
        module_dir / "urls.py",
        module_dir / "wsgi.py",
        project_path / "manage.py",
    ]

    must_preserve = [
        settings_dir / "generated.py",
        settings_dir / "local.py",
    ]

    for f in must_update:
        f.write_text("UPDATE_ME\n")

    for f in must_preserve:
        f.write_text("KEEP_ME\n")

    sync_goats_files(project_path, "25.11.1", full_recopy=True, quiet=True)

    # Updated
    for f in must_update:
        assert f.read_text() != "UPDATE_ME\n", f"{f} was not overwritten in full recopy"

    # Always preserved
    for f in must_preserve:
        assert f.read_text() == "KEEP_ME\n", f"{f} was incorrectly overwritten"
