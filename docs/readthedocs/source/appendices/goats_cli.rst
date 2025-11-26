.. _goats_cli:

GOATS Command Line Interface
============================

The GOATS CLI provides everything you need to install a new GOATS project and run
it locally. All commands support ``--help`` and display clear, colorized output.
The screenshots below show exactly what users will see.

``goats``
---------

.. image:: images/cli-goats.png
   :alt: GOATS CLI main help output
   :align: center

Running ``goats`` with no arguments lists the available commands and options.
From here, users can install a new GOATS project or start an existing one.

``goats --version``
-------------------

Displays the installed GOATS CLI version.


``goats install``
-----------------

.. image:: images/cli-install-goats.png
   :alt: GOATS install command screenshot
   :align: center

Use this command to create a complete GOATS project in the directory of your
choice.

What it does:

- Creates a ready-to-run Django-based GOATS project.  
- Sets up project files, Redis configuration, and the initial database.  
- Lets you choose a custom media directory, or defaults internally.  
- Creates a superuser (interactive or headless).  
- Can overwrite an existing installation if ``--overwrite`` is provided.

Typical steps for users:

1. Run ``goats install``.  
2. Follow prompts to finalize setup.  
3. Use the printed “Next steps” to start GOATS.


``goats run``
-------------

.. image:: images/cli-run-goats.png
   :alt: GOATS run command screenshot
   :align: center

Starts your complete local GOATS environment with one command.

What it does:
- Supports custom host/port, number of workers, and browser preference.  
- Checks for port conflicts and verifies Redis is installed.  
- Syncs any template-managed GOATS files so your project stays current.  
- Starts Redis, the Django development server, background workers, and the scheduler.  
- Automatically opens your browser when the system is responsive.  
- Cleanly shuts everything down when you press ``Ctrl+C``.

Typical steps:

1. Run ``goats run``.  
2. GOATS opens automatically in your browser.  
3. Press ``Ctrl+C`` to shut it all down.