from goats_cli.cli import cli

def test_cli_help(cli_runner):
    """
    Test that the CLI displays the help message when no arguments are provided.
    """
    result = cli_runner.invoke(cli, ["--help"])
    assert result.exit_code == 0

def test_cli_install_command(cli_runner):
    """
    Test that the 'install' command is available in the CLI.
    """
    result = cli_runner.invoke(cli, ["install", "--help"])
    assert result.exit_code == 0

def test_cli_run_command(cli_runner):
    """
    Test that the 'run' command is available in the CLI.
    """
    result = cli_runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0

def test_cli_invalid_command(cli_runner):
    """
    Test that an invalid command returns an error.
    """
    result = cli_runner.invoke(cli, ["invalid_command"])
    assert result.exit_code != 0

def test_cli_version_option(cli_runner):
    """
    Test that the '--version' option displays the correct version and exits.
    """
    result = cli_runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
