``goats_tom/``
==================

This is the main Django application powering GOATS. It extends TOMToolkit and includes all server-side logic, models, views, serializers, tasks, and static frontend assets.

Main Responsibilities
---------------------

- Extends TOMToolkit to provide Gemini-specific functionality.
- Implements core data models for DRAGONS, GPP, and observation management.
- Serves and manages all Django views, serializers, and forms.
- Defines and registers DRF API endpoints.
- Manages real-time communication using Django Channels and WebSockets.
- Orchestrates background tasks via Dramatiq and Redis.
- Handles file and recipe management for DRAGONS data reduction.
- Stores and renders user-facing templates and custom template tags.
- Interfaces with external services (GOA, GPP, TNS, Antares, Astro Data Lab).
- Contains all frontend assets and JavaScript apps for dynamic UI behavior.


Built on TOMToolkit
-------------------

GOATS is built on top of the `TOMToolkit <https://tom-toolkit.readthedocs.io/en/stable/>`_, a Django-based platform designed for developing Target and Observation Manager (TOM) systems in astronomy.

TOMToolkit provides core functionality such as:

- Target management
- Observation submission
- Alert ingestion
- Facility integration

GOATS extends this foundation with additional features and domain-specific logic for Gemini observatories, including custom APIs, reduction integration, and UI enhancements.

How GOATS Extends TOMToolkit
----------------------------

GOATS is implemented as a Django project that uses TOMToolkit apps and infrastructure. The base Django application lives in ``src/goats_tom/``.

URL Routing
~~~~~~~~~~~

GOATS reuses and overrides TOMToolkit URL patterns. You can find the custom URL configuration in:

.. code-block:: text

   src/goats_tom/urls.py

We include TOMToolkit routes and extend or override views where necessary.

Views
~~~~~

We build on TOMToolkit's class-based views and override behavior for custom UI or data needs. Most custom views live in:

.. code-block:: text

   src/goats_tom/views/

or in:

.. code-block:: text

    src/goats_tom/api_views/

Examples include:

- Customized target and observation views
- Additional views for DRAGONS reduction and file management
- Viewsets for Django REST Framework APIs

Templates
~~~~~~~~~

Django uses ``APP_DIRS = True`` to load templates from app-specific directories. GOATS overrides TOMToolkit templates by mirroring their paths under:

.. code-block:: text

   src/goats_tom/templates/

For example, to customize the target detail page, GOATS overrides:

.. code-block:: text

   src/goats_tom/templates/tom_targets/target_detail.html

Custom templates follow TOMToolkit's structure and are rendered automatically when placed in the correct location.

Template Tags
-------------

GOATS defines custom template tags in:

.. code-block:: text

   src/goats_tom/templatetags/

To use them in templates:

.. code-block:: django

   {% load goats_tags %}

These tags allow us to modify rendering logic without changing view logic.

Static Files
------------

Custom JavaScript, CSS, and images are stored in:

.. code-block:: text

   src/goats_tom/static/

GOATS extends TOMToolkit's default interface with custom UI behavior and styling.

Customizations Unique to GOATS
------------------------------

In addition to TOMToolkit functionality, GOATS adds several core components to support Gemini-specific workflows and data reduction pipelines.

Key Features
------------

- Integration with the Gemini Program Platform (GPP) via the ``gpp-client`` package.
- DRAGONS data reduction task orchestration using Redis and Dramatiq.
- File and recipe management system for data processing and calibration.
- Real-time UI updates via WebSockets for notifications and file downloads.
- Per-user credential storage to support authenticated interactions with external services.

JavaScript and async UX
~~~~~~~~~~~~~~~~~~~~~~~

- GOATS uses JavaScript (vanilla + ES6) to dynamically update page content without requiring full reloads.

WebSockets and Channels
~~~~~~~~~~~~~~~~~~~~~~~

- GOATS uses Django Channels to support real-time communication.
- Redis is configured as the channel layer backend to broadcast updates between workers and browser clients.
- Subscriptions are used for:
  - System-wide and per-user notifications
  - Long-running file processing updates
  - Background file download status

Dramatiq and Redis
~~~~~~~~~~~~~~~~~~

- All long-running or non-blocking work is delegated to **Dramatiq** background tasks.
- Redis acts as the message broker for Dramatiq.
- Common background tasks:
  - Launching DRAGONS reduction jobs
  - Importing external data
  - Downloading files
  - Processing observation metadata
  - Sending program notifications

DRAGONS Data Reduction
~~~~~~~~~~~~~~~~~~~~~~

- The DRAGONS interface is the largest JavaScript web application in GOATS.
- It is implemented in ``src/goats_tom/static/js/dragons_app/`` and dynamically manages all data reduction workflows.
- When a user initiates a reduction session through the UI, a **DRAGONS Run** is created.
- A run is a snapshot of the input files, parsed using Astrodata, which extracts metadata for filtering and grouping.
- Files are automatically grouped and sorted based on their metadata, but users may also manually sort or filter them.
- Users interact with the interface to:
  - Inspect and manage grouped files.
  - Select or override recipes.
  - Launch DRAGONS reductions on subsets of files.
- The reduction pipeline includes:
  - File validation.
  - Recipe selection.
  - Job queuing via Dramatiq.
  - Live status updates through WebSockets.
- Final results are stored and made available through the file manager interface.

Gemini Program Platform (GPP)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- GOATS integrates with GPP via the ``gpp-client`` library.
- Users can:
  - Authenticate with GPP.
  - View program and observation metadata.
  - Import program information directly into the TOM system.
  - Trigger ToOs.

Credential Manager
~~~~~~~~~~~~~~~~~~

- GOATS securely stores user credentials for external services.
- Credentials are stored per-user in the database and scoped by service (e.g., GPP, TNS).
- All credential input is handled via secure forms.
- Tokens are used to authorize data pulls and API requests.

Tips for Working with TOMToolkit
--------------------------------

- Before adding new code, check if TOMToolkit already provides what you need.
- When customizing views, prefer subclassing TOMToolkit views over rewriting them.
- Use Django's template inheritance and block overrides to customize UI.
- Explore TOMToolkit's source code and documentation for implementation patterns.

Resources
---------

- TOMToolkit Documentation: https://tom-toolkit.readthedocs.io/en/stable/
- TOMToolkit GitHub Repository: https://github.com/TOMToolkit/tom_base

Files
-----

- ``api_views/``: Django REST Framework API viewsets for all major data types and services, including DRAGONS, GPP, and external integrations.
- ``antares_client/``: Lightweight client for querying and consuming Antares alerts.
- ``astro_data_lab/``: Client code and configuration for interacting with Astro Data Lab.
- ``astroquery/``: GOATS-specific extensions for ``astroquery`` GOA.
- ``brokers/``: Alert broker integrations (currently Antares), including parsing and formatting of incoming alert data.
- ``consumers/``: Django Channels WebSocket consumers for real-time updates (e.g., DRAGONS progress, notifications, downloads).
- ``facilities/``: Facility-specific logic, including Gemini facility plugins and override hooks for TOMToolkit.
- ``filters/``: Custom filter backends and logic, especially for AstroData and ReducedDatum filtering using safe expression parsing.
- ``forms/``: Django forms for user authentication, external service logins, and GOA/GPP queries.
- ``harvesters/``: Polling-based external data harvester (e.g., TNS harvester).
- ``logging_extensions/``: Custom logging handlers and configurations for DRAGONS-specific event logging.
- ``middleware/``: Django middleware extensions for GOATS-specific workflows and background behaviors.
- ``migrations/``: Django migration files for GOATS models.
- ``models/``: Core data models for GOATS including DRAGONS runs, files, recipes, keys, and credential management.
- ``ocs/``: Parsers and helpers for communicating with the OCS.
- ``processors/``: Data processing pipelines, including spectroscopy support and reduction chaining
- ``realtime/``: Real-time state tracking logic for WebSocket-driven updates (e.g., download progress, notifications).
- ``routing.py``: Channel routing configuration for WebSocket consumers.
- ``serializers/``: DRF serializers for all public-facing data models and nested APIs.
- ``static/``: JavaScript, CSS, and image assets for GOATS frontend, including the DRAGONS reduction app and GPP interface.
- ``tasks/``: Dramatiq background task definitions (e.g., for DRAGONS reduction, file downloads).
- ``templates/``: All Django templates used or overridden in GOATS, organized by TOMToolkit app and component.
- ``templatetags/``: Custom Django template tags and filters (e.g., for rendering dynamic buttons, visualizers, and overrides).
- ``tests/``: Internal test tools for GOATS, organized by module. Includes ``factories/``, test settings, and URL overrides. Does not contain the actual test files.
- ``tns/``: Client integration with the Transient Name Server (TNS) for report submission and validation.
- ``utils/``: Shared utility functions and helpers used across multiple GOATS modules.
- ``views/``: All Django views, including class-based and function-based views for targets, observations, data products, keys, and reduction workflows.
- ``urls.py``: Root URL configuration for the GOATS Django app.