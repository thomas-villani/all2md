all2md Documentation
=====================

Welcome to all2md, a Python document conversion library for rapid, lightweight transformation of various document formats to Markdown. Designed specifically for LLMs and document processing pipelines.

.. image:: https://img.shields.io/badge/python-3.12+-blue.svg
   :target: https://python.org
   :alt: Python Version

.. image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT
   :alt: License: MIT

.. image:: https://badge.fury.io/py/all2md.svg
   :target: https://badge.fury.io/py/all2md
   :alt: PyPI version

Key Features
------------

🚀 **Rapid Conversion Pipelines** – Optimised parsers and renderers for fast, reliable Markdown

🔍 **Smart Detection** – Multi-stage format detection (extension, MIME, magic bytes) with graceful fallbacks

📄 **Wide Format Coverage** – 20+ document, markup, and archive formats plus 200+ source-code/flat text types

⚙️ **Dynamic Configuration** – Dataclass-driven options, presets, and CLI/env overrides for every converter

🖼️ **Attachment Management** – Unified system for downloading, embedding, or annotating images and binaries

🧠 **AST Transforms** – Hookable transformation pipeline with built-in TOC generation, boilerplate removal, and plugins

🎨 **Custom Templates** – Jinja2-based rendering for custom output formats (DocBook, YAML, ANSI terminal, etc.) without writing Python

🧭 **Rich CLI Toolkit** – Batch processing, watch mode, parallel workers, collated output, and themed Rich terminals

🤖 **Integrations Ready** – MCP server, plugin entry points, static-site templating, and bidirectional conversion APIs

Quick Example
-------------

.. code-block:: python

   from all2md import to_markdown

   # Convert any document to Markdown
   markdown = to_markdown('document.pdf')
   print(markdown)

   # With custom options
   from all2md.options import PdfOptions

   options = PdfOptions(
       pages=[1, 2, 3],  # First 3 pages only
       attachment_mode='download',
       attachment_output_dir='./images'
   )
   markdown = to_markdown('document.pdf', parser_options=options)

   # With AST transforms
   from all2md.transforms import RemoveImagesTransform, HeadingOffsetTransform

   markdown = to_markdown(
       'document.pdf',
       transforms=[
           RemoveImagesTransform(),
           HeadingOffsetTransform(offset=1)
       ]
   )

Command Line Usage
------------------

.. code-block:: bash

   # Convert any document to markdown
   all2md document.pdf

   # Save output to file
   all2md document.docx --out output.md

   # Download images to a directory
   all2md document.html --attachment-mode download --attachment-output-dir ./images

Supported Formats
-----------------

**Documents**
  PDF, Word (DOCX), PowerPoint (PPTX), HTML/MHTML, Email (EML), EPUB, RTF, OpenDocument (ODT/ODP with bidirectional support)

**Data & Other**
  Excel (XLSX), CSV/TSV, Jupyter Notebooks (IPYNB), Archives (TAR/7Z/RAR/ZIP), Images (PNG/JPEG/GIF), 200+ text formats

**Markup**
  Markdown, reStructuredText, AsciiDoc, Org-Mode, MediaWiki, LaTeX, OpenAPI/Swagger, Textile

Getting Started
---------------

New to all2md? Start here:

1. :doc:`installation` - Install all2md with the formats you need
2. :doc:`quickstart` - Get up and running in 5 minutes
3. :doc:`overview` - Understand the library architecture and capabilities

Guides & References
-------------------

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart
   overview
   formats

.. toctree::
   :maxdepth: 2
   :caption: Core Workflows

   cli
   options
   python_api
   attachments
   transforms
   ast_guide

.. toctree::
   :maxdepth: 2
   :caption: Advanced Topics

   architecture
   templates
   static_sites
   security
   threat_model
   performance
   recipes

.. toctree::
   :maxdepth: 2
   :caption: Integrations & Operations

   mcp
   plugins
   integrations
   environment_variables
   troubleshooting

API Reference
-------------

.. toctree::
   :maxdepth: 2

   api/modules

About
-----

.. toctree::
   :maxdepth: 1

   license

**all2md** is developed by Tom Villani, Ph.D. and released under the MIT License.

* **Source Code**: https://github.com/thomas.villani/all2md
* **Issues**: https://github.com/thomas.villani/all2md/issues
* **PyPI**: https://pypi.org/project/all2md/
* **License**: :doc:`MIT License <license>`

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
