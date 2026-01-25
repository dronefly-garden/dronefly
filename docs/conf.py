# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

sys.path.insert(0, os.path.abspath(".."))


# -- Project information -----------------------------------------------------

project = "Dronefly"
copyright = "2020-2026, Ben Armstrong and Michael Pirrello"
author = "Ben Armstrong, Michael Pirrello"
programming_language = "py"


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx.ext.doctest",
    "sphinx.ext.imgconverter",
    "sphinxcontrib_trio",
]

autosectionlabel_prefix_document = True

intersphinx_mapping = {"redbot": ("https://docs.discord.red/en/stable", None)}

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_logo = "Pictures/eristalis_1.png"
html_theme = "sphinx_material"
html_theme_options = {
    "base_url": "http://bashtage.github.io/sphinx-material/",
    "repo_url": "https://github.com/dronefly-garden/dronefly/",
    "repo_name": "Dronefly cogs for Naturalists",
    "html_minify": True,
    "css_minify": True,
    "nav_title": "Dronefly Project",
    "localtoc_label_text": "Contents",
    "globaltoc_depth": 2,
    "version_info": {
        "latest": "https://dronefly.readthedocs.io/en/latest/",
        "devel": "https://dronefly.readthedocs.io/en/devel/",
    },
}
html_sidebars = {
    "**": ["logo-text.html", "globaltoc.html", "localtoc.html", "searchbox.html"]
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

master_doc = "index"
