==============
Full Changelog
==============

.. note::

   As of June 17, 2025, changelog entries are now derived from `GitHub pull requests <https://github.com/gemini-hlsw/goats/pulls>`_.

   For full project tracking (requires access), see the `GOATS Jira board <https://noirlab.atlassian.net/jira/software/projects/GOATS/summary>`_.

.. towncrier release notes start
Version 25.6.1 (2025-06-27)
===========================

New Features
------------

- Added `--ci` flag to allow installing GOATS bypassing the user prompts for a CI pipeline. (`PR #323 <https://github.com/gemini-hlsw/goats/pull/323>`_)
- Add saving GPP credentials with ``gpp_client``: Communication with GPP is now established in GOATS. Users can save and verify their credential in GOATS for future use. (`PR #330 <https://github.com/gemini-hlsw/goats/pull/330>`_)
- Extended the API to allow fetching program information from GPP. (`PR #331 <https://github.com/gemini-hlsw/goats/pull/331>`_)
- Extended API to fetch observations from GPP. (`PR #332 <https://github.com/gemini-hlsw/goats/pull/332>`_)


Changes
-------

- Switch to `furo` theme for Read the Docs. (`PR #320 <https://github.com/gemini-hlsw/goats/pull/320>`_)
- Removed OCS key manager: Currently migrating to GPP, which simplifies how tokens need to be stored. (`PR #328 <https://github.com/gemini-hlsw/goats/pull/328>`_)


Other
-----

- Added user documentation for Astro Data Lab integration into GOATS. (`PR #GOATS-651 <https://github.com/gemini-hlsw/goats/pull/GOATS-651>`_)
- Improved build time for unit tests on GitHub by using `uv`: Removed the dependency for `conda` and install `dragons` and `fits_storage` from their respective repos. This removes the need for `conda` and the bloated install. (`PR #322 <https://github.com/gemini-hlsw/goats/pull/322>`_)


Documentation
-------------

- Moved `changelog` to documentation: The `changelog` has been moved to be hosted on Read the Docs. Towncrier has been converted to format the `changelog` in `.rst` (`PR #321 <https://github.com/gemini-hlsw/goats/pull/321>`_)
- Improve documentation and README. (`PR #325 <https://github.com/gemini-hlsw/goats/pull/325>`_)


GOATS 25.6.0 (2025-06-16)
=========================

New Features
------------

- Added ``uv`` for dependency management: Used ``uv`` to manage
  dependencies and generate lockfile for reproducible environments.
  [`#GOATS-101 <https://noirlab.atlassian.net/browse/GOATS-101>`_]
- Enabled automated updates: Configured Dependabot to create pull
  requests for dependency updates.
  [`#GOATS-680 <https://noirlab.atlassian.net/browse/GOATS-680>`_]
- Replaced Astro Data Lab client: Implemented internal class to remove
  dependency conflicts.
  [`#GOATS-668 <https://noirlab.atlassian.net/browse/GOATS-668>`_]
- Added nox testing for different python and dependency versions.
  [`#GOATS-670 <https://noirlab.atlassian.net/browse/GOATS-670>`_]
- Imported ``antares-client`` code: Added ``antares-client`` code
  directly into the repo to avoid dependency issues with ``marshmallow``
  and ``confluent-kafka``.
  [`#GOATS-672 <https://noirlab.atlassian.net/browse/GOATS-672>`_]

Changes
-------

- Skip building documentation if no changes to ``/docs/readthedocs``
  [`#GOATS-684 <https://noirlab.atlassian.net/browse/GOATS-684>`_]
- Updated GOATS user documentation (along with the videos) to clarify
  where one can add their GOA credentials.
  [`#GOATS-618 <https://noirlab.atlassian.net/browse/GOATS-618>`_]
- Updated DRAGONS and dependencies: Updated to DRAGONS 4.0.0 and raised
  the required Python version to 3.12. Also updated other dependencies
  for compatibility.
  [`#GOATS-678 <https://noirlab.atlassian.net/browse/GOATS-678>`_]

Other
-----

- Updated the GOATS workflow flowchart showing an additional step for
  adding existing Gemini observation and added a miscellaneous page for
  tips and tricks that users might find helpful.
  [`#GOATS-658 <https://noirlab.atlassian.net/browse/GOATS-658>`_]


GOATS 25.3.0 (2025-03-30)
=========================



New Features
------------

- Ensured worker shutdown in Dramatiq: Added fallbacks to manage worker
  threads, ensuring they were terminated if graceful shutdown failed.
  This prevented orphaned or zombie workers.
  [`#GOATS-654 <https://noirlab.atlassian.net/browse/GOATS-654>`_]
- Shutdown return code and port checks for Redis: Added shutdown return
  code for Redis and enforced killing child workers if timeout occurs.
  Checked if ports are in use on startup, issuing an error and
  preventing startup if occupied.
  [`#GOATS-655 <https://noirlab.atlassian.net/browse/GOATS-655>`_]
- Shutdown return code and port checks for Django: Added shutdown return
  code for Django and enforced killing child workers if timeout occurs.
  Checked if ports are in use on startup, issuing an error and
  preventing startup if occupied.
  [`#GOATS-656 <https://noirlab.atlassian.net/browse/GOATS-656>`_]
- Shutdown return code Dramatiq: Added shutdown return code for Dramatiq
  and enforced killing child workers if timeout occurs.
  [`#GOATS-657 <https://noirlab.atlassian.net/browse/GOATS-657>`_]
- Cleanly shut down DRAGONS in worker threads: Removed leftover orphaned
  processes on GOATS shutdown using custom middleware.
  [`#GOATS-660 <https://noirlab.atlassian.net/browse/GOATS-660>`_]
- Check ETISubprocess before shutdown: Prevented redundant creation and
  destruction of singleton.
  [`#GOATS-665 <https://noirlab.atlassian.net/browse/GOATS-665>`_]



Changes
-------

- Credential storage redesign: Improved how users store credentials and
  generate tokens for the browser extension. Added a popover explaining
  the credential manager in the user management page.
  [`#GOATS-632 <https://noirlab.atlassian.net/browse/GOATS-632>`_]

GOATS 25.2.2 (2025-02-28)
=========================



New Features
------------

- Created GitHub Pages for project: Set up a GitHub Pages site for GOATS
  to host documentation and Conda packages.
  [`#GOATS-648 <https://noirlab.atlassian.net/browse/GOATS-648>`_]
- Added barebones content for GitHub Pages: Added initial HTML
  structure, Bootstrap styling, and essential links.
  [`#GOATS-649 <https://noirlab.atlassian.net/browse/GOATS-649>`_]
- Created an empty Conda channel: Prepared ``gh-pages/conda/`` for
  hosting Conda packages with ``conda index``.
  [`#GOATS-650 <https://noirlab.atlassian.net/browse/GOATS-650>`_]

GOATS 25.2.1 (2025-02-27)
=========================



New Features
------------

- Included tooltips to explain “Create Groupings” and “Use All Files for
  Observation ID” in the DRAGONS app.
  [`#GOATS-561 <https://noirlab.atlassian.net/browse/GOATS-561>`_]
- Add DRAGONS docs link: Linked to the DRAGONS documentation based on
  the installed version in the reduction app. Defaults to the base
  documentation if no version is found.
  [`#GOATS-562 <https://noirlab.atlassian.net/browse/GOATS-562>`_]
- Open browser on GOATS start: GOATS now opens in the default browser
  when launched. Users can specify a browser via CLI, and if none is
  given, the system default is used.
  [`#GOATS-587 <https://noirlab.atlassian.net/browse/GOATS-587>`_]
- Added model for encrypted Astro Datalab credentials.
  [`#GOATS-610 <https://noirlab.atlassian.net/browse/GOATS-610>`_]
- Extend user page: Added form to store and validate Astro Datalab
  credentials. Users receive feedback on whether their credentials are
  correct.
  [`#GOATS-611 <https://noirlab.atlassian.net/browse/GOATS-611>`_]
- Build UI for sending files: Implemented UI for sending data files to
  Astro Datalab in the “Manage Data” tab in the target view. Added a
  dropdown menu for actions. Placeholder made for async API calls.
  [`#GOATS-612 <https://noirlab.atlassian.net/browse/GOATS-612>`_]
- Added API backend for Astro Datalab: Allowed users to send data files
  to Astro Datalab with their credentials.
  [`#GOATS-613 <https://noirlab.atlassian.net/browse/GOATS-613>`_]
- Linked UI with backend to send files to Astro Datalab. Updated the
  interface to show a process indicator during file transfer and provide
  feedback on success or failure.
  [`#GOATS-623 <https://noirlab.atlassian.net/browse/GOATS-623>`_]
- Created Astro Datalab landing page: Added a new Astro Datalab page
  with an associated Django view.
  [`#GOATS-624 <https://noirlab.atlassian.net/browse/GOATS-624>`_]
- Added pytest code coverage reporting.
  [`#GOATS-626 <https://noirlab.atlassian.net/browse/GOATS-626>`_]
- Added code coverage badge to README and refactored pull request
  template.
  [`#GOATS-630 <https://noirlab.atlassian.net/browse/GOATS-630>`_]
- Migrated ReadTheDocs to main repo: Transferred documentation from the
  ``goats-docs`` repository to the GOATS main repository for centralized
  management.
  [`#GOATS-635 <https://noirlab.atlassian.net/browse/GOATS-635>`_]



Changes
-------

- Disable GOA query for incomplete observations: Prevented users from
  submitting a GOA query if the observation status was not “Observed”.
  Added a backend check to issue a warning if the restriction is
  bypassed.
  [`#GOATS-192 <https://noirlab.atlassian.net/browse/GOATS-192>`_]
- Added last modified timestamp: Processed files in the DRAGONS app now
  include a last modified timestamp.
  [`#GOATS-560 <https://noirlab.atlassian.net/browse/GOATS-560>`_]
- Improve target name handling: Long target names now scroll instead of
  breaking the layout. Edit and delete buttons are now in a separate div
  for better responsiveness.
  [`#GOATS-563 <https://noirlab.atlassian.net/browse/GOATS-563>`_]
- Updated dependencies: Upgraded to the latest tomtoolkit release,
  refactored pyproject.toml, and removed redundant code now included in
  tomtoolkit.
  [`#GOATS-596 <https://noirlab.atlassian.net/browse/GOATS-596>`_]
- Refactored test infrastructure: Separated tests and optimized
  execution.
  [`#GOATS-625 <https://noirlab.atlassian.net/browse/GOATS-625>`_]
- iframe support for Astro Data Lab: Replaced static image link with an
  iframe to display the most recent version of the Astro Data Lab
  webpage. Added a failsafe text link for accessibility.
  [`#GOATS-628 <https://noirlab.atlassian.net/browse/GOATS-628>`_]
- iframe support for ANTARES: Replaced static image link with an iframe
  to display the most recent version of the ANTARES webpage. Added a
  failsafe text link for accessibility.
  [`#GOATS-629 <https://noirlab.atlassian.net/browse/GOATS-629>`_]
- Refactored GitHub workflows to run on PR and merge to main.
  [`#GOATS-631 <https://noirlab.atlassian.net/browse/GOATS-631>`_]

Bug Fixes
---------

- Fixed test slowdown bug: Resolved issue causing excessive test
  execution time when querying DRAGONS version.
  [`#GOATS-558 <https://noirlab.atlassian.net/browse/GOATS-558>`_]
- Corrected typo in Astro Data Lab name.
  [`#GOATS-627 <https://noirlab.atlassian.net/browse/GOATS-627>`_]

GOATS 25.1.1 (2025-01-30)
=========================



New Features
------------

- Add delete run functionality: Enabled a delete button for DRAGONS
  runs, allowing users to reclaim disk space. Extended the API to
  support run deletions.
  [`#GOATS-428 <https://noirlab.atlassian.net/browse/GOATS-428>`_]
- Added TNS query support: Developed class to query TNS objects and
  return payload.
  [`#GOATS-574 <https://noirlab.atlassian.net/browse/GOATS-574>`_]
- Updated TNS harvester: Modified harvester to use the TNSClient for
  object querying.
  [`#GOATS-575 <https://noirlab.atlassian.net/browse/GOATS-575>`_]
- Added LICENSE to repository.
  [`#GOATS-151 <https://noirlab.atlassian.net/browse/GOATS-151>`_]
- Add default recipe card with instructions: Introduced a default card
  that guides users to select a recipe. Provides tips on starting and
  stopping DRAGONS reduction, modifying recipes, and viewing logs.
  [`#GOATS-370 <https://noirlab.atlassian.net/browse/GOATS-370>`_]
- Show processed files in run directory: Renamed “Output Files” to
  “Processed Files” across classes and objects. Added button to view
  files in JS9 and display headers in a modal. Introduced
  ``DataProductMetadata`` model to minimize astrodata reads.
  [`#GOATS-429 <https://noirlab.atlassian.net/browse/GOATS-429>`_]
- Added user docs button: Added a button to the navbar that opens the
  user documentation in a new tab.
  [`#GOATS-495 <https://noirlab.atlassian.net/browse/GOATS-495>`_]
- Improved facility status page: Fetches and displays Gemini North and
  South status and updated weather URLs.
  [`#GOATS-497 <https://noirlab.atlassian.net/browse/GOATS-497>`_]
- Add filesearch textbox in Manage Data: Enhanced file management with a
  search box to filter files by filename and path.
  [`#GOATS-515 <https://noirlab.atlassian.net/browse/GOATS-515>`_]
- Improve cancel functionality: Enabled multiple attempts to stop
  background tasks during DRAGONS reduction if the initial cancellation
  fails.
  [`#GOATS-524 <https://noirlab.atlassian.net/browse/GOATS-524>`_]
- Fetch initial running reductions: Added functionality to retrieve and
  display initial running reductions on the DRAGONS page. Users can now
  see the current status of reductions immediately upon page load.
  [`#GOATS-525 <https://noirlab.atlassian.net/browse/GOATS-525>`_]
- Added responsive table format for long Target values in view.
  [`#GOATS-530 <https://noirlab.atlassian.net/browse/GOATS-530>`_]
- Added calibration file viewing and header display: Implemented support
  for viewing calibration files through the DRAGONS interface with JS9
  and displaying FITS header information.
  [`#GOATS-555 <https://noirlab.atlassian.net/browse/GOATS-555>`_]



Changes
-------

- Used local fontawesomefree: Incorporated FontAwesome into GOATS static
  assets and removed external Python dependency.
  [`#GOATS-535 <https://noirlab.atlassian.net/browse/GOATS-535>`_]
- Removed Update Broker Data button: Removed the “Update Broker Data”
  button from the target list view.
  [`#GOATS-160 <https://noirlab.atlassian.net/browse/GOATS-160>`_]
- Refactored product IDs: Changed how products are stored by using file
  paths to handle files in different directories with the same product
  IDs. [`#GOATS-473 <https://noirlab.atlassian.net/browse/GOATS-473>`_]
- Updated environment.yaml for latest DRAGONS: Updated the environment
  file to include the latest DRAGONS release with patches specific to
  GOATS.
  [`#GOATS-547 <https://noirlab.atlassian.net/browse/GOATS-547>`_]
- Remove tom-antares dependency: Ingested its functionality directly
  into GOATS due to extensive customizations and installation
  complexities.
  [`#GOATS-554 <https://noirlab.atlassian.net/browse/GOATS-554>`_]



Bug Fixes
---------

- Fixed file deletion bug: Correctly built full path for processed files
  to delete.
  [`#GOATS-559 <https://noirlab.atlassian.net/browse/GOATS-559>`_]
- Handle duplicate file entries in checksum files: Fixed an issue where
  duplicate file entries in GOA checksum files caused errors during
  downloading and decompression. The process now skips duplicates and
  continues without interruption.
  [`#GOATS-577 <https://noirlab.atlassian.net/browse/GOATS-577>`_]
- Set astroquery version: Fixed SIMBAD query compatibility by pinning
  astroquery to a working version.
  [`#GOATS-579 <https://noirlab.atlassian.net/browse/GOATS-579>`_]
- Fixed calibration path handling: Resolved issue with spaces in
  calibration database paths causing errors during DRAGONS reduction.
  [`#GOATS-317 <https://noirlab.atlassian.net/browse/GOATS-317>`_]
- Fixed ANTARES queries: Ensured user queries can be renamed properly
  and querying with elastic search works.
  [`#GOATS-498 <https://noirlab.atlassian.net/browse/GOATS-498>`_]
- Fix issue with conda environment with GitHub Actions.
  [`#GOATS-504 <https://noirlab.atlassian.net/browse/GOATS-504>`_]
- Added functionality to handle decompression of bz2 FITS files uploaded
  into the calibration database. Previously, silent errors occurred due
  to improper handling of decompression and file placement.
  [`#GOATS-556 <https://noirlab.atlassian.net/browse/GOATS-556>`_]
- Workaround for DRAGONS version mismatch: Addressed an issue where the
  DRAGONS version reported by pip differed from the conda-installed
  version by implementing logic to pull the version directly from conda.
  [`#GOATS-557 <https://noirlab.atlassian.net/browse/GOATS-557>`_]

GOATS 24.12.0 (2024-12-21)
=========================-



New Features
------------

- Implemented dataproduct visualizer template tag: Designed and
  implemented a templatetag to fetch and display dataproducts for
  visualization based on data type.
  [`#GOATS-489 <https://noirlab.atlassian.net/browse/GOATS-489>`_]
- Add photometric data plotting: Refactored plotting logic and enhanced
  interface usability.
  [`#GOATS-490 <https://noirlab.atlassian.net/browse/GOATS-490>`_]
- Added tests for API endpoints added for data visualizer.
  [`#GOATS-492 <https://noirlab.atlassian.net/browse/GOATS-492>`_]
- Connected backend API with frontend fetching: Implemented async
  fetching to dynamically retrieve or process dataproducts for plotting.
  [`#GOATS-493 <https://noirlab.atlassian.net/browse/GOATS-493>`_]
- Added Plotly.js for dynamic plotting: Integrated Plotly.js for
  interactive plotting in the dataproduct visualizer and implemented
  styling to toggle between dark and light themes.
  [`#GOATS-494 <https://noirlab.atlassian.net/browse/GOATS-494>`_]
- Added django filter for reduced dataproducts: Allowed querying of
  reduced data by product ID and data type.
  [`#GOATS-496 <https://noirlab.atlassian.net/browse/GOATS-496>`_]
- Added plotting function to update plot with requested spectroscopy
  data.
  [`#GOATS-499 <https://noirlab.atlassian.net/browse/GOATS-499>`_]
- Extended Gemini facility class functionality: Added methods for
  reading FITS headers and handling Gemini-specific image data.
  [`#GOATS-503 <https://noirlab.atlassian.net/browse/GOATS-503>`_]
- Added search field for file names: Implemented client-side filtering
  for the File Name column on the data visualizer to allow users to
  quickly find files.
  [`#GOATS-509 <https://noirlab.atlassian.net/browse/GOATS-509>`_]
- Update plot with axis unit handling and editable labels: Added support
  to display correct units for Wavelength and Flux if available in FITS
  files. Defaulted to “Wavelength” and “Flux” when units are missing.
  Made axis labels editable for manual input with CSV files for both
  photometry and spectroscopy.
  [`#GOATS-510 <https://noirlab.atlassian.net/browse/GOATS-510>`_]
- Added editable axis ranges: Enabled users to click directly on x and y
  axis end values to edit their ranges.
  [`#GOATS-511 <https://noirlab.atlassian.net/browse/GOATS-511>`_]
- Added user feedback when no files matched filter criteria during file
  plotting.
  [`#GOATS-512 <https://noirlab.atlassian.net/browse/GOATS-512>`_]



Changes
-------

- Update photometry tab message: Revised message to include supported
  CSV format with a link to Manage Data.
  [`#GOATS-507 <https://noirlab.atlassian.net/browse/GOATS-507>`_]
- Update spectroscopy tab message: Revised message to include supported
  FITS and CSV formats with a link to Manage Data.
  [`#GOATS-508 <https://noirlab.atlassian.net/browse/GOATS-508>`_]



Bug Fixes
---------

- Dynamic WebSocket URL generation: Built WebSocket URL from window and
  request.
  [`#GOATS-281 <https://noirlab.atlassian.net/browse/GOATS-281>`_]
- Converted endpoint to API: Browser extension endpoint now functions as
  a fully integrated API endpoint with proper token authentication to
  validate posts.
  [`#GOATS-383 <https://noirlab.atlassian.net/browse/GOATS-383>`_]
- Fixed issue with Django template and airmass plot.
  [`#GOATS-500 <https://noirlab.atlassian.net/browse/GOATS-500>`_]
- Fixed typo with filter backend in the settings template.
  [`#GOATS-501 <https://noirlab.atlassian.net/browse/GOATS-501>`_]
- Implemented workaround for CORS-related issue with plotting.
  [`#GOATS-502 <https://noirlab.atlassian.net/browse/GOATS-502>`_]
- Fixed issue with url for fetching and plotting data.
  [`#GOATS-505 <https://noirlab.atlassian.net/browse/GOATS-505>`_]

GOATS 24.11.0 (2024-11-27)
=========================-



New Features
------------

- Added navbar to observation page: Implemented a new template tag to
  include the navigation bar on the observation page for targets.
  [`#GOATS-173 <https://noirlab.atlassian.net/browse/GOATS-173>`_]
- Added GHOST in DRAGONS application: Implemented features in DRAGONS
  application to debundle and reduce GHOST data. Bugfix for file group
  selection and improved astroquery login verification.
  [`#GOATS-328 <https://noirlab.atlassian.net/browse/GOATS-328>`_]
- Enhanced file fetch control: Added a checkbox to the UI that allows
  users to fetch all files for an observation ID, disabling the default
  filters of observation class, type, and object name. This change
  grants users full control over the selection of files for use in
  DRAGONS recipe reductions.
  [`#GOATS-411 <https://noirlab.atlassian.net/browse/GOATS-411>`_]
- Renamed ‘uparms’ for clarity and added a tooltip to assist users in
  using it correctly.
  [`#GOATS-444 <https://noirlab.atlassian.net/browse/GOATS-444>`_]
- Added API endpoint for DRAGONS reduced images: Implemented a new
  processor to extract data from DRAGONS reduced images and extended
  TOMToolkit functions to support new requirements.
  [`#GOATS-484 <https://noirlab.atlassian.net/browse/GOATS-484>`_]



Changes
-------

- Refactored codebase for better organization.
  [`#GOATS-329 <https://noirlab.atlassian.net/browse/GOATS-329>`_]
- Removed unnecessary data types for data products: Only ‘fits_file’ is
  needed for DRAGONS reduction.
  [`#GOATS-445 <https://noirlab.atlassian.net/browse/GOATS-445>`_]
- Hide UI elements without run selection: The visibility of the output
  files and calibration database manager is now controlled by the
  selection of a run ID.
  [`#GOATS-467 <https://noirlab.atlassian.net/browse/GOATS-467>`_]
- Sort files by observation type for DRAGONS compatibility: Ensured the
  first file in the list matches the recipe’s observation type to
  prevent mismatches with tags and primitives.
  [`#GOATS-479 <https://noirlab.atlassian.net/browse/GOATS-479>`_]



Bug Fixes
---------

- Fixed observation record ID handling: Corrected an issue where a
  hardcoded observation ID from testing persisted into production,
  ensuring that only runs associated with an actual observation record
  are displayed.
  [`#GOATS-464 <https://noirlab.atlassian.net/browse/GOATS-464>`_]
- Fixed filter expression and ID uniqueness bugs: Resolved an issue
  where user-provided filter expressions were not correctly used in
  filtering and grouping available files. Additionally, improved the
  uniqueness of file checkbox IDs by incorporating more identifying
  information, addressing an issue uncovered when allowing user access
  to all files.
  [`#GOATS-465 <https://noirlab.atlassian.net/browse/GOATS-465>`_]
- Fixed recipe and primitive extraction for DRAGONS application:
  Extracted primitives now include all lines, ensuring comments and
  docstrings are no longer ignored.
  [`#GOATS-470 <https://noirlab.atlassian.net/browse/GOATS-470>`_]
- Added safeguard for missing primitive params in ``showpars``: Ensured
  DRAGONS/GOATS ``showpars`` handles cases where parameters for specific
  primitives are absent.
  [`#GOATS-471 <https://noirlab.atlassian.net/browse/GOATS-471>`_]
- Fixed query order operations: Corrected handling of logical operations
  in expressions. Implemented using the ``ast`` module to parse
  expressions more reliably. Updated logical operators to be
  case-sensitive as required by ``ast``. Removed “not” but added “!=” as
  a valid operation. Updated UI help documentation to reflect these
  changes.
  [`#GOATS-474 <https://noirlab.atlassian.net/browse/GOATS-474>`_]
- Bugfix for numerical astrodata descriptors: Allowed numerical values
  for astrodata_descriptors like ‘object’. Users now need to enclose
  strings in quotes for correct parsing, while numerical values should
  be entered without quotes. Added a default return to ensure consistent
  API responses when no files are found during grouping.
  [`#GOATS-475 <https://noirlab.atlassian.net/browse/GOATS-475>`_]

GOATS 24.10.0 (2024-10-29)
=========================-



New Features
------------

- Added API backend for output file listing: Implemented functionality
  to list output files and their last modified timestamps from a
  ``DRAGONSRun``.
  [`#GOATS-426 <https://noirlab.atlassian.net/browse/GOATS-426>`_]
- Linked API with UI for output directory display: Integrated the API
  and UI to enhance visibility of the output file directory. Added user
  feedback mechanisms for updates and refresh actions.
  [`#GOATS-430 <https://noirlab.atlassian.net/browse/GOATS-430>`_]
- Added API file management for DRAGONS runs: Extended the system to
  allow adding files from the output directory of a DRAGONS run to the
  saved dataproducts. Users can now also remove these files; doing so
  deletes both the dataproduct entry and the file itself.
  [`#GOATS-431 <https://noirlab.atlassian.net/browse/GOATS-431>`_]
- Linked backend and frontend for DRAGONS output file operations: The
  integration now allows adding output files to data products and
  removing them directly through the frontend interface.
  [`#GOATS-433 <https://noirlab.atlassian.net/browse/GOATS-433>`_]
- Designed uparms UI for DRAGONS recipe modification: Implemented a user
  interface to edit ‘uparms’ for recipes, requiring ‘edit’ mode
  activation similar to existing recipe and primitive modifications.
  [`#GOATS-434 <https://noirlab.atlassian.net/browse/GOATS-434>`_]
- Extended DRAGONS recipe “uparms” handling in API: Updated the backend
  to support modifications to “uparms” for DRAGONS recipe reductions.
  The update includes parsing “uparms” from string format into Python
  objects, enabling dynamic parameter adjustments.
  [`#GOATS-435 <https://noirlab.atlassian.net/browse/GOATS-435>`_]
- Connected frontend to backend for using uparms in DRAGONS reduction.
  [`#GOATS-436 <https://noirlab.atlassian.net/browse/GOATS-436>`_]
- Refactored DRAGONS logger: Improved efficiency and cleaned up code.
  [`#GOATS-437 <https://noirlab.atlassian.net/browse/GOATS-437>`_]
- Refactored progress bar for recipes: Improved maintainability and
  readability of the code handling the recipe progress bar.
  [`#GOATS-438 <https://noirlab.atlassian.net/browse/GOATS-438>`_]
- Fix versioning issues: Resolved bugs in tomtoolkit, GOA, and
  astroquery. Fixed tomtoolkit version to prevent future compatibility
  issues.
  [`#GOATS-439 <https://noirlab.atlassian.net/browse/GOATS-439>`_]



Changes
-------

- Major refactor of DRAGONS app: Accommodated changes to recipe and file
  nesting.
  [`#GOATS-412 <https://noirlab.atlassian.net/browse/GOATS-412>`_]
- Refactor run panel UI: Improved loading animation and user feedback
  during actions.
  [`#GOATS-441 <https://noirlab.atlassian.net/browse/GOATS-441>`_]
- Refactored files table: Improved display of groups and file toggling
  for runs.
  [`#GOATS-442 <https://noirlab.atlassian.net/browse/GOATS-442>`_]
- Moved API to singleton design: Simplified DRAGONS API by converting it
  to a singleton pattern and made it globally accessible to all classes.
  Adjusted how default options are constructed.
  [`#GOATS-446 <https://noirlab.atlassian.net/browse/GOATS-446>`_]
- Refactored modal: Improved modal code for maintainability.
  [`#GOATS-447 <https://noirlab.atlassian.net/browse/GOATS-447>`_]
- Refactored dragons app folder: Consolidated and organized code in the
  dragons app folder for better modularity and maintainability.
  [`#GOATS-448 <https://noirlab.atlassian.net/browse/GOATS-448>`_]
- Refactored available recipes logic: Refactored the available recipes
  structure to simplify code and improve maintainability. Added a global
  event dispatcher to notify when a recipe is changed, allowing other
  components to react accordingly.
  [`#GOATS-449 <https://noirlab.atlassian.net/browse/GOATS-449>`_]
- Refactored available files for observation type: Simplified the
  structure of available files by refactoring the code. Introduced
  helper functions to create unique IDs using observation type,
  observation class, and object name.
  [`#GOATS-450 <https://noirlab.atlassian.net/browse/GOATS-450>`_]
- Refactored observation data organization: Enhanced how observation
  type, observation class, and object name organize recipes and files.
  Added a new endpoint to set up initial data for recipes and files for
  a specific run.
  [`#GOATS-451 <https://noirlab.atlassian.net/browse/GOATS-451>`_]
- Refactored API grouping control: The API now allows users to specify
  fields to group for better DRAGONS use.
  [`#GOATS-452 <https://noirlab.atlassian.net/browse/GOATS-452>`_]
- Refactored file identifiers in accordions: Refactored how files are
  displayed in accordions based on observation type, class, and object
  name. Introduced a helper class to manage these identifiers
  efficiently.
  [`#GOATS-457 <https://noirlab.atlassian.net/browse/GOATS-457>`_]
- Refactored available files handling: Enhanced file filtering
  mechanisms and prepared for future expansion to include all files.
  Callbacks for filtering processes were integrated to ensure smooth
  operations.
  [`#GOATS-458 <https://noirlab.atlassian.net/browse/GOATS-458>`_]
- Refactored recipe reduction.
  [`#GOATS-459 <https://noirlab.atlassian.net/browse/GOATS-459>`_]
- General cleanup: Removed unnecessary data storage and added
  documentation.
  [`#GOATS-461 <https://noirlab.atlassian.net/browse/GOATS-461>`_]
- Refactored WebSocket updates and app initialization.
  [`#GOATS-462 <https://noirlab.atlassian.net/browse/GOATS-462>`_]

GOATS 24.9.0 (2024-09-20)
=========================



New Features
------------

- Enabled extended downloading from GOA: Added capability to download
  and link missing data from other observation IDs or calibration files.
  Users can now use standard stars, BPMs, and other resources from other
  observation IDs for use in DRAGONS reduction.​
  [`#GOATS-267 <https://noirlab.atlassian.net/browse/GOATS-267>`_]
- Updated file UI interactions: Connected UI components and API fetch
  functionalities to update, filter, group, and query available files
  for DRAGONS reductions.
  [`#GOATS-379 <https://noirlab.atlassian.net/browse/GOATS-379>`_]
- Added date and time filtering: Enhanced DRAGONS file filtering by
  adding support for date, time, and datetime descriptors. Comprehensive
  tests were implemented for the new astrodata descriptor filtering
  features.
  [`#GOATS-391 <https://noirlab.atlassian.net/browse/GOATS-391>`_]
- Refreshed dropdown on selection: Added a handler to clear the input
  text and refresh available options whenever a user selects an item
  from the multiselect dropdown for descriptor groups.
  [`#GOATS-394 <https://noirlab.atlassian.net/browse/GOATS-394>`_]
- Included file count for ‘All’: Displayed the number of files when
  filtering to reduce confusion between filtering only and grouping with
  filtering.
  [`#GOATS-396 <https://noirlab.atlassian.net/browse/GOATS-396>`_]
- Extended background worker timeout and made configurable: Allowed
  users to configure the time limit for background tasks via Django
  settings, enabling better control over task execution duration.
  [`#GOATS-400 <https://noirlab.atlassian.net/browse/GOATS-400>`_]
- Added truncation for grouped values: Grouping values are now truncated
  to include file counts.
  [`#GOATS-405 <https://noirlab.atlassian.net/browse/GOATS-405>`_]
- Enhanced UI with informational tooltips: Added clickable icons to the
  DRAGONS frontend that display tooltips explaining strict filtering
  options and available logical operators for filter expressions.
  [`#GOATS-409 <https://noirlab.atlassian.net/browse/GOATS-409>`_]
- Added select-all/deselect-all functionality for files for observation
  types.
  [`#GOATS-410 <https://noirlab.atlassian.net/browse/GOATS-410>`_]
- Design UI for calibration database: Completed the UI design and
  development for the calibration database.
  [`#GOATS-415 <https://noirlab.atlassian.net/browse/GOATS-415>`_]
- Added file management capabilities to the calibration database: Users
  can now add files to, remove files from, and list files in the
  calibration database directly via the API.
  [`#GOATS-417 <https://noirlab.atlassian.net/browse/GOATS-417>`_]
- Connected frontend with backend API for file removal and refresh:
  Integrated the frontend user interface with the backend API to enable
  file removal from the calibration database. Added a refresh button to
  update the database view.
  [`#GOATS-420 <https://noirlab.atlassian.net/browse/GOATS-420>`_]
- Added file upload support: Enabled uploading files to the calibration
  database for DRAGONS reduction.
  [`#GOATS-421 <https://noirlab.atlassian.net/browse/GOATS-421>`_]
- Developed output files UI: Developed a user interface container to
  manage and display output files for a DRAGONS reduction.
  [`#GOATS-425 <https://noirlab.atlassian.net/browse/GOATS-425>`_]
- Enhanced file upload feedback and usability: Added a new column in the
  user interface to indicate which files were uploaded by users. Fixed
  an issue that prevented the re-upload of the same file consecutively.
  [`#GOATS-427 <https://noirlab.atlassian.net/browse/GOATS-427>`_]



Changes
-------

- Improved error handling for GOA downloads: Added error handling for
  file downloads with updates to the webpage’s progress bar to reflect
  errors. Errors are now logged within the download model, providing
  users with detailed error messages when issues occur.​
  [`#GOATS-312 <https://noirlab.atlassian.net/browse/GOATS-312>`_]
- Sanitized run IDs for folder names: When a user provides a run ID for
  DRAGONS reduction, all characters unsuitable for a folder directory
  name are removed, and spaces are replaced with underscores.
  [`#GOATS-337 <https://noirlab.atlassian.net/browse/GOATS-337>`_]
- Removed old bias filtering: Replaced with a more powerful file
  filtering system.
  [`#GOATS-399 <https://noirlab.atlassian.net/browse/GOATS-399>`_]
- Enhanced product ID uniqueness: Made the product ID for a dataproduct
  more robust to fix integrity issues when adding the same dataproduct
  under different observations and targets.
  [`#GOATS-401 <https://noirlab.atlassian.net/browse/GOATS-401>`_]
- Refactored run table classes for clarity and improve the
  maintainability of the DRAGONS UI.
  [`#GOATS-413 <https://noirlab.atlassian.net/browse/GOATS-413>`_]



Bug Fixes
---------

- Removed limit on multiselect dropdown options: The maximum number of
  options displayed in the multiselect dropdown has been removed,
  allowing for unrestricted selection from all available options.
  [`#GOATS-390 <https://noirlab.atlassian.net/browse/GOATS-390>`_]
- Updated database model for DRAGONS runs: Corrected the database model
  to handle unique recipes per observation type and object name when the
  observation type is an object, addressing crashes for observation
  records with similar recipe requirements.
  [`#GOATS-392 <https://noirlab.atlassian.net/browse/GOATS-392>`_]
- Fixed dataset referencing in DRAGONS interface: The observation record
  ID dataset attached to the DRAGONS interface was referenced improperly
  and has been corrected.
  [`#GOATS-393 <https://noirlab.atlassian.net/browse/GOATS-393>`_]

GOATS 24.8.0 (2024-08-22)
=========================



New Features
------------

- Added run information panel on DRAGONS UI: Displayed selected run
  details, including creation date, DRAGONS version, and output
  directory path.
  [`#GOATS-332 <https://noirlab.atlassian.net/browse/GOATS-332>`_]
- Added UI components for file grouping and filtering: Introduced user
  interface elements that allow grouping and filtering of files,
  featuring a multiselect dropdown for selecting astrodata descriptors.
  [`#GOATS-376 <https://noirlab.atlassian.net/browse/GOATS-376>`_]
- Enhanced file grouping and filtering: Added functionality to fetch
  files from the frontend to the grouping and filtering API backend.
  Implemented listeners for button clicks to query API from the form.
  [`#GOATS-377 <https://noirlab.atlassian.net/browse/GOATS-377>`_]
- Added API endpoint for groups retrieval: Provided astrodata
  descriptors (groups) via API for DRAGONS runs and files.
  [`#GOATS-378 <https://noirlab.atlassian.net/browse/GOATS-378>`_]
- Grouped files by astrodata descriptors: Implemented an API backend to
  group files by their astrodata descriptors and count the files
  accordingly.
  [`#GOATS-380 <https://noirlab.atlassian.net/browse/GOATS-380>`_]
- Filtered files by astrodata descriptor values: Created an API backend
  to filter files based on expressions matching astrodata descriptor
  values.
  [`#GOATS-381 <https://noirlab.atlassian.net/browse/GOATS-381>`_]



Changes
-------

- Overhaul recipe assignment logic: Abandoned reliance on observation
  types for assigning recipes. Transitioned to using recipes modules,
  instruments, and tags to manage file recipes. This change enables
  GOATS to efficiently segregate files by their respective recipes and
  further distinguish different objects that may require unique recipes.
  The update prepares GOATS for integrating new instruments.
  [`#GOATS-360 <https://noirlab.atlassian.net/browse/GOATS-360>`_]
- Extended help page for interactive mode: Enhanced help documentation
  to show how to enable interactive mode for specific primitives.
  Interactive mode is no longer the default setting.
  [`#GOATS-367 <https://noirlab.atlassian.net/browse/GOATS-367>`_]



Bug Fixes
---------

- Fixed modal and toast closing issues: Resolved a bug caused by the
  transition to Bootstrap 5.
  [`#GOATS-356 <https://noirlab.atlassian.net/browse/GOATS-356>`_]
- Fixed help page docstring retrieval: Corrected an issue where
  docstrings were not properly fetched for the help page. Added tests to
  prevent in future.
  [`#GOATS-371 <https://noirlab.atlassian.net/browse/GOATS-371>`_]

GOATS 24.7.0 (2024-07-23)
=========================



New Features
------------

- Add Chrome extension link: Users can now click to access the Chrome
  extension store for installing antares2goats to enhance their GOATS
  experience from the ANTARES broker page.
  [`#GOATS-294 <https://noirlab.atlassian.net/browse/GOATS-294>`_]
- Editing, resetting, and saving DRAGONS recipes: DRAGONS recipes now
  support editing, saving, and resetting to original states. Users can
  customize recipes during data reduction processes.
  [`#GOATS-321 <https://noirlab.atlassian.net/browse/GOATS-321>`_]
- Enabled custom recipe input for DRAGONS: Users can now specify and
  utilize their own recipes in the DRAGONS reduction process.
  [`#GOATS-345 <https://noirlab.atlassian.net/browse/GOATS-345>`_]
- Added UI for DRAGONS reduction help pages: Side offcanvas with
  animation opens and closes to display helpful information for users on
  click.
  [`#GOATS-346 <https://noirlab.atlassian.net/browse/GOATS-346>`_]
- Added query parameter for detailed docs for primitives in API:
  Extended the DRAGONS files and recipes system to include a new query
  parameter. This parameter allows API responses to provide detailed
  documentation and descriptions of primitives used in a recipe.
  [`#GOATS-349 <https://noirlab.atlassian.net/browse/GOATS-349>`_]
- Connected frontend and backend for help docs: Established linkage
  between the frontend and backend systems for fetching and displaying
  help documentation related to primitives. Designed the user interface
  to comprehensively present all components of numpy doc strings and
  parameters when available.
  [`#GOATS-350 <https://noirlab.atlassian.net/browse/GOATS-350>`_]
- Implemented version-based recipe creation: Prevented redundant recipe
  entries in DRAGONS by creating base recipes only when the version
  changes.
  [`#GOATS-358 <https://noirlab.atlassian.net/browse/GOATS-358>`_]
- Updated UI recipe selection: Added functionality to choose and display
  recipes dynamically in DRAGONS recipe cards. Enhanced user interface
  elements include ordered observation types and updated card titles.
  [`#GOATS-359 <https://noirlab.atlassian.net/browse/GOATS-359>`_]



Changes
-------

- Output directory now matches run ID: Removed unused setup form and
  refresh button for DRAGONS runs. Disabled the delete option but
  retained it as a placeholder.
  [`#GOATS-305 <https://noirlab.atlassian.net/browse/GOATS-305>`_]
- Refactored UI for recipe management: Redesigned the user interface for
  managing observation type recipes and reductions. Now, only one
  reduction is displayed at a time, requiring users to toggle between
  them. This change simplifies the interface, helping users focus on one
  task at a time and reducing information overload.
  [`#GOATS-351 <https://noirlab.atlassian.net/browse/GOATS-351>`_]
- Improved “Help” bar output: Preserved spacing in docstrings for
  improved readability and changed applied styles.
  [`#GOATS-352 <https://noirlab.atlassian.net/browse/GOATS-352>`_]



Bug Fixes
---------

- Fixed custom media directory issue: Resolved path handling for custom
  media directories when running DRAGONS and saving products.
  [`#GOATS-304 <https://noirlab.atlassian.net/browse/GOATS-304>`_]
- Disabled automatic retries for failed DRAGONS reductions and GOA
  downloads.
  [`#GOATS-335 <https://noirlab.atlassian.net/browse/GOATS-335>`_]
- Resolved bug for trying to set state of null element in UI.
  [`#GOATS-340 <https://noirlab.atlassian.net/browse/GOATS-340>`_]
- Improved error handling for GOA timeouts when querying data products.
  [`#GOATS-344 <https://noirlab.atlassian.net/browse/GOATS-344>`_]

Enhancements
------------

- Enhanced GOATS startup and shutdown: Removed threading and implemented
  subprocesses. GOATS now exits cleanly, allowing sufficient time for
  all processes to shutdown properly.
  [`#GOATS-336 <https://noirlab.atlassian.net/browse/GOATS-336>`_]
- Reduced file operations in DRAGONS recipe queries.
  [`#GOATS-357 <https://noirlab.atlassian.net/browse/GOATS-357>`_]

GOATS 24.6.0 (2024-06-25)
=========================



New Features
------------

- Extended pagination to include item count: Overrode
  bootstrap_pagination to show “Showing x-y of n” message. Updated HTML
  template to display item counts.
  [`#GOATS-178 <https://noirlab.atlassian.net/browse/GOATS-178>`_]
- Implemented WebSocket support for DRAGONS logs: Developed a Channels
  consumer to handle real-time log messages from DRAGONS. Added a new
  WebSocket endpoint for DRAGONS updates and integrated a WebSocket
  logging handler. Expanded testing to cover Django Channels consumers.
  [`#GOATS-286 <https://noirlab.atlassian.net/browse/GOATS-286>`_]
- Developed DRAGONS WebSocket logging: Developed a Python logging
  handler for WebSocket communication to provide real-time logs for the
  DRAGONS system.
  [`#GOATS-290 <https://noirlab.atlassian.net/browse/GOATS-290>`_]
- Add backend for DRAGONS reduction: Developed an API to initiate and
  manage DRAGONS reduction processes in the background. Introduced a
  model to store details and updates of background tasks. Wrote
  comprehensive tests for the new backend infrastructure.
  [`#GOATS-292 <https://noirlab.atlassian.net/browse/GOATS-292>`_]
- Enabled initiation of DRAGONS recipe reduction from the UI.
  [`#GOATS-295 <https://noirlab.atlassian.net/browse/GOATS-295>`_]
- Added cancel endpoint for DRAGONS tasks: An API endpoint now allows
  canceling running or queued tasks in DRAGONS by setting the status of
  a recipe reduction to “canceled.” This action triggers the abortion of
  the background task. The update includes a new serializer to handle
  patches and extends tests to cover both valid and invalid patch
  scenarios.
  [`#GOATS-299 <https://noirlab.atlassian.net/browse/GOATS-299>`_]
- Enabled running task cancellation from UI: Connected the frontend
  “Stop” button with the backend to enable users to cancel running tasks
  directly from the interface. Added logic to dynamically enable or
  disable “Start” and “Stop” buttons based on the current status of
  recipe reductions.
  [`#GOATS-300 <https://noirlab.atlassian.net/browse/GOATS-300>`_]
- Display real-time logs on frontend with websocket: Built
  infrastructure to manage recipes for reduce runs, simplifying updates
  to specific recipes. Refactored recipe MVC.
  [`#GOATS-301 <https://noirlab.atlassian.net/browse/GOATS-301>`_]
- Extended DRAGONS consumer for real-time recipe progress updates:
  Updated the UI to display initial progress information. Added
  utilities for easier real-time communication and refactored UI
  progress bars to lay the foundation for future enhancements.
  [`#GOATS-302 <https://noirlab.atlassian.net/browse/GOATS-302>`_]
- Enabled interactive mode for select file types in recipe reduce:
  Integrated Bokeh for interactive visualization in ‘arc’, ‘flat’, and
  ‘object’ file types.
  [`#GOATS-303 <https://noirlab.atlassian.net/browse/GOATS-303>`_]
- Wrote tests for additional Django Channels classes: Added unit tests
  for websocket classes responsible for the notification system.
  [`#GOATS-307 <https://noirlab.atlassian.net/browse/GOATS-307>`_]
- Enhanced DRAGONS log autoscroll behavior: Updated logger to
  conditionally autoscroll based on the user’s current scroll position.
  Methods intended for logger internal use were made private.
  [`#GOATS-308 <https://noirlab.atlassian.net/browse/GOATS-308>`_]
- Cleared DRAGONS logs at recipe start.
  [`#GOATS-309 <https://noirlab.atlassian.net/browse/GOATS-309>`_]
- Load running reductions on DRAGONS run select: Implemented
  synchronization of running reductions on page refresh or when a new
  run is selected. Added support for query parameters to fetch and limit
  reduction results in the API.
  [`#GOATS-313 <https://noirlab.atlassian.net/browse/GOATS-313>`_]



Changes
-------

- Update conda environment file and dependencies: Removed the set
  version for tomtoolkit. Fixed issue caused by the new version of
  tomtoolkit.
  [`#GOATS-272 <https://noirlab.atlassian.net/browse/GOATS-272>`_]
- Added additional recipe reduce status feedback: Enhanced visibility of
  recipe reduce states and refined error handling in the DRAGONS reduce
  background task.
  [`#GOATS-310 <https://noirlab.atlassian.net/browse/GOATS-310>`_]
- Enhanced recipe progress UI: Updated the progress bar to display
  different colors for different states and provide status label.
  [`#GOATS-311 <https://noirlab.atlassian.net/browse/GOATS-311>`_]
- Switched to ``dramatiq`` for task management: GOATS now uses
  ``dramatiq`` for background tasks due to its support for aborting
  running tasks, a feature not available in ``huey``.
  [`#GOATS-315 <https://noirlab.atlassian.net/browse/GOATS-315>`_]



Bug Fixes
---------

- Fixed websocket connection issue: Resolved a bug where websockets
  failed to open on the DRAGONS run page, restoring functionality for
  notifications and download progress updates.
  [`#GOATS-314 <https://noirlab.atlassian.net/browse/GOATS-314>`_]

GOATS 24.5.0 (2024-05-28)
=========================



New Features
------------

- Link JS9 button to open file with JS9: Extended the serializer to
  include data URL for JS9.
  [`#GOATS-208 <https://noirlab.atlassian.net/browse/GOATS-208>`_]
- Added serializer tests: Wrote test cases for serializers used to
  validate API requests.
  [`#GOATS-234 <https://noirlab.atlassian.net/browse/GOATS-234>`_]
- Added api view tests: Wrote test cases for API viewsets.
  [`#GOATS-239 <https://noirlab.atlassian.net/browse/GOATS-239>`_]
- Enhanced UI with modal to display header: Implemented buttons to
  display modals with detailed file headers and to eventually trigger
  JS9 views. Added event listeners for smooth modal interactions and
  developed a function to build reusable modals.
  [`#GOATS-246 <https://noirlab.atlassian.net/browse/GOATS-246>`_]
- Changed DRAGONS run initialization: Extended backend logic to disable
  all bias files outside a specified day range of the observations
  during the initialization of a DRAGONS run. Optimized number of
  database queries when creating a DRAGONS run.
  [`#GOATS-257 <https://noirlab.atlassian.net/browse/GOATS-257>`_]
- Enhanced file retrieval with header inclusion: Added a query
  parameter, ``?include=header``, to include header information for
  files in DRAGONS runs.
  [`#GOATS-258 <https://noirlab.atlassian.net/browse/GOATS-258>`_]
- Added DRAGONS recipes and primitives API v1: Implemented REST API
  endpoints for DRAGONS recipes and primitives. The system now includes
  serializers for filtering by query parameters. Models were structured
  to connect recipes with primitives, allowing users to enable or
  disable individual primitives. This version supports only default
  recipes.
  [`#GOATS-259 <https://noirlab.atlassian.net/browse/GOATS-259>`_]
- Developed interactive DRAGONS recipe cards: Constructed interactive
  recipe cards for DRAGONS, featuring a built-in code editor for dynamic
  user customization. Also implemented a logger widget for real-time log
  monitoring. Created a utility class for common JavaScript
  functionalities and modified the backend by removing the storage of
  individual Primitives.
  [`#GOATS-261 <https://noirlab.atlassian.net/browse/GOATS-261>`_]
- Linked header API to modal display: Connected backend header API with
  modal UI to enable header information display when a button is
  clicked. Improved the header information presentation and error
  handling.
  [`#GOATS-263 <https://noirlab.atlassian.net/browse/GOATS-263>`_]
- Linked run selector to recipe card generator: The DRAGONS run selector
  now dynamically updates the displayed recipes when a new run is
  selected.
  [`#GOATS-264 <https://noirlab.atlassian.net/browse/GOATS-264>`_]
- Moved Ace editor local: Served Ace editor from app, removing CDN
  dependency.
  [`#GOATS-266 <https://noirlab.atlassian.net/browse/GOATS-266>`_]
- Added daily conda caching: Implemented a GitHub action to create and
  cache the goats conda environment daily for quicker testing.
  [`#GOATS-270 <https://noirlab.atlassian.net/browse/GOATS-270>`_]
- Extended models tests: Added comprehensive tests for newer models in
  GOATS.
  [`#GOATS-271 <https://noirlab.atlassian.net/browse/GOATS-271>`_]
- Added workflow to generate releases and update version.
  [`#GOATS-278 <https://noirlab.atlassian.net/browse/GOATS-278>`_]



Changes
-------

- Allow changing DRAGONS setup files names: Users can now change the
  DRAGONS setup files names. Removed the ability to change the log file
  name and removed from form. Added helper functions to get the path of
  DRAGONS setup files.
  [`#GOATS-250 <https://noirlab.atlassian.net/browse/GOATS-250>`_]
- Changed “Unknown” to “Other” for the file type when extracting file
  metadata.
  [`#GOATS-256 <https://noirlab.atlassian.net/browse/GOATS-256>`_]



Bug Fixes
---------

- Fixed bug in JS9 to ensure correct color for labels.
  [`#GOATS-208 <https://noirlab.atlassian.net/browse/GOATS-208>`_]
- Fixed file count and duplicate entries: Corrected the bug in the total
  file count calculation and prevented duplicates in the list of files
  downloaded to ensure an accurate count.
  [`#GOATS-247 <https://noirlab.atlassian.net/browse/GOATS-247>`_]
- Fixed JS9 and Ace conflict: Used no-conflict Ace with own namespace.
  [`#GOATS-256 <https://noirlab.atlassian.net/browse/GOATS-256>`_]

GOATS 24.04.0 (2024-04-26)
=========================-



New Features
------------

- Add toggle for file enable/disable: Checkbox functionality was added
  to allow users to enable or disable files for DRAGONS reduction runs.
  Additionally, a CSS class was introduced to limit the size of tables
  when displaying large lists of files.
  [`#GOATS-209 <https://noirlab.atlassian.net/browse/GOATS-209>`_]
- Implemented file list generation: Version 1 of generating the file
  list for users was implemented, focusing on both frontend and backend
  development. This initial version is set to be revised based on user
  feedback.
  [`#GOATS-237 <https://noirlab.atlassian.net/browse/GOATS-237>`_]
- Switched to ``ruff`` for faster linting and formatting.
  [`#GOATS-254 <https://noirlab.atlassian.net/browse/GOATS-254>`_]



Changes
-------

- Refactored API structure: Updated API endpoints and class names for
  DRAGONS reduction. The code now uses a flat REST API structure,
  enabling filtering via query parameters. For more details, access
  ``/api/`` in debug mode to explore possible endpoints. [`#
  GOATS-235 <https://noirlab.atlassian.net/browse/%20GOATS-235>`_]
- Updated GitHub action to use conda environment with DRAGONS: The
  GitHub action for running unit tests has been fixed by using the
  ``goats`` conda environment. The environment is cached to reuse builds
  if it has not changed.
  [`#GOATS-240 <https://noirlab.atlassian.net/browse/GOATS-240>`_]
- Refactored frontend for efficiency: Combined setup steps and
  streamlined file listing for DRAGONS runs. Changed the timing of
  metadata extraction from data products to occur during downloading
  from GOA. This update ensures that metadata is always refreshed in
  tandem with data product updates, leading to faster loading and
  listing of file metadata.
  [`#GOATS-243 <https://noirlab.atlassian.net/browse/GOATS-243>`_]
- Refactored DRAGONS setup to MVC: Enhanced the DRAGONS run setup
  process by adopting the Model-View-Controller architecture, improving
  reactivity and maintainability of components.
  [`#GOATS-244 <https://noirlab.atlassian.net/browse/GOATS-244>`_]

GOATS 24.03.0 (2024-03-25)
=========================-



New Features
------------

- DRAGONS integration and conda environment creation: DRAGONS is now
  part of the GOATS stack. A dedicated Conda environment file,
  ``environment.yml``, is available for easy installation by users
  cloning the repository. Additionally, the stack now includes a Redis
  server to support the latest changes in GOATS infrastructure.
  [`#GOATS-210 <https://noirlab.atlassian.net/browse/GOATS-210>`_]
- Add dark mode toggle to navbar: Added a dark mode toggle to the navbar
  using Halfmoon UI as a CSS dependency.
  [`#GOATS-212 <https://noirlab.atlassian.net/browse/GOATS-212>`_]
- Real-time communication enhanced: Implemented real-time communication
  between the backend and frontend using Django Channels and Redis.
  [`#GOATS-213 <https://noirlab.atlassian.net/browse/GOATS-213>`_]
- Extend CLI for Redis setup and running: Extended the ``install`` CLI
  to allow users to setup the Redis server. Modified the ``run`` CLI to
  run the Redis server in a separate thread alongside GOATS and Huey.
  [`#GOATS-216 <https://noirlab.atlassian.net/browse/GOATS-216>`_]
- Switched to Django Channels: Enhanced downloads and notifications
  using WebSocket communication. The download user interface was
  refactored to improve the overall user experience. Toast popups were
  introduced for real-time notifications. Gevent was removed to address
  and resolve asynchronous operation issues encountered with Django
  Channels.
  [`#GOATS-219 <https://noirlab.atlassian.net/browse/GOATS-219>`_]
- Implemented DRAGONS setup and config: Added a new Django model and
  serializer for DRAGONS run setup, enhancing the platform’s ability to
  handle DRAGONS reduction configurations asynchronously through the web
  interface. Initiated REST framework setup to streamline data exchange.
  [`#GOATS-230 <https://noirlab.atlassian.net/browse/GOATS-230>`_]

GOATS 24.02.0 (2024-02-26)
=========================-



New Features
------------

- Extended error handling in OCSClient: The update introduces a
  dictionary return type for OCSClient methods, now including a
  ‘success’ key to clearly indicate the outcome of requests.
  Additionally, a ‘return_raw_data’ option has been implemented,
  allowing the inclusion of raw XML responses in the returned payload.
  [`#GOATS-180 <https://noirlab.atlassian.net/browse/GOATS-180>`_]
- Passwords for external services are securely stored using encryption
  to enhance data security.
  [`#GOATS-194 <https://noirlab.atlassian.net/browse/GOATS-194>`_]
- Implement key retrieval in Gemini facility: Added utility functions to
  retrieve keys based on user and identifier.
  [`#GOATS-196 <https://noirlab.atlassian.net/browse/GOATS-196>`_]
- Customizable server address and port: Users can now specify the
  address and port to run GOATS, accepting formats like ‘8000’,
  ‘0.0.0.0:8000’, or ‘192.168.1.5:8000’.
  [`#GOATS-88 <https://noirlab.atlassian.net/browse/GOATS-88>`_]



Bug Fixes
---------

- Correctly handle missing “value” in parameter set from XML data from
  OCS: The OCSParser received enhancements to effectively handle missing
  values in nested XML elements and improved its key naming strategy to
  utilize both the value and type of parameter sets for clearer and more
  accurate data representation.
  [`#GOATS-200 <https://noirlab.atlassian.net/browse/GOATS-200>`_]

GOATS 24.01.0 (2024-01-26)
=========================-



New Features
------------

- Add CLI data product save location: Implemented a new option in the
  CLI to specify the save directory ``--media-dir`` for data products.
  [`#GOATS-174 <https://noirlab.atlassian.net/browse/GOATS-174>`_]
- Implemented Gemini OCS communication client: Added XML-RPC and URL
  endpoint handling in the OCS client and created a parser to convert
  XML data into dictionaries suitable for web view presentation.
  [`#GOATS-179 <https://noirlab.atlassian.net/browse/GOATS-179>`_]
- Implemented Gemini ID parsing: Added ``GeminiID`` class to parse and
  handle both program and observation IDs for use in ``OCSClient``,
  enhancing ID management and validation.
  [`#GOATS-187 <https://noirlab.atlassian.net/browse/GOATS-187>`_]
- Implemented key models for OCS API access: Added UserKey and
  ProgramKey models to manage API keys for OCS queries. Extended
  GeminiID to include class methods for validating program and
  observation IDs.
  [`#GOATS-189 <https://noirlab.atlassian.net/browse/GOATS-189>`_]
- Implemented key management frontend: Enhanced the Gemini OT interface
  with new views and forms for key management.
  [`#GOATS-191 <https://noirlab.atlassian.net/browse/GOATS-191>`_]



Changes
-------

- Switched to temporary directory usage: ``GOATS`` now downloads and
  unpacks archive data into a temporary directory, preventing collisions
  during decompression. Additionally, optimized the process of moving
  downloaded files to the destination folder by implementing
  parallelization.
  [`#GOATS-169 <https://noirlab.atlassian.net/browse/GOATS-169>`_]



Bug Fixes
---------

- Fixed client availability for xmlrpc: Resolved an issue where the
  client was not correctly set up for XML-RPC communication, ensuring
  proper functioning of remote procedure calls. Expanded testing with
  remote data to avoid more issues.
  [`#GOATS-188 <https://noirlab.atlassian.net/browse/GOATS-188>`_]

GOATS 23.12.0 (2023-12-22)
=========================-



New Features
------------

- Implemented Huey for background tasks: Integrated Huey, a lightweight
  Python task queue, into GOATS to handle background tasks using
  sqlite3. This addition streamlines the data download process,
  eliminating the need for users to endure unresponsive periods during
  downloads and keeps the application lightweight by avoiding complex
  libraries.
  [`#GOATS-129 <https://noirlab.atlassian.net/browse/GOATS-129>`_]
- Implemented navbar download display and recent downloads view:
  Introduced a new update mechanism in the navbar for displaying
  background downloads across all pages using polling and implemented a
  new view for accessing recent downloads.
  [`#GOATS-157 <https://noirlab.atlassian.net/browse/GOATS-157>`_]
- Allowed editing of query names in query list view.
  [`#GOATS-78 <https://noirlab.atlassian.net/browse/GOATS-78>`_]



Changes
-------

- Implemented dark mode and enhanced UI flexibility: Switched to dark
  mode for GOATS, limited to light or dark because bootstrap 4 does not
  support switching using themes. Integrated Font Awesome icons to
  improve the user interface aesthetics and enabled setting Plotly theme
  from Django settings for customizable visualizations.
  [`#GOATS-109 <https://noirlab.atlassian.net/browse/GOATS-109>`_]
- Modified view for observations: Included the target sidebar in the
  observation view to provide a cohesive user experience, enabling users
  to see target information alongside specific observation details.
  [`#GOATS-112 <https://noirlab.atlassian.net/browse/GOATS-112>`_]
- Enhanced GOATS CLI for worker management: Extended the GOATS
  command-line interface to include the ``--workers`` option in the
  ``goats run`` command, enabling users to spin up or down \`greenlet`\`
  workers as needed. This feature allows for flexible worker management
  while maintaining a lightweight footprint, though users should be
  cautious not to start too many or too few workers.
  [`#GOATS-129 <https://noirlab.atlassian.net/browse/GOATS-129>`_]
- Change data product storage organization: Data products are now
  organized by observation ID folders, nested under target and facility
  folders.
  [`#GOATS-156 <https://noirlab.atlassian.net/browse/GOATS-156>`_]
- Improved target deletion process: Enhanced deletion of targets now
  includes removal of all associated observation records and their data
  products.
  [`#GOATS-170 <https://noirlab.atlassian.net/browse/GOATS-170>`_]



Bug Fixes
---------

- Fixed a bug in TOMToolkit where the time was incorrectly displayed
  with the month instead of the minute.
  [`#GOATS-166 <https://noirlab.atlassian.net/browse/GOATS-166>`_]

GOATS 23.11.0 (2023-11-27)
=========================-



New Features
------------

- Added data product type support.
  [`#GOATS-117 <https://noirlab.atlassian.net/browse/GOATS-117>`_]
- Enhanced GOA query feedback: Extended the GOA query functionality to
  construct and return comprehensive download information. This
  enhancement includes detailed feedback to GOATS users regarding the
  status of their queries, encompassing error notifications, the count
  of downloaded files, and alerts about potentially missed files due to
  the absence of user authentication.
  [`#GOATS-122 <https://noirlab.atlassian.net/browse/GOATS-122>`_]
- Added calibration radio button to ``GOA`` query form: Introduced an
  option to include, exclude, or solely download calibration data for an
  observation ID.
  [`#GOATS-123 <https://noirlab.atlassian.net/browse/GOATS-123>`_]
- Added GOA observation ID URL: Implemented a new feature to display a
  URL for GOA observation ID on the observation page for viewing
  available data files.
  [`#GOATS-152 <https://noirlab.atlassian.net/browse/GOATS-152>`_]
- Enhanced observation record management: Introduced a new view to
  efficiently handle the deletion of all data products associated with
  an observation record. This update includes a confirmation page for
  deletion operations, ensuring user confirmation before proceeding with
  data removal. Additionally, the update fixes a typo and improves
  permission handling for both ``GET`` and ``POST`` requests for
  deleting all data products, enhancing the overall user experience and
  security.
  [`#GOATS-158 <https://noirlab.atlassian.net/browse/GOATS-158>`_]



Changes
-------

- Updated URL to reflect active tab: Enhanced the target page to modify
  the URL in accordance with the currently active tab, ensuring that
  refreshing the page maintains the user’s selected tab.
  [`#GOATS-159 <https://noirlab.atlassian.net/browse/GOATS-159>`_]



Bug Fixes
---------

- Simplified redirecting users to the target list view for consistency
  and better UX.
  [`#GOATS-126 <https://noirlab.atlassian.net/browse/GOATS-126>`_]
- Fixed thumbnail deletion for data products: Resolved a bug where data
  product thumbnails were not being deleted properly along with the data
  product, leading to multiple copies.
  [`#GOATS-154 <https://noirlab.atlassian.net/browse/GOATS-154>`_]



Enhancements
------------

- Enhanced download and decompression performance: Optimized the process
  for downloading and decompressing tar files from GOA, significantly
  reducing the time required. Implemented streaming for data downloads,
  which minimizes memory usage for large files.
  [`#GOATS-155 <https://noirlab.atlassian.net/browse/GOATS-155>`_]

GOATS 23.10.0 (2023-10-26)
=========================-



New Features
------------

- Integrate Firefox add-on: ``antares2goats`` hosted on Firefox has been
  integrated into ``GOATS``. Users will be able to install the browser
  add-on, configure the token, and use the add-on without issue.
  [`#GOATS-110 <https://noirlab.atlassian.net/browse/GOATS-110>`_]
- ``astroquery`` and ``GOATS`` enhanced for calibration files: Extended
  ``astroquery`` to download associated calibration files as a tar
  archive. ``GOATS`` now automatically downloads and ingests these files
  for an observation record into saved data products.
  [`#GOATS-118 <https://noirlab.atlassian.net/browse/GOATS-118>`_]
- Added observation and thumbnail deletion: Added the ability to delete
  observations from a target and fixed a bug to correctly delete
  associated thumbnails from data products.
  [`#GOATS-121 <https://noirlab.atlassian.net/browse/GOATS-121>`_]
- GOA Public Data Connection and Gemini Update: Introduced GOA
  connection for public data. Added query features. Improved Gemini
  facility documentation and code quality. Extended astroquery for
  future integration.
  [`#GOATS-6 <https://noirlab.atlassian.net/browse/GOATS-6>`_]
- GOA Proprietary Data Connection and Gemini Update: Introduced GOA
  connection for proprietary data. Added GOA credential management.
  [`#GOATS-7 <https://noirlab.atlassian.net/browse/GOATS-7>`_]



Changes
-------

- Removed CLI for installing extension: Due to Chrome being the only
  browser to be able to install an extension from the CLI, removing all
  references and code to install from the CLI. Users will only be able
  to install the ``antares2goats`` extension via the extension store.
  [`#GOATS-111 <https://noirlab.atlassian.net/browse/GOATS-111>`_]
- Improved GOATS frontend: Enhanced the user interface by adding two new
  input fields for GOA queries. Refined tab views for target management,
  specifically when adding existing observations or updating statuses.
  [`#GOATS-117 <https://noirlab.atlassian.net/browse/GOATS-117>`_]
- Optimized GOA data and overhauled ``astroquery`` for Gemini:
  Implemented compressed and tar files for efficient data retrieval from
  GOA. Completed a major refactoring of the ``astroquery`` package for
  Gemini, in preparation for a future merge into the main ``astroquery``
  project.
  [`#GOATS-119 <https://noirlab.atlassian.net/browse/GOATS-119>`_]



Other
-----

- Add Makefile for ``antares2goats`` packaging: Created a Makefile to
  automate the packaging of ``antares2goats`` into a ZIP file for
  uploading to Firefox and Chrome extension stores.
  [`#GOATS-103 <https://noirlab.atlassian.net/browse/GOATS-103>`_]

GOATS 23.09.0 (2023-09-25)
=========================-



New Features
------------

- Incorporated token support in ``antares2goats``: Integrated token
  authentication to allow users to securely save queries and targets
  from ``ANTARES``. Revamped the Options page for token input.
  [`#GOATS-100 <https://noirlab.atlassian.net/browse/GOATS-100>`_]
- Chrome extension v1: The initial version of the Chrome extension has
  been implemented, paving the way for enhanced browser functionality. A
  custom exception handling mechanism has been integrated within the
  GOATS Click, improving user experience in the command line interface.
  Additionally, a new CLI command facilitates the straightforward
  installation of the Chrome extension, while modifications to the
  ANTARES plugin now allow for direct query creation from the extension.
  To round off these updates, a new view has been established to monitor
  browser extension push notifications.
  [`#GOATS-72 <https://noirlab.atlassian.net/browse/GOATS-72>`_]
- Added CLI command ``install-extension``: CLI framework created so
  users in the future can install the browser extension for GOATS.
  Installation can be done in the ``install`` step or after with
  ``install-extension``.
  [`#GOATS-83 <https://noirlab.atlassian.net/browse/GOATS-83>`_]
- Single-Target Creation via Extension: Enhanced the extension to
  directly create individual targets within ANTARES, eliminating the
  need for query generation.
  [`#GOATS-85 <https://noirlab.atlassian.net/browse/GOATS-85>`_]
- “Select All” feature enhancement: Users can now effortlessly select
  all targets with a single click, streamlining the addition process and
  enhancing user experience. Additionally, the query results have been
  refined to eliminate superfluous information, promoting a cleaner,
  more intuitive interface.
  [`#GOATS-91 <https://noirlab.atlassian.net/browse/GOATS-91>`_]
- Added token authentication: Admins can now generate tokens for
  authentication in the backend of GOATS, facilitating secure
  interactions with the \`antares2goats`\` browser extension.
  [`#GOATS-99 <https://noirlab.atlassian.net/browse/GOATS-99>`_]



Changes
-------

- GOATS Prompt Overhaul: Enhanced user experience during GOATS
  installation and execution with transparent process descriptions and
  progress updates.
  [`#GOATS-67 <https://noirlab.atlassian.net/browse/GOATS-67>`_]
- GOATS ANTARES Broker webpage v1: Enhanced integration with GOATS,
  leveraging the \`antares2goats`\` extension for streamlined
  performance and alignment.
  [`#GOATS-80 <https://noirlab.atlassian.net/browse/GOATS-80>`_]
- Removed non-functional broker plugins: TNS, Fink and LASAIR.
  [`#GOATS-82 <https://noirlab.atlassian.net/browse/GOATS-82>`_]

GOATS 23.08.0 (2023-08-25)
=========================-



New Features
------------

- GOATS CLI: The GOATS CLI was updated to use Python Click, simplifying
  the command-line interface. The CLI is now included with the package
  installation. Use the goats command in the terminal to start.
  [`#GOATS-42 <https://noirlab.atlassian.net/browse/GOATS-42>`_]
- Added v1 of GOATS footer: A custom footer was developed for the GOATS
  platform. The update involved integrating essential elements from the
  ``tom_base/tom_common`` files and initiating the use of custom CSS.
  [`#GOATS-44 <https://noirlab.atlassian.net/browse/GOATS-44>`_]
- Added v1 of GOATS navbar: A custom navbar was developed for the GOATS
  platform.
  [`#GOATS-45 <https://noirlab.atlassian.net/browse/GOATS-45>`_]
- Design initial version of GOATS CSS and layout: Bootstrap serves as a
  foundational element in our project, being a critical component of the
  TOM Toolkit. We leverage its robust framework as a starting point,
  extending and customizing it to create our own distinctive style that
  aligns with our specific needs and branding.
  [`#GOATS-47 <https://noirlab.atlassian.net/browse/GOATS-47>`_]
- Created v1 of GOATS banner: A new banner has been added to display
  site logo and affiliates.
  [`#GOATS-48 <https://noirlab.atlassian.net/browse/GOATS-48>`_]
- Improved CLI for GOATS: The CLI for GOATS now supports a development
  server that allows for real-time template modifications. Additionally,
  shorthand options have been introduced for a more streamlined user
  experience.
  [`#GOATS-51 <https://noirlab.atlassian.net/browse/GOATS-51>`_]



Other
-----

- Tooling for release notes: Added infrastructure to produce useful,
  summarized change logs with ``towncrier``.
  [`#GOATS-22 <https://noirlab.atlassian.net/browse/GOATS-22>`_]
- ``pytest`` GitHub Action Integration: Established automated unit
  testing and initial code coverage assessment. This action, triggered
  on every ‘push’ event, provides continual testing and a basic coverage
  report, laying the groundwork for future integration with Codecov.
  [`#GOATS-24 <https://noirlab.atlassian.net/browse/GOATS-24>`_]
- ``pytest`` infrastructure started: Established a ``pytest``
  infrastructure for ``goats``, introducing robust unit and integration
  tests. This setup enhances the reliability and maintainability of the
  codebase, facilitating more secure code updates and deployments.
  [`#GOATS-25 <https://noirlab.atlassian.net/browse/GOATS-25>`_]
- Standard ``pyproject.toml`` started: Implemented a ``pyproject.toml``
  file for ``goats`` to standardize build tool dependencies,
  streamlining the build process and ensuring consistency across
  different environments.
  [`#GOATS-28 <https://noirlab.atlassian.net/browse/GOATS-28>`_]
- Integrated ``flake8`` in GitHub Actions: Incorporated ``flake8`` into
  the GitHub Actions pipeline, enabling automatic linting checks for
  Python code. This enforces code quality standards across ``goats``.
  [`#GOATS-33 <https://noirlab.atlassian.net/browse/GOATS-33>`_]
- Overrode default TOMToolkit index page and updated ``pyproject.toml``:
  Improved pip installation process, enhancing user interface
  customization for GOATS and project distribution.
  [`#GOATS-43 <https://noirlab.atlassian.net/browse/GOATS-43>`_]
- Optimized GitHub Actions and integrated HTML linting: GitHub Actions
  now operate selectively, with the HTML linter (``htmlhint``) triggered
  when template HTML files change, and unit tests and ``flake8`` checks
  run when Python files change. Additionally, common Jinja templating
  settings are now ignored by the HTML linter, thanks to the updated
  ``htmlhint`` configuration.
  [`#GOATS-53 <https://noirlab.atlassian.net/browse/GOATS-53>`_]
- CSS linting added to GitHub Actions: Used stylelint to ensure CSS code
  quality.
  [`#GOATS-54 <https://noirlab.atlassian.net/browse/GOATS-54>`_]
- JS Testing using ``jest``: Implemented a test suite for JavaScript
  files in the GOATS project using ``jest``. Ensures robust testing
  across the website and integrates GitHub action to run tests
  automatically. A badge has been added to the repository to show the
  test status.
  [`#GOATS-61 <https://noirlab.atlassian.net/browse/GOATS-61>`_]
