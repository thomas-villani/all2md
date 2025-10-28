"""Tool input/output schemas for MCP server.

This module defines the data structures for tool inputs and outputs
using Python dataclasses, which FastMCP will automatically convert
to JSON schemas for the MCP protocol.

Classes
-------
- ReadDocumentAsMarkdownInput: Input schema for read_document_as_markdown tool
- SaveDocumentFromMarkdownInput: Input schema for save_document_from_markdown tool
- SaveDocumentFromMarkdownOutput: Output schema for save_document_from_markdown tool
- EditDocumentSimpleInput: Input schema for edit_document tool (simplified)
- EditDocumentSimpleOutput: Output schema for edit_document tool (simplified)


Notes
-----
The read_document_as_markdown tool returns a list directly (markdown + images),
not a structured output object, to leverage FastMCP's automatic content
block conversion for vLLM visibility.

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

from dataclasses import dataclass, field
from typing import Literal

# Type aliases for better readability
SourceFormat = Literal[
    "auto",
    "pdf",
    "docx",
    "pptx",
    "html",
    "eml",
    "epub",
    "ipynb",
    "odt",
    "odp",
    "ods",
    "xlsx",
    "csv",
    "rst",
    "markdown",
    "plaintext",
]

TargetFormat = Literal["html", "pdf", "docx", "pptx", "rst", "epub", "markdown"]

MarkdownFlavor = Literal["gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus"]


@dataclass
class ReadDocumentAsMarkdownInput:
    """Input schema for read_document_as_markdown tool (simplified API).

    Note: Image inclusion (include_images) and markdown flavor are configured
    at the server level and cannot be overridden per-call.

    Attributes
    ----------
    source : str
        Unified source parameter. Auto-detected as:
        - File path (if file exists in read allowlist)
        - Data URI (data:...) -> decode to bytes
        - Base64 string -> decode to bytes if valid
        - Otherwise -> treat as plain text content
    section : str | None
        Optional section name to extract (case-insensitive heading match).
        If provided, only that section is returned.
    format_hint : SourceFormat | None
        Optional format hint for ambiguous cases (e.g., extensionless files).
        Use "auto" for auto-detection (default).
    pdf_pages : str | None
        Page specification for PDF sources (e.g., "1-3,5,10-")

    """

    source: str
    section: str | None = None
    format_hint: SourceFormat | None = None
    pdf_pages: str | None = None


@dataclass
class SaveDocumentFromMarkdownInput:
    """Input schema for save_document_from_markdown tool (simplified API).

    Attributes
    ----------
    format : TargetFormat
        Target output format (required)
    source : str
        Markdown content as string (required)
    filename : str
        Output file path (must be in write allowlist, required)

    """

    format: TargetFormat
    source: str
    filename: str


@dataclass
class SaveDocumentFromMarkdownOutput:
    """Output schema for save_document_from_markdown tool.

    Attributes
    ----------
    output_path : str
        Path where file was written
    warnings : list[str]
        Warning messages from rendering process

    """

    output_path: str
    warnings: list[str] = field(default_factory=list)


# Simplified edit_document tool schemas
EditDocumentAction = Literal[
    "list-sections",
    "extract",
    "add:before",
    "add:after",
    "remove",
    "replace",
    "insert:start",
    "insert:end",
    "insert:after_heading",
]


@dataclass
class EditDocumentSimpleInput:
    """Input schema for edit_document tool (simplified LLM-friendly interface).

    This is a simplified wrapper around the powerful AST-based document
    manipulation functionality. It uses sensible defaults and a streamlined
    interface designed for LLM usage.

    Attributes
    ----------
    action : EditDocumentAction
        Operation to perform on the document. One of:
        - "list-sections": List all sections with metadata
        - "extract": Get a single section by heading or index
        - "add:before": Add new section before target
        - "add:after": Add new section after target
        - "remove": Remove a section
        - "replace": Replace section content
        - "insert:start": Insert content at start of section
        - "insert:end": Insert content at end of section
        - "insert:after_heading": Insert content right after heading
    doc : str
        File path to the document (must be in read allowlist).
        Only file paths are supported (no inline content).
    target : str | None
        Section to target for operations. Can be:
        - Heading text (case-insensitive): "Introduction"
        - Index notation: "#0", "#1", "#2", etc. (zero-based)
        Required for all operations except "list-sections".
    content : str | None
        Markdown content to add/replace/insert.
        Required for add/replace/insert operations.
        Ignored for list-sections/extract/remove.

    Notes
    -----
    Defaults (not configurable in simplified interface):

    - Format: markdown only (no AST JSON)
    - Case sensitivity: case-insensitive heading matching
    - Flavor: "gfm" (GitHub Flavored Markdown)
    - Output: always returned in response (no file writing)

    """

    action: EditDocumentAction
    doc: str
    target: str | None = None
    content: str | None = None


@dataclass
class EditDocumentSimpleOutput:
    """Output schema for edit_document tool.

    Attributes
    ----------
    success : bool
        Whether the operation succeeded
    message : str
        Human-readable message describing the result.
        For errors, contains clear error description.
        For success, contains confirmation message.
    content : str | None
        Content returned by the operation (when applicable).
        - For "list-sections": formatted list of sections with metadata
        - For "extract": markdown content of the extracted section
        - For add/remove/replace/insert operations: updated markdown content
        - None otherwise

    """

    success: bool
    message: str
    content: str | None = None
