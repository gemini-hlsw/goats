# Configuration file for the Sphinx documentation builder.

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
]

graphviz_output_format = "svg"

templates_path = ["_templates"]

# The suffix of source filenames.
source_suffix = ".rst"

# The encoding of source files.
#source_encoding = "utf-8-sig"

# The master toctree document.
master_doc = "index"

# _static subdirectory to put videos 
html_static_path = ["_static"]

# html_theme = "alabaster"
# html_sidebars = {
#     "**": [
#         "about.html",
#         "searchfield.html",
#         "navigation.html",
#         "relations.html",
#     ]
# }
# html_theme_options = {
#     "logo": "GOATS_logo.png",
#     "github_user"
#     "logo_name": "false",
#     "fixed_sidebar": "true",
#     "description": "Time-domain astronomy made time efficient.",
#     "github_button": "true",
#     "github_repo": "goats",
#     "github_user": "gemini-hlsw",
#     "codecov_button": "true",
#     "badge_branch": "main",
# }
html_theme = "sphinx_rtd_theme"
html_theme_options = {"style_nav_header_background": "#343131"}
html_logo = "images/GOATS_logo.png"
github_url = "https://github.com/gemini-hlsw/goats"

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

"""
