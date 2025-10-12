"""Tool input/output schemas for MCP server.

This module defines the data structures for tool inputs and outputs
using Python dataclasses, which FastMCP will automatically convert
to JSON schemas for the MCP protocol.

Classes
-------
- ConvertToMarkdownInput: Input schema for convert_to_markdown tool
- RenderFromMarkdownInput: Input schema for render_from_markdown tool
- RenderFromMarkdownOutput: Output schema for render_from_markdown tool
- EditDocumentInput: Input schema for edit_document_ast tool
- EditDocumentOutput: Output schema for edit_document_ast tool

Notes
-----
The convert_to_markdown tool returns a list directly (markdown + images),
not a structured output object, to leverage FastMCP's automatic content
block conversion for vLLM visibility.

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


# Type aliases for edit_document_ast tool
EditOperation = Literal[
    "list_sections",
    "get_section",
    "add_section",
    "remove_section",
    "replace_section",
    "insert_content",
    "generate_toc",
    "split_document"
]

InsertPosition = Literal["before", "after", "start", "end", "after_heading"]

OutputFormat = Literal["markdown", "ast_json"]

TOCStyle = Literal["markdown", "list", "nested"]


@dataclass
class EditDocumentInput:
    """Input schema for edit_document_ast tool.

    This tool allows LLMs to manipulate document structure at the AST level,
    supporting operations like adding/removing sections, generating TOC, etc.

    Attributes
    ----------
    operation : EditOperation
        Operation to perform on the document (required)
    source_path : str | None
        File path to document (must be in read allowlist).
        Mutually exclusive with source_content.
    source_content : str | None
        Document content as string (markdown or AST JSON).
        Mutually exclusive with source_path.
    content_encoding : Literal["plain", "base64"] | None
        Encoding of source_content ("plain" or "base64")
    source_format : Literal["markdown", "ast_json"]
        Format of source content (default: "markdown")
    target_heading : str | None
        Heading text to target for section operations
    target_index : int | None
        Section index to target (alternative to target_heading)
    content : str | None
        Content to add/insert (markdown format for add/replace operations)
    position : InsertPosition | None
        Position for add/insert operations ("before", "after", "start", "end")
    case_sensitive : bool
        Whether heading text matching is case-sensitive (default: False)
    max_toc_level : int
        Maximum heading level for TOC generation (default: 3)
    toc_style : TOCStyle
        Style for TOC generation (default: "markdown")
    flavor : MarkdownFlavor | None
        Markdown flavor for parsing/rendering (default: "gfm")
    output_path : str | None
        Output file path (must be in write allowlist).
        If not provided, content is returned in response.
    output_format : OutputFormat
        Format for output content (default: "markdown")

    """

    operation: EditOperation
    source_path: str | None = None
    source_content: str | None = None
    content_encoding: Literal["plain", "base64"] | None = None
    source_format: Literal["markdown", "ast_json"] = "markdown"
    target_heading: str | None = None
    target_index: int | None = None
    content: str | None = None
    position: InsertPosition | None = None
    case_sensitive: bool = False
    max_toc_level: int = 3
    toc_style: TOCStyle = "markdown"
    flavor: MarkdownFlavor | None = None
    output_path: str | None = None
    output_format: OutputFormat = "markdown"


@dataclass
class SectionInfo:
    """Information about a document section for list_sections operation.

    Attributes
    ----------
    index : int
        Zero-based index of the section in the document
    heading_text : str
        Plain text of the heading
    level : int
        Heading level (1-6)
    content_nodes : int
        Number of content nodes in the section
    start_index : int
        Start index in document children list
    end_index : int
        End index in document children list

    """

    index: int
    heading_text: str
    level: int
    content_nodes: int
    start_index: int
    end_index: int


@dataclass
class EditDocumentOutput:
    """Output schema for edit_document_ast tool.

    Attributes
    ----------
    content : str | None
        Modified document content (markdown or AST JSON).
        None when operation is list_sections or when output_path is provided.
    sections : list[SectionInfo] | None
        Section metadata for list_sections operation
    section_count : int | None
        Number of sections (for list_sections)
    sections_modified : int
        Number of sections modified by the operation
    output_path : str | None
        Path where file was written (if output_path was provided in input)
    warnings : list[str]
        Warning messages from the operation

    """

    content: str | None = None
    sections: list[SectionInfo] | None = None
    section_count: int | None = None
    sections_modified: int = 0
    output_path: str | None = None
    warnings: list[str] = field(default_factory=list)
