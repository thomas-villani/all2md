"""Sphinx documentation configuration for all2md.

This module configures the Sphinx documentation builder for the all2md
project, including extensions, themes, and HTML output options.

"""
# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html


import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "all2md"
copyright = "2025, Tom Villani, Ph.D."
author = "Tom Villani, Ph.D."
release = "0.1.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.doctest",
    "sphinx_copybutton"
]

templates_path = ["_templates"]
exclude_patterns = []

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "private-members": False,
    # "special-members": "__init__",
    # "inherited-members": False,
    "show-inheritance": True,
}
autodoc_inherit_docstrings = True
autodoc_member_order = "bysource"
autoclass_content = "both"
autodoc_typehints = "signature"

# -- Options for doctest -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/doctest.html

doctest_test_doctest_blocks = "default"
doctest_global_setup = """
from all2md import to_markdown, to_ast
from all2md.options import (
    PdfOptions, DocxOptions, HtmlOptions, PptxOptions,
    EmlOptions, IpynbOptions, MarkdownOptions
)
from all2md.ast import NodeVisitor, Heading
from all2md.renderers.markdown import MarkdownRenderer
from all2md.utils.flavors import GFMFlavor
from pathlib import Path
import tempfile
"""

# Skip testing code blocks that require external files or network
doctest_default_flags = 0

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
