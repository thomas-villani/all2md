"""FastMCP server for all2md document conversion.

This module implements the main MCP server using FastMCP with stdio transport.
It exposes convert_to_markdown and render_from_markdown tools to LLMs
with comprehensive security controls.

Functions
---------
- main: Server entry point (for CLI)

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import logging
import os
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any, cast

from all2md import DependencyError
from all2md.logging_utils import configure_logging as configure_root_logging

if TYPE_CHECKING:
    from fastmcp import FastMCP

from all2md.mcp.config import MCPConfig, load_config
from all2md.mcp.schemas import (
    EditDocumentAction,
    EditDocumentSimpleInput,
    EditDocumentSimpleOutput,
    ReadDocumentAsMarkdownInput,
    SaveDocumentFromMarkdownInput,
    SaveDocumentFromMarkdownOutput,
    SourceFormat,
    TargetFormat,
)
from all2md.mcp.security import MCPSecurityError, prepare_allowlist_dirs

logger = logging.getLogger(__name__)


def create_server(
    config: MCPConfig,
    read_impl: Callable[[ReadDocumentAsMarkdownInput, MCPConfig], list[Any]],
    save_impl: Callable[[SaveDocumentFromMarkdownInput, MCPConfig], SaveDocumentFromMarkdownOutput],
    edit_doc_impl: Callable[[EditDocumentSimpleInput, MCPConfig], EditDocumentSimpleOutput],
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

            result = save_impl(input_obj, config)

            return {"output_path": result.output_path, "warnings": result.warnings}

        logger.info("Registered tool: save_document_from_markdown")

    # Conditionally register edit_document tool
    if config.enable_doc_edit:

        @mcp.tool(name="edit_document")
        def edit_document(
            action: Annotated[
                str,
                "Action to perform: list-sections, extract, add:before, add:after, remove, replace, "
                "insert:start, insert:end, insert:after_heading. REQUIRED.",
            ],
            doc: Annotated[str, "File path to the document (must be within read allowlist). REQUIRED."],
            target: Annotated[
                str | None,
                "Section to target. Either heading text (case-insensitive) like 'Introduction', or "
                "index notation like '#0', '#1', '#2' (zero-based). Required for all actions except "
                "list-sections.",
            ] = None,
            content: Annotated[
                str | None,
                "Markdown content to add/replace/insert. Required for add:before, add:after, replace, "
                "insert:start, insert:end, and insert:after_heading actions.",
            ] = None,
        ) -> dict:
            """Edit markdown documents by manipulating their structure.

            This tool provides a simplified interface for document manipulation with sensible
            LLM-friendly defaults (markdown only, case-insensitive heading matching, GFM flavor).

            Available actions:
            - list-sections: List all sections with metadata (returns formatted section list)
            - extract: Get a specific section by heading or index (returns section content)
            - add:before: Add new section before the target section
            - add:after: Add new section after the target section
            - remove: Remove a section from the document
            - replace: Replace section content with new content
            - insert:start: Insert content at the start of a section
            - insert:end: Insert content at the end of a section
            - insert:after_heading: Insert content right after the section heading

            Target format:
            - Heading text: "Introduction", "Methods and Results", etc. (case-insensitive)
            - Index notation: "#0" (first section), "#1" (second section), etc.

            Requires --enable-doc-edit flag (disabled by default for security).

            Returns a dictionary with:
            - success: Boolean indicating if operation succeeded
            - message: Human-readable result or error message
            - content: Content from operation (for list-sections and extract actions)
            """
            # Cast to proper Literal type (FastMCP validates at the boundary)
            input_obj = EditDocumentSimpleInput(
                action=cast(EditDocumentAction, action), doc=doc, target=target, content=content
            )

            result = edit_doc_impl(input_obj, config)

            return {"success": result.success, "message": result.message, "content": result.content}

        logger.info("Registered tool: edit_document")

    return mcp


def configure_logging(level: str) -> None:
    """Configure logging for the MCP server."""
    configure_root_logging(level, trace_mode=True)


def main() -> int:
    """Run all2md-mcp server."""
    try:
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
            f"enable_from_md={config.enable_from_md}, enable_doc_edit={config.enable_doc_edit}"
        )
        logger.info(f"Include images: {config.include_images}")

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
        from all2md.mcp.tools import read_document_as_markdown_impl, save_document_from_markdown_impl

        # Create and run server
        mcp = create_server(
            config, read_document_as_markdown_impl, save_document_from_markdown_impl, edit_document_impl
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
