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

2. Run the release SHA script to retrieve the version and checksum:

   .. code-block:: bash

      python get_release_sha.py

3. Open ``goats-feedstock/recipe/meta.yaml`` and update:

   - ``{% set version - "..." %}`` to the release version.
   - ``source.sha256`` to the generated SHA256 value.

4. Commit and push the changes:

   .. code-block:: bash

      git add .
      git commit -m "Update version to VERSION"
      git push origin main

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