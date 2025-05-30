import os

import nox

# Force Conda to use osx-64 architecture.
os.environ["CONDA_SUBDIR"] = "osx-64"

nox.options.sessions = ["tests"]

PYTHON_VERSIONS = ["3.10", "3.12"]
DRAGONS_VERSION_PY310 = "3.2.3"
DRAGONS_VERSION_PY312 = "4.0.0"
CONDA_CHANNELS = ["http://astroconda.gemini.edu/public", "conda-forge"]


def run_pytest(session, *, remote: bool = False, coverage: bool = False) -> None:
    """Helper to install and run pytest with optional flags."""

    # Determine the correct DRAGONS version based on Python version.
    if session.python.startswith("3.10"):
        dragons_version = DRAGONS_VERSION_PY310
    elif session.python.startswith("3.12"):
        dragons_version = DRAGONS_VERSION_PY312
    else:
        session.skip(f"No compatible DRAGONS version for Python {session.python}")

    # Install Conda packages.
    session.conda_install(
        f"dragons={dragons_version}",
        channel=CONDA_CHANNELS,
    )

    # Install dev/test dependencies via pip.
    session.install("-e", ".[test]")

    # Pytest options.
    args = ["-r", "A", "-v", "-n", "auto"]
    if remote:
        args.append("--remote-data")
    if coverage and session.python == "3.10":
        args += ["--cov=gpp_client", "--cov=tests", "--cov-report=xml", "--cov-branch"]

    session.run("pytest", *args)


@nox.session(venv_backend="conda", python=PYTHON_VERSIONS)
def tests(session):
    """Run the test suite."""
    run_pytest(session)


@nox.session(venv_backend="conda", python=PYTHON_VERSIONS)
def remote(session):
    """Run the '--remote-data' test suite."""
    run_pytest(session, remote=True)


# @nox.session(python=PYTHON_VERSIONS)
# def github_tests(session):
#     """Run GitHub CI test suite with coverage (only in 3.10)."""
#     run_pytest(session, coverage=True)


@nox.session(python=["3.10"])
def github_lint(session):
    """Run GitHub CI linting."""
    session.install("ruff")
    session.run("ruff", "check")
