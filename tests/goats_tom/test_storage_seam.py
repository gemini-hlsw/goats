"""Guards that nothing reaches around `goats_tom.storage` to the local disk.

Two shapes broke the assumption in ``STATUS.md`` that swapping the storage
backend would be free:

- ``FieldFile.path``, which raises `NotImplementedError` on any backend that
  is not a local filesystem.
- ``settings.MEDIA_ROOT / …``, which does not touch the storage API at all
  and so would go on reading and writing the control-plane disk after a
  swap, silently.

The second is the one worth a build failure. A `NotImplementedError` shows
up on the first request. A file written to the wrong disk in ``datalab``
mode is proprietary data on a VM that is supposed never to hold any, and
nothing reports it.

This is the same argument as `test_context_scoping`: a sweep that depends on
someone remembering to look will rot. Both findings here were made by
grepping a checkout, not by any test, and the next one will be reintroduced
by a merge nobody reviews this closely.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "goats_tom"

#: Modules allowed to name these directly, each with a reason.
#:
#: An entry here means "this file is the seam, or is on the far side of it".
#: Anything else needs `goats_tom.storage`.
ALLOWED = {
    "storage.py": "The seam itself.",
    "remote/runner.py": (
        "Runs on Data Lab, not on the VM. Its filesystem is the remote "
        "scratch directory and has nothing to do with MEDIA_ROOT."
    ),
}


def _python_files():
    """Yield every GOATS source file, skipping migrations and vendored code."""
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC).as_posix()
        if "migrations/" in rel or rel.startswith("tests/"):
            continue
        yield rel, path


def _is_media_root(node: ast.AST) -> bool:
    """Whether `node` is an attribute access of ``settings.MEDIA_ROOT``."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "MEDIA_ROOT"
        and isinstance(node.value, ast.Name)
        and node.value.id == "settings"
    )


def _is_field_file_path(node: ast.AST) -> bool:
    """Whether `node` looks like ``<something>.data.path``.

    Notes
    -----
    Matches on the ``.data.path`` shape rather than on the type, which is
    not knowable statically. That is narrow enough to avoid flagging
    ``os.path`` and every other unrelated ``.path``, and wide enough to
    catch the form every one of the ten call sites actually used.
    """
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "path"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "data"
    )


@pytest.mark.parametrize("rel,path", list(_python_files()), ids=lambda v: str(v))
def test_no_direct_local_storage_access(rel, path):
    """Fail if a module reaches past the storage seam.

    Parameters
    ----------
    rel : str
        Path relative to the ``goats_tom`` package.
    path : `pathlib.Path`
        Absolute path to the module.
    """
    if rel in ALLOWED:
        pytest.skip(ALLOWED[rel])

    tree = ast.parse(path.read_text(), filename=str(path))

    offences = []
    for node in ast.walk(tree):
        if _is_media_root(node):
            offences.append((node.lineno, "settings.MEDIA_ROOT"))
        elif _is_field_file_path(node):
            offences.append((node.lineno, ".data.path"))

    assert not offences, (
        f"{rel} reaches the local filesystem directly at "
        + ", ".join(f"line {line} ({what})" for line, what in offences)
        + ". Use `goats_tom.storage`: `local_path` for a file that must exist "
        "on disk, `storage_name` for a storage-relative name, `working_root` "
        "for a directory to build a working tree in. If this module genuinely "
        "belongs on the far side of the seam, add it to ALLOWED with a reason."
    )
