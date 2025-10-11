MCP Server
==========

all2md includes an MCP (Model Context Protocol) server implementation that enables AI assistants and language models to convert documents directly through the MCP protocol. This allows LLMs to read PDFs, Word documents, presentations, and other formats as part of their workflow.

.. contents::
   :local:
   :depth: 2

Overview
--------

What is MCP?
~~~~~~~~~~~~

The Model Context Protocol (MCP) is an open standard that enables AI assistants to connect with external data sources and tools. By running all2md as an MCP server, you give AI models the ability to:

* Read and convert documents in 20+ formats
* Extract text and images from PDFs and Office documents
* Convert Markdown to other formats (HTML, PDF, DOCX, etc.)
* Process documents with comprehensive security controls

The all2md MCP server exposes two primary tools:

1. **convert_to_markdown** - Convert documents to Markdown format
2. **render_from_markdown** - Convert Markdown to other formats (disabled by default for security)

Features
~~~~~~~~

* **Format Support**: PDF, DOCX, PPTX, HTML, EPUB, XLSX, and 200+ text formats
* **Security First**: File access allowlists, network controls, path validation
* **Image Support**: Extract images for vLLM visibility (base64 embedding)
* **Flexible Input**: Accept file paths or inline content (text/base64)
* **Bidirectional**: Both to-Markdown and from-Markdown conversions
* **Standards Compliant**: Uses FastMCP for MCP protocol implementation

Installation
------------

Install all2md with MCP support:

.. code-block:: bash

   # Install with MCP dependencies
   pip install 'all2md[mcp]'

   # Or install all dependencies including MCP
   pip install 'all2md[all]'

This installs FastMCP, which provides the MCP protocol implementation.

Quick Start
-----------

Basic Usage
~~~~~~~~~~~

Start the MCP server with default settings (current directory access only):

.. code-block:: bash

   # Start server (reads/writes in current directory only)
   all2md-mcp

   # Or use Python module form
   python -m all2md.mcp

The server will start and listen on stdio, ready to accept MCP requests from AI clients.

Temporary Workspace
~~~~~~~~~~~~~~~~~~~

For AI assistant usage, create a temporary workspace:

.. code-block:: bash

   # Create temporary directory for LLM operations
   all2md-mcp --temp

This creates an isolated temporary directory and restricts all file operations to it.

Enable Writing/Rendering
~~~~~~~~~~~~~~~~~~~~~~~~~

By default, only document-to-Markdown conversion is enabled. To allow Markdown-to-format rendering:

.. code-block:: bash

   # Enable both reading and writing
   all2md-mcp --temp --enable-from-md

Available Tools
---------------

convert_to_markdown
~~~~~~~~~~~~~~~~~~~

Convert documents to Markdown format.

**Parameters:**

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``source_path``
     - string
     - File path to convert. Must be within read allowlist. Mutually exclusive with ``source_content``.
   * - ``source_content``
     - string
     - Inline content to convert. For text formats (HTML, Markdown): plain text. For binary formats (PDF, DOCX): base64-encoded. Mutually exclusive with ``source_path``.
   * - ``content_encoding``
     - string
     - Encoding of ``source_content``: ``"plain"`` (default) or ``"base64"``.
   * - ``source_format``
     - string
     - Source format: ``auto`` (default), ``pdf``, ``docx``, ``pptx``, ``html``, ``eml``, ``epub``, ``ipynb``, ``odt``, ``odp``, ``ods``, ``xlsx``, ``csv``, ``rst``, ``markdown``, ``txt``.
   * - ``flavor``
     - string
     - Markdown flavor: ``gfm`` (default), ``commonmark``, ``multimarkdown``, ``pandoc``, ``kramdown``, ``markdown_plus``.
   * - ``pdf_pages``
     - string
     - PDF page specification (e.g., ``"1-3"``, ``"1,3,5"``, ``"1-3,5,10-"``).

**Returns:**

A list with:

* Markdown text (string) as the first element
* Image objects (when ``attachment_mode=base64``) for vLLM visibility

**Examples:**

.. code-block:: json

   {
     "source_path": "/workspace/document.pdf",
     "source_format": "pdf",
     "pdf_pages": "1-5"
   }

.. code-block:: json

   {
     "source_content": "<html><body><h1>Title</h1></body></html>",
     "content_encoding": "plain",
     "source_format": "html",
     "flavor": "gfm"
   }

render_from_markdown
~~~~~~~~~~~~~~~~~~~~

Convert Markdown to other formats. **Requires** ``--enable-from-md`` flag (disabled by default).

**Parameters:**

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``target_format``
     - string
     - **REQUIRED.** Target format: ``html``, ``pdf``, ``docx``, ``pptx``, ``rst``, ``epub``, ``markdown``.
   * - ``markdown``
     - string
     - Markdown content as string. Mutually exclusive with ``markdown_path``.
   * - ``markdown_path``
     - string
     - Path to markdown file. Must be in read allowlist. Mutually exclusive with ``markdown``.
   * - ``output_path``
     - string
     - Output file path (must be in write allowlist). If not provided, content is returned.
   * - ``flavor``
     - string
     - Markdown flavor for parsing: ``gfm`` (default), ``commonmark``, etc.

**Returns:**

A dictionary with:

* ``content``: Rendered content (if no output_path). Binary formats are base64-encoded.
* ``output_path``: File path where content was written (if output_path specified).
* ``warnings``: List of warning messages.

**Examples:**

.. code-block:: json

   {
     "markdown": "# Hello World\\n\\nThis is a test.",
     "target_format": "html"
   }

.. code-block:: json

   {
     "markdown_path": "/workspace/document.md",
     "target_format": "docx",
     "output_path": "/workspace/output.docx"
   }

Configuration
-------------

The MCP server can be configured via environment variables and command-line arguments. CLI arguments take precedence over environment variables.

Command-Line Arguments
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   all2md-mcp [OPTIONS]

**Workspace:**

* ``--temp`` - Create temporary workspace directory (sets read/write allowlists to temp dir)

**Tool Toggles:**

* ``--enable-to-md`` - Enable convert_to_markdown tool (default: true)
* ``--no-to-md`` - Disable convert_to_markdown tool
* ``--enable-from-md`` - Enable render_from_markdown tool (default: false)
* ``--no-from-md`` - Disable render_from_markdown tool

**Path Allowlists:**

* ``--read-dirs PATHS`` - Semicolon-separated list of allowed read directories
* ``--write-dirs PATHS`` - Semicolon-separated list of allowed write directories

**Attachment Handling:**

* ``--attachment-mode MODE`` - How to handle attachments: ``skip``, ``alt_text``, ``base64`` (default: base64)

**Network Control:**

* ``--allow-network`` - Allow network access (default: disabled)
* ``--disable-network`` - Disable network access (default: true)

**Logging:**

* ``--log-level LEVEL`` - Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Variable
     - Default
     - Description
   * - ``ALL2MD_MCP_ENABLE_TO_MD``
     - ``true``
     - Enable convert_to_markdown tool
   * - ``ALL2MD_MCP_ENABLE_FROM_MD``
     - ``false``
     - Enable render_from_markdown tool
   * - ``ALL2MD_MCP_ALLOWED_READ_DIRS``
     - CWD
     - Semicolon-separated read allowlist paths
   * - ``ALL2MD_MCP_ALLOWED_WRITE_DIRS``
     - CWD
     - Semicolon-separated write allowlist paths
   * - ``ALL2MD_MCP_ATTACHMENT_MODE``
     - ``base64``
     - Attachment mode: skip, alt_text, base64
   * - ``ALL2MD_DISABLE_NETWORK``
     - ``true``
     - Disable network access globally
   * - ``ALL2MD_MCP_LOG_LEVEL``
     - ``INFO``
     - Logging level

Configuration Examples
~~~~~~~~~~~~~~~~~~~~~~

**Production Web Service (Read-Only):**

.. code-block:: bash

   # Restrict to uploads directory, no writing
   all2md-mcp \
     --read-dirs "/var/app/uploads" \
     --write-dirs "/var/app/tmp" \
     --attachment-mode base64 \
     --disable-network \
     --log-level WARNING

**Development Environment:**

.. code-block:: bash

   # Allow full access to project directory
   export ALL2MD_MCP_ALLOWED_READ_DIRS="/home/user/projects"
   export ALL2MD_MCP_ALLOWED_WRITE_DIRS="/home/user/projects"
   export ALL2MD_MCP_LOG_LEVEL="DEBUG"

   all2md-mcp --enable-from-md --allow-network

**AI Assistant (Isolated Workspace):**

.. code-block:: bash

   # Create isolated temporary workspace
   all2md-mcp --temp --enable-from-md

Security
--------

The MCP server includes comprehensive security controls to protect against unauthorized file access and resource abuse.

File Access Controls
~~~~~~~~~~~~~~~~~~~~

**Read Allowlist:**

* All file read operations are restricted to directories in the read allowlist
* Default: current working directory only
* Configure with ``--read-dirs`` or ``ALL2MD_MCP_ALLOWED_READ_DIRS``

**Write Allowlist:**

* All file write operations are restricted to directories in the write allowlist
* Default: current working directory only
* Configure with ``--write-dirs`` or ``ALL2MD_MCP_ALLOWED_WRITE_DIRS``
* Requires ``--enable-from-md`` flag

**Path Validation:**

* Automatic path traversal protection (``..`` detection)
* Symlink resolution to prevent escapes
* Case-normalized paths on Windows
* Existence validation before access

Network Controls
~~~~~~~~~~~~~~~~

By default, network access is **disabled** to prevent:

* Server-Side Request Forgery (SSRF) attacks
* Unauthorized external data fetching
* Internal network scanning

When ``disable_network=true`` (default):

* External HTML images cannot be fetched
* Embedded images in PDF/DOCX/PPTX still work
* Maximum security for untrusted input

To enable network access (not recommended for untrusted content):

.. code-block:: bash

   all2md-mcp --allow-network

Attachment Modes
~~~~~~~~~~~~~~~~

The server supports three attachment modes:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Mode
     - Behavior
   * - ``skip``
     - Ignore all images and attachments
   * - ``alt_text``
     - Include alt text and filenames in markdown
   * - ``base64``
     - Embed images as base64 data URIs (enables vLLM visibility)

.. note::

   The ``download`` attachment mode is **not available** in MCP mode for security reasons. Images are either skipped, referenced as alt text, or embedded as base64.

Best Practices
~~~~~~~~~~~~~~

1. **Use --temp for AI Assistants**: Create isolated workspaces
2. **Keep from_md Disabled**: Only enable rendering when necessary
3. **Restrict Allowlists**: Limit to specific directories, never use ``/``
4. **Disable Network**: Keep network disabled unless absolutely required
5. **Monitor Logs**: Use appropriate log level to track operations

Integration Examples
--------------------

Claude Desktop
~~~~~~~~~~~~~~

Add to your Claude Desktop configuration (``claude_desktop_config.json``):

.. code-block:: json

   {
     "mcpServers": {
       "all2md": {
         "command": "all2md-mcp",
         "args": ["--temp", "--enable-from-md"],
         "env": {
           "ALL2MD_MCP_LOG_LEVEL": "INFO"
         }
       }
     }
   }

Cline (VSCode)
~~~~~~~~~~~~~~

Add to your Cline MCP settings (``cline_mcp_settings.json``):

.. code-block:: json

   {
     "mcpServers": {
       "all2md": {
         "command": "all2md-mcp",
         "args": [
           "--read-dirs", "/path/to/project",
           "--write-dirs", "/path/to/output",
           "--attachment-mode", "base64",
           "--log-level", "DEBUG"
         ]
       }
     }
   }

Python MCP Client
~~~~~~~~~~~~~~~~~

Using the ``mcp`` Python client library:

.. code-block:: python

   import asyncio
   from mcp import ClientSession, StdioServerParameters
   from mcp.client.stdio import stdio_client

   async def convert_document():
       server_params = StdioServerParameters(
           command="all2md-mcp",
           args=["--temp"],
           env={"ALL2MD_MCP_LOG_LEVEL": "DEBUG"}
       )

       async with stdio_client(server_params) as (read, write):
           async with ClientSession(read, write) as session:
               await session.initialize()

               # Call convert_to_markdown tool
               result = await session.call_tool(
                   "convert_to_markdown",
                   arguments={
                       "source_path": "/tmp/document.pdf",
                       "source_format": "pdf",
                       "pdf_pages": "1-3"
                   }
               )

               # Extract markdown text
               markdown_text = result.content[0].text
               print(markdown_text)

   asyncio.run(convert_document())

Custom MCP Server Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Embedding all2md-mcp in your own MCP server:

.. code-block:: python

   from all2md.mcp import create_server, MCPConfig
   from all2md.mcp.tools import convert_to_markdown_impl, render_from_markdown_impl

   # Create custom configuration
   config = MCPConfig(
       enable_to_md=True,
       enable_from_md=False,
       read_allowlist=["/safe/documents"],
       write_allowlist=["/safe/output"],
       attachment_mode="base64",
       disable_network=True,
       log_level="INFO"
   )

   # Create MCP server with custom config
   mcp = create_server(config, convert_to_markdown_impl, render_from_markdown_impl)

   # Run server
   mcp.run()

Troubleshooting
---------------

Server Won't Start
~~~~~~~~~~~~~~~~~~

**Error:** ``ImportError: FastMCP not installed``

**Solution:**

.. code-block:: bash

   pip install 'all2md[mcp]'

Permission Denied Errors
~~~~~~~~~~~~~~~~~~~~~~~~

**Error:** ``MCPSecurityError: Read access denied: path not in allowlist``

**Solution:**

Ensure the file path is within the read allowlist:

.. code-block:: bash

   # Add directory to allowlist
   all2md-mcp --read-dirs "/path/to/documents"

   # Or use environment variable
   export ALL2MD_MCP_ALLOWED_READ_DIRS="/path/to/documents"
   all2md-mcp

Images Not Visible to LLM
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem:** LLM can't "see" images from converted documents.

**Solution:**

Use ``base64`` attachment mode (default):

.. code-block:: bash

   all2md-mcp --attachment-mode base64

.. note::

   With ``disable_network=true`` (default), external HTML images won't be embedded, but images from PDF/DOCX/PPTX will work fine.

Network Access Errors
~~~~~~~~~~~~~~~~~~~~~~

**Error:** ``Network access is disabled``

**Solution:**

If you need to fetch external HTML images (not recommended for untrusted content):

.. code-block:: bash

   all2md-mcp --allow-network

Invalid Base64 Content
~~~~~~~~~~~~~~~~~~~~~~~

**Error:** ``Invalid base64 encoding``

**Solution:**

Ensure binary content is properly base64-encoded:

.. code-block:: python

   import base64

   # Read binary file
   with open('document.pdf', 'rb') as f:
       pdf_bytes = f.read()

   # Encode for MCP
   pdf_base64 = base64.b64encode(pdf_bytes).decode('ascii')

   # Send to MCP server
   result = await session.call_tool(
       "convert_to_markdown",
       arguments={
           "source_content": pdf_base64,
           "content_encoding": "base64",
           "source_format": "pdf"
       }
   )

Debugging
~~~~~~~~~

Enable debug logging to diagnose issues:

.. code-block:: bash

   # Command line
   all2md-mcp --log-level DEBUG

   # Environment variable
   export ALL2MD_MCP_LOG_LEVEL=DEBUG
   all2md-mcp

Logs are written to stderr (MCP uses stdout for protocol communication).

Limitations
-----------

Current Limitations
~~~~~~~~~~~~~~~~~~~

* **No Download Mode**: Attachment mode ``download`` is not available in MCP for security reasons
* **No Streaming**: Large documents are processed synchronously
* **Network Default Off**: External HTML images require explicit ``--allow-network`` flag
* **Single Server**: Each MCP server instance handles one request at a time (stdio transport)

Security Considerations
~~~~~~~~~~~~~~~~~~~~~~~

When exposing all2md via MCP:

* **Always use allowlists** - Never allow unrestricted file access
* **Keep network disabled** - Enable only when absolutely necessary
* **Validate inputs** - Assume all LLM-provided inputs are potentially malicious
* **Monitor resource usage** - Large documents can consume significant memory
* **Use --temp for AI** - Isolate AI operations in temporary workspaces

See Also
--------

* :doc:`security` - Comprehensive security documentation
* :doc:`formats` - Supported file formats and options
* :doc:`cli` - Command-line interface reference
* :doc:`troubleshooting` - General troubleshooting guide
