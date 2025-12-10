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
   strong_symbol = "**"
   bullet_list_marker = "-"

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
     strong_symbol: "**"

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

1. **CLI arguments** - Command-line flags always win
2. **Preset** - The ``--preset`` flag (e.g., ``--preset quality``)
3. **Explicit config** - The ``--config`` flag
4. **Environment variable** - ``ALL2MD_CONFIG`` environment variable
5. **Auto-discovered config** - ``.all2md.toml`` etc. found via directory search
6. **Default values** - Built-in defaults

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
   all2md document.pdf --attachment-mode inline
   # Uses: attachment_mode = "inline" (CLI always wins)

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
   * - ``strong_symbol``
     - string
     - Characters for strong: ``**`` or ``__``
   * - ``bullet_list_marker``
     - string
     - Bullet character: ``-``, ``*``, or ``+``

Format-Specific Options
~~~~~~~~~~~~~~~~~~~~~~~

Each input format has its own configuration section. See :doc:`options` for the complete reference. Common sections include:

* ``[pdf]`` - PDF conversion options (pages, column detection, table detection)
* ``[html]`` - HTML conversion options (sanitization, network settings)
* ``[docx]`` - Word document options (headers/footers, comments)
* ``[pptx]`` - PowerPoint options (slide handling)
* ``[eml]`` - Email options (chain detection, attachment handling)

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

   # Save current settings
   all2md document.pdf --attachment-mode save --pdf-pages "1-10" \
       --save-config my-settings.toml

   # Reuse saved settings
   all2md other-document.pdf --config my-settings.toml

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
