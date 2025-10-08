"""Tool input/output schemas for MCP server.

This module defines the data structures for tool inputs and outputs
using Python dataclasses, which FastMCP will automatically convert
to JSON schemas for the MCP protocol.

Classes
-------
- ConvertToMarkdownInput: Input schema for convert_to_markdown tool
- ConvertToMarkdownOutput: Output schema for convert_to_markdown tool
- RenderFromMarkdownInput: Input schema for render_from_markdown tool
- RenderFromMarkdownOutput: Output schema for render_from_markdown tool

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

from dataclasses import dataclass, field
from typing import Literal

# Type aliases for better readability
SourceFormat = Literal[
    "auto", "pdf", "docx", "pptx", "html", "eml", "epub", "ipynb",
    "odt", "odp", "ods", "xlsx", "csv", "rst", "markdown", "txt"
]

TargetFormat = Literal[
    "html", "pdf", "docx", "pptx", "rst", "epub", "markdown"
]

MarkdownFlavor = Literal[
    "gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus"
]


@dataclass
class ConvertToMarkdownInput:
    """Input schema for convert_to_markdown tool.

    Note: attachment_mode and attachment_output_dir are configured at the
    server level and cannot be overridden per-call for security.

    Attributes
    ----------
    source_path : str | None
        File path to convert (must be in read allowlist).
        Mutually exclusive with source_content.
    source_content : str | None
        String content to convert. Can be plain text (HTML, Markdown, etc.)
        or base64-encoded binary content (PDF, DOCX, etc.).
        Mutually exclusive with source_path.
    content_encoding : Literal["plain", "base64"] | None
        Encoding of source_content. Use "base64" for binary formats,
        "plain" for text formats (default: "plain" if not specified).
    source_format : SourceFormat
        Explicit source format, or "auto" for detection (default: "auto")
    flavor : MarkdownFlavor | None
        Markdown flavor/dialect for output (default: server-configured or "gfm")
    pdf_pages : str | None
        Page specification for PDF sources (e.g., "1-3,5,10-")

    """

    source_path: str | None = None
    source_content: str | None = None
    content_encoding: Literal["plain", "base64"] | None = None
    source_format: SourceFormat = "auto"
    flavor: MarkdownFlavor | None = None
    pdf_pages: str | None = None


@dataclass
class ConvertToMarkdownOutput:
    """Output schema for convert_to_markdown tool.

    Attributes
    ----------
    markdown : str
        Converted markdown content
    attachments : list[str]
        List of attachment file paths (if attachment_mode=download).
        Paths are relative to attachment_output_dir.
    warnings : list[str]
        Warning messages from conversion process

    """

    markdown: str
    attachments: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class RenderFromMarkdownInput:
    """Input schema for render_from_markdown tool.

    Attributes
    ----------
    markdown : str | None
        Markdown content as string.
        Mutually exclusive with markdown_path.
    markdown_path : str | None
        Path to markdown file (must be in read allowlist).
        Mutually exclusive with markdown.
    target_format : TargetFormat
        Target output format (required)
    output_path : str | None
        Output file path (must be in write allowlist).
        If not provided, content is returned in the response.
    flavor : MarkdownFlavor | None
        Markdown flavor for parsing (default: "gfm")

    """

    target_format: TargetFormat = "html"  # Required but provide default for type safety
    markdown: str | None = None
    markdown_path: str | None = None
    output_path: str | None = None
    flavor: MarkdownFlavor | None = None


@dataclass
class RenderFromMarkdownOutput:
    """Output schema for render_from_markdown tool.

    Attributes
    ----------
    content : str | None
        Rendered content (for text formats when output_path not provided).
        For binary formats, this will be base64-encoded.
    output_path : str | None
        Path where file was written (if output_path was provided in input)
    warnings : list[str]
        Warning messages from rendering process

    """

    content: str | None = None
    output_path: str | None = None
    warnings: list[str] = field(default_factory=list)
