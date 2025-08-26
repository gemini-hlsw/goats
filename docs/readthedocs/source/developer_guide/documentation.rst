Documentation
=============

We use `Read the Docs <https://readthedocs.org/>`_ for publishing our documentation online. The GOATS team manages the project using the shared ``goats`` email. Documentation builds are triggered on pull requests **only** if changes are made within the ``docs/readthedocs`` directory.

We do **not** currently publish a code API, as GOATS is an application rather than a library.

Preview Changes Locally
-----------------------

To preview documentation locally:

1. Install the documentation dependencies. These are included in the ``docs`` extras group:

   .. code-block:: bash

      uv pip install -e . --group docs

2. From the ``docs/readthedocs`` directory, run:

   .. code-block:: bash

      sphinx-autobuild source build

3. Navigate to ``http://localhost:8000`` in your browser to preview the documentation.

   Any changes to the source files will automatically trigger a rebuild and refresh the page.

.. note::

   Make sure the GOATS app is **not** running while previewing docs, as it also uses port ``8000``.