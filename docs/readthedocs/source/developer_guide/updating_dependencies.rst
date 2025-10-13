Updating Dependencies
=====================

Overview
--------
GOATS uses **Dependabot** to automatically check for dependency updates.  
Dependabot is a GitHub-native automation tool that monitors your dependency files
(e.g., ``pyproject.toml`` and ``uv.lock``) and creates pull requests
(PRs) when new versions of packages are available.

For GOATS, a dedicated GitHub Action groups dependency updates into four categories:

- ``dependencies``
- ``development-dependencies``
- ``documentation-dependencies``
- ``notebook-dependencies``

Dependabot runs **weekly** and will create PRs every **Monday** with any available updates.

Because GOATS is an application (and not a library that others depend on),
we aim to keep dependencies up to date.  
However, we must be careful since GOATS depends on both **DRAGONS** and **TOMToolkit**,  
and all dependencies must be available on **conda-forge**.

Before approving or merging any update:

1. Verify that the new release is available on ``conda-forge`` or that you are the maintainer of the package and can ensure its availability.  
   (See the upcoming section *"Conda-Forge Maintenance"* for details.)
2. Confirm that **DRAGONS** and **TOMToolkit** support the proposed versions.  
   DRAGONS, for example, is sensitive to specific ``astropy`` versions.

Dependency Categories
---------------------

``dependencies``
^^^^^^^^^^^^^^^^
These are the **core runtime dependencies** for GOATS.  
They must all be available on ``conda-forge``.

- These updates are the trickiest and require **thorough testing**.
- Read the changelogs carefully before merging.
- Test both the web application and the CLI components.
- Run the full test suite with ``pytest``.
- Update slowly and cautiously to avoid breaking compatibility with DRAGONS or TOMToolkit.
- TOMToolkit updates will update templates and static assets, so check the UI carefully.

``development-dependencies``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Used for local and CI development tools (e.g., linters, formatters, test utilities).

- Easy to update.
- Simply update the PR and run the full test suite with ``pytest``.
- These packages **do not need to be on conda-forge**.

``documentation-dependencies``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Used by **ReadTheDocs** to build the documentation.

- Same process as development dependencies.
- Updates are generally low-risk and can be merged after a quick docs build check.

``notebook-dependencies``
^^^^^^^^^^^^^^^^^^^^^^^^^
Used only for running and testing local Jupyter notebooks.

- Safe to update immediately.
- Minimal testing required.

How to Update
-------------
1. Dependabot will open pull requests every Monday for detected updates.
2. For each PR:
   - Create a **Jira ticket** under the Epic **GOATS-732 - Dependabot Updates**.
   - Use the PR title as the Jira story title.
   - If the PR title is too generic (e.g., "Bump dependencies"),  
     append version details (e.g., *"Update astropy to 6.0.2"*).
3. Add the ticket to the **current sprint**.

Pull the pull request locally. In the current development with uv, which is the package manager we use, the ``uv.lock`` file is updated, however, the ``pyproject.toml`` file is not updated and we must update that. For example we will use a PR titled: *Bump ruff from 0.13.1 to 0.13.3 in the development-dependencies group.*

We will pull it locally:

.. code-block:: bash

   gh pr checkout 436

Then I will update the ``pyproject.toml`` file to match the ``uv.lock`` file by running the command:

.. code-block:: bash

   uv add --dev "ruff>=0.13.3"

.. note::
   - ``--dev`` specifies the **development** group.  
   - For other groups such as documentation, use ``--group docs``.  
   - For the main ``dependencies`` group, you do **not** need to specify ``--dev`` or ``--group``.  
   - Use ``>=`` for flexible version ranges and ``==`` when pinning exact versions.  
     - For example, ``gpp-client`` should be pinned using ``==``.

Then we do:

.. code-block:: bash

   git add .
   git commit -m "GOATS-<ISSUE_NUMBER>: Update pyproject.toml."
   git push

GitHub Actions should run automatically since the ``pyproject.toml`` file changed and ``pytest`` should run. After the tests pass, it should be good to squash and merge. Then link the PR to the ticket.

.. note::
   You do **not** need to add a Towncrier entry for dependency updates.

Testing Locally
---------------
To verify dependency updates locally before pushing, install GOATS in editable mode with development dependencies:

.. code-block:: bash

   uv pip install -e . --dev

Then run the full test suite:

.. code-block:: bash

   pytest

If the update affects runtime dependencies or UI components, start the application locally to ensure it loads correctly.

.. note::
   Always test local execution after updating major dependencies (e.g., ``django``, ``tomtoolkit``, or ``dragons``)  
   to confirm that no runtime or import errors occur before merging.