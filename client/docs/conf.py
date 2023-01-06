# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "HitSave"
copyright = "2022, hitsave.io"
author = "hitsave.io"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ["myst_parser", "sphinx.ext.autodoc", "sphinx_gallery.gen_gallery"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Sphinx gallery
# reference: https://sphinx-gallery.github.io/stable/getting_started.html
sphinx_gallery_conf = {
    "examples_dirs": "../examples",  # path to your example scripts
    "gallery_dirs": "examples",  # path to where to save gallery generated output
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# html_theme = "sphinx_book_theme"
html_title = "HitSave Docs"
html_theme = "hitsave_theme"
html_theme_path = ["_themes"]
html_favicon = "../../web/public/favicon.ico"
html_static_path = ["_static"]
html_css_files = ["css/custom.css"]
