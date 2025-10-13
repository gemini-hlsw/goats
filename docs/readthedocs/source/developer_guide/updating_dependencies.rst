Updating Dependencies
=====================

GOATS uses **Dependabot** to automatically check for dependency updates.  
Dependabot is a GitHub-native automation tool that monitors dependency files
(e.g., ``pyproject.toml`` and ``uv.lock``) and creates pull requests
(PRs) when new versions of packages are available.

A dedicated GitHub Action groups dependency updates into five categories:

- ``dependencies``
- ``development-dependencies``
- ``documentation-dependencies``
- ``notebook-dependencies``
- ``github-actions``

Dependabot runs **weekly** and creates PRs every **Monday** with any available updates.

GOATS is an application and not a library depended upon by others, so its
dependencies should be kept as current as possible.  
Updates must be performed carefully because GOATS relies on both **DRAGONS** and **TOMToolkit**,  
and all dependencies must be available on **conda-forge**.

Before approving or merging any update:

1. Verify that the new release is available on ``conda-forge`` or that it can be published there if maintained internally.  
   (See the upcoming section *"Conda-Forge Maintenance"* for details.)
2. Confirm that **DRAGONS** and **TOMToolkit** support the proposed versions.  
   DRAGONS, for example, depends on specific ``astropy`` versions.

Dependency Categories
---------------------

``dependencies``
^^^^^^^^^^^^^^^^
These are the **core runtime dependencies** for GOATS and must all be available on ``conda-forge``.

- Require the most careful review and testing.
- Review release notes and changelogs before merging.
- Test both the web application and the CLI components.
- Run the full test suite with ``pytest``.
- Proceed cautiously to maintain compatibility with DRAGONS and TOMToolkit.
- TOMToolkit updates may alter templates or static assets, so the UI should be checked thoroughly.

``development-dependencies``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Used for local and CI development tools (e.g., linters, formatters, test utilities).

- Generally safe and simple to update.
- Run the full test suite with ``pytest`` after updating.
- These dependencies **do not need to be on conda-forge**.

``documentation-dependencies``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Used by **ReadTheDocs** to build project documentation.

- Follow the same process as development dependencies.
- Typically low-risk and can be merged after confirming the documentation builds successfully.

``notebook-dependencies``
^^^^^^^^^^^^^^^^^^^^^^^^^
Used only for running and testing local Jupyter notebooks.

- Can be updated immediately.
- Require minimal testing.

``github-actions``
^^^^^^^^^^^^^^^^^^
Used to keep the **GitHub Actions workflows** up to date.  
Dependabot will check for new versions of actions defined in the repository's workflow files.

- These updates do **not** modify ``pyproject.toml`` or ``uv.lock``.
- Dependabot manages these PRs automatically.
- Validate the affected workflow if possible to confirm it still functions as expected.
- If the action cannot easily be tested (e.g., publishing or deployment workflows),  
  assume it will continue to function correctly until the next applicable run.

How to Update
-------------
1. Dependabot opens pull requests every Monday for detected updates.
2. For each PR:

  - Create a **Jira ticket** under the Epic **GOATS-732 - Dependabot Updates**.
  - Use the PR title as the Jira story title.
  - If the PR title is too generic (e.g., "Bump dependencies"), append version details (e.g., *"Update astropy to 6.0.2"*).

3. Add the ticket to the **current sprint**.

.. note::
   ``github-actions`` updates do **not** require any further steps beyond ticket creation and review. These updates do not modify ``pyproject.toml`` or ``uv.lock`` and are handled entirely by Dependabot. 

Pull the pull request locally. Dependabot updates the ``uv.lock`` file but not ``pyproject.toml``.  
This file must therefore be updated manually most of the time. For example, for a PR titled  
*Bump ruff from 0.13.1 to 0.13.3 in the development-dependencies group*:

.. code-block:: bash

   gh pr checkout 436

Then update the ``pyproject.toml`` file to match the ``uv.lock`` file by running:

.. code-block:: bash

   uv add --dev "ruff>=0.13.3"

.. note::
   - ``--dev`` specifies the **development** group.  
   - For other groups such as documentation, use ``--group docs``.  
   - The main ``dependencies`` group does **not** require ``--dev`` or ``--group``.  
   - Use ``>=`` for flexible version ranges and ``==`` when pinning exact versions.  

Commit and push the change:

.. code-block:: bash

   git add .
   git commit -m "GOATS-<ISSUE_NUMBER>: Update pyproject.toml."
   git push

GitHub Actions automatically run when ``pyproject.toml`` changes, triggering the test suite via ``pytest``.  
After all tests pass, the PR can be squash merged and linked to the corresponding Jira ticket.

.. note::
   A Towncrier entry is **not required** for dependency updates.

Testing Locally
---------------
To verify dependency updates before pushing, install GOATS in editable mode with development dependencies:

.. code-block:: bash

   uv pip install -e . --dev

Run the full test suite to confirm that all functionality remains stable:

.. code-block:: bash

   pytest


.. note::
   Local execution should always be tested after updating major dependencies such as  
   ``django``, ``tomtoolkit``, or ``dragons`` to confirm that no runtime or import errors occur prior to merging.