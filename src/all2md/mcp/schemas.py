"""Tool input/output schemas for MCP server.

This module defines the data structures for tool inputs and outputs
using Python dataclasses, which FastMCP will automatically convert
to JSON schemas for the MCP protocol.

Classes
-------
- ReadDocumentAsMarkdownInput: Input schema for read_document_as_markdown tool
- SaveDocumentFromMarkdownInput: Input schema for save_document_from_markdown tool
- SaveDocumentFromMarkdownOutput: Output schema for save_document_from_markdown tool
- EditOperation: A single edit within an edit_document batch
- EditDocumentInput: Input schema for edit_document tool (batch, in-place)
- EditResultItem: Per-edit result entry for edit_document tool
- EditDocumentOutput: Output schema for edit_document tool
- ListWorkspaceFilesInput: Input schema for list_workspace_files tool
- ListWorkspaceFilesOutput: Output schema for list_workspace_files tool
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
class EditOperation:
    """A single edit within an edit_document batch.

    Attributes
    ----------
    action : EditDocumentAction
        Operation to perform. One of:
        - "list-sections": list all sections with metadata (read-only)
        - "extract": get a single section by heading or index (read-only)
        - "add:before" / "add:after": add a new section relative to target
        - "remove": remove a section
        - "replace": replace a section's content
        - "insert:start" / "insert:end" / "insert:after_heading": insert content
          within the target section
    target : str | None
        Section to target. Either heading text (case-insensitive), e.g.
        "Introduction", or zero-based index notation, e.g. "#0", "#1".
        Required for every action except "list-sections". Heading text is
        recommended in multi-edit batches, since indices can shift as earlier
        edits in the batch add or remove sections.
    content : str | None
        Markdown content to add/replace/insert. Required for the add/replace/
        insert actions; ignored for list-sections/extract/remove.

    """

    action: EditDocumentAction
    target: str | None = None
    content: str | None = None


@dataclass
class EditDocumentInput:
    """Input schema for edit_document tool (batch, in-place editing).

    Applies one or more edits to a single document. Edits are applied in order
    to one parse of the document and the whole batch is atomic: if any edit
    fails, none are applied and nothing is written. When the batch contains a
    mutating action, the modified document is written back to disk in its
    original format (the file must be within the write allowlist).

    Attributes
    ----------
    doc : str
        Path to the document (absolute or workspace-relative). For mutating
        edits it must be within the write allowlist.
    edits : list[EditOperation]
        Ordered list of edits to apply.

    Notes
    -----
    - Source format is auto-detected (Markdown, DOCX, HTML, RST, EPUB, ...), so
      the tool is not Markdown-only.
    - Non-Markdown formats are re-rendered on write-back; for binary formats this
      can lose some fine-grained formatting (a warning is returned). DOCX uses
      the original file as a template to preserve styles where possible.
    - Mutating responses echo only the edited region, not the whole document, to
      keep responses small.

    """

    doc: str
    edits: list[EditOperation] = field(default_factory=list)


@dataclass
class EditResultItem:
    """Result of a single edit within a batch.

    Attributes
    ----------
    index : int
        Zero-based position of this edit in the request batch.
    action : str
        The action that was requested.
    target : str | None
        The target that was requested (if any).
    success : bool
        Whether this individual edit applied successfully.
    message : str
        Human-readable result or error message.
    edited_region : str | None
        For mutating edits, the markdown of just the affected section after the
        edit (not the whole document). For "list-sections"/"extract", the
        requested listing/section content. None when not applicable.

    """

    index: int
    action: str
    target: str | None
    success: bool
    message: str
    edited_region: str | None = None


@dataclass
class EditDocumentOutput:
    """Output schema for edit_document tool.

    Attributes
    ----------
    success : bool
        True only if every edit in the batch applied successfully.
    disk_written : bool
        Whether the modified document was persisted to disk. False for read-only
        batches (list-sections/extract only) and for any failed/atomically
        aborted batch.
    output_path : str | None
        Path written to, when disk_written is True.
    results : list[EditResultItem]
        Per-edit results, in request order.
    warnings : list[str]
        Non-fatal warnings (e.g. potential fidelity loss on a binary round-trip).

    """

    success: bool
    disk_written: bool = False
    output_path: str | None = None
    results: list[EditResultItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


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


# list_workspace_files tool schemas
@dataclass
class ListWorkspaceFilesInput:
    """Input schema for list_workspace_files tool.

    Lists files the server is allowed to read, so an agent can orient itself
    before reading or editing. Results are confined to the read allowlist
    (workspace folder plus any additional read-only folders).

    Attributes
    ----------
    subdirectory : str | None
        Optional workspace-relative subdirectory to list. When omitted, all read
        allowlist roots are listed. Must resolve to a location inside the read
        allowlist.
    pattern : str | None
        Optional glob filter applied to file names, e.g. "*.pdf" or "*.docx".
    recursive : bool
        Recurse into subdirectories (default: True).

    """

    subdirectory: str | None = None
    pattern: str | None = None
    recursive: bool = True


@dataclass
class ListWorkspaceFilesOutput:
    """Output schema for list_workspace_files tool.

    Attributes
    ----------
    files : list[dict]
        Listed files, each ``{"path": str, "size_bytes": int}`` where ``path`` is
        absolute. Sorted by path.
    total : int
        Number of files returned.
    truncated : bool
        True if the listing was capped and more files exist than were returned.
    read_dirs : list[str]
        The read allowlist roots that were searched (helps the agent understand
        what it can access).

    """

    files: list[dict] = field(default_factory=list)
    total: int = 0
    truncated: bool = False
    read_dirs: list[str] = field(default_factory=list)
