``goats_cli/``
==============

This package implements the command-line interface (CLI) for GOATS. It enables users to install and run the GOATS application without needing to manually configure Django, Redis, or background workers.

The CLI is built with `Click <https://click.palletsprojects.com/>`_ and exposed via the ``goats`` command, defined in ``pyproject.toml`` under ``[project.scripts]``.

Main Responsibilities
---------------------

- Scaffold a new GOATS project (via ``django-admin startproject``).
- Apply project-specific settings using TOMToolkit integration.
- Configure and launch the following components:

  - Redis server  
  - Django development server  
  - Background workers via Dramatiq

- Validate port bindings, environment state, and Redis availability.
- Open GOATS in the browser automatically after startup.
- Support for non-interactive CI installs.


Files
-----

- ``cli.py``  
  Entry point for the CLI.  
  Defines top-level commands like ``install`` and ``run``.  
  Uses ``Click`` decorators and option validation.  
  Handles startup, process management, and error reporting.

- ``config.py``  
  Centralized configuration (e.g., default Redis address, regex patterns).

- ``exceptions.py``  
  Defines ``GOATSClickException``, used for CLI-specific error handling.

- ``modify_settings.py``  
  Dynamically modifies Django ``settings.py`` during install to register GOATS and TOMToolkit apps.

- ``plugins.py``  
  Provides a framework for CLI plugin discovery and registration when modifying settings.

- ``process_manager.py``  
  Starts and supervises subprocesses (Redis, Django, Dramatiq workers).  
  Gracefully stops all processes on exit or interruption.

- ``utils.py``  
  Shared helper functions for messaging, port checks, browser launching, and CLI output formatting.