Parsers
=======

Parsers convert documents from various formats into the all2md AST (Abstract Syntax Tree).
Each parser implements the :class:`~all2md.parsers.base.BaseParser` interface and accepts
format-specific options.

Core Formats
------------

The most commonly used document formats with full-featured parsing support:

.. list-table::
   :widths: 15 25 60
   :header-rows: 1

   * - Format
     - Module
     - Description
   * - PDF
     - :doc:`all2md.parsers.pdf`
     - Advanced PDF parsing with table detection using PyMuPDF
   * - DOCX
     - :doc:`all2md.parsers.docx`
     - Microsoft Word with formatting preservation
   * - HTML
     - :doc:`all2md.parsers.html`
     - HTML/XHTML with configurable conversion
   * - PPTX
     - :doc:`all2md.parsers.pptx`
     - PowerPoint slide-by-slide extraction
   * - EML
     - :doc:`all2md.parsers.eml`
     - Email with chain detection and attachments

Data Formats
------------

Structured data and spreadsheet formats:

.. list-table::
   :widths: 15 25 60
   :header-rows: 1

   * - Format
     - Module
     - Description
   * - XLSX
     - :doc:`all2md.parsers.xlsx`
     - Excel workbooks with sheet selection
   * - CSV
     - :doc:`all2md.parsers.csv`
     - Comma-separated values with dialect detection
   * - JSON
     - :doc:`all2md.parsers.json`
     - JSON documents with pretty-printing
   * - YAML
     - :doc:`all2md.parsers.yaml`
     - YAML configuration files
   * - TOML
     - :doc:`all2md.parsers.toml`
     - TOML configuration files
   * - INI
     - :doc:`all2md.parsers.ini`
     - INI configuration files

Markup Formats
--------------

Text markup languages with semantic conversion:

.. list-table::
   :widths: 15 25 60
   :header-rows: 1

   * - Format
     - Module
     - Description
   * - Markdown
     - :doc:`all2md.parsers.markdown`
     - Markdown parsing (for round-trip transformations)
   * - RST
     - :doc:`all2md.parsers.restructuredtext`
     - reStructuredText documents
   * - LaTeX
     - :doc:`all2md.parsers.latex`
     - LaTeX documents with math support
   * - AsciiDoc
     - :doc:`all2md.parsers.asciidoc`
     - AsciiDoc documents
   * - Org-Mode
     - :doc:`all2md.parsers.org`
     - Emacs Org-Mode files
   * - MediaWiki
     - :doc:`all2md.parsers.mediawiki`
     - MediaWiki/Wikipedia markup
   * - Textile
     - :doc:`all2md.parsers.textile`
     - Textile markup
   * - DokuWiki
     - :doc:`all2md.parsers.dokuwiki`
     - DokuWiki syntax

E-book & Document Formats
-------------------------

Long-form document and e-book formats:

.. list-table::
   :widths: 15 25 60
   :header-rows: 1

   * - Format
     - Module
     - Description
   * - EPUB
     - :doc:`all2md.parsers.epub`
     - E-book format with chapter extraction
   * - ODT
     - :doc:`all2md.parsers.odt`
     - OpenDocument Text
   * - ODP
     - :doc:`all2md.parsers.odp`
     - OpenDocument Presentation
   * - RTF
     - :doc:`all2md.parsers.rtf`
     - Rich Text Format
   * - FB2
     - :doc:`all2md.parsers.fb2`
     - FictionBook e-book format
   * - CHM
     - :doc:`all2md.parsers.chm`
     - Microsoft Compiled HTML Help

Archive & Web Formats
---------------------

Archives, web captures, and specialized formats:

.. list-table::
   :widths: 15 25 60
   :header-rows: 1

   * - Format
     - Module
     - Description
   * - ZIP/Archive
     - :doc:`all2md.parsers.archive`
     - ZIP, TAR, 7z, RAR archives
   * - MHTML
     - :doc:`all2md.parsers.mhtml`
     - MIME HTML web archives
   * - WebArchive
     - :doc:`all2md.parsers.webarchive`
     - Safari web archives
   * - MBOX
     - :doc:`all2md.parsers.mbox`
     - Mailbox files
   * - ENEX
     - :doc:`all2md.parsers.enex`
     - Evernote export format
   * - OpenAPI
     - :doc:`all2md.parsers.openapi`
     - OpenAPI/Swagger specifications
   * - Jupyter
     - :doc:`all2md.parsers.ipynb`
     - Jupyter notebooks

Other Formats
-------------

Additional supported formats:

.. list-table::
   :widths: 15 25 60
   :header-rows: 1

   * - Format
     - Module
     - Description
   * - Plain Text
     - :doc:`all2md.parsers.plaintext`
     - Plain text files
   * - Source Code
     - :doc:`all2md.parsers.sourcecode`
     - 200+ programming languages
   * - BBCode
     - :doc:`all2md.parsers.bbcode`
     - Forum BBCode markup
   * - Outlook
     - :doc:`all2md.parsers.outlook`
     - Microsoft Outlook MSG files

Base Parser Class
-----------------

All parsers inherit from the base parser class:

.. autosummary::
   :nosignatures:

   all2md.parsers.base.BaseParser

Complete Parser Reference
-------------------------

For detailed documentation on all parser modules, see:

.. toctree::
   :maxdepth: 1

   all2md.parsers
