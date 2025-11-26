"""
Rich-based output utilities for the GOATS CLI.
"""

__all__ = [
    "section",
    "info",
    "success",
    "warning",
    "fail",
    "panel",
    "confirm_prompt",
    "print_exception",
    "status",
    "space",
]

from contextlib import contextmanager
from typing import Optional

from rich.console import RenderableType
from rich.padding import Padding
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from goats_cli.console import console, error_console
from goats_cli.process import ProcessName, ProcessResult, StartResult

ICON_BULLET = "[bold white]•[/]"
ICON_SUCCESS = "[bold green]✔[/]"
ICON_WARNING = "[bold yellow]![/]"
ICON_ERROR = "[bold red]✖[/]"
ICON_PROCEDURE = "[bold blue]↴[/]"


def space() -> None:
    """
    Print a blank line to the console.
    """
    console.print("")


def section(title: str, style: str = "dim cyan", align: str = "left") -> None:
    """
    Render a horizontal rule section header.

    Parameters
    ----------
    title : str
        Text to display inside the rule.
    style : str, optional
        Rich style applied to the rule line and title.
    align : str, optional
        Alignment of the title within the rule.
    """
    space()
    console.rule(title=f"{title}", style=style, align=align)
    space()


def info(msg: str) -> None:
    """
    Print a plain informational message.

    Parameters
    ----------
    msg : str
        The message text.
    """
    console.print(f"{msg}", style="white")


def dim_info(msg: RenderableType) -> None:
    """
    Print a dimmed informational message.

    Parameters
    ----------
    msg : RenderableType
        The message text.
    """
    console.print(f"{msg}", style="dim")


def success(msg: RenderableType) -> None:
    """
    Print a success message prefixed with a green check mark.

    Parameters
    ----------
    msg : RenderableType
        Success message text.
    """
    console.print(f"{ICON_SUCCESS} {msg}")


def warning(msg: RenderableType) -> None:
    """
    Print a warning message prefixed with a yellow warning symbol.

    Parameters
    ----------
    msg : RenderableType
        Warning text.
    """
    console.print(f"{ICON_WARNING} {msg}")
    space()


def fail(msg: RenderableType) -> None:
    """
    Print an error message to stderr, prefixed with a red cross.

    Parameters
    ----------
    msg : RenderableType
        Error message text.
    """
    error_console.print(f"{ICON_ERROR} {msg}")


def procedure(msg: RenderableType) -> None:
    """
    Print a procedure message prefixed with a blue arrow.

    Parameters
    ----------
    msg : RenderableType
        Procedure message text.
    """
    console.print(f"{ICON_PROCEDURE} {msg}")


def procedure_steps(steps: list[RenderableType]) -> None:
    """
    Print a list of procedure steps, each prefixed with a dot and indented.

    Parameters
    ----------
    steps : list[RenderableType]
        List of procedure step messages.
    """
    for step in steps:
        console.print(f"  {ICON_BULLET} {step}")


def panel(
    msg: RenderableType,
    *,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    style: Optional[str] = None,
    border_style: str = "cyan",
    expand: bool = False,
) -> None:
    """
    Render a styled Rich panel.

    Parameters
    ----------
    msg : RenderableType
        Contents of the panel.
    title : str, optional
        Optional panel title.
    subtitle : str, optional
        Optional panel subtitle.
    style : str, optional
        Optional panel style.
    border_style : str, default="cyan"
        Border style for the panel.
    expand : bool, default=False
        Whether the panel should expand to the full width of the console.
    """
    console.print(
        Panel(
            msg,
            title=title,
            subtitle=subtitle,
            style=style if style is not None else "none",
            border_style=border_style,
            expand=expand,
        )
    )


def info_table(items: dict[str, str]) -> None:
    """
    Render a table of informational key-value pairs.

    Parameters
    ----------
    items : dict[str, str]
        Dictionary of key-value pairs to display.
    """
    table = Table(box=None, show_header=False, padding=(0, 1))
    table.add_column("Field", style="white")
    table.add_column("Value", style="dim")

    for key, value in items.items():
        table.add_row(f"{ICON_BULLET} {key}", f"{value}")

    console.print(Padding(table, (0, 0, 1, 4)))


def subprocess_info_and_padding(msg: RenderableType, output: RenderableType) -> None:
    """
    Render a Rich message with padding for subprocess output.

    Parameters
    ----------
    msg : RenderableType
        The message to render.
    output : RenderableType
        The subprocess output to render with padding.
    """
    procedure(msg)
    console.print(Padding(output, pad=(0, 0, 1, 4), style="dim"))


def confirm_prompt(msg: str) -> bool:
    """
    Display a yes/no prompt and return True if the user confirms.

    Parameters
    ----------
    msg : str
        Prompt text.

    Returns
    -------
    bool
        True if the user selects yes, False otherwise.
    """
    return Confirm.ask(
        f"[bold yellow]{msg}[/]",
    )


def print_exception(show_locals: bool = True) -> None:
    """
    Print the current exception's traceback to stderr.

    Parameters
    ----------
    show_locals : bool, default=True
        Whether to show local variables in each stack frame.
    """
    error_console.print_exception(show_locals=show_locals)


@contextmanager
def status(message: str, *, spinner: str = "dots"):
    """
    Context manager for displaying a Rich status spinner.

    Parameters
    ----------
    message : str
        Text to display next to the spinner.
    spinner : str, default="dots"
        Spinner style (see: ``python -m rich.spinner``).
    """
    with console.status(f"[cyan]{message}[/]", spinner=spinner) as status:
        yield status


def stop_summary_table(results: dict[ProcessName, ProcessResult]) -> None:
    """
    Render a two-column shutdown summary:
    - Left column: colored icon + process label
    - Right column: dim explanatory message
    """

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Process", style="none")
    table.add_column("Message", style="dim")

    for name, result in results.items():
        # --- Left column content (icon + label) ---
        label = f"[white]{name.value}[/]"

        # Process not started
        if not result.existed:
            left = f"{ICON_BULLET} {label}"
            right = "was not running"
            table.add_row(left, right)
            continue

        # Clean stop
        if result.ok():
            left = f"{ICON_SUCCESS} {label}"
            right = "stopped cleanly"
            table.add_row(left, right)
            continue

        # Forced kill
        if result.killed:
            rc = (
                f"(code {result.return_code})" if result.return_code is not None else ""
            )
            left = f"{ICON_WARNING} {label}"
            right = f"force killed {rc}"
            table.add_row(left, right)
            continue

        # Abnormal exit without kill
        left = f"{ICON_ERROR} {label}"
        right = (
            f"exited abnormally (code {result.return_code})"
            if result.return_code is not None
            else "exited abnormally"
        )
        table.add_row(left, right)

    # Left padding to align with CLI layout
    console.print(Padding(table, (0, 0, 1, 4)))


def start_summary_table(results: dict[ProcessName, StartResult]) -> None:
    """
    Render a two-column startup summary:
    left: colored icon + bold label
    right: dim summary message
    """

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Process", style="none")
    table.add_column("Message", style="dim")

    for name, result in results.items():
        label = f"[white]{name.value}[/]"

        # Never attempted
        if not result.existed:
            table.add_row(f"{ICON_BULLET} {label}", "was not started")
            continue

        # Started OK
        if result.ok():
            table.add_row(f"{ICON_SUCCESS} {label}", "started successfully")
            continue

        # Startup failure
        table.add_row(f"{ICON_ERROR} {label}", f"failed to start: {result.error}")

    console.print(Padding(table, (0, 0, 1, 4)))
