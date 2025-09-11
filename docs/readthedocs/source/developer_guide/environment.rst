Environment Setup
=================

GOATS must be installed using **both Conda and uv**. Some dependencies, like ``redis-server`` and ``dragons``, are only available on Conda, while Python packages are managed using `uv <https://docs.astral.sh/uv/>`_.

Requirements
------------

- Conda (Miniforge recommended)
- `uv <https://docs.astral.sh/uv/>`_
- Python 3.12 (managed by Conda)
- Git


Installing Miniforge
--------------------

To install Miniforge, `download the appropriate installer for your system <https://conda-forge.org/download/>`_ and follow the instructions :ref:`Installing Miniforge <installing_miniforge>`.

Set Up the Conda Environment
----------------------------

GOATS provides a pre-configured environment file: ``ci_environment.yaml``.

.. code-block:: bash

   git clone https://github.com/gemini-hlsw/goats.git
   cd goats

   # For Intel/macOS/Linux.
   conda env create -f ci_environment.yaml

   # For Apple Silicon (M1/M2), use the x86_64 platform.
   conda env create -f ci_environment.yaml --platform osx-64

Activate the environment:

.. code-block:: bash

   conda activate goats-dev

Install GOATS Using ``uv``
--------------------------

Once the Conda environment is active, use ``uv`` to install Python packages in editable mode.

Install all development, notebook, and documentation dependencies:

.. code-block:: bash

   uv pip install -e . --group dev --group notebook --group docs

Or, if you only need core dependencies:

.. code-block:: bash

   uv pip install -e . --group dev

This installs:

- The GOATS package in development mode (changes reflect instantly).
- Python development tools like pytest, Ruff, Sphinx, etc..
- Optional support for Jupyter notebooks.
- Optional documentation libaries for building documentation locally.