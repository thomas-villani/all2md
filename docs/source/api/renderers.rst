Renderers
=========

Renderers convert the all2md AST into various output formats. Each renderer implements
the :class:`~all2md.renderers.base.BaseRenderer` interface and accepts format-specific options.

Core Output Formats
-------------------

Primary output formats with full formatting support:

.. list-table::
   :widths: 15 25 60
   :header-rows: 1

   * - Format
     - Module
     - Description
   * - Markdown
     - :doc:`all2md.renderers.markdown`
     - Markdown with flavor support (GFM, CommonMark, etc.)
   * - HTML
     - :doc:`all2md.renderers.html`
     - HTML5 with CSS styling options
   * - DOCX
     - :doc:`all2md.renderers.docx`
     - Microsoft Word documents
   * - PDF
     - :doc:`all2md.renderers.pdf`
     - PDF documents with styling
   * - PPTX
     - :doc:`all2md.renderers.pptx`
     - PowerPoint presentations

Data Output Formats
-------------------

Structured data and configuration formats:

.. list-table::
   :widths: 15 25 60
   :header-rows: 1

   * - Format
     - Module
     - Description
   * - JSON
     - :doc:`all2md.renderers.json`
     - JSON document output
   * - YAML
     - :doc:`all2md.renderers.yaml`
     - YAML document output
   * - TOML
     - :doc:`all2md.renderers.toml`
     - TOML configuration output
   * - CSV
     - :doc:`all2md.renderers.csv`
     - CSV table export
   * - INI
     - :doc:`all2md.renderers.ini`
     - INI configuration output

Markup Output Formats
---------------------

Markup language renderers:

.. list-table::
   :widths: 15 25 60
   :header-rows: 1

   * - Format
     - Module
     - Description
   * - RST
     - :doc:`all2md.renderers.restructuredtext`
     - reStructuredText output
   * - LaTeX
     - :doc:`all2md.renderers.latex`
     - LaTeX document output
   * - AsciiDoc
     - :doc:`all2md.renderers.asciidoc`
     - AsciiDoc output
   * - Org-Mode
     - :doc:`all2md.renderers.org`
     - Emacs Org-Mode output
   * - MediaWiki
     - :doc:`all2md.renderers.mediawiki`
     - MediaWiki markup output
   * - Textile
     - :doc:`all2md.renderers.textile`
     - Textile markup output
   * - DokuWiki
     - :doc:`all2md.renderers.dokuwiki`
     - DokuWiki syntax output

Document & E-book Formats
-------------------------

Long-form document renderers:

.. list-table::
   :widths: 15 25 60
   :header-rows: 1

   * - Format
     - Module
     - Description
   * - EPUB
     - :doc:`all2md.renderers.epub`
     - E-book creation
   * - ODT
     - :doc:`all2md.renderers.odt`
     - OpenDocument Text
   * - ODP
     - :doc:`all2md.renderers.odp`
     - OpenDocument Presentation
   * - RTF
     - :doc:`all2md.renderers.rtf`
     - Rich Text Format

Special Renderers
-----------------

Specialized output formats:

.. list-table::
   :widths: 15 25 60
   :header-rows: 1

   * - Format
     - Module
     - Description
   * - Plain Text
     - :doc:`all2md.renderers.plaintext`
     - Plain text (strip formatting)
   * - AST JSON
     - :doc:`all2md.renderers.ast_json`
     - JSON AST serialization
   * - Jinja
     - :doc:`all2md.renderers.jinja`
     - Custom Jinja2 template rendering
   * - Jupyter
     - :doc:`all2md.renderers.ipynb`
     - Jupyter notebook output

Base Renderer Class
-------------------

All renderers inherit from the base renderer class:

.. autosummary::
   :nosignatures:

   all2md.renderers.base.BaseRenderer

Complete Renderer Reference
---------------------------

For detailed documentation on all renderer modules, see:

.. toctree::
   :maxdepth: 1

   all2md.renderers
