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
# This is the KEY object that registers your plugin with all2md
# The entry point in pyproject.toml points to this CONVERTER_METADATA object
CONVERTER_METADATA = ConverterMetadata(
    # Format identifier: Unique name for your format (lowercase, no spaces)
    # Used in CLI (--format simpledoc) and API (get_parser("simpledoc"))
    format_name="simpledoc",

    # File extensions: List of extensions for auto-detection
    # When a file ends with .sdoc, all2md automatically uses this plugin
    extensions=[".sdoc", ".simpledoc"],

    # MIME types: For web/HTTP-based format detection
    # Use standard MIME types if they exist, or invent x- prefixed ones
    mime_types=["text/x-simpledoc", "application/x-simpledoc"],

    # Magic bytes: Binary signatures for format detection from file content
    # Format: list of (byte_pattern, offset) tuples
    # This allows detection even when file extension is missing/wrong
    magic_bytes=[
        (b"---\n", 0),  # Frontmatter at start of file (Unix line endings)
        (b"---\r\n", 0),  # Frontmatter with Windows line endings
    ],

    # Parser class: Can be direct class reference (shown here) or string path
    # Direct reference is preferred for plugins (avoids import issues)
    parser_class=SimpleDocParser,

    # Renderer class: Enables bidirectional conversion (AST -> SimpleDoc)
    # If you only need parsing, you can omit this or use a standard renderer
    renderer_class=SimpleDocRenderer,

    # Output type: True if renderer produces string, False for binary (bytes)
    # SimpleDoc is text, so True. PDF/DOCX would be False.
    renders_as_string=True,

    # Dependencies: List required packages as (pip_name, import_name, version_spec)
    # Example: [("python-docx", "docx", ">=0.8.11")]
    # Empty list means no dependencies
    parser_required_packages=[],
    renderer_required_packages=[],

    # Optional packages: Nice-to-have but not required
    # Example: [("pillow", "PIL", ">=9.0")] for optional image processing
    optional_packages=[],

    # Error message: Shown when required dependencies are missing
    # Provide helpful installation instructions
    import_error_message="SimpleDoc conversion requires no external dependencies.",

    # Options classes: Configuration for parser and renderer
    # These enable CLI flags and programmatic options
    parser_options_class=SimpleDocOptions,
    renderer_options_class=SimpleDocRendererOptions,

    # Description: Human-readable description for --list-formats
    description="Convert SimpleDoc lightweight markup format to and from AST. "
    "SimpleDoc is an educational format demonstrating plugin development.",

    # Priority: Controls detection order when multiple formats match
    # Higher numbers checked first. Range: 0-10
    # 10 = very specific formats (PDF, DOCX)
    # 5 = medium specificity (our format)
    # 0 = generic fallbacks (plain text)
    priority=5,
)

__all__ = [
    "SimpleDocParser",
    "SimpleDocRenderer",
    "SimpleDocOptions",
    "SimpleDocRendererOptions",
    "CONVERTER_METADATA",
]
