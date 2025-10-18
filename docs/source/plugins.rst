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

Creating a Plugin
------------------

Basic Plugin Structure
~~~~~~~~~~~~~~~~~~~~~~~

A typical plugin package should have the following structure:

.. code-block::

    all2md_myformat/
    ├── pyproject.toml
    ├── README.md
    └── all2md_myformat/
        ├── __init__.py
        └── converter.py

Implementing the Converter
~~~~~~~~~~~~~~~~~~~~~~~~~~

1. **Create a parser class**

Your parser should inherit from ``BaseParser`` and implement both the ``parse()`` and
``extract_metadata()`` methods:

.. code-block:: python

    # all2md_myformat/parser.py
    from pathlib import Path
    from typing import IO, Any, Optional, Union
    from all2md.parsers.base import BaseParser
    from all2md.ast import Document, Paragraph, Text
    from all2md.options import BaseParserOptions
    from all2md.progress import ProgressCallback
    from all2md.utils.metadata import DocumentMetadata
    from all2md.exceptions import ParsingError

    class MyFormatParser(BaseParser):
        """Convert MyFormat documents to AST representation.

        Parameters
        ----------
        options : BaseParserOptions or None
            Conversion options
        progress_callback : ProgressCallback or None
            Optional callback for progress updates during parsing
        """

        def __init__(
            self,
            options: BaseParserOptions | None = None,
            progress_callback: Optional[ProgressCallback] = None
        ):
            """Initialize the parser with options and progress callback."""
            super().__init__(options or BaseParserOptions(), progress_callback)

        def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
            """Parse MyFormat input into an AST Document.

            Parameters
            ----------
            input_data : str, Path, IO[bytes], or bytes
                The input document to parse

            Returns
            -------
            Document
                AST Document node representing the parsed document structure

            Raises
            ------
            ParsingError
                If parsing fails due to invalid format or corruption
            """
            # Emit started event for progress tracking
            self._emit_progress("started", "Converting MyFormat document", current=0, total=1)

            # Read content based on input type
            try:
                if isinstance(input_data, (str, Path)):
                    with open(input_data, 'rb') as f:
                        content = f.read()
                elif isinstance(input_data, bytes):
                    content = input_data
                else:
                    content = input_data.read()
            except Exception as e:
                raise ParsingError(f"Failed to read MyFormat file: {e}") from e

            # Process the content and build AST
            children = self._convert_to_ast_nodes(content)

            # Emit finished event
            self._emit_progress("finished", "MyFormat conversion completed", current=1, total=1)

            return Document(children=children)

        def extract_metadata(self, document: Any) -> DocumentMetadata:
            """Extract metadata from MyFormat document.

            Parameters
            ----------
            document : Any
                The loaded document object (format-specific type)

            Returns
            -------
            DocumentMetadata
                Extracted metadata including title, author, dates, keywords, etc.
                Returns empty DocumentMetadata if no metadata is available.
            """
            metadata = DocumentMetadata()
            # Extract metadata from your format here
            # Example:
            # metadata.title = document.get("title")
            # metadata.author = document.get("author")
            return metadata

        def _convert_to_ast_nodes(self, content: bytes) -> list:
            """Convert format-specific content to AST nodes.

            This is a helper method for your conversion logic.
            """
            # Your conversion logic here
            # Example: parse content and return AST nodes
            text = content.decode('utf-8', errors='replace')
            return [Paragraph(content=[Text(content=text)])]

2. **Define the converter metadata**

Create a ``ConverterMetadata`` object that describes your converter:

.. code-block:: python

    # all2md_myformat/parser.py (continued)
    from all2md.converter_metadata import ConverterMetadata
    from all2md.options import BaseParserOptions

    CONVERTER_METADATA = ConverterMetadata(
        format_name="myformat",
        extensions=[".myf", ".myformat"],
        mime_types=["application/x-myformat"],
        magic_bytes=[
            (b"MYFORMAT", 0),  # File signature at offset 0
            (b"MYF\x01", 0),   # Alternative signature
        ],
        parser_class=MyFormatParser,  # Direct class reference (recommended for plugins)
        # Or use fully qualified string: "all2md_myformat.parser.MyFormatParser"
        renderer_class="all2md.renderers.markdown.MarkdownRenderer",  # Full module path
        renders_as_string=True,  # True if renderer produces string output
        parser_required_packages=[
            ("myformat-parser", "myformat_parser", ">=1.0.0"),
            ("some-dependency", "some_dep", ""),
        ],
        renderer_required_packages=[],  # No special packages needed for markdown rendering
        optional_packages=[
            ("advanced-feature", "advanced_feature", ">=2.0"),
        ],
        import_error_message=(
            "MyFormat conversion requires 'myformat-parser' version 1.0.0 or later. "
            "Install with: pip install 'myformat-parser>=1.0.0'"
        ),
        parser_options_class=BaseParserOptions,  # Direct class reference
        # Or use string: "all2md.options.BaseParserOptions"
        renderer_options_class="all2md.options.markdown.MarkdownOptions",
        description="Convert MyFormat documents to Markdown with advanced features",
        priority=5  # Higher numbers = higher priority for format detection
    )

Package Configuration
~~~~~~~~~~~~~~~~~~~~~

Configure your ``pyproject.toml`` to register the plugin:

.. code-block:: toml

    [build-system]
    requires = ["hatchling"]
    build-backend = "hatchling.build"

    [project]
    name = "all2md-myformat"
    version = "1.0.0"
    description = "MyFormat support for all2md"
    authors = [
        {name = "Your Name", email = "your.email@example.com"},
    ]
    requires-python = ">=3.12"
    dependencies = [
        "all2md",
        "myformat-parser>=1.0.0",
    ]

    [project.entry-points."all2md.converters"]
    myformat = "all2md_myformat.parser:CONVERTER_METADATA"

    [project.urls]
    Homepage = "https://github.com/yourusername/all2md-myformat"
    Repository = "https://github.com/yourusername/all2md-myformat"

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

    @dataclass
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

**No Options Class**

If your converter doesn't need custom options, use ``BaseParserOptions``:

.. code-block:: python

    from all2md.options import BaseParserOptions

    CONVERTER_METADATA = ConverterMetadata(
        # ... other fields ...
        parser_options_class=BaseParserOptions,
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

Create comprehensive tests for your plugin:

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

Example Plugins
---------------

Here are some ideas for useful plugins:

- **all2md-visio**: Microsoft Visio diagrams
- **all2md-dwg**: AutoCAD drawings
- **all2md-pages**: Apple Pages documents
- **all2md-latex**: LaTeX documents
- **all2md-confluence**: Confluence wiki pages
- **all2md-notion**: Notion exports

Community
---------

- Share your plugins on the `all2md community discussions <https://github.com/thomas.villani/all2md/discussions>`_
- Follow the `all2md-plugin <https://github.com/topics/all2md-plugin>`_ topic on GitHub
- Contribute examples and documentation improvements

Support
-------

If you encounter issues developing plugins:

1. Check the `plugin development examples <https://github.com/yourusername/all2md/tree/main/examples/plugins>`_
2. Review existing plugin implementations
3. Open an issue with the ``plugin-development`` label