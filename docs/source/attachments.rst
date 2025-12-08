Attachment Handling
===================

all2md provides a unified attachment handling system for managing images, embedded files, and other linked resources across all attachment-capable document formats. This guide explains how the attachment system works, the available modes, and format-specific behaviors.

What Are Attachments?
---------------------

"Attachments" in all2md refers to any binary content embedded in or referenced by a document:

* **Images** - Embedded or linked images (PNG, JPEG, GIF, SVG, etc.)
* **Embedded Files** - Files attached to documents (e.g., PDF attachments, email attachments)
* **Remote Resources** - Externally linked content (e.g., images in HTML documents)
* **Diagrams and Charts** - Visual elements in presentations and documents

Different document formats handle attachments in different ways:

* **PDF** - Images and vector graphics are embedded in the document
* **DOCX/PPTX** - Images and media are stored as relationships within the ZIP archive
* **HTML** - Images can be embedded as data URIs or referenced via URLs
* **EML** - Files can be attached as MIME parts
* **EPUB** - Images and media are packaged within the EPUB container

Attachment Modes
----------------

all2md supports four attachment handling modes that work consistently across all attachment-capable formats:

skip
~~~~

**Skip all attachments completely.**

Attachments are removed from the output. For images, nothing is rendered. For embedded files, they are ignored.

**Use when:**

* You only need text content
* Processing untrusted documents where attachments might be malicious
* Minimizing output size

**Example:**

.. code-block:: python

   from all2md import to_markdown

   # Remove all images and attachments
   markdown = to_markdown('document.pdf', attachment_mode='skip')

**Output:**

.. code-block:: markdown

   # Document Title

   This document has content.

   More text here.

**CLI:**

.. code-block:: bash

   all2md document.pdf --attachment-mode skip

alt_text
~~~~~~~~

**Replace attachments with descriptive text (default).**

For images, uses alt-text if available, otherwise uses the filename or a placeholder. For embedded files, references them by filename.

**Use when:**

* You want to know where images were in the original document
* Processing documents for text analysis while preserving structure
* Creating accessible text-only versions

**Example:**

.. code-block:: python

   markdown = to_markdown('document.pdf', attachment_mode='alt_text')

**Output:**

.. code-block:: markdown

   # Document Title

   ![Company Logo](logo.png)

   This document has content.

   ![Chart showing quarterly results](chart-q4.png)

**CLI:**

.. code-block:: bash

   all2md document.pdf --attachment-mode alt_text

**Fine-grained Control:**

You can control exactly what text is shown for images using the ``alt_text_mode`` option:

.. code-block:: python

   from all2md.options import PdfOptions

   # Default mode: alt text with filename fallback, markdown-safe
   options = PdfOptions(
       attachment_mode='alt_text',
       alt_text_mode='default'
   )

   # Plain filename only (may contain special characters)
   options = PdfOptions(
       attachment_mode='alt_text',
       alt_text_mode='plain_filename'
   )

   # Strict markdown-safe alt text (sanitized)
   options = PdfOptions(
       attachment_mode='alt_text',
       alt_text_mode='strict_markdown'
   )

   # Alt text as footnote reference
   options = PdfOptions(
       attachment_mode='alt_text',
       alt_text_mode='footnote'
   )

**CLI:**

.. code-block:: bash

   all2md document.pdf --attachment-mode alt_text --alt-text-mode plain_filename

download
~~~~~~~~

**Save attachments to a local directory and reference them with relative paths.**

Images and files are extracted and saved to the specified directory. Markdown output uses relative file paths to reference them.

**Use when:**

* You need the actual attachment files preserved
* Creating standalone Markdown documents with local resources
* Archiving documents with all their media

**Example:**

.. code-block:: python

   markdown = to_markdown(
       'document.pdf',
       attachment_mode='download',
       attachment_output_dir='./pdf_images'
   )

**Output:**

.. code-block:: markdown

   # Document Title

   ![Company Logo](pdf_images/logo.png)

   This document has content.

   ![Chart showing quarterly results](pdf_images/chart-q4.png)

**File Structure:**

.. code-block:: text

   ./
   ├── document.md
   └── pdf_images/
       ├── logo.png
       ├── chart-q4.png
       └── diagram-1.png

**CLI:**

.. code-block:: bash

   all2md document.pdf --attachment-mode download --attachment-output-dir ./images

**Advanced Options:**

.. code-block:: python

   from all2md.options import DocxOptions

   options = DocxOptions(
       attachment_mode='download',
       attachment_output_dir='./doc_media',
       # Optionally set base URL for Markdown references
       attachment_base_url='https://example.com/media'
   )
   markdown = to_markdown('document.docx', parser_options=options)

This creates references like:

.. code-block:: markdown

   ![Logo](https://example.com/media/logo.png)

base64
~~~~~~

**Embed attachments directly in Markdown as base64 data URIs.**

Images and other compatible files are encoded as base64 and embedded inline. This creates self-contained Markdown files with no external dependencies.

**Use when:**

* Creating truly portable Markdown (single file, no external resources)
* Sharing documents without worrying about broken image links
* Embedding in systems that don't support external file references

**Example:**

.. code-block:: python

   markdown = to_markdown('presentation.pptx', attachment_mode='base64')

**Output:**

.. code-block:: markdown

   # Slide Title

   ![Logo](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgA...)

   Slide content here.

**Pros:**

* Single self-contained file
* No broken links
* Works offline

**Cons:**

* Much larger file size (base64 encoding increases size by ~33%)
* Harder to read/edit the raw Markdown
* May not render in all Markdown viewers

**CLI:**

.. code-block:: bash

   all2md presentation.pptx --attachment-mode base64

Global vs Format-Specific Flags
--------------------------------

all2md provides both global and format-specific attachment flags for maximum flexibility:

**Global Flags (recommended for most use cases):**

.. code-block:: bash

   # Applies to all formats
   all2md document.pdf --attachment-mode download --attachment-output-dir ./images

Available global flags:

* ``--attachment-mode`` - Attachment handling mode (skip, alt_text, download, base64)
* ``--attachment-output-dir`` - Directory to save attachments
* ``--attachment-base-url`` - Base URL for attachment references
* ``--alt-text-mode`` - How to render alt-text (default, plain_filename, strict_markdown, footnote)
* ``--max-asset-size-bytes`` - Maximum size for individual assets
* ``--attachment-filename-template`` - Template for attachment filenames
* ``--attachment-overwrite`` - File collision strategy (unique, overwrite, skip)
* ``--attachment-deduplicate-by-hash`` - Deduplicate attachments by content hash
* ``--attachments-footnotes-section`` - Section title for footnote-style references

**Format-Specific Overrides (for advanced batch processing):**

When processing multiple formats, you can use format-specific flags to override global settings:

.. code-block:: bash

   # Skip attachments by default, but download from PDFs
   all2md *.* --attachment-mode skip --pdf-attachment-mode download --pdf-attachment-output-dir ./pdf_images

   # Use alt-text globally, but embed base64 for presentations
   all2md docs/* reports/*.pdf slides/*.pptx \
       --attachment-mode alt_text \
       --pptx-attachment-mode base64

   # Different output directories per format
   all2md mixed_docs/* \
       --attachment-mode download \
       --pdf-attachment-output-dir ./pdf_assets \
       --docx-attachment-output-dir ./word_assets \
       --html-attachment-output-dir ./web_assets

**Override Precedence:**

Format-specific flags always take precedence over global flags:

.. code-block:: bash

   # PDFs use 'download', all others use 'skip'
   all2md *.* --attachment-mode skip --pdf-attachment-mode download

This is particularly useful for:

* **Mixed format directories** - Different attachment strategies per format
* **Selective processing** - Skip attachments for most formats, enable for specific ones
* **Performance optimization** - Use faster modes for some formats, thorough modes for others
* **Security policies** - Apply strict rules globally with exceptions for trusted formats

**Format Prefixes:**

Each format has its own prefix for format-specific flags:

* PDF: ``--pdf-attachment-mode``, ``--pdf-attachment-output-dir``, etc.
* Word: ``--docx-attachment-mode``, ``--docx-attachment-output-dir``, etc.
* PowerPoint: ``--pptx-attachment-mode``, ``--pptx-attachment-output-dir``, etc.
* HTML: ``--html-attachment-mode``, ``--html-attachment-output-dir``, etc.
* Email: ``--eml-attachment-mode``, ``--eml-attachment-output-dir``, etc.
* EPUB: ``--epub-attachment-mode``, ``--epub-attachment-output-dir``, etc.
* Jupyter: ``--ipynb-attachment-mode``, ``--ipynb-attachment-output-dir``, etc.
* OpenDocument: ``--odt-attachment-mode``, ``--odp-attachment-mode``, etc.
* Excel: ``--xlsx-attachment-mode``, ``--xlsx-attachment-output-dir``, etc.
* And more... (see ``all2md help <format>`` for complete list)

Format-Specific Behavior
-------------------------

While all formats support the four attachment modes, each format has specific considerations:

PDF Documents
~~~~~~~~~~~~~

**Attachment Types:**

* Embedded images (JPEG, PNG, etc.)
* Vector graphics (converted to raster if needed)
* Embedded files (if PDF contains file attachments)

**Example:**

.. code-block:: python

   from all2md.options import PdfOptions

   options = PdfOptions(
       attachment_mode='download',
       attachment_output_dir='./pdf_images',
       image_format='jpeg',
       image_quality=85,
       skip_image_extraction=False
   )
   markdown = to_markdown('report.pdf', parser_options=options)

**Note:** PDF vector graphics are rasterized during extraction. Image quality depends on the PDF's embedded resolution.

Word Documents (DOCX)
~~~~~~~~~~~~~~~~~~~~~

**Attachment Types:**

* Inline images
* Floating images
* Shapes with image fills
* Charts (rendered as images)

**Example:**

.. code-block:: python

   from all2md.options import DocxOptions

   options = DocxOptions(
       attachment_mode='download',
       attachment_output_dir='./word_images'
   )
   markdown = to_markdown('document.docx', parser_options=options)

**Note:** DOCX images maintain their original format (PNG, JPEG, etc.) and quality.

PowerPoint (PPTX)
~~~~~~~~~~~~~~~~~

**Attachment Types:**

* Slide images
* Shape fills
* Charts and diagrams
* SmartArt graphics (rendered as images)

**Example:**

.. code-block:: python

   from all2md.options import PptxOptions

   options = PptxOptions(
       attachment_mode='base64',  # Embed all slide images
       include_slide_numbers=True
   )
   markdown = to_markdown('presentation.pptx', parser_options=options)

**Note:** Each visual element on a slide may be extracted as a separate image.

HTML and MHTML
~~~~~~~~~~~~~~

**Attachment Types:**

* Inline images (``<img>`` tags)
* Background images (CSS)
* Data URI embedded images
* Remote images (HTTP/HTTPS URLs)

**Example:**

.. code-block:: python

   from all2md.options import HtmlOptions, NetworkFetchOptions

   options = HtmlOptions(
       attachment_mode='download',
       attachment_output_dir='./web_images',
       attachment_base_url='https://example.com',  # Resolve relative URLs
       network=NetworkFetchOptions(
           allow_remote_fetch=True,  # Allow downloading remote images
           require_https=True        # Only HTTPS images
       )
   )
   markdown = to_markdown('webpage.html', parser_options=options)

**Security Note:** Be cautious with ``allow_remote_fetch`` on untrusted HTML. See :doc:`security` for details.

**MHTML Note:** MHTML files bundle resources, so remote fetching is typically not needed.

Email Files (EML)
~~~~~~~~~~~~~~~~~

**Attachment Types:**

* Email attachments (any file type)
* Inline images (Content-ID references)
* HTML email embedded images

**Example:**

.. code-block:: python

   from all2md.options import EmlOptions

   options = EmlOptions(
       attachment_mode='download',
       attachment_output_dir='./email_attachments',
       # EML-specific: limit attachment size
       max_email_attachment_bytes=10 * 1024 * 1024  # 10 MB max
   )
   markdown = to_markdown('message.eml', parser_options=options)

**Note:** Email attachments include both files explicitly attached and images embedded in HTML emails.

EPUB E-books
~~~~~~~~~~~~

**Attachment Types:**

* Chapter images
* Cover images
* Embedded media files

**Example:**

.. code-block:: python

   from all2md.options import EpubOptions

   options = EpubOptions(
       attachment_mode='download',
       attachment_output_dir='./epub_images',
       include_toc=True
   )
   markdown = to_markdown('book.epub', parser_options=options)

**Note:** EPUB images are already packaged within the EPUB file and maintain their original format.

OpenDocument (ODT/ODP)
~~~~~~~~~~~~~~~~~~~~~~

**Attachment Types:**

* Document images (ODT)
* Presentation images (ODP)
* Embedded objects

**Example:**

.. code-block:: python

   from all2md.options import OdtOptions

   options = OdtOptions(
       attachment_mode='download',
       attachment_output_dir='./odt_images'
   )
   markdown = to_markdown('document.odt', parser_options=options)

Excel and Spreadsheets (XLSX/ODS)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Attachment Types:**

* Embedded charts (rendered as images)
* Cell images
* Drawing objects

**Example:**

.. code-block:: python

   from all2md.options import XlsxOptions

   options = XlsxOptions(
       attachment_mode='base64',  # Embed images inline
       chart_mode='data'          # Extract chart data as tables
   )
   markdown = to_markdown('spreadsheet.xlsx', parser_options=options)

**Note:** Charts are rendered as static images during conversion.

Jupyter Notebooks (IPYNB)
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Attachment Types:**

* Matplotlib plots
* Output images from cells
* Embedded images in Markdown cells

**Example:**

.. code-block:: python

   from all2md.options import IpynbOptions

   options = IpynbOptions(
       attachment_mode='base64',  # Embed all plots
       include_outputs=True
   )
   markdown = to_markdown('notebook.ipynb', parser_options=options)

Filename Sanitization
---------------------

When using ``download`` mode, all2md automatically sanitizes filenames to ensure cross-platform compatibility:

* Removes or replaces unsafe characters (e.g., ``/``, ``\\``, ``:``)
* Limits filename length to 255 characters
* Normalizes Unicode characters
* Prevents path traversal attacks (e.g., ``../../../etc/passwd``)

**Example transformations:**

.. code-block:: text

   Original:              Sanitized:
   ----------------       ----------------
   "My Image.png"      →  "My_Image.png"
   "file/name.jpg"     →  "file_name.jpg"
   "../../bad.png"     →  "bad.png"
   "file (1).jpg"      →  "file_1.jpg"

Security Considerations
-----------------------

Attachment handling has important security implications, especially when processing untrusted documents:

Safe Modes
~~~~~~~~~~

For untrusted documents, use ``skip`` or ``alt_text`` modes:

.. code-block:: python

   # Maximum security: no attachments processed
   markdown = to_markdown('untrusted.pdf', attachment_mode='skip')

   # Safe alternative: reference attachments but don't extract
   markdown = to_markdown('untrusted.html', attachment_mode='alt_text')

Download Mode Risks
~~~~~~~~~~~~~~~~~~~

``download`` mode writes files to disk, which poses risks:

* **Path Traversal** - Malicious filenames could attempt directory traversal (mitigated by sanitization)
* **Disk Space** - Large or numerous attachments could fill disk space
* **Malicious Content** - Downloaded files could contain malware

**Best Practices:**

.. code-block:: python

   from all2md.options import PdfOptions

   options = PdfOptions(
       attachment_mode='download',
       attachment_output_dir='./safe_sandbox',  # Isolated directory
       # Consider setting size limits if your format supports it
   )

Base64 Mode Memory Usage
~~~~~~~~~~~~~~~~~~~~~~~~~

``base64`` mode loads attachments into memory and embeds them in output:

* Large images significantly increase memory usage
* Output Markdown files become very large
* May cause issues with Markdown renderers

**Best Practices:**

.. code-block:: python

   # For documents with many/large images, prefer download mode
   options = PdfOptions(
       attachment_mode='download',  # Better for large documents
       attachment_output_dir='./images'
   )

Remote Fetch Security (HTML)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

HTML documents can reference remote resources. This poses security risks:

.. code-block:: python

   from all2md.options import HtmlOptions, NetworkFetchOptions

   # Strict security (default)
   options = HtmlOptions(
       attachment_mode='skip',  # Don't fetch any remote content
       network=NetworkFetchOptions(
           allow_remote_fetch=False
       )
   )

   # Balanced security
   options = HtmlOptions(
       attachment_mode='download',
       attachment_output_dir='./images',
       network=NetworkFetchOptions(
           allow_remote_fetch=True,
           require_https=True,              # HTTPS only
           allowed_hosts=['example.com'],   # Whitelist specific domains
           max_remote_asset_bytes=5 * 1024 * 1024  # 5 MB limit
       )
   )

See :doc:`security` for comprehensive security guidance.

Configuration Examples
----------------------

Quick Reference
~~~~~~~~~~~~~~~

**Text-only extraction:**

.. code-block:: bash

   all2md document.pdf --attachment-mode skip

**Preserve structure with references:**

.. code-block:: bash

   all2md document.docx --attachment-mode alt_text

**Extract with local files:**

.. code-block:: bash

   all2md document.pdf --attachment-mode download --attachment-output-dir ./images

**Self-contained Markdown:**

.. code-block:: bash

   all2md presentation.pptx --attachment-mode base64

Python API Examples
~~~~~~~~~~~~~~~~~~~

**Multi-document processing with consistent attachment handling:**

.. code-block:: python

   from all2md import to_markdown
   from pathlib import Path

   # Process all PDFs in directory
   output_dir = Path('./extracted_images')
   output_dir.mkdir(exist_ok=True)

   for pdf_file in Path('./pdfs').glob('*.pdf'):
       markdown = to_markdown(
           pdf_file,
           attachment_mode='download',
           attachment_output_dir=output_dir / pdf_file.stem
       )

       output_file = Path('./markdown') / f'{pdf_file.stem}.md'
       output_file.write_text(markdown)

**Conditional attachment handling:**

.. code-block:: python

   from all2md import to_markdown
   import os

   # Use base64 for small documents, download for large ones
   file_size = os.path.getsize('document.pdf')

   if file_size < 1_000_000:  # < 1 MB
       mode = 'base64'
       output_dir = None
   else:
       mode = 'download'
       output_dir = './images'

   markdown = to_markdown(
       'document.pdf',
       attachment_mode=mode,
       attachment_output_dir=output_dir
   )

**Per-format attachment strategies:**

.. code-block:: python

   from all2md import to_markdown
   from pathlib import Path

   def convert_with_smart_attachments(file_path):
       path = Path(file_path)
       suffix = path.suffix.lower()

       # Strategy based on format
       if suffix == '.pdf':
           # PDFs: download high-quality images
           return to_markdown(
               file_path,
               attachment_mode='download',
               attachment_output_dir=f'./{path.stem}_images'
           )
       elif suffix == '.pptx':
           # Presentations: embed for portability
           return to_markdown(file_path, attachment_mode='base64')
       elif suffix == '.html':
           # HTML: use alt-text to avoid security issues
           return to_markdown(file_path, attachment_mode='alt_text')
       else:
           # Default: alt-text mode
           return to_markdown(file_path, attachment_mode='alt_text')

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

Set default attachment behavior via environment variables:

.. code-block:: bash

   # Set default mode
   export ALL2MD_ATTACHMENT_MODE="save"
   export ALL2MD_ATTACHMENT_OUTPUT_DIR="./attachments"
   export ALL2MD_ATTACHMENT_BASE_URL="https://cdn.example.com"

   # Now all conversions use these defaults
   all2md document.pdf
   all2md document.docx

See Also
--------

* :doc:`formats` - Format-specific options and examples
* :doc:`options` - Complete options reference
* :doc:`security` - Security considerations for untrusted documents
* :doc:`cli` - Command-line attachment options
* :doc:`recipes` - Cookbook examples for common tasks
