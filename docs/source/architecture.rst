Architecture Overview
=====================

This document provides a high-level overview of all2md's architecture, data flow, and extension points. It's designed to help new contributors understand the system and guide implementation decisions.

.. contents::
   :local:
   :depth: 3

System Architecture
-------------------

all2md uses a modular architecture built around three core concepts:

1. **Parsers:** Convert input formats to AST (Abstract Syntax Tree)
2. **AST:** Unified document representation
3. **Renderers:** Convert AST to output formats

This design enables bidirectional conversion and consistent document transformation regardless of input/output format combinations.

High-Level Data Flow
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   ┌─────────────────────────────────────────────────────────────┐
   │                     CLI / Public API                        │
   │                  (all2md/__init__.py)                       │
   │                                                             │
   │  Entry points:                                              │
   │  • to_markdown(source, *, source_format="auto", ...)        │
   │  • to_ast(source, *, source_format="auto", ...)             │
   │  • from_ast(ast_doc, target_format, output=None, ...)       │
   │  • convert(source, output=None, *, source_format="auto",    │
   │    target_format="auto", ...)                               │
   │  • from_markdown(source, target_format, output=None, ...)   │
   └────────────────┬────────────────────────────────────────────┘
                    │
                    ├─── Format Detection ───────────────────────┐
                    │    (MIME, extension, magic bytes)          │
                    │                                            │
                    ▼                                            │
   ┌─────────────────────────────────────────────────────────────┤
   │            Converter Registry Discovery                     │
   │           (converter_registry.py)                           │
   │                                                             │
   │  • Auto-discovers parsers via entry points                  │
   │  • Maps formats to parser/renderer classes                  │
   │  • Provides metadata about capabilities                     │
   └────────────────┬────────────────────────────────────────────┘
                    │
                    ▼
   ┌─────────────────────────────────────────────────────────────┐
   │              Parser Selection & Execution                   │
   │       (parsers/pdf.py, html.py, docx.py, etc.)              │
   │                                                             │
   │  Each parser:                                               │
   │  • Inherits from BaseParser                                 │
   │  • Accepts format-specific options                          │
   │  • Converts input → AST                                     │
   └────────────────┬────────────────────────────────────────────┘
                    │
                    ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                  AST Representation                         │
   │                    (ast/nodes.py)                           │
   │                                                             │
   │  Unified node types:                                        │
   │  • Document, Heading, Paragraph                             │
   │  • Text, Link, Image, Code, CodeBlock                       │
   │  • Table, List, BlockQuote                                  │
   │  • FootnoteDefinition, FootnoteReference                    │
   └────────────────┬────────────────────────────────────────────┘
                    │
                    ├─── Optional Transform Pipeline ────────────┐
                    │    (transforms/pipeline.py)                │
                    │                                            │
                    ▼                                            │
   ┌─────────────────────────────────────────────────────────────┤
   │            Transform Pipeline (Optional)                    │
   │         (transforms/pipeline.py + builtin.py)               │
   │                                                             │
   │  • Chain multiple transforms                                │
   │  • Execute hooks before/after                               │
   │  • Modify AST programmatically                              │
   │                                                             │
   │  Built-in transforms:                                       │
   │  • RemoveImagesTransform                                    │
   │  • HeadingOffsetTransform                                   │
   │  • AddHeadingIdsTransform                                   │
   │  • LinkRewriterTransform                                    │
   │  • AddAttachmentFootnotesTransform                          │
   └────────────────┬────────────────────────────────────────────┘
                    │
                    ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                 Renderer Selection                          │
   │       (renderers/markdown.py, docx.py, etc.)                │
   │                                                             │
   │  Each renderer:                                             │
   │  • Inherits from BaseRenderer                               │
   │  • Accepts format-specific options                          │
   │  • Converts AST → Output format                             │
   └────────────────┬────────────────────────────────────────────┘
                    │
                    ▼
                  Output
              (Markdown, DOCX, HTML, PDF, etc.)

Core Components
---------------

1. Public API Layer
~~~~~~~~~~~~~~~~~~~

**Location:** ``src/all2md/api.py`` (re-exported from ``src/all2md/__init__.py``)

**Key Functions:**

.. code-block:: python

   # Primary conversion functions
   to_markdown(source, *, source_format="auto", parser_options=None,
               renderer_options=None, flavor=None, transforms=None,
               hooks=None, progress_callback=None, remote_input_options=None, **kwargs)

   to_ast(source, *, source_format="auto", parser_options=None,
          progress_callback=None, remote_input_options=None, **kwargs)

   from_ast(ast_doc, target_format, output=None, *, renderer_options=None,
            transforms=None, hooks=None, progress_callback=None, **kwargs)

   convert(source, output=None, *, source_format="auto", target_format="auto",
           parser_options=None, renderer_options=None, transforms=None,
           hooks=None, flavor=None, progress_callback=None,
           remote_input_options=None, **kwargs)

   from_markdown(source, target_format, output=None, *, parser_options=None,
                 renderer_options=None, transforms=None, hooks=None,
                 progress_callback=None, **kwargs)

**Responsibilities:**

* Provide simple public interface
* Delegate to converter registry for format detection
* Route to appropriate parser/renderer
* Handle options merging (CLI → JSON → defaults)

**Data Flow:**

1. Accept input (path, bytes, file-like, or document object)
2. Detect format (if ``format="auto"``)
3. Load appropriate parser from registry
4. Execute parser with options
5. Optionally apply transforms
6. Load appropriate renderer from registry
7. Execute renderer with options
8. Return output

---

2. Converter Registry
~~~~~~~~~~~~~~~~~~~~~~

**Location:** ``src/all2md/converter_registry.py``

**Purpose:** Central registry for discovering and accessing parsers/renderers

**Key Features:**

* **Auto-discovery:** Finds parsers via Python entry points
* **Metadata storage:** Tracks format capabilities, options classes, dependencies
* **Dynamic loading:** Only imports parsers when needed (lazy loading)
* **Extensibility:** Third-party packages can register converters

**Registry Structure:**

.. code-block:: python

   class ConverterRegistry:
       def auto_discover(self):
           """Discover all converters via entry points"""

       def register_converter(self, format_name, metadata):
           """Register a converter manually"""

       def get_parser_class(self, format_name):
           """Get parser class for format"""

       def get_renderer_class(self, format_name):
           """Get renderer class for format"""

       def get_parser_options_class(self, format_name):
           """Get options dataclass for format"""

**Entry Point Example:**

.. code-block:: toml

   # pyproject.toml
   [project.entry-points."all2md.converters"]
   pdf = "all2md.parsers.pdf:CONVERTER_METADATA"
   html = "all2md.parsers.html:CONVERTER_METADATA"

---

3. Parsers
~~~~~~~~~~

**Location:** ``src/all2md/parsers/``

**Base Class:** ``BaseParser``

**Available Parsers (highlights):**

* ``pdf.py`` – PDF via PyMuPDF with table/column heuristics
* ``docx.py`` / ``pptx.py`` – Microsoft Office documents via python-docx / python-pptx
* ``html.py`` / ``mhtml.py`` – HTML and web archives via BeautifulSoup + MIME parsing
* ``asciidoc.py`` / ``markdown.py`` / ``rst.py`` / ``latex.py`` – markup languages (AsciiDoc, Markdown, reStructuredText, LaTeX)
* ``org.py`` – Org-mode documents via orgparse
* ``epub.py`` – EPUB containers via ebooklib
* ``eml.py`` – Email threads with attachment extraction
* ``xlsx.py`` / ``ods_spreadsheet.py`` / ``csv.py`` – Spreadsheet and tabular data via openpyxl/odfpy/builtins
* ``odt.py`` / ``odp.py`` – OpenDocument text and presentations via odfpy
* ``ipynb.py`` – Jupyter notebooks via nbformat
* ``rtf.py`` – RTF via pyth3
* ``chm.py`` – Compiled HTML Help archives
* ``sourcecode.py`` / ``plaintext.py`` – Code and plain-text lexers (200+ formats)
* ``zip.py`` – Mixed archives with per-entry detection
* ``ast_json.py`` – Developer-facing AST JSON interchange

**Parser Interface:**

.. code-block:: python

   class BaseParser:
       def __init__(self, options: BaseParserOptions):
           self.options = options

       def parse(self, input_data) -> Document:
           """Convert input to AST Document"""
           raise NotImplementedError

       def extract_metadata(self, input_data) -> DocumentMetadata:
           """Extract document metadata"""
           return DocumentMetadata()

**Parser Responsibilities:**

1. Accept input in various formats (path, bytes, file-like)
2. Validate input using ``utils/inputs.py`` helpers
3. Parse format-specific structure
4. Build AST using ``ast/nodes.py`` classes
5. Handle attachments (images, files) via ``utils/attachments.py``
6. Apply security validation (network, local files, ZIP)
7. Return Document node

**Example Parser Flow:**

.. code-block:: python

   # PDF Parser simplified flow
   def parse(self, input_data):
       # 1. Validate input
       doc = self._open_pdf(input_data)

       # 2. Extract pages
       ast_children = []
       for page in doc:
           # 3. Extract text with formatting
           blocks = self._extract_blocks(page)

           # 4. Build AST nodes
           for block in blocks:
               if block.type == "heading":
                   ast_children.append(Heading(...))
               elif block.type == "paragraph":
                   ast_children.append(Paragraph(...))

       # 5. Return Document
       return Document(children=ast_children)

---

4. AST (Abstract Syntax Tree)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Location:** ``src/all2md/ast/``

**Core Modules:**

* ``nodes.py`` - Node class definitions
* ``builder.py`` - Helper functions for building AST
* ``visitors.py`` - Tree traversal utilities
* ``transforms.py`` - Node transformation base classes
* ``serialization.py`` - JSON serialization

**Node Hierarchy:**

.. code-block:: text

   Node (base)
   ├── Document
   ├── Block Nodes
   │   ├── Heading
   │   ├── Paragraph
   │   ├── CodeBlock
   │   ├── BlockQuote
   │   ├── List
   │   ├── ListItem
   │   ├── Table
   │   ├── TableRow
   │   ├── TableCell
   │   ├── ThematicBreak
   │   ├── HTMLBlock
   │   ├── MathBlock
   │   ├── FootnoteDefinition
   │   ├── DefinitionList
   │   ├── DefinitionTerm
   │   └── DefinitionDescription
   └── Inline Nodes
       ├── Text
       ├── Link
       ├── Image
       ├── Code
       ├── Strong
       ├── Emphasis
       ├── Strikethrough
       ├── LineBreak
       ├── HTMLInline
       ├── MathInline
       └── FootnoteReference

**Node Structure:**

All nodes inherit from ``Node`` base class:

.. code-block:: python

   @dataclass
   class Node:
       metadata: dict = field(default_factory=dict)
       source_location: SourceLocation | None = None

   @dataclass
   class Paragraph(Node):
       content: list[Node] = field(default_factory=list)  # Inline nodes

   @dataclass
   class Heading(Node):
       level: int = 1
       content: list[Node] = field(default_factory=list)  # Inline nodes
       # metadata['id'] can be set by transforms like AddHeadingIdsTransform

**Key Features:**

* **Immutability:** Nodes are dataclasses (use ``replace()`` for modifications)
* **Type Safety:** Full type hints for all fields
* **Extensibility:** Metadata dict for format-specific data
* **Source Tracking:** Optional source_location for debugging

---

5. Transform Pipeline
~~~~~~~~~~~~~~~~~~~~~

**Location:** ``src/all2md/transforms/``

**Purpose:** Programmatic AST manipulation

**Components:**

* ``pipeline.py`` - Pipeline execution engine
* ``builtin.py`` - Built-in transforms
* ``registry.py`` - Transform discovery
* ``hooks.py`` - Hook system for element-level transforms
* ``metadata.py`` - Transform metadata and parameter specs

**Transform Types:**

1. **Visitor-based Transforms** (modify entire tree):

   .. code-block:: python

      class RemoveImagesTransform(NodeTransformer):
          def visit_image(self, node: Image) -> None:
              return None  # Remove image

2. **Hook-based Transforms** (modify specific elements):

   .. code-block:: python

      def uppercase_headings(node: Heading, context: HookContext) -> Heading:
          # Modify heading text to uppercase
          return replace_heading_text(node, text.upper())

      # Register hook
      hooks.register_element_hook('heading', uppercase_headings)

**Built-in Transforms:**

* ``RemoveImagesTransform`` - Remove all images
* ``RemoveNodesTransform`` - Remove specific node types
* ``HeadingOffsetTransform`` - Shift heading levels
* ``LinkRewriterTransform`` - Rewrite URLs with regex
* ``TextReplacerTransform`` - Find/replace text
* ``AddHeadingIdsTransform`` - Generate heading IDs
* ``RemoveBoilerplateTextTransform`` - Remove boilerplate
* ``AddConversionTimestampTransform`` - Add timestamp to metadata
* ``CalculateWordCountTransform`` - Calculate word count
* ``AddAttachmentFootnotesTransform`` - Add footnote definitions

**Pipeline Example:**

.. code-block:: python

   from all2md.transforms import Pipeline
   from all2md.transforms.builtin import (
       RemoveImagesTransform,
       HeadingOffsetTransform
   )

   # Create pipeline
   pipeline = Pipeline([
       RemoveImagesTransform(),
       HeadingOffsetTransform(offset=1)
   ])

   # Apply to AST
   modified_ast = pipeline.apply(original_ast)

---

6. Renderers
~~~~~~~~~~~~

**Location:** ``src/all2md/renderers/``

**Base Class:** ``BaseRenderer``

**Available Renderers:**

* ``markdown.py`` - Markdown (CommonMark, GFM, custom flavors)
* ``docx.py`` - Word documents (requires python-docx)
* ``html.py`` - HTML
* ``pdf.py`` - PDF (requires reportlab)
* ``pptx.py`` - PowerPoint (requires python-pptx)
* ``epub.py`` - EPUB e-books (requires ebooklib)
* ``rst.py`` - reStructuredText
* ``asciidoc.py`` - AsciiDoc
* ``latex.py`` - LaTeX
* ``mediawiki.py`` - MediaWiki
* ``org.py`` - Org-Mode
* ``plaintext.py`` - Plain text
* ``ipynb.py`` - Jupyter notebooks
* ``rtf.py`` - Rich Text Format (requires pyth3)
* ``ast_json.py`` - JSON AST format

**Renderer Interface:**

.. code-block:: python

   class BaseRenderer:
       def __init__(self, options: BaseRendererOptions | None = None):
           self.options = options

       def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
           """Write rendered AST to output file or stream"""
           raise NotImplementedError

       def render_to_string(self, doc: Document) -> str:
           """Render AST to string (for text-based formats)"""
           raise NotImplementedError

       def render_to_bytes(self, doc: Document) -> bytes:
           """Render AST to bytes (for binary formats)"""
           raise NotImplementedError

**Renderer Responsibilities:**

1. Accept AST Document
2. Traverse tree using visitor pattern
3. Generate format-specific output
4. Handle formatting options (heading style, list symbols, etc.)
5. Write output to file/stream (``render()``) or return directly (``render_to_string()`` / ``render_to_bytes()``)

**Example Renderer Flow:**

.. code-block:: python

   # Markdown Renderer simplified
   def render_to_string(self, document: Document) -> str:
       output = []

       for node in document.children:
           if isinstance(node, Heading):
               output.append(self._render_heading(node))
           elif isinstance(node, Paragraph):
               output.append(self._render_paragraph(node))

       return "\n".join(output)

   def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
       content = self.render_to_string(doc)
       self.write_text_output(content, output)

---

Options Architecture
--------------------

all2md uses a cascading options system with dataclasses:

Options Hierarchy
~~~~~~~~~~~~~~~~~

.. code-block:: text

   BaseParserOptions (universal)
   ├── attachment_mode
   ├── attachment_output_dir
   ├── alt_text_mode
   └── markdown_options (MarkdownRendererOptions)

   Format-Specific Options (inherit from BaseParserOptions)
   ├── HtmlOptions
   │   ├── strip_dangerous_elements
   │   ├── preserve_tables
   │   ├── network (NetworkFetchOptions)
   │   └── local_files (LocalFileAccessOptions)
   ├── PdfOptions
   │   ├── pages
   │   ├── extract_images
   │   └── detect_columns
   ├── DocxOptions
   │   ├── include_comments
   │   └── include_footnotes
   ├── EmlOptions
   │   ├── network (NetworkFetchOptions)
   │   └── local_files (LocalFileAccessOptions)
   └── (other format options...)

**Nested Options:**

Some options are themselves dataclasses:

.. code-block:: python

   @dataclass
   class NetworkFetchOptions:
       allow_remote_fetch: bool = False
       allowed_hosts: list[str] | None = None
       require_https: bool = True
       network_timeout: float = 10.0
       max_remote_asset_bytes: int = 10 * 1024 * 1024

   @dataclass
   class LocalFileAccessOptions:
       allow_local_files: bool = False
       allow_cwd_files: bool = False
       local_file_allowlist: list[str] | None = None
       local_file_denylist: list[str] | None = None

**Options Cascade:**

1. **Defaults:** Defined in dataclass field defaults
2. **Config File:** Loaded from ``--config`` file (JSON or TOML)
3. **CLI Arguments:** Highest priority, override config/defaults

**CLI Mapping:**

The CLI builder uses dot notation for nested options:

.. code-block:: bash

   # Maps to: HtmlOptions(network=NetworkFetchOptions(allowed_hosts=[...]))
   all2md doc.html --html-network-allowed-hosts cdn.example.com

---

Extension Points
----------------

all2md is designed for extensibility. Here are the main extension points:

1. Custom Parsers
~~~~~~~~~~~~~~~~~

Create a custom parser for a new format:

.. code-block:: python

   # my_package/parsers/custom.py
   from all2md.parsers.base import BaseParser
   from all2md.ast import Document, Paragraph, Text

   class CustomParser(BaseParser):
       def parse(self, input_data) -> Document:
           # Your parsing logic
           return Document(children=[
               Paragraph(content=[Text(content="Parsed!")])
           ])

   # Register via entry point in pyproject.toml
   [project.entry-points."all2md.converters"]
   custom = "my_package.parsers.custom:CONVERTER_METADATA"

2. Custom Renderers
~~~~~~~~~~~~~~~~~~~

Create a custom renderer for a new output format:

.. code-block:: python

   # my_package/renderers/custom.py
   from all2md.renderers.base import BaseRenderer
   from all2md.ast import Document

   class CustomRenderer(BaseRenderer):
       def render(self, document: Document) -> str:
           # Your rendering logic
           return "Custom output"

   # Register via converter metadata
   from all2md.converter_metadata import ConverterMetadata

   metadata = ConverterMetadata(
       format_name="custom",
       renderer_class=CustomRenderer,
       renderer_options_class=CustomOptions,
       renders_as_string=True
   )

3. Custom Transforms
~~~~~~~~~~~~~~~~~~~~

Create a custom transform:

.. code-block:: python

   # my_package/transforms/custom.py
   from all2md.ast.transforms import NodeTransformer
   from all2md.ast import Heading, Text

   class CustomTransform(NodeTransformer):
       def visit_heading(self, node: Heading) -> Heading:
           # Add emoji to headings
           new_content = [Text(content="📝 ")] + node.content
           return Heading(level=node.level, content=new_content)

   # Register via entry point
   [project.entry-points."all2md.transforms"]
   custom = "my_package.transforms.custom:CustomTransform"

4. Element Hooks
~~~~~~~~~~~~~~~~

Register hooks for specific elements:

.. code-block:: python

   from all2md.transforms.hooks import HookContext
   from all2md.ast import Image

   def watermark_images(node: Image, context: HookContext) -> Image:
       # Add watermark to image alt text
       new_alt = f"{node.alt_text} [Watermarked]"
       return Image(url=node.url, alt_text=new_alt, title=node.title)

   # Register hook
   from all2md.transforms import HookManager

   manager = HookManager()
   manager.register_hook('image', watermark_images)

See :doc:`plugins` for detailed plugin development guide.

---

Dependency Management
---------------------

all2md uses optional dependencies grouped by format:

**Core (always installed):**

* None - core uses only stdlib

**Optional Groups:**

* ``[pdf]`` - PyMuPDF
* ``[docx]`` - python-docx, lxml
* ``[pptx]`` - python-pptx
* ``[html]`` - beautifulsoup4, httpx, readability-lxml
* ``[excel]`` - openpyxl
* ``[odf]`` - odfpy
* ``[epub]`` - ebooklib
* ``[eml]`` - (stdlib email package)
* ``[rtf]`` - pyth3
* ``[markdown]`` - mistune
* ``[all]`` - All of the above

**Lazy Loading:**

Parsers are only imported when used. If a format's dependencies aren't installed, a helpful error message is shown:

.. code-block:: python

   from all2md.exceptions import DependencyError

   try:
       import PyMuPDF
   except ImportError as e:
       raise DependencyError(
           converter_name="pdf",
           missing_packages=[("PyMuPDF", ">=1.23.0")],
           install_command="pip install 'all2md[pdf]'"
       ) from e

---

Testing Architecture
--------------------

all2md uses pytest with multiple test categories:

**Test Organization:**

.. code-block:: text

   tests/
   ├── unit/              # Fast, isolated tests
   │   ├── test_pdf2markdown.py
   │   ├── test_html_ast.py
   │   ├── test_docx_ast.py
   │   ├── test_security.py
   │   └── ...
   ├── integration/       # Multi-component tests
   │   ├── test_full_conversion_pipeline.py
   │   ├── test_transform_pipeline.py
   │   └── ...
   └── e2e/               # End-to-end CLI tests
       ├── test_cli_e2e.py
       └── ...

**Test Markers:**

.. code-block:: python

   @pytest.mark.unit        # Fast unit tests
   @pytest.mark.integration # Integration tests
   @pytest.mark.e2e         # End-to-end tests
   @pytest.mark.slow        # Slow tests (skip in CI)
   @pytest.mark.pdf         # PDF-specific tests
   @pytest.mark.docx        # DOCX-specific tests
   # ... etc

**Run Specific Tests:**

.. code-block:: bash

   # All tests
   pytest

   # Only unit tests (fast)
   pytest -m unit

   # Only PDF tests
   pytest -m pdf

   # Exclude slow tests
   pytest -m "not slow"

---

Performance Considerations
--------------------------

Memory Management
~~~~~~~~~~~~~~~~~

* **Streaming:** Large files are processed in chunks where possible
* **Lazy Loading:** Parsers/renderers only imported when needed
* **AST Size:** AST representation is memory-efficient (dataclasses, minimal overhead)

Optimization Strategies
~~~~~~~~~~~~~~~~~~~~~~~

1. **Caching:** Converter registry caches discovered parsers
2. **Parallel Processing:** Application can process multiple documents in parallel
3. **Profiling:** Use ``cProfile`` to identify bottlenecks

**Example Profiling:**

.. code-block:: python

   import cProfile
   import pstats

   profiler = cProfile.Profile()
   profiler.enable()

   result = to_markdown("large_document.pdf")

   profiler.disable()
   stats = pstats.Stats(profiler)
   stats.sort_stats('cumulative')
   stats.print_stats(20)  # Top 20 functions

---

See Also
--------

* :doc:`plugins` - Creating custom converters and transforms
* :doc:`transforms` - Transform system details
* :doc:`ast_guide` - AST structure and manipulation
* :doc:`security` - Security architecture
* :doc:`threat_model` - Threat model and attack vectors
