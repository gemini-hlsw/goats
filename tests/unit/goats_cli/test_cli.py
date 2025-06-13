import click.testing
import pytest
from goats_cli import cli


@pytest.fixture()
def runner():
    return click.testing.CliRunner()


def test_cli_succeeds_without_subcommand(runner):
    result = runner.invoke(cli)
    assert result.exit_code == 0
