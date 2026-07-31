"""Tests for the database configuration in the settings template.

The database block lives in ``base.py.jinja``, which is a Copier template
rather than an importable module, so these tests render it and execute just
the database section. That is more involved than importing a function, but it
tests the code that actually ships -- extracting the logic into a helper
purely to make it importable would leave the template itself untested, which
is where a mistake would actually bite.
"""

import ast
import os
import re
from pathlib import Path

import pytest

TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "goats_cli"
    / "goats_template"
    / "{{ project_name }}"
    / "settings"
    / "base.py.jinja"
)


def _render() -> str:
    """Render the template with a placeholder project name.

    Returns
    -------
    str
        The template with ``{{ project_name }}`` substituted. A plain
        substitution rather than a real Jinja render: the file uses no
        control flow, only that one variable, and this keeps the test from
        depending on Copier's rendering configuration.
    """
    return TEMPLATE.read_text().replace("{{ project_name }}", "testproject")


def _exec_database_block(monkeypatch, generated=None, **env) -> dict:
    """Execute only the database section of the rendered settings.

    Parameters
    ----------
    monkeypatch : `pytest.MonkeyPatch`
        Used to set the ``GOATS_DB_*`` environment variables.
    generated : dict, optional
        Values as if written into ``generated.py`` by the installer. Seeded
        into the namespace before execution, which is exactly how the real
        settings see them -- ``base.py`` star-imports generated.py before the
        database block runs.
    **env
        Environment variables to set for this call.

    Returns
    -------
    dict
        The namespace after execution, containing ``DATABASES``.

    Notes
    -----
    Slices from ``DATABASE_TIMEOUT`` to the end of the database block rather
    than executing the whole settings file, which would import Redis, Django
    apps and the generated/dynamic settings modules that only exist in a real
    installation. Note this means these tests only cover the database block --
    `test_required_setting_still_defined` is what guards the rest of the file.
    """
    for key in (
        "GOATS_DB_ENGINE",
        "GOATS_DB_NAME",
        "GOATS_DB_USER",
        "GOATS_DB_PASSWORD",
        "GOATS_DB_HOST",
        "GOATS_DB_PORT",
        "GOATS_DB_CONN_MAX_AGE",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    source = _render()
    start = source.index("DATABASE_TIMEOUT = 20")
    # The database block ends at its trailing docstring. Anything past that
    # references Redis and other settings this helper deliberately does not
    # set up.
    marker = '"""Database configuration."""'
    end = source.index(marker) + len(marker)
    block = source[start:end]

    from django.core.exceptions import ImproperlyConfigured

    namespace = {
        "os": os,
        "Path": Path,
        "BASE_DIR": Path("/fake/base"),
        "ImproperlyConfigured": ImproperlyConfigured,
    }
    namespace.update(generated or {})
    exec(compile(block, str(TEMPLATE), "exec"), namespace)
    return namespace


def test_rendered_template_is_valid_python():
    """The template renders to something Python can parse."""
    ast.parse(_render())


# Settings that base.py must define. Not exhaustive -- the point is to notice
# if an edit to the database block accidentally removes unrelated settings.
# An earlier version of the database change did exactly that: it replaced a
# span between two markers that turned out to be 300 lines apart, silently
# deleting LOGGING, the Channels config and the whole Dramatiq setup. The file
# still parsed cleanly, so a syntax check did not catch it -- `goats install`
# failed at `migrate` instead, with a NameError from deep inside Django.
REQUIRED_SETTINGS = [
    "DATABASES",
    "DATABASE_TIMEOUT",
    "LOGGING",
    "INSTALLED_APPS",
    "MIDDLEWARE",
    "ASGI_APPLICATION",
    "WSGI_APPLICATION",
    "CHANNEL_LAYERS",
    "DRAMATIQ_BROKER",
    "DRAMATIQ_REDIS_URL",
    "DRAMATIQ_AUTODISCOVER_MODULES",
    "AUTH_PASSWORD_VALIDATORS",
    "TEMPLATES",
    "STATIC_URL",
    "TARGET_PERMISSIONS_ONLY",
    "ANTARES_TIMEOUT",
    "GPP_ENV",
]


@pytest.mark.parametrize("name", REQUIRED_SETTINGS)
def test_required_setting_still_defined(name):
    """Every expected setting survives edits to the database block."""
    assigned = {
        target.id
        for node in ast.parse(_render()).body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            node.targets if isinstance(node, ast.Assign) else [node.target]
        )
        if isinstance(target, ast.Name)
    }
    # DATABASES is assigned inside the engine if/else, so also accept names
    # bound anywhere in the module body.
    for node in ast.walk(ast.parse(_render())):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned.add(target.id)

    assert name in assigned, f"{name} is no longer defined in base.py"


def test_wal_pragma_not_applied_outside_sqlite_branch():
    """The WAL pragma must not be set unconditionally after DATABASES.

    It used to be applied by mutating DATABASES after the fact, which would
    crash under PostgreSQL -- `init_command` is a sqlite3 driver option.
    """
    rendered = _render()
    assert 'DATABASES["default"]["OPTIONS"]["init_command"]' not in rendered
    assert "PRAGMA journal_mode=WAL;" in rendered


def test_defaults_to_sqlite(monkeypatch):
    """With nothing set, GOATS uses SQLite.

    Single-user installs must keep working with no configuration and no
    database server.
    """
    namespace = _exec_database_block(monkeypatch)
    default = namespace["DATABASES"]["default"]
    assert default["ENGINE"] == "django.db.backends.sqlite3"
    assert default["NAME"] == Path("/fake/base") / "db.sqlite3"


def test_sqlite_keeps_wal_and_timeout(monkeypatch):
    """SQLite still gets WAL mode and the lock timeout."""
    default = _exec_database_block(monkeypatch)["DATABASES"]["default"]
    assert default["OPTIONS"]["init_command"] == "PRAGMA journal_mode=WAL;"
    assert default["OPTIONS"]["timeout"] == 20


@pytest.mark.parametrize("value", ["postgres", "postgresql", "POSTGRES", " postgres "])
def test_postgres_selected(monkeypatch, value):
    """The Postgres backend is selected, case- and whitespace-insensitively."""
    default = _exec_database_block(monkeypatch, GOATS_DB_ENGINE=value)["DATABASES"][
        "default"
    ]
    assert default["ENGINE"] == "django.db.backends.postgresql"


def test_postgres_has_no_sqlite_options(monkeypatch):
    """SQLite-only options must not leak into the Postgres config.

    ``timeout`` and the WAL pragma are sqlite3 driver options; passing them to
    Postgres would fail at connection time.
    """
    default = _exec_database_block(monkeypatch, GOATS_DB_ENGINE="postgres")[
        "DATABASES"
    ]["default"]
    assert "OPTIONS" not in default or not default.get("OPTIONS")


def test_postgres_reads_connection_settings(monkeypatch):
    """Connection details come from the environment."""
    default = _exec_database_block(
        monkeypatch,
        GOATS_DB_ENGINE="postgres",
        GOATS_DB_NAME="mydb",
        GOATS_DB_USER="myuser",
        GOATS_DB_PASSWORD="secret",
        GOATS_DB_HOST="db.example.org",
        GOATS_DB_PORT="6543",
        GOATS_DB_CONN_MAX_AGE="120",
    )["DATABASES"]["default"]

    assert default["NAME"] == "mydb"
    assert default["USER"] == "myuser"
    assert default["PASSWORD"] == "secret"
    assert default["HOST"] == "db.example.org"
    assert default["PORT"] == "6543"
    assert default["CONN_MAX_AGE"] == 120


def test_postgres_defaults(monkeypatch):
    """Sensible defaults when only the engine is set."""
    default = _exec_database_block(monkeypatch, GOATS_DB_ENGINE="postgres")[
        "DATABASES"
    ]["default"]
    assert default["NAME"] == "goats"
    assert default["HOST"] == "localhost"
    assert default["PORT"] == "5432"
    assert default["CONN_MAX_AGE"] == 60


def test_sqlite_name_overridable(monkeypatch):
    """A SQLite database can be placed somewhere other than BASE_DIR."""
    default = _exec_database_block(
        monkeypatch, GOATS_DB_ENGINE="sqlite", GOATS_DB_NAME="/tmp/other.sqlite3"
    )["DATABASES"]["default"]
    assert default["NAME"] == "/tmp/other.sqlite3"


def test_unknown_engine_fails_loudly(monkeypatch):
    """A typo must not silently fall back to SQLite.

    Falling back would mean a deployment that believed it was on Postgres
    quietly running on SQLite -- and hitting its single-writer limit under
    load with no indication why.
    """
    from django.core.exceptions import ImproperlyConfigured

    with pytest.raises(ImproperlyConfigured):
        _exec_database_block(monkeypatch, GOATS_DB_ENGINE="mysql")


def test_postgres_extra_declared():
    """The driver is declared as an optional dependency.

    Selecting Postgres without a driver fails at connection time with an
    unhelpful import error, so the extra needs to exist to point users at.
    """
    pyproject = (
        Path(__file__).resolve().parents[2] / "pyproject.toml"
    ).read_text()
    assert re.search(r"^postgres = \[", pyproject, re.M)
    assert "psycopg" in pyproject


def test_local_settings_never_overwritten():
    """`local.py` must survive upgrades.

    It is documented as the place to override `DATABASES` without depending on
    the environment, which is only true if `goats run`'s recopy step leaves it
    alone. `generated.py` is protected for the same reason -- it holds the
    SECRET_KEY.
    """
    from goats_cli.config import config

    protected = set(config.never_overwrite)
    assert "{{ project_name }}/settings/local.py" in protected
    assert "{{ project_name }}/settings/generated.py" in protected


def test_local_settings_loaded_last():
    """`local.py` is imported after base and environment settings.

    Import order is what makes a `DATABASES` override there actually win.
    """
    loader = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "goats_cli"
        / "goats_template"
        / "{{ project_name }}"
        / "settings"
        / "__init__.py.jinja"
    ).read_text()

    assert loader.index("from .base import *") < loader.index("from .local import *")
    assert loader.index("environments.production") < loader.index(
        "from .local import *"
    )


def test_generated_settings_are_used(monkeypatch):
    """Values written by the installer are honoured without any env vars.

    This is what makes `goats install --db-engine postgres` stick: the choice
    is recorded in generated.py, so it applies in every shell rather than only
    where the variables happen to be exported.
    """
    default = _exec_database_block(
        monkeypatch,
        generated={
            "GOATS_DB_ENGINE": "postgres",
            "GOATS_DB_NAME": "installed_db",
            "GOATS_DB_HOST": "db.internal",
        },
    )["DATABASES"]["default"]

    assert default["ENGINE"] == "django.db.backends.postgresql"
    assert default["NAME"] == "installed_db"
    assert default["HOST"] == "db.internal"


def test_environment_overrides_generated(monkeypatch):
    """An environment variable beats the installed value.

    Lets a container or CI job point an existing installation somewhere else
    without editing files.
    """
    default = _exec_database_block(
        monkeypatch,
        generated={"GOATS_DB_ENGINE": "postgres", "GOATS_DB_HOST": "installed"},
        GOATS_DB_HOST="from_env",
    )["DATABASES"]["default"]

    assert default["HOST"] == "from_env"


def test_blank_generated_values_fall_back(monkeypatch):
    """Blank installer values mean "not specified", not an empty setting.

    The installer writes blanks for anything not passed, so a blank host must
    fall back to the default rather than producing HOST="".
    """
    default = _exec_database_block(
        monkeypatch,
        generated={
            "GOATS_DB_ENGINE": "postgres",
            "GOATS_DB_HOST": "",
            "GOATS_DB_PORT": "",
        },
    )["DATABASES"]["default"]

    assert default["HOST"] == "localhost"
    assert default["PORT"] == "5432"


def test_blank_generated_engine_means_sqlite(monkeypatch):
    """A blank engine falls back to SQLite rather than failing."""
    default = _exec_database_block(
        monkeypatch, generated={"GOATS_DB_ENGINE": ""}
    )["DATABASES"]["default"]
    assert default["ENGINE"] == "django.db.backends.sqlite3"


def test_installer_passes_database_answers():
    """`goats install` forwards its --db-* options into the template context.

    Without this the options would be accepted and silently ignored.
    """
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "goats_cli"
        / "commands"
        / "install.py"
    ).read_text()

    for key in (
        "db_engine",
        "db_name",
        "db_user",
        "db_password",
        "db_host",
        "db_port",
    ):
        assert f'"{key}": {key},' in source


def test_generated_template_emits_database_settings():
    """generated.py records the database answers.

    This file is never overwritten, which is what makes the choice persist.
    """
    template = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "goats_cli"
        / "goats_template"
        / "{{ project_name }}"
        / "settings"
        / "generated.py.jinja"
    ).read_text()

    assert 'GOATS_DB_ENGINE = "{{ db_engine }}"' in template
    assert 'GOATS_DB_NAME = "{{ db_name }}"' in template
