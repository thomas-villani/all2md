Supported Formats
=================

all2md ships with a broad range of parsers and renderers that cover everything from enterprise PDFs to
knowledge-base markup and developer archives. This page summarises what each converter does, highlights the
most important options, and points you to the right reference guides for deeper detail.

.. tip::
   Run ``all2md list-formats`` (or ``all2md list-formats --available-only``) to inspect the converters that are
   currently installed in your environment. The command reports missing dependencies, MIME types, and whether the
   format supports parsing, rendering, or both.

.. contents:: Format Families
   :local:
   :depth: 1

Document & Presentation Formats
-------------------------------

PDF Documents
~~~~~~~~~~~~~

*Parser:* ``PdfToAstConverter`` — *Renderer:* ``PdfRenderer``

Key capabilities:

- Adaptive layout analysis with multi-column detection and ruling/table heuristics
- Page filtering, header/footer trimming, and hyphen merging for cleaner prose
- Rich attachment pipeline (download/base64/alt-text) shared with other formats
- Optional word/character counts via :doc:`transforms`

Essentials:

- Options class: ``PdfOptions`` (see :doc:`options`)
- CLI prefix: ``--pdf-*``

.. code-block:: bash

   # Focus on specific pages and collect images locally
   all2md report.pdf \
     --pdf-pages "1-5" \
     --attachment-mode download \
     --attachment-output-dir ./assets/report

Word Documents (DOCX)
~~~~~~~~~~~~~~~~~~~~~

*Parser:* ``DocxToAstConverter`` — *Renderer:* ``DocxRenderer``

- Preserves paragraph, list, and table structure; handles nested styles and runs
- Extracts images or embeds them inline according to ``attachment_mode``
- Renderer supports bidirectional workflows (:doc:`bidirectional`)

Common options: ``DocxOptions`` (tables, style normalisation, image handling) and ``DocxRendererOptions``
(default fonts, style mapping, template overrides).

PowerPoint Presentations (PPTX)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Parser:* ``PptxToAstConverter`` — *Renderer:* ``PptxRenderer``

- Slide-by-slide extraction with optional speaker notes and slide numbers
- Pulls text from shapes, tables, and grouped items; captures alt text for accessibility
- Works well with ``--collate`` to assemble slide decks into long-form markdown

OpenDocument Suite (ODT & ODP)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Parsers:* ``OdtToAstConverter`` & ``OdpToAstConverter`` — *Renderers:* ``OdtRenderer`` & ``OdpRenderer``

- Full bidirectional conversion support for OpenDocument Text and Presentation formats
- Uses ``odfpy`` to preserve structure, lists, tables, and embedded media
- Parsers extract content while maintaining formatting and document structure
- Renderers support Markdown-to-ODT/ODP conversion for round-trip workflows
- Shares attachment controls and works with ``renderer_options=MarkdownRendererOptions(...)`` for unified formatting
- Ideal companion for LibreOffice / OpenOffice pipelines and cross-format document workflows

Rich Text Format (RTF)
~~~~~~~~~~~~~~~~~~~~~~

*Parser & Renderer:* ``RtfToAstConverter`` / ``RtfRenderer``

- Converts legacy RTF documents with paragraph, list, and inline formatting
- Renderer provides round-trip support for MailMerge-style workflows

HTML & Web Archives
~~~~~~~~~~~~~~~~~~~~

*Parsers:* ``HtmlToAstConverter`` & ``MhtmlToAstConverter`` — *Renderer:* ``HtmlRenderer``

- Sanitisation-aware HTML conversion with configurable handling of inline tags and raw HTML blocks
- Optional readability extraction (``--html-use-readability``) removes navigation chrome using readability-lxml
- Secure remote fetching through ``NetworkFetchOptions`` (rate limiting, host allowlists, HTTPS enforcement)
- Template modes (inject/replace/jinja) in the renderer support custom HTML generation
- Native Hugo/Jekyll site generation via ``generate-site`` command (:doc:`static_sites`)

Email Messages (EML/MSG)
~~~~~~~~~~~~~~~~~~~~~~~~

*Parser:* ``EmlToAstConverter``

- Flattens email threads, quoted replies, and multipart content into readable Markdown
- Preserves headers, inline images, and attachments; optional thread-aware formatting

EPUB eBooks
~~~~~~~~~~~

*Parser:* ``EpubToAstConverter`` — *Renderer:* ``EpubRenderer``

- Chapter-aware extraction with configurable TOC generation and chapter merging
- Automatically resolves embedded resources and applies attachment policy

FictionBook 2.0 (FB2)
~~~~~~~~~~~~~~~~~~~~~

*Parser:* ``Fb2ToAstConverter``

- Supports standalone ``.fb2`` files and zipped ``.fb2`` bundles, validating archives before parsing
- Preserves FictionBook metadata (titles, authors, annotations, genres) and merges note bodies when desired
- Converts sections, poems, and epigraphs into structured headings and paragraphs while reusing HTML inline semantics
- Attachment pipeline handles embedded binaries (images) with the full ``attachment_mode`` feature set
- Options: ``Fb2Options`` (note inclusion, notes heading label, encoding fallbacks)

Compiled HTML Help (CHM)
~~~~~~~~~~~~~~~~~~~~~~~~

*Parser:* ``ChmParser``

- Opens Microsoft CHM archives, extracts HTML topics, and reuses the HTML converter for consistent output
- Useful when migrating legacy documentation sets

Markup & Knowledge-Management Formats
-------------------------------------

Markdown
~~~~~~~~

*Parser & Renderer:* ``MarkdownToAstConverter`` / ``MarkdownRenderer``

- Supports flavour-specific parsing and rendering (GFM, CommonMark, Markdown Plus, etc.)
- Enables bidirectional conversion to DOCX/HTML/PDF (see :doc:`bidirectional`)
- Works with ``MarkdownParserOptions`` and ``MarkdownRendererOptions`` for fine control of tables, code fences, and math

AsciiDoc
~~~~~~~~~

*Parser & Renderer:* ``AsciiDocParser`` / ``AsciiDocRenderer``

- Handles attributes, admonitions, include directives (secure by default), and inline formatting
- Renderer produces lightweight AsciiDoc, enabling round trips between Markdown and AsciiDoc ecosystems

reStructuredText
~~~~~~~~~~~~~~~~

*Parser & Renderer:* ``RestructuredTextParser`` / ``RestructuredTextRenderer``

- Parses documents using docutils, including directives, definition lists, and field lists
- Renderer targets Sphinx-friendly output and supports flavour-specific sanitisation

Textile
~~~~~~~

*Parser & Renderer:* ``TextileParser`` / ``TextileRenderer``

- Uses the ``textile`` library to turn Textile markup into HTML before reusing the HTML parser for AST construction
- Supports inline formatting, tables, and footnotes while honouring the shared attachment and security pipeline
- Rendering offers extended block syntax, HTML passthrough controls, and line-wrapping preferences
- Options: ``TextileParserOptions`` / ``TextileRendererOptions``

Org Mode
~~~~~~~~

*Parser & Renderer:* ``OrgParser`` / ``OrgRenderer``

- Provides full bidirectional conversions for headings, TODO keywords, drawer metadata, and code blocks
- Ideal for Emacs-based knowledge bases that need Markdown or DOCX exports

MediaWiki
~~~~~~~~~

*Parser:* ``MediaWikiParser`` — *Renderer:* ``MediaWikiRenderer``

- Full bidirectional conversion support for MediaWiki markup
- Parser handles wiki tables, templates, categories, internal/external links, and formatting
- Renderer emits MediaWiki markup from the common AST, enabling Markdown → Wiki migrations
- Combine with any parser to publish to wikis without manual rewriting
- Ideal for migrating between wiki platforms or converting wiki content to other formats

LaTeX / TeX
~~~~~~~~~~~

*Parser & Renderer:* ``LatexParser`` / ``LatexRenderer``

- Parses structural LaTeX (sections, environments, equations) into the AST
- Renderer can generate snippets suitable for inclusion in larger LaTeX projects

OpenAPI/Swagger Specifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Parser:* ``OpenApiParser``

- Supports both OpenAPI 3.x and Swagger 2.0 formats in YAML or JSON
- Parses API metadata (title, version, servers, contact, license)
- Converts paths and operations into structured headings with parameter and response tables
- Optional tag-based grouping for organized API documentation
- Includes component schema definitions with property tables
- Handles deprecated operations with filtering options

Essentials:

- Options class: ``OpenApiParserOptions`` (see :doc:`options`)
- CLI prefix: ``--openapi-*``

.. code-block:: bash

   # Convert OpenAPI spec to Markdown documentation
   all2md api-spec.yaml

   # Exclude deprecated endpoints
   all2md api-spec.yaml --no-openapi-include-deprecated

   # Disable tag grouping for sequential listing
   all2md swagger.json --no-openapi-group-by-tag

Data, Code, and Archives
------------------------

Spreadsheets (XLSX & ODS)
~~~~~~~~~~~~~~~~~~~~~~~~~~

*Parsers:* ``XlsxToAstConverter`` & ``OdsSpreadsheetToAstConverter``

- Iterate over worksheets with sheet filtering, row/column limits, and truncation indicators
- Produce clean Markdown tables with optional sheet-title headings

Delimited Files (CSV/TSV)
~~~~~~~~~~~~~~~~~~~~~~~~~~

*Parser:* ``CsvToAstConverter``

- Dialect detection, encoding handling, and size guards for large datasets
- Shares spreadsheet options such as ``max_rows`` and ``max_cols``

Jupyter Notebooks (IPYNB)
~~~~~~~~~~~~~~~~~~~~~~~~~~

*Parser & Renderer:* ``IpynbToAstConverter`` / ``IpynbRenderer``

- Extracts code cells, rich outputs, and metadata with truncation controls for verbose outputs
- Renderer can rebuild lightweight notebooks from Markdown content

Archive Formats (TAR/7Z/RAR)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Parser:* ``ArchiveToAstConverter``

- Supports TAR (including .tgz, .tar.gz, .tbz2, .tar.bz2, .txz, .tar.xz), 7Z, and RAR archives
- Recursively extracts and converts parseable files to AST using appropriate format parsers
- Automatically detects and processes nested archives
- Supports file filtering with include/exclude patterns for selective extraction
- Extracts resource files (images, binaries) to attachment directory when configured
- Creates structured document with headings for each archive member
- Handles compressed archives transparently with automatic decompression

Source Code & Plain Text
~~~~~~~~~~~~~~~~~~~~~~~~~

*Parsers:* ``SourceCodeToAstConverter`` & ``PlainTextToAstConverter`` — *Renderer:* ``PlainTextRenderer``

- ``sourcecode`` uses Pygments lexers to normalise more than 200 programming and config formats
- ``plaintext`` handles everything else, mapping headings and simple structure where possible

ZIP Archives
~~~~~~~~~~~~

*Parser:* ``ZipToAstConverter``

- Recursively inspects archive members, auto-detects each entry's format, and merges content under section headings
- Supports include/exclude patterns, directory depth limits, and asset extraction for non-convertible files

AST JSON (Developer Format)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Parser & Renderer:* ``AstJsonParser`` / ``AstJsonRenderer``

- Serialises the document AST to a stable JSON structure for testing, caching, or external tooling
- Helpful when building custom transforms or diffing structural changes

Next Steps
----------

- :doc:`cli` — complete reference for flags such as ``--format``, ``--preset``, ``--merge-from-list``, and rich output options
- :doc:`options` — exhaustive dataclass reference including security helpers and Markdown flavours
- :doc:`transforms` — manipulate content with built-in transforms (TOC generation, heading IDs, boilerplate removal)
- :doc:`attachments` — deep dive on download/base64/annotation strategies shared by every parser
