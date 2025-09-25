Configuration Options
====================

all2md provides extensive configuration options for customizing document conversion. This reference covers all available options classes and their parameters.

.. contents::
   :local:
   :depth: 3

Options Overview
----------------

all2md uses a hierarchical options system:

1. **Format-specific options** (``PdfOptions``, ``DocxOptions``, etc.)
2. **Common options** inherited from ``BaseOptions``
3. **Markdown formatting options** (``MarkdownOptions``)

Options can be provided in multiple ways:

.. code-block:: python

   from all2md import to_markdown, PdfOptions, MarkdownOptions

   # Method 1: Pre-configured options object
   options = PdfOptions(pages=[0, 1, 2], attachment_mode='download')
   markdown = to_markdown('doc.pdf', options=options)

   # Method 2: Keyword arguments (creates options object)
   markdown = to_markdown('doc.pdf', pages=[0, 1, 2], attachment_mode='download')

   # Method 3: Mixed (kwargs override options)
   markdown = to_markdown('doc.pdf', options=options, attachment_mode='base64')

Base Options
------------

``BaseOptions``
~~~~~~~~~~~~~~~

All format-specific options inherit from ``BaseOptions``, which provides common settings for attachment handling and Markdown formatting.

**Attachment Parameters:**

``attachment_mode`` : ``{"skip", "alt_text", "download", "base64"}``
   How to handle attachments and images in documents.

   * ``"skip"`` - Ignore all attachments
   * ``"alt_text"`` - Replace with alt text or filename (default)
   * ``"download"`` - Download attachments to local directory
   * ``"base64"`` - Embed attachments as base64 data URLs

   **Default:** ``"alt_text"``

   .. code-block:: python

      # Download images to directory
      options = PdfOptions(attachment_mode='download',
                          attachment_output_dir='./images')

      # Embed as base64
      options = PdfOptions(attachment_mode='base64')

``attachment_output_dir`` : ``str | None``
   Directory to save attachments when using ``download`` mode.

   **Default:** ``None``

   .. code-block:: python

      options = PdfOptions(
          attachment_mode='download',
          attachment_output_dir='./pdf_attachments'
      )

``attachment_base_url`` : ``str | None``
   Base URL for resolving relative attachment references.

   **Default:** ``None``

   .. code-block:: python

      # Useful for HTML documents with relative image paths
      options = HtmlOptions(
          attachment_mode='download',
          attachment_base_url='https://example.com'
      )

``markdown_options`` : ``MarkdownOptions | None``
   Common Markdown formatting settings that apply across formats.

   **Default:** ``None`` (uses format defaults)

   .. code-block:: python

      md_options = MarkdownOptions(
          emphasis_symbol='_',
          bullet_symbols='•◦▪',
          page_separator='---'
      )

      options = PdfOptions(markdown_options=md_options)

Markdown Options
----------------

``MarkdownOptions``
~~~~~~~~~~~~~~~~~~~

Controls common Markdown formatting settings used across all conversion modules.

**Text Formatting:**

``escape_special`` : ``bool``
   Whether to escape special Markdown characters in text content.

   **Default:** ``True``

   .. code-block:: python

      # Disable escaping (may cause formatting issues)
      options = MarkdownOptions(escape_special=False)

``emphasis_symbol`` : ``{"*", "_"}``
   Symbol to use for emphasis and italic formatting.

   **Default:** ``"*"``

   .. code-block:: python

      # Use underscores for emphasis
      options = MarkdownOptions(emphasis_symbol='_')

``bullet_symbols`` : ``str``
   Characters to cycle through for nested bullet lists.

   **Default:** ``"*-+"``

   .. code-block:: python

      # Custom bullet symbols
      options = MarkdownOptions(bullet_symbols='•◦▪')

**Page and Section Formatting:**

``page_separator`` : ``str``
   Text used to separate pages or sections in output.

   **Default:** ``"-----"``

``page_separator_format`` : ``str``
   Format string for page separators. Can include ``{page_num}`` placeholder.

   **Default:** ``"-----"``

   .. code-block:: python

      options = MarkdownOptions(
          page_separator='===',
          page_separator_format='=== Page {page_num} ===',
          include_page_numbers=True
      )

``include_page_numbers`` : ``bool``
   Whether to include page numbers in page separators.

   **Default:** ``False``

``list_indent_width`` : ``int``
   Number of spaces to use for each level of list indentation.

   **Default:** ``4``

**Special Formatting Modes:**

``underline_mode`` : ``{"html", "markdown", "ignore"}``
   How to handle underlined text:

   * ``"html"`` - Use ``<u>text</u>`` tags (default)
   * ``"markdown"`` - Use ``__text__`` (non-standard)
   * ``"ignore"`` - Strip underline formatting

``superscript_mode`` : ``{"html", "markdown", "ignore"}``
   How to handle superscript text:

   * ``"html"`` - Use ``<sup>text</sup>`` tags (default)
   * ``"markdown"`` - Use ``^text^`` (non-standard)
   * ``"ignore"`` - Strip superscript formatting

``subscript_mode`` : ``{"html", "markdown", "ignore"}``
   How to handle subscript text:

   * ``"html"`` - Use ``<sub>text</sub>`` tags (default)
   * ``"markdown"`` - Use ``~text~`` (non-standard)
   * ``"ignore"`` - Strip subscript formatting

   .. code-block:: python

      # Use Markdown-style formatting (non-standard)
      options = MarkdownOptions(
          underline_mode='markdown',
          superscript_mode='markdown',
          subscript_mode='markdown'
      )

Format-Specific Options
-----------------------

PDF Options
~~~~~~~~~~~

``PdfOptions(BaseOptions)``

Advanced PDF processing with sophisticated table detection and layout analysis.

**Page Selection:**

``pages`` : ``list[int] | None``
   Specific page numbers to convert using 0-based indexing.

   **Default:** ``None`` (converts all pages)

   .. code-block:: python

      # Convert first 3 pages
      options = PdfOptions(pages=[0, 1, 2])

      # Convert specific pages
      options = PdfOptions(pages=[0, 4, 9, 15])

``password`` : ``str | None``
   Password for encrypted PDF documents.

   **Default:** ``None``

   .. code-block:: python

      options = PdfOptions(password='secret123')

**Header Detection:**

``header_sample_pages`` : ``int | list[int] | None``
   Pages to sample for header font size analysis.

   **Default:** ``None`` (samples all pages)

   .. code-block:: python

      # Sample first 3 pages for header detection
      options = PdfOptions(header_sample_pages=[0, 1, 2])

``header_percentile_threshold`` : ``float``
   Percentile threshold for header detection (e.g., 75 = top 25% of font sizes).

   **Default:** ``75.0``

``header_min_occurrences`` : ``int``
   Minimum occurrences of a font size to consider it for headers.

   **Default:** ``3``

``header_size_allowlist`` : ``list[float] | None``
   Specific font sizes to always treat as headers.

   **Default:** ``None``

``header_size_denylist`` : ``list[float] | None``
   Font sizes to never treat as headers.

   **Default:** ``None``

``header_use_font_weight`` : ``bool``
   Consider bold/font weight when detecting headers.

   **Default:** ``True``

``header_use_all_caps`` : ``bool``
   Consider all-caps text as potential headers.

   **Default:** ``True``

   .. code-block:: python

      # Fine-tune header detection
      options = PdfOptions(
          header_sample_pages=[0, 1, 2],
          header_percentile_threshold=80,
          header_min_occurrences=2,
          header_use_font_weight=True,
          header_use_all_caps=True
      )

**Layout Processing:**

``detect_columns`` : ``bool``
   Enable multi-column layout detection.

   **Default:** ``True``

``merge_hyphenated_words`` : ``bool``
   Merge words split by hyphens at line breaks.

   **Default:** ``True``

``handle_rotated_text`` : ``bool``
   Process rotated text blocks.

   **Default:** ``True``

``column_gap_threshold`` : ``float``
   Minimum gap between columns in points.

   **Default:** ``20.0``

   .. code-block:: python

      # Disable column detection for simple layouts
      options = PdfOptions(
          detect_columns=False,
          merge_hyphenated_words=True
      )

**Table Detection:**

``table_fallback_detection`` : ``bool``
   Use heuristic fallback if PyMuPDF table detection fails.

   **Default:** ``True``

``detect_merged_cells`` : ``bool``
   Attempt to identify merged cells in tables.

   **Default:** ``True``

``table_ruling_line_threshold`` : ``float``
   Threshold for detecting table ruling lines.

   **Default:** ``0.5``

   .. code-block:: python

      # Advanced table processing
      options = PdfOptions(
          table_fallback_detection=True,
          detect_merged_cells=True,
          table_ruling_line_threshold=0.3
      )

**Image Processing:**

``image_placement_markers`` : ``bool``
   Add markers showing image positions.

   **Default:** ``True``

``include_image_captions`` : ``bool``
   Try to extract image captions.

   **Default:** ``True``

   .. code-block:: python

      # Comprehensive PDF processing
      options = PdfOptions(
          pages=[0, 1, 2],
          detect_columns=True,
          table_fallback_detection=True,
          attachment_mode='download',
          attachment_output_dir='./pdf_images',
          image_placement_markers=True,
          include_image_captions=True
      )

Word Document Options
~~~~~~~~~~~~~~~~~~~~~

``DocxOptions(BaseOptions)``

Microsoft Word document processing with formatting preservation.

``preserve_tables`` : ``bool``
   Whether to preserve table formatting in Markdown.

   **Default:** ``True``

   .. code-block:: python

      # Basic DOCX conversion with image download
      options = DocxOptions(
          preserve_tables=True,
          attachment_mode='download',
          attachment_output_dir='./word_images'
      )

      # Custom formatting
      md_options = MarkdownOptions(
          emphasis_symbol='_',
          bullet_symbols='•◦▪'
      )

      options = DocxOptions(
          preserve_tables=True,
          markdown_options=md_options
      )

PowerPoint Options
~~~~~~~~~~~~~~~~~~

``PptxOptions(BaseOptions)``

Microsoft PowerPoint presentation processing.

``slide_numbers`` : ``bool``
   Whether to include slide numbers in the output.

   **Default:** ``False``

``include_notes`` : ``bool``
   Whether to include speaker notes in the conversion.

   **Default:** ``True``

   .. code-block:: python

      # Include slide numbers and speaker notes
      options = PptxOptions(
          slide_numbers=True,
          include_notes=True,
          attachment_mode='base64'
      )

      # Slides only (no notes)
      options = PptxOptions(
          slide_numbers=True,
          include_notes=False
      )

HTML Options
~~~~~~~~~~~~

``HtmlOptions(BaseOptions)``

HTML document processing with intelligent content extraction.

``extract_title`` : ``bool``
   Whether to extract and use the HTML ``<title>`` element.

   **Default:** ``False``

``strip_dangerous_elements`` : ``bool``
   Remove potentially dangerous HTML elements (script, style, etc.).

   **Default:** ``False``

   .. code-block:: python

      # Safe HTML processing
      options = HtmlOptions(
          extract_title=True,
          strip_dangerous_elements=True,
          attachment_mode='download',
          attachment_base_url='https://example.com'
      )

Email Options
~~~~~~~~~~~~~

``EmlOptions(BaseOptions)``

Email message processing with thread handling and attachment support.

**Header and Structure:**

``include_headers`` : ``bool``
   Whether to include email headers in the output.

   **Default:** ``True``

``preserve_thread_structure`` : ``bool``
   Whether to maintain email thread/reply chain structure.

   **Default:** ``True``

``normalize_headers`` : ``bool``
   Whether to normalize header formatting.

   **Default:** ``True``

``preserve_raw_headers`` : ``bool``
   Whether to preserve raw header formatting.

   **Default:** ``False``

**Date Formatting:**

``date_format_mode`` : ``DateFormatMode``
   How to format email dates.

   **Default:** Uses system default

``date_strftime_pattern`` : ``str``
   Custom date formatting pattern.

   **Default:** Uses system default

**Content Processing:**

``convert_html_to_markdown`` : ``bool``
   Whether to convert HTML email parts to Markdown.

   **Default:** ``True``

``clean_quotes`` : ``bool``
   Whether to clean up quote formatting.

   **Default:** ``True``

``detect_reply_separators`` : ``bool``
   Whether to detect and clean reply separators.

   **Default:** ``True``

``clean_wrapped_urls`` : ``bool``
   Whether to fix wrapped and broken URLs.

   **Default:** ``True``

``url_wrappers`` : ``list[str] | None``
   Custom URL wrapper patterns to detect.

   **Default:** Standard patterns

   .. code-block:: python

      # Comprehensive email processing
      options = EmlOptions(
          include_headers=True,
          preserve_thread_structure=True,
          convert_html_to_markdown=True,
          clean_quotes=True,
          detect_reply_separators=True,
          clean_wrapped_urls=True,
          attachment_mode='download',
          attachment_output_dir='./email_attachments'
      )

      # Clean, simplified email conversion
      options = EmlOptions(
          include_headers=False,
          preserve_thread_structure=False,
          clean_quotes=True,
          attachment_mode='skip'
      )

Jupyter Notebook Options
~~~~~~~~~~~~~~~~~~~~~~~~

``IpynbOptions(BaseOptions)``

Jupyter Notebook processing with output handling.

``truncate_long_outputs`` : ``int | None``
   Maximum number of lines for text outputs before truncating.

   **Default:** ``None`` (no truncation)

``truncate_output_message`` : ``str | None``
   Message to display when truncating outputs.

   **Default:** ``"\\n... (output truncated) ...\\n"``

   .. code-block:: python

      # Limit long outputs
      options = IpynbOptions(
          truncate_long_outputs=50,
          truncate_output_message='--- OUTPUT TRUNCATED ---',
          attachment_mode='base64'
      )

      # No output truncation
      options = IpynbOptions(
          truncate_long_outputs=None,
          attachment_mode='download'
      )

EPUB Options
~~~~~~~~~~~~

``EpubOptions(BaseOptions)``

EPUB e-book processing with chapter and TOC handling.

``merge_chapters`` : ``bool``
   Whether to merge chapters into a single continuous document.

   **Default:** ``True``

``include_toc`` : ``bool``
   Whether to generate and prepend a Markdown Table of Contents.

   **Default:** ``True``

   .. code-block:: python

      # Continuous document with TOC
      options = EpubOptions(
          merge_chapters=True,
          include_toc=True,
          attachment_mode='base64'
      )

      # Separate chapters without TOC
      options = EpubOptions(
          merge_chapters=False,
          include_toc=False,
          attachment_mode='download',
          attachment_output_dir='./epub_images'
      )

OpenDocument Options
~~~~~~~~~~~~~~~~~~~~

``OdfOptions(BaseOptions)``

OpenDocument Text (.odt) and Presentation (.odp) processing.

``preserve_tables`` : ``bool``
   Whether to preserve table formatting in Markdown.

   **Default:** ``True``

   .. code-block:: python

      options = OdfOptions(
          preserve_tables=True,
          attachment_mode='download',
          attachment_output_dir='./odf_attachments'
      )

RTF Options
~~~~~~~~~~~

``RtfOptions(BaseOptions)``

Rich Text Format processing. Inherits all settings from ``BaseOptions`` with no additional parameters.

   .. code-block:: python

      options = RtfOptions(
          attachment_mode='base64'
      )

MHTML Options
~~~~~~~~~~~~~

``MhtmlOptions(BaseOptions)``

MHTML web archive processing. Inherits all settings from ``BaseOptions`` with no additional parameters.

   .. code-block:: python

      options = MhtmlOptions(
          attachment_mode='download',
          attachment_output_dir='./mhtml_assets'
      )

Option Usage Patterns
---------------------

Simple Conversions
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown

   # Use defaults
   markdown = to_markdown('document.pdf')

   # Basic customization with kwargs
   markdown = to_markdown('document.pdf',
                         attachment_mode='download',
                         attachment_output_dir='./images')

Pre-configured Options
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown, PdfOptions, MarkdownOptions

   # Create reusable configuration
   md_options = MarkdownOptions(
       emphasis_symbol='_',
       bullet_symbols='•◦▪',
       page_separator='---'
   )

   pdf_options = PdfOptions(
       pages=[0, 1, 2],
       detect_columns=True,
       attachment_mode='download',
       attachment_output_dir='./pdf_images',
       markdown_options=md_options
   )

   # Use configuration
   markdown = to_markdown('document.pdf', options=pdf_options)

Mixed Configuration
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Override specific settings
   markdown = to_markdown('document.pdf',
                         options=pdf_options,
                         attachment_mode='base64')  # Override download mode

Batch Processing
~~~~~~~~~~~~~~~

.. code-block:: python

   import os
   from all2md import to_markdown, PdfOptions

   # Consistent options for batch processing
   options = PdfOptions(
       detect_columns=True,
       attachment_mode='download',
       attachment_output_dir='./batch_images'
   )

   for filename in os.listdir('./documents'):
       if filename.endswith('.pdf'):
           input_path = os.path.join('./documents', filename)
           output_path = os.path.join('./output', f"{filename}.md")

           markdown = to_markdown(input_path, options=options)

           with open(output_path, 'w', encoding='utf-8') as f:
               f.write(markdown)

JSON Configuration
~~~~~~~~~~~~~~~~~

Options can be serialized to/from JSON for configuration files:

.. code-block:: python

   import json
   from all2md import PdfOptions, MarkdownOptions

   # Create configuration
   md_options = MarkdownOptions(emphasis_symbol='_')
   pdf_options = PdfOptions(
       pages=[0, 1, 2],
       attachment_mode='download',
       markdown_options=md_options
   )

   # Serialize to JSON (manual - dataclasses don't auto-serialize)
   config = {
       'pages': [0, 1, 2],
       'attachment_mode': 'download',
       'attachment_output_dir': './images',
       'markdown_emphasis_symbol': '_'
   }

   with open('config.json', 'w') as f:
       json.dump(config, f)

   # Use from command line
   # all2md document.pdf --options-json config.json

Best Practices
--------------

1. **Start Simple**
   Begin with default options and add customization as needed.

2. **Use Format-Specific Options**
   Take advantage of format-specific features like PDF table detection or email thread handling.

3. **Consistent Formatting**
   Use ``MarkdownOptions`` to maintain consistent formatting across different document types.

4. **Handle Attachments Appropriately**
   Choose attachment mode based on your use case:
   - ``download`` for local processing
   - ``base64`` for self-contained documents
   - ``skip`` for text-only extraction

5. **Performance Considerations**
   For large documents, consider:
   - Processing specific pages only (``pages`` parameter)
   - Limiting output truncation (``truncate_long_outputs``)
   - Skipping attachments if not needed

For practical usage examples, see the :doc:`formats` guide. For troubleshooting configuration issues, visit the :doc:`troubleshooting` section.