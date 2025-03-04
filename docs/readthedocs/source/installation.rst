.. installation.rst

.. _install:

############
Installation
############

GOATS is designed to be run **locally**. As of now, there are no plans for a dedicated central server hosting GOATS. All installations should be performed on your local machine following the steps outlined below.

System Requirements
===================

* Python 3.10 or higher
* Conda (Miniforge)
* Supported Operating Systems:

  - Linux
  - macOS (Intel & ARM)
  - Windows with WSL (Windows Subsystem for Linux)
* Supported Browsers:

  - Chrome
  - Chromium-based browsers
  - Firefox

.. note::

   If you already have Anaconda or Miniconda installed, then you can go directly to the :ref:`Installing GOATS <installing_goats>` section below. 
  
   Otherwise we recommend installing Miniforge. Miniforge defaults to using the community-driven **Conda-Forge** repository, which provides more up-to-date and widely maintained packages. Additionally, Anaconda/Miniconda enforces licensing restrictions for commercial use. Miniforge does not have such restrictions, thus making it a more flexible and widely accepted alternative.

.. _installing_miniforge:

Installing Miniforge
====================

To install Miniforge, `download the appropriate installer for your system <https://conda-forge.org/download/>`_ and follow the instructions below.

**Choose the correct installer for your system:**

+--------------------------+--------------------------------------------------+
| **Operating System**     | **Installation Command**                         |
+==========================+==================================================+
| **Linux**                | ``$ sh Miniforge3-Linux-x86_64.sh``              |
+--------------------------+--------------------------------------------------+
| **macOS (Intel)**        | ``$ sh Miniforge3-MacOSX-x86_64.sh``             |
+--------------------------+--------------------------------------------------+
| **macOS (M1/M2 ARM)**    | ``$ sh Miniforge3-MacOSX-arm64.sh``              |
+--------------------------+--------------------------------------------------+
| **Windows (WSL)**        | See :ref:`Windows with WSL <installing_wsl>`     |
+--------------------------+--------------------------------------------------+

After downloading the installer, open a terminal and run the command specific to your platform.

We recommend **manual initialization of conda**. When prompted with:

``Do you wish to update your shell profile to automatically initialize conda?``

answer **no**. After installation completes, manually initialize conda for your preferred shell:

.. code-block:: console

   $ ~/miniforge3/bin/conda init <shell>

Replace ``<shell>`` with your shell of choice (e.g., ``bash``, ``zsh``, ``fish``).

To verify the installation, run:

.. code-block:: console

   $ which conda

Ensure that `miniforge3` appears in the output of `which conda`.

.. _installing_goats:

Installing GOATS
================

Follow the steps below to install GOATS across all supported platforms.

1. Create the GOATS conda environment:

   .. code-block:: console

      $ conda create -n goats-env python=3.10 goats -c https://gemini-hlsw.github.io/goats/conda

   .. note::
      If the environment creation fails, it may be due to an outdated version of Conda. 
      Upgrade to the latest version. If issues persist, consider reinstalling Conda by installing ``Miniforge`` as described :ref:`above <installing_miniforge>`.

2. Activate the conda environment:

   .. code-block:: console

      $ conda activate goats-env

3. Install and run GOATS:

   .. code-block:: console

      $ goats install
      $ goats run

   .. note::
      For more details on the ``goats`` command, see :ref:`goats_cli`.

   When executing ``goats install``, you will be prompted to create a username and password, which you will use to log into your GOATS interface.

   The installation step will create a folder named **GOATS** in your current directory; you can specify a different parent directory by using the ``-d`` flag (see :ref:`goats_cli`).

4. To close your GOATS interface, simply press ``Ctrl+C`` in the terminal.

   .. note::
      To open your GOATS interface the next time, execute:

      .. code-block:: console

         $ goats run -d /your/parent/directory/of/GOATS

      within the conda environment you created for GOATS.

5. When you are finished using GOATS, **deactivate the conda environment** by running:

   .. code-block:: console

      $ conda deactivate


Platform-Specific Notes
=======================

.. _installing_wsl:

Windows with WSL
----------------

GOATS **does not support native Windows installations** but can be run through **WSL (Windows Subsystem for Linux)**. To install WSL, `follow the official tutorial <https://learn.microsoft.com/en-us/windows/wsl/install>`_.

Once WSL is installed, follow the Linux Miniforge installation instructions from :ref:`installing_miniforge` and proceed with :ref:`installing_goats`.

.. _installing_macos_arm:

Running GOATS on macOS (M1/M2 ARM)
----------------------------------

Currently, DRAGONS (one of the dependencies of GOATS) does not support macOS ARM architecture. To ensure compatibility, use the ARM version of Miniforge but include the ``--platform osx-64`` flag when creating the environment:

.. code-block:: console

   $ conda create --platform osx-64 -n goats-env python=3.10 goats -c https://gemini-hlsw.github.io/goats/conda

This ensures that dependencies are installed in a way that maintains compatibility with required packages.

Once the environment is created and activated, install and run GOATS normally:

.. code-block:: console

   $ goats install
   $ goats run

Since the entire Conda environment is running under ``osx-64``, GOATS will always execute in ``x86`` mode automatically.



