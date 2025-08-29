# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
# https://eikonomega.medium.com/getting-started-with-sphinx-autodoc-part-1-2cebbbca5365

project = "GOATS"
copyright = "2025, Association of Universities for Research in Astronomy"
author = "GOATS Team"

extensions = [
    "sphinx.ext.duration",
    "sphinx.ext.doctest",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinxcontrib.video",
    "sphinx.ext.graphviz",
    "sphinx_copybutton",
]

graphviz_output_format = "svg"

templates_path = ["_templates"]

# The suffix of source filenames.
source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# _static subdirectory to put videos
html_static_path = ["_static"]
html_theme = "furo"
html_logo = "images/GOATS_logo.png"
github_url = "https://github.com/gemini-hlsw/goats"
html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#8244ee",
        "color-brand-content": "#8244ee",
        "color-brand-visited": "#45237f",
    },
    "dark_css_variables": {
        "color-brand-primary": "#f2aa0d",
        "color-brand-content": "#f2aa0d",
        "color-brand-visited": "#ffc23e",
    },
    "sidebar_hide_name": True,
    "navigation_with_keys": True,
    # Fill out announcement to have banner appear.
    "announcement": "",
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/gemini-hlsw/goats",
            "html": """
                <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
            """,
            "class": "",
        },
    ],
}

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Figure numbering
numfig = True

# Substitutions and replacements
rst_epilog = """
.. role:: raw-html(raw)
   :format: html

.. |TOMToolkit| replace:: :raw-html:`<a href="https://tom-toolkit.readthedocs.io/en/stable/">TOM Toolkit</a>`
.. |ANTARES| replace:: :raw-html:`<a href="https://antares.noirlab.edu/">ANTARES</a>`
.. |DRAGONS| replace:: :raw-html:`<a href="https://dragons.readthedocs.io/en/stable/">DRAGONS</a>`
.. |GOA| replace:: :raw-html:`<a href="https://archive.gemini.edu/">Gemini Observatory Archive</a>`
.. |Dlab| replace:: :raw-html:`<a href="https://datalab.noirlab.edu/">Astro Data Lab</a>`
.. |GPP| replace:: :raw-html:`<a href="https://noirlab.edu/public/media/archives/presentations/pdf/presentation011.pdf">Gemini Program Platform</a>`
.. |python_min| replace:: 3.12
"""
