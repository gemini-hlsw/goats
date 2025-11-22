``goats_setup/``
================

This Django app bootstraps a new GOATS installation by configuring project settings, URLs, and ASGI routing. It is invoked by the CLI's ``goats install`` command and defines a Django management command to perform this setup non-interactively.

Main Responsibilities
---------------------

- Provides the ``goats_setup`` management command.
- Modifies ``settings.py``, ``urls.py``, and ``asgi.py`` using Jinja2-based templates.
- Registers required GOATS and TOMToolkit apps.
- Configures Redis, Channels, and static/media directories for GOATS projects.

Files
-----

- ``apps.py``  
  Django app registry file for ``goats_setup``.

- ``management/commands/goats_setup.py``  
  Custom Django management command used by ``goats install``.  
  Applies settings modifications using the provided templates.  
  Supports CLI options like ``--media-dir``, ``--ci``, and ``--redis-addrport``.

- ``templates/goats_setup/``  
  Jinja2-compatible templates rendered into the generated project.

  - ``settings.tmpl``  
    Used to produce a modified ``settings.py`` with required installed apps and middleware.

  - ``urls.tmpl``  
    Used to generate a ``urls.py`` pre-configured with GOATS and TOMToolkit routes.

  - ``asgi.tmpl``  
    Used to configure Channels and Redis for asynchronous features.