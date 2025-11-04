.. _updating:

Updating
========

This guide explains how to update GOATS to the latest version.  
The update process is simple and takes just a few minutes.

.. note::

   GOATS must be updated using **Conda**, which manages all environment and dependency changes.  
   Do **not** attempt to update GOATS using ``pip`` or by manually replacing files.

Update Procedure
----------------

Follow these steps to safely update GOATS:

1. **Stop GOATS**

   Make sure GOATS is not running before updating.

   - If it is running in the foreground, press ``Ctrl + C`` to stop it.
   - If running in the background (e.g., as a service or in Docker), stop it using the appropriate method.

2. **Update GOATS using Conda**

   Run the following command to update GOATS and its dependencies:

   .. code-block:: bash

      conda update goats

   Conda will automatically update GOATS and manage any required dependency changes.

3. **Restart GOATS**

   After the update completes, restart GOATS:

   .. code-block:: bash

      goats run

   On startup, GOATS will automatically apply any necessary internal updates to ensure your installation is fully synchronized.

Automatic Version Check
-----------------------

GOATS checks for newer versions every time you run ``goats run``. If your version is outdated, a warning like the following will appear:

.. code-block:: text

   A new version of GOATS is available: 25.11.0 (current: 25.10.1)

   GOATS interacts with several external services (e.g., GPP, GOA, TNS)
       which may evolve over time. Using an outdated version can result in
       unexpected behavior or failed operations due to API changes or
       incompatible features.

   ➤ Visit https://goats.readthedocs.io/en/latest/updating/ for update instructions

   Press Enter to continue at your own risk, or Ctrl+C to cancel...

If your version is current, GOATS will confirm:

.. code-block:: text

   GOATS is up to date (version 25.11.0). No update necessary.

Verification
------------

After restarting, verify the update with:

.. code-block:: bash

   goats --version

You should see the updated version number displayed.