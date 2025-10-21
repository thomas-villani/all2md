Plugin Development Guide
========================

Overview
--------

The ``all2md`` library supports a plugin system that allows third-party developers to add support for additional document formats without modifying the core library. This system uses Python entry points to automatically discover and register converter plugins.

Plugin Architecture
-------------------

The plugin system is built around two key components:

1. **ConverterMetadata**: A data class that describes the converter's capabilities
2. **Entry Points**: Python packaging mechanism for plugin discovery

When ``all2md`` starts up, it automatically scans for plugins registered under the ``all2md.converters`` entry point group and loads their metadata. This enables seamless integration of custom formats.

Creating a Plugin
------------------

Basic Plugin Structure
~~~~~~~~~~~~~~~~~~~~~~~

A typical plugin package should have the following structure:

.. code-block::

    all2md_myformat/
    ├── pyproject.toml          # Package configuration with entry point
    ├── README.md               # Documentation
    ├── LICENSE                 # License file
    └── src/
        └── all2md_myformat/
            ├── __init__.py     # Metadata registration
            ├── parser.py       # Parser implementation
            ├── renderer.py     # Renderer implementation (optional)
            └── options.py      # Configuration options

Complete Plugin Walkthrough
----------------------------

The best way to learn plugin development is to study a complete, working example. The ``simpledoc-plugin`` in the ``examples/`` directory demonstrates all aspects of building a bidirectional converter plugin.

**SimpleDoc** is a lightweight markup format created specifically for this example. It supports:

- Frontmatter metadata (YAML-style between ``---`` delimiters)
- Headings (lines starting with ``@@``)
- Lists (lines starting with ``-``)
- Code blocks (triple backticks)
- Paragraphs (separated by blank lines)

The complete simpledoc-plugin source is available at:
``examples/simpledoc-plugin/``

Parser Implementation
~~~~~~~~~~~~~~~~~~~~~

A parser converts your format into the all2md AST (Abstract Syntax Tree). Here's how the SimpleDoc parser implements the core ``parse()`` method:

.. literalinclude:: ../../examples/simpledoc-plugin/src/all2md_simpledoc/parser.py
   :language: python
   :lines: 51-93
   :linenos:
   :emphasize-lines: 20-22,24-25,31-33,35-36,38-39,41-43
   :caption: SimpleDocParser.parse() - Main parsing entry point

Key parser patterns demonstrated:

1. **Progress tracking**: Use ``_emit_progress()`` for CLI feedback
2. **Two-phase parsing**: Separate metadata extraction from content parsing
3. **Error handling**: Wrap in try/except and raise ``ParsingError``
4. **Input flexibility**: Handle str, Path, IO[bytes], and bytes

Input Type Handling
^^^^^^^^^^^^^^^^^^^

The parser must handle multiple input types uniformly:

.. literalinclude:: ../../examples/simpledoc-plugin/src/all2md_simpledoc/parser.py
   :language: python
   :lines: 102-134
   :linenos:
   :emphasize-lines: 15-16,18-20,23,26-28
   :caption: SimpleDocParser._read_content() - Multi-format input handling

Content Parsing
^^^^^^^^^^^^^^^

The core parsing logic uses a line-by-line state machine approach:

.. literalinclude:: ../../examples/simpledoc-plugin/src/all2md_simpledoc/parser.py
   :language: python
   :lines: 213-272
   :linenos:
   :emphasize-lines: 15-16,29-30,32-34,39-40,47-48,54
   :caption: SimpleDocParser._parse_content() - State machine parser

The parser demonstrates:

- **Pattern matching**: Check line prefixes to determine block type
- **Look-ahead parsing**: Pass remaining lines to sub-parsers
- **Option-driven behavior**: Respect user configuration
- **Clean separation**: Each block type has its own parser method

Metadata Extraction
^^^^^^^^^^^^^^^^^^^

Metadata can be extracted separately from full parsing:

.. literalinclude:: ../../examples/simpledoc-plugin/src/all2md_simpledoc/parser.py
   :language: python
   :lines: 136-211
   :linenos:
   :emphasize-lines: 17-18,21-22,26-29,34-39,44-49,56-66
   :caption: SimpleDocParser._extract_frontmatter() - Metadata parsing

Renderer Implementation
~~~~~~~~~~~~~~~~~~~~~~~

A renderer converts the all2md AST back into your format. The SimpleDoc renderer uses the visitor pattern:

.. literalinclude:: ../../examples/simpledoc-plugin/src/all2md_simpledoc/renderer.py
   :language: python
   :lines: 52-105
   :linenos:
   :emphasize-lines: 24-26,29-30,47-54
   :caption: SimpleDocRenderer - Core rendering structure

Visitor Pattern Basics
^^^^^^^^^^^^^^^^^^^^^^

The renderer implements ``visit_*()`` methods for each AST node type:

.. literalinclude:: ../../examples/simpledoc-plugin/src/all2md_simpledoc/renderer.py
   :language: python
   :lines: 121-141
   :linenos:
   :emphasize-lines: 10-12,14-16,18-21
   :caption: SimpleDocRenderer.visit_document() - Visitor pattern dispatch

Inline Content Rendering
^^^^^^^^^^^^^^^^^^^^^^^^^

Use the ``InlineContentMixin`` helper for inline nodes:

.. literalinclude:: ../../examples/simpledoc-plugin/src/all2md_simpledoc/renderer.py
   :language: python
   :lines: 181-194
   :linenos:
   :emphasize-lines: 10-14
   :caption: SimpleDocRenderer.visit_heading() - Inline content extraction

Renderer Implementation Patterns
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When implementing a renderer plugin, you must provide ``visit_*()`` methods for **all** AST node types, even if your format doesn't support them. There are three standard patterns for handling unsupported nodes:

Pattern 1: Extract Content from Formatting Nodes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For nodes that represent formatting your format doesn't support (bold, italic, strikethrough, underline, superscript, subscript), **extract and render the text content**:

.. literalinclude:: ../../examples/simpledoc-plugin/src/all2md_simpledoc/renderer.py
   :language: python
   :lines: 343-358
   :linenos:
   :emphasize-lines: 12-16
   :caption: Handling unsupported formatting - Extract text content

This preserves the text content even if the formatting is lost. Apply this pattern to:

- ``Strong`` (bold)
- ``Emphasis`` (italic)
- ``Strikethrough``
- ``Underline``
- ``Superscript``
- ``Subscript``
- ``Code`` (inline code)

Pattern 2: Provide Simplified Representation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For elements that have some meaningful equivalent, provide a simplified representation:

.. literalinclude:: ../../examples/simpledoc-plugin/src/all2md_simpledoc/renderer.py
   :language: python
   :lines: 387-403
   :linenos:
   :emphasize-lines: 13-17
   :caption: Handling links - Include URL in plain text

.. literalinclude:: ../../examples/simpledoc-plugin/src/all2md_simpledoc/renderer.py
   :language: python
   :lines: 284-319
   :linenos:
   :emphasize-lines: 13-14,17-26,28-36
   :caption: Handling tables - Simplified text representation

This approach preserves information even if not in ideal format. Apply this pattern to:

- ``Link`` - Include URL in parentheses
- ``Image`` - Show alt text or description
- ``Table`` - Render as formatted text
- ``DefinitionList`` - Render as key-value pairs
- ``BlockQuote`` - Render children as-is or with prefix

Pattern 3: Skip Unsupported Elements
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For elements your format truly cannot represent, use ``pass`` with clear documentation:

.. literalinclude:: ../../examples/simpledoc-plugin/src/all2md_simpledoc/renderer.py
   :language: python
   :lines: 526-542
   :linenos:
   :emphasize-lines: 14-17
   :caption: Handling HTML blocks - Skip entirely

**Always document why** you're skipping an element. Don't leave empty methods unexplained. Apply this pattern to:

- ``HTMLBlock`` / ``HTMLInline`` - Raw HTML
- ``FootnoteReference`` / ``FootnoteDefinition`` - Footnotes
- ``MathInline`` / ``MathBlock`` - Mathematical notation
- ``ThematicBreak`` - Horizontal rule (if no equivalent)

Pattern 4: Parent-Handled Structural Nodes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some nodes are only rendered as part of their parent:

.. literalinclude:: ../../examples/simpledoc-plugin/src/all2md_simpledoc/renderer.py
   :language: python
   :lines: 495-510
   :linenos:
   :emphasize-lines: 13-16
   :caption: Structural nodes handled by parent

Apply this pattern to:

- ``TableCell`` - Handled by ``visit_table``
- ``TableRow`` - Handled by ``visit_table``
- ``DefinitionTerm`` / ``DefinitionDescription`` - Handled by ``visit_definition_list``

Options Classes
~~~~~~~~~~~~~~~

Define custom options for parser and renderer configuration:

.. literalinclude:: ../../examples/simpledoc-plugin/src/all2md_simpledoc/options.py
   :language: python
   :lines: 15-70
   :linenos:
   :emphasize-lines: 1-3,25-28,29-35
   :caption: SimpleDocOptions - Parser configuration with CLI integration

Key patterns:

- **Frozen dataclass**: Use ``frozen=True`` for immutability
- **Field metadata**: Enables automatic CLI flag generation
- **Validation**: Use ``__post_init__`` for validation

.. literalinclude:: ../../examples/simpledoc-plugin/src/all2md_simpledoc/options.py
   :language: python
   :lines: 131-158
   :linenos:
   :emphasize-lines: 1-3,13-14,16-21,23-28
   :caption: __post_init__ validation pattern

Metadata Registration
~~~~~~~~~~~~~~~~~~~~~

The ``ConverterMetadata`` object is the key to plugin discovery:

.. literalinclude:: ../../examples/simpledoc-plugin/src/all2md_simpledoc/__init__.py
   :language: python
   :lines: 43-108
   :linenos:
   :emphasize-lines: 1-3,5-7,17-23,25-27,51-53
   :caption: CONVERTER_METADATA - Plugin registration

Key fields:

- ``format_name``: Unique identifier (used in CLI and API)
- ``extensions``: File extensions for auto-detection
- ``mime_types``: MIME types for web/HTTP detection
- ``magic_bytes``: Binary signatures for content-based detection
- ``parser_class`` / ``renderer_class``: Implementation classes
- ``parser_options_class`` / ``renderer_options_class``: Configuration classes
- ``parser_required_packages``: Dependencies as ``(pip_name, import_name, version_spec)`` tuples
- ``priority``: Detection order (0-10, higher = checked first)

Package Configuration
~~~~~~~~~~~~~~~~~~~~~

Register your plugin via entry points in ``pyproject.toml``:

.. literalinclude:: ../../examples/simpledoc-plugin/pyproject.toml
   :language: toml
   :lines: 1-38
   :linenos:
   :emphasize-lines: 1-3,5-14,24-26,33-35
   :caption: pyproject.toml - Package configuration with entry point

The critical element is the entry point:

.. code-block:: toml

    [project.entry-points."all2md.converters"]
    simpledoc = "all2md_simpledoc:CONVERTER_METADATA"

This tells all2md to load ``CONVERTER_METADATA`` from the ``all2md_simpledoc`` package when discovering plugins.

Advanced Features
-----------------

Custom Options Classes
~~~~~~~~~~~~~~~~~~~~~~~

For complex converters, you may want to define custom options. The ``parser_options_class``
and ``renderer_options_class`` attributes in ``ConverterMetadata`` support two ways to
specify options classes:

**Method 1: Direct Class Reference (Recommended)**

Pass the class object directly:

.. code-block:: python

    from all2md.options import BaseParserOptions

    CONVERTER_METADATA = ConverterMetadata(
        # ... other fields ...
        parser_options_class=BaseParserOptions,  # Direct class reference
        renderer_options_class=MarkdownOptions,
        # ... rest of metadata ...
    )

**Method 2: Fully Qualified Class Name (String)**

Use a string with the full module path:

.. code-block:: python

    CONVERTER_METADATA = ConverterMetadata(
        # ... other fields ...
        parser_options_class="all2md.options.BaseParserOptions",  # String reference
        renderer_options_class="all2md.options.markdown.MarkdownOptions",
        # ... rest of metadata ...
    )

**Creating Custom Options**

For custom options classes in your plugin package:

.. code-block:: python

    # all2md_myformat/options.py
    from dataclasses import dataclass, field
    from all2md.options.base import BaseParserOptions

    @dataclass(frozen=True)
    class MyFormatOptions(BaseParserOptions):
        """Options for MyFormat conversion."""

        extract_metadata: bool = field(
            default=True,
            metadata={"help": "Extract document metadata"}
        )
        preserve_formatting: bool = field(
            default=False,
            metadata={"help": "Preserve original formatting"}
        )
        custom_parser_mode: str = field(
            default="strict",
            metadata={"help": "Parser mode: strict, lenient, or auto"}
        )

Then reference it in your metadata (either direct or string reference):

.. code-block:: python

    from all2md_myformat.options import MyFormatOptions

    CONVERTER_METADATA = ConverterMetadata(
        # ... other fields ...
        parser_options_class=MyFormatOptions,  # Direct reference
        # Or: parser_options_class="all2md_myformat.options.MyFormatOptions",
        # ... rest of metadata ...
    )

Error Handling
~~~~~~~~~~~~~~

Implement robust error handling in your parser class:

.. code-block:: python

    from all2md.exceptions import DependencyError, ParsingError
    from all2md.utils.decorators import requires_dependencies

    class MyFormatParser(BaseParser):
        """Parser with proper error handling."""

        @requires_dependencies("myformat", [("myformat-lib", "myformat_lib", ">=1.0")])
        def parse(self, input_data):
            """Parse with dependency checking via decorator.

            The @requires_dependencies decorator automatically raises DependencyError
            with correct parameters if the required packages are missing.
            """
            try:
                # Your conversion logic
                pass
            except Exception as e:
                raise ParsingError(
                    f"Failed to convert MyFormat document: {e}",
                    parsing_stage="parsing",
                    original_error=e
                ) from e

        def extract_metadata(self, document):
            """Extract metadata with error handling."""
            try:
                # Metadata extraction logic
                return DocumentMetadata()
            except Exception as e:
                # Log but don't fail - return empty metadata on error
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to extract metadata: {e}")
                return DocumentMetadata()

**Manual Dependency Error Handling**

If you need to manually raise ``DependencyError`` (not recommended - use the decorator instead):

.. code-block:: python

    try:
        import myformat_lib
    except ImportError as e:
        raise DependencyError(
            converter_name="myformat",
            missing_packages=[("myformat-lib", "myformat_lib", ">=1.0")],
            version_mismatches=None,
            install_command="pip install 'myformat-lib>=1.0'",
            message=None,
            original_import_error=e  # Note: parameter name is original_import_error
        ) from e

Format Detection
~~~~~~~~~~~~~~~~

The plugin system supports multiple format detection methods:

1. **File extensions**: Listed in ``extensions`` field
2. **MIME types**: Listed in ``mime_types`` field
3. **Magic bytes**: Binary signatures in ``magic_bytes`` field
4. **Priority**: Higher priority converters are checked first

Example magic bytes patterns:

.. code-block:: python

    magic_bytes=[
        (b"MYFORMAT", 0),      # Exact match at start of file
        (b"<?xml", 0),         # XML declaration
        (b"\x50\x4B", 0),      # ZIP signature (for container formats)
        (b"VERSION", 10),      # Pattern at specific offset
    ]

Testing Your Plugin
-------------------

Create comprehensive tests for your plugin. Here's an example test suite:

.. code-block:: python

    # tests/test_myformat_plugin.py
    import pytest
    from pathlib import Path
    from all2md.converter_registry import get_registry
    from all2md.ast import Document
    from all2md_myformat.parser import CONVERTER_METADATA, MyFormatParser
    from all2md.options import BaseParserOptions

    def test_plugin_registration():
        """Test that the plugin is properly registered."""
        registry = get_registry()
        assert "myformat" in registry.list_formats()

    def test_format_detection():
        """Test format detection by extension and magic bytes."""
        registry = get_registry()
        # Test extension detection
        assert registry.detect_format("test.myf") == "myformat"
        # Test magic bytes detection
        assert registry.detect_format(b"MYFORMAT content here") == "myformat"

    def test_parser_instantiation():
        """Test that parser can be instantiated."""
        parser = MyFormatParser()
        assert parser is not None
        assert isinstance(parser.options, BaseParserOptions)

    def test_parse_from_bytes():
        """Test parsing from bytes input."""
        parser = MyFormatParser()
        test_content = b"MYFORMAT test document content"
        result = parser.parse(test_content)
        assert isinstance(result, Document)
        assert len(result.children) > 0

    def test_parse_from_path(tmp_path):
        """Test parsing from file path."""
        # Create test file
        test_file = tmp_path / "test.myf"
        test_file.write_bytes(b"MYFORMAT test document content")

        # Parse
        parser = MyFormatParser()
        result = parser.parse(test_file)
        assert isinstance(result, Document)
        assert len(result.children) > 0

    def test_metadata_extraction():
        """Test metadata extraction."""
        parser = MyFormatParser()
        # Create mock document object
        mock_doc = {"title": "Test Document", "author": "Test Author"}
        metadata = parser.extract_metadata(mock_doc)
        assert metadata is not None
        # Add assertions based on your metadata extraction logic

    def test_error_handling():
        """Test that appropriate errors are raised."""
        parser = MyFormatParser()
        with pytest.raises(Exception):  # ParsingError or similar
            parser.parse(b"INVALID content that should fail")

    def test_with_options():
        """Test parsing with custom options."""
        options = BaseParserOptions()
        parser = MyFormatParser(options=options)
        result = parser.parse(b"MYFORMAT test content")
        assert isinstance(result, Document)

Testing Renderer
~~~~~~~~~~~~~~~~

Test the renderer with a variety of AST structures:

.. code-block:: python

    def test_renderer_basic():
        """Test basic rendering."""
        from all2md.ast import Document, Paragraph, Text
        from all2md_myformat.renderer import MyFormatRenderer

        doc = Document(children=[
            Paragraph(content=[Text(content="Hello, world!")])
        ])

        renderer = MyFormatRenderer()
        output = renderer.render_to_string(doc)
        assert "Hello, world!" in output

    def test_unsupported_formatting_preserves_content():
        """Test that unsupported formatting still renders text content."""
        from all2md.ast import Document, Paragraph, Strikethrough, Text
        from all2md_myformat.renderer import MyFormatRenderer

        doc = Document(children=[
            Paragraph(content=[
                Strikethrough(content=[Text(content="crossed out")])
            ])
        ])

        renderer = MyFormatRenderer()
        output = renderer.render_to_string(doc)

        # Content should be preserved even without strikethrough
        assert "crossed out" in output

    def test_complex_document():
        """Test rendering a complex document with all node types."""
        from all2md.ast import (
            Document, Heading, Paragraph, List, ListItem,
            CodeBlock, Strong, Emphasis, Link, Image, Text
        )
        from all2md_myformat.renderer import MyFormatRenderer

        # Build complex document with many node types
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[
                Strong(content=[Text(content="bold")]),
                Text(content=" and "),
                Emphasis(content=[Text(content="italic")]),
            ]),
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
            ]),
            CodeBlock(language="python", content="print('hello')"),
        ])

        renderer = MyFormatRenderer()
        output = renderer.render_to_string(doc)

        # Verify all content is present
        assert "Title" in output
        assert "bold" in output
        assert "italic" in output
        assert "Item 1" in output
        assert "print('hello')" in output

Publishing Your Plugin
----------------------

Naming Convention
~~~~~~~~~~~~~~~~~

Follow the naming convention ``all2md-{format}`` for your package name to make it easily discoverable.

Distribution
~~~~~~~~~~~~

1. **Build your package**:

   .. code-block:: bash

       python -m build

2. **Upload to PyPI**:

   .. code-block:: bash

       python -m twine upload dist/*

3. **Installation by users**:

   .. code-block:: bash

       pip install all2md-myformat

The plugin will be automatically discovered when ``all2md`` is imported.

Best Practices
--------------

1. **Comprehensive format detection**: Implement robust magic byte detection for reliable format identification
2. **Graceful degradation**: Handle missing optional dependencies gracefully
3. **Clear error messages**: Provide helpful error messages with installation instructions
4. **Documentation**: Include clear documentation and usage examples
5. **Testing**: Test with various file types and edge cases
6. **Performance**: Optimize for large files and consider memory usage
7. **Compatibility**: Ensure compatibility with all supported Python versions
8. **Complete visitor implementation**: Implement all ``visit_*()`` methods in renderers, even if just ``pass``
9. **Document unsupported features**: Clearly document which AST node types your format doesn't support

Example Plugins
---------------

Here are some ideas for useful plugins:

- **all2md-visio**: Microsoft Visio diagrams
- **all2md-dwg**: AutoCAD drawings
- **all2md-pages**: Apple Pages documents
- **all2md-confluence**: Confluence wiki pages
- **all2md-notion**: Notion exports
- **all2md-custom-transforms**: Custom AST transforms for specialized workflows

Reference Implementation
-------------------------

The complete SimpleDoc plugin serves as a reference implementation:

- **Source code**: ``examples/simpledoc-plugin/``
- **Parser**: ``src/all2md_simpledoc/parser.py`` (full bidirectional parser)
- **Renderer**: ``src/all2md_simpledoc/renderer.py`` (complete visitor implementation)
- **Options**: ``src/all2md_simpledoc/options.py`` (parser and renderer options)
- **Metadata**: ``src/all2md_simpledoc/__init__.py`` (plugin registration)
- **Tests**: ``tests/test_simpledoc.py`` (comprehensive test coverage)
- **README**: Detailed usage examples and format specification

Community
---------

- Share your plugins on the `all2md community discussions <https://github.com/thomas.villani/all2md/discussions>`_
- Follow the `all2md-plugin <https://github.com/topics/all2md-plugin>`_ topic on GitHub
- Contribute examples and documentation improvements

Support
-------

If you encounter issues developing plugins:

1. Check the SimpleDoc plugin example in ``examples/simpledoc-plugin/``
2. Review the RENDERER_PATTERNS.md guide in the simpledoc-plugin directory
3. Review existing plugin implementations
4. Open an issue with the ``plugin-development`` label
