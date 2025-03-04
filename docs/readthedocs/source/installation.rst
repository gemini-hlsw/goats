.. installation.rst

.. _install:

Installation
============

Upon beta release, GOATS will be distributed as a conda package. 


System Requirements
-------------------
* Python 3.10 or higher
* Conda 

We recommend using **Miniforge** for conda. However, if you already have Miniconda or Anaconda installed, those will work as well.  

To install Miniforge, follow the instructions `here <https://conda-forge.org/download/>`_. Download the appropriate installer for your system, then open a terminal and run the following:

.. code-block:: console

   $ bash Miniforge3-$(uname)-$(uname -m).sh

(``$`` indicates the terminal prompt)

Replace `Miniforge3-$(uname)-$(uname -m).sh` with the actual file name you downloaded.  

We recommend **manual initialization of conda**. When prompted with:

``Do you wish to update your shell profile to automatically initialize conda?``  

answer **no**. After installation completes, run the following commands to manually initialize conda and verify the installation:

.. code-block:: console

   $ ~/miniforge3/bin/conda init
   $ which conda

Ensure that `miniforge3` appears in the output of `which conda`.  



Workaround for ARM (M1/M2) Mac Users
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
If you’re using an Apple M1 or M2 system, follow these steps to ensure compatibility:  

1. Ensure `Rosetta 2` is installed to run Intel-based binaries. You can install it using:  

   .. code-block:: console

      $ softwareupdate --install-rosetta

2. Install an x86 version of Miniforge.

3. Use an x86 terminal for installing and running Intel-only packages like *DRAGONS*. To start an x86 terminal on ``zsh``, run:

   .. code-block:: console

      $ arch -x86_64 zsh


Switching Back to Default ARM Architecture
------------------------------------------

Once you’re done with x86 tasks, you can switch back to macOS's default ARM architecture. Simply close the x86 terminal and open a new terminal window. The new terminal will default to ARM.

To confirm your current architecture, run:

.. code-block:: console

   $ uname -m

If the output is `arm64`, your terminal is running in ARM mode.

Alternatively, if you want to switch back to ARM without closing the terminal, run:

.. code-block:: console

   $ arch -arm64 zsh

This will start a new shell session in ARM mode.


Install GOATS
-------------

For alpha-testing GOATS, create a conda environment using the `environment.yaml` file included in the circulated email. 

.. code-block:: console

   $ conda env create -f environment.yml
   
.. note::
   By the time of the beta release, GOATS will be available as a conda package and users will not need to work with a yaml file.   

Activate the conda environment just created.

.. code-block:: console

   $ conda activate goats

This environment contains the ``goats`` Command Line Interface (CLI), which you can use to spin up your own GOATS project/interface, as shown below. 

.. code-block:: console

   $ goats install
   $ goats run

When executing ``goats install``, you will be prompted to create a username and password, which you will use to log into your GOATS interface. 

The installation step will create a folder named **GOATS** in your current directory; you can specify a different parent directory by using the ``-d`` flag (see :ref:`goats_cli`). 

To close your GOATS interface, simply press ``Ctrl+C`` in the terminal. 

.. note::
   To open your GOATS interface the next time, you will only need to execute ``goats run -d /your/parent/directory/of/GOATS`` in the terminal (within the conda environment you created for GOATS). 

For more details on the CLI, see :ref:`goats_cli`.

