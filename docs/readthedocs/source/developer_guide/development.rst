Developer Guide
===============

This page documents how to maintain and develop GOATS.

Overview
--------

GOATS uses `uv <https://github.com/astral-sh/uv>`_ and Conda to manage dependencies and execute scripts.

Set Up ``pre-commit``
---------------------

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

To manually run all hooks on the entire codebase:

.. code-block:: bash

   pre-commit run --all-files
