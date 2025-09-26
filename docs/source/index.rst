all2md Documentation
===================

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

🚀 **Rapid Conversion** - Lightweight and fast document processing

🔍 **Smart Detection** - Automatic format detection from content and filenames

📄 **Multiple Formats** - Support for 15+ document formats plus 200+ text formats

⚙️ **Highly Configurable** - Extensive options for customizing Markdown output

🖼️ **Image Handling** - Download, embed as base64, or skip images entirely

💻 **CLI & API** - Use from command line or integrate into Python applications

🔧 **Modular Design** - Optional dependencies per format to keep installs lightweight

Quick Example
-------------

.. code-block:: python

   from all2md import to_markdown

   # Convert any document to Markdown
   markdown = to_markdown('document.pdf')
   print(markdown)

   # With custom options
   from all2md import PdfOptions

   options = PdfOptions(
       pages=[0, 1, 2],  # First 3 pages only
       attachment_mode='download',
       attachment_output_dir='./images'
   )
   markdown = to_markdown('document.pdf', options=options)

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
  PDF, Word (DOCX), PowerPoint (PPTX), HTML/MHTML, Email (EML), EPUB, RTF, OpenDocument (ODT/ODP)

**Data & Other**
  Excel (XLSX), CSV/TSV, Jupyter Notebooks (IPYNB), Images (PNG/JPEG/GIF), 200+ text formats

Getting Started
---------------

New to all2md? Start here:

1. :doc:`installation` - Install all2md with the formats you need
2. :doc:`quickstart` - Get up and running in 5 minutes
3. :doc:`overview` - Understand the library architecture and capabilities

User Guide
----------

.. toctree::
   :maxdepth: 2

   installation
   quickstart
   overview
   formats
   cli
   options
   plugins
   troubleshooting

API Reference
-------------

.. toctree::
   :maxdepth: 2

   api/modules

About
-----

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