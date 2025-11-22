Deployment How-To
=================

This guide describes how to create a GOATS release, build Conda packages, and publish them for installation via GitHub Pages.

Release Strategy
----------------

GOATS uses **CalVer** (calendar versioning), since it is an application that depends on evolving external systems. We prioritize compatibility with current systems rather than strict backward compatibility with older versions of GOATS.

Version Format
^^^^^^^^^^^^^^

- Format: ``YY.MM.PATCH`` (e.g., ``25.6.0`` for the first release of June 2025)
- Add ``rcN`` suffix for release candidates (e.g., ``25.6.0rc1``)
- Increment the patch version for subsequent releases within the same month (e.g., ``27.12.4``)

Creating a GitHub Release
-------------------------

1. **Choose a tag version** to release (see version format above).
2. Navigate to the `GOATS GitHub repository <https://github.com/gemini-hlsw/goats>`_.
3. Click the **Actions** tab.
4. Find the **Build Release** workflow and click it.
5. Click the **Run Workflow** button.
6. Fill out the version tag and any other required fields, then click **Run Workflow**.

The release will be created automatically in a few minutes, along with release notes and a GitHub release tag.

Preparing Conda Feedstock
-------------------------

1. Clone the ``goats-infra`` repository:

   .. code-block:: bash

      git clone https://github.com/gemini-hlsw/goats-infra.git
      cd goats-infra

2. Run the script to update the version and checksum:

   .. code-block:: bash

      python update_release_sha.py

3.  Open ``goats-feedstock/recipe/meta.yaml`` and update:

   - The ``version`` and ``sha256`` fields will be updated automatically by the script.
   - Dependencies under ``host:`` and ``run:`` to reflect any new or removed packages:

     - Use the ``pyproject.toml`` from the GOATS project version being released to determine the correct dependencies.
     - Add new dependencies if needed.
     - Remove outdated dependencies.
     - Update versions for any changed libraries.


4.  Commit and push the changes:

   .. code-block:: bash

      git add .
      git commit -m "Update version to VERSION"
      git push origin main

Verifying New or Changed Dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you add or update a dependency in ``meta.yaml``, you must:

- **Verify the dependency exists on conda-forge.**
- **Check the correct package name**, as it may differ from the PyPI name.).
- **If the package is missing or out-of-date**, you are responsible for:

  - Submitting a pull request to the appropriate ``feedstock`` on conda-forge to update the package.
  - Or, if it's a new package, submitting a new ``feedstock`` PR following conda-forge's guidelines.

Be cautious when adding new dependencies, as this can delay the release process significantly.

Building Conda Packages
-----------------------

1. Go to the ``goats-infra`` `Actions page <https://github.com/gemini-hlsw/goats-infra/actions>`_.
2. Select the **Conda Build** workflow.
3. Click **Run Workflow** and wait for the job to finish.

Publish to Custom Conda Channel
-------------------------------

After the Conda Build workflow completes, a pull request will be created automatically on ``goats-infra`` with the title:

.. code-block:: bash

   Publish goats-VERSION to Conda.

1.	Review the pull request and ensure the build artifacts and metadata look correct.
2.	Once you're satisfied, approve and merge the PR into the main branch.
3.	After merging, GitHub Pages will automatically deploy the updated Conda channel.

Confirming the Package Availability
-----------------------------------

Run the following command to ensure the package has been published successfully:

.. code-block:: bash

   conda search -c https://gemini-hlsw.github.io/goats-infra/conda goats

Walkthrough: Publishing GOATS 25.11.3
-------------------------------------

This walkthrough documents the process used to publish version ``25.11.3`` of GOATS.

1. **Created the GitHub release**:

   - Navigated to the `goats` repo → **Actions** → **Build Release**
   - Clicked **Run Workflow**
   - Entered tag: ``25.11.3`` and ran the workflow
   - Waited ~3 minutes for the workflow to complete and the release to be published

2. **Cloned the ``goats-infra`` repository**:

   .. code-block:: bash

      git clone https://github.com/gemini-hlsw/goats-infra.git
      cd goats-infra

3. **Update the SHA256 and version from the GitHub release**:

   .. code-block:: bash

      python update_release_sha.py

   - This updates the ``version`` and the release ``sha256``.

4. **Updated the feedstock metadata**:

   - Edited ``goats-feedstock/recipe/meta.yaml``:

     - The script updates the ``version`` and ``sha256`` automatically.
     - Verified all ``host:`` and ``run:`` dependencies against the ``pyproject.toml`` of the release.

   .. figure:: _images/25.11.3-diff.png
      :alt: Diff of meta.yaml for version 25.11.3 
      :align: center
      :scale: 100%

      Diff of ``meta.yaml`` showing the version and SHA256 updates for ``25.11.3``. No changes to dependencies were needed.

5. **Committed and pushed the update**:

   .. code-block:: bash

      git add goats-feedstock/recipe/meta.yaml
      git commit -m "Update version to 25.11.3."
      git push origin main

6. **Updated gpp-client on conda-forge**:

   The GOATS 25.11.3 release depends on an updated version of ``gpp-client``.

   - PR submitted to conda-forge feedstock:

     - https://github.com/conda-forge/gpp-client-feedstock/pull/19

   - This PR:

     - Updated the version of ``gpp-client`` to match GOATS needs.
     - Bumped dependencies: ``typer`` and ``websockets``.
     - Verified SHA256 and build via conda-forge CI.

   .. figure:: _images/gpp-client-diff.png
      :alt: Diff of meta.yaml for gpp-client 
      :align: center
      :scale: 100%

   - The bot auto-generated the version and checksum.
   - After CI passed, the PR was approved and merged.
   - The new package was published to conda-forge.

7. **Updated ``tomtoolkit`` on conda-forge**:

   The GOATS 25.11.3 release depends on ``tomtoolkit==2.26.2``.

   - PR submitted to conda-forge feedstock:

     - https://github.com/conda-forge/tomtoolkit-feedstock/pull/18

   - This PR:

     - Updated the version of ``tomtoolkit`` to ``2.26.2``.
     - Verified SHA256 and build via conda-forge CI.

   .. figure:: _images/tomtoolkit-diff.png
      :alt: Diff of meta.yaml for tomtoolkit 
      :align: center
      :scale: 100%

   - The bot auto-generated the version and checksum.
   - After CI passed, the PR was approved and merged.
   - The new package was published to conda-forge.

8. **Ran the Conda Build workflow**:

   - Returned to ``goats-infra`` GitHub → **Actions** → **Conda Build**
   - Clicked **Run Workflow**
   - Waited ~15 minutes for the build to complete

9. **Merged the publish PR**:

   - GitHub automatically opened a PR titled ``Publish goats-25.11.3 to Conda.``

     - https://github.com/gemini-hlsw/goats-infra/pull/9

   - Reviewed the PR and confirmed the correct version and packages
   - Merged the PR into ``main``, which triggered GitHub Pages to deploy the updated Conda channel

10. **Verified package installation and functionality**:

   - Created a clean test environment:

     .. code-block:: bash

        conda create -n goats-25.11.3 goats
        conda activate goats-25.11.3

   - Verified the installation with:

     .. code-block:: bash

        goats --help