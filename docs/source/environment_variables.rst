Environment Variables
=====================

all2md supports configuration through environment variables, providing a convenient way to set defaults for CLI commands, control security settings, and configure application behavior. This reference documents all available environment variables and their usage.

.. contents::
   :local:
   :depth: 2

Overview
--------

Environment variables in all2md follow these patterns:

1. **Global Security Controls**: ``ALL2MD_DISABLE_NETWORK``
2. **MCP Server Configuration**: ``ALL2MD_MCP_*``
3. **Configuration File**: ``ALL2MD_CONFIG``
4. **CLI Option Defaults**: ``ALL2MD_<OPTION_NAME>`` (any CLI flag)

Environment variables are particularly useful for:

* Setting security defaults in production
* Configuring Docker containers
* Managing CI/CD pipelines
* Avoiding repetitive CLI flags

Security Variables
------------------

ALL2MD_DISABLE_NETWORK
~~~~~~~~~~~~~~~~~~~~~~

**Purpose:** Globally disable network access to prevent SSRF attacks and unauthorized data fetching.

**Type:** Boolean

**Default:** ``false`` (network enabled by default)

**Valid Values:** ``true``, ``1``, ``yes``, ``on`` (case-insensitive) enable the restriction

**Scope:** Global - affects all document conversions

**Description:**

When enabled, blocks all network requests for fetching external resources (primarily affects HTML documents with remote images). This is the strongest defense against Server-Side Request Forgery (SSRF) attacks.

**Impact:**

* **HTML**: Cannot fetch external images via ``<img src="http://...">``
* **MHTML**: Cannot fetch external resources
* **PDF/DOCX/PPTX**: No impact (embedded images still work)
* **Other formats**: No impact

**Examples:**

.. code-block:: bash

   # Production: Disable network globally
   export ALL2MD_DISABLE_NETWORK=true
   all2md webpage.html

   # Docker deployment
   docker run -e ALL2MD_DISABLE_NETWORK=1 \
     -v /docs:/docs \
     all2md-image all2md /docs/file.html

.. code-block:: python

   # Python: Set before importing all2md
   import os
   os.environ['ALL2MD_DISABLE_NETWORK'] = '1'

   from all2md import to_markdown
   markdown = to_markdown('webpage.html')  # Network blocked

**See Also:**

* :doc:`security` - Network security documentation
* ``NetworkFetchOptions.allow_remote_fetch`` - Per-call network control

MCP Server Variables
--------------------

ALL2MD_MCP_ENABLE_TO_MD
~~~~~~~~~~~~~~~~~~~~~~~

**Purpose:** Enable/disable the ``convert_to_markdown`` tool in MCP server.

**Type:** Boolean

**Default:** ``true``

**Valid Values:** ``true``, ``false``, ``1``, ``0``, ``yes``, ``no``

**Example:**

.. code-block:: bash

   # Disable markdown conversion (unusual)
   export ALL2MD_MCP_ENABLE_TO_MD=false
   all2md-mcp

ALL2MD_MCP_ENABLE_FROM_MD
~~~~~~~~~~~~~~~~~~~~~~~~~

**Purpose:** Enable/disable the ``render_from_markdown`` tool in MCP server.

**Type:** Boolean

**Default:** ``false`` (disabled for security - prevents arbitrary file writes)

**Valid Values:** ``true``, ``false``, ``1``, ``0``, ``yes``, ``no``

**Example:**

.. code-block:: bash

   # Enable rendering (allows LLM to write files)
   export ALL2MD_MCP_ENABLE_FROM_MD=true
   all2md-mcp

ALL2MD_MCP_ALLOWED_READ_DIRS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Purpose:** Semicolon-separated list of directories the MCP server can read from.

**Type:** String (semicolon-separated paths)

**Default:** Current working directory

**Example:**

.. code-block:: bash

   # Allow reading from multiple directories
   export ALL2MD_MCP_ALLOWED_READ_DIRS="/home/user/documents;/var/app/uploads"
   all2md-mcp

   # Windows paths
   set ALL2MD_MCP_ALLOWED_READ_DIRS=C:\Users\User\Documents;D:\Data

ALL2MD_MCP_ALLOWED_WRITE_DIRS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Purpose:** Semicolon-separated list of directories the MCP server can write to.

**Type:** String (semicolon-separated paths)

**Default:** Current working directory

**Example:**

.. code-block:: bash

   # Restrict writes to output directory only
   export ALL2MD_MCP_ALLOWED_WRITE_DIRS="/var/app/output"
   all2md-mcp --enable-from-md

ALL2MD_MCP_ATTACHMENT_MODE
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Purpose:** Default attachment handling mode for MCP server.

**Type:** String

**Default:** ``base64``

**Valid Values:** ``skip``, ``alt_text``, ``base64``

**Note:** The ``download`` mode is intentionally not available in MCP for security.

**Example:**

.. code-block:: bash

   # Skip all attachments for maximum speed
   export ALL2MD_MCP_ATTACHMENT_MODE=skip
   all2md-mcp

ALL2MD_MCP_LOG_LEVEL
~~~~~~~~~~~~~~~~~~~~~

**Purpose:** Logging level for MCP server.

**Type:** String

**Default:** ``INFO``

**Valid Values:** ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, ``CRITICAL``

**Example:**

.. code-block:: bash

   # Enable debug logging
   export ALL2MD_MCP_LOG_LEVEL=DEBUG
   all2md-mcp

Configuration File
------------------

ALL2MD_CONFIG
~~~~~~~~~~~~~

**Purpose:** Specify path to configuration file (JSON or TOML format).

**Type:** String (file path)

**Default:** None (auto-discovery is used if not set)

**Description:**

Points to a configuration file containing conversion options. Useful for:

* Docker/Kubernetes ConfigMaps
* CI/CD pipelines
* Avoiding long command lines
* Sharing configurations across projects

Supports both JSON and TOML formats. TOML is preferred for human editing as it supports comments.

**Examples:**

**TOML Configuration:**

.. code-block:: bash

   # .all2md.toml
   attachment_mode = "skip"

   [pdf]
   pages = [1, 2, 3]
   detect_columns = false

   [html]
   strip_dangerous_elements = true

   [html.network]
   allow_remote_fetch = false

   # Use file path
   export ALL2MD_CONFIG=/etc/all2md/config.toml
   all2md document.pdf

**JSON Configuration:**

.. code-block:: bash

   # config.json
   {
     "attachment_mode": "base64",
     "markdown": {
       "flavor": "gfm",
       "emphasis_symbol": "*"
     }
   }

   # Use file path
   export ALL2MD_CONFIG=/etc/all2md/config.json
   all2md document.pdf

**Docker Usage:**

.. code-block:: yaml

   # docker-compose.yml
   services:
     converter:
       image: all2md:latest
       volumes:
         - ./config.toml:/etc/all2md/config.toml
       environment:
         ALL2MD_CONFIG: /etc/all2md/config.toml

CLI Option Environment Variables
---------------------------------

Pattern: ALL2MD_<OPTION_NAME>
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Purpose:** Set default values for any CLI option.

**Pattern:** ``ALL2MD_`` + uppercase option name with dashes/dots replaced by underscores

**Scope:** Affects CLI commands only (not programmatic API)

**Examples:**

**Common CLI Options:**

.. list-table::
   :header-rows: 1
   :widths: 40 30 30

   * - Environment Variable
     - CLI Flag
     - Example Value
   * - ``ALL2MD_ATTACHMENT_MODE``
     - ``--attachment-mode``
     - ``skip``
   * - ``ALL2MD_ATTACHMENT_OUTPUT_DIR``
     - ``--attachment-output-dir``
     - ``./images``
   * - ``ALL2MD_RICH``
     - ``--rich``
     - ``true``
   * - ``ALL2MD_OUTPUT_DIR``
     - ``--output-dir``
     - ``./converted``
   * - ``ALL2MD_SOURCE_FORMAT``
     - ``--source-format``
     - ``pdf``

**Format-Specific Options:**

.. list-table::
   :header-rows: 1
   :widths: 40 30 30

   * - Environment Variable
     - CLI Flag
     - Example Value
   * - ``ALL2MD_PDF_PAGES``
     - ``--pdf-pages``
     - ``1-10``
   * - ``ALL2MD_PDF_DETECT_COLUMNS``
     - ``--pdf-detect-columns``
     - ``true``
   * - ``ALL2MD_HTML_STRIP_DANGEROUS_ELEMENTS``
     - ``--html-strip-dangerous-elements``
     - ``true``
   * - ``ALL2MD_MARKDOWN_FLAVOR``
     - ``--markdown-flavor``
     - ``gfm``
   * - ``ALL2MD_MARKDOWN_EMPHASIS_SYMBOL``
     - ``--markdown-emphasis-symbol``
     - ``_``

**Nested Options:**

For nested options (e.g., ``--html-network-allow-remote-fetch``), replace all separators with underscores:

.. code-block:: bash

   # CLI: --html-network-allow-remote-fetch
   export ALL2MD_HTML_NETWORK_ALLOW_REMOTE_FETCH=false

   # CLI: --pdf-enable-table-fallback-detection
   export ALL2MD_PDF_ENABLE_TABLE_FALLBACK_DETECTION=true

**Usage Example:**

.. code-block:: bash

   # Set defaults via environment
   export ALL2MD_ATTACHMENT_MODE=skip
   export ALL2MD_PDF_PAGES="1-5"
   export ALL2MD_RICH=true

   # CLI commands use these defaults
   all2md document.pdf  # Uses pages=1-5, attachment_mode=skip, rich=true

   # Override specific defaults
   all2md document.pdf --pdf-pages "1-10"  # Overrides env var

**Type Conversion:**

Environment variable values are automatically converted to appropriate types:

* **Boolean**: ``true``, ``false``, ``1``, ``0``, ``yes``, ``no``, ``on``, ``off``
* **Integer**: Numeric strings (``"10"``)
* **String**: Text values
* **Lists**: Comma-separated (``"1,2,3"``)

Practical Examples
------------------

Production Web Server
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # .env file
   ALL2MD_DISABLE_NETWORK=true
   ALL2MD_ATTACHMENT_MODE=skip
   ALL2MD_CONFIG=/etc/all2md/production.toml

   # Start server
   uvicorn app:main --env-file .env

Docker Container
~~~~~~~~~~~~~~~~

.. code-block:: dockerfile

   # Dockerfile
   FROM python:3.12-slim
   RUN pip install all2md[all]

   # Set environment defaults
   ENV ALL2MD_DISABLE_NETWORK=true \
       ALL2MD_ATTACHMENT_MODE=skip \
       ALL2MD_PDF_DETECT_COLUMNS=false

   CMD ["all2md"]

.. code-block:: bash

   # Run with custom env vars
   docker run \
     -e ALL2MD_ATTACHMENT_MODE=base64 \
     -e ALL2MD_PDF_PAGES="1-10" \
     -v /docs:/docs \
     all2md-image all2md /docs/file.pdf

CI/CD Pipeline
~~~~~~~~~~~~~~

**GitHub Actions:**

.. code-block:: yaml

   # .github/workflows/convert-docs.yml
   name: Convert Documents
   on: [push]

   jobs:
     convert:
       runs-on: ubuntu-latest
       env:
         ALL2MD_DISABLE_NETWORK: "true"
         ALL2MD_ATTACHMENT_MODE: "skip"
       steps:
         - uses: actions/checkout@v3
         - uses: actions/setup-python@v4
           with:
             python-version: '3.12'
         - run: pip install all2md[all]
         - run: all2md docs/*.pdf --output-dir converted/

**GitLab CI:**

.. code-block:: yaml

   # .gitlab-ci.yml
   convert-docs:
     image: python:3.12
     variables:
       ALL2MD_DISABLE_NETWORK: "true"
       ALL2MD_ATTACHMENT_MODE: "skip"
       ALL2MD_PDF_PAGES: "1-5"
     script:
       - pip install all2md[all]
       - all2md documents/*.pdf --output-dir converted/
     artifacts:
       paths:
         - converted/

MCP Server Deployment
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Production MCP server with strict security
   export ALL2MD_MCP_ENABLE_TO_MD=true
   export ALL2MD_MCP_ENABLE_FROM_MD=false
   export ALL2MD_MCP_ALLOWED_READ_DIRS="/var/app/uploads"
   export ALL2MD_MCP_ALLOWED_WRITE_DIRS="/var/app/output"
   export ALL2MD_MCP_ATTACHMENT_MODE=skip
   export ALL2MD_DISABLE_NETWORK=true
   export ALL2MD_MCP_LOG_LEVEL=WARNING

   all2md-mcp

**Systemd Service:**

.. code-block:: ini

   # /etc/systemd/system/all2md-mcp.service
   [Unit]
   Description=all2md MCP Server
   After=network.target

   [Service]
   Type=simple
   User=all2md
   Environment="ALL2MD_DISABLE_NETWORK=true"
   Environment="ALL2MD_MCP_ALLOWED_READ_DIRS=/var/app/uploads"
   Environment="ALL2MD_MCP_ALLOWED_WRITE_DIRS=/var/app/output"
   Environment="ALL2MD_MCP_ATTACHMENT_MODE=skip"
   Environment="ALL2MD_MCP_LOG_LEVEL=INFO"
   ExecStart=/usr/local/bin/all2md-mcp
   Restart=always

   [Install]
   WantedBy=multi-user.target

Development vs Production
~~~~~~~~~~~~~~~~~~~~~~~~~

**Development (.env.development):**

.. code-block:: bash

   # Development: Permissive settings
   ALL2MD_DISABLE_NETWORK=false
   ALL2MD_ATTACHMENT_MODE=download
   ALL2MD_ATTACHMENT_OUTPUT_DIR=./dev-images
   ALL2MD_RICH=true
   ALL2MD_MCP_LOG_LEVEL=DEBUG

**Production (.env.production):**

.. code-block:: bash

   # Production: Secure settings
   ALL2MD_DISABLE_NETWORK=true
   ALL2MD_ATTACHMENT_MODE=skip
   ALL2MD_CONFIG=/etc/all2md/production-config.toml
   ALL2MD_MCP_LOG_LEVEL=WARNING

**Load Appropriately:**

.. code-block:: python

   # Python application
   from dotenv import load_dotenv
   import os

   # Load environment-specific config
   env = os.getenv('ENVIRONMENT', 'development')
   load_dotenv(f'.env.{env}')

   from all2md import to_markdown
   markdown = to_markdown('document.pdf')

Environment Variable Precedence
--------------------------------

When multiple configuration sources are present, they are applied in this order (later sources override earlier):

1. **Default values** (defined in code)
2. **Auto-discovered config files** (``.all2md.toml`` or ``.all2md.json``)
3. **Environment variables** (``ALL2MD_*``)
4. **Configuration file** (``ALL2MD_CONFIG``)
5. **Preset** (``--preset``)
6. **CLI arguments** (highest precedence)

**Example:**

.. code-block:: bash

   # Auto-discovered config
   # .all2md.toml contains: attachment_mode = "skip"

   # Environment variable
   export ALL2MD_ATTACHMENT_MODE=base64

   # Explicit config file
   export ALL2MD_CONFIG=custom.toml  # contains: attachment_mode = "download"

   # CLI flag
   all2md document.pdf --attachment-mode inline

   # Final value: "inline" (CLI wins over all)

Validation and Error Handling
------------------------------

Invalid Values
~~~~~~~~~~~~~~

Invalid environment variable values trigger errors:

.. code-block:: bash

   # Invalid boolean
   export ALL2MD_DISABLE_NETWORK=maybe
   all2md document.pdf
   # Error: Invalid boolean value for ALL2MD_DISABLE_NETWORK

   # Invalid choice
   export ALL2MD_ATTACHMENT_MODE=invalid
   all2md document.pdf
   # Error: Invalid attachment_mode: must be skip, alt_text, base64, or download

Required Values
~~~~~~~~~~~~~~~

Some environment variables require specific formats:

.. code-block:: bash

   # Invalid JSON
   export ALL2MD_CONFIG_JSON='{ bad json'
   all2md document.pdf
   # Error: Invalid JSON in ALL2MD_CONFIG_JSON

Type Mismatches
~~~~~~~~~~~~~~~

Environment variables are validated against expected types:

.. code-block:: bash

   # Expecting boolean, got string
   export ALL2MD_PDF_DETECT_COLUMNS=maybe
   all2md document.pdf
   # Error: Cannot convert 'maybe' to boolean

Quick Reference
---------------

**Most Common Variables:**

.. code-block:: bash

   # Security (production)
   export ALL2MD_DISABLE_NETWORK=true

   # Attachment handling
   export ALL2MD_ATTACHMENT_MODE=skip

   # Output configuration
   export ALL2MD_RICH=true
   export ALL2MD_OUTPUT_DIR=./converted

   # PDF-specific
   export ALL2MD_PDF_PAGES="1-10"

   # HTML security
   export ALL2MD_HTML_STRIP_DANGEROUS_ELEMENTS=true

   # Configuration file
   export ALL2MD_CONFIG=/path/to/config.toml

**MCP Server:**

.. code-block:: bash

   export ALL2MD_MCP_ENABLE_TO_MD=true
   export ALL2MD_MCP_ENABLE_FROM_MD=false
   export ALL2MD_MCP_ALLOWED_READ_DIRS="/path/to/docs"
   export ALL2MD_MCP_ALLOWED_WRITE_DIRS="/path/to/output"
   export ALL2MD_MCP_ATTACHMENT_MODE=base64
   export ALL2MD_DISABLE_NETWORK=true
   export ALL2MD_MCP_LOG_LEVEL=INFO

See Also
--------

* :doc:`cli` - Command-line interface reference
* :doc:`security` - Security configuration
* :doc:`mcp` - MCP server documentation
* :doc:`integrations` - Framework integration examples
