"""
Rich-based console instances for the GOATS CLI.
"""

__all__ = [
    "console",
    "error_console",
]

from rich.console import Console

console = Console(highlight=False)
"""Standard console for general output with syntax highlighting enabled."""

error_console = Console(stderr=True, highlight=False)
"""Console for error output directed to stderr with bold red styling."""
