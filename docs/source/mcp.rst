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

The all2md MCP server exposes six tools:

1. **read_document_as_markdown** - Read and convert documents to Markdown format
2. **save_document_from_markdown** - Save Markdown to other formats (disabled by default for security)
3. **edit_document** - Edit markdown documents by manipulating their structure (disabled by default for security)
4. **search_documents** - Search a corpus of documents (grep + keyword/BM25) and return ranked snippets
5. **diff_documents** - Compare two documents and return a unified or JSON diff
6. **get_document_outline** - List a document's heading structure for navigation

Tools 4-6 are read-only and **enabled by default**. Tools 2 and 3 write or mutate
files and remain disabled by default.

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
     "source": "# Hello World\n\nThis is a test.",
     "filename": "/workspace/output.html"
   }

Save Markdown as PDF:

.. code-block:: json

   {
     "format": "pdf",
     "source": "# Report\n\nExecutive summary here.",
     "filename": "/workspace/report.pdf"
   }

Save Markdown as DOCX:

.. code-block:: json

   {
     "format": "docx",
     "source": "# Document Title\n\nContent goes here.",
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

search_documents
~~~~~~~~~~~~~~~~~

Search a corpus of documents and return ranked snippets instead of whole files,
so an agent can locate information across many documents cheaply. Read-only;
enabled by default.

Two modes are supported:

* ``keyword`` (default) - BM25 relevance ranking. Best for "find the most
  relevant passages" queries. Requires the optional ``rank-bm25`` dependency
  (``pip install 'all2md[search]'``).
* ``grep`` - literal or regex line matching with highlighted spans. Best for
  "find every occurrence of X". Stateless, no extra dependencies.

Matched text in each snippet is wrapped in ``<<`` / ``>>`` markers.

**Parameters:**

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``query``
     - string
     - **REQUIRED.** Natural-language query (keyword mode) or literal/regex pattern (grep mode).
   * - ``paths``
     - list[string]
     - *Optional.* Files, directories, or globs to search (each validated against the read allowlist). Defaults to the read allowlist.
   * - ``mode``
     - string
     - *Optional.* ``keyword`` (default) or ``grep``.
   * - ``top_k``
     - integer
     - *Optional.* Maximum number of results to return (default: 10).
   * - ``ignore_case``
     - boolean
     - *Optional.* Case-insensitive matching (grep mode only; default: false).
   * - ``regex``
     - boolean
     - *Optional.* Treat the query as a regular expression (grep mode only; default: false).
   * - ``recursive``
     - boolean
     - *Optional.* Recurse into directories when collecting input files (default: true).

**Persistent index (optional):**

By default a fresh index is built in memory on every call. Set
``--search-index-dir PATH`` (or ``ALL2MD_MCP_SEARCH_INDEX_DIR``) to persist the
keyword index to disk and reuse it on subsequent calls. The directory must be
within the write allowlist. Grep mode is always stateless and never persisted.

**Returns:**

A dictionary with:

* ``results``: list of ``{snippet, score, document_path, section_heading, chunk_id}``
* ``mode``: the search mode used
* ``total``: number of results returned

**Examples:**

Keyword search across a directory:

.. code-block:: json

   {
     "query": "data retention policy",
     "paths": ["/workspace/contracts"],
     "mode": "keyword",
     "top_k": 5
   }

Grep for every occurrence of a pattern (case-insensitive):

.. code-block:: json

   {
     "query": "TODO|FIXME",
     "mode": "grep",
     "regex": true,
     "ignore_case": true
   }

diff_documents
~~~~~~~~~~~~~~

Compare two documents and return their differences. Read-only; enabled by
default. Each input is auto-detected (file path within the read allowlist, data
URI, base64, or inline content), so documents in any supported format can be
compared — even across formats (e.g. a DOCX against its PDF export).

**Parameters:**

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``old``
     - string
     - **REQUIRED.** Original document (path or inline content).
   * - ``new``
     - string
     - **REQUIRED.** Updated document (path or inline content).
   * - ``format``
     - string
     - *Optional.* Output format: ``unified`` (default, plain text) or ``json`` (structured).
   * - ``context_lines``
     - integer
     - *Optional.* Context lines around changes in unified output (default: 3).
   * - ``granularity``
     - string
     - *Optional.* Comparison granularity: ``block`` (default), ``sentence``, or ``word``.
   * - ``ignore_whitespace``
     - boolean
     - *Optional.* Normalize whitespace before comparing (default: false).

**Returns:**

A dictionary with:

* ``diff``: the rendered diff (unified text or JSON string)
* ``has_changes``: whether any differences were found

**Example:**

Compare two report versions:

.. code-block:: json

   {
     "old": "/workspace/report_v1.docx",
     "new": "/workspace/report_v2.docx",
     "format": "unified"
   }

get_document_outline
~~~~~~~~~~~~~~~~~~~~~

Return the heading structure (table of contents) of a document so an agent can
navigate a large file before extracting specific sections. Read-only; enabled by
default. The ``doc`` parameter is auto-detected (path, data URI, base64, or
inline content). The returned indices line up with ``edit_document``'s ``#N``
target notation.

**Parameters:**

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Parameter
     - Type
     - Description
   * - ``doc``
     - string
     - **REQUIRED.** Document to outline (path or inline content).
   * - ``max_level``
     - integer
     - *Optional.* Deepest heading level to include, 1-6 (default: 6 = all levels).
   * - ``format_hint``
     - string
     - *Optional.* Format hint for ambiguous/extensionless sources (``pdf``, ``docx``, ``html``, etc.).

**Returns:**

A dictionary with:

* ``sections``: list of ``{index, level, heading}``
* ``total``: number of headings returned

**Example:**

.. code-block:: json

   {
     "doc": "/workspace/manual.pdf",
     "max_level": 2
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

* ``--enable-to-md`` - Enable the read_document_as_markdown tool (default: true)
* ``--no-to-md`` - Disable the read_document_as_markdown tool
* ``--enable-from-md`` - Enable the save_document_from_markdown tool (default: false)
* ``--no-from-md`` - Disable the save_document_from_markdown tool
* ``--enable-doc-edit`` / ``--no-doc-edit`` - Toggle the edit_document tool (default: false)
* ``--enable-search`` / ``--no-search`` - Toggle the search_documents tool (default: true)
* ``--enable-diff`` / ``--no-diff`` - Toggle the diff_documents tool (default: true)
* ``--enable-outline`` / ``--no-outline`` - Toggle the get_document_outline tool (default: true)

**Path Allowlists:**

* ``--read-dirs PATHS`` - Semicolon-separated list of allowed read directories
* ``--write-dirs PATHS`` - Semicolon-separated list of allowed write directories

**Search Index:**

* ``--search-index-dir PATH`` - Persist/load the search keyword index in this directory (must be within the write allowlist). Omit to rebuild a fresh index on every call.

**Image Inclusion:**

* ``--include-images`` - Include images in output for vLLM visibility (default: false)
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
   * - ``ALL2MD_MCP_ENABLE_SEARCH``
     - ``true``
     - Enable search_documents tool
   * - ``ALL2MD_MCP_ENABLE_DIFF``
     - ``true``
     - Enable diff_documents tool
   * - ``ALL2MD_MCP_ENABLE_OUTLINE``
     - ``true``
     - Enable get_document_outline tool
   * - ``ALL2MD_MCP_SEARCH_INDEX_DIR``
     - *(none)*
     - Directory to persist the search keyword index (must be in write allowlist)
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

When ``include_images=true``:

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

Claude Desktop (one-click bundle)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The easiest way to use all2md in Claude Desktop is the prebuilt MCPB bundle
(``.mcpb``), which installs the server in one click — no manual config and no
separate Python install (the bundle resolves all2md via ``uv`` on first run).

#. Download ``all2md.mcpb`` from the `latest release
   <https://github.com/thomas-villani/all2md/releases/latest>`_.
#. Open **Claude Desktop → Settings → Extensions** (gear icon, or
   :kbd:`Ctrl+,` / :kbd:`Cmd+,`).
#. **Drag** ``all2md.mcpb`` onto the Extensions pane, or use the **Install
   Extension** / **Advanced** button to browse for it. (Double-clicking the
   file also works if your OS has the ``.mcpb`` association registered, but the
   drag path does not depend on it.)
#. In the install dialog, choose a **workspace folder** all2md may read from and
   write to (defaults to your Documents folder; files outside it are rejected),
   and optionally adjust the toggles for writing/rendering, in-place editing,
   and network access.
#. The tools then appear under the **"+" → Connectors** panel in a chat, ready
   to use on files in your workspace folder.

The bundle configures the server entirely through environment variables set
from your dialog choices, so it enables ``read_document_as_markdown``,
``save_document_from_markdown``, and ``edit_document`` by default (you can turn
the latter two off in the dialog). Requires a Claude Desktop build with MCPB
extension support (late-2025 or newer). The bundle sources live in the
``mcpb/`` directory of the repository if you want to rebuild it.

Building the bundle from source
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Releases ship a prebuilt ``all2md.mcpb`` automatically (CI packs and attaches it
to every GitHub release), so most users never need to build it. To produce one
yourself — for testing local changes, or to bundle a different set of format
extras — you need `Node.js <https://nodejs.org>`_ and the MCPB CLI:

.. code-block:: bash

   # Install the MCPB CLI (one-time)
   npm install -g @anthropic-ai/mcpb

   # From the repository root: validate, then pack
   mcpb validate mcpb/manifest.json
   mcpb pack mcpb all2md.mcpb

This writes ``all2md.mcpb`` (a small archive containing only the manifest, a
``pyproject.toml``, and a thin launcher — the ``all2md`` package itself is
resolved by ``uv`` on the end user's machine at install time). Install the
result with the drag-and-drop steps above.

A few things worth knowing when building or modifying the bundle:

* **Dependency extras.** ``mcpb/pyproject.toml`` declares which all2md format
  extras get installed (PDF, DOCX, render targets, etc.). Edit that dependency
  line and re-pack to bundle a different set — e.g. ``all2md[all]`` for every
  format.
* **Version sync.** The version in ``mcpb/manifest.json`` and
  ``mcpb/pyproject.toml`` is managed by the project's ``bumpversion`` config —
  bump the package version rather than hand-editing those strings, or the
  release job's version check will fail.
* **CLI version.** CI pins a known-good MCPB CLI version for reproducible
  builds; if your locally installed CLI is much newer, the manifest schema it
  validates against may differ slightly.

See ``mcpb/README.md`` in the repository for the full rebuild and dependency
notes.

Claude Desktop (manual configuration)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For development, or to control the exact flags, configure the server directly
in ``claude_desktop_config.json``:

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

   from all2md.mcp import MCPConfig
   from all2md.mcp.server import create_server
   from all2md.mcp.document_tools import edit_document_impl
   from all2md.mcp.query_tools import (
       diff_documents_impl,
       get_document_outline_impl,
       search_documents_impl,
   )
   from all2md.mcp.security import prepare_allowlist_dirs
   from all2md.mcp.tools import read_document_as_markdown_impl, save_document_from_markdown_impl

   # Create custom configuration
   config = MCPConfig(
       enable_to_md=True,
       enable_from_md=False,
       enable_doc_edit=False,
       enable_search=True,
       enable_diff=True,
       enable_outline=True,
       read_allowlist=prepare_allowlist_dirs(["/safe/documents"]),
       write_allowlist=prepare_allowlist_dirs(["/safe/output"]),
       include_images=True,
       flavor="gfm",
       disable_network=True,
       log_level="INFO"
   )

   # Create MCP server with custom config
   mcp = create_server(
       config,
       read_document_as_markdown_impl,
       save_document_from_markdown_impl,
       edit_document_impl,
       search_documents_impl,
       diff_documents_impl,
       get_document_outline_impl,
   )

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

Image inclusion is **off by default** (it inflates responses); enable it so a
vision-capable client can see embedded images:

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
