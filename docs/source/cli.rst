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

The primary entry point is simply ``all2md`` (equivalent to ``all2md convert``). Provide one or more
input paths and optional output arguments to drive the conversion pipeline.

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

   # Quick help with the most important options
   all2md --help
   all2md help

   # Full reference (all options, grouped by format)
   all2md help full

   # Format-specific help (parser + renderer options)
   all2md help pdf
   all2md help docx

   # Rich-formatted help (colour, emphasis) when Rich is installed
   all2md help full --rich

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

Search Command
--------------

``all2md search`` builds a lightweight index over one or more documents and executes
keyword (BM25), vector (FAISS), hybrid, or simple grep searches. The command works
with any format supported by the core converters and can reuse or persist indexes for
faster follow-up queries.

.. code-block:: bash

   # Keyword search across a directory (ephemeral index)
   all2md search "contract termination" contracts/*.pdf --keyword

   # Hybrid search with persisted index (requires extras: pip install all2md[search])
   all2md search "macroeconomic outlook" reports/ --hybrid --index-dir ./index --persist

   # Reuse an existing index without reprocessing inputs
   all2md search "incident response" --index-dir ./index

Common grep-style flags are supported:

* ``-A/-B/-C`` to control trailing/leading context lines (e.g. ``-C 1`` for one line around each match)
* ``--regex``/``--no-regex`` to treat the query as a case-insensitive regular expression
* ``--rich`` to enable colorized output (requires ``rich``)

Key options:

* ``--mode`` / ``--grep`` / ``--keyword`` / ``--vector`` / ``--hybrid`` – select search strategy
* ``--index-dir`` – directory to load or store the index
* ``--persist`` – write the generated index to disk for later reuse
* ``--chunk-size`` / ``--chunk-overlap`` – control chunking granularity
* ``--vector-model`` – sentence-transformers model (vector or hybrid modes)

``all2md search`` honours configuration defaults under the ``[search]`` section in
``.all2md.toml``. Install the optional extras ``all2md[search]`` to enable BM25 and
vector search backends.

Diff Command
------------

``all2md diff`` compares two documents and generates a unified diff, similar to the Unix
``diff`` command but supporting any document format (PDF, DOCX, HTML, etc.). The comparison
is text-based and guaranteed symmetric: comparing A to B produces the exact opposite of
comparing B to A (with +/- swapped).

Basic Usage
~~~~~~~~~~~

.. code-block:: bash

   # Compare two documents (unified diff output by default)
   all2md diff report_v1.pdf report_v2.pdf

   # Compare documents of different formats
   all2md diff contract.docx contract.pdf

   # Save diff to file
   all2md diff doc1.md doc2.md --output changes.diff

Common Options
~~~~~~~~~~~~~~

Output Formats
^^^^^^^^^^^^^^

.. code-block:: bash

   # Unified diff (default, like diff -u)
   all2md diff doc1.pdf doc2.pdf

   # HTML visual diff (GitHub-style inline highlighting)
   all2md diff doc1.pdf doc2.pdf --format html --output diff.html

   # JSON structured diff (for programmatic access)
   all2md diff doc1.pdf doc2.pdf --format json

Comparison Options
^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Ignore whitespace changes (like diff -w)
   all2md diff doc1.md doc2.md --ignore-whitespace
   all2md diff doc1.md doc2.md -w

   # Custom context lines (default: 3, like diff -C)
   all2md diff doc1.pdf doc2.pdf --context 5
   all2md diff doc1.pdf doc2.pdf -C 5

Color Output
^^^^^^^^^^^^

.. code-block:: bash

   # Colorize output automatically if terminal
   all2md diff doc1.md doc2.md --color auto  # (default)

   # Always colorize (even when piped)
   all2md diff doc1.md doc2.md --color always

   # Never colorize
   all2md diff doc1.md doc2.md --color never

Examples
~~~~~~~~

**Compare PDF Reports:**

.. code-block:: bash

   # Compare two versions of a report
   all2md diff quarterly_report_q1.pdf quarterly_report_q2.pdf

   # Generate visual HTML diff
   all2md diff report_draft.pdf report_final.pdf \
       --format html --output report_changes.html

**Compare Word Documents:**

.. code-block:: bash

   # Compare contract versions, ignoring whitespace
   all2md diff contract_v1.docx contract_v2.docx -w

   # Save unified diff to file
   all2md diff proposal_old.docx proposal_new.docx -o changes.diff

**Cross-Format Comparison:**

.. code-block:: bash

   # Compare different formats of the same document
   all2md diff document.md document.pdf

   # Compare web page to markdown
   all2md diff page.html page.md --ignore-whitespace

**Symmetric Comparison:**

.. code-block:: bash

   # These produce opposite results (+ becomes -, - becomes +)
   all2md diff doc1.pdf doc2.pdf
   all2md diff doc2.pdf doc1.pdf

Output Formats
~~~~~~~~~~~~~~

Unified Diff (Default)
^^^^^^^^^^^^^^^^^^^^^^^

Standard unified diff format compatible with ``patch``, ``git diff``, and other tools:

.. code-block:: diff

   --- report_v1.pdf
   +++ report_v2.pdf
   @@ -1,5 +1,6 @@
    # Executive Summary

    This report covers Q1 performance.
   +Key findings include revenue growth.

   -## Challenges
   +## Opportunities
    We identified several growth areas.

HTML Visual Diff
^^^^^^^^^^^^^^^^^

GitHub-style inline highlighting with additions in green, deletions in red with
strikethrough, and context in normal text. Ideal for viewing in a browser.

.. code-block:: bash

   all2md diff doc1.pdf doc2.pdf --format html -o changes.html
   # Open in browser: open changes.html

JSON Structured Diff
^^^^^^^^^^^^^^^^^^^^^

Machine-readable format for programmatic processing:

.. code-block:: json

   {
     "type": "unified_diff",
     "old_file": "doc1.pdf",
     "new_file": "doc2.pdf",
     "statistics": {
       "lines_added": 3,
       "lines_deleted": 2,
       "lines_context": 15,
       "total_changes": 5
     },
     "hunks": [
       {
         "header": "@@ -1,5 +1,6 @@",
         "changes": [
           {"type": "context", "content": "# Executive Summary"},
           {"type": "added", "content": "Key findings..."},
           {"type": "deleted", "content": "Old text..."}
         ]
       }
     ]
   }

Configuration Management
~~~~~~~~~~~~~~~~~~~~~~~~~

The ``all2md config`` command provides tools for managing configuration files.

.. _config-generate:

Generate Default Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Create a configuration file with all available options:

.. code-block:: bash

   # Generate TOML configuration (recommended)
   all2md config generate --out .all2md.toml

   # Generate JSON configuration
   all2md config generate --format json --out config.json

   # Print to stdout
   all2md config generate
   all2md config generate --format json

The generated configuration includes:
* Helpful comments explaining each option (TOML only)
* All available options with their default values
* Format-specific settings organized by section

**Example Generated Configuration (TOML):**

.. code-block:: toml

   # all2md configuration file
   # Automatically generated default configuration

   # Attachment handling mode: "skip", "download", or "base64"
   attachment_mode = "skip"

   # PDF conversion options
   [pdf]
   # Detect multi-column layouts
   detect_columns = true
   # Skip extracting images from PDFs
   skip_image_extraction = false
   # Enable fallback table detection
   enable_table_fallback_detection = true
   # Merge hyphenated words at line breaks
   merge_hyphenated_words = false

   # HTML conversion options
   [html]
   # Strip potentially dangerous HTML elements
   strip_dangerous_elements = true
   # Extract title from HTML
   extract_title = false

   # Markdown output options
   [markdown]
   # Symbol to use for emphasis: "*" or "_"
   emphasis_symbol = "*"

   # ... (additional format sections)

**Example Generated Configuration (JSON):**

.. code-block:: json

   {
     "attachment_mode": "skip",
     "pdf": {
       "detect_columns": false,
       "skip_image_extraction": false,
       "enable_table_fallback_detection": true,
       "merge_hyphenated_words": false
     },
     "html": {
       "strip_dangerous_elements": true,
       "extract_title": false
     },
     "markdown": {
       "emphasis_symbol": "*"
     }
   }

**Show Effective Configuration**

Display the merged configuration from all sources:

.. code-block:: bash

   # Show current configuration
   all2md config show

   # Show as JSON
   all2md config show --format json

   # Hide source information
   all2md config show --no-source

This command shows configuration merged from:
1. ``ALL2MD_CONFIG`` environment variable
2. ``.all2md.toml`` or ``.all2md.json`` in current directory
3. ``.all2md.toml`` or ``.all2md.json`` in home directory

**Example Output:**

.. code-block:: text

   Configuration Sources (in priority order):
   ------------------------------------------------------------
   1. ALL2MD_CONFIG env var: (not set)
   2. /home/user/project/.all2md.toml [FOUND]
   3. /home/user/.all2md.toml [-]

   Effective Configuration:
   ============================================================
   attachment_mode = "download"
   attachment_output_dir = "./images"

   [pdf]
   detect_columns = true

   [markdown]
   emphasis_symbol = "_"

**Validate Configuration File**

Check configuration file syntax:

.. code-block:: bash

   # Validate a configuration file
   all2md config validate .all2md.toml
   all2md config validate ~/.all2md.json

   # Get detailed validation errors
   all2md config validate my-config.toml

This verifies:
* File can be read and parsed
* JSON/TOML syntax is valid
* Configuration structure is correct

**Example Output (Valid Config):**

.. code-block:: text

   Configuration file is valid: .all2md.toml
   Format: .toml
   Keys found: attachment_mode, pdf, html, markdown

**Example Output (Invalid Config):**

.. code-block:: text

   Invalid configuration file: Invalid TOML syntax at line 5: Expected '=' after key
   Error validating configuration: .all2md.toml

**Configuration Priority**

Configuration sources are applied in this order (highest to lowest priority):

1. CLI arguments (highest priority)
2. ``--preset`` flag (see :ref:`presets` for available presets)
3. Explicit ``--config`` flag
4. Environment variable config (``ALL2MD_CONFIG``)
5. Auto-discovered config files (``.all2md.toml`` or ``.all2md.json``, lowest priority)

.. seealso::

   :ref:`presets`
      For information about preset configurations and how to use them

**Example Workflow:**

.. code-block:: bash

   # 1. Generate a template
   all2md config generate --out .all2md.toml

   # 2. Edit the file with your preferences
   vim .all2md.toml

   # 3. Validate your changes
   all2md config validate .all2md.toml

   # 4. Check effective configuration
   all2md config show

   # 5. Use it (auto-discovered)
   all2md document.pdf

Static Site Generation
-----------------------

The ``all2md generate-site`` subcommand converts document collections into Hugo or Jekyll static sites with proper frontmatter, asset organization, and directory structures.

.. code-block:: bash

   all2md generate-site INPUT... --output-dir DIR --generator GENERATOR [OPTIONS]

Basic Usage
~~~~~~~~~~~

Convert a directory of documents to a Hugo site:

.. code-block:: bash

   all2md generate-site docs/ \
       --output-dir my-hugo-site \
       --generator hugo \
       --scaffold \
       --recursive

Convert blog posts to a Jekyll site:

.. code-block:: bash

   all2md generate-site posts/*.md \
       --output-dir my-blog \
       --generator jekyll \
       --scaffold

Arguments
~~~~~~~~~

**Required Arguments:**

``INPUT...``
   One or more input files or directories to convert

``--output-dir DIR``
   Output directory for the generated site

``--generator {hugo,jekyll}``
   Static site generator to target (hugo or jekyll)

**Optional Arguments:**

``--scaffold``
   Create complete site structure with config files and layouts

``--frontmatter-format {yaml,toml}``
   Override default frontmatter format
   (Hugo defaults to TOML, Jekyll to YAML)

``--content-subdir PATH``
   Subdirectory within content dir for output
   (e.g., "posts" creates content/posts/ for Hugo)

``--recursive``
   Recursively process directories

``--exclude PATTERN``
   Exclude files matching pattern (can be used multiple times)

Examples
~~~~~~~~

**Hugo Site with Scaffolding:**

.. code-block:: bash

   # Create complete Hugo site structure
   all2md generate-site documentation/ \
       --output-dir my-docs-site \
       --generator hugo \
       --scaffold \
       --recursive

   # Result:
   # my-docs-site/
   # ├── config.toml
   # ├── content/
   # │   ├── _index.md
   # │   ├── page1.md
   # │   └── page2.md
   # ├── static/images/
   # │   └── (copied images)
   # ├── themes/
   # ├── layouts/
   # └── data/

**Jekyll Blog with Date Prefixes:**

.. code-block:: bash

   # Convert blog posts with metadata
   all2md generate-site posts/ \
       --output-dir my-blog \
       --generator jekyll \
       --scaffold \
       --recursive

   # Result:
   # my-blog/
   # ├── _config.yml
   # ├── _posts/
   # │   ├── 2025-01-22-my-post.md
   # │   └── 2025-01-20-another-post.md
   # ├── assets/images/
   # │   └── (copied images)
   # ├── _layouts/
   # │   ├── default.html
   # │   └── post.html
   # └── _includes/

**Without Scaffolding (Content Only):**

.. code-block:: bash

   # Just convert files, don't create config/layouts
   all2md generate-site reports/ \
       --output-dir hugo-reports \
       --generator hugo \
       --content-subdir reports

**With Exclusions:**

.. code-block:: bash

   # Exclude drafts and private files
   all2md generate-site content/ \
       --output-dir site \
       --generator hugo \
       --recursive \
       --exclude "draft-*" \
       --exclude "private/*"

**Custom Frontmatter Format:**

.. code-block:: bash

   # Use YAML frontmatter with Hugo (instead of default TOML)
   all2md generate-site docs/ \
       --output-dir hugo-site \
       --generator hugo \
       --frontmatter-format yaml

Frontmatter Generation
~~~~~~~~~~~~~~~~~~~~~~~

The command automatically generates frontmatter from document metadata:

**Metadata Mapping:**

- ``title`` → Extracted from document title or filename
- ``date`` → From creation_date, date, or modified metadata
- ``author`` → From author field
- ``description`` → From description or subject field
- ``tags`` → From tags or keywords field (comma-separated)
- ``categories`` → From categories or category field (comma-separated)

**Generator-Specific Fields:**

*Hugo:*
- ``draft: false`` (always set)
- ``weight`` (if present in metadata)

*Jekyll:*
- ``layout: post`` (default)
- ``permalink`` (if present in metadata)

**Example frontmatter output (Hugo/TOML):**

.. code-block:: text

   +++
   title = "Getting Started Guide"
   date = 2025-01-22T10:00:00
   author = "Jane Doe"
   description = "A comprehensive guide to getting started"
   tags = ["tutorial", "beginner"]
   draft = false
   +++

**Example frontmatter output (Jekyll/YAML):**

.. code-block:: yaml

   ---
   title: Getting Started Guide
   date: 2025-01-22 10:00:00
   author: Jane Doe
   description: A comprehensive guide to getting started
   categories:
     - tutorial
     - beginner
   layout: post
   ---

Asset Management
~~~~~~~~~~~~~~~~

Images and other assets are automatically:

1. **Collected** from the document AST
2. **Copied** to the appropriate static directory
3. **Referenced** with updated paths in the markdown

**Hugo:** Assets → ``static/images/``, referenced as ``/images/filename``

**Jekyll:** Assets → ``assets/images/``, referenced as ``/assets/images/filename``

See Also
~~~~~~~~

- :doc:`static_sites` - Complete static site generation guide
- :doc:`cli` - Complete CLI reference
- ``all2md --help`` - Built-in help

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
   Force a parser instead of using auto-detection (``auto`` remains the default). Accepted values line up with
   ``all2md list-formats`` (e.g. ``pdf``, ``docx``, ``markdown``, ``asciidoc``, ``pptx``, ``zip``, ``ast`` …).

   .. code-block:: bash

      # Force PDF processing for file without extension
      all2md mysterious_file --format pdf

      # Treat binary data as markdown for rendering
      cat draft.md | all2md - --format markdown

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

Remote Input (HTTP/HTTPS)
~~~~~~~~~~~~~~~~~~~~~~~~~

``--remote-input-enabled``
   Allow all2md to fetch documents directly from HTTP(S) URLs. Disabled by default to prevent SSRF-style attacks.

   .. code-block:: bash

      # Convert a remote PDF after enabling remote input and restricting hosts
      all2md https://docs.example.com/guide.pdf \
        --remote-input-enabled \
        --remote-input-allowed-hosts docs.example.com

``--remote-input-allowed-hosts``
   Comma-separated allowlist of hostnames or CIDR ranges permitted when remote input is enabled. If omitted, every
   host is allowed—explicitly listing trusted origins is strongly recommended.

``--remote-input-allow-http``
   Permit plain HTTP downloads. HTTPS remains mandatory unless this flag is supplied.

``--remote-input-timeout``
   Network timeout (seconds) for downloading remote inputs. Default: ``10``.

``--remote-input-max-size-bytes``
   Maximum size (in bytes) for a remote document. Default: ``20971520`` (20 MB). Requests exceeding the limit abort
   before parsing to protect memory budgets.

``--remote-input-user-agent``
   Custom ``User-Agent`` header used for remote input requests. Defaults to ``all2md/<version>``.

These options only affect the source document download. Per-format network controls (e.g. ``--html-network-*``) still
apply to embedded resources fetched during conversion.

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

Rich Terminal Output
~~~~~~~~~~~~~~~~~~~~

``--rich``
   Enable Rich-rendered Markdown with colour, hyperlinks, and tables. Automatically disables itself when stdout is
   redirected, unless ``--force-rich`` is present.

``--force-rich``
   Force Rich formatting even when piping or redirecting output. Useful for capturing styled console logs.

``--rich-code-theme`` / ``--rich-inline-code-theme``
   Pick Pygments themes for fenced code blocks and inline code. ``monokai`` is the default. List available styles with
   ``pygmentize -L styles``.

``--rich-word-wrap``
   Apply word-wrapping to long lines in the Rich renderer.

``--no-rich-hyperlinks``
   Disable clickable hyperlinks (maps to ``ALL2MD_RICH_HYPERLINKS=false`` in env vars).

``--rich-justify``
   Control text justification for Rich Markdown (``left`` | ``center`` | ``right`` | ``full``).

The related environment variables are ``ALL2MD_RICH``, ``ALL2MD_FORCE_RICH``, ``ALL2MD_RICH_CODE_THEME``,
``ALL2MD_RICH_INLINE_CODE_THEME``, ``ALL2MD_RICH_WORD_WRAP``, ``ALL2MD_RICH_HYPERLINKS`` (set to ``false`` to disable),
and ``ALL2MD_RICH_JUSTIFY``.

Configuration and Debugging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. _presets:

``--preset``
   Apply a preset configuration for common use cases. Presets provide pre-configured settings that can be overridden by CLI arguments.

   .. seealso::

      :ref:`config-generate`
         To create a customizable configuration file based on a preset

``--config``
   Path to configuration file (JSON or TOML format). Command line options override config file settings.

   Configuration files are automatically discovered in this order:
   1. Explicit ``--config`` flag
   2. ``ALL2MD_CONFIG`` environment variable
   3. ``.all2md.toml`` or ``.all2md.json`` in current directory
   4. ``.all2md.toml`` or ``.all2md.json`` in home directory

   .. note::

      **Passing List Values:** For options that accept a list of values (e.g., ``--pdf-pages``, ``--html-network-allowed-hosts``), you can provide a comma-separated string. For more complex lists or to avoid shell escaping issues, using a configuration file is recommended.

      **List-type options supporting comma-separated values:**

      * ``html.network.allowed_hosts``
      * ``eml.url_wrappers``
      * ``spreadsheet.sheets``
      * ``pdf.pages``

      **Example:**

      .. code-block:: bash

         # Pass a list of hosts via the CLI
         all2md webpage.html --html-network-allowed-hosts "cdn.example.com,images.example.org"

         # Pass multiple pages
         all2md document.pdf --pdf-pages "1,2,3,5"

      **Using configuration files for complex lists:**

      .. code-block:: json

         {
           "html.network.allowed_hosts": ["cdn.example.com", "images.example.org"],
           "eml.url_wrappers": ["safelinks.protection.outlook.com", "urldefense.com"],
           "spreadsheet.sheets": ["Sheet1", "Summary", "Data"]
         }

      **Usage:**

      .. code-block:: bash

         # Use config file for list values
         all2md webpage.html --config config.json --html-network-allow-remote-fetch

         # CLI flags can still override config settings
         all2md webpage.html --config config.toml --attachment-mode download

   .. code-block:: bash

      # Use options from config file
      all2md document.pdf --config config.toml

      # Config file settings with CLI overrides
      all2md document.pdf --config config.json --attachment-mode download

      # Auto-discovery (checks cwd, then home directory)
      all2md document.pdf  # Uses .all2md.toml if present

   Example TOML configuration (recommended):

   .. code-block:: toml

      # all2md configuration file
      attachment_mode = "download"
      attachment_output_dir = "./images"

      [pdf]
      detect_columns = true
      pages = [1, 2, 3]

      [markdown]
      emphasis_symbol = "_"

   Example JSON configuration:

   .. code-block:: json

      {
        "attachment_mode": "download",
        "attachment_output_dir": "./images",
        "pdf.detect_columns": true,
        "pdf.pages": [1, 2, 3],
        "markdown.emphasis_symbol": "_"
      }

``--preset``
   Apply a preset configuration for common use cases. Presets provide pre-configured settings that can be overridden by CLI arguments.

   **Available Presets:**

   * ``fast`` - Fast processing optimized for speed over quality
   * ``quality`` - High quality processing with maximum fidelity
   * ``minimal`` - Text-only output with no attachments or images
   * ``complete`` - Complete preservation with all content and metadata
   * ``archival`` - Self-contained documents with embedded resources (base64)
   * ``documentation`` - Optimized for technical documentation

   **Preset Comparison:**

   .. list-table::
      :header-rows: 1
      :widths: 20 13 13 13 13 13 15

      * - Setting
        - fast
        - quality
        - minimal
        - complete
        - archival
        - documentation
      * - Attachment Mode
        - skip
        - download
        - skip
        - download
        - base64
        - download
      * - PDF Column Detection
        - Disabled
        - Enabled
        - Default
        - Enabled
        - Enabled
        - Enabled
      * - PDF Image Extraction
        - Skipped
        - Default
        - Skipped
        - Default
        - Default
        - Default
      * - PDF Table Fallback
        - Disabled
        - Enabled
        - Default
        - Enabled
        - Default
        - Default
      * - PDF Hyphen Merging
        - Disabled
        - Enabled
        - Default
        - Default
        - Enabled
        - Default
      * - HTML Strip Dangerous
        - Enabled
        - Disabled
        - Enabled
        - Default
        - Default
        - Enabled
      * - HTML Extract Title
        - Default
        - Enabled
        - Default
        - Enabled
        - Enabled
        - Enabled
      * - HTML Remote Fetch
        - Default
        - Default
        - Default
        - Enabled
        - Default
        - Default
      * - PPTX Include Notes
        - Disabled
        - Enabled
        - Default
        - Enabled
        - Default
        - Default
      * - PPTX Slide Numbers
        - Default
        - Enabled
        - Default
        - Enabled
        - Default
        - Default
      * - EPUB Merge Chapters
        - Default
        - Enabled
        - Default
        - Enabled
        - Enabled
        - Default
      * - EPUB Include TOC
        - Default
        - Enabled
        - Default
        - Enabled
        - Enabled
        - Default
      * - Jupyter Truncate
        - Default
        - Default
        - Default
        - Default
        - Default
        - 50 lines

   .. code-block:: bash

      # Use fast preset for quick processing
      all2md document.pdf --preset fast

      # Use quality preset with overrides
      all2md document.pdf --preset quality --attachment-mode skip

      # Combine preset with config file
      all2md document.pdf --preset quality --config custom.toml

   **Detailed Preset Descriptions:**

   **fast** - Speed-optimized processing

      Optimized for maximum conversion speed by skipping expensive operations:

      * ``attachment_mode: skip`` - No attachment processing
      * ``pdf.skip_image_extraction: true`` - Skip PDF image extraction
      * ``pdf.detect_columns: false`` - Disable column layout detection
      * ``pdf.enable_table_fallback_detection: false`` - Disable fallback table detection
      * ``html.strip_dangerous_elements: true`` - Basic security
      * ``pptx.include_notes: false`` - Skip speaker notes

      **Use when:** You need quick text extraction from many documents and don't need images or complex layout preservation.

   **quality** - Maximum fidelity

      Optimized for highest quality output with comprehensive content preservation:

      * ``attachment_mode: download`` - Save all attachments locally
      * ``pdf.detect_columns: true`` - Detect multi-column layouts
      * ``pdf.enable_table_fallback_detection: true`` - Advanced table detection
      * ``pdf.merge_hyphenated_words: true`` - Fix line-break hyphenation
      * ``html.extract_title: true`` - Extract document titles
      * ``pptx.include_notes: true`` - Include speaker notes
      * ``pptx.slide_numbers: true`` - Add slide numbers
      * ``epub.merge_chapters: true`` - Create continuous document
      * ``epub.include_toc: true`` - Include table of contents

      **Use when:** You need the highest quality output and have time for thorough processing.

   **minimal** - Text-only extraction

      Minimal processing focused on text content only:

      * ``attachment_mode: skip`` - No attachments
      * ``pdf.skip_image_extraction: true`` - Skip images
      * ``html.strip_dangerous_elements: true`` - Basic security
      * ``markdown.emphasis_symbol: *`` - Simple markdown

      **Use when:** You only need plain text content without images, tables, or formatting.

   **complete** - Full preservation

      Complete content and metadata extraction:

      * ``attachment_mode: download`` - Download all attachments
      * ``pdf.detect_columns: true`` - Advanced layout detection
      * ``pdf.enable_table_fallback_detection: true`` - Comprehensive table detection
      * ``html.extract_title: true`` - Extract metadata
      * ``html.network.allow_remote_fetch: true`` - Fetch remote resources
      * ``html.network.require_https: true`` - Secure fetching only
      * ``pptx.include_notes: true`` - Include all notes
      * ``pptx.slide_numbers: true`` - Number slides
      * ``epub.merge_chapters: true`` - Continuous document
      * ``epub.include_toc: true`` - Table of contents
      * ``eml.include_headers: true`` - Email headers
      * ``eml.preserve_thread_structure: true`` - Email threading

      **Use when:** Creating an archive or need every piece of content and metadata preserved.

   **archival** - Self-contained documents

      Creates completely self-contained documents with no external dependencies:

      * ``attachment_mode: base64`` - Embed all resources inline
      * ``pdf.detect_columns: true`` - Preserve layout
      * ``pdf.merge_hyphenated_words: true`` - Clean text
      * ``html.extract_title: true`` - Include metadata
      * ``epub.merge_chapters: true`` - Single document
      * ``epub.include_toc: true`` - Navigation structure

      **Use when:** Creating portable documents that must work without external files or network access.

   **documentation** - Technical documentation

      Optimized for technical documentation with readable code and clean formatting:

      * ``attachment_mode: download`` - External image files
      * ``markdown.emphasis_symbol: _`` - Underscore emphasis (common in tech docs)
      * ``html.extract_title: true`` - Document structure
      * ``html.strip_dangerous_elements: true`` - Clean HTML
      * ``ipynb.truncate_long_outputs: 50`` - Limit output verbosity
      * ``pdf.detect_columns: true`` - Handle multi-column layouts

      **Use when:** Converting technical documentation, API docs, or Jupyter notebooks for publication.

   **Working with Presets:**

   Presets can be combined with CLI arguments and configuration files. The priority order is:

   1. CLI arguments (highest priority)
   2. ``--preset`` flag
   3. ``--config`` file
   4. Auto-discovered config files
   5. Default values (lowest priority)

   .. code-block:: bash

      # Use quality preset with custom output directory
      all2md document.pdf --preset quality --attachment-output-dir ./my-images

      # Override preset's attachment mode
      all2md document.pdf --preset archival --attachment-mode download

      # Combine preset with config file
      all2md document.pdf --preset quality --config custom.toml

      # Fast preset for batch processing
      all2md *.pdf --preset fast --output-dir ./converted --parallel 8

   **Creating Custom Configurations Based on Presets:**

   You can create a configuration file inspired by a preset and customize it:

   .. code-block:: bash

      # Generate base config
      all2md config generate --out .all2md.toml

      # Edit to match a preset's settings and add customizations
      vim .all2md.toml

      # Use your custom config
      all2md document.pdf --config .all2md.toml

   Example of customizing the ``quality`` preset:

   .. code-block:: toml

      # Based on 'quality' preset with customizations
      attachment_mode = "download"
      attachment_output_dir = "./document-assets"

      [pdf]
      detect_columns = true
      enable_table_fallback_detection = true
      merge_hyphenated_words = true
      pages = [1, 2, 3, 5]  # Custom: only specific pages

      [html]
      extract_title = true

      [markdown]
      emphasis_symbol = "_"  # Custom: prefer underscore
      flavor = "gfm"  # Custom: GitHub-flavored markdown

   .. note::

      Use ``all2md --help`` to see preset descriptions in the command-line help.
      To create a configuration file with customizable settings, use ``all2md config generate``
      (see :ref:`config-generate` below).

``--log-level``
   Set logging level for debugging and detailed output.

   **Choices:** ``DEBUG``, ``INFO``, ``WARNING`` (default), ``ERROR``

   .. tip::

      Validation warnings such as ignored ``--out`` arguments or attachment
      directory mismatches are emitted through the logger. Make sure the
      selected log level includes ``WARNING`` messages when you want those
      hints on the console.

   .. code-block:: bash

      # Enable debug logging
      all2md document.pdf --log-level DEBUG

      # Quiet mode (errors only)
      all2md document.pdf --log-level ERROR

``--log-file``
   Write log output to a file instead of (or in addition to) console output.

   .. code-block:: bash

      # Save logs to file
      all2md *.pdf --log-file conversion.log --output-dir ./converted

      # Combine with verbose logging
      all2md ./docs --recursive --log-file debug.log --log-level DEBUG --output-dir ./output

      # Useful for batch processing
      all2md ./archive --recursive --log-file archive_conversion.log --skip-errors --output-dir ./converted

   .. note::

      Log files capture all log messages regardless of console output settings. This is useful for post-processing analysis and debugging batch conversions.

``--trace``
   Enable trace mode with very verbose output including per-stage timing information. This is equivalent to ``--log-level DEBUG`` with additional timing instrumentation.

   .. code-block:: bash

      # Trace mode for performance analysis
      all2md document.pdf --trace

      # Trace with log file for detailed analysis
      all2md complex_document.pdf --trace --log-file trace.log

      # Trace batch processing
      all2md *.pdf --trace --log-file batch_trace.log --output-dir ./converted

   **Trace Output Includes:**

   * Detailed parsing timing for each stage
   * AST transformation timing
   * Rendering performance metrics
   * Timestamp-formatted log messages

   .. note::

      Trace mode is primarily useful for performance debugging and optimization. For normal operation, use ``--log-level DEBUG`` or ``--verbose`` instead.

``--strict-args``
   Treat unknown command-line arguments as fatal errors. By default the CLI logs a warning and continues; enabling
   ``--strict-args`` is useful in CI pipelines and scripts where typos must halt execution.

   .. code-block:: bash

      # Fail fast if any flag is misspelled
      all2md report.pdf --strict-args --pdf-pages "1-3"

   Configuration files may still contain extra keys; these produce validation warnings rather than aborting.

``--about``
   Display comprehensive system information including version, dependencies, and format availability.

   .. code-block:: bash

      # Show system information
      all2md --about

   **Output Includes:**

   * all2md version and Python version
   * System platform and architecture
   * Installed dependencies with versions
   * Available format converters and their status
   * Missing optional dependencies

   .. note::

      Use ``--about`` when reporting bugs or troubleshooting dependency issues. It provides a complete snapshot of your environment configuration.

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
   Save current CLI arguments to a configuration file.

   .. code-block:: bash

      # Save current settings to JSON
      all2md document.pdf --attachment-mode download --save-config my-config.json

      # Save and reuse
      all2md document.pdf --preset quality --save-config quality-config.json
      all2md other-doc.pdf --config quality-config.json

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

      For specifying multiple hosts in a list, you can use a comma-separated value as shown below for a single invocation. For more complex list specifications, use a configuration file with the ``--config`` flag.

   .. code-block:: bash

      # Only allow specific hosts (single host)
      all2md webpage.html --html-network-allow-remote-fetch --html-network-allowed-hosts "example.com"

      # Multiple hosts via config file (recommended for multiple values)
      # In config.json: {"html.network.allowed_hosts": ["example.com", "cdn.example.com"]}
      all2md webpage.html --html-network-allow-remote-fetch --config config.json

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

OpenDocument Text (ODT) Options
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``--odt-no-preserve-tables``
   Disable table preservation when parsing ODT documents.

   **Default:** Tables are preserved.

   .. code-block:: bash

      # Convert ODT tables to simple paragraphs
      all2md document.odt --odt-no-preserve-tables

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

Format-Specific Options in Batch Mode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When processing multiple formats in a single batch, you can use format-specific flags to override global settings. This is particularly useful when different formats require different attachment handling strategies.

**Global + Format-Specific Overrides:**

.. code-block:: bash

   # Skip attachments by default, but download from PDFs
   all2md *.* --attachment-mode skip \
       --pdf-attachment-mode download \
       --pdf-attachment-output-dir ./pdf_images \
       --output-dir ./converted

   # Use alt-text globally, but embed base64 for presentations
   all2md docs/* reports/*.pdf slides/*.pptx \
       --attachment-mode alt_text \
       --pptx-attachment-mode base64 \
       --output-dir ./output

   # Different attachment directories per format
   all2md mixed_content/* \
       --attachment-mode download \
       --pdf-attachment-output-dir ./assets/pdf \
       --docx-attachment-output-dir ./assets/word \
       --html-attachment-output-dir ./assets/web \
       --output-dir ./converted

**How It Works:**

1. Global flags (``--attachment-mode``, ``--attachment-output-dir``, etc.) apply to ALL formats
2. Format-specific flags (``--pdf-attachment-mode``, ``--docx-attachment-mode``, etc.) override global settings for that format
3. Format-specific flags always take precedence over global flags

**Use Cases:**

* **Security policies** - Strict defaults with exceptions for trusted formats
* **Performance optimization** - Fast modes for text formats, thorough modes for complex documents
* **Mixed format directories** - Different strategies per format type
* **Selective processing** - Skip attachments except where needed

For a complete list of format-specific flags, see :doc:`attachments` or run ``all2md help <format>``.

Merge from List
~~~~~~~~~~~~~~~

Create structured multi-document outputs by merging files listed in a TSV file. This feature is ideal for building complex documents like books, manuals, or reports from individual section files.

``--merge-from-list``
   Merge files from a TSV list file with optional section titles.

   **List File Format:**

   The list file uses a simple tab-separated format:

   .. code-block:: text

      # Comments start with #
      path/to/file1.md
      path/to/file2.pdf<TAB>Section Title
      path/to/file3.docx<TAB>Another Section

   * Lines starting with ``#`` are comments and ignored
   * Blank lines are ignored
   * File paths are resolved relative to the list file directory
   * Optional section titles follow a tab character
   * Files can be any supported format (PDF, DOCX, Markdown, etc.)

   .. code-block:: bash

      # Basic merge from list
      all2md --merge-from-list chapters.txt --out book.md

      # Merge to stdout
      all2md --merge-from-list sections.txt

``--generate-toc``
   Generate a table of contents when using ``--merge-from-list``.

   .. code-block:: bash

      # Add table of contents to merged document
      all2md --merge-from-list chapters.txt --generate-toc --out book.md

``--toc-title``
   Set the title for the generated table of contents.

   **Default:** ``Table of Contents``

   .. code-block:: bash

      # Custom TOC title
      all2md --merge-from-list chapters.txt --generate-toc --toc-title "Contents" --out book.md

``--toc-depth``
   Maximum heading level to include in the table of contents (1-6).

   **Default:** 3

   .. code-block:: bash

      # Include only level 1 and 2 headings in TOC
      all2md --merge-from-list chapters.txt --generate-toc --toc-depth 2 --out book.md

``--toc-position``
   Position of the table of contents in the output.

   **Choices:** ``top`` (default), ``bottom``

   .. code-block:: bash

      # Place TOC at the end of document
      all2md --merge-from-list chapters.txt --generate-toc --toc-position bottom --out book.md

``--list-separator``
   Separator character for the list file.

   **Default:** Tab character (``\t``)

   .. code-block:: bash

      # Use comma separator instead of tab
      all2md --merge-from-list chapters.csv --list-separator "," --out book.md

``--no-section-titles``
   Disable automatic section title headers when merging.

   .. code-block:: bash

      # Merge without adding section headers
      all2md --merge-from-list chapters.txt --no-section-titles --out book.md

**Complete Example:**

Create a list file ``book_chapters.txt``:

.. code-block:: text

   # Book Structure
   frontmatter/preface.md	Preface
   chapters/introduction.pdf	Chapter 1: Introduction
   chapters/methodology.docx	Chapter 2: Methodology
   chapters/results.pdf	Chapter 3: Results
   chapters/conclusion.md	Chapter 4: Conclusion
   # Appendices
   appendix/references.md	References

Merge with table of contents:

.. code-block:: bash

   # Create complete book with TOC
   all2md --merge-from-list book_chapters.txt \
       --generate-toc \
       --toc-title "Book Contents" \
       --toc-depth 2 \
       --out complete_book.md

**Use Cases:**

* **Multi-chapter books:** Combine individual chapter files with automatic TOC generation
* **Technical documentation:** Merge API docs, guides, and tutorials into a single document
* **Reports:** Assemble executive summaries, analyses, and appendices
* **Project documentation:** Combine README, architecture, and design docs
* **Course materials:** Merge lecture notes, assignments, and resources

**Integration with Transforms:**

The merge-from-list feature works seamlessly with the transform system. Use ``--transform`` to apply custom AST transformations to the merged document:

.. code-block:: bash

   # Merge and apply custom transforms
   all2md --merge-from-list chapters.txt \
       --generate-toc \
       --transform "HeadingOffsetTransform offset=1" \
       --out book.md

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
      all2md other_document.pdf --config my_settings.json

``--dry-run``
   Preview what would be converted without actually processing files.

   .. code-block:: bash

      # See what files would be processed
      all2md ./documents --recursive --dry-run

      # Test exclusion patterns
      all2md ./docs --recursive --exclude "*.draft.*" --dry-run

Output Packaging
~~~~~~~~~~~~~~~~

``--zip``
   Create a ZIP archive of the conversion output. Can be used with or without a custom path.

   .. code-block:: bash

      # Create ZIP archive with automatic naming
      all2md *.pdf --output-dir ./converted --zip

      # Create ZIP with custom path
      all2md *.pdf --output-dir ./converted --zip ./archive.zip

      # Combine with asset organization
      all2md *.docx --output-dir ./output --zip --assets-layout flat

   .. note::

      The ZIP archive includes all converted markdown files and their associated assets. When used without a path argument, the ZIP file is named after the output directory (e.g., ``converted.zip``).

``--assets-layout``
   Organize asset files (images, attachments) using different layout strategies.

   **Choices:**

   * ``flat`` - All assets in a single ``assets/`` directory (default)
   * ``by-stem`` - Assets organized by document name: ``assets/{document}/``
   * ``structured`` - Preserves original directory structure

   **Default:** ``flat``

   .. code-block:: bash

      # Flat layout - all assets in assets/
      all2md *.pdf --output-dir ./output --assets-layout flat

      # By-stem layout - assets/{doc_name}/
      all2md report1.pdf report2.pdf --output-dir ./output --assets-layout by-stem

      # Structured layout - preserves directory structure
      all2md ./docs --recursive --output-dir ./output --assets-layout structured

   .. note::

      Asset organization automatically updates markdown links to point to the new locations. This is particularly useful when creating shareable documentation bundles.

Watch Mode
~~~~~~~~~~

``--watch``
   Monitor files or directories for changes and automatically reconvert when changes are detected. Requires the ``watchdog`` library (install with ``pip install all2md[cli_extras]``).

   .. code-block:: bash

      # Watch a single file
      all2md document.txt --watch --output-dir ./output

      # Watch a directory
      all2md ./docs --watch --recursive --output-dir ./output

      # Watch with custom debounce
      all2md ./docs --watch --watch-debounce 2.0 --output-dir ./output

      # Watch with file exclusions
      all2md ./docs --watch --recursive --exclude "*.tmp" --exclude "draft_*" --output-dir ./output

   .. note::

      * Watch mode runs continuously until interrupted with ``Ctrl+C``
      * Changes are debounced to prevent duplicate processing of rapid changes
      * The ``--output-dir`` flag is required for watch mode
      * Files matching ``--exclude`` patterns are ignored

``--watch-debounce``
   Set the debounce delay in seconds for watch mode (prevents duplicate processing of rapid changes).

   **Default:** ``1.0``

   .. code-block:: bash

      # Short debounce for fast iteration
      all2md ./src --watch --watch-debounce 0.5 --output-dir ./docs

      # Longer debounce for slower systems
      all2md ./content --watch --watch-debounce 2.0 --output-dir ./output

   **Use Cases:**

   * **Documentation Development:** Automatically regenerate docs as source files change
   * **Content Authoring:** Live preview of markdown output while editing
   * **Integration Testing:** Auto-convert test fixtures during development

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

Install Missing Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To install missing dependencies, use pip with the appropriate extra:

.. code-block:: bash

   # Install PDF dependencies
   pip install all2md[pdf]

   # Install PowerPoint dependencies
   pip install all2md[pptx]

   # Install all optional dependencies
   pip install all2md[all]

**Available dependency groups:**
   * ``[pdf]`` - PyMuPDF for PDF processing
   * ``[docx]`` - python-docx for Word documents
   * ``[pptx]`` - python-pptx for PowerPoint
   * ``[html]`` - BeautifulSoup4, httpx, and readability-lxml for HTML parsing and article extraction
   * ``[epub]`` - ebooklib for EPUB e-books
   * ``[rtf]`` - pyth3 for Rich Text Format
   * ``[odf]`` - odfpy for OpenDocument formats
   * ``[xlsx]`` - openpyxl for Excel files
   * ``[all]`` - All optional dependencies

See :doc:`installation` for more details.

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
   html           .html, .htm            BeautifulSoup4, readability-lxml  ✓ Available
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

Using Presets Effectively
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Scenario 1: Fast batch conversion of many PDFs
   # Use the 'fast' preset to skip expensive operations
   all2md *.pdf --preset fast --output-dir ./converted --parallel 8

   # Scenario 2: Archival of important documents
   # Use 'archival' preset for self-contained files with base64 images
   all2md important_*.pdf --preset archival --out ./archive/

   # Scenario 3: Creating technical documentation
   # Use 'documentation' preset with custom notebook truncation
   all2md *.ipynb --preset documentation --ipynb-truncate-long-outputs 30

   # Scenario 4: Quality conversion with preset overrides
   # Start with quality, but skip attachments for this specific use case
   all2md research.pdf --preset quality --attachment-mode skip

   # Scenario 5: Combining preset with config file
   # Use preset as base, config file for project settings, CLI for one-off changes
   all2md report.pdf --preset quality --config .all2md.toml --pdf-pages "1-5"

**When to Use Each Preset:**

For **fast batch processing** of many documents where you only need text:

.. code-block:: bash

   all2md documents/*.pdf --preset fast --output-dir ./text-only --parallel

For **high-quality conversions** where accuracy matters most:

.. code-block:: bash

   all2md important.pdf --preset quality --out important.md

For **archival purposes** where files must be completely self-contained:

.. code-block:: bash

   all2md archive/*.* --preset archival --output-dir ./archive

For **documentation projects** with notebooks and technical content:

.. code-block:: bash

   all2md docs/*.ipynb --preset documentation --output-dir ./docs

Configuration File Usage
~~~~~~~~~~~~~~~~~~~~~~~~

Create a configuration file ``.all2md.toml`` (preferred):

.. code-block:: toml

   # all2md configuration
   attachment_mode = "download"
   attachment_output_dir = "./attachments"
   log_level = "INFO"

   [markdown]
   emphasis_symbol = "_"
   bullet_symbols = "•◦▪"

   [pdf]
   detect_columns = true

   [html]
   strip_dangerous_elements = true

Or use JSON format:

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

   # Auto-discovery (place .all2md.toml in current directory)
   all2md document.pdf

   # Explicit config file
   all2md document.pdf --config custom-config.toml

   # Override specific options
   all2md document.pdf --config config.json --attachment-mode base64

   # Combine with presets
   all2md document.pdf --preset fast --config overrides.toml

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

The CLI provides granular exit codes for automation and scripting:

* ``0`` - Success
* ``1`` - General/unexpected error
* ``2`` - Missing dependency error
* ``3`` - Validation error (invalid arguments)
* ``4`` - File error (not found, permission denied, malformed)
* ``5`` - Format error (unsupported/unknown format)
* ``6`` - Parsing error (failed to parse document)
* ``7`` - Rendering error (failed to generate output)
* ``8`` - Security error (SSRF, zip bombs, etc.)
* ``9`` - Password-protected file

See ``EXIT_CODES.md`` in the repository for detailed documentation and shell scripting examples.

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

``ALL2MD_CONFIG``
   Path to a configuration file (JSON or TOML) containing conversion options. This is equivalent to using ``--config`` on the command line. The CLI argument ``--config`` takes precedence over this environment variable if both are specified.

   .. code-block:: bash

      # Set default config file location
      export ALL2MD_CONFIG="$HOME/.config/all2md/default.toml"

      # Now all commands use this config by default
      all2md document.pdf

      # Override with explicit flag
      all2md document.pdf --config ./project-config.json

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
Enhanced Help System
--------------------

The CLI exposes a tiered help system that mirrors the dynamic options generated from dataclasses:

* ``all2md --help`` or ``all2md help`` renders a concise overview with the most important flags.
* ``all2md help full`` lists every parser and renderer option, grouped by format.
* ``all2md help <format>`` (for example ``pdf`` or ``docx``) shows only the options relevant to that format. Renderer options appear alongside parser options so you can see both halves of the pipeline in one view.
* ``--rich`` is available on the help subcommand to colourise headings, flags, defaults, and metadata when the `rich` library is installed.

The same formatting and grouping logic is used by the generated CLI output and this reference documentation, ensuring that new options surface automatically as dataclass metadata evolves.
