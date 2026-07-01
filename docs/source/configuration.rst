Configuration Files
===================

all2md supports configuration files for persistent settings, enabling you to avoid repeating CLI options and share configurations across projects. This guide covers all configuration file formats, auto-discovery behavior, and configuration priority.

.. contents::
   :local:
   :depth: 2

Overview
--------

Configuration files allow you to:

* Set default values for CLI options without typing them every time
* Share consistent settings across team members via version control
* Define format-specific options in a structured way
* Integrate with Python project tooling via ``pyproject.toml``

**Quick Start:**

.. code-block:: bash

   # Generate a configuration template
   all2md config generate --out .all2md.toml

   # Edit the file with your preferences, then use it
   all2md document.pdf  # Auto-discovers .all2md.toml

Supported Formats
-----------------

all2md supports four configuration file formats:

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Format
     - Filename
     - Notes
   * - TOML
     - ``.all2md.toml``
     - Recommended. Supports comments, human-readable.
   * - YAML
     - ``.all2md.yaml``, ``.all2md.yml``
     - Alternative to TOML with similar readability.
   * - JSON
     - ``.all2md.json``
     - Machine-readable, no comments.
   * - pyproject.toml
     - ``pyproject.toml``
     - Python projects. Uses ``[tool.all2md]`` section.

TOML Configuration (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

TOML is the recommended format because it supports comments and is easy to read and edit (and who doesn't love a guy named Tom?)

.. code-block:: toml

   # .all2md.toml - all2md configuration file

   # Global options (apply to all conversions)
   attachment_mode = "save"
   attachment_output_dir = "./images"

   # Markdown output settings
   [markdown]
   flavor = "gfm"
   emphasis_symbol = "*"
   bullet_symbols = "-"
   use_hash_headings = true

   # PDF-specific options
   [pdf]
   detect_columns = true
   detect_tables = true
   pages = [1, 2, 3, 4, 5]  # First 5 pages only

   # HTML-specific options
   [html]
   strip_dangerous_elements = true
   preserve_whitespace = false

   # HTML network settings (nested section)
   [html.network]
   allow_remote_fetch = false
   require_https = true

   # DOCX-specific options
   [docx]
   include_headers_footers = true
   extract_comments = true

YAML Configuration
~~~~~~~~~~~~~~~~~~

YAML provides similar readability to TOML with a different syntax style.

.. code-block:: yaml

   # .all2md.yaml - all2md configuration file

   # Global options
   attachment_mode: save
   attachment_output_dir: ./images

   # Markdown output settings
   markdown:
     flavor: gfm
     emphasis_symbol: "*"
     bullet_symbols: "-"

   # PDF-specific options
   pdf:
     detect_columns: true
     detect_tables: true
     pages: [1, 2, 3, 4, 5]

   # HTML-specific options
   html:
     strip_dangerous_elements: true
     network:
       allow_remote_fetch: false
       require_https: true

JSON Configuration
~~~~~~~~~~~~~~~~~~

JSON is useful for programmatic generation but doesn't support comments.

.. code-block:: json

   {
     "attachment_mode": "save",
     "attachment_output_dir": "./images",
     "markdown": {
       "flavor": "gfm",
       "emphasis_symbol": "*"
     },
     "pdf": {
       "detect_columns": true,
       "pages": [1, 2, 3, 4, 5]
     },
     "html": {
       "strip_dangerous_elements": true,
       "network": {
         "allow_remote_fetch": false
       }
     }
   }

pyproject.toml Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~

For Python projects, you can add all2md configuration to your existing ``pyproject.toml`` under the ``[tool.all2md]`` section:

.. code-block:: toml

   # pyproject.toml

   [project]
   name = "my-project"
   version = "1.0.0"

   [tool.all2md]
   attachment_mode = "skip"

   [tool.all2md.pdf]
   detect_columns = true
   detect_tables = true

   [tool.all2md.markdown]
   flavor = "gfm"

   [tool.all2md.html]
   strip_dangerous_elements = true

   [tool.all2md.html.network]
   allow_remote_fetch = false

This integrates seamlessly with Python development workflows and keeps project configuration centralized.

Auto-Discovery
--------------

all2md automatically discovers configuration files without requiring explicit paths. This enables project-specific configurations that "just work" when you run commands from within a project directory.

Search Order
~~~~~~~~~~~~

When no explicit ``--config`` flag is provided, all2md searches for configuration files in this order:

1. **Parent directory walk** - Starting from the current working directory, searches upward through each parent directory to the filesystem root:

   * ``.all2md.toml`` (highest priority)
   * ``.all2md.yaml``
   * ``.all2md.yml``
   * ``.all2md.json``
   * ``pyproject.toml`` (only if it contains a ``[tool.all2md]`` section)

2. **Home directory fallback** - If no config found in the directory tree:

   * ``~/.all2md.toml``
   * ``~/.all2md.yaml``
   * ``~/.all2md.yml``
   * ``~/.all2md.json``

The search stops at the **first** configuration file found.

Example Directory Structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Consider this project structure:

.. code-block:: text

   /home/user/
   ├── .all2md.toml           # User-level defaults
   └── projects/
       └── my-project/
           ├── .all2md.toml   # Project-specific config
           ├── pyproject.toml # Also has [tool.all2md] section
           └── docs/
               └── manual.pdf

* Running ``all2md docs/manual.pdf`` from ``/home/user/projects/my-project/`` uses ``my-project/.all2md.toml``
* Running ``all2md docs/manual.pdf`` from ``/home/user/projects/my-project/docs/`` also uses ``my-project/.all2md.toml`` (found via parent search)
* Running ``all2md some-doc.pdf`` from ``/home/user/other-folder/`` uses ``~/.all2md.toml`` (home directory fallback)

Disabling Auto-Discovery
~~~~~~~~~~~~~~~~~~~~~~~~

To completely disable configuration file loading (auto-discovery, ``ALL2MD_CONFIG`` env var, and ``--config`` flag), use the ``--no-config`` flag:

.. code-block:: bash

   # Disable all configuration file loading
   all2md document.pdf --no-config

   # --no-config also ignores the ALL2MD_CONFIG env var
   ALL2MD_CONFIG=/path/to/config.toml all2md document.pdf --no-config

   # --no-config takes precedence over --config
   all2md document.pdf --no-config --config some-config.toml

This is useful when you want to:

* Ensure reproducible conversions without any config influence
* Debug configuration issues by starting with defaults
* Run one-off conversions that should ignore project settings

Note that CLI arguments still work normally with ``--no-config`` - only configuration files are disabled.

Configuration Priority
----------------------

When multiple configuration sources exist, they are merged with the following priority (highest to lowest):

1. **CLI arguments** - Explicitly provided command-line flags always win
2. **Presets** - The ``--preset`` flag (e.g., ``--preset quality``) and the
   security presets (``--safe-mode``, ``--paranoid-mode``, ``--strict-html-sanitize``)
3. **Configuration file** - a single file resolved in this order: the
   ``--config`` flag, else the ``ALL2MD_CONFIG`` environment variable, else an
   auto-discovered ``.all2md.toml``/``.all2md.json`` (or ``[tool.all2md]`` in
   ``pyproject.toml``)
4. **Built-in defaults** - including any default supplied by a per-option
   ``ALL2MD_<OPTION>`` environment variable (these set the default for a flag you
   do not pass explicitly; see :doc:`environment_variables`)

.. note::

   ``ALL2MD_CONFIG`` (which *points at* a config file) is distinct from the
   per-option ``ALL2MD_<OPTION>`` variables (which set individual option
   defaults). The two precedence pages — this one and
   :doc:`environment_variables` — describe the same ordering from opposite
   ends (highest-first here, lowest-first there).

**Example:**

.. code-block:: bash

   # Scenario: Multiple configs exist
   # ~/.all2md.toml contains: attachment_mode = "skip"
   # ./project/.all2md.toml contains: attachment_mode = "base64"
   # ALL2MD_CONFIG points to: /etc/all2md.toml with attachment_mode = "save"

   # From ./project directory:
   all2md document.pdf
   # Uses: attachment_mode = "base64" (auto-discovered ./project/.all2md.toml)

   # With explicit config:
   all2md document.pdf --config /etc/all2md.toml
   # Uses: attachment_mode = "save" (explicit --config wins over auto-discovery)

   # With CLI override:
   all2md document.pdf --attachment-mode base64
   # Uses: attachment_mode = "base64" (CLI always wins)

Deep Merging
~~~~~~~~~~~~

Nested configuration sections are merged recursively, not replaced entirely:

.. code-block:: toml

   # Auto-discovered .all2md.toml
   [html]
   strip_dangerous_elements = true

   [html.network]
   allow_remote_fetch = false
   timeout = 30

.. code-block:: bash

   # CLI override for just one nested option
   all2md page.html --html-network-timeout 60

   # Result: html.strip_dangerous_elements = true (from file)
   #         html.network.allow_remote_fetch = false (from file)
   #         html.network.timeout = 60 (from CLI)

Configuration Options Reference
-------------------------------

Global Options
~~~~~~~~~~~~~~

These options apply to all conversions regardless of input format:

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Option
     - Type
     - Description
   * - ``attachment_mode``
     - string
     - How to handle images/attachments: ``skip``, ``alt_text``, ``base64``, ``save``
   * - ``attachment_output_dir``
     - string
     - Directory for saved attachments (when mode is ``save``)

Markdown Options
~~~~~~~~~~~~~~~~

Control the Markdown output format under the ``[markdown]`` section:

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Option
     - Type
     - Description
   * - ``flavor``
     - string
     - Markdown dialect: ``gfm``, ``commonmark``, ``pandoc``, etc.
   * - ``emphasis_symbol``
     - string
     - Character for emphasis: ``*`` or ``_``
   * - ``bullet_symbols``
     - string
     - Characters to cycle through for nested bullet lists (default ``*-+``)
   * - ``use_hash_headings``
     - bool
     - Use ``#`` ATX headings (``true``) instead of Setext underline headings (``false``)

Terminal (Rich) Styling
~~~~~~~~~~~~~~~~~~~~~~~~~

When you render to the terminal with ``--rich`` (requires ``pip install
all2md[rich]``), the colors used for Markdown elements — headings, links, block
quotes, list bullets, inline code, and so on — can be customized under a
``[rich]`` table. Each key is a `Rich style name
<https://rich.readthedocs.io/en/stable/style.html>`_ and each value is a Rich
style string (e.g. ``"bold red"``, ``"italic green"``, ``"underline blue"``).

Bare Markdown element names are accepted as a convenience and are automatically
prefixed with ``markdown.``; fully-qualified names (anything containing a dot)
are passed through verbatim, so you can also override non-Markdown Rich styles.

.. code-block:: toml

   [rich]
   h1 = "bold magenta"            # same as markdown.h1
   h2 = "bold cyan"
   block_quote = "italic green"
   "item.bullet" = "yellow"       # markdown.item.bullet
   link = "underline blue"
   code = "bold bright_white on grey23"

Notes:

* The ``[rich]`` table only affects terminal rendering; it is ignored for file
  output and never changes the converted document content.
* Invalid style strings (or non-string values) are skipped with a warning so a
  single bad entry never aborts the run; the affected element keeps Rich's
  default styling.
* Syntax-highlighting themes for code blocks are controlled separately via the
  ``--rich-code-theme`` / ``--rich-inline-code-theme`` flags (Pygments themes).

Run ``all2md config generate`` to emit a commented ``[rich]`` example alongside
the rest of your configuration template.

Format-Specific Options
~~~~~~~~~~~~~~~~~~~~~~~

Each input format has its own configuration section. See :doc:`options` for the complete reference. Common sections include:

* ``[pdf]`` - PDF conversion options (pages, column detection, table detection)
* ``[html]`` - HTML conversion options (sanitization, network settings)
* ``[docx]`` - Word document options (headers/footers, comments)
* ``[pptx]`` - PowerPoint options (slide handling)
* ``[eml]`` - Email options (chain detection, attachment handling)

Subcommand Options
~~~~~~~~~~~~~~~~~~

Besides the main ``all2md <file>`` converter, several subcommands read their own
configuration section, so you can set their flags once instead of typing them
on every invocation. Each command reads a table named after the command:

.. list-table::
   :header-rows: 1
   :widths: 25 22 53

   * - Command
     - Config section
     - Example keys
   * - ``all2md view``
     - ``[view]``
     - ``no_wait``, ``toc``, ``dark``, ``theme``, ``keep``
   * - ``all2md serve``
     - ``[serve]``
     - ``port``, ``host``, ``theme``, ``no_cache``, ``poll_interval``
   * - ``all2md diff``
     - ``[diff]``
     - ``format``, ``granularity``, ``context``, ``color``
   * - ``all2md edit``
     - ``[edit]``
     - ``port``, ``host``, ``no_browser``, ``default_format``
   * - ``all2md arxiv``
     - ``[arxiv]``
     - ``document_class``, ``figure_format``, ``output_format``, ``bib_style``
   * - ``all2md generate-site``
     - ``[generate-site]``
     - ``generator``, ``output_dir``, ``scaffold``, ``content_subdir``

Example:

.. code-block:: toml

   # .all2md.toml

   [view]
   no_wait = true        # don't wait for Enter before cleaning up the temp file
   theme = "sidebar"

   [serve]
   port = 9123
   host = "0.0.0.0"

   [diff]
   granularity = "word"
   format = "json"

A few things to know:

* **Keys are the option name**, with hyphens or underscores accepted (``no-wait``
  and ``no_wait`` are equivalent). For the handful of flags whose stored name
  differs from the flag spelling — notably ``diff``'s ``--no-context`` — use the
  underlying field name (``show_context = false``).
* **Precedence is** built-in default < config section < explicit CLI flag, so a
  flag on the command line always wins.
* **Only the matching section is read.** Subcommand sections never affect the
  main converter, and top-level or format options never leak into a subcommand.
  (A top-level ``format`` — the converter's *input* format — is unrelated to
  ``[diff]``'s ``format``.)
* **Config can supply required options.** For example,
  ``[arxiv]`` with ``output = "paper.tar.gz"`` lets ``all2md arxiv paper.tex``
  run without ``-o`` on the command line.
* Every one of these commands also accepts ``--config <path>`` and
  ``--no-config``, mirroring the main converter.

``all2md config generate`` emits a template section for each of these commands,
so generating a config and editing it is the quickest way to see every
available key and its default.

.. _lint-configuration:

Lint Options
~~~~~~~~~~~~

Configure the ``all2md lint`` subcommand under the ``[lint]`` section of
``.all2md.toml`` (or the equivalent ``[tool.all2md.lint]`` block in
``pyproject.toml``). See :doc:`cli` for the full list of built-in rules and
command-line usage.

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Option
     - Type
     - Description
   * - ``disable``
     - list of strings
     - Rule codes to skip entirely. Example: ``["TYP003", "HDG004"]``.
   * - ``enable``
     - list of strings
     - Whitelist of rule codes to run. When set, every other rule is skipped.
   * - ``severity_threshold``
     - string
     - Minimum severity to report: ``info`` (default), ``warning``, or ``error``.
       Filters both the output and the process exit code.
   * - ``severity``
     - table
     - Per-rule severity overrides. Keys are rule codes, values are
       ``info``/``warning``/``error``. Overrides each rule's built-in default.
   * - ``rules``
     - table of tables
     - Per-rule option dictionaries, keyed by rule code. Forwarded to the rule
       via the ``LintContext.config`` parameter. See the per-rule options
       table below.

Per-Rule Options
^^^^^^^^^^^^^^^^

A handful of rules read options from ``[tool.all2md.lint.rules.<CODE>]``.
Rules not listed here ignore the ``rules`` table.

.. list-table::
   :header-rows: 1
   :widths: 15 25 15 45

   * - Rule
     - Option
     - Default
     - Meaning
   * - ``HDG002``
     - ``max_length``
     - 80
     - Maximum heading length in characters.
   * - ``HDG006``
     - ``max_words``
     - 12
     - Heading word-count threshold above which a sentence-ending heading is flagged.
   * - ``STR006``
     - ``min_words``
     - 10
     - Minimum word count for a section before it's flagged as too short.
   * - ``STR008``
     - ``max_depth``
     - 4
     - Maximum block-level nesting depth (blockquotes / list items).
   * - ``LST004``
     - ``max_depth``
     - 4
     - Maximum list-nesting depth.
   * - ``TBL006``
     - ``max_columns``
     - 12
     - Maximum table column count.
   * - ``IMG004``
     - ``max_bytes``
     - 1048576
     - Maximum decoded size of a base64-inlined image.

Example ``pyproject.toml`` block:

.. code-block:: toml

   [tool.all2md.lint]
   disable = ["TYP003", "HDG004"]
   severity_threshold = "warning"

   [tool.all2md.lint.severity]
   STR005 = "error"
   LNK003 = "warning"

   [tool.all2md.lint.rules.HDG002]
   max_length = 100

   [tool.all2md.lint.rules.STR006]
   min_words = 25

   [tool.all2md.lint.rules.IMG004]
   max_bytes = 524288  # 512 KiB

Equivalent ``.all2md.toml`` block (no ``tool.all2md`` prefix):

.. code-block:: toml

   [lint]
   disable = ["TYP003", "HDG004"]
   severity_threshold = "warning"

   [lint.severity]
   STR005 = "error"
   LNK003 = "warning"

   [lint.rules.HDG002]
   max_length = 100

Command-line flags layer on top of the config file: ``--rule``/``--disable``
extend the whitelist/blacklist, ``--severity`` overrides
``severity_threshold``, and ``--fix`` applies safe auto-fixes in place
(``--dry-run`` previews without writing).

Managing Configuration
----------------------

Generating Configuration
~~~~~~~~~~~~~~~~~~~~~~~~

Create a template configuration file with all available options:

.. code-block:: bash

   # Generate TOML template (recommended)
   all2md config generate --out .all2md.toml

   # Generate YAML template
   all2md config generate --format yaml --out .all2md.yaml

   # Generate JSON template
   all2md config generate --format json --out .all2md.json

   # Print to stdout for inspection
   all2md config generate

The generated file includes comments explaining each option and shows default values.

Viewing Effective Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See the merged configuration from all sources:

.. code-block:: bash

   # Show current effective configuration
   all2md config show

   # Show as JSON
   all2md config show --format json

   # Show without source information
   all2md config show --no-source

Example output:

.. code-block:: text

   Configuration Sources (in priority order):
   ------------------------------------------------------------
   1. ALL2MD_CONFIG env var: (not set)
   2. /home/user/project/.all2md.toml [FOUND]
   3. /home/user/.all2md.toml [-]

   Effective Configuration:
   ============================================================
   attachment_mode = "save"
   attachment_output_dir = "./images"

   [pdf]
   detect_columns = true

Validating Configuration
~~~~~~~~~~~~~~~~~~~~~~~~

Check that a configuration file is syntactically correct:

.. code-block:: bash

   # Validate a configuration file
   all2md config validate .all2md.toml
   all2md config validate config.json

Example output:

.. code-block:: text

   Configuration file is valid: .all2md.toml
   Format: .toml
   Keys found: attachment_mode, pdf, html, markdown

Saving CLI Arguments
~~~~~~~~~~~~~~~~~~~~

Save your current CLI arguments to a configuration file for reuse:

.. code-block:: bash

   # Save current settings (--save-config always writes JSON)
   all2md document.pdf --attachment-mode save --pdf-pages "1-10" \
       --save-config my-settings.json

   # Reuse saved settings
   all2md other-document.pdf --config my-settings.json

Common Use Cases
----------------

Project-Specific Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Place a ``.all2md.toml`` in your project root for settings specific to that project:

.. code-block:: toml

   # /my-project/.all2md.toml

   # Skip images for faster LLM processing
   attachment_mode = "skip"

   [pdf]
   # Only process first 50 pages of large PDFs
   pages = "1-50"
   detect_tables = true

   [markdown]
   flavor = "gfm"

Team members cloning the repo automatically get these settings.

User-Level Defaults
~~~~~~~~~~~~~~~~~~~

Set personal preferences in your home directory:

.. code-block:: toml

   # ~/.all2md.toml

   # Personal preference: always use rich output
   rich = true

   # Default attachment handling
   attachment_mode = "save"
   attachment_output_dir = "~/Documents/all2md-attachments"

   [markdown]
   emphasis_symbol = "_"

CI/CD Pipeline Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the ``ALL2MD_CONFIG`` environment variable in CI/CD:

.. code-block:: yaml

   # .github/workflows/convert.yml
   jobs:
     convert:
       runs-on: ubuntu-latest
       env:
         ALL2MD_CONFIG: ./ci-config.toml
       steps:
         - uses: actions/checkout@v4
         - run: pip install all2md
         - run: all2md docs/*.pdf --output-dir converted/

With ``ci-config.toml``:

.. code-block:: toml

   # ci-config.toml - CI/CD optimized settings
   attachment_mode = "skip"

   [pdf]
   detect_columns = false  # Faster processing

   [html]
   strip_dangerous_elements = true

   [html.network]
   allow_remote_fetch = false  # Security

Docker Configuration
~~~~~~~~~~~~~~~~~~~~

Mount configuration into containers:

.. code-block:: bash

   docker run -v $(pwd)/config.toml:/app/config.toml \
       -e ALL2MD_CONFIG=/app/config.toml \
       all2md-image all2md /data/document.pdf

Or use ``pyproject.toml`` for Python-based containers:

.. code-block:: dockerfile

   FROM python:3.12-slim
   WORKDIR /app
   COPY pyproject.toml .
   RUN pip install all2md
   # Config auto-discovered from pyproject.toml [tool.all2md] section

Troubleshooting
---------------

Configuration Not Being Applied
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **Check discovery**: Run ``all2md config show`` to see which config file is being used
2. **Verify syntax**: Run ``all2md config validate <file>`` to check for errors
3. **Check priority**: CLI arguments override config files; ensure no conflicting flags
4. **Check location**: Auto-discovery walks up from the current directory, not the input file's directory

Invalid Configuration Errors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   Error: Invalid TOML in config file: Expected '=' after key at line 5

Fix syntax errors in your configuration file. Use ``all2md config validate`` to check.

pyproject.toml Not Being Detected
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ensure your ``pyproject.toml`` has a ``[tool.all2md]`` section:

.. code-block:: toml

   [tool.all2md]
   # At least one option must be present
   attachment_mode = "skip"

An empty ``[tool.all2md]`` section is not detected.

See Also
--------

* :doc:`cli` - Full CLI reference including ``config`` subcommands
* :doc:`environment_variables` - Environment variable configuration
* :doc:`options` - Complete options reference for all formats
* :doc:`quickstart` - Getting started guide
