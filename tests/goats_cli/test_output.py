import pytest

from goats_cli import output
from goats_cli.process import ProcessName, ProcessResult, StartResult


@pytest.fixture()
def consoles(mocker):
    """
    Mock both console and error_console for all tests.
    """
    mock_console = mocker.patch("goats_cli.output.console")
    mock_error_console = mocker.patch("goats_cli.output.error_console")
    return mock_console, mock_error_console


@pytest.mark.parametrize(
    "func, expected",
    [
        (output.success, f"{output.ICON_SUCCESS} hello"),
        (output.warning, f"{output.ICON_WARNING} hello"),
        (output.fail, f"{output.ICON_ERROR} hello"),
        (output.info, "hello"),
        (output.procedure, f"{output.ICON_PROCEDURE} hello"),
    ],
)
def test_basic_output_functions(consoles, func, expected):
    """Ensure basic output helpers call the correct console with the expected markup."""
    mock_console, mock_error = consoles

    func("hello")

    if func is output.fail:
        mock_error.print.assert_called_once_with(expected)
        mock_console.print.assert_not_called()
    elif func is output.info:
        mock_console.print.assert_any_call("hello", style="white")
    else:
        mock_console.print.assert_any_call(expected)


def test_space(consoles):
    """Verify space() prints a blank line."""
    mock_console, _ = consoles
    output.space()
    mock_console.print.assert_called_once_with("")


def test_section(consoles):
    """Verify section() prints a rule before and after spacing."""
    mock_console, _ = consoles
    output.section("TITLE")
    assert mock_console.rule.call_count == 1
    assert mock_console.print.call_count == 2


def test_dim_info(consoles):
    """Ensure dim_info uses dim style."""
    mock_console, _ = consoles
    output.dim_info("msg")
    mock_console.print.assert_called_once()


def test_panel(consoles):
    """Verify panel() wraps content and prints exactly once."""
    mock_console, _ = consoles
    output.panel("hello", title="Test")
    assert mock_console.print.call_count == 1


def test_info_table(consoles):
    """Verify info_table() prints a padded table."""
    mock_console, _ = consoles
    output.info_table({"A": "1"})
    assert mock_console.print.call_count == 1


def test_procedure_steps(consoles):
    """Ensure procedure_steps prints all steps with bullet prefixes."""
    mock_console, _ = consoles
    output.procedure_steps(["x", "y", "z"])
    assert mock_console.print.call_count == 3
    calls = [str(call.args[0]) for call in mock_console.print.call_args_list]
    assert all(output.ICON_BULLET in c for c in calls)


def test_subprocess_info_and_padding(consoles):
    """Ensure subprocess info prints a procedure and padded output."""
    mock_console, _ = consoles
    output.subprocess_info_and_padding("msg", "data")
    assert mock_console.print.call_count >= 1


def test_confirm_prompt(mocker):
    """Ensure confirm_prompt invokes Confirm.ask with markup."""
    mock_confirm = mocker.patch("goats_cli.output.Confirm.ask", return_value=True)
    assert output.confirm_prompt("Proceed?") is True
    mock_confirm.assert_called_once()


def test_print_exception(consoles):
    """Verify print_exception sends output to error_console."""
    _, mock_error = consoles
    output.print_exception()
    mock_error.print_exception.assert_called_once()


def test_status_context_manager(mocker):
    """Ensure status() yields the inner Rich status object."""
    mock_console = mocker.patch("goats_cli.output.console")
    fake_status = mocker.MagicMock()
    mock_console.status.return_value.__enter__.return_value = fake_status

    with output.status("Working...") as s:
        assert s is fake_status

    mock_console.status.assert_called_once()


@pytest.mark.parametrize(
    "result",
    [
        ProcessResult(existed=False, terminated=False, killed=False),
        ProcessResult(existed=True, terminated=False, killed=False, return_code=0),
        ProcessResult(existed=True, terminated=True, killed=True, return_code=9),
        ProcessResult(existed=True, terminated=False, killed=False, return_code=1),
    ],
)
def test_stop_summary_table(consoles, result):
    """Ensure stop_summary_table prints exactly once."""
    mock_console, _ = consoles

    results = {ProcessName.DJANGO: result}
    output.stop_summary_table(results)

    # Should produce one console.print() call
    mock_console.print.assert_called_once()


@pytest.mark.parametrize(
    "result",
    [
        StartResult(existed=False, started=False),
        StartResult(existed=True, started=True),
        StartResult(existed=True, started=True, error="boom"),
    ],
)
def test_start_summary_table(consoles, result):
    """Ensure start_summary_table prints exactly once."""
    mock_console, _ = consoles

    results = {ProcessName.REDIS: result}
    output.start_summary_table(results)

    mock_console.print.assert_called_once()
