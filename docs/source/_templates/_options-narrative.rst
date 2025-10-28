Configuration Options
=====================

all2md exposes every converter knob as an immutable dataclass. The command line, environment variables, presets,
and Python API all hydrate the same option objects, so behaviour stays consistent regardless of entry point.

Overview
--------

The options stack is intentionally layered:

1. :class:`~all2md.options.base.BaseParserOptions` — shared attachment policy, metadata extraction, asset limits
2. Nested security helpers such as :class:`~all2md.options.common.NetworkFetchOptions` and
   :class:`~all2md.options.common.LocalFileAccessOptions`
3. Format-specific parser options (``PdfOptions``, ``HtmlOptions``, ``ZipOptions``, …) combined with
   renderer counterparts (``MarkdownRendererOptions``, ``HtmlRendererOptions``) via the ``renderer_options``
   parameter when rendering output

Because every class inherits from ``CloneFrozenMixin`` you can derive safe variants without mutating originals:

.. code-block:: python

   from all2md import to_markdown
   from all2md.options import HtmlOptions, MarkdownRendererOptions, NetworkFetchOptions

   hardened_network = NetworkFetchOptions(
       allow_remote_fetch=False,
       require_https=True,
       allowed_hosts=["docs.example.com"],
   )

   html_options = HtmlOptions(
       extract_title=True,
       network=hardened_network,
   )

   markdown_defaults = MarkdownRendererOptions(flavor="gfm")

   secure_html = to_markdown(
       "page.html",
       parser_options=html_options,
       renderer_options=markdown_defaults.create_updated(link_style="reference"),
   )

   hardened_html_options = html_options.create_updated(strip_dangerous_elements=True)

CLI flag mapping follows the field path. For example ``HtmlOptions.network.require_https`` becomes
``--html-network-require-https`` (and the env var ``ALL2MD_HTML_NETWORK_REQUIRE_HTTPS``). Nested collections such as
``ZipOptions.include_patterns`` accept multiple values via repeated flags or comma-separated lists.

Options Map
-----------

The table below shows where to look for the most commonly tuned converters.

.. list-table::
   :header-rows: 1
   :widths: 25 30 45

   * - Format / Feature
     - Options Class
     - Highlights
   * - PDF documents
     - ``PdfOptions``
     - Page selection, table/ruling detection, column heuristics, attachment templating
   * - Microsoft Office (DOCX/PPTX)
     - ``DocxOptions`` / ``PptxOptions``
     - Style preservation, image extraction, slide numbering, speaker notes
   * - Web content
     - ``HtmlOptions`` / ``MhtmlOptions``
     - Network security, sanitisation presets, Markdown flavour bridging
   * - Email threads
     - ``EmlOptions``
     - Header preservation, thread stitching, inline attachment handling
   * - EPUB / eBook containers
     - ``EpubOptions``
     - Chapter merging, TOC generation, CSS asset limits
   * - Spreadsheets & tabular data
     - ``XlsxOptions`` / ``OdsSpreadsheetOptions`` / ``CsvOptions``
     - Sheet filtering, row/column caps, truncation indicators
   * - Archives / batch processing
     - ``ZipOptions``
     - Include/exclude patterns, directory depth limits, section heading layout
   * - Markdown rendering
     - ``MarkdownRendererOptions`` / ``MarkdownParserOptions``
     - Flavour defaults (GFM/CommonMark/etc), table handling, HTML passthrough policy

Using Options
-------------

Python API
~~~~~~~~~~

Pass an options object directly or let ``to_markdown`` assemble one from keyword arguments. Nested dataclasses are
constructed automatically from matching kwargs.

.. code-block:: python

   from all2md import to_markdown
   from all2md.options import HtmlOptions, MarkdownRendererOptions

   markdown = to_markdown(
       "page.html",
       parser_options=HtmlOptions(
           extract_title=True,
           network=dict(
               allow_remote_fetch=False,
               allowed_hosts=["docs.example.com"],
               require_https=True,
           ),
       ),
       renderer_options=MarkdownRendererOptions(link_style="reference"),
   )

   # Kwargs override existing settings (nested dataclass fields are detected automatically)
   hardened = to_markdown(
       "page.html",
       parser_options=HtmlOptions(),
       allow_remote_fetch=False,
   )

Command Line
~~~~~~~~~~~~

CLI flags mirror the dataclass field names. Format-specific options use prefixes like ``--pdf-*`` or ``--html-*``.
Nested fields join their parents with dashes:

.. code-block:: bash

   # Harden HTML fetching and customise Markdown output
   all2md site.mhtml \
     --html-network-allow-remote-fetch false \
     --html-network-allowed-hosts docs.example.com \
     --html-network-require-https \
     --markdown-flavor gfm

   # ZIP archives with include/exclude filters
   all2md archive.zip \
     --zip-include "docs/**/*.md" \
     --zip-exclude "**/__pycache__/**" \
     --zip-create-section-headings

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

Any CLI flag can be expressed as ``ALL2MD_<DESTINATION>``. Dashes and dots become underscores. Booleans recognise
``true/false`` (or ``1/0``). Example shell snippet:

.. code-block:: bash

   export ALL2MD_ATTACHMENT_MODE=download
   export ALL2MD_PDF_PAGES="1-3,10"
   export ALL2MD_HTML_NETWORK_REQUIRE_HTTPS=true
   export ALL2MD_MARKDOWN_FLAVOR=gfm

   all2md report.pdf  # picks up defaults, still overrideable via CLI

Boolean Defaults Cheat Sheet
----------------------------

Options that default to ``True`` use ``--<prefix>-no-<field>`` on the CLI. This keeps the positive form in Python while
following common ``--no-*`` conventions in shell scripts.

.. list-table::
   :header-rows: 1
   :widths: 32 16 23 29

   * - Dataclass field
     - Default
     - CLI to enable
     - CLI to disable
   * - ``MarkdownRendererOptions.use_hash_headings``
     - ``True``
     - (default)
     - ``--markdown-no-use-hash-headings``
   * - ``PdfOptions.detect_columns``
     - ``True``
     - (default)
     - ``--pdf-no-detect-columns``
   * - ``PdfOptions.merge_hyphenated_words``
     - ``True``
     - (default)
     - ``--pdf-no-merge-hyphenated-words``
   * - ``HtmlOptions.preserve_nested_structure``
     - ``True``
     - (default)
     - ``--html-no-preserve-nested-structure``
   * - ``HtmlOptions.detect_table_alignment``
     - ``True``
     - (default)
     - ``--html-no-detect-table-alignment``
   * - ``PptxOptions.include_notes``
     - ``True``
     - (default)
     - ``--pptx-no-include-notes``
   * - ``EmlOptions.include_headers``
     - ``True``
     - (default)
     - ``--eml-no-include-headers``
   * - ``EpubOptions.merge_chapters``
     - ``True``
     - (default)
     - ``--epub-no-merge-chapters``
   * - ``OdtOptions.preserve_tables``
     - ``True``
     - (default)
     - ``--odt-no-preserve-tables``

For booleans that default to ``False`` simply use the positive flag (e.g. ``--html-strip-dangerous-elements``). The
full list—including renderer toggles and security helpers—is maintained in the generated :doc:`options` reference.
