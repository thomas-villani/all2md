all2md Documentation
=====================

**all2md** is a comprehensive Python library for bidirectional document conversion between various file formats and Markdown. It provides intelligent content extraction and formatting preservation for PDF, Word, PowerPoint, HTML, email, Excel, images, and 200+ text file formats.

Key Features
------------

* **Bidirectional Conversion**: Format-to-Markdown and Markdown-to-Format
* **Comprehensive Format Support**: PDF, DOCX, PPTX, HTML, EML, XLSX, images, and 200+ text formats
* **Intelligent Processing**: Advanced PDF table detection, email chain parsing, formatting preservation
* **Easy Integration**: Simple API with automatic file type detection

Quick Start
-----------

.. code-block:: python

   from all2md import parse_file

   # Convert any supported file to Markdown
   with open('document.pdf', 'rb') as f:
       markdown_content = parse_file(f, 'document.pdf')
       print(markdown_content)

Installation
------------

Install all2md from PyPI:

.. code-block:: bash

   pip install all2md

Requirements:
* Python 3.12+
* Optional dependencies installed automatically per format

Table of Contents
-----------------

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   quickstart
   usage
   api
   formats
   contributing
