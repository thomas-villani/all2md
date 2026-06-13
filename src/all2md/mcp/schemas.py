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
- SearchDocumentsInput: Input schema for search_documents tool
- SearchResultItem: Single result entry for search_documents tool
- SearchDocumentsOutput: Output schema for search_documents tool
- DiffDocumentsInput: Input schema for diff_documents tool
- DiffDocumentsOutput: Output schema for diff_documents tool
- GetDocumentOutlineInput: Input schema for get_document_outline tool
- GetDocumentOutlineOutput: Output schema for get_document_outline tool


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


# search_documents tool schemas
SearchMode = Literal["keyword", "grep"]


@dataclass
class SearchDocumentsInput:
    """Input schema for search_documents tool.

    Searches a corpus of documents and returns ranked snippets rather than whole
    files. Two modes are supported in this slice:

    - "keyword": BM25 relevance ranking (requires the optional ``rank-bm25``
      dependency). Best for "find the most relevant passages" queries.
    - "grep": literal/regex line matching with highlighted spans. Best for
      "find every occurrence of X" queries. Stateless, no extra dependencies.

    Attributes
    ----------
    query : str
        Search query. For grep mode this is a literal string unless ``regex`` is
        set; for keyword mode it is a natural-language query (required).
    paths : list[str] | None
        Files, directories, or globs to search (each validated against the read
        allowlist). When omitted, the server's read allowlist is searched.
    mode : SearchMode
        "keyword" (default, BM25) or "grep".
    top_k : int
        Maximum number of results to return (default: 10).
    ignore_case : bool
        Case-insensitive matching (grep mode only; default: False).
    regex : bool
        Treat the query as a regular expression (grep mode only; default: False).
    recursive : bool
        Recurse into directories when collecting input files (default: True).

    """

    query: str
    paths: list[str] | None = None
    mode: SearchMode = "keyword"
    top_k: int = 10
    ignore_case: bool = False
    regex: bool = False
    recursive: bool = True


@dataclass
class SearchResultItem:
    """A single search result.

    Attributes
    ----------
    snippet : str
        Matched text with hit spans wrapped in ``<<`` / ``>>`` markers.
    score : float
        Relevance score (BM25 score for keyword mode; match count for grep mode).
    document_path : str | None
        Path of the document the match came from, when available.
    section_heading : str | None
        Heading of the section the match was found in, when available.
    chunk_id : str
        Identifier of the underlying chunk/section the match belongs to.

    """

    snippet: str
    score: float
    document_path: str | None
    section_heading: str | None
    chunk_id: str


@dataclass
class SearchDocumentsOutput:
    """Output schema for search_documents tool.

    Attributes
    ----------
    results : list[SearchResultItem]
        Ranked search results.
    mode : str
        The resolved search mode used.
    total : int
        Number of results returned.

    """

    results: list[SearchResultItem] = field(default_factory=list)
    mode: str = "keyword"
    total: int = 0


# diff_documents tool schemas
DiffFormat = Literal["unified", "json"]
DiffGranularity = Literal["block", "sentence", "word"]


@dataclass
class DiffDocumentsInput:
    """Input schema for diff_documents tool.

    Compares two documents and returns their differences. Each of ``old`` and
    ``new`` is auto-detected (file path within the read allowlist, data URI,
    base64, or plain text content), so documents in any supported format can be
    compared — even across formats.

    Attributes
    ----------
    old : str
        Original document (path or inline content).
    new : str
        Updated document (path or inline content).
    format : DiffFormat
        Output format: "unified" (default, plain text) or "json" (structured).
    context_lines : int
        Number of context lines around changes in unified output (default: 3).
    granularity : DiffGranularity
        Comparison granularity: "block" (default), "sentence", or "word".
    ignore_whitespace : bool
        Normalize whitespace before comparing (default: False).

    """

    old: str
    new: str
    format: DiffFormat = "unified"
    context_lines: int = 3
    granularity: DiffGranularity = "block"
    ignore_whitespace: bool = False


@dataclass
class DiffDocumentsOutput:
    """Output schema for diff_documents tool.

    Attributes
    ----------
    diff : str
        Rendered diff in the requested format (unified text or JSON string).
    has_changes : bool
        Whether any differences were found.

    """

    diff: str
    has_changes: bool


# get_document_outline tool schemas
@dataclass
class GetDocumentOutlineInput:
    """Input schema for get_document_outline tool.

    Returns the heading structure of a document so an agent can navigate a large
    file before extracting specific sections. ``doc`` is auto-detected (file path
    within the read allowlist, data URI, base64, or plain text content).

    Attributes
    ----------
    doc : str
        Document to outline (path or inline content).
    max_level : int
        Deepest heading level to include, 1-6 (default: 6, i.e. all levels).
    format_hint : SourceFormat | None
        Optional format hint for ambiguous/extensionless sources.

    """

    doc: str
    max_level: int = 6
    format_hint: SourceFormat | None = None


@dataclass
class GetDocumentOutlineOutput:
    """Output schema for get_document_outline tool.

    Attributes
    ----------
    sections : list[dict]
        Ordered list of headings, each ``{"index": int, "level": int,
        "heading": str}`` where ``index`` is the zero-based section index usable
        with edit_document's ``#N`` target notation.
    total : int
        Number of headings returned.

    """

    sections: list[dict] = field(default_factory=list)
    total: int = 0
