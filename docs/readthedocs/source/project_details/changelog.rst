==============
Full Changelog
==============

.. towncrier release notes start
Version 25.8.3 (2025-08-28)
===========================

Documentation
-------------

- Fixed typos in user doc. (`PR #415 <https://github.com/gemini-hlsw/goats/pull/415>`_)


Version 25.8.2 (2025-08-28)
===========================

Changes
-------

- Improved UI for tables when no data to display. Also hide empty select box when no observation groups. (`PR #414 <https://github.com/gemini-hlsw/goats/pull/414>`_)


Documentation
-------------

- Updated deployment guide about PRs on ``goats-infra``. (`PR #411 <https://github.com/gemini-hlsw/goats/pull/411>`_)
- Added ``copybutton`` to documentation to improve UI for users for code blocks. (`PR #412 <https://github.com/gemini-hlsw/goats/pull/412>`_)
- Updated collab list and made minor fixes in user doc. (`PR #413 <https://github.com/gemini-hlsw/goats/pull/413>`_)


Version 25.8.1 (2025-08-28)
===========================

New Features
------------

- Improved the GOATS interface based on user feedback. Updated the navbar layout and styling, added tooltip titles to navbar items, removed the hardcoded active class from the Observations tab view, clarified wording for adding existing observations, added a landing page card for credential setup, updated the CSS library to 2.0.2, and refined the URL resolver for the active tab. (`PR #395 <https://github.com/gemini-hlsw/goats/pull/395>`_)
- Added "View at Archive" button for viewing observations at ``GOA``. Added disabled button for eventually link for viewing observations at ``Gemini Explore``. (`PR #397 <https://github.com/gemini-hlsw/goats/pull/397>`_)


Changes
-------

- Reverted changes from alpha feedback. Added toast on landing page directing users to credential page. Extened toast manager to modify options per toast. (`PR #396 <https://github.com/gemini-hlsw/goats/pull/396>`_)
- Updated title on target detail page to help users understand managing groups better. (`PR #402 <https://github.com/gemini-hlsw/goats/pull/402>`_)
- Bumped the contrast of the border in dark mode around buttons and form inputs to make it easier for users on the GOATS UI. (`PR #409 <https://github.com/gemini-hlsw/goats/pull/409>`_)


Bug Fixes
---------

- Fixed issue when updating credentials. (`PR #401 <https://github.com/gemini-hlsw/goats/pull/401>`_)
- Fixed issue fetching Gemini South shutter status. The Gemini South shutter status is updated from a JSON payload using javascript. Scraping the HTML is not a viable solution and we must instead grab the information from the JSON endpoint. (`PR #403 <https://github.com/gemini-hlsw/goats/pull/403>`_)
- Fixed issue uploading spectrum for Gemini facility. Users before couldn't upload spectrum for Gemini. The issue has been resolved. The correct units are now used and orphaned files are now cleaned up if errors are occured when uploading. (`PR #404 <https://github.com/gemini-hlsw/goats/pull/404>`_)
- Fixed issue plotting GHOST data. Resolved parsing ``DATE-OBS`` and ``TIME-OBS`` header keywords from FITS files. Now cleanly handle missing keywords from Gemini FITS files. (`PR #405 <https://github.com/gemini-hlsw/goats/pull/405>`_)
- Fixed issue plotting IRAF-reduced multi-extension FITS file. (`PR #406 <https://github.com/gemini-hlsw/goats/pull/406>`_)
- Enabled the ``Actions`` button for all uploaded files. Disabled ``JS9`` button for non-FITS files. (`PR #407 <https://github.com/gemini-hlsw/goats/pull/407>`_)
- Added check to restrict plotting of FITS images. (`PR #408 <https://github.com/gemini-hlsw/goats/pull/408>`_)
- Fixed how the timestamp is displayed when plotting the spectrum. (`PR #410 <https://github.com/gemini-hlsw/goats/pull/410>`_)


Documentation
-------------

- Updated user documentation at various places for beta release. (`PR #400 <https://github.com/gemini-hlsw/goats/pull/400>`_)


Version 25.8.0 (2025-08-12)
===========================

New Features
------------

- Added a credential-management page for Las Cumbres Observatory (LCO) and SOAR that lets each user save their personal portal API token in the web interface. Observation submissions and whereever the api key is used now draw from the logged-in user's stored key, falling back to the project-wide key in settings.FACILITIES when necessary. The update introduces a dedicated model, view, template, and navigation link in the user settings, plus accompanying tests, and modifies the LCO and SOAR facility classes so they retrieve the key on a per-user basis. (`PR #369 <https://github.com/gemini-hlsw/goats/pull/369>`_)
- Added ``alpine.js`` and ``htmx.js`` to match ``tomtoolkit`` requirements, which resolved issue with Alias and Tag blocks when creating a target. (`PR #370 <https://github.com/gemini-hlsw/goats/pull/370>`_)
- Added validation for LCO token when saved. (`PR #374 <https://github.com/gemini-hlsw/goats/pull/374>`_)
- Added support for the Transient Name Server (TNS), including a model to store credentials, a corresponding form and view, and a factory for testing. Updated login forms and extended the credential manager UI to support TNS. Also added `tom_tns` as a dependency and included tests for TNS integration. (`PR #377 <https://github.com/gemini-hlsw/goats/pull/377>`_)
- Patched ``tom-tns`` to use per-user credentials when interacting with TNS by using middleware. (`PR #378 <https://github.com/gemini-hlsw/goats/pull/378>`_)
- Added tests for TNS middleware and updated message for unconfigured TNS credentials. (`PR #379 <https://github.com/gemini-hlsw/goats/pull/379>`_)
- Add endpoint to fetch existing observations around target from GOA. This will be used by the frontend so users can easily add observations for a target for Gemini. (`PR #380 <https://github.com/gemini-hlsw/goats/pull/380>`_)
- Added a widget to fetch existing observations from the Gemini Observatory Archive (GOA) near a target's coordinates and link them to the target. (`PR #382 <https://github.com/gemini-hlsw/goats/pull/382>`_)
- Created ``Dependabot`` groups to reduce number of PRs when updating dependencies. (`PR #388 <https://github.com/gemini-hlsw/goats/pull/388>`_)


Changes
-------

- Removed confusing wording about how to import targets from barebones ``tomtoolkit`` library. (`PR #371 <https://github.com/gemini-hlsw/goats/pull/371>`_)
- Removed support for LT, aka BLANCO, telescope from GOATS. This will be enabled when GOATS fully supports this telescope in the future. (`PR #372 <https://github.com/gemini-hlsw/goats/pull/372>`_)
- Changed the visibility of downloading from GOA and reducing data with DRAGONS for observations not associated with Gemini. (`PR #373 <https://github.com/gemini-hlsw/goats/pull/373>`_)
- Fixed url link in the release workflow to point to the correct changelog url in the documentation. (`PR #390 <https://github.com/gemini-hlsw/goats/pull/390>`_)


Version 25.7.0 (2025-07-29)
===========================

New Features
------------

- Added ``pre-commit`` and hooks to run formatters. (`PR #340 <https://github.com/gemini-hlsw/goats/pull/340>`_)
- Extended frontend to display available programs from GPP: Users can now use GPP to fetch the available programs and display in a select widget on the Gemini submit observation page. (`PR #342 <https://github.com/gemini-hlsw/goats/pull/342>`_)
- Added query parameter support for `api/gpp/observations`: Payloads from GPP can be filtered by the program ID to reduce the number of observations returned. (`PR #343 <https://github.com/gemini-hlsw/goats/pull/343>`_)
- Extended GPP app to fetch and display available observations per selected program. (`PR #344 <https://github.com/gemini-hlsw/goats/pull/344>`_)
- Updated ``gpp-client`` to use GOATS-specific queries to aggregate all necessary information for observations. (`PR #348 <https://github.com/gemini-hlsw/goats/pull/348>`_)
- Extended GPP application to display selected observation data: Users can now browse the available programs and observations available. (`PR #351 <https://github.com/gemini-hlsw/goats/pull/351>`_)
- Added prototype for saving, editing, and creating new observation in GPP app. (`PR #352 <https://github.com/gemini-hlsw/goats/pull/352>`_)
- Added "Gemini Explore" to navbar on GOATS. (`PR #354 <https://github.com/gemini-hlsw/goats/pull/354>`_)
- Addressed GPP integration feedback and improved GPP interaction part 1. (`PR #358 <https://github.com/gemini-hlsw/goats/pull/358>`_)
- Users are now notified of missing credentials and GPP connection when starting GPP application. (`PR #359 <https://github.com/gemini-hlsw/goats/pull/359>`_)
- Added ability to save observations pulled from the GOATS/GPP interface. (`PR #362 <https://github.com/gemini-hlsw/goats/pull/362>`_)


Changes
-------

- Switched to production database for GPP: Users will now interact with the production database for GPP rather than the development. (`PR #336 <https://github.com/gemini-hlsw/goats/pull/336>`_)
- Overhauled GitHub workflow for python CI: Format and linting will be checked before proceeding with running the tests. (`PR #341 <https://github.com/gemini-hlsw/goats/pull/341>`_)


Documentation
-------------

- Removed Jira links from changelog: Jira ticket links are now included only in pull requests to keep public changelog entries clean and accessible. (`PR #334 <https://github.com/gemini-hlsw/goats/pull/334>`_)
- Updated user documentation at various places following alpha feedback. (`PR #360 <https://github.com/gemini-hlsw/goats/pull/360>`_)


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

- Added user documentation for Astro Data Lab integration into GOATS. (`PR #329 <https://github.com/gemini-hlsw/goats/pull/329>`_)
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
  
- Enabled automated updates: Configured Dependabot to create pull
  requests for dependency updates.
  
- Replaced Astro Data Lab client: Implemented internal class to remove
  dependency conflicts.
  
- Added nox testing for different python and dependency versions.
  
- Imported ``antares-client`` code: Added ``antares-client`` code
  directly into the repo to avoid dependency issues with ``marshmallow``
  and ``confluent-kafka``.
  

Changes
-------

- Skip building documentation if no changes to ``/docs/readthedocs``
  
- Updated GOATS user documentation (along with the videos) to clarify
  where one can add their GOA credentials.
  
- Updated DRAGONS and dependencies: Updated to DRAGONS 4.0.0 and raised
  the required Python version to 3.12. Also updated other dependencies
  for compatibility.
  

Other
-----

- Updated the GOATS workflow flowchart showing an additional step for
  adding existing Gemini observation and added a miscellaneous page for
  tips and tricks that users might find helpful.
  


GOATS 25.3.0 (2025-03-30)
=========================



New Features
------------

- Ensured worker shutdown in Dramatiq: Added fallbacks to manage worker
  threads, ensuring they were terminated if graceful shutdown failed.
  This prevented orphaned or zombie workers.
  
- Shutdown return code and port checks for Redis: Added shutdown return
  code for Redis and enforced killing child workers if timeout occurs.
  Checked if ports are in use on startup, issuing an error and
  preventing startup if occupied.
  
- Shutdown return code and port checks for Django: Added shutdown return
  code for Django and enforced killing child workers if timeout occurs.
  Checked if ports are in use on startup, issuing an error and
  preventing startup if occupied.
  
- Shutdown return code Dramatiq: Added shutdown return code for Dramatiq
  and enforced killing child workers if timeout occurs.
  
- Cleanly shut down DRAGONS in worker threads: Removed leftover orphaned
  processes on GOATS shutdown using custom middleware.
  
- Check ETISubprocess before shutdown: Prevented redundant creation and
  destruction of singleton.
  



Changes
-------

- Credential storage redesign: Improved how users store credentials and
  generate tokens for the browser extension. Added a popover explaining
  the credential manager in the user management page.
  

GOATS 25.2.2 (2025-02-28)
=========================



New Features
------------

- Created GitHub Pages for project: Set up a GitHub Pages site for GOATS
  to host documentation and Conda packages.
  
- Added barebones content for GitHub Pages: Added initial HTML
  structure, Bootstrap styling, and essential links.
  
- Created an empty Conda channel: Prepared ``gh-pages/conda/`` for
  hosting Conda packages with ``conda index``.
  

GOATS 25.2.1 (2025-02-27)
=========================



New Features
------------

- Included tooltips to explain “Create Groupings” and “Use All Files for
  Observation ID” in the DRAGONS app.
  
- Add DRAGONS docs link: Linked to the DRAGONS documentation based on
  the installed version in the reduction app. Defaults to the base
  documentation if no version is found.
  
- Open browser on GOATS start: GOATS now opens in the default browser
  when launched. Users can specify a browser via CLI, and if none is
  given, the system default is used.
  
- Added model for encrypted Astro Datalab credentials.
  
- Extend user page: Added form to store and validate Astro Datalab
  credentials. Users receive feedback on whether their credentials are
  correct.
  
- Build UI for sending files: Implemented UI for sending data files to
  Astro Datalab in the “Manage Data” tab in the target view. Added a
  dropdown menu for actions. Placeholder made for async API calls.
  
- Added API backend for Astro Datalab: Allowed users to send data files
  to Astro Datalab with their credentials.
  
- Linked UI with backend to send files to Astro Datalab. Updated the
  interface to show a process indicator during file transfer and provide
  feedback on success or failure.
  
- Created Astro Datalab landing page: Added a new Astro Datalab page
  with an associated Django view.
  
- Added pytest code coverage reporting.
  
- Added code coverage badge to README and refactored pull request
  template.
  
- Migrated ReadTheDocs to main repo: Transferred documentation from the
  ``goats-docs`` repository to the GOATS main repository for centralized
  management.
  



Changes
-------

- Disable GOA query for incomplete observations: Prevented users from
  submitting a GOA query if the observation status was not “Observed”.
  Added a backend check to issue a warning if the restriction is
  bypassed.
  
- Added last modified timestamp: Processed files in the DRAGONS app now
  include a last modified timestamp.
  
- Improve target name handling: Long target names now scroll instead of
  breaking the layout. Edit and delete buttons are now in a separate div
  for better responsiveness.
  
- Updated dependencies: Upgraded to the latest tomtoolkit release,
  refactored pyproject.toml, and removed redundant code now included in
  tomtoolkit.
  
- Refactored test infrastructure: Separated tests and optimized
  execution.
  
- iframe support for Astro Data Lab: Replaced static image link with an
  iframe to display the most recent version of the Astro Data Lab
  webpage. Added a failsafe text link for accessibility.
  
- iframe support for ANTARES: Replaced static image link with an iframe
  to display the most recent version of the ANTARES webpage. Added a
  failsafe text link for accessibility.
  
- Refactored GitHub workflows to run on PR and merge to main.
  

Bug Fixes
---------

- Fixed test slowdown bug: Resolved issue causing excessive test
  execution time when querying DRAGONS version.
  
- Corrected typo in Astro Data Lab name.
  

GOATS 25.1.1 (2025-01-30)
=========================



New Features
------------

- Add delete run functionality: Enabled a delete button for DRAGONS
  runs, allowing users to reclaim disk space. Extended the API to
  support run deletions.
  
- Added TNS query support: Developed class to query TNS objects and
  return payload.
  
- Updated TNS harvester: Modified harvester to use the TNSClient for
  object querying.
  
- Added LICENSE to repository.
  
- Add default recipe card with instructions: Introduced a default card
  that guides users to select a recipe. Provides tips on starting and
  stopping DRAGONS reduction, modifying recipes, and viewing logs.
  
- Show processed files in run directory: Renamed “Output Files” to
  “Processed Files” across classes and objects. Added button to view
  files in JS9 and display headers in a modal. Introduced
  ``DataProductMetadata`` model to minimize astrodata reads.
  
- Added user docs button: Added a button to the navbar that opens the
  user documentation in a new tab.
  
- Improved facility status page: Fetches and displays Gemini North and
  South status and updated weather URLs.
  
- Add filesearch textbox in Manage Data: Enhanced file management with a
  search box to filter files by filename and path.
  
- Improve cancel functionality: Enabled multiple attempts to stop
  background tasks during DRAGONS reduction if the initial cancellation
  fails.
  
- Fetch initial running reductions: Added functionality to retrieve and
  display initial running reductions on the DRAGONS page. Users can now
  see the current status of reductions immediately upon page load.
  
- Added responsive table format for long Target values in view.
  
- Added calibration file viewing and header display: Implemented support
  for viewing calibration files through the DRAGONS interface with JS9
  and displaying FITS header information.
  



Changes
-------

- Used local fontawesomefree: Incorporated FontAwesome into GOATS static
  assets and removed external Python dependency.
  
- Removed Update Broker Data button: Removed the “Update Broker Data”
  button from the target list view.
  
- Refactored product IDs: Changed how products are stored by using file
  paths to handle files in different directories with the same product
  IDs. 
- Updated environment.yaml for latest DRAGONS: Updated the environment
  file to include the latest DRAGONS release with patches specific to
  GOATS.
  
- Remove tom-antares dependency: Ingested its functionality directly
  into GOATS due to extensive customizations and installation
  complexities.
  



Bug Fixes
---------

- Fixed file deletion bug: Correctly built full path for processed files
  to delete.
  
- Handle duplicate file entries in checksum files: Fixed an issue where
  duplicate file entries in GOA checksum files caused errors during
  downloading and decompression. The process now skips duplicates and
  continues without interruption.
  
- Set astroquery version: Fixed SIMBAD query compatibility by pinning
  astroquery to a working version.
  
- Fixed calibration path handling: Resolved issue with spaces in
  calibration database paths causing errors during DRAGONS reduction.
  
- Fixed ANTARES queries: Ensured user queries can be renamed properly
  and querying with elastic search works.
  
- Fix issue with conda environment with GitHub Actions.
  
- Added functionality to handle decompression of bz2 FITS files uploaded
  into the calibration database. Previously, silent errors occurred due
  to improper handling of decompression and file placement.
  
- Workaround for DRAGONS version mismatch: Addressed an issue where the
  DRAGONS version reported by pip differed from the conda-installed
  version by implementing logic to pull the version directly from conda.
  

GOATS 24.12.0 (2024-12-21)
==========================



New Features
------------

- Implemented dataproduct visualizer template tag: Designed and
  implemented a templatetag to fetch and display dataproducts for
  visualization based on data type.
  
- Add photometric data plotting: Refactored plotting logic and enhanced
  interface usability.
  
- Added tests for API endpoints added for data visualizer.
  
- Connected backend API with frontend fetching: Implemented async
  fetching to dynamically retrieve or process dataproducts for plotting.
  
- Added Plotly.js for dynamic plotting: Integrated Plotly.js for
  interactive plotting in the dataproduct visualizer and implemented
  styling to toggle between dark and light themes.
  
- Added django filter for reduced dataproducts: Allowed querying of
  reduced data by product ID and data type.
  
- Added plotting function to update plot with requested spectroscopy
  data.
  
- Extended Gemini facility class functionality: Added methods for
  reading FITS headers and handling Gemini-specific image data.
  
- Added search field for file names: Implemented client-side filtering
  for the File Name column on the data visualizer to allow users to
  quickly find files.
  
- Update plot with axis unit handling and editable labels: Added support
  to display correct units for Wavelength and Flux if available in FITS
  files. Defaulted to “Wavelength” and “Flux” when units are missing.
  Made axis labels editable for manual input with CSV files for both
  photometry and spectroscopy.
  
- Added editable axis ranges: Enabled users to click directly on x and y
  axis end values to edit their ranges.
  
- Added user feedback when no files matched filter criteria during file
  plotting.
  



Changes
-------

- Update photometry tab message: Revised message to include supported
  CSV format with a link to Manage Data.
  
- Update spectroscopy tab message: Revised message to include supported
  FITS and CSV formats with a link to Manage Data.
  



Bug Fixes
---------

- Dynamic WebSocket URL generation: Built WebSocket URL from window and
  request.
  
- Converted endpoint to API: Browser extension endpoint now functions as
  a fully integrated API endpoint with proper token authentication to
  validate posts.
  
- Fixed issue with Django template and airmass plot.
  
- Fixed typo with filter backend in the settings template.
  
- Implemented workaround for CORS-related issue with plotting.
  
- Fixed issue with url for fetching and plotting data.
  

GOATS 24.11.0 (2024-11-27)
==========================



New Features
------------

- Added navbar to observation page: Implemented a new template tag to
  include the navigation bar on the observation page for targets.
  
- Added GHOST in DRAGONS application: Implemented features in DRAGONS
  application to debundle and reduce GHOST data. Bugfix for file group
  selection and improved astroquery login verification.
  
- Enhanced file fetch control: Added a checkbox to the UI that allows
  users to fetch all files for an observation ID, disabling the default
  filters of observation class, type, and object name. This change
  grants users full control over the selection of files for use in
  DRAGONS recipe reductions.
  
- Renamed ‘uparms’ for clarity and added a tooltip to assist users in
  using it correctly.
  
- Added API endpoint for DRAGONS reduced images: Implemented a new
  processor to extract data from DRAGONS reduced images and extended
  TOMToolkit functions to support new requirements.
  



Changes
-------

- Refactored codebase for better organization.
  
- Removed unnecessary data types for data products: Only ‘fits_file’ is
  needed for DRAGONS reduction.
  
- Hide UI elements without run selection: The visibility of the output
  files and calibration database manager is now controlled by the
  selection of a run ID.
  
- Sort files by observation type for DRAGONS compatibility: Ensured the
  first file in the list matches the recipe’s observation type to
  prevent mismatches with tags and primitives.
  



Bug Fixes
---------

- Fixed observation record ID handling: Corrected an issue where a
  hardcoded observation ID from testing persisted into production,
  ensuring that only runs associated with an actual observation record
  are displayed.
  
- Fixed filter expression and ID uniqueness bugs: Resolved an issue
  where user-provided filter expressions were not correctly used in
  filtering and grouping available files. Additionally, improved the
  uniqueness of file checkbox IDs by incorporating more identifying
  information, addressing an issue uncovered when allowing user access
  to all files.
  
- Fixed recipe and primitive extraction for DRAGONS application:
  Extracted primitives now include all lines, ensuring comments and
  docstrings are no longer ignored.
  
- Added safeguard for missing primitive params in ``showpars``: Ensured
  DRAGONS/GOATS ``showpars`` handles cases where parameters for specific
  primitives are absent.
  
- Fixed query order operations: Corrected handling of logical operations
  in expressions. Implemented using the ``ast`` module to parse
  expressions more reliably. Updated logical operators to be
  case-sensitive as required by ``ast``. Removed “not” but added “!=” as
  a valid operation. Updated UI help documentation to reflect these
  changes.
  
- Bugfix for numerical astrodata descriptors: Allowed numerical values
  for astrodata_descriptors like ‘object’. Users now need to enclose
  strings in quotes for correct parsing, while numerical values should
  be entered without quotes. Added a default return to ensure consistent
  API responses when no files are found during grouping.
  

GOATS 24.10.0 (2024-10-29)
==========================



New Features
------------

- Added API backend for output file listing: Implemented functionality
  to list output files and their last modified timestamps from a
  ``DRAGONSRun``.
  
- Linked API with UI for output directory display: Integrated the API
  and UI to enhance visibility of the output file directory. Added user
  feedback mechanisms for updates and refresh actions.
  
- Added API file management for DRAGONS runs: Extended the system to
  allow adding files from the output directory of a DRAGONS run to the
  saved dataproducts. Users can now also remove these files; doing so
  deletes both the dataproduct entry and the file itself.
  
- Linked backend and frontend for DRAGONS output file operations: The
  integration now allows adding output files to data products and
  removing them directly through the frontend interface.
  
- Designed uparms UI for DRAGONS recipe modification: Implemented a user
  interface to edit ‘uparms’ for recipes, requiring ‘edit’ mode
  activation similar to existing recipe and primitive modifications.
  
- Extended DRAGONS recipe “uparms” handling in API: Updated the backend
  to support modifications to “uparms” for DRAGONS recipe reductions.
  The update includes parsing “uparms” from string format into Python
  objects, enabling dynamic parameter adjustments.
  
- Connected frontend to backend for using uparms in DRAGONS reduction.
  
- Refactored DRAGONS logger: Improved efficiency and cleaned up code.
  
- Refactored progress bar for recipes: Improved maintainability and
  readability of the code handling the recipe progress bar.
  
- Fix versioning issues: Resolved bugs in tomtoolkit, GOA, and
  astroquery. Fixed tomtoolkit version to prevent future compatibility
  issues.
  



Changes
-------

- Major refactor of DRAGONS app: Accommodated changes to recipe and file
  nesting.
  
- Refactor run panel UI: Improved loading animation and user feedback
  during actions.
  
- Refactored files table: Improved display of groups and file toggling
  for runs.
  
- Moved API to singleton design: Simplified DRAGONS API by converting it
  to a singleton pattern and made it globally accessible to all classes.
  Adjusted how default options are constructed.
  
- Refactored modal: Improved modal code for maintainability.
  
- Refactored dragons app folder: Consolidated and organized code in the
  dragons app folder for better modularity and maintainability.
  
- Refactored available recipes logic: Refactored the available recipes
  structure to simplify code and improve maintainability. Added a global
  event dispatcher to notify when a recipe is changed, allowing other
  components to react accordingly.
  
- Refactored available files for observation type: Simplified the
  structure of available files by refactoring the code. Introduced
  helper functions to create unique IDs using observation type,
  observation class, and object name.
  
- Refactored observation data organization: Enhanced how observation
  type, observation class, and object name organize recipes and files.
  Added a new endpoint to set up initial data for recipes and files for
  a specific run.
  
- Refactored API grouping control: The API now allows users to specify
  fields to group for better DRAGONS use.
  
- Refactored file identifiers in accordions: Refactored how files are
  displayed in accordions based on observation type, class, and object
  name. Introduced a helper class to manage these identifiers
  efficiently.
  
- Refactored available files handling: Enhanced file filtering
  mechanisms and prepared for future expansion to include all files.
  Callbacks for filtering processes were integrated to ensure smooth
  operations.
  
- Refactored recipe reduction.
  
- General cleanup: Removed unnecessary data storage and added
  documentation.
  
- Refactored WebSocket updates and app initialization.
  

GOATS 24.9.0 (2024-09-20)
=========================



New Features
------------

- Enabled extended downloading from GOA: Added capability to download
  and link missing data from other observation IDs or calibration files.
  Users can now use standard stars, BPMs, and other resources from other
  observation IDs for use in DRAGONS reduction.​
  
- Updated file UI interactions: Connected UI components and API fetch
  functionalities to update, filter, group, and query available files
  for DRAGONS reductions.
  
- Added date and time filtering: Enhanced DRAGONS file filtering by
  adding support for date, time, and datetime descriptors. Comprehensive
  tests were implemented for the new astrodata descriptor filtering
  features.
  
- Refreshed dropdown on selection: Added a handler to clear the input
  text and refresh available options whenever a user selects an item
  from the multiselect dropdown for descriptor groups.
  
- Included file count for ‘All’: Displayed the number of files when
  filtering to reduce confusion between filtering only and grouping with
  filtering.
  
- Extended background worker timeout and made configurable: Allowed
  users to configure the time limit for background tasks via Django
  settings, enabling better control over task execution duration.
  
- Added truncation for grouped values: Grouping values are now truncated
  to include file counts.
  
- Enhanced UI with informational tooltips: Added clickable icons to the
  DRAGONS frontend that display tooltips explaining strict filtering
  options and available logical operators for filter expressions.
  
- Added select-all/deselect-all functionality for files for observation
  types.
  
- Design UI for calibration database: Completed the UI design and
  development for the calibration database.
  
- Added file management capabilities to the calibration database: Users
  can now add files to, remove files from, and list files in the
  calibration database directly via the API.
  
- Connected frontend with backend API for file removal and refresh:
  Integrated the frontend user interface with the backend API to enable
  file removal from the calibration database. Added a refresh button to
  update the database view.
  
- Added file upload support: Enabled uploading files to the calibration
  database for DRAGONS reduction.
  
- Developed output files UI: Developed a user interface container to
  manage and display output files for a DRAGONS reduction.
  
- Enhanced file upload feedback and usability: Added a new column in the
  user interface to indicate which files were uploaded by users. Fixed
  an issue that prevented the re-upload of the same file consecutively.
  



Changes
-------

- Improved error handling for GOA downloads: Added error handling for
  file downloads with updates to the webpage’s progress bar to reflect
  errors. Errors are now logged within the download model, providing
  users with detailed error messages when issues occur.​
  
- Sanitized run IDs for folder names: When a user provides a run ID for
  DRAGONS reduction, all characters unsuitable for a folder directory
  name are removed, and spaces are replaced with underscores.
  
- Removed old bias filtering: Replaced with a more powerful file
  filtering system.
  
- Enhanced product ID uniqueness: Made the product ID for a dataproduct
  more robust to fix integrity issues when adding the same dataproduct
  under different observations and targets.
  
- Refactored run table classes for clarity and improve the
  maintainability of the DRAGONS UI.
  



Bug Fixes
---------

- Removed limit on multiselect dropdown options: The maximum number of
  options displayed in the multiselect dropdown has been removed,
  allowing for unrestricted selection from all available options.
  
- Updated database model for DRAGONS runs: Corrected the database model
  to handle unique recipes per observation type and object name when the
  observation type is an object, addressing crashes for observation
  records with similar recipe requirements.
  
- Fixed dataset referencing in DRAGONS interface: The observation record
  ID dataset attached to the DRAGONS interface was referenced improperly
  and has been corrected.
  

GOATS 24.8.0 (2024-08-22)
=========================



New Features
------------

- Added run information panel on DRAGONS UI: Displayed selected run
  details, including creation date, DRAGONS version, and output
  directory path.
  
- Added UI components for file grouping and filtering: Introduced user
  interface elements that allow grouping and filtering of files,
  featuring a multiselect dropdown for selecting astrodata descriptors.
  
- Enhanced file grouping and filtering: Added functionality to fetch
  files from the frontend to the grouping and filtering API backend.
  Implemented listeners for button clicks to query API from the form.
  
- Added API endpoint for groups retrieval: Provided astrodata
  descriptors (groups) via API for DRAGONS runs and files.
  
- Grouped files by astrodata descriptors: Implemented an API backend to
  group files by their astrodata descriptors and count the files
  accordingly.
  
- Filtered files by astrodata descriptor values: Created an API backend
  to filter files based on expressions matching astrodata descriptor
  values.
  



Changes
-------

- Overhaul recipe assignment logic: Abandoned reliance on observation
  types for assigning recipes. Transitioned to using recipes modules,
  instruments, and tags to manage file recipes. This change enables
  GOATS to efficiently segregate files by their respective recipes and
  further distinguish different objects that may require unique recipes.
  The update prepares GOATS for integrating new instruments.
  
- Extended help page for interactive mode: Enhanced help documentation
  to show how to enable interactive mode for specific primitives.
  Interactive mode is no longer the default setting.
  



Bug Fixes
---------

- Fixed modal and toast closing issues: Resolved a bug caused by the
  transition to Bootstrap 5.
  
- Fixed help page docstring retrieval: Corrected an issue where
  docstrings were not properly fetched for the help page. Added tests to
  prevent in future.
  

GOATS 24.7.0 (2024-07-23)
=========================



New Features
------------

- Add Chrome extension link: Users can now click to access the Chrome
  extension store for installing antares2goats to enhance their GOATS
  experience from the ANTARES broker page.
  
- Editing, resetting, and saving DRAGONS recipes: DRAGONS recipes now
  support editing, saving, and resetting to original states. Users can
  customize recipes during data reduction processes.
  
- Enabled custom recipe input for DRAGONS: Users can now specify and
  utilize their own recipes in the DRAGONS reduction process.
  
- Added UI for DRAGONS reduction help pages: Side offcanvas with
  animation opens and closes to display helpful information for users on
  click.
  
- Added query parameter for detailed docs for primitives in API:
  Extended the DRAGONS files and recipes system to include a new query
  parameter. This parameter allows API responses to provide detailed
  documentation and descriptions of primitives used in a recipe.
  
- Connected frontend and backend for help docs: Established linkage
  between the frontend and backend systems for fetching and displaying
  help documentation related to primitives. Designed the user interface
  to comprehensively present all components of numpy doc strings and
  parameters when available.
  
- Implemented version-based recipe creation: Prevented redundant recipe
  entries in DRAGONS by creating base recipes only when the version
  changes.
  
- Updated UI recipe selection: Added functionality to choose and display
  recipes dynamically in DRAGONS recipe cards. Enhanced user interface
  elements include ordered observation types and updated card titles.
  



Changes
-------

- Output directory now matches run ID: Removed unused setup form and
  refresh button for DRAGONS runs. Disabled the delete option but
  retained it as a placeholder.
  
- Refactored UI for recipe management: Redesigned the user interface for
  managing observation type recipes and reductions. Now, only one
  reduction is displayed at a time, requiring users to toggle between
  them. This change simplifies the interface, helping users focus on one
  task at a time and reducing information overload.
  
- Improved “Help” bar output: Preserved spacing in docstrings for
  improved readability and changed applied styles.
  



Bug Fixes
---------

- Fixed custom media directory issue: Resolved path handling for custom
  media directories when running DRAGONS and saving products.
  
- Disabled automatic retries for failed DRAGONS reductions and GOA
  downloads.
  
- Resolved bug for trying to set state of null element in UI.
  
- Improved error handling for GOA timeouts when querying data products.
  

Enhancements
------------

- Enhanced GOATS startup and shutdown: Removed threading and implemented
  subprocesses. GOATS now exits cleanly, allowing sufficient time for
  all processes to shutdown properly.
  
- Reduced file operations in DRAGONS recipe queries.
  

GOATS 24.6.0 (2024-06-25)
=========================



New Features
------------

- Extended pagination to include item count: Overrode
  bootstrap_pagination to show “Showing x-y of n” message. Updated HTML
  template to display item counts.
  
- Implemented WebSocket support for DRAGONS logs: Developed a Channels
  consumer to handle real-time log messages from DRAGONS. Added a new
  WebSocket endpoint for DRAGONS updates and integrated a WebSocket
  logging handler. Expanded testing to cover Django Channels consumers.
  
- Developed DRAGONS WebSocket logging: Developed a Python logging
  handler for WebSocket communication to provide real-time logs for the
  DRAGONS system.
  
- Add backend for DRAGONS reduction: Developed an API to initiate and
  manage DRAGONS reduction processes in the background. Introduced a
  model to store details and updates of background tasks. Wrote
  comprehensive tests for the new backend infrastructure.
  
- Enabled initiation of DRAGONS recipe reduction from the UI.
  
- Added cancel endpoint for DRAGONS tasks: An API endpoint now allows
  canceling running or queued tasks in DRAGONS by setting the status of
  a recipe reduction to “canceled.” This action triggers the abortion of
  the background task. The update includes a new serializer to handle
  patches and extends tests to cover both valid and invalid patch
  scenarios.
  
- Enabled running task cancellation from UI: Connected the frontend
  “Stop” button with the backend to enable users to cancel running tasks
  directly from the interface. Added logic to dynamically enable or
  disable “Start” and “Stop” buttons based on the current status of
  recipe reductions.
  
- Display real-time logs on frontend with websocket: Built
  infrastructure to manage recipes for reduce runs, simplifying updates
  to specific recipes. Refactored recipe MVC.
  
- Extended DRAGONS consumer for real-time recipe progress updates:
  Updated the UI to display initial progress information. Added
  utilities for easier real-time communication and refactored UI
  progress bars to lay the foundation for future enhancements.
  
- Enabled interactive mode for select file types in recipe reduce:
  Integrated Bokeh for interactive visualization in ‘arc’, ‘flat’, and
  ‘object’ file types.
  
- Wrote tests for additional Django Channels classes: Added unit tests
  for websocket classes responsible for the notification system.
  
- Enhanced DRAGONS log autoscroll behavior: Updated logger to
  conditionally autoscroll based on the user’s current scroll position.
  Methods intended for logger internal use were made private.
  
- Cleared DRAGONS logs at recipe start.
  
- Load running reductions on DRAGONS run select: Implemented
  synchronization of running reductions on page refresh or when a new
  run is selected. Added support for query parameters to fetch and limit
  reduction results in the API.
  



Changes
-------

- Update conda environment file and dependencies: Removed the set
  version for tomtoolkit. Fixed issue caused by the new version of
  tomtoolkit.
  
- Added additional recipe reduce status feedback: Enhanced visibility of
  recipe reduce states and refined error handling in the DRAGONS reduce
  background task.
  
- Enhanced recipe progress UI: Updated the progress bar to display
  different colors for different states and provide status label.
  
- Switched to ``dramatiq`` for task management: GOATS now uses
  ``dramatiq`` for background tasks due to its support for aborting
  running tasks, a feature not available in ``huey``.
  



Bug Fixes
---------

- Fixed websocket connection issue: Resolved a bug where websockets
  failed to open on the DRAGONS run page, restoring functionality for
  notifications and download progress updates.
  

GOATS 24.5.0 (2024-05-28)
=========================



New Features
------------

- Link JS9 button to open file with JS9: Extended the serializer to
  include data URL for JS9.
  
- Added serializer tests: Wrote test cases for serializers used to
  validate API requests.
  
- Added api view tests: Wrote test cases for API viewsets.
  
- Enhanced UI with modal to display header: Implemented buttons to
  display modals with detailed file headers and to eventually trigger
  JS9 views. Added event listeners for smooth modal interactions and
  developed a function to build reusable modals.
  
- Changed DRAGONS run initialization: Extended backend logic to disable
  all bias files outside a specified day range of the observations
  during the initialization of a DRAGONS run. Optimized number of
  database queries when creating a DRAGONS run.
  
- Enhanced file retrieval with header inclusion: Added a query
  parameter, ``?include=header``, to include header information for
  files in DRAGONS runs.
  
- Added DRAGONS recipes and primitives API v1: Implemented REST API
  endpoints for DRAGONS recipes and primitives. The system now includes
  serializers for filtering by query parameters. Models were structured
  to connect recipes with primitives, allowing users to enable or
  disable individual primitives. This version supports only default
  recipes.
  
- Developed interactive DRAGONS recipe cards: Constructed interactive
  recipe cards for DRAGONS, featuring a built-in code editor for dynamic
  user customization. Also implemented a logger widget for real-time log
  monitoring. Created a utility class for common JavaScript
  functionalities and modified the backend by removing the storage of
  individual Primitives.
  
- Linked header API to modal display: Connected backend header API with
  modal UI to enable header information display when a button is
  clicked. Improved the header information presentation and error
  handling.
  
- Linked run selector to recipe card generator: The DRAGONS run selector
  now dynamically updates the displayed recipes when a new run is
  selected.
  
- Moved Ace editor local: Served Ace editor from app, removing CDN
  dependency.
  
- Added daily conda caching: Implemented a GitHub action to create and
  cache the goats conda environment daily for quicker testing.
  
- Extended models tests: Added comprehensive tests for newer models in
  GOATS.
  
- Added workflow to generate releases and update version.
  



Changes
-------

- Allow changing DRAGONS setup files names: Users can now change the
  DRAGONS setup files names. Removed the ability to change the log file
  name and removed from form. Added helper functions to get the path of
  DRAGONS setup files.
  
- Changed “Unknown” to “Other” for the file type when extracting file
  metadata.
  



Bug Fixes
---------

- Fixed bug in JS9 to ensure correct color for labels.
  
- Fixed file count and duplicate entries: Corrected the bug in the total
  file count calculation and prevented duplicates in the list of files
  downloaded to ensure an accurate count.
  
- Fixed JS9 and Ace conflict: Used no-conflict Ace with own namespace.
  

GOATS 24.04.0 (2024-04-26)
==========================



New Features
------------

- Add toggle for file enable/disable: Checkbox functionality was added
  to allow users to enable or disable files for DRAGONS reduction runs.
  Additionally, a CSS class was introduced to limit the size of tables
  when displaying large lists of files.
  
- Implemented file list generation: Version 1 of generating the file
  list for users was implemented, focusing on both frontend and backend
  development. This initial version is set to be revised based on user
  feedback.
  
- Switched to ``ruff`` for faster linting and formatting.
  



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
  
- Refactored frontend for efficiency: Combined setup steps and
  streamlined file listing for DRAGONS runs. Changed the timing of
  metadata extraction from data products to occur during downloading
  from GOA. This update ensures that metadata is always refreshed in
  tandem with data product updates, leading to faster loading and
  listing of file metadata.
  
- Refactored DRAGONS setup to MVC: Enhanced the DRAGONS run setup
  process by adopting the Model-View-Controller architecture, improving
  reactivity and maintainability of components.
  

GOATS 24.03.0 (2024-03-25)
==========================



New Features
------------

- DRAGONS integration and conda environment creation: DRAGONS is now
  part of the GOATS stack. A dedicated Conda environment file,
  ``environment.yml``, is available for easy installation by users
  cloning the repository. Additionally, the stack now includes a Redis
  server to support the latest changes in GOATS infrastructure.
  
- Add dark mode toggle to navbar: Added a dark mode toggle to the navbar
  using Halfmoon UI as a CSS dependency.
  
- Real-time communication enhanced: Implemented real-time communication
  between the backend and frontend using Django Channels and Redis.
  
- Extend CLI for Redis setup and running: Extended the ``install`` CLI
  to allow users to setup the Redis server. Modified the ``run`` CLI to
  run the Redis server in a separate thread alongside GOATS and Huey.
  
- Switched to Django Channels: Enhanced downloads and notifications
  using WebSocket communication. The download user interface was
  refactored to improve the overall user experience. Toast popups were
  introduced for real-time notifications. Gevent was removed to address
  and resolve asynchronous operation issues encountered with Django
  Channels.
  
- Implemented DRAGONS setup and config: Added a new Django model and
  serializer for DRAGONS run setup, enhancing the platform’s ability to
  handle DRAGONS reduction configurations asynchronously through the web
  interface. Initiated REST framework setup to streamline data exchange.
  

GOATS 24.02.0 (2024-02-26)
==========================



New Features
------------

- Extended error handling in OCSClient: The update introduces a
  dictionary return type for OCSClient methods, now including a
  ‘success’ key to clearly indicate the outcome of requests.
  Additionally, a ‘return_raw_data’ option has been implemented,
  allowing the inclusion of raw XML responses in the returned payload.
  
- Passwords for external services are securely stored using encryption
  to enhance data security.
  
- Implement key retrieval in Gemini facility: Added utility functions to
  retrieve keys based on user and identifier.
  
- Customizable server address and port: Users can now specify the
  address and port to run GOATS, accepting formats like ‘8000’,
  ‘0.0.0.0:8000’, or ‘192.168.1.5:8000’.
  



Bug Fixes
---------

- Correctly handle missing “value” in parameter set from XML data from
  OCS: The OCSParser received enhancements to effectively handle missing
  values in nested XML elements and improved its key naming strategy to
  utilize both the value and type of parameter sets for clearer and more
  accurate data representation.
  

GOATS 24.01.0 (2024-01-26)
==========================



New Features
------------

- Add CLI data product save location: Implemented a new option in the
  CLI to specify the save directory ``--media-dir`` for data products.
  
- Implemented Gemini OCS communication client: Added XML-RPC and URL
  endpoint handling in the OCS client and created a parser to convert
  XML data into dictionaries suitable for web view presentation.
  
- Implemented Gemini ID parsing: Added ``GeminiID`` class to parse and
  handle both program and observation IDs for use in ``OCSClient``,
  enhancing ID management and validation.
  
- Implemented key models for OCS API access: Added UserKey and
  ProgramKey models to manage API keys for OCS queries. Extended
  GeminiID to include class methods for validating program and
  observation IDs.
  
- Implemented key management frontend: Enhanced the Gemini OT interface
  with new views and forms for key management.
  



Changes
-------

- Switched to temporary directory usage: ``GOATS`` now downloads and
  unpacks archive data into a temporary directory, preventing collisions
  during decompression. Additionally, optimized the process of moving
  downloaded files to the destination folder by implementing
  parallelization.
  



Bug Fixes
---------

- Fixed client availability for xmlrpc: Resolved an issue where the
  client was not correctly set up for XML-RPC communication, ensuring
  proper functioning of remote procedure calls. Expanded testing with
  remote data to avoid more issues.
  

GOATS 23.12.0 (2023-12-22)
==========================



New Features
------------

- Implemented Huey for background tasks: Integrated Huey, a lightweight
  Python task queue, into GOATS to handle background tasks using
  sqlite3. This addition streamlines the data download process,
  eliminating the need for users to endure unresponsive periods during
  downloads and keeps the application lightweight by avoiding complex
  libraries.
  
- Implemented navbar download display and recent downloads view:
  Introduced a new update mechanism in the navbar for displaying
  background downloads across all pages using polling and implemented a
  new view for accessing recent downloads.
  
- Allowed editing of query names in query list view.
  



Changes
-------

- Implemented dark mode and enhanced UI flexibility: Switched to dark
  mode for GOATS, limited to light or dark because bootstrap 4 does not
  support switching using themes. Integrated Font Awesome icons to
  improve the user interface aesthetics and enabled setting Plotly theme
  from Django settings for customizable visualizations.
  
- Modified view for observations: Included the target sidebar in the
  observation view to provide a cohesive user experience, enabling users
  to see target information alongside specific observation details.
  
- Enhanced GOATS CLI for worker management: Extended the GOATS
  command-line interface to include the ``--workers`` option in the
  ``goats run`` command, enabling users to spin up or down \`greenlet`\`
  workers as needed. This feature allows for flexible worker management
  while maintaining a lightweight footprint, though users should be
  cautious not to start too many or too few workers.
  
- Change data product storage organization: Data products are now
  organized by observation ID folders, nested under target and facility
  folders.
  
- Improved target deletion process: Enhanced deletion of targets now
  includes removal of all associated observation records and their data
  products.
  



Bug Fixes
---------

- Fixed a bug in TOMToolkit where the time was incorrectly displayed
  with the month instead of the minute.
  

GOATS 23.11.0 (2023-11-27)
==========================



New Features
------------

- Added data product type support.
  
- Enhanced GOA query feedback: Extended the GOA query functionality to
  construct and return comprehensive download information. This
  enhancement includes detailed feedback to GOATS users regarding the
  status of their queries, encompassing error notifications, the count
  of downloaded files, and alerts about potentially missed files due to
  the absence of user authentication.
  
- Added calibration radio button to ``GOA`` query form: Introduced an
  option to include, exclude, or solely download calibration data for an
  observation ID.
  
- Added GOA observation ID URL: Implemented a new feature to display a
  URL for GOA observation ID on the observation page for viewing
  available data files.
  
- Enhanced observation record management: Introduced a new view to
  efficiently handle the deletion of all data products associated with
  an observation record. This update includes a confirmation page for
  deletion operations, ensuring user confirmation before proceeding with
  data removal. Additionally, the update fixes a typo and improves
  permission handling for both ``GET`` and ``POST`` requests for
  deleting all data products, enhancing the overall user experience and
  security.
  



Changes
-------

- Updated URL to reflect active tab: Enhanced the target page to modify
  the URL in accordance with the currently active tab, ensuring that
  refreshing the page maintains the user’s selected tab.
  



Bug Fixes
---------

- Simplified redirecting users to the target list view for consistency
  and better UX.
  
- Fixed thumbnail deletion for data products: Resolved a bug where data
  product thumbnails were not being deleted properly along with the data
  product, leading to multiple copies.
  



Enhancements
------------

- Enhanced download and decompression performance: Optimized the process
  for downloading and decompressing tar files from GOA, significantly
  reducing the time required. Implemented streaming for data downloads,
  which minimizes memory usage for large files.
  

GOATS 23.10.0 (2023-10-26)
==========================



New Features
------------

- Integrate Firefox add-on: ``antares2goats`` hosted on Firefox has been
  integrated into ``GOATS``. Users will be able to install the browser
  add-on, configure the token, and use the add-on without issue.
  
- ``astroquery`` and ``GOATS`` enhanced for calibration files: Extended
  ``astroquery`` to download associated calibration files as a tar
  archive. ``GOATS`` now automatically downloads and ingests these files
  for an observation record into saved data products.
  
- Added observation and thumbnail deletion: Added the ability to delete
  observations from a target and fixed a bug to correctly delete
  associated thumbnails from data products.
  
- GOA Public Data Connection and Gemini Update: Introduced GOA
  connection for public data. Added query features. Improved Gemini
  facility documentation and code quality. Extended astroquery for
  future integration.
  
- GOA Proprietary Data Connection and Gemini Update: Introduced GOA
  connection for proprietary data. Added GOA credential management.
  



Changes
-------

- Removed CLI for installing extension: Due to Chrome being the only
  browser to be able to install an extension from the CLI, removing all
  references and code to install from the CLI. Users will only be able
  to install the ``antares2goats`` extension via the extension store.
  
- Improved GOATS frontend: Enhanced the user interface by adding two new
  input fields for GOA queries. Refined tab views for target management,
  specifically when adding existing observations or updating statuses.
  
- Optimized GOA data and overhauled ``astroquery`` for Gemini:
  Implemented compressed and tar files for efficient data retrieval from
  GOA. Completed a major refactoring of the ``astroquery`` package for
  Gemini, in preparation for a future merge into the main ``astroquery``
  project.
  



Other
-----

- Add Makefile for ``antares2goats`` packaging: Created a Makefile to
  automate the packaging of ``antares2goats`` into a ZIP file for
  uploading to Firefox and Chrome extension stores.
  

GOATS 23.09.0 (2023-09-25)
==========================



New Features
------------

- Incorporated token support in ``antares2goats``: Integrated token
  authentication to allow users to securely save queries and targets
  from ``ANTARES``. Revamped the Options page for token input.
  
- Chrome extension v1: The initial version of the Chrome extension has
  been implemented, paving the way for enhanced browser functionality. A
  custom exception handling mechanism has been integrated within the
  GOATS Click, improving user experience in the command line interface.
  Additionally, a new CLI command facilitates the straightforward
  installation of the Chrome extension, while modifications to the
  ANTARES plugin now allow for direct query creation from the extension.
  To round off these updates, a new view has been established to monitor
  browser extension push notifications.
  
- Added CLI command ``install-extension``: CLI framework created so
  users in the future can install the browser extension for GOATS.
  Installation can be done in the ``install`` step or after with
  ``install-extension``.
  
- Single-Target Creation via Extension: Enhanced the extension to
  directly create individual targets within ANTARES, eliminating the
  need for query generation.
  
- “Select All” feature enhancement: Users can now effortlessly select
  all targets with a single click, streamlining the addition process and
  enhancing user experience. Additionally, the query results have been
  refined to eliminate superfluous information, promoting a cleaner,
  more intuitive interface.
  
- Added token authentication: Admins can now generate tokens for
  authentication in the backend of GOATS, facilitating secure
  interactions with the \`antares2goats`\` browser extension.
  



Changes
-------

- GOATS Prompt Overhaul: Enhanced user experience during GOATS
  installation and execution with transparent process descriptions and
  progress updates.
  
- GOATS ANTARES Broker webpage v1: Enhanced integration with GOATS,
  leveraging the \`antares2goats`\` extension for streamlined
  performance and alignment.
  
- Removed non-functional broker plugins: TNS, Fink and LASAIR.
  

GOATS 23.08.0 (2023-08-25)
==========================



New Features
------------

- GOATS CLI: The GOATS CLI was updated to use Python Click, simplifying
  the command-line interface. The CLI is now included with the package
  installation. Use the goats command in the terminal to start.
  
- Added v1 of GOATS footer: A custom footer was developed for the GOATS
  platform. The update involved integrating essential elements from the
  ``tom_base/tom_common`` files and initiating the use of custom CSS.
  
- Added v1 of GOATS navbar: A custom navbar was developed for the GOATS
  platform.
  
- Design initial version of GOATS CSS and layout: Bootstrap serves as a
  foundational element in our project, being a critical component of the
  TOM Toolkit. We leverage its robust framework as a starting point,
  extending and customizing it to create our own distinctive style that
  aligns with our specific needs and branding.
  
- Created v1 of GOATS banner: A new banner has been added to display
  site logo and affiliates.
  
- Improved CLI for GOATS: The CLI for GOATS now supports a development
  server that allows for real-time template modifications. Additionally,
  shorthand options have been introduced for a more streamlined user
  experience.
  



Other
-----

- Tooling for release notes: Added infrastructure to produce useful,
  summarized change logs with ``towncrier``.
  
- ``pytest`` GitHub Action Integration: Established automated unit
  testing and initial code coverage assessment. This action, triggered
  on every ‘push’ event, provides continual testing and a basic coverage
  report, laying the groundwork for future integration with Codecov.
  
- ``pytest`` infrastructure started: Established a ``pytest``
  infrastructure for ``goats``, introducing robust unit and integration
  tests. This setup enhances the reliability and maintainability of the
  codebase, facilitating more secure code updates and deployments.
  
- Standard ``pyproject.toml`` started: Implemented a ``pyproject.toml``
  file for ``goats`` to standardize build tool dependencies,
  streamlining the build process and ensuring consistency across
  different environments.
  
- Integrated ``flake8`` in GitHub Actions: Incorporated ``flake8`` into
  the GitHub Actions pipeline, enabling automatic linting checks for
  Python code. This enforces code quality standards across ``goats``.
  
- Overrode default TOMToolkit index page and updated ``pyproject.toml``:
  Improved pip installation process, enhancing user interface
  customization for GOATS and project distribution.
  
- Optimized GitHub Actions and integrated HTML linting: GitHub Actions
  now operate selectively, with the HTML linter (``htmlhint``) triggered
  when template HTML files change, and unit tests and ``flake8`` checks
  run when Python files change. Additionally, common Jinja templating
  settings are now ignored by the HTML linter, thanks to the updated
  ``htmlhint`` configuration.
  
- CSS linting added to GitHub Actions: Used stylelint to ensure CSS code
  quality.
  
- JS Testing using ``jest``: Implemented a test suite for JavaScript
  files in the GOATS project using ``jest``. Ensures robust testing
  across the website and integrates GitHub action to run tests
  automatically. A badge has been added to the repository to show the
  test status.
  
