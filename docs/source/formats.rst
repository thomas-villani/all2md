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
       table_detection=True,               # Enable table detection
       column_detection=True,              # Handle multi-column layouts
       header_detection=True,              # Detect headers/footers
       merge_hyphenated_words=True,        # Fix line-break hyphens
       include_page_numbers=True,          # Add page number markers
       attachment_mode='base64'            # Embed images as base64
   )

   markdown = to_markdown('complex_report.pdf', options=options)

**Command Line:**

.. code-block:: bash

   # Basic conversion
   all2md document.pdf

   # With specific pages and image download
   all2md document.pdf --pages "0,1,2" --attachment-mode download

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
       bullet_symbols=['•', '◦', '▪'],    # Custom bullet points
       use_hash_headings=True             # Use # instead of underlines
   )

   options = DocxOptions(
       markdown_options=md_options,
       preserve_tables=True,               # Maintain table formatting
       extract_images=True,                # Process embedded images
       style_mapping=True,                 # Map Word styles to Markdown
       attachment_mode='download',         # Download images locally
       attachment_output_dir='./doc_images'
   )

   markdown = to_markdown('formatted_document.docx', options=options)

**Command Line:**

.. code-block:: bash

   # Basic conversion
   all2md document.docx --out output.md

   # Custom formatting with image download
   all2md document.docx --emphasis-symbol "_" --attachment-mode download

**DOCX-Specific Features:**

* **Style Preservation:** Maps Word styles to appropriate Markdown
* **Table Handling:** Preserves complex table structures
* **Image Processing:** Extracts images from document relationships
* **List Formatting:** Maintains numbered and bulleted list structures
* **Header Mapping:** Converts Word heading styles to Markdown headers

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
       include_speaker_notes=True,         # Include speaker notes
       include_slide_numbers=True,         # Add slide number headers
       extract_shapes=True,                # Process text boxes and shapes
       attachment_mode='base64',           # Embed images as base64
       slide_separator='---'               # Custom slide separator
   )

   markdown = to_markdown('detailed_presentation.pptx', options=options)

**Command Line:**

.. code-block:: bash

   # Include speaker notes
   all2md presentation.pptx --include-speaker-notes

**PPTX-Specific Features:**

* **Slide Extraction:** Each slide becomes a section in Markdown
* **Speaker Notes:** Optional inclusion of presentation notes
* **Shape Processing:** Extracts text from text boxes and shapes
* **Image Handling:** Processes embedded images and charts
* **Layout Preservation:** Maintains slide structure and hierarchy

HTML Documents
~~~~~~~~~~~~~~

**File Extensions:** ``.html``, ``.htm``

**Dependencies:** ``pip install all2md[html]`` (included in base)

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

   from all2md import to_markdown, HtmlOptions

   options = HtmlOptions(
       strip_dangerous_elements=True,      # Remove script/style tags
       convert_links=True,                 # Process hyperlinks
       preserve_tables=True,               # Maintain table structure
       attachment_mode='download',         # Download referenced images
       attachment_base_url='https://example.com',  # Base URL for relative links
       custom_element_mapping={            # Custom element handling
           'div.highlight': 'code_block',
           'span.note': 'emphasis'
       }
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
       max_chain_depth=3,                  # Limit reply chain depth
       convert_html_parts=True             # Convert HTML email parts
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
       include_metadata=True,              # Include book metadata
       include_toc=True,                   # Add table of contents
       chapter_separators=True,            # Add chapter dividers
       extract_images=True,                # Process book images
       attachment_mode='base64',           # Embed images as base64
       max_chapters=10                     # Limit number of chapters
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

Excel Spreadsheets (XLSX)
~~~~~~~~~~~~~~~~~~~~~~~~~~

**File Extensions:** ``.xlsx``

**Dependencies:** ``pip install all2md[csv]``

**Technology:** pandas for robust spreadsheet processing

Multi-sheet workbook processing with intelligent table formatting.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Convert spreadsheet
   markdown = to_markdown('data.xlsx')

**Advanced Options:**

.. code-block:: python

   from all2md import to_markdown, XlsxOptions

   options = XlsxOptions(
       sheets=['Sheet1', 'Summary'],       # Process specific sheets
       include_sheet_names=True,           # Add sheet name headers
       skip_empty_sheets=True,             # Ignore empty sheets
       table_formatting=True,              # Enhanced table formatting
       max_rows=1000,                      # Limit rows per sheet
       header_detection=True               # Auto-detect headers
   )

   markdown = to_markdown('workbook.xlsx', options=options)

**Command Line:**

.. code-block:: bash

   # Process specific sheets
   all2md workbook.xlsx --sheets "Sheet1,Summary"

**XLSX-Specific Features:**

* **Multi-sheet Support:** Process all or selected worksheets
* **Header Detection:** Automatically identifies table headers
* **Data Type Preservation:** Maintains formatting for dates, numbers
* **Table Formatting:** Creates clean Markdown tables
* **Empty Cell Handling:** Intelligent handling of sparse data

CSV/TSV Files
~~~~~~~~~~~~~

**File Extensions:** ``.csv``, ``.tsv``

**Dependencies:** ``pip install all2md[csv]`` (pandas) or built-in

**Technology:** pandas (preferred) or built-in csv module

Tabular data conversion with automatic delimiter detection.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Convert CSV
   markdown = to_markdown('data.csv')

   # Convert TSV
   markdown = to_markdown('data.tsv')

**Advanced Options:**

.. code-block:: python

   from all2md import to_markdown, CsvOptions

   options = CsvOptions(
       delimiter=',',                      # Explicit delimiter
       encoding='utf-8',                   # File encoding
       header_row=0,                       # Header row index
       skip_rows=0,                        # Rows to skip
       max_rows=500,                       # Limit output rows
       table_formatting='grid'             # Table style
   )

   markdown = to_markdown('large_dataset.csv', options=options)

**Command Line:**

.. code-block:: bash

   # Custom delimiter
   all2md data.txt --delimiter ";" --encoding "latin1"

**CSV/TSV-Specific Features:**

* **Auto-detection:** Automatically detects delimiters and structure
* **Encoding Support:** Handles various character encodings
* **Large File Handling:** Memory-efficient processing of large datasets
* **Flexible Parsing:** Configurable parsing parameters
* **Clean Tables:** Produces well-formatted Markdown tables

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
       include_outputs=True,               # Include cell outputs
       include_execution_count=True,       # Show execution numbers
       include_metadata=False,             # Skip cell metadata
       code_block_style='fenced',          # Code block formatting
       attachment_mode='base64',           # Embed plots as base64
       max_output_lines=100,               # Limit output length
       strip_ansi_codes=True               # Remove ANSI color codes
   )

   markdown = to_markdown('data_analysis.ipynb', options=options)

**Command Line:**

.. code-block:: bash

   # Include outputs and execution counts
   all2md notebook.ipynb --include-outputs --include-execution-count

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
* **Table Support:** Converts RTF tables to Markdown
* **Character Encoding:** Handles various RTF encodings
* **Legacy Compatibility:** Supports older RTF versions

OpenDocument Formats (ODT/ODP)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**File Extensions:** ``.odt`` (text), ``.odp`` (presentation)

**Dependencies:** ``pip install all2md[odf]``

**Technology:** odfpy for OpenDocument parsing

LibreOffice and OpenOffice document support.

**Basic Usage:**

.. code-block:: python

   from all2md import to_markdown

   # Convert OpenDocument Text
   markdown = to_markdown('document.odt')

   # Convert OpenDocument Presentation
   markdown = to_markdown('slides.odp')

**ODF-Specific Features:**

* **Style Mapping:** Converts ODF styles to Markdown
* **Table Processing:** Handles ODF table structures
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
~~~~~~~~~~~~~~~~~~~~~~~~~

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

Format-Specific Error Handling
------------------------------

Missing Dependencies
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from all2md import to_markdown
   from all2md.exceptions import ImportError

   try:
       markdown = to_markdown('document.pdf')
   except ImportError as e:
       print(f"Missing PDF support: {e}")
       print("Install with: pip install all2md[pdf]")

Unsupported Features
~~~~~~~~~~~~~~~~~~~

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
          table_detection=True,
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
      docx_options = DocxOptions(style_mapping=True)
      pdf_options = PdfOptions(table_detection=True)
      html_options = HtmlOptions(strip_dangerous_elements=True)

For complete configuration options, see the :doc:`options` reference. For troubleshooting specific format issues, visit the :doc:`troubleshooting` guide.