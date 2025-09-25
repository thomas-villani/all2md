Command Line Interface
======================

all2md provides a comprehensive command-line interface for converting documents to Markdown. This reference covers all available options and provides practical examples.

.. contents::
   :local:
   :depth: 2

Basic Usage
-----------

Simple Conversion
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Convert any document (output to stdout)
   all2md document.pdf

   # Save output to file
   all2md document.pdf --out output.md
   all2md document.docx -o report.md

   # Process multiple files
   for file in *.pdf; do
       all2md "$file" --out "${file%.pdf}.md"
   done

Reading from Standard Input
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Read from stdin
   all2md -

   # Pipe content through all2md
   cat document.pdf | all2md -
   curl -s https://example.com/doc.pdf | all2md - --out output.md

   # With explicit format specification
   cat unknown_file | all2md - --format pdf

Version and Help
~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Show version
   all2md --version

   # Show help
   all2md --help
   all2md -h

   # Show detailed about information
   all2md --about

Global Options
--------------

Output Control
~~~~~~~~~~~~~~

``--out``, ``-o``
   Output file path. If not specified, output goes to stdout.

   .. code-block:: bash

      # Save to file
      all2md document.pdf --out converted.md
      all2md document.pdf -o converted.md

``--format``
   Force specific file format instead of auto-detection.

   **Choices:** ``auto``, ``pdf``, ``docx``, ``pptx``, ``html``, ``mhtml``, ``eml``, ``epub``, ``rtf``, ``ipynb``, ``odt``, ``odp``, ``csv``, ``tsv``, ``xlsx``, ``image``, ``txt``

   **Default:** ``auto``

   .. code-block:: bash

      # Force PDF processing for file without extension
      all2md mysterious_file --format pdf

      # Process as plain text
      all2md document.pdf --format txt

Attachment Handling
~~~~~~~~~~~~~~~~~~~

``--attachment-mode``
   How to handle images and attachments in documents.

   **Choices:**

   * ``skip`` - Ignore all attachments
   * ``alt_text`` - Replace with alt text or filename (default)
   * ``download`` - Download attachments to local directory
   * ``base64`` - Embed attachments as base64 data URLs

   **Default:** ``alt_text``

   .. code-block:: bash

      # Download images to directory
      all2md document.pdf --attachment-mode download --attachment-output-dir ./images

      # Embed images as base64
      all2md presentation.pptx --attachment-mode base64

      # Skip all images
      all2md document.html --attachment-mode skip

``--attachment-output-dir``
   Directory to save attachments when using ``download`` mode.

   .. code-block:: bash

      # Create images directory and save attachments
      all2md document.docx --attachment-mode download --attachment-output-dir ./doc_images

``--attachment-base-url``
   Base URL for resolving relative attachment references.

   .. code-block:: bash

      # Resolve relative URLs in HTML documents
      all2md webpage.html --attachment-mode download --attachment-base-url https://example.com

Markdown Formatting
~~~~~~~~~~~~~~~~~~~

``--markdown-emphasis-symbol``
   Symbol to use for emphasis and italic text.

   **Choices:** ``*`` (default), ``_``

   .. code-block:: bash

      # Use underscores for emphasis
      all2md document.pdf --markdown-emphasis-symbol "_"

``--markdown-bullet-symbols``
   Characters to cycle through for nested bullet lists.

   **Default:** ``*-+``

   .. code-block:: bash

      # Custom bullet symbols
      all2md document.docx --markdown-bullet-symbols "•◦▪"

``--markdown-page-separator``
   Text used to separate pages in multi-page documents.

   **Default:** ``-----``

   .. code-block:: bash

      # Custom page separator
      all2md document.pdf --markdown-page-separator "=== PAGE BREAK ==="

Configuration and Debugging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``--options-json``
   Path to JSON file containing conversion options. Command line options override JSON settings.

   .. code-block:: bash

      # Use options from JSON file
      all2md document.pdf --options-json config.json

      # JSON file overrides with CLI options
      all2md document.pdf --options-json config.json --attachment-mode download

   Example JSON configuration:

   .. code-block:: json

      {
        "attachment_mode": "download",
        "attachment_output_dir": "./images",
        "pdf_detect_columns": true,
        "pdf_pages": [0, 1, 2],
        "markdown_emphasis_symbol": "_"
      }

``--log-level``
   Set logging level for debugging and detailed output.

   **Choices:** ``DEBUG``, ``INFO``, ``WARNING`` (default), ``ERROR``

   .. code-block:: bash

      # Enable debug logging
      all2md document.pdf --log-level DEBUG

      # Quiet mode (errors only)
      all2md document.pdf --log-level ERROR

Format-Specific Options
-----------------------

PDF Options
~~~~~~~~~~~

``--pdf-pages``
   Specific pages to convert using comma-separated, 0-based indexing.

   .. code-block:: bash

      # Convert first 3 pages
      all2md document.pdf --pdf-pages "0,1,2"

      # Convert pages 1, 5, and 10 (0-based)
      all2md document.pdf --pdf-pages "0,4,9"

      # Single page
      all2md document.pdf --pdf-pages "0"

``--pdf-password``
   Password for encrypted PDF documents.

   .. code-block:: bash

      # Provide password for encrypted PDF
      all2md encrypted.pdf --pdf-password "secret123"

``--pdf-detect-columns``, ``--pdf-no-detect-columns``
   Enable or disable multi-column layout detection.

   **Default:** Enabled

   .. code-block:: bash

      # Enable column detection (default)
      all2md document.pdf --pdf-detect-columns

      # Disable column detection
      all2md document.pdf --pdf-no-detect-columns

HTML Options
~~~~~~~~~~~~

``--html-extract-title``
   Extract and use HTML ``<title>`` element as main heading.

   .. code-block:: bash

      # Use page title as main heading
      all2md webpage.html --html-extract-title

``--html-strip-dangerous-elements``
   Remove potentially dangerous HTML elements (script, style, etc.).

   .. code-block:: bash

      # Clean up HTML by removing scripts and styles
      all2md webpage.html --html-strip-dangerous-elements

PowerPoint Options
~~~~~~~~~~~~~~~~~~

``--pptx-slide-numbers``
   Include slide numbers in output.

   .. code-block:: bash

      # Add slide numbers
      all2md presentation.pptx --pptx-slide-numbers

``--pptx-no-include-notes``
   Exclude speaker notes from conversion.

   **Default:** Notes are included

   .. code-block:: bash

      # Skip speaker notes
      all2md presentation.pptx --pptx-no-include-notes

Email Options
~~~~~~~~~~~~~

``--eml-no-include-headers``
   Exclude email headers from output.

   **Default:** Headers are included

   .. code-block:: bash

      # Skip email headers
      all2md message.eml --eml-no-include-headers

``--eml-no-preserve-thread-structure``
   Don't maintain email thread/reply chain structure.

   **Default:** Thread structure is preserved

   .. code-block:: bash

      # Flatten email thread structure
      all2md thread.eml --eml-no-preserve-thread-structure

OpenDocument Options
~~~~~~~~~~~~~~~~~~~~

``--odf-no-preserve-tables``
   Don't preserve table formatting in Markdown.

   **Default:** Tables are preserved

   .. code-block:: bash

      # Convert tables to plain text
      all2md document.odt --odf-no-preserve-tables

Jupyter Notebook Options
~~~~~~~~~~~~~~~~~~~~~~~~

``--ipynb-truncate-long-outputs``
   Truncate cell outputs longer than specified number of lines.

   .. code-block:: bash

      # Limit output to 20 lines
      all2md notebook.ipynb --ipynb-truncate-long-outputs 20

      # No truncation (default)
      all2md notebook.ipynb

``--ipynb-truncate-output-message``
   Message to display when truncating long outputs.

   **Default:** ``\n... (output truncated) ...\n``

   .. code-block:: bash

      # Custom truncation message
      all2md notebook.ipynb --ipynb-truncate-long-outputs 10 --ipynb-truncate-output-message "*** OUTPUT CUT ***"

EPUB Options
~~~~~~~~~~~~

``--epub-no-merge-chapters``
   Don't merge chapters into continuous document (add separators between chapters).

   **Default:** Chapters are merged

   .. code-block:: bash

      # Keep chapters separate
      all2md book.epub --epub-no-merge-chapters

``--epub-no-include-toc``
   Don't include a Table of Contents in the output.

   **Default:** TOC is included

   .. code-block:: bash

      # Skip table of contents
      all2md book.epub --epub-no-include-toc

Practical Examples
------------------

Basic Document Conversion
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Convert common document types
   all2md report.pdf --out report.md
   all2md presentation.pptx --out slides.md
   all2md spreadsheet.xlsx --out data.md
   all2md notebook.ipynb --out analysis.md

Working with Images
~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Download images from PDF to local directory
   all2md manual.pdf --attachment-mode download --attachment-output-dir ./pdf_images

   # Embed PowerPoint images as base64
   all2md presentation.pptx --attachment-mode base64

   # Process HTML with external images
   all2md webpage.html --attachment-mode download --attachment-base-url https://example.com

Advanced PDF Processing
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Process specific pages with custom formatting
   all2md large_document.pdf --pdf-pages "0,1,2,5,10" --markdown-emphasis-symbol "_"

   # Handle encrypted PDF
   all2md encrypted.pdf --pdf-password "secret" --attachment-mode download

   # Disable column detection for simple layout
   all2md simple.pdf --pdf-no-detect-columns

Email Processing
~~~~~~~~~~~~~~~

.. code-block:: bash

   # Process email with attachments
   all2md message.eml --attachment-mode download --attachment-output-dir ./email_files

   # Clean email conversion (no headers, flat structure)
   all2md thread.eml --eml-no-include-headers --eml-no-preserve-thread-structure

Batch Processing
~~~~~~~~~~~~~~~

.. code-block:: bash

   # Process all PDFs in directory
   for pdf in *.pdf; do
       echo "Converting $pdf..."
       all2md "$pdf" --out "${pdf%.pdf}.md" --attachment-mode download --attachment-output-dir "./images/${pdf%.pdf}"
   done

   # Process with consistent options
   find ./documents -name "*.docx" -exec all2md {} --out {}.md --markdown-emphasis-symbol "_" \;

Web Content Processing
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Download and convert web page
   curl -s "https://example.com/page.html" | all2md - --html-extract-title --html-strip-dangerous-elements

   # Process saved web page with images
   all2md saved_page.html --attachment-mode download --attachment-base-url "https://example.com"

Configuration File Usage
~~~~~~~~~~~~~~~~~~~~~~~~

Create a configuration file ``config.json``:

.. code-block:: json

   {
       "attachment_mode": "download",
       "attachment_output_dir": "./attachments",
       "markdown_emphasis_symbol": "_",
       "markdown_bullet_symbols": "•◦▪",
       "pdf_detect_columns": true,
       "html_strip_dangerous_elements": true,
       "log_level": "INFO"
   }

Use the configuration:

.. code-block:: bash

   # Use config file
   all2md document.pdf --options-json config.json

   # Override specific options
   all2md document.pdf --options-json config.json --attachment-mode base64

Debugging and Troubleshooting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Enable debug output
   all2md problematic.pdf --log-level DEBUG

   # Test format detection
   all2md unknown_file --log-level DEBUG --format auto

   # Force specific format if detection fails
   all2md mystery_file --format pdf --log-level INFO

Error Handling
--------------

Common Exit Codes
~~~~~~~~~~~~~~~~~

* ``0`` - Success
* ``1`` - General error (conversion failed)
* ``2`` - Missing dependency error
* ``3`` - Input/output error (file not found, permission denied)

Error Examples
~~~~~~~~~~~~~

.. code-block:: bash

   # Missing dependency
   $ all2md document.pdf
   Error: PyMuPDF is required for PDF processing. Install with: pip install all2md[pdf]

   # File not found
   $ all2md nonexistent.pdf
   Error: File not found: nonexistent.pdf

   # Invalid option
   $ all2md document.pdf --invalid-option
   Error: unrecognized arguments: --invalid-option

Shell Integration
-----------------

Bash Completion
~~~~~~~~~~~~~~

Add to your ``.bashrc`` or ``.bash_profile``:

.. code-block:: bash

   # Basic completion for file extensions
   complete -f -X '!*.@(pdf|docx|pptx|html|eml|epub|ipynb|odt|odp|xlsx|csv|tsv)' all2md

Aliases and Functions
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Useful aliases
   alias pdf2md='all2md --format pdf --attachment-mode download'
   alias docx2md='all2md --format docx --markdown-emphasis-symbol "_"'
   alias html2md='all2md --format html --html-strip-dangerous-elements'

   # Function for batch processing
   all2md_batch() {
       local dir="${1:-.}"
       local pattern="${2:-*}"
       find "$dir" -name "$pattern" -type f | while read -r file; do
           echo "Converting: $file"
           all2md "$file" --out "${file%.*}.md"
       done
   }

Environment Variables
~~~~~~~~~~~~~~~~~~~~

Set default options using environment variables:

.. code-block:: bash

   # Set default attachment mode
   export ALL2MD_ATTACHMENT_MODE="download"
   export ALL2MD_ATTACHMENT_OUTPUT_DIR="./attachments"

   # Set default markdown formatting
   export ALL2MD_EMPHASIS_SYMBOL="_"
   export ALL2MD_BULLET_SYMBOLS="•◦▪"

   # Use in script
   all2md document.pdf  # Uses environment defaults

For complete option details and programmatic usage, see the :doc:`options` reference and Python API documentation.