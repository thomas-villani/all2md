Supported Formats
=================

all2md supports a comprehensive range of file formats for conversion to and from Markdown. This page provides detailed information about format support, capabilities, and limitations.

Document Formats
----------------

PDF (.pdf)
~~~~~~~~~~

**Capabilities:**
- Advanced text extraction with reading order preservation
- Table detection and conversion to Markdown tables
- Image extraction and base64 embedding
- Header/footer handling
- Multi-column layout support
- Font-based header detection

**Features:**
- PyMuPDF-powered processing for high accuracy
- Sophisticated table boundary detection
- Western reading order text sorting
- Complex layout analysis
- Password-protected PDF support

**Limitations:**
- Complex graphics may be simplified
- Some formatting may be approximated
- OCR text requires pre-processing

**Example:**

.. code-block:: python

   from all2md.pdf2markdown import pdf_to_markdown

   # Convert entire document
   markdown = pdf_to_markdown('report.pdf')

   # Convert specific pages
   markdown = pdf_to_markdown('report.pdf', pages=[0, 1, 2])

Microsoft Word (.docx)
~~~~~~~~~~~~~~~~~~~~~~

**Capabilities:**
- Complete text formatting preservation (bold, italic, underline, strikethrough)
- List detection and conversion (bulleted, numbered, nested)
- Table structure and content preservation
- Hyperlink extraction and conversion
- Image embedding as base64 data URIs
- Style-based formatting detection

**Features:**
- Intelligent list level detection
- Table cell formatting preservation
- Hyperlink URL extraction
- Document structure analysis
- Paragraph-level processing

**Limitations:**
- Complex Word features (comments, track changes) not supported
- Some advanced formatting may be simplified
- Embedded objects converted to basic representations

**Example:**

.. code-block:: python

   from all2md.docx2markdown import docx_to_markdown

   # Basic conversion
   markdown = docx_to_markdown('document.docx')

   # Include images as base64
   markdown = docx_to_markdown('document.docx', convert_images_to_base64=True)

PowerPoint (.pptx)
~~~~~~~~~~~~~~~~~~

**Capabilities:**
- Slide-by-slide content extraction
- Text formatting preservation
- Table extraction with Markdown formatting
- Image embedding as base64
- Bullet point and list conversion
- Slide title and content separation

**Features:**
- Hierarchical content structure preservation
- Chart metadata extraction
- Text box processing
- Multi-level list handling
- Slide numbering and separation

**Limitations:**
- Animations and transitions not supported
- Complex slide layouts may be simplified
- Speaker notes not extracted
- Embedded videos not supported

**Example:**

.. code-block:: python

   from all2md.pptx2markdown import pptx_to_markdown

   markdown = pptx_to_markdown('presentation.pptx')

HTML (.html, .htm)
~~~~~~~~~~~~~~~~~~

**Capabilities:**
- Complete HTML element support
- Configurable conversion options
- Table structure preservation
- Link and image processing
- Nested element handling
- Custom styling options

**Features:**
- Configurable heading styles (hash vs underline)
- Custom emphasis symbols
- Bullet symbol customization
- Image handling modes
- Title extraction from HTML head

**Supported Elements:**
- Text formatting: ``<strong>``, ``<em>``, ``<u>``, ``<strike>``, ``<code>``
- Structure: ``<h1>``-``<h6>``, ``<p>``, ``<br>``, ``<hr>``
- Lists: ``<ul>``, ``<ol>``, ``<li>`` with nesting
- Tables: ``<table>``, ``<thead>``, ``<tbody>``, ``<tr>``, ``<td>``, ``<th>``
- Links: ``<a>`` with href attributes
- Images: ``<img>`` with src and alt attributes
- Code: ``<pre>``, ``<code>`` blocks

**Example:**

.. code-block:: python

   from all2md.html2markdown import HTMLToMarkdown

   converter = HTMLToMarkdown(
       hash_headings=True,
       emphasis_symbol="*",
       bullet_symbols="*-+"
   )
   markdown = converter.convert(html_content)

Email (.eml)
~~~~~~~~~~~~

**Capabilities:**
- Email chain detection and parsing
- Header extraction (From, To, CC, Date, Subject)
- Content type handling (text/plain, text/html)
- Attachment metadata extraction
- Reply chain hierarchy preservation
- Thread reconstruction

**Features:**
- Automatic chain splitting using regex patterns
- Date parsing and UTC normalization
- Encoding detection and conversion
- Quote cleaning and formatting
- Message ID and reference tracking

**Supported Email Features:**
- Multiple recipients (To, CC, BCC)
- Various content encodings
- MIME multipart messages
- Inline content and attachments
- Forwarded message detection

**Example:**

.. code-block:: python

   from all2md.emlfile import parse_email_chain

   # Get structured data
   messages = parse_email_chain('conversation.eml')

   # Get Markdown format
   markdown = parse_email_chain('conversation.eml', as_markdown=True)

Spreadsheet Formats
-------------------

Excel (.xlsx)
~~~~~~~~~~~~~

**Capabilities:**
- Multi-sheet processing
- Table conversion to Markdown
- Data type preservation
- Sheet naming and organization

**Features:**
- Automatic sheet iteration
- Pandas-powered processing
- Missing value handling
- Column header detection

**Example:**

.. code-block:: python

   # Automatically handled by parse_file
   with open('spreadsheet.xlsx', 'rb') as f:
       markdown = parse_file(f, 'spreadsheet.xlsx')

CSV/TSV (.csv, .tsv)
~~~~~~~~~~~~~~~~~~~~

**Capabilities:**
- Delimiter detection
- Header row identification
- Data formatting preservation
- Markdown table generation

**Features:**
- Pandas integration for robust parsing
- Encoding detection
- Quote character handling
- Missing data representation

**Example:**

.. code-block:: python

   # CSV files are converted to Markdown tables
   with open('data.csv', 'rb') as f:
       markdown = parse_file(f, 'data.csv')

Image Formats
-------------

Supported Image Types
~~~~~~~~~~~~~~~~~~~~~

- **PNG** (.png) - Lossless compression, transparency support
- **JPEG** (.jpg, .jpeg) - Lossy compression, smaller file sizes
- **GIF** (.gif) - Animation and transparency support

**Processing:**
Images are embedded as base64 data URIs in Markdown:

.. code-block:: markdown

   ![Image description](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...)

**Example:**

.. code-block:: python

   # Images are automatically embedded
   with open('image.png', 'rb') as f:
       markdown = parse_file(f, 'image.png')

Text Formats
------------

Supported Extensions (200+)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Programming Languages:**
``.py``, ``.js``, ``.java``, ``.c``, ``.cpp``, ``.cs``, ``.go``, ``.rs``, ``.rb``, ``.php``, ``.swift``, ``.kt``, ``.ts``, ``.jsx``, ``.tsx``, ``.vue``, ``.svelte``

**Markup and Data:**
``.md``, ``.html``, ``.xml``, ``.json``, ``.yaml``, ``.toml``, ``.csv``, ``.ini``, ``.cfg``, ``.conf``

**Configuration Files:**
``.dockerfile``, ``.jenkinsfile``, ``.eslintrc``, ``.babelrc``, ``.gitignore``, ``.env``

**Scripts and Tools:**
``.sh``, ``.bat``, ``.ps1``, ``.pl``, ``.awk``, ``.sed``, ``.vim``

**Documentation:**
``.rst``, ``.adoc``, ``.textile``, ``.wiki``, ``.org``, ``.tex``

**Processing:**
Text files are processed as UTF-8 with fallback encoding detection.

Reverse Conversion Formats
---------------------------

Markdown to Word (.docx)
~~~~~~~~~~~~~~~~~~~~~~~~~

**Supported Markdown Elements:**
- Headers (H1-H6) with Word styles
- Text formatting (bold, italic, underline)
- Lists (bulleted, numbered, nested)
- Tables with structure and formatting
- Links (converted to Word hyperlinks)
- Code blocks with monospace formatting
- Horizontal rules

**Features:**
- Automatic Word style creation
- Hyperlink styling with colors
- Table border formatting
- List indentation management
- Font customization support

**Example:**

.. code-block:: python

   from all2md.markdown2docx import markdown_to_docx

   doc = markdown_to_docx(markdown_text)
   doc.save('output.docx')

PDF to Images
~~~~~~~~~~~~~

**Supported Output Formats:**
- **JPEG** - Smaller file sizes, good for photos
- **PNG** - Lossless quality, supports transparency

**Features:**
- Configurable resolution (zoom levels)
- Page range selection
- Password-protected PDF support
- Base64 encoding for web applications
- High-quality anti-aliasing

**Example:**

.. code-block:: python

   from all2md.pdf2image import pdf_to_images

   # High quality PNG conversion
   images = pdf_to_images('document.pdf', fmt='png', zoom=2.0)

   # Web-ready base64 JPEG
   images_b64 = pdf_to_images('document.pdf', fmt='jpeg', as_base64=True)

Format Limitations and Considerations
-------------------------------------

General Limitations
~~~~~~~~~~~~~~~~~~~

**Complex Layouts:**
- Very complex document layouts may be simplified
- Multi-column layouts are linearized
- Advanced graphic elements may be omitted

**Formatting Approximations:**
- Some proprietary formatting may not have Markdown equivalents
- Advanced typography (kerning, tracking) is not preserved
- Custom fonts are not embedded

**Binary Content:**
- Embedded objects are converted to text representations
- Audio/video content is not supported
- Interactive elements become static

Format-Specific Considerations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**PDF Processing:**
- Scanned PDFs require OCR pre-processing
- Password-protected files need credentials
- Very large files may require significant memory

**Word Documents:**
- Requires python-docx package
- Some advanced Word features (macros, form fields) not supported
- Document protection may limit access

**PowerPoint:**
- Slide animations and transitions are lost
- Complex slide masters may not convert perfectly
- Embedded media becomes static references

**Email Processing:**
- Attachments are listed but not embedded
- Complex HTML emails may have formatting issues
- Some email clients create non-standard formats

**HTML Conversion:**
- JavaScript and dynamic content is ignored
- CSS styling is not fully preserved
- Some HTML5 elements may not convert

Best Practices by Format
------------------------

PDF Files
~~~~~~~~~

.. code-block:: python

   # Use page ranges for large documents
   markdown = pdf_to_markdown(doc, pages=list(range(10)))

   # Check for password protection
   try:
       markdown = pdf_to_markdown(doc)
   except Exception as e:
       if "password" in str(e).lower():
           # Handle password-protected PDF
           pass

Word Documents
~~~~~~~~~~~~~~

.. code-block:: python

   # Enable image conversion for complete documents
   markdown = docx_to_markdown(doc, convert_images_to_base64=True)

   # Handle tables and lists properly
   if "table" in markdown.lower() or "|" in markdown:
       # Process tables
       pass

Email Files
~~~~~~~~~~~

.. code-block:: python

   # Use structured format for processing
   messages = parse_email_chain(eml_file, as_markdown=False)

   # Check for thread information
   for msg in messages:
       if msg.get('in_reply_to'):
           # This is part of a thread
           pass

Encoding and Character Support
------------------------------

**Supported Encodings:**
- UTF-8 (primary)
- UTF-16
- Latin-1 (ISO-8859-1)
- Windows-1252 (CP1252)
- ASCII

**Character Handling:**
- Unicode normalization
- Smart quote conversion
- Special character preservation
- Emoji support (when possible)

**Error Handling:**
- Graceful degradation for unsupported characters
- Encoding detection with fallbacks
- Error reporting for problematic content

This comprehensive format support makes all2md suitable for a wide range of document processing tasks, from simple text conversion to complex document workflow automation.