"""FastMCP server for all2md document conversion.

This module implements the main MCP server using FastMCP with stdio transport.
It exposes read_document_as_markdown, save_document_from_markdown, and
edit_document tools to LLMs with comprehensive security controls.

Functions
---------
- main: Server entry point (for CLI)

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import contextlib
import logging
import os
import sys
import threading
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Annotated, Any, cast

from all2md import DependencyError
from all2md.logging_utils import configure_logging as configure_root_logging

if TYPE_CHECKING:
    from fastmcp import FastMCP

from all2md.mcp.config import MCPConfig, load_config
from all2md.mcp.schemas import (
    DiffDocumentsInput,
    DiffDocumentsOutput,
    DiffFormat,
    DiffGranularity,
    EditDocumentInput,
    EditDocumentOutput,
    EditOperation,
    GetDocumentOutlineInput,
    GetDocumentOutlineOutput,
    ListWorkspaceFilesInput,
    ListWorkspaceFilesOutput,
    ReadDocumentAsMarkdownInput,
    SaveDocumentFromMarkdownInput,
    SaveDocumentFromMarkdownOutput,
    SearchDocumentsInput,
    SearchDocumentsOutput,
    SearchMode,
    SourceFormat,
    TargetFormat,
)
from all2md.mcp.security import MCPSecurityError, prepare_allowlist_dirs

logger = logging.getLogger(__name__)

# Serialize the brief stdout->stderr redirect below across any concurrent tool
# calls so they never clobber each other's saved file descriptor.
_stdout_guard_lock = threading.Lock()


@contextlib.contextmanager
def protect_stdout() -> Iterator[None]:
    """Redirect OS-level stdout (fd 1) to stderr for the duration.

    The MCP stdio transport uses stdout for its JSON-RPC messages. Some
    libraries in the conversion pipeline (notably PyMuPDF) print advisories
    straight to stdout, which corrupts that channel and breaks the client
    connection. We point fd 1 at stderr while running conversion code, then
    restore it before FastMCP serializes the response. This catches both
    Python-level ``print`` and C-level writes.
    """
    with _stdout_guard_lock:
        sys.stdout.flush()
        sys.stderr.flush()
        saved_fd = os.dup(1)
        try:
            os.dup2(2, 1)
            yield
        finally:
            sys.stdout.flush()
            os.dup2(saved_fd, 1)
            os.close(saved_fd)


def create_server(
    config: MCPConfig,
    read_impl: Callable[[ReadDocumentAsMarkdownInput, MCPConfig], list[Any]],
    save_impl: Callable[[SaveDocumentFromMarkdownInput, MCPConfig], SaveDocumentFromMarkdownOutput],
    edit_doc_impl: Callable[[EditDocumentInput, MCPConfig], EditDocumentOutput],
    search_impl: Callable[[SearchDocumentsInput, MCPConfig], SearchDocumentsOutput],
    diff_impl: Callable[[DiffDocumentsInput, MCPConfig], DiffDocumentsOutput],
    outline_impl: Callable[[GetDocumentOutlineInput, MCPConfig], GetDocumentOutlineOutput],
    list_files_impl: Callable[[ListWorkspaceFilesInput, MCPConfig], ListWorkspaceFilesOutput],
) -> "FastMCP":
    """Create and configure FastMCP server with tools.

    Parameters
    ----------
    config : MCPConfig
        Server configuration
    read_impl : callable
        Implementation function for read_document_as_markdown tool
    save_impl : callable
        Implementation function for save_document_from_markdown tool
    edit_doc_impl : callable
        Implementation function for edit_document tool
    search_impl : callable
        Implementation function for search_documents tool
    diff_impl : callable
        Implementation function for diff_documents tool
    outline_impl : callable
        Implementation function for get_document_outline tool
    list_files_impl : callable
        Implementation function for list_workspace_files tool

    Returns
    -------
    FastMCP
        Configured MCP server instance

    """
    try:
        from fastmcp import FastMCP
    except ImportError as e:
        print("Error: FastMCP not installed. Install with: pip install 'all2md[mcp]'", file=sys.stderr)
        raise DependencyError("mcp", [("fastmcp", ">=2.0.0")]) from e

    # Create MCP server
    mcp: FastMCP = FastMCP(name="all2md")

    # Conditionally register read_document_as_markdown tool
    if config.enable_to_md:

        @mcp.tool(name="read_document_as_markdown")
        def read_document_as_markdown(
            source: Annotated[
                str,
                "Unified source parameter. Auto-detected as: file path (if exists in read allowlist), "
                "data URI (data:...), base64 string, or plain text content. REQUIRED.",
            ],
            section: Annotated[
                str | None,
                "Optional section name to extract (case-insensitive heading match). "
                "If provided, only that section is returned.",
            ] = None,
            format_hint: Annotated[
                str | None,
                "Optional format hint for ambiguous cases (e.g., extensionless files). "
                "Options: auto (default), pdf, docx, pptx, html, eml, epub, ipynb, odt, odp, ods, "
                "xlsx, csv, rst, markdown, txt.",
            ] = None,
            pdf_pages: Annotated[
                str | None,
                "Page specification for PDF sources only. Examples: '1-3' (pages 1-3), '1,3,5' "
                "(specific pages), '1-3,5,10-' (ranges and individual pages), '1-' (from page 1 to end).",
            ] = None,
        ) -> list:
            """Read a document and convert it to Markdown format (simplified API).

            Supports PDF, Word (DOCX), PowerPoint (PPTX), HTML, email (EML), EPUB,
            Jupyter Notebooks (IPYNB), Excel (XLSX/CSV), ODF formats, and 200+ text formats.

            The source parameter is auto-detected as:
            - File path (if file exists in read allowlist)
            - Data URI (data:image/...)
            - Base64-encoded content (auto-detected)
            - Plain text content (HTML, Markdown, etc.)

            Optionally extract a specific section by providing the section parameter
            with a heading name (case-insensitive match).

            Image inclusion and markdown flavor are configured at server startup and
            cannot be changed per-call.

            Returns a list with markdown text as the first element, followed by FastMCP Image
            objects for any images found (when include_images=true). When include_images=false,
            returns just the markdown text with image alt text.

            FastMCP automatically converts this list into appropriate MCP content blocks,
            allowing vLLMs to "see" the images alongside the text.
            """
            # Cast to proper Literal types (FastMCP validates these at the boundary)
            input_obj = ReadDocumentAsMarkdownInput(
                source=source, section=section, format_hint=cast(SourceFormat | None, format_hint), pdf_pages=pdf_pages
            )

            # Return list directly - FastMCP converts to content blocks
            with protect_stdout():
                return read_impl(input_obj, config)

        logger.info("Registered tool: read_document_as_markdown")

    # Conditionally register save_document_from_markdown tool
    if config.enable_from_md:

        @mcp.tool(name="save_document_from_markdown")
        def save_document_from_markdown(
            format: Annotated[
                str, "Target output format. Options: html, pdf, docx, pptx, rst, epub, markdown. REQUIRED."
            ],
            source: Annotated[str, "Markdown content as a string to convert. REQUIRED."],
            filename: Annotated[str, "Output file path. Must be within write allowlist. REQUIRED."],
        ) -> dict:
            """Save Markdown content to another format (simplified API).

            Supports rendering to HTML, PDF, DOCX, PPTX, RST, EPUB, and Markdown.

            This tool always writes to disk (no content return). The filename parameter
            is required and must pass write allowlist validation.

            Markdown flavor for parsing is configured at server startup.

            This tool requires --enable-from-md flag (disabled by default for security).

            Returns a dictionary with:
            - output_path: File path where content was written
            - warnings: List of warning messages from the rendering process
            """
            # Cast to proper Literal types (FastMCP validates these at the boundary)
            input_obj = SaveDocumentFromMarkdownInput(
                format=cast(TargetFormat, format), source=source, filename=filename
            )

            with protect_stdout():
                result = save_impl(input_obj, config)

            return {"output_path": result.output_path, "warnings": result.warnings}

        logger.info("Registered tool: save_document_from_markdown")

    # Conditionally register edit_document tool
    if config.enable_doc_edit:

        @mcp.tool(name="edit_document")
        def edit_document(
            doc: Annotated[
                str,
                "Path to the document (absolute or workspace-relative). For mutating edits it must be "
                "within the write allowlist. REQUIRED.",
            ],
            edits: Annotated[
                list[EditOperation],
                "Ordered list of edits to apply atomically. Each edit is an object with: "
                "'action' (one of list-sections, extract, add:before, add:after, remove, replace, "
                "insert:start, insert:end, insert:after_heading); 'target' (heading text like "
                "'Introduction', or index like '#0' — required for every action except list-sections; "
                "prefer heading text in multi-edit batches since indices can shift); and 'content' "
                "(markdown, required for add/replace/insert actions). REQUIRED.",
            ],
        ) -> dict:
            """Apply a batch of structural edits to a document, in place.

            Source format is auto-detected (Markdown, DOCX, HTML, RST, EPUB, ...), so this is
            not Markdown-only. The whole batch is atomic: if any edit fails, none are applied
            and nothing is written. When the batch contains a mutating action, the modified
            document is written back to disk in its original format (the file must be within the
            write allowlist). Heading matching is case-insensitive.

            Actions:
            - list-sections: list all sections with metadata (read-only)
            - extract: get a section by heading or index (read-only)
            - add:before / add:after: add a new section relative to target
            - remove: remove a section
            - replace: replace a section's content
            - insert:start / insert:end / insert:after_heading: insert within a section

            In-place write-back is supported for .md, .html, .docx, .pptx, .rst, .epub. For other
            formats (e.g. .pdf), use save_document_from_markdown to export instead.

            Requires --enable-doc-edit flag (disabled by default for security).

            Returns a dictionary with:
            - success: True only if every edit applied
            - disk_written: whether the file was persisted to disk
            - output_path: path written to (when disk_written is True)
            - results: per-edit {index, action, target, success, message, edited_region}
              where edited_region is only the affected section, not the whole document
            - warnings: non-fatal notes (e.g. potential formatting loss on a binary round-trip)
            """
            input_obj = EditDocumentInput(doc=doc, edits=list(edits))

            with protect_stdout():
                result = edit_doc_impl(input_obj, config)

            return {
                "success": result.success,
                "disk_written": result.disk_written,
                "output_path": result.output_path,
                "results": [
                    {
                        "index": item.index,
                        "action": item.action,
                        "target": item.target,
                        "success": item.success,
                        "message": item.message,
                        "edited_region": item.edited_region,
                    }
                    for item in result.results
                ],
                "warnings": result.warnings,
            }

        logger.info("Registered tool: edit_document")

    # Conditionally register search_documents tool (read-only)
    if config.enable_search:

        @mcp.tool(name="search_documents")
        def search_documents(
            query: Annotated[
                str,
                "Search query. Natural language for keyword mode; a literal string (or regex) for grep mode. REQUIRED.",
            ],
            paths: Annotated[
                list[str] | None,
                "Files, directories, or globs to search (each must be within the read allowlist). "
                "If omitted, the server's read allowlist is searched.",
            ] = None,
            mode: Annotated[
                str,
                "Search mode: 'keyword' (default, BM25 relevance ranking) or 'grep' (literal/regex line matching).",
            ] = "keyword",
            top_k: Annotated[int, "Maximum number of results to return (default: 10)."] = 10,
            ignore_case: Annotated[bool, "Case-insensitive matching (grep mode only). Default: false."] = False,
            regex: Annotated[bool, "Treat the query as a regular expression (grep mode only). Default: false."] = False,
            recursive: Annotated[bool, "Recurse into directories when collecting input files. Default: true."] = True,
        ) -> dict:
            """Search a corpus of documents and return ranked snippets.

            Instead of returning whole files, this tool returns the most relevant
            passages (with hit spans wrapped in << >> markers), so an agent can
            locate information across many documents cheaply.

            Modes:
            - keyword: BM25 relevance ranking (requires the optional rank-bm25
              dependency). Best for "find the most relevant passages" queries.
            - grep: literal/regex line matching. Best for "find every occurrence
              of X". Stateless, no extra dependencies.

            Supports all formats the read tool supports (PDF, DOCX, HTML, etc.);
            files are converted to text before searching.

            Returns a dictionary with:
            - results: list of {snippet, score, document_path, section_heading, chunk_id}
            - mode: the search mode used
            - total: number of results returned
            """
            input_obj = SearchDocumentsInput(
                query=query,
                paths=paths,
                mode=cast(SearchMode, mode),
                top_k=top_k,
                ignore_case=ignore_case,
                regex=regex,
                recursive=recursive,
            )
            with protect_stdout():
                result = search_impl(input_obj, config)
            return {
                "results": [
                    {
                        "snippet": item.snippet,
                        "score": item.score,
                        "document_path": item.document_path,
                        "section_heading": item.section_heading,
                        "chunk_id": item.chunk_id,
                    }
                    for item in result.results
                ],
                "mode": result.mode,
                "total": result.total,
            }

        logger.info("Registered tool: search_documents")

    # Conditionally register diff_documents tool (read-only)
    if config.enable_diff:

        @mcp.tool(name="diff_documents")
        def diff_documents(
            old: Annotated[
                str,
                "Original document: file path (within read allowlist), data URI, base64, or inline content. REQUIRED.",
            ],
            new: Annotated[
                str,
                "Updated document: file path (within read allowlist), data URI, base64, or inline content. REQUIRED.",
            ],
            format: Annotated[
                str, "Output format: 'unified' (default, plain text) or 'json' (structured)."
            ] = "unified",
            context_lines: Annotated[int, "Context lines around changes in unified output (default: 3)."] = 3,
            granularity: Annotated[str, "Comparison granularity: 'block' (default), 'sentence', or 'word'."] = "block",
            ignore_whitespace: Annotated[bool, "Normalize whitespace before comparing. Default: false."] = False,
        ) -> dict:
            """Compare two documents and return their differences.

            Each input is auto-detected (file path, data URI, base64, or inline
            content), so documents in any supported format can be compared — even
            across formats (e.g. a DOCX against its PDF export).

            Returns a dictionary with:
            - diff: the rendered diff (unified text or JSON string)
            - has_changes: whether any differences were found
            """
            input_obj = DiffDocumentsInput(
                old=old,
                new=new,
                format=cast(DiffFormat, format),
                context_lines=context_lines,
                granularity=cast(DiffGranularity, granularity),
                ignore_whitespace=ignore_whitespace,
            )
            with protect_stdout():
                result = diff_impl(input_obj, config)
            return {"diff": result.diff, "has_changes": result.has_changes}

        logger.info("Registered tool: diff_documents")

    # Conditionally register get_document_outline tool (read-only)
    if config.enable_outline:

        @mcp.tool(name="get_document_outline")
        def get_document_outline(
            doc: Annotated[
                str,
                "Document to outline: file path (within read allowlist), data URI, base64, "
                "or inline content. REQUIRED.",
            ],
            max_level: Annotated[int, "Deepest heading level to include, 1-6 (default: 6 = all levels)."] = 6,
            format_hint: Annotated[
                str | None,
                "Optional format hint for ambiguous/extensionless sources (e.g. 'pdf', 'docx', 'html').",
            ] = None,
        ) -> dict:
            """Return the heading structure (table of contents) of a document.

            Use this to navigate a large document before extracting specific
            sections: the returned indices line up with edit_document's '#N'
            target notation.

            Returns a dictionary with:
            - sections: list of {index, level, heading}
            - total: number of headings returned
            """
            input_obj = GetDocumentOutlineInput(
                doc=doc, max_level=max_level, format_hint=cast(SourceFormat | None, format_hint)
            )
            with protect_stdout():
                result = outline_impl(input_obj, config)
            return {"sections": result.sections, "total": result.total}

        logger.info("Registered tool: get_document_outline")

    # Conditionally register list_workspace_files tool (read-only)
    if config.enable_list_files:

        @mcp.tool(name="list_workspace_files")
        def list_workspace_files(
            subdirectory: Annotated[
                str | None,
                "Optional workspace-relative subdirectory to list. If omitted, all read folders are listed.",
            ] = None,
            pattern: Annotated[
                str | None,
                "Optional glob filter on file names, e.g. '*.pdf' or '*.docx'. Default: all files.",
            ] = None,
            recursive: Annotated[bool, "Recurse into subdirectories. Default: true."] = True,
        ) -> dict:
            """List files the server is allowed to read.

            Use this to discover what is available before reading or editing. Results
            are confined to the read allowlist (the workspace folder plus any additional
            read-only folders). Paths returned here can be passed directly to the other
            tools.

            Returns a dictionary with:
            - files: list of {path, size_bytes} (absolute paths, sorted)
            - total: number of files returned
            - truncated: true if more files exist than were returned (capped)
            - read_dirs: the read folders that were searched
            """
            input_obj = ListWorkspaceFilesInput(subdirectory=subdirectory, pattern=pattern, recursive=recursive)
            with protect_stdout():
                result = list_files_impl(input_obj, config)
            return {
                "files": result.files,
                "total": result.total,
                "truncated": result.truncated,
                "read_dirs": result.read_dirs,
            }

        logger.info("Registered tool: list_workspace_files")

    return mcp


def configure_logging(level: str) -> None:
    """Configure logging for the MCP server."""
    configure_root_logging(level, trace_mode=True)


def main() -> int:
    """Run all2md-mcp server."""
    try:
        # Route PyMuPDF's advisory messages to stderr (fd 2) instead of stdout,
        # which the stdio transport reserves for JSON-RPC. Must be set before
        # PyMuPDF is imported. protect_stdout() is the runtime backstop, but this
        # keeps even import-time advisories off the protocol channel.
        os.environ.setdefault("PYMUPDF_MESSAGE", "fd:2")

        # Configure logging with default level first (will be reconfigured if needed)
        configure_logging("INFO")

        # Load configuration
        config = load_config()

        # Reconfigure logging with user-specified level if different
        if config.log_level != "INFO":
            configure_logging(config.log_level)

        logger.info("Starting all2md MCP server")
        logger.info(
            f"Configuration: enable_to_md={config.enable_to_md}, "
            f"enable_from_md={config.enable_from_md}, enable_doc_edit={config.enable_doc_edit}, "
            f"enable_search={config.enable_search}, enable_diff={config.enable_diff}, "
            f"enable_outline={config.enable_outline}, enable_list_files={config.enable_list_files}"
        )
        logger.info(f"Include images: {config.include_images}")
        if config.search_index_dir:
            logger.info(f"Search index directory: {config.search_index_dir}")

        # Validate and prepare allowlists
        try:
            prepared_read = prepare_allowlist_dirs(config.read_allowlist)
            prepared_write = prepare_allowlist_dirs(config.write_allowlist)
            config = config.create_updated(read_allowlist=prepared_read, write_allowlist=prepared_write)
        except MCPSecurityError as e:
            logger.error(f"Invalid allowlist configuration: {e}")
            sys.exit(1)

        if config.read_allowlist:
            logger.info(f"Read allowlist: {len(config.read_allowlist)} directories")
            for dir_path in config.read_allowlist:
                logger.debug(f"  - {dir_path}")

        if config.write_allowlist:
            logger.info(f"Write allowlist: {len(config.write_allowlist)} directories")
            for dir_path in config.write_allowlist:
                logger.debug(f"  - {dir_path}")

        # Set network disable env var if configured (MUST be done before importing all2md)
        if config.disable_network:
            os.environ["ALL2MD_DISABLE_NETWORK"] = "true"
            logger.info("Network access disabled")
        else:
            # Clear or override the env var to ensure network is actually enabled
            if "ALL2MD_DISABLE_NETWORK" in os.environ:
                del os.environ["ALL2MD_DISABLE_NETWORK"]
            logger.warning("Network access enabled - ensure this is intentional!")

        # Import tool implementations after setting env vars
        from all2md.mcp.document_tools import edit_document_impl
        from all2md.mcp.query_tools import (
            diff_documents_impl,
            get_document_outline_impl,
            list_workspace_files_impl,
            search_documents_impl,
        )
        from all2md.mcp.tools import read_document_as_markdown_impl, save_document_from_markdown_impl

        # Create and run server
        mcp = create_server(
            config,
            read_document_as_markdown_impl,
            save_document_from_markdown_impl,
            edit_document_impl,
            search_documents_impl,
            diff_documents_impl,
            get_document_outline_impl,
            list_workspace_files_impl,
        )

        logger.info("Server ready, listening on stdio")
        mcp.run()  # Run with default stdio transport

    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e!r}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    main()
