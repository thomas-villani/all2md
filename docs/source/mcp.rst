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

The all2md MCP server exposes three primary tools:

1. **read_document_as_markdown** - Read and convert documents to Markdown format
2. **save_document_from_markdown** - Save Markdown to other formats (disabled by default for security)
3. **edit_document** - Edit markdown documents by manipulating their structure (disabled by default for security)

Features
~~~~~~~~

* **Format Support**: PDF, DOCX, PPTX, HTML, EPUB, XLSX, and 200+ text formats
* **Security First**: File access allowlists, network controls, path validation
* **Image Support**: Extract images for vLLM visibility (base64 embedding)
* **Auto-Detection**: Smart source detection (path, data URI, base64, or plain text)
* **Section Extraction**: Extract specific sections by heading name or index
* **Simplified API**: Just 2-3 parameters per tool with server-level configuration
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

read_document_as_markdown
~~~~~~~~~~~~~~~~~~~~~~~~~

Read and convert documents to Markdown format with smart source auto-detection.

**Parameters:**

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``source``
     - string
     - **REQUIRED.** Unified source parameter. Auto-detected as: (1) file path if exists in read allowlist, (2) data URI (``data:...``), (3) base64 string if valid, or (4) plain text content.
   * - ``section``
     - string
     - *Optional.* Section name to extract (case-insensitive heading match). If provided, only that section is returned.
   * - ``format_hint``
     - string
     - *Optional.* Format hint for ambiguous cases: ``auto`` (default), ``pdf``, ``docx``, ``pptx``, ``html``, ``eml``, ``epub``, ``ipynb``, etc.
   * - ``pdf_pages``
     - string
     - *Optional.* PDF page specification (e.g., ``"1-3"``, ``"1,3,5"``, ``"1-3,5,10-"``).

**Auto-Detection Behavior:**

The ``source`` parameter is automatically detected as:

1. **File path**: If the string resolves to a file in the read allowlist
2. **Data URI**: If the string starts with ``data:`` (e.g., ``data:image/png;base64,...``)
3. **Base64**: If the string looks like base64 and decodes successfully
4. **Plain text**: Otherwise, treated as inline text content (HTML, Markdown, etc.)

**Server-Level Configuration:**

* ``include_images`` - Whether to include images (configured at server startup)
* ``flavor`` - Markdown flavor to use (gfm, commonmark, etc.)

**Returns:**

A list with:

* Markdown text (string) as the first element
* Image objects (when ``include_images=true``) for vLLM visibility

**Examples:**

Convert a file by path:

.. code-block:: json

   {
     "source": "/workspace/document.pdf",
     "pdf_pages": "1-5"
   }

Convert HTML content (auto-detected as plain text):

.. code-block:: json

   {
     "source": "<html><body><h1>Title</h1></body></html>",
     "format_hint": "html"
   }

Convert base64-encoded PDF (auto-detected):

.. code-block:: json

   {
     "source": "JVBERi0xLjQKJeLjz9MK...",
     "format_hint": "pdf"
   }

Extract a specific section:

.. code-block:: json

   {
     "source": "/workspace/report.md",
     "section": "Executive Summary"
   }

save_document_from_markdown
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Save Markdown content to other formats. **Requires** ``--enable-from-md`` flag (disabled by default for security).

This tool always writes to disk - the ``filename`` parameter is required and must pass write allowlist validation.

**Parameters:**

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``format``
     - string
     - **REQUIRED.** Target format: ``html``, ``pdf``, ``docx``, ``pptx``, ``rst``, ``epub``, ``markdown``.
   * - ``source``
     - string
     - **REQUIRED.** Markdown content as a string.
   * - ``filename``
     - string
     - **REQUIRED.** Output file path (must be in write allowlist).

**Server-Level Configuration:**

* ``flavor`` - Markdown flavor for parsing (gfm, commonmark, etc.)

**Returns:**

A dictionary with:

* ``output_path``: File path where content was written
* ``warnings``: List of warning messages

**Examples:**

Save Markdown as HTML:

.. code-block:: json

   {
     "format": "html",
     "source": "# Hello World\\n\\nThis is a test.",
     "filename": "/workspace/output.html"
   }

Save Markdown as PDF:

.. code-block:: json

   {
     "format": "pdf",
     "source": "# Report\\n\\nExecutive summary here.",
     "filename": "/workspace/report.pdf"
   }

Save Markdown as DOCX:

.. code-block:: json

   {
     "format": "docx",
     "source": "# Document Title\\n\\nContent goes here.",
     "filename": "/workspace/document.docx"
   }

edit_document
~~~~~~~~~~~~~

Edit markdown documents by manipulating their structure. **Requires** ``--enable-doc-edit`` flag (disabled by default for security).

This tool provides a simplified, LLM-friendly interface for document manipulation with sensible defaults (markdown only, case-insensitive heading matching, GFM flavor).

**Parameters:**

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``action``
     - string
     - **REQUIRED.** Action to perform: ``list-sections``, ``extract``, ``add:before``, ``add:after``, ``remove``, ``replace``, ``insert:start``, ``insert:end``, ``insert:after_heading``.
   * - ``doc``
     - string
     - **REQUIRED.** File path to the document (must be in read allowlist).
   * - ``target``
     - string
     - Section to target. Either heading text (case-insensitive) like ``"Introduction"``, or index notation like ``"#0"``, ``"#1"`` (zero-based). Required for all actions except ``list-sections``.
   * - ``content``
     - string
     - Markdown content to add/replace/insert. Required for ``add:before``, ``add:after``, ``replace``, and insert actions.

**Actions:**

- ``list-sections``: List all sections with metadata (returns formatted section list)
- ``extract``: Get a specific section by heading or index (returns section content)
- ``add:before``: Add new section before the target section
- ``add:after``: Add new section after the target section
- ``remove``: Remove a section from the document
- ``replace``: Replace section content with new content
- ``insert:start``: Insert content at the start of a section
- ``insert:end``: Insert content at the end of a section
- ``insert:after_heading``: Insert content right after the section heading

**Returns:**

A dictionary with:

- ``success``: Boolean indicating if operation succeeded
- ``message``: Human-readable result or error message
- ``content``: Content from operation (for ``list-sections`` and ``extract`` actions)

**Examples:**

List all sections:

.. code-block:: json

   {
     "action": "list-sections",
     "doc": "/workspace/document.md"
   }

Extract a section by heading:

.. code-block:: json

   {
     "action": "extract",
     "doc": "/workspace/document.md",
     "target": "Introduction"
   }

Extract a section by index:

.. code-block:: json

   {
     "action": "extract",
     "doc": "/workspace/document.md",
     "target": "#2"
   }

Add a new section:

.. code-block:: json

   {
     "action": "add:after",
     "doc": "/workspace/document.md",
     "target": "Chapter 1",
     "content": "# New Section\n\nContent here."
   }

Replace section content:

.. code-block:: json

   {
     "action": "replace",
     "doc": "/workspace/document.md",
     "target": "#0",
     "content": "# Updated Heading\n\nUpdated content."
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

**Image Inclusion:**

* ``--include-images`` - Include images in output for vLLM visibility (default: true)
* ``--no-include-images`` - Do not include images, use alt text only

**Markdown Flavor:**

* ``--flavor FLAVOR`` - Markdown flavor: ``gfm`` (default), ``commonmark``, ``multimarkdown``, ``pandoc``, ``kramdown``, ``markdown_plus``

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
     - Enable read_document_as_markdown tool
   * - ``ALL2MD_MCP_ENABLE_FROM_MD``
     - ``false``
     - Enable save_document_from_markdown tool
   * - ``ALL2MD_MCP_ENABLE_DOC_EDIT``
     - ``false``
     - Enable edit_document tool
   * - ``ALL2MD_MCP_ALLOWED_READ_DIRS``
     - CWD
     - Semicolon-separated read allowlist paths
   * - ``ALL2MD_MCP_ALLOWED_WRITE_DIRS``
     - CWD
     - Semicolon-separated write allowlist paths
   * - ``ALL2MD_MCP_INCLUDE_IMAGES``
     - ``false``
     - Include images in output (true/false)
   * - ``ALL2MD_MCP_FLAVOR``
     - ``gfm``
     - Markdown flavor (gfm, commonmark, etc.)
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
     --include-images \
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

Image Inclusion
~~~~~~~~~~~~~~~

The server supports a simple boolean flag for image handling:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Setting
     - Behavior
   * - ``include_images=true``
     - Embed images as base64 data URIs (enables vLLM visibility)
   * - ``include_images=false``
     - Include alt text only (no image data)

When ``include_images=true`` (default):

* Images from PDF, DOCX, PPTX are embedded as base64
* FastMCP automatically converts images to content blocks
* vLLMs can "see" the images alongside text

When ``include_images=false``:

* Images are replaced with alt text only
* Reduces output size
* Useful when images are not needed

.. note::

   The ``save`` attachment mode is **not available** in MCP mode for security reasons. Images are either embedded as base64 or replaced with alt text.

Best Practices
~~~~~~~~~~~~~~

1. **Use --temp for AI Assistants**: Create isolated workspaces
2. **Keep from_md Disabled**: Only enable rendering when necessary
3. **Restrict Allowlists**: Limit to specific directories, never use ``/``
4. **Disable Network**: Keep network disabled unless absolutely required
5. **Monitor Logs**: Use appropriate log level to track operations

Integration Examples
--------------------

.. TODO: add examples using uv to launch in isolated environment

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
           "--include-images",
           "--flavor", "gfm",
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

               # Call read_document_as_markdown tool
               result = await session.call_tool(
                   "read_document_as_markdown",
                   arguments={
                       "source": "/tmp/document.pdf",
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
   from all2md.mcp.document_tools import edit_document_impl
   from all2md.mcp.security import prepare_allowlist_dirs
   from all2md.mcp.tools import read_document_as_markdown_impl, save_document_from_markdown_impl

   # Create custom configuration
   config = MCPConfig(
       enable_to_md=True,
       enable_from_md=False,
       enable_doc_edit=False,
       read_allowlist=prepare_allowlist_dirs(["/safe/documents"]),
       write_allowlist=prepare_allowlist_dirs(["/safe/output"]),
       include_images=True,
       flavor="gfm",
       disable_network=True,
       log_level="INFO"
   )

   # Create MCP server with custom config
   mcp = create_server(config, read_document_as_markdown_impl, save_document_from_markdown_impl, edit_document_impl)

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

Enable image inclusion (enabled by default):

.. code-block:: bash

   all2md-mcp --include-images

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
       "read_document_as_markdown",
       arguments={
           "source": pdf_base64,
           "format_hint": "pdf"
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

* **No Download Mode**: Attachment mode ``save`` is not available in MCP for security reasons
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
