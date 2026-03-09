import pytest
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture(scope="module")
def cli_runner():
    return runner
