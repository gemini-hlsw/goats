Environment Setup
=================

This page describes how to install the GOATS package and set up its development environment using Conda and ``uv``.

Requirements
------------

- Miniforge for Conda (preferred): https://conda-forge.org/download/
- Git

Installation Instructions
-------------------------

1. **Clone the repository**:

   .. code-block:: bash

      git clone https://github.com/gemini-hlsw/goats.git
      cd goats

2. **Create the Conda environment**:

   .. code-block:: bash

      conda env create -f ci_environment.yaml -n goats-env
      conda activate goats-env

   .. note::

      On Apple Silicon systems (e.g., M1, M2), the ``--platform osx-64`` flag is required to ensure compatibility with packages that do not support ``arm64``.

3. **Install the Python dependencies**:

   .. code-block:: bash

      uv pip install -e . --group dev --group notebook --group docs

   This installs the package in editable mode and includes development, notebook, and documentation dependencies.

   To install only a subset of the dependencies, omit the groups that are not required:

   .. code-block:: bash

      uv pip install -e . --group dev

You're now ready to develop and run the GOATS application locally.

Additional Notes
----------------

- The ``ci_environment.yaml`` file defines a stable environment using only ``conda-forge`` packages.
- ``uv`` is installed as part of the environment and is used to manage Python dependencies.
- Dependency groups are defined under ``[dependency-groups]`` in ``pyproject.toml``.