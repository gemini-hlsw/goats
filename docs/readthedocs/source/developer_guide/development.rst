Developer Guide
===============

This page documents how to maintain and develop GOATS.

Trunk-Based Development
-----------------------

GOATS follows `trunk-based development <https://trunkbaseddevelopment.com/>`_, where all changes are integrated into a single shared branch (``main``) frequently.

Key practices:

- Developers work in short-lived branches (typically < 1-3 day).
- All changes are merged back into ``main`` after passing CI.
- No long-lived feature branches.
- Feature flags may be used for incomplete or experimental features.

This encourages rapid integration, reduces merge conflicts, and supports continuous delivery.

Code Style and Standards
------------------------

Python Version
~~~~~~~~~~~~~~

GOATS requires **Python 3.12**. All code must be compatible with this version. This is dictated by DRAGONS.

Docstring Style
~~~~~~~~~~~~~~~

- Follow the `numpydoc <https://numpydoc.readthedocs.io/en/latest/format.html>`_ style guide for all public modules, classes, functions, and methods.
- Docstring content is validated using ``numpydoc`` checks, configured in ``pyproject.toml``.

Formatting
~~~~~~~~~~

GOATS uses `Ruff <https://docs.astral.sh/ruff/>`_ for both linting and formatting.

To format and lint code manually:

.. code-block:: bash

   ruff check .
   ruff format .

Excluded Paths
~~~~~~~~~~~~~~

Certain directories are excluded from linting and formatting.

These exclusions are defined in ``pyproject.toml`` under ``[tool.ruff]``.

``numpydoc`` also excludes private methods and ``__init__`` definitions from required docstring validation.


Pre-commit Hooks
----------------

GOATS uses pre-commit hooks to ensure consistent code quality and prevent common mistakes before commits are made.

Set Up ``pre-commit``
~~~~~~~~~~~~~~~~~~~~~

Install ``pre-commit`` using ``uv``:

.. code-block:: bash

   uv tool install pre-commit --with pre-commit-uv

.. note::

   You may be prompted to add ``~/.local/bin`` to your ``PATH``. ``uv`` installs tools there by default.

Install the hooks defined in ``.pre-commit-config.yaml``:

.. code-block:: bash

   pre-commit install

Once installed, ``pre-commit`` will automatically run the configured hooks each time you commit changes.

This helps catch formatting issues, docstring violations, and other problems before code is committed.

Hook Summary
~~~~~~~~~~~~

The following hooks are enabled in ``.pre-commit-config.yaml``:

- ``ruff-check``: Runs Ruff linter on Python files.
- ``ruff-format``: Formats code using Ruff's formatter.
- ``trailing-whitespace``: Removes trailing whitespace.
- ``end-of-file-fixer``: Ensures files end with a single newline.
- ``name-tests-test``: Enforces ``test_`` prefix for test functions.
- ``no-commit-to-branch``: Blocks commits directly to the ``main`` branch.
- ``check-yaml``: Validates YAML files.
- ``check-json``: Validates JSON files.
- ``check-toml``: Validates TOML files.
- ``check-docstring-first``: Ensures first statement is a docstring.
- ``check-case-conflict``: Detects filename case conflicts.
- ``pretty-format-json``: Reformats JSON files with consistent indentation.
- ``debug-statements``: Blocks committed ``print()``.
- ``detect-private-key``: Prevents committing private keys.
- ``forbid-submodules``: Disallows Git submodules.
- ``uv-lock``: Ensures ``uv``-managed lockfile stays updated.

Notes
~~~~~

- Hooks are configured in ``.pre-commit-config.yaml``.
- Some hooks exclude files in ``docs/``, ``migrations/``, ``static/``, or ``templates/``.
- Run all hooks manually:

  .. code-block:: bash

     pre-commit run --all-files

- Update hook versions:

  .. code-block:: bash

     pre-commit autoupdate

Changelog Management
--------------------

GOATS uses `towncrier <https://towncrier.readthedocs.io/>`_ to manage release changelogs from structured news fragments.

Writing News Fragments
~~~~~~~~~~~~~~~~~~~~~~

Each pull request should include a news fragment saved to ``doc/changes`` using the naming format ``<PR number>.<type>.rst``. Supported types:

- ``new`` - new feature
- ``bugfix`` - bug fix
- ``change`` - behavior change
- ``perf`` - performance improvement
- ``doc`` - documentation
- ``other`` - miscellaneous

Example: ``42.bugfix.rst``

Best practices:

- Use the Jira ticket title as a starting point.
- Write in past tense, using active voice.
- Keep it short and user-facing.
- Use one file per PR; update as needed.

Previewing and Building
~~~~~~~~~~~~~~~~~~~~~~~

- Preview changes:

  .. code-block:: bash

     towncrier build --draft

.. note::

   Building and appending the changelog is automatically handled by the ``Build Release`` GitHub workflow.