import shutil
from pathlib import Path

import pytest

from goats_cli.modify_settings import modify_settings
from goats_cli.plugins import GOATSPlugin


@pytest.fixture()
def settings_file(tmp_path):
    settings_file = Path(__file__).parent.parent / "data" / "settings.py"
    copied_settings_file = tmp_path / "settings.py"

    shutil.copyfile(settings_file, copied_settings_file)
    return copied_settings_file


@pytest.fixture()
def tom_setup_settings_file(tmp_path):
    tom_setup_settings_file = Path(__file__).parent.parent / "data" / "goats_setup_settings.py"
    copied_tom_setup_settings_file = tmp_path / "goats_setup_settings.py"

    shutil.copyfile(tom_setup_settings_file, copied_tom_setup_settings_file)
    return copied_tom_setup_settings_file


def test_modify_settings_goats(tom_setup_settings_file):
    # Test adding ANTARES plugin.
    modify_settings(tom_setup_settings_file, add_goats=True)
    with open(tom_setup_settings_file) as f:
        lines = f.readlines()
    assert GOATSPlugin().line_to_add in lines
