# Copyright (c) 2025 All2md Contributors
"""SimpleDoc format plugin for all2md.

This plugin provides bidirectional conversion between SimpleDoc format
and the all2md AST. It serves as a comprehensive example of how to build
a complete converter plugin (parser + renderer) for the all2md library.

SimpleDoc is a lightweight markup format with:
- Frontmatter metadata (YAML-style between --- delimiters)
- Headings (lines starting with @@)
- Lists (lines starting with -)
- Code blocks (triple backticks)
- Paragraphs (separated by blank lines)

Example usage:

    from all2md import to_markdown
    from all2md.converter_registry import get_registry

    # Parse SimpleDoc to Markdown
    markdown = to_markdown("document.sdoc")

    # Convert Markdown to SimpleDoc
    registry = get_registry()
    parser = registry.get_parser("markdown")()
    ast_doc = parser.parse("document.md")

    renderer_class = registry.get_renderer("simpledoc")
    renderer = renderer_class()
    renderer.render(ast_doc, "output.sdoc")

"""

from all2md.converter_metadata import ConverterMetadata

from .options import SimpleDocOptions, SimpleDocRendererOptions
from .parser import SimpleDocParser
from .renderer import SimpleDocRenderer

__version__ = "1.0.0"
__author__ = "All2md Contributors"

# Converter metadata for plugin discovery
# This is the key object that registers the plugin with all2md
CONVERTER_METADATA = ConverterMetadata(
    # Format identifier
    format_name="simpledoc",
    # File extensions for this format
    extensions=[".sdoc", ".simpledoc"],
    # MIME type (custom for our invented format)
    mime_types=["text/x-simpledoc", "application/x-simpledoc"],
    # Magic bytes for format detection
    # SimpleDoc files typically start with "---\n" (frontmatter)
    magic_bytes=[
        (b"---\n", 0),  # Frontmatter at start of file
        (b"---\r\n", 0),  # Frontmatter with Windows line endings
    ],
    # Parser class (can be direct class reference or string path)
    parser_class=SimpleDocParser,
    # Renderer class
    renderer_class=SimpleDocRenderer,
    # Renderer produces string output (not binary)
    renders_as_string=True,
    # No external dependencies required for this parser
    parser_required_packages=[],
    # No external dependencies required for renderer
    renderer_required_packages=[],
    # Optional packages (none for this simple format)
    optional_packages=[],
    # Custom error message if dependencies are missing (not applicable here)
    import_error_message="SimpleDoc conversion requires no external dependencies.",
    # Options classes
    parser_options_class=SimpleDocOptions,
    renderer_options_class=SimpleDocRendererOptions,
    # Human-readable description
    description="Convert SimpleDoc lightweight markup format to and from AST. "
    "SimpleDoc is an educational format demonstrating plugin development.",
    # Detection priority (higher = checked first)
    # Set to 5 to be checked before generic text but after specialized formats
    priority=5,
)

__all__ = [
    "SimpleDocParser",
    "SimpleDocRenderer",
    "SimpleDocOptions",
    "SimpleDocRendererOptions",
    "CONVERTER_METADATA",
]
