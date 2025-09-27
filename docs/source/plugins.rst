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

1. **Create the converter function**

Your converter function should accept the same signature as built-in converters:

.. code-block:: python

    # all2md_myformat/converter.py
    from pathlib import Path
    from typing import IO, Union
    from all2md.options import BaseOptions

    def myformat_to_markdown(
        input_data: Union[str, Path, IO[bytes]],
        options: BaseOptions | None = None
    ) -> str:
        """Convert MyFormat documents to Markdown.

        Parameters
        ----------
        input_data : str, Path, or IO[bytes]
            The document to convert
        options : BaseOptions | None
            Conversion options

        Returns
        -------
        str
            The document content in Markdown format
        """
        # Your conversion logic here
        if isinstance(input_data, (str, Path)):
            with open(input_data, 'rb') as f:
                content = f.read()
        else:
            content = input_data.read()

        # Process the content and convert to markdown
        markdown_output = process_myformat_content(content, options)
        return markdown_output

2. **Define the converter metadata**

Create a ``ConverterMetadata`` object that describes your converter:

.. code-block:: python

    # all2md_myformat/converter.py (continued)
    from all2md.converter_metadata import ConverterMetadata

    CONVERTER_METADATA = ConverterMetadata(
        format_name="myformat",
        extensions=[".myf", ".myformat"],
        mime_types=["application/x-myformat"],
        magic_bytes=[
            (b"MYFORMAT", 0),  # File signature at offset 0
            (b"MYF\x01", 0),   # Alternative signature
        ],
        converter_module="all2md_myformat.converter",
        converter_function="myformat_to_markdown",
        required_packages=[
            ("myformat-parser", ">=1.0.0"),
            ("some-dependency", ""),
        ],
        optional_packages=[
            ("advanced-feature", ">=2.0"),
        ],
        import_error_message=(
            "MyFormat conversion requires 'myformat-parser' version 1.0.0 or later. "
            "Install with: pip install 'myformat-parser>=1.0.0'"
        ),
        options_class="BaseOptions",  # Or your custom options class
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
    myformat = "all2md_myformat.converter:CONVERTER_METADATA"

    [project.urls]
    Homepage = "https://github.com/yourusername/all2md-myformat"
    Repository = "https://github.com/yourusername/all2md-myformat"

Advanced Features
-----------------

Custom Options Classes
~~~~~~~~~~~~~~~~~~~~~~~

For complex converters, you may want to define custom options:

.. code-block:: python

    # all2md_myformat/options.py
    from dataclasses import dataclass
    from all2md.options import BaseOptions

    @dataclass
    class MyFormatOptions(BaseOptions):
        """Options for MyFormat conversion."""

        extract_metadata: bool = True
        preserve_formatting: bool = False
        custom_parser_mode: str = "strict"

Then reference it in your metadata:

.. code-block:: python

    CONVERTER_METADATA = ConverterMetadata(
        # ... other fields ...
        options_class="MyFormatOptions",
        # ... rest of metadata ...
    )

Error Handling
~~~~~~~~~~~~~~

Implement robust error handling in your converter:

.. code-block:: python

    from all2md.exceptions import MarkdownConversionError

    def myformat_to_markdown(input_data, options=None):
        try:
            # Your conversion logic
            pass
        except ImportError as e:
            raise MarkdownConversionError(
                f"Required dependency missing: {e}",
                conversion_stage="dependency_check",
                original_error=e
            )
        except Exception as e:
            raise MarkdownConversionError(
                f"Failed to convert MyFormat document: {e}",
                conversion_stage="conversion",
                original_error=e
            )

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
    from all2md.converter_registry import registry
    from all2md_myformat.converter import CONVERTER_METADATA

    def test_plugin_registration():
        """Test that the plugin is properly registered."""
        assert "myformat" in registry.list_formats()

    def test_format_detection():
        """Test format detection."""
        assert registry.detect_format("test.myf") == "myformat"
        assert registry.detect_format(b"MYFORMAT content") == "myformat"

    def test_conversion():
        """Test basic conversion functionality."""
        test_content = create_test_myformat_content()
        result = registry.get_converter("myformat")[0](test_content)
        assert isinstance(result, str)
        assert len(result) > 0

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