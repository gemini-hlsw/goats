.. _conda_forge_maintenance:

``conda-forge`` Maintenance
===========================

The end goal of **GOATS** is eventual distribution as a `conda-forge <https://conda-forge.org>`_ package.
To achieve this, all dependencies must first be available on ``conda-forge``.

As part of this process, the GOATS project contributes to the broader Python astronomy ecosystem by maintaining and co-maintaining
several ``conda-forge`` feedstocks.

Currently, the project maintains:

- 5 ``conda-forge`` packages with sole maintainership,
- 2 ``conda-forge`` packages with shared maintainership, and
- 1 package (*DRAGONS*) that is awaiting ``conda-forge`` support and currently prevents full inclusion of GOATS on ``conda-forge``.

Sole-Maintained Packages
------------------------

Feedstocks fully maintained under the GOATS organization:

- `django-bootstrap4 <https://github.com/conda-forge/django-bootstrap4-feedstock>`_
- `dramatiq-abort <https://github.com/conda-forge/dramatiq-abort-feedstock>`_
- `django-dramatiq <https://github.com/conda-forge/django-dramatiq-feedstock>`_
- `marshmallow-jsonapi <https://github.com/conda-forge/marshmallow-jsonapi-feedstock>`_
- `gpp-client <https://github.com/conda-forge/gpp-client-feedstock>`_

.. note::
    Feedstock repositories are automatically created and hosted under the conda-forge GitHub organization.
    Changes to recipes are submitted as pull requests to these repositories (for example, django-dramatiq-feedstock).

Co-Maintained Packages
----------------------

Feedstocks with shared maintainership:

- `tomtoolkit <https://github.com/conda-forge/tomtoolkit-feedstock>`_
- `tom-tns <https://github.com/conda-forge/tom-tns-feedstock>`_

The TOMToolkit team typically manages releases and feedstock updates for these packages.
If a release requires attention or coordination, contact with the TOMToolkit maintainers is recommended.

Pending Packages
----------------

The remaining dependency that currently prevents GOATS from becoming a fully supported ``conda-forge`` package is **DRAGONS**
and its related sub-dependencies:

- `DRAGONS <https://github.com/GeminiDRSoftware/DRAGONS>`_

During recent meetings, it was discussed that DRAGONS is being considered for addition to ``conda-forge``.
This topic will be revisited following the release of version **4.1.0**.

Tracking and Coordination
--------------------------

All work related to maintaining and supporting the ``conda-forge`` effort for GOATS is organized under the **Epic GOATS-952: conda-forge Maintenance**.  
Issues, tasks, and subtickets related to feedstock updates, ``conda`` maintenance, or package onboarding
should be created under this epic.

.. note::
    All new issues or updates related to any feedstock should be logged as subtasks under **GOATS-952** in Jira.

Maintaining a ``conda-forge`` Feedstock
---------------------------------------

The official ``conda-forge`` `maintainer documentation <https://conda-forge.org/docs/maintainer/>`_ provides the authoritative
reference for feedstock maintenance and update procedures.

.. note::
   To perform any maintenance actions on a ``conda-forge`` feedstock—such as merging pull requests,
   rerendering recipes, or triggering rebuilds—the maintainer must first be listed in the
   ``recipe-maintainers`` section of the feedstock's ``meta.yaml`` file.  

When a new release of a maintained package is published, ``conda-forge`` automation tags maintainers on the corresponding pull request
in the feedstock repository. Responsibilities include:

1. Reviewing the tagged pull request and verifying that the upstream release matches the feedstock version and metadata.
2. Confirming that dependency versions are correct and compatible.
3. Ensuring that continuous integration builds (Linux, macOS, Windows) complete successfully.
4. Merging the pull request once all checks have passed.

In most cases, dependencies remain stable between releases.
When upstream dependencies change, the ``meta.yaml`` recipe must be updated accordingly, local builds verified if necessary,
and tests confirmed to pass before merging.

.. note::
    When troubleshooting CI build failures, check the conda-forge build logs for each platform (Linux, macOS, Windows).
    These logs often indicate missing dependencies, version mismatches, or syntax issues in meta.yaml.

Internal Package Hosting
------------------------

Because GOATS cannot currently be distributed through ``conda-forge`` until all dependencies
are supported there, an internal build and hosting mechanism is used
to maintain package availability.

All internal builds are managed through the `goats-infra <https://github.com/gemini-hlsw/goats-infra>`_
repository.  This repository contains the build recipes, GitHub Actions workflows, and configuration
for producing and publishing GOATS and related packages as Conda artifacts.

Completed builds are automatically published to the `goats-infra GitHub Pages Conda channel <https://gemini-hlsw.github.io/goats-infra/conda/>`_.

This channel is configured as a Conda repository and can be added to a local environment with:

.. code-block:: bash

   conda config --add channels https://gemini-hlsw.github.io/goats-infra/conda/

This workflow ensures that GOATS and its ecosystem can continue to be installed, tested, and deployed
while work toward full ``conda-forge`` inclusion is ongoing.
