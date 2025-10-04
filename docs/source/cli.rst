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

Discovery Commands
------------------

List Available Formats
~~~~~~~~~~~~~~~~~~~~~~

Use ``all2md list-formats`` to see all supported file formats and their details.

.. code-block:: bash

   # List all formats
   all2md list-formats

   # Show only formats with all dependencies installed
   all2md list-formats --available-only

   # Display with rich formatting (tables and colors)
   all2md list-formats --rich

Example output:

.. code-block:: text

   Available Formats:

   Format: pdf
     Extensions: .pdf
     MIME Types: application/pdf
     Status: Available
     Dependencies: PyMuPDF (fitz)

   Format: docx
     Extensions: .docx
     MIME Types: application/vnd.openxmlformats-officedocument.wordprocessingml.document
     Status: Available
     Dependencies: python-docx

List Available Transforms
~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``all2md list-transforms`` to see all available AST transforms. For detailed transform documentation, see :doc:`transforms`.

.. code-block:: bash

   # List all transforms
   all2md list-transforms

   # Show only installed transforms
   all2md list-transforms --available-only

   # Display with rich formatting
   all2md list-transforms --rich

Example output:

.. code-block:: text

   Available Transforms:

   Transform: RemoveImagesTransform
     Module: all2md.transforms.builtin
     Description: Remove all image nodes from the AST
     Status: Available

   Transform: HeadingOffsetTransform
     Module: all2md.transforms.builtin
     Description: Adjust heading levels by a specified offset
     Status: Available
     Options: offset (int)

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

   **Choices:** ``auto``, ``pdf``, ``docx``, ``pptx``, ``html``, ``mhtml``, ``eml``, ``epub``, ``rtf``, ``ipynb``, ``odf``, ``spreadsheet``, ``image``, ``txt``

   **Default:** ``auto``

   .. note::

      * ``odf`` handles both OpenDocument Text (.odt) and Presentation (.odp) files
      * ``spreadsheet`` handles Excel (.xlsx), CSV (.csv), and TSV (.tsv) files

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

``--markdown-page-separator-template``
   Template text used to separate pages in multi-page documents. Use ``{page_num}`` to include the page number.

   **Default:** ``-----``

   .. code-block:: bash

      # Custom page separator template
      all2md document.pdf --markdown-page-separator-template "=== PAGE BREAK ==="

      # Include page numbers in separator
      all2md document.pdf --markdown-page-separator-template "--- Page {page_num} ---"

Configuration and Debugging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``--options-json``
   Path to JSON file containing conversion options. Command line options override JSON settings.

   .. note::

      **Passing List Values:** The current CLI implementation does not parse comma-separated strings into lists for ``list[str]`` fields. For options that accept multiple values (lists), you must use JSON configuration:

      **List-type options requiring JSON:**

      * ``html.network.allowed_hosts`` - Whitelist of allowed hostnames
      * ``eml.url_wrappers`` - Custom URL wrapper patterns to clean
      * ``spreadsheet.sheets`` - Specific sheets to process (or use regex pattern as single string)
      * ``pdf.pages`` - Can use comma-separated string: ``"0,1,2"`` (parsed as integers)

      **Example JSON configuration:**

      .. code-block:: json

         {
           "html.network.allowed_hosts": ["cdn.example.com", "images.example.org"],
           "eml.url_wrappers": ["safelinks.protection.outlook.com", "urldefense.com"],
           "spreadsheet.sheets": ["Sheet1", "Summary", "Data"]
         }

      **Usage:**

      .. code-block:: bash

         # Use JSON for list values
         all2md webpage.html --options-json config.json --html-network-allow-remote-fetch

         # CLI flags can still override non-list settings
         all2md webpage.html --options-json config.json --attachment-mode download

      **Single-value workaround:**

      For single values, you can pass them directly:

      .. code-block:: bash

         # Single host (works without JSON)
         all2md webpage.html --html-network-allowed-hosts "cdn.example.com"

         # Single sheet as regex pattern
         all2md workbook.xlsx --spreadsheet-sheets "^Sheet1$"

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
        "pdf.detect_columns": true,
        "pdf.pages": [1, 2, 3],
        "markdown.emphasis_symbol": "_"
      }

``--log-level``
   Set logging level for debugging and detailed output.

   **Choices:** ``DEBUG``, ``INFO``, ``WARNING`` (default), ``ERROR``

   .. code-block:: bash

      # Enable debug logging
      all2md document.pdf --log-level DEBUG

      # Quiet mode (errors only)
      all2md document.pdf --log-level ERROR

Processing and Output Control
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``--rich``
   Enable rich terminal output with enhanced formatting and colors.

   .. code-block:: bash

      # Enhanced terminal output
      all2md document.pdf --rich

``--pager``
   Display output using system pager for long documents (stdout only). Uses the system's default pager (``less`` on Unix, ``more`` on Windows) or the pager specified in ``PAGER`` or ``MANPAGER`` environment variables.

   .. note::

      * Only applies to stdout output (not when using ``--out`` or ``--output-dir``)
      * Requires the ``rich`` library (install with ``pip install all2md[rich]``)
      * On Linux/macOS, set ``PAGER=less -r`` to enable ANSI color support in the pager

   .. code-block:: bash

      # View long document with pager
      all2md long_document.pdf --pager

      # Combine with other options
      all2md report.pdf --pager --pdf-pages "1,2,3,4,5"

      # Enable color support in pager (bash/zsh)
      export PAGER="less -r"
      all2md document.pdf --pager

``--progress``
   Show progress bar for file conversions (automatically enabled for multiple files).

   .. code-block:: bash

      # Force progress bar for single file
      all2md document.pdf --progress

``--output-dir``
   Directory to save converted files (for multi-file processing).

   .. code-block:: bash

      # Convert multiple files to directory
      all2md *.pdf --output-dir ./markdown_output

``--recursive``, ``-r``
   Process directories recursively.

   .. code-block:: bash

      # Recursively convert all files in a directory tree
      all2md ./documents --recursive --output-dir ./converted

``--parallel``, ``-p``
   Process files in parallel (optionally specify number of workers).

   .. code-block:: bash

      # Process files in parallel (auto-detect CPU cores)
      all2md *.pdf --parallel

      # Use specific number of workers
      all2md *.pdf --parallel 4

   .. note::

      **Performance Considerations:**

      Parallel processing provides significant speedups for certain formats:

      * **CPU-bound formats** (best for parallel processing):

        - **PDF:** Excellent parallelization - parsing is CPU-intensive (text extraction, table detection, image decoding)
        - **DOCX/PPTX:** Good parallelization - XML parsing and formatting logic benefits from multiple cores
        - **Images (OCR):** Excellent parallelization - OCR operations are very CPU-intensive

      * **I/O-bound formats** (less benefit from parallel processing):

        - **HTML/Markdown:** Minimal benefit - parsing is fast, most time spent on I/O
        - **Plain text:** No benefit - trivial processing time

      **Memory Considerations:**

      * Each worker process imports dependencies independently (startup overhead per worker)
      * Large PDFs with many images can use significant memory per worker
      * **Recommendation:** For large PDFs, use ``--pdf-skip-image-extraction`` with parallel mode if you only need text
      * Monitor memory usage when processing large files in parallel (e.g., ``htop`` on Linux)

      **Optimal Worker Count:**

      * **Auto-detect** (``--parallel`` without number): Uses CPU core count - good default for most cases
      * **CPU-bound workloads:** Use core count or ``core count - 1`` to leave headroom for OS
      * **Mixed I/O/CPU:** Start with 2-4 workers, increase if CPU utilization is low
      * **Large PDFs with images:** Reduce workers (e.g., 2-4) to avoid memory pressure
      * **Network-heavy workloads:** Can use more workers than CPU cores (e.g., ``core count * 2``)

      **Example Configurations:**

      .. code-block:: bash

         # Large PDFs, text-only, maximize throughput
         all2md *.pdf --parallel --pdf-skip-image-extraction --output-dir ./out

         # Medium PDFs with images, conservative memory usage
         all2md *.pdf --parallel 4 --output-dir ./out

         # Many small files, I/O bound
         all2md *.html --parallel 2 --output-dir ./out

``--skip-errors``
   Continue processing remaining files if one fails.

   .. code-block:: bash

      # Don't stop on errors
      all2md *.pdf --skip-errors --output-dir ./converted

``--preserve-structure``
   Preserve directory structure in output directory.

   .. code-block:: bash

      # Maintain folder hierarchy
      all2md ./docs --recursive --preserve-structure --output-dir ./markdown

``--collate``
   Combine multiple files into a single output (stdout or file).

   .. code-block:: bash

      # Combine all chapters into one file
      all2md chapter_*.pdf --collate --out book.md

      # Collate to stdout
      all2md *.md --collate

``--no-summary``
   Disable summary output after processing multiple files.

   .. code-block:: bash

      # Quiet multi-file processing
      all2md *.pdf --output-dir ./converted --no-summary

``--save-config``
   Save current CLI arguments to a JSON configuration file.

   .. code-block:: bash

      # Save current settings
      all2md document.pdf --attachment-mode download --save-config my-config.json

``--dry-run``
   Show what would be converted without actually processing files.

   .. code-block:: bash

      # Preview what would be processed
      all2md ./documents --recursive --dry-run

``--exclude``
   Exclude files matching this glob pattern (can be specified multiple times).

   .. code-block:: bash

      # Exclude temporary and backup files
      all2md ./docs --recursive --exclude "*.tmp" --exclude "*.bak"

      # Exclude multiple patterns
      all2md ./source --recursive --exclude "__pycache__" --exclude "*.pyc"

Format-Specific Options
-----------------------

PDF Options
~~~~~~~~~~~

``--pdf-pages``
   Specific pages to convert (1-based indexing). Supports lists and ranges: "1,2,3", "1-3,5", "10-".

   .. code-block:: bash

      # Convert first 3 pages
      all2md document.pdf --pdf-pages "1,2,3"

      # Convert pages 1, 5, and 10
      all2md document.pdf --pdf-pages "1,5,10"

      # Convert page range 1-3 and page 5
      all2md document.pdf --pdf-pages "1-3,5"

      # Convert from page 10 to end
      all2md document.pdf --pdf-pages "10-"

``--pdf-password``
   Password for encrypted PDF documents.

   .. code-block:: bash

      # Provide password for encrypted PDF
      all2md encrypted.pdf --pdf-password "secret123"

``--pdf-no-detect-columns``
   Disable multi-column layout detection.

   **Default:** Column detection is enabled

   .. code-block:: bash

      # Disable column detection
      all2md document.pdf --pdf-no-detect-columns

``--pdf-header-percentile-threshold``
   Percentile threshold for header detection (e.g., 75 = top 25% of font sizes).

   **Default:** 75

   .. code-block:: bash

      # Use stricter header detection (top 10% of font sizes)
      all2md document.pdf --pdf-header-percentile-threshold 90

``--pdf-no-enable-table-fallback-detection``
   Disable heuristic fallback when PyMuPDF table detection fails.

   **Default:** Fallback detection is enabled

   .. code-block:: bash

      # Disable table fallback detection
      all2md document.pdf --pdf-no-enable-table-fallback-detection

``--pdf-no-merge-hyphenated-words``
   Disable merging of words split by hyphens at line breaks.

   **Default:** Hyphenated word merging is enabled

   .. code-block:: bash

      # Keep hyphenated line breaks as-is
      all2md document.pdf --pdf-no-merge-hyphenated-words

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

Network Security Options
^^^^^^^^^^^^^^^^^^^^^^^^^

``--html-network-allow-remote-fetch``
   Allow fetching remote URLs for images and resources (base64/download modes).

   **Default:** Disabled (prevents SSRF attacks)

   .. code-block:: bash

      # Enable remote fetching with security controls
      all2md webpage.html --html-network-allow-remote-fetch --html-network-require-https --html-network-network-timeout 5

``--html-network-allowed-hosts``
   Comma-separated list of allowed hostnames for remote fetching.

   .. note::

      For specifying multiple hosts in a list, you can use a comma-separated value as shown below for a single invocation. For more complex list specifications, use a JSON configuration file with the ``--options-json`` flag.

   .. code-block:: bash

      # Only allow specific hosts (single host)
      all2md webpage.html --html-network-allow-remote-fetch --html-network-allowed-hosts "example.com"

      # Multiple hosts via JSON config (recommended for multiple values)
      # In config.json: {"html.network.allowed_hosts": ["example.com", "cdn.example.com"]}
      all2md webpage.html --html-network-allow-remote-fetch --options-json config.json

``--html-network-require-https``
   Require HTTPS for all remote URL fetching.

   **Default:** Disabled

   .. code-block:: bash

      # Force HTTPS for security
      all2md webpage.html --html-network-allow-remote-fetch --html-network-require-https

``--html-network-network-timeout``
   Timeout in seconds for remote URL fetching.

   **Default:** 10.0

   .. code-block:: bash

      # Set 5-second timeout
      all2md webpage.html --html-network-allow-remote-fetch --html-network-network-timeout 5

``--html-network-max-remote-asset-bytes``
   Maximum allowed size in bytes for downloaded remote assets.

   **Default:** 20971520 (20MB)

   .. code-block:: bash

      # Limit remote assets to 2MB
      all2md webpage.html --html-network-allow-remote-fetch --html-network-max-remote-asset-bytes 2097152

Global Network Control
^^^^^^^^^^^^^^^^^^^^^^^

For maximum security, use the ``ALL2MD_DISABLE_NETWORK`` environment variable to globally block all network operations:

.. code-block:: bash

   # Disable all network operations globally
   export ALL2MD_DISABLE_NETWORK=1
   all2md webpage.html  # Will skip all remote resources regardless of options

Security Examples
^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Secure web scraping with allowlist
   all2md webpage.html \
       --html-network-allow-remote-fetch \
       --html-network-allowed-hosts "trusted-site.com" \
       --html-network-require-https \
       --html-network-network-timeout 5 \
       --html-network-max-remote-asset-bytes 1048576 \
       --attachment-mode download \
       --attachment-output-dir ./secure_images

   # Maximum security (no network access)
   ALL2MD_DISABLE_NETWORK=1 all2md webpage.html --attachment-mode skip

Security Preset Options
^^^^^^^^^^^^^^^^^^^^^^^^

For common security scenarios, all2md provides convenient preset flags that configure multiple security settings at once. These presets are especially useful when processing untrusted HTML or web content.

``--strict-html-sanitize``
   Strict security preset: strips dangerous HTML elements and disables all remote and local file fetching.

   **Applies the following settings:**
      * ``strip_dangerous_elements=True`` - Removes script, style, and other potentially dangerous tags
      * ``allow_remote_fetch=False`` - Blocks all remote URL fetching
      * ``allow_local_files=False`` - Blocks local file access
      * ``allow_cwd_files=False`` - Blocks current directory file access

   .. code-block:: bash

      # Maximum HTML sanitization
      all2md untrusted.html --strict-html-sanitize

``--safe-mode``
   Balanced security preset: sanitizes HTML and allows remote fetch with HTTPS requirement, but blocks local file access.

   **Applies the following settings:**
      * ``strip_dangerous_elements=True`` - Removes dangerous HTML elements
      * ``allow_remote_fetch=True`` - Allows remote fetching with restrictions
      * ``require_https=True`` - Enforces HTTPS for all remote URLs
      * ``allow_local_files=False`` - Blocks local file access
      * ``allow_cwd_files=False`` - Blocks current directory file access

   .. code-block:: bash

      # Balanced security for web content
      all2md webpage.html --safe-mode --attachment-mode download

``--paranoid-mode``
   Maximum security preset: like safe-mode but with stricter size limits and host validation.

   **Applies the following settings:**
      * All settings from ``--safe-mode``
      * ``allowed_hosts=[]`` - Denies all remote hosts by default (use ``--html-network-allowed-hosts`` to add specific trusted hosts)
      * ``max_attachment_size_bytes=5242880`` - Reduces max size to 5MB (from default 20MB)
      * ``max_remote_asset_bytes=5242880`` - Reduces max remote asset size to 5MB

   .. note::

      **Host Allowlist Semantics:**

      * ``allowed_hosts=[]`` (empty list) - Blocks ALL remote hosts
      * ``allowed_hosts=None`` (not set) - Allows all hosts subject to other constraints (HTTPS requirement, size limits, etc.)
      * ``allowed_hosts=["example.com"]`` (specific hosts) - Only allows listed hosts

      In paranoid mode, you must explicitly add trusted hosts using ``--html-network-allowed-hosts`` to allow any remote fetching.

   .. code-block:: bash

      # Maximum security for untrusted sources
      all2md suspicious.html --paranoid-mode

**Understanding Security Presets:**

Security presets provide quick, pre-configured security settings for common scenarios. They're especially valuable when processing untrusted HTML or web content where you need protection against:

* **Server-Side Request Forgery (SSRF)** - Preventing malicious HTML from accessing internal network resources
* **Local File Disclosure** - Blocking access to sensitive local files
* **Resource Exhaustion** - Limiting download sizes to prevent DoS attacks
* **Script Injection** - Removing dangerous HTML elements

**Preset Comparison:**

.. list-table::
   :header-rows: 1
   :widths: 25 25 25 25

   * - Setting
     - strict-html-sanitize
     - safe-mode
     - paranoid-mode
   * - Strip dangerous elements
     - ✓ Yes
     - ✓ Yes
     - ✓ Yes
   * - Remote fetch
     - ✗ Blocked
     - ✓ HTTPS only
     - ✓ HTTPS only
   * - Local file access
     - ✗ Blocked
     - ✗ Blocked
     - ✗ Blocked
   * - Max download size
     - N/A
     - 20MB (default)
     - 5MB (reduced)
   * - Host validation
     - N/A
     - Optional
     - ✓ Enforced

**When to Use Each Preset:**

* **--strict-html-sanitize**: Maximum security for completely untrusted HTML. Blocks all network and file access.

  *Use cases:* User-submitted HTML, scraped content from unknown sources, any HTML that shouldn't access external resources.

* **--safe-mode**: Balanced security for web content that needs images. Allows HTTPS-only remote fetching.

  *Use cases:* Converting web pages with images, processing HTML emails, documentation with external resources.

* **--paranoid-mode**: Maximum security with some remote access. Like safe-mode but with stricter size limits and host validation.

  *Use cases:* High-security environments, processing potentially malicious content, compliance-sensitive operations.

**Overriding Preset Values:**

Individual security flags specified after a preset will override the preset's defaults. This allows you to start with a secure baseline and selectively relax restrictions:

.. code-block:: bash

   # Start with strict sanitization, then allow specific trusted hosts
   all2md webpage.html --safe-mode --html-network-allowed-hosts "cdn.example.com"

   # Use paranoid mode but increase size limit for legitimate large images
   all2md webpage.html --paranoid-mode --html-network-max-remote-asset-bytes 10485760  # 10MB

   # Combine safe-mode with attachment downloads
   all2md webpage.html --safe-mode --attachment-mode download --attachment-output-dir ./images

**Important:** CLI flags are processed left-to-right, so presets should come first:

.. code-block:: bash

   # ✓ Correct: Preset first, then overrides
   all2md page.html --safe-mode --html-network-max-remote-asset-bytes 5242880

   # ✗ Wrong: Override will be reset by preset
   all2md page.html --html-network-max-remote-asset-bytes 5242880 --safe-mode

**Progressive Security Examples:**

.. code-block:: bash

   # From least to most secure processing of the same HTML file

   # 1. No security (default - use only for trusted local HTML)
   all2md trusted.html --attachment-mode download

   # 2. Basic sanitization (remove scripts/styles)
   all2md webpage.html --html-strip-dangerous-elements --attachment-mode download

   # 3. Safe mode (HTTPS-only external resources)
   all2md webpage.html --safe-mode --attachment-mode download

   # 4. Paranoid mode (strict size limits and validation)
   all2md webpage.html --paranoid-mode --attachment-mode download

   # 5. Maximum security (no external access at all)
   all2md untrusted.html --strict-html-sanitize --attachment-mode skip

**Note on Network Access:**

For absolute maximum security across all operations (not just HTML), use the ``ALL2MD_DISABLE_NETWORK`` environment variable which globally disables all network operations:

.. code-block:: bash

   # Global network disable - overrides ALL other settings
   export ALL2MD_DISABLE_NETWORK=1
   all2md webpage.html  # No network access regardless of flags

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

Batch Processing
----------------

Multi-File Processing
~~~~~~~~~~~~~~~~~~~~~

all2md supports processing multiple files with parallel execution and rich output formatting.

``--output-dir``
   Directory to save converted files when processing multiple inputs.

   .. code-block:: bash

      # Convert all PDFs in current directory
      all2md *.pdf --output-dir ./converted

      # Convert with directory structure preservation
      all2md ./documents --recursive --output-dir ./markdown --preserve-structure

``--recursive``, ``-r``
   Process directories recursively.

   .. code-block:: bash

      # Convert all supported files in directory tree
      all2md ./documents --recursive --output-dir ./converted

      # Process specific formats recursively
      all2md ./documents --recursive --format pdf --output-dir ./pdfs

``--parallel``, ``-p``
   Process files in parallel with optional worker count.

   .. code-block:: bash

      # Use default number of workers (CPU count)
      all2md *.pdf --parallel --output-dir ./converted

      # Specify 4 parallel workers
      all2md *.pdf --parallel 4 --output-dir ./converted

``--skip-errors``
   Continue processing remaining files if one fails.

   .. code-block:: bash

      # Don't stop on errors
      all2md *.pdf --skip-errors --output-dir ./converted

``--preserve-structure``
   Maintain directory structure in output directory.

   .. code-block:: bash

      # Keep original directory hierarchy
      all2md ./docs --recursive --preserve-structure --output-dir ./markdown

``--collate``
   Combine multiple files into a single output.

   .. code-block:: bash

      # Combine all PDFs into one markdown file
      all2md *.pdf --collate --out combined.md

      # Combine to stdout
      all2md *.pdf --collate > all_documents.md

``--exclude``
   Exclude files matching glob pattern (can be used multiple times).

   .. code-block:: bash

      # Exclude test files
      all2md ./docs --recursive --exclude "*test*" --output-dir ./converted

      # Multiple exclusions
      all2md ./docs --recursive --exclude "*.draft.*" --exclude "temp/*" --output-dir ./converted

Rich Output Features
~~~~~~~~~~~~~~~~~~~~

``--rich``
   Enable rich terminal output with formatting and colors.

   .. code-block:: bash

      # Pretty formatted output
      all2md *.pdf --rich --output-dir ./converted

``--progress``
   Show progress bar for file conversions.

   .. code-block:: bash

      # Show progress bar
      all2md *.pdf --progress --output-dir ./converted

      # Progress is auto-enabled for multiple files with --rich
      all2md *.pdf --rich --output-dir ./converted

``--no-summary``
   Disable summary output after processing multiple files.

   .. code-block:: bash

      # No summary statistics
      all2md *.pdf --no-summary --output-dir ./converted

Advanced Features
~~~~~~~~~~~~~~~~~~

``--save-config``
   Save current CLI arguments to a JSON configuration file.

   .. code-block:: bash

      # Save settings for reuse
      all2md document.pdf --attachment-mode base64 --save-config my_settings.json

      # Use saved settings
      all2md other_document.pdf --options-json my_settings.json

``--dry-run``
   Preview what would be converted without actually processing files.

   .. code-block:: bash

      # See what files would be processed
      all2md ./documents --recursive --dry-run

      # Test exclusion patterns
      all2md ./docs --recursive --exclude "*.draft.*" --dry-run

Dependency Management
---------------------

all2md provides built-in dependency management commands to check and install format-specific dependencies.

Check Dependencies
~~~~~~~~~~~~~~~~~~

Check which dependencies are available for a specific format:

.. code-block:: bash

   # Check all dependencies
   all2md check-deps

   # Check PDF dependencies
   all2md check-deps pdf

   # Check Word document dependencies
   all2md check-deps docx

   # Check all spreadsheet dependencies
   all2md check-deps spreadsheet

   # Show help for check command
   all2md check-deps --help

Install Dependencies
~~~~~~~~~~~~~~~~~~~~

Install missing dependencies for a specific format:

.. code-block:: bash

   # Install PDF dependencies
   all2md install-deps pdf

   # Install PowerPoint dependencies
   all2md install-deps pptx

   # Install all missing dependencies
   all2md install-deps

   # Show help for install command
   all2md install-deps --help

**Supported dependency groups:**
   * ``pdf`` - PyMuPDF for PDF processing
   * ``docx`` - python-docx for Word documents
   * ``pptx`` - python-pptx for PowerPoint
   * ``html`` - BeautifulSoup4 and httpx for HTML
   * ``epub`` - ebooklib for EPUB e-books
   * ``rtf`` - pyth3 for Rich Text Format
   * ``odf`` - odfpy for OpenDocument formats
   * ``spreadsheet`` - openpyxl for Excel files
   * ``all`` - All optional dependencies

Format Detection and Planning
------------------------------

List Supported Formats
~~~~~~~~~~~~~~~~~~~~~~

The ``list-formats`` command displays all supported file formats, their extensions, required dependencies, and availability status in your environment.

**Basic Usage:**

.. code-block:: bash

   # List all supported formats with availability status
   all2md list-formats

**Example output:**

.. code-block:: text

   Format         Extensions              Dependencies    Status
   ─────────────────────────────────────────────────────────────
   pdf            .pdf                   PyMuPDF         ✓ Available
   docx           .docx                  python-docx     ✓ Available
   html           .html, .htm            BeautifulSoup4  ✓ Available
   pptx           .pptx                  python-pptx     ✗ Missing
   ...

**Show Format Details:**

.. code-block:: bash

   # Get detailed information about a specific format
   all2md list-formats pdf

**Example output:**

.. code-block:: text

   Format: pdf
   Extensions: .pdf
   MIME types: application/pdf
   Dependencies:
     - PyMuPDF (fitz) - ✓ Installed (version 1.23.8)
   Features:
     - Table detection and extraction
     - Multi-column layout handling
     - Image extraction
     - Page-specific processing
     - Encrypted PDF support

**Filter by Availability:**

.. code-block:: bash

   # Show only formats with installed dependencies
   all2md list-formats --available-only

**Rich Output:**

.. code-block:: bash

   # Enhanced formatting with colors and styling (requires rich library)
   all2md list-formats --rich

This command is especially useful for:

* **Diagnosing format support issues** - Verify that required dependencies are installed
* **Planning installations** - See what formats are available before processing files
* **CI/CD pipelines** - Check environment setup programmatically
* **Documentation** - Generate up-to-date format support lists

Detect File Format Without Converting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``--detect-only`` flag analyzes files to determine their format without performing conversion. This is useful for validating format detection, checking file types in batch operations, or verifying dependencies before processing.

**Basic Usage:**

.. code-block:: bash

   # Detect format for a single file
   all2md document.pdf --detect-only

**Example output:**

.. code-block:: text

   File: document.pdf
   Detected format: pdf
   Converter: pdf2markdown
   Dependencies: ✓ All required dependencies available
   Ready to convert: Yes

**Batch Detection:**

.. code-block:: bash

   # Detect formats for multiple files
   all2md *.* --detect-only

**Example output:**

.. code-block:: text

   File                    Format      Status
   ───────────────────────────────────────────────
   report.pdf             pdf         ✓ Ready
   slides.pptx            pptx        ✗ Missing python-pptx
   data.xlsx              spreadsheet ✓ Ready
   notes.txt              txt         ✓ Ready
   webpage.html           html        ✓ Ready

**With Rich Output:**

.. code-block:: bash

   # Enhanced detection table with colors and progress bar
   all2md documents/*.* --detect-only --rich

**Use Cases:**

* **Pre-flight checks** - Verify all files can be processed before starting batch conversion
* **Format validation** - Confirm file extensions match actual content
* **Dependency verification** - Identify missing dependencies for specific files
* **CI/CD integration** - Validate document collections in automated pipelines

Dry Run Mode
~~~~~~~~~~~~

The ``--dry-run`` flag shows exactly what would be converted without actually processing files. This is invaluable for previewing batch operations, verifying file selection patterns, and checking configurations.

**Basic Usage:**

.. code-block:: bash

   # Preview what would be converted
   all2md documents/*.pdf --dry-run --output-dir ./converted

**Example output:**

.. code-block:: text

   Dry run mode: No files will be converted

   Planned conversions:

   documents/report.pdf → ./converted/report.md
   documents/analysis.pdf → ./converted/analysis.md
   documents/summary.pdf → ./converted/summary.md

   Total: 3 files would be converted

**With Exclusions:**

.. code-block:: bash

   # Preview with exclusion patterns
   all2md ./project --recursive --exclude "*.tmp" --exclude "__pycache__" --dry-run

**Example output:**

.. code-block:: text

   Dry run mode: No files will be converted

   Scanning directory: ./project (recursive)
   Exclusion patterns: *.tmp, __pycache__

   Planned conversions:

   ./project/docs/readme.md → ./project/docs/readme.md (text)
   ./project/reports/q1.pdf → ./project/reports/q1.md
   ./project/data/sales.xlsx → ./project/data/sales.md

   Excluded:
   ./project/cache/temp.tmp (matches *.tmp)
   ./project/__pycache__/config.pyc (matches __pycache__)

   Total: 3 files would be converted, 2 excluded

**With Rich Progress:**

.. code-block:: bash

   # Show dry run with rich formatting
   all2md large_collection/*.* --dry-run --rich --progress

**Example output:**

.. code-block:: text

   🔍 Analyzing files...

   ┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ Source              ┃ Format   ┃ Destination           ┃
   ┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
   │ report.pdf          │ pdf      │ ./converted/report.md │
   │ slides.pptx         │ pptx     │ ./converted/slides.md │
   │ data.xlsx           │ sheet    │ ./converted/data.md   │
   └─────────────────────┴──────────┴───────────────────────┘

   ✓ 3 files ready to convert
   ⚠ 1 file missing dependencies (pptx)

**Combined with Other Options:**

.. code-block:: bash

   # Preview complex batch operation
   all2md ./documents \
       --recursive \
       --preserve-structure \
       --output-dir ./markdown \
       --exclude "*.draft.*" \
       --exclude "temp/*" \
       --parallel 4 \
       --dry-run

This shows exactly how files will be processed, where they'll be saved, and what directory structure will be created, all without touching any files.

**Use Cases:**

* **Validate glob patterns** - Ensure file selection matches expectations
* **Test exclusion rules** - Verify that unwanted files are properly filtered
* **Preview directory structure** - See output layout with ``--preserve-structure``
* **Verify batch settings** - Check all configuration before starting long-running jobs
* **Safe experimentation** - Try different options without risk

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
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Process specific pages with custom formatting
   all2md large_document.pdf --pdf-pages "1,2,3,6,11" --markdown-emphasis-symbol "_"

   # Handle encrypted PDF
   all2md encrypted.pdf --pdf-password "secret" --attachment-mode download

   # Disable column detection for simple layout
   all2md simple.pdf --pdf-no-detect-columns

Email Processing
~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Process email with attachments
   all2md message.eml --attachment-mode download --attachment-output-dir ./email_files

   # Clean email conversion (no headers, flat structure)
   all2md thread.eml --eml-no-include-headers --eml-no-preserve-thread-structure

Batch Processing
~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Process all PDFs in directory with parallel processing
   all2md *.pdf --parallel --output-dir ./converted --skip-errors

   # Recursive processing with structure preservation
   all2md ./documents --recursive --preserve-structure --output-dir ./markdown --exclude "*.tmp"

   # Process with consistent options using old approach
   find ./documents -name "*.docx" -exec all2md {} --out {}.md --markdown-emphasis-symbol "_" \;

Web Content Processing
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Download and convert web page
   curl -s "https://example.com/page.html" | all2md - --html-extract-title --html-strip-dangerous-elements

   # Process saved web page with images
   all2md saved_page.html --attachment-mode download --attachment-base-url "https://example.com"

Advanced Multi-File Processing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Recursively convert all documents with parallel processing
   all2md ./documents --recursive --parallel 8 --output-dir ./markdown_output --rich

   # Collate multiple chapters into a single book
   all2md chapter_*.pdf --collate --out complete_book.md --skip-errors

   # Process with exclusions and structure preservation
   all2md ./project --recursive --preserve-structure --exclude "__pycache__" --exclude "*.tmp" --exclude "node_modules"

   # Dry run to preview what would be processed
   all2md ./large_project --recursive --dry-run --exclude "*.log"

   # Quiet batch processing with error handling
   all2md *.docx --parallel --skip-errors --no-summary --output-dir ./converted

Configuration File Usage
~~~~~~~~~~~~~~~~~~~~~~~~

Create a configuration file ``config.json``:

.. code-block:: json

   {
       "attachment_mode": "download",
       "attachment_output_dir": "./attachments",
       "markdown.emphasis_symbol": "_",
       "markdown.bullet_symbols": "•◦▪",
       "pdf.detect_columns": true,
       "html.strip_dangerous_elements": true,
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
~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~

Add to your ``.bashrc`` or ``.bash_profile``:

.. code-block:: bash

   # Basic completion for file extensions
   complete -f -X '!*.@(pdf|docx|pptx|html|eml|epub|ipynb|odt|odp|xlsx|csv|tsv)' all2md

Aliases and Functions
~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~

all2md supports setting default values for **all CLI options** using environment variables. This provides a convenient way to configure defaults for scripts or user preferences.

**Configuration File via Environment Variable:**

``ALL2MD_CONFIG_JSON``
   Path to a JSON configuration file containing conversion options. This is equivalent to using ``--options-json`` on the command line. The CLI argument ``--options-json`` takes precedence over this environment variable if both are specified.

   .. code-block:: bash

      # Set default config file location
      export ALL2MD_CONFIG_JSON="$HOME/.config/all2md/default.json"

      # Now all commands use this config by default
      all2md document.pdf

      # Override with explicit flag
      all2md document.pdf --options-json ./project-config.json

**Naming Convention:**

Environment variables use the pattern ``ALL2MD_<OPTION_NAME>`` where ``<OPTION_NAME>`` is the CLI argument name in uppercase with hyphens and dots replaced by underscores.

**Examples:**

.. code-block:: bash

   # CLI argument: --output-dir
   export ALL2MD_OUTPUT_DIR="./converted"

   # CLI argument: --markdown-emphasis-symbol
   export ALL2MD_MARKDOWN_EMPHASIS_SYMBOL="_"

   # CLI argument: --pdf-pages (comma-separated, 1-based)
   export ALL2MD_PDF_PAGES="1,2,3"

   # CLI argument: --parallel (integer)
   export ALL2MD_PARALLEL="4"

**Supported Value Types:**

* **Strings:** Use the value directly
* **Booleans:** Use ``true``, ``1``, ``yes``, or ``on`` for true; anything else for false
* **Integers:** Provide numeric values (validated for positive integers where applicable)
* **Lists:** Use comma-separated values (e.g., for ``--exclude`` or ``--pdf-pages``)

**Complete Example Configuration:**

.. code-block:: bash

   # Universal attachment options
   export ALL2MD_ATTACHMENT_MODE="download"
   export ALL2MD_ATTACHMENT_OUTPUT_DIR="./attachments"

   # Markdown formatting
   export ALL2MD_MARKDOWN_EMPHASIS_SYMBOL="_"
   export ALL2MD_MARKDOWN_BULLET_SYMBOLS="•◦▪"

   # Multi-file processing options
   export ALL2MD_RICH="true"
   export ALL2MD_PARALLEL="4"
   export ALL2MD_OUTPUT_DIR="./converted"
   export ALL2MD_SKIP_ERRORS="true"
   export ALL2MD_RECURSIVE="true"
   export ALL2MD_PRESERVE_STRUCTURE="true"

   # Format-specific options
   export ALL2MD_PDF_DETECT_COLUMNS="false"
   export ALL2MD_HTML_STRIP_DANGEROUS_ELEMENTS="true"
   export ALL2MD_PPTX_INCLUDE_SLIDE_NUMBERS="true"

   # Exclusion patterns (comma-separated)
   export ALL2MD_EXCLUDE="*.tmp,*.bak,__pycache__"

**Precedence:**

Command-line arguments always override environment variables:

.. code-block:: bash

   export ALL2MD_OUTPUT_DIR="./default"

   # This will use "./override" instead of "./default"
   all2md document.pdf --output-dir ./override

**Use Cases:**

1. **User Preferences:** Set your preferred defaults in ``.bashrc`` or ``.zshrc``
2. **CI/CD Scripts:** Configure consistent behavior across pipeline stages
3. **Docker Containers:** Set default configuration without modifying commands
4. **Batch Processing:** Avoid repeating common options

**Global Network Control:**

For security-sensitive environments, use ``ALL2MD_DISABLE_NETWORK`` to globally disable all network operations:

.. code-block:: bash

   # Disable all network operations globally (overrides all other network settings)
   export ALL2MD_DISABLE_NETWORK=1
   all2md webpage.html  # Will skip all remote resources

For complete option details and programmatic usage, see the :doc:`options` reference and Python API documentation.