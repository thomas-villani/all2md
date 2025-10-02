Supported Formats
=================

all2md supports a wide range of document formats. This guide provides detailed examples and format-specific options for each supported type.

.. contents:: Formats
   :local:
   :depth: 2

Document Formats
----------------

PDF Documents
~~~~~~~~~~~~~

**File Extensions:** ``.pdf``

**Dependencies:** ``pip install all2md[pdf]``

**Technology:** PyMuPDF (fitz) for advanced PDF parsing

PDF processing includes sophisticated table detection, multi-column layout handling, and intelligent text extraction.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Simple conversion
   markdown = to_markdown('document.pdf')

   # With images downloaded
   markdown = to_markdown('document.pdf',
                         attachment_mode='download',
                         attachment_output_dir='./pdf_images')

**Advanced Options:**

.. code-block:: python

   from all2md import to_markdown, PdfOptions

   options = PdfOptions(
       pages=[0, 1, 2],                    # Process first 3 pages only
       enable_table_fallback_detection=True, # Enable fallback table detection
       detect_columns=True,                # Handle multi-column layouts (default)
       header_percentile_threshold=75,     # Header detection threshold
       merge_hyphenated_words=True,        # Fix line-break hyphens
       attachment_mode='base64'            # Embed images as base64
   )

   markdown = to_markdown('complex_report.pdf', options=options)

**Command Line:**

.. code-block:: bash

   # Basic conversion
   all2md document.pdf

   # With specific pages and image download
   all2md document.pdf --pdf-pages "0,1,2" --attachment-mode download --markdown-emphasis-symbol "*"

**PDF-Specific Features:**

* **Table Detection:** Advanced algorithm detects and preserves table structures
* **Multi-Column Support:** Handles complex layouts with multiple columns
* **Image Extraction:** Extracts and processes embedded images
* **Header/Footer Detection:** Identifies and handles recurring elements
* **Page Selection:** Process specific pages or ranges

Word Documents (DOCX)
~~~~~~~~~~~~~~~~~~~~~

**File Extensions:** ``.docx``

**Dependencies:** ``pip install all2md[docx]``

**Technology:** python-docx for comprehensive Word document parsing

Full formatting preservation including styles, tables, images, and document structure.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Simple conversion
   markdown = to_markdown('document.docx')

   # With custom formatting
   markdown = to_markdown('document.docx',
                         emphasis_symbol='_',
                         use_hash_headings=True)

**Advanced Options:**

.. code-block:: python

   from all2md import to_markdown, DocxOptions, MarkdownOptions

   # Custom Markdown formatting
   md_options = MarkdownOptions(
       emphasis_symbol='_',                # Use underscores for emphasis
       bullet_symbols='•◦▪',              # Custom bullet points string
       page_separator_template="--- Page {page_num} ---" # Include page numbers in separators
   )

   options = DocxOptions(
       markdown_options=md_options,
       preserve_tables=True,               # Maintain table formatting
       attachment_mode='download',         # Download images locally
       attachment_output_dir='./doc_images'
   )

   markdown = to_markdown('formatted_document.docx', options=options)

**Command Line:**

.. code-block:: bash

   # Basic conversion
   all2md document.docx --out output.md

   # Custom formatting with image download
   all2md document.docx --markdown-emphasis-symbol "_" --attachment-mode download

**DOCX-Specific Features:**

* **Table Handling:** Configurable preservation of table structures
* **Image Processing:** Automatic extraction of embedded images
* **List Formatting:** Maintains numbered and bulleted list structures
* **Style Conversion:** Built-in conversion of Word styles to Markdown
* **Format Preservation:** Maintains bold, italic, and other text formatting

PowerPoint Presentations (PPTX)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**File Extensions:** ``.pptx``

**Dependencies:** ``pip install all2md[pptx]``

**Technology:** python-pptx for presentation parsing

Slide-by-slide extraction with support for speaker notes, shapes, and embedded content.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Convert presentation
   markdown = to_markdown('presentation.pptx')

**Advanced Options:**

.. code-block:: python

   from all2md import to_markdown, PptxOptions

   options = PptxOptions(
       include_notes=True,                 # Include speaker notes
       include_slide_numbers=True,         # Add slide number headers
       attachment_mode='base64',           # Embed images as base64
       markdown_options=MarkdownOptions(
           page_separator='---'            # Custom slide separator
       )
   )

   markdown = to_markdown('detailed_presentation.pptx', options=options)

**Command Line:**

.. code-block:: bash

   # Include slide numbers
   all2md presentation.pptx --pptx-slide-numbers

   # Exclude speaker notes (default is to include them)
   all2md presentation.pptx --pptx-no-include-notes

   # Include slide numbers and keep speaker notes
   all2md presentation.pptx --pptx-slide-numbers

**PPTX-Specific Features:**

* **Slide Extraction:** Each slide becomes a section in Markdown
* **Speaker Notes:** Optional inclusion of presentation notes
* **Shape Processing:** Extracts text from text boxes and shapes
* **Image Handling:** Processes embedded images and charts
* **Layout Preservation:** Maintains slide structure and hierarchy

HTML Documents
~~~~~~~~~~~~~~

**File Extensions:** ``.html``, ``.htm``

**Dependencies:** ``pip install all2md[html]``

**Technology:** BeautifulSoup4 for robust HTML parsing

Intelligent conversion of web content with configurable element handling.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Convert HTML file
   markdown = to_markdown('webpage.html')

   # Convert HTML string
   html_content = '<h1>Title</h1><p>Content with <strong>bold</strong> text.</p>'
   markdown = to_markdown(html_content.encode('utf-8'))

**Advanced Options:**

.. code-block:: python

   from all2md import to_markdown, HtmlOptions, MarkdownOptions

   # Create MarkdownOptions for hash headings
   md_options = MarkdownOptions(
       use_hash_headings=True              # Use # syntax for headings
   )

   options = HtmlOptions(
       strip_dangerous_elements=True,      # Remove script/style tags
       extract_title=True,                 # Extract HTML title element
       attachment_mode='download',         # Download referenced images
       attachment_base_url='https://example.com',  # Base URL for relative links
       detect_table_alignment=True,        # Auto-detect table alignment
       markdown_options=md_options         # Pass MarkdownOptions
   )

   markdown = to_markdown('complex_webpage.html', options=options)

**Command Line:**

.. code-block:: bash

   # Download images with base URL
   all2md webpage.html --attachment-mode download --attachment-base-url "https://example.com"

**HTML-Specific Features:**

* **Semantic Conversion:** Maps HTML elements to appropriate Markdown
* **Link Processing:** Handles relative and absolute URLs
* **Table Preservation:** Maintains HTML table structures
* **Image Downloading:** Fetches and processes referenced images
* **Custom Mapping:** Configurable element-to-Markdown conversion

Email Messages (EML)
~~~~~~~~~~~~~~~~~~~~

**File Extensions:** ``.eml``

**Dependencies:** Built-in (no additional packages required)

**Technology:** Python's built-in email libraries

Comprehensive email parsing with attachment handling and reply chain detection.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Convert email file
   markdown = to_markdown('message.eml')

**Advanced Options:**

.. code-block:: python

   from all2md import to_markdown, EmlOptions

   options = EmlOptions(
       include_headers=True,               # Include email headers
       detect_reply_separators=True,       # Clean up reply chains
       clean_wrapped_urls=True,            # Fix broken URLs
       attachment_mode='download',         # Save email attachments
       attachment_output_dir='./email_attachments',
       convert_html_to_markdown=True       # Convert HTML email parts to Markdown
   )

   markdown = to_markdown('thread.eml', options=options)

**Command Line:**

.. code-block:: bash

   # Process email with attachments
   all2md message.eml --attachment-mode download --attachment-output-dir ./attachments

**EML-Specific Features:**

* **Multi-part Handling:** Processes text and HTML parts
* **Attachment Extraction:** Saves email attachments locally
* **Reply Chain Detection:** Identifies and cleans reply separators
* **Header Processing:** Optional inclusion of email metadata
* **URL Cleanup:** Fixes wrapped and broken URLs in email text

EPUB E-books
~~~~~~~~~~~~

**File Extensions:** ``.epub``

**Dependencies:** ``pip install all2md[epub]``

**Technology:** ebooklib for EPUB processing

Chapter-by-chapter extraction with metadata and navigation preservation.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Convert EPUB
   markdown = to_markdown('book.epub')

**Advanced Options:**

.. code-block:: python

   from all2md import to_markdown, EpubOptions

   options = EpubOptions(
       extract_metadata=True,              # Include book metadata
       include_toc=True,                   # Add table of contents
       merge_chapters=False,               # Keep chapters separated
       attachment_mode='base64'            # Embed images as base64
   )

   markdown = to_markdown('novel.epub', options=options)

**Command Line:**

.. code-block:: bash

   # Include metadata and TOC
   all2md book.epub --include-metadata --include-toc

**EPUB-Specific Features:**

* **Chapter Extraction:** Each chapter becomes a major section
* **Metadata Processing:** Includes title, author, and publication info
* **Navigation Support:** Preserves table of contents structure
* **Image Handling:** Processes embedded illustrations
* **Content Filtering:** Skip non-content sections (copyright, etc.)

Data and Spreadsheet Formats
-----------------------------

Spreadsheet Files (XLSX/CSV/TSV)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**File Extensions:** ``.xlsx``, ``.csv``, ``.tsv``

**Dependencies:** ``pip install all2md[spreadsheet]``

**Technology:** openpyxl for XLSX files, built-in csv module for CSV/TSV

**Format Note:** All spreadsheet formats are handled by the unified ``spreadsheet`` converter with ``SpreadsheetOptions``.

Multi-sheet workbook processing with intelligent table formatting and automatic format detection.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Convert Excel spreadsheet
   markdown = to_markdown('data.xlsx')

   # Convert CSV
   markdown = to_markdown('data.csv')

   # Convert TSV
   markdown = to_markdown('data.tsv')

**Advanced Options:**

.. code-block:: python

   from all2md import to_markdown, SpreadsheetOptions

   options = SpreadsheetOptions(
       sheets=['Sheet1', 'Summary'],       # XLSX: Process specific sheets
       include_sheet_titles=True,          # Add sheet name headers
       render_formulas=True,               # XLSX: Use stored values vs formulas
       max_rows=1000,                      # Limit rows per sheet
       max_cols=20,                        # Limit columns per sheet
       truncation_indicator="...",         # Message when truncated
       detect_csv_dialect=True,            # CSV/TSV: Auto-detect format
       attachment_mode='alt_text'          # Future: embedded images
   )

   markdown = to_markdown('workbook.xlsx', options=options)

**Command Line:**

.. code-block:: bash

   # Process specific sheets in XLSX using regex pattern
   all2md workbook.xlsx --spreadsheet-sheets "^(Sheet1|Summary)$"

   # For multiple specific sheets, use JSON config (recommended)
   # In config.json: {"spreadsheet.sheets": ["Sheet1", "Summary"]}
   all2md workbook.xlsx --options-json config.json

   # Limit output size
   all2md large_data.csv --spreadsheet-max-rows 500 --spreadsheet-max-cols 10

**Spreadsheet-Specific Features:**

* **Unified Processing:** Single converter handles XLSX, CSV, and TSV
* **Multi-sheet Support:** Process all or selected XLSX worksheets
* **Auto-detection:** Automatically detects CSV/TSV delimiters and structure
* **Formula Handling:** XLSX can show stored values or formulas
* **Size Limiting:** Configurable row and column limits for large datasets
* **Clean Tables:** Produces well-formatted Markdown tables
* **Encoding Support:** Handles various character encodings for CSV/TSV

Notebook and Code Formats
--------------------------

Jupyter Notebooks (IPYNB)
~~~~~~~~~~~~~~~~~~~~~~~~~~

**File Extensions:** ``.ipynb``

**Dependencies:** Built-in (JSON processing)

**Technology:** Built-in JSON libraries

Complete notebook conversion including code cells, outputs, and metadata.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Convert notebook
   markdown = to_markdown('analysis.ipynb')

**Advanced Options:**

.. code-block:: python

   from all2md import to_markdown, IpynbOptions

   options = IpynbOptions(
       truncate_long_outputs=100,          # Truncate outputs after 100 lines
       truncate_output_message='... [output truncated] ...',  # Truncation message
       attachment_mode='base64',           # Embed plots as base64
       extract_metadata=True               # Include notebook metadata
   )

   markdown = to_markdown('data_analysis.ipynb', options=options)

**Command Line:**

.. code-block:: bash

   # Truncate long outputs
   all2md notebook.ipynb --ipynb-truncate-long-outputs 50 --ipynb-truncate-output-message "... output truncated ..."

**IPYNB-Specific Features:**

* **Code Cell Preservation:** Maintains syntax highlighting
* **Output Processing:** Handles text, HTML, and image outputs
* **Execution Count:** Optional display of cell execution order
* **Metadata Filtering:** Configurable metadata inclusion
* **Plot Handling:** Processes matplotlib and other plot outputs

Other Document Formats
-----------------------

Rich Text Format (RTF)
~~~~~~~~~~~~~~~~~~~~~~

**File Extensions:** ``.rtf``

**Dependencies:** ``pip install all2md[rtf]``

**Technology:** pyth3 for RTF parsing

Legacy document format support with formatting preservation.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Convert RTF
   markdown = to_markdown('document.rtf')

**RTF-Specific Features:**

* **Formatting Preservation:** Maintains bold, italic, and other formatting
* **Tables:** Not supported by the current RTF parser (pyth). Table-like content appears as plain paragraphs
* **Character Encoding:** Handles various RTF encodings
* **Legacy Compatibility:** Supports older RTF versions

OpenDocument Formats (ODT/ODP)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**File Extensions:** ``.odt`` (text), ``.odp`` (presentation)

**Dependencies:** ``pip install all2md[odf]``

**Technology:** odfpy for OpenDocument parsing

**Format Note:** Both ODT and ODP files are handled by the unified ``odf`` converter with ``OdfOptions``.

LibreOffice and OpenOffice document support with consistent processing for both text and presentation formats.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Convert OpenDocument Text
   markdown = to_markdown('document.odt')

   # Convert OpenDocument Presentation
   markdown = to_markdown('slides.odp')

**Advanced Options:**

.. code-block:: python

   from all2md import to_markdown, OdfOptions

   options = OdfOptions(
       preserve_tables=True,               # Maintain table formatting
       attachment_mode='download',         # Handle embedded images
       attachment_output_dir='./odf_images'
   )

   markdown = to_markdown('document.odt', options=options)

**Command Line:**

.. code-block:: bash

   # Disable table preservation
   all2md document.odt --odf-no-preserve-tables

   # Process with image download
   all2md presentation.odp --attachment-mode download --attachment-output-dir ./images

**ODF-Specific Features:**

* **Unified Processing:** Single converter handles both ODT and ODP formats
* **Style Mapping:** Converts ODF styles to Markdown
* **Table Processing:** Configurable table structure preservation
* **Image Extraction:** Processes embedded images and objects
* **Cross-platform:** Works with LibreOffice/OpenOffice documents

MHTML Web Archives
~~~~~~~~~~~~~~~~~~

**File Extensions:** ``.mhtml``, ``.mht``

**Dependencies:** ``pip install all2md[html]``

**Technology:** Built-in MIME processing + BeautifulSoup4

Single-file web archive processing with embedded resources.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Convert MHTML
   markdown = to_markdown('webpage.mhtml')

**MHTML-Specific Features:**

* **Resource Extraction:** Processes embedded images and stylesheets
* **Multi-part Handling:** Parses MIME multi-part structure
* **Web Archive Support:** Handles Internet Explorer and Edge web archives
* **Content Reconstruction:** Rebuilds page structure from archive

Images and Media
----------------

Image Files
~~~~~~~~~~~

**File Extensions:** ``.png``, ``.jpg``, ``.jpeg``, ``.gif``

**Dependencies:** Built-in

**Technology:** Built-in image processing

Image files are handled as attachments with various processing modes.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Images are typically embedded in other documents
   # Standalone image processing:
   try:
       markdown = to_markdown('image.png')
   except FormatError:
       print("Direct image conversion not supported")
       # Images are processed as attachments in other documents

**Image Processing Modes:**

* **base64:** Embed images as base64 data URLs
* **download:** Save images locally with file references
* **skip:** Ignore images (text-only conversion)
* **alt_text:** Replace with alt text or filename

Text and Code Formats
---------------------

Plain Text and Code Files
~~~~~~~~~~~~~~~~~~~~~~~~~

**File Extensions:** 200+ text formats including ``.txt``, ``.py``, ``.js``, ``.md``, ``.json``, ``.xml``, ``.yaml``, ``.cfg``, etc.

**Dependencies:** Built-in

**Technology:** Built-in text processing with encoding detection

Comprehensive support for text-based files with intelligent formatting.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Convert any text file
   markdown = to_markdown('script.py')
   markdown = to_markdown('config.json')
   markdown = to_markdown('README.txt')

**Text Processing Features:**

* **Encoding Detection:** Automatic character encoding detection
* **Format Preservation:** Maintains code formatting and structure
* **Syntax Detection:** Identifies file types for appropriate formatting
* **Large File Handling:** Efficient processing of large text files

Format Detection
----------------

Automatic Format Detection
~~~~~~~~~~~~~~~~~~~~~~~~~~~

all2md uses multiple strategies to detect document formats:

**1. Filename Extension** (Primary)

.. code-block:: python

   # Explicit extension mapping
   markdown = to_markdown('document.pdf')    # Detected as PDF
   markdown = to_markdown('data.xlsx')       # Detected as Excel
   markdown = to_markdown('page.html')       # Detected as HTML

**2. MIME Type Analysis** (Secondary)

.. code-block:: python

   import mimetypes
   # Uses system MIME database for verification
   mime_type = mimetypes.guess_type('document.pdf')[0]
   # 'application/pdf'

**3. Content Analysis** (Fallback)

.. code-block:: python

   # Magic byte detection for file objects
   with open('unknown_file', 'rb') as f:
       markdown = to_markdown(f)  # Analyzes content to detect format

**4. Explicit Format Specification**

.. code-block:: python

   # Override automatic detection
   markdown = to_markdown('file.dat', format='pdf')
   markdown = to_markdown(file_object, format='docx')

Programmatic Format Override
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can explicitly force a specific format converter, even when the file extension or content suggests otherwise. This is useful for:

* Files with incorrect or missing extensions
* Raw data that needs specific parsing
* Testing format converters with unusual inputs
* Working with streams or file-like objects without reliable metadata

**Basic Format Override:**

.. code-block:: python

   from all2md import to_markdown

   # Force PDF processing regardless of filename
   markdown = to_markdown('unknown_file', format='pdf')

   # Process data as HTML even if extension says .txt
   markdown = to_markdown('content.txt', format='html')

   # Explicitly handle file object as DOCX
   with open('document', 'rb') as f:
       markdown = to_markdown(f, format='docx')

**Format Override with Options:**

Combine explicit format specification with format-specific options:

.. code-block:: python

   from all2md import to_markdown, PdfOptions, DocxOptions, HtmlOptions

   # Force PDF processing with specific options
   pdf_options = PdfOptions(
       pages=[0, 1, 2],
       detect_columns=False,
       attachment_mode='base64'
   )
   markdown = to_markdown('file.dat', format='pdf', options=pdf_options)

   # Or use kwargs for simpler cases
   markdown = to_markdown(
       'mystery_file',
       format='pdf',
       pages=[0, 1, 2],
       detect_columns=False,
       attachment_mode='base64'
   )

   # Force Word processing with custom Markdown formatting
   from all2md import MarkdownOptions

   md_opts = MarkdownOptions(emphasis_symbol='_', use_hash_headings=False)
   docx_opts = DocxOptions(markdown_options=md_opts)
   markdown = to_markdown('document.bin', format='docx', options=docx_opts)

   # Force HTML processing with security settings
   html_opts = HtmlOptions(
       strip_dangerous_elements=True,
       extract_title=True
   )
   markdown = to_markdown('content', format='html', options=html_opts)

**Real-World Use Cases:**

.. code-block:: python

   from all2md import to_markdown, PdfOptions
   import tempfile

   # 1. Process downloaded content without filename
   def process_download(response_content):
       """Convert downloaded document regardless of source filename."""
       with tempfile.NamedTemporaryFile(suffix='.tmp') as tmp:
           tmp.write(response_content)
           tmp.flush()
           # Explicitly specify format since temp file has .tmp extension
           return to_markdown(tmp.name, format='pdf')

   # 2. Handle file objects from database BLOBs
   def convert_blob(file_data, detected_type):
       """Convert binary data with known type."""
       import io
       file_obj = io.BytesIO(file_data)
       # No filename available, must specify format
       return to_markdown(file_obj, format=detected_type)

   # 3. Batch process with format verification
   def safe_convert(filepath, expected_format='auto'):
       """Convert file with format validation."""
       try:
           # Try with expected format
           return to_markdown(filepath, format=expected_format)
       except Exception as e:
           print(f"Failed with {expected_format}, trying auto-detection")
           return to_markdown(filepath, format='auto')

   # 4. Pipeline with format transformation
   def extract_text_from_mixed_sources(files_dict):
       """Process different formats from various sources."""
       results = {}
       for name, (data, fmt) in files_dict.items():
           results[name] = to_markdown(data, format=fmt)
       return results

   # Example usage:
   mixed_data = {
       'report': (report_bytes, 'pdf'),
       'slides': (pptx_data, 'pptx'),
       'spreadsheet': (excel_bytes, 'spreadsheet')
   }
   converted = extract_text_from_mixed_sources(mixed_data)

**Testing Format Converters:**

.. code-block:: python

   from all2md import to_markdown

   # Test how different converters handle the same content
   test_file = 'ambiguous_file.bin'

   formats_to_try = ['pdf', 'docx', 'html', 'txt']
   results = {}

   for fmt in formats_to_try:
       try:
           result = to_markdown(test_file, format=fmt)
           results[fmt] = {'success': True, 'length': len(result)}
       except Exception as e:
           results[fmt] = {'success': False, 'error': str(e)}

   # Find which format worked best
   successful = {k: v for k, v in results.items() if v['success']}
   best_format = max(successful.items(), key=lambda x: x[1]['length'])[0]
   print(f"Best format: {best_format}")

**Important Notes:**

* **Validation**: Format override bypasses automatic detection but not validation. If the file isn't actually the specified format, conversion will fail.
* **Dependencies**: The required dependencies for the forced format must be installed.
* **Performance**: Explicit format specification is slightly faster than auto-detection.
* **Error Handling**: Always wrap format overrides in try-except blocks when the actual format is uncertain.

**Available Format Values:**

Valid format strings for the ``format`` parameter:

* ``'auto'`` - Automatic detection (default)
* ``'pdf'`` - PDF documents
* ``'docx'`` - Word documents (.docx)
* ``'pptx'`` - PowerPoint presentations (.pptx)
* ``'html'`` - HTML documents
* ``'mhtml'`` - MHTML web archives
* ``'eml'`` - Email messages (.eml)
* ``'epub'`` - EPUB e-books
* ``'rtf'`` - Rich Text Format
* ``'ipynb'`` - Jupyter notebooks
* ``'odf'`` - OpenDocument formats (.odt, .odp)
* ``'spreadsheet'`` - Excel/CSV/TSV files
* ``'image'`` - Image files (limited support)
* ``'txt'`` - Plain text (fallback)

Format-Specific Error Handling
------------------------------

Missing Dependencies
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown
   from all2md.exceptions import ImportError

   try:
       markdown = to_markdown('document.pdf')
   except ImportError as e:
       print(f"Missing PDF support: {e}")
       print("Install with: pip install all2md[pdf]")

Unsupported Features
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown
   from all2md.exceptions import MarkdownConversionError

   try:
       markdown = to_markdown('complex_document.pdf')
   except MarkdownConversionError as e:
       print(f"Conversion issue: {e}")
       # Try with different options or manual processing

Best Practices
--------------

1. **Install Only What You Need**

   .. code-block:: bash

      # Don't install all formats if you only need PDF
      pip install all2md[pdf]

2. **Use Explicit Options for Complex Documents**

   .. code-block:: python

      # Better control over complex conversions
      options = PdfOptions(
          pages=[0, 1, 2],
          enable_table_fallback_detection=True,
          attachment_mode='download'
      )
      markdown = to_markdown('complex.pdf', options=options)

3. **Handle Errors Gracefully**

   .. code-block:: python

      def safe_convert(file_path):
          try:
              return to_markdown(file_path)
          except ImportError as e:
              return f"Missing dependency: {e}"
          except Exception as e:
              return f"Conversion failed: {e}"

4. **Use Format-Specific Options**

   .. code-block:: python

      # Take advantage of format-specific features
      docx_options = DocxOptions(preserve_tables=True)
      pdf_options = PdfOptions(enable_table_fallback_detection=True)
      html_options = HtmlOptions(strip_dangerous_elements=True)

For complete configuration options, see the :doc:`options` reference. For troubleshooting specific format issues, visit the :doc:`troubleshooting` guide.