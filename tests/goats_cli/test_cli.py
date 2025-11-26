from goats_cli.cli import cli


class TestGOATSCli:
    """
    Test suite for the GOATS CLI.
    """

    def test_cli_help(self, cli_runner):
        """
        Test that the CLI displays the help message when no arguments are provided.
        """
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

    def test_cli_install_command(self, cli_runner):
        """
        Test that the 'install' command is available in the CLI.
        """
        result = cli_runner.invoke(cli, ["install", "--help"])
        assert result.exit_code == 0

    def test_cli_run_command(self, cli_runner):
        """
        Test that the 'run' command is available in the CLI.
        """
        result = cli_runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0

    def test_cli_invalid_command(self, cli_runner):
        """
        Test that an invalid command returns an error.
        """
        result = cli_runner.invoke(cli, ["invalid_command"])
        assert result.exit_code != 0
