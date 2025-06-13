__all__ = ["modify_settings"]

from pathlib import Path

from goats_cli.plugins import GOATSPlugin, Plugin

# Initialize constants.
SETTINGS_FILENAME = "settings.py"


def modify_settings(
    file_path: Path, add_goats: bool | None = False, verbose: bool | None = False
) -> None:
    """Modify Django settings to include additional apps.

    Parameters
    ----------
    file_path : `Path`
        The path to the settings file that needs to be modified.
    add_goats : `bool`, optional
        Flag indicating if GOATS plugin should be added to settings.
    verbose : `bool | None`, optional
        If `True`, prints extra information.

    Raises
    ------
    FileNotFoundError
        Raised if the settings file does not exist.

    """
    if verbose:
        print(f"Modifying {file_path.absolute()}...")

    # Convert to path object if it isn't.
    if not isinstance(file_path, Path):
        file_path = Path(file_path)

    # Check if file exists and raise if not.
    if not file_path.is_file():
        raise FileNotFoundError(f"{file_path.absolute()} does not exist.")

    # Read the file.
    with open(file_path) as f:
        lines = f.readlines()

    # Add plugins.
    if add_goats:
        lines = _find_and_add(lines, GOATSPlugin(), verbose=verbose)

    # Write the file back out
    with open(file_path, "w") as f:
        f.writelines(lines)


def _find_and_add(
    lines: list[str], plugin: Plugin, verbose: bool | None = False
) -> list[str]:
    """Utility function to add a plugin to the lines from a settings file.

    Parameters
    ----------
    lines : `list[str]`
        The lines from the settings file.
    plugin: `Plugin`
        Class instance of the specific plugin to install.
    verbose : `bool | None`, optional
        If `True`, prints extra information.

    Returns
    -------
    `list[str]`
        The updated list of lines with the plugin added.

    Raises
    ------
    ValueError
        Raised if the ``Plugin.look_for`` string is not found in the file.

    """
    line_number = None

    # Don't change anything if already exists.
    if plugin.line_to_add.strip() in (line.strip() for line in lines):
        if verbose:
            print(f"Plugin '{plugin.name}' already added...")
        return lines

    # Remove line if specified and exists
    if plugin.line_to_remove and plugin.line_to_remove.strip() in (
        line.strip() for line in lines
    ):
        lines.remove(plugin.line_to_remove)
        if verbose:
            print(f"Line removed for plugin '{plugin.name}'.")

    # Find line number for matching string.
    for index, line in enumerate(lines):
        if plugin.look_for in line:
            line_number = index
            break

    if line_number is None:
        raise ValueError(
            f"'{plugin.look_for}' not found in file, please verify contents."
        )

    # Find the opening bracket line.
    pointer = None
    for index, line in enumerate(lines[line_number:]):
        if "[" in line:
            pointer = index + line_number
            break

    # Insert just after the opening bracket.
    lines.insert(pointer + 1, plugin.line_to_add)

    if verbose:
        print(f"Plugin '{plugin.name}' added.")
    return lines
