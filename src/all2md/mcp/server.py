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
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

if TYPE_CHECKING:
    from fastmcp import FastMCP

from all2md.mcp.config import MCPConfig, load_config
from all2md.mcp.schemas import (
    ConvertToMarkdownInput,
    EditDocumentInput,
    EditDocumentOutput,
    EditOperation,
    InsertPosition,
    MarkdownFlavor,
    OutputFormat,
    RenderFromMarkdownInput,
    RenderFromMarkdownOutput,
    SourceFormat,
    TargetFormat,
    TOCStyle,
)
from all2md.mcp.security import MCPSecurityError, prepare_allowlist_dirs

logger = logging.getLogger(__name__)

# Type alias for content encoding
ContentEncoding = Literal["plain", "base64"]


def create_server(
    config: MCPConfig,
    convert_impl: Callable[[ConvertToMarkdownInput, MCPConfig], list[Any]],
    render_impl: Callable[[RenderFromMarkdownInput, MCPConfig], RenderFromMarkdownOutput],
    edit_doc_impl: Callable[[EditDocumentInput, MCPConfig], EditDocumentOutput]
) -> "FastMCP":
    """Create and configure FastMCP server with tools.

    Parameters
    ----------
    config : MCPConfig
        Server configuration
    convert_impl : callable
        Implementation function for convert_to_markdown tool
    render_impl : callable
        Implementation function for render_from_markdown tool
    edit_doc_impl : callable
        Implementation function for edit_document_ast tool

    Returns
    -------
    FastMCP
        Configured MCP server instance

    """
    try:
        from fastmcp import FastMCP
    except ImportError as e:
        print("Error: FastMCP not installed. Install with: pip install 'all2md[mcp]'", file=sys.stderr)
        raise ImportError("FastMCP not installed") from e

    # Create MCP server
    mcp = FastMCP(name="all2md")

    # Conditionally register convert_to_markdown tool
    if config.enable_to_md:
        @mcp.tool(name="convert_to_markdown")
        def convert_to_markdown(
            source_path: Annotated[
                str | None,
                "File path to convert. Must be within read allowlist. Mutually exclusive with source_content."
            ] = None,
            source_content: Annotated[
                str | None,
                "Inline content to convert (plain text or base64-encoded). For text formats (HTML, "
                "Markdown): pass plain text. For binary formats (PDF, DOCX): pass base64-encoded and "
                "set content_encoding='base64'. Mutually exclusive with source_path."
            ] = None,
            content_encoding: Annotated[
                str | None,
                "Encoding of source_content: 'plain' (default) or 'base64'. Only relevant when "
                "source_content is provided."
            ] = None,
            source_format: Annotated[
                str,
                "Source format for auto-detection or explicit specification. Options: auto (default), "
                "pdf, docx, pptx, html, eml, epub, ipynb, odt, odp, ods, xlsx, csv, rst, markdown, txt."
            ] = "auto",
            flavor: Annotated[
                str | None,
                "Markdown flavor/dialect for output. Options: gfm (default), commonmark, "
                "multimarkdown, pandoc, kramdown, markdown_plus."
            ] = None,
            pdf_pages: Annotated[
                str | None,
                "Page specification for PDF sources only. Examples: '1-3' (pages 1-3), '1,3,5' "
                "(specific pages), '1-3,5,10-' (ranges and individual pages), '1-' (from page 1 to end)."
            ] = None
        ) -> list:
            """Convert a document to Markdown format.

            Supports PDF, Word (DOCX), PowerPoint (PPTX), HTML, email (EML), EPUB,
            Jupyter Notebooks (IPYNB), Excel (XLSX/CSV), ODF formats, and 200+ text formats.

            Source input must be provided as either source_path OR source_content (not both).
            Attachment handling (images, embedded files) is configured at server startup and cannot be changed per-call.

            Returns a list with markdown text as the first element, followed by FastMCP Image
            objects for any images found (when attachment_mode=base64). For other attachment
            modes (skip, alt_text), returns just the markdown text.

            FastMCP automatically converts this list into appropriate MCP content blocks,
            allowing vLLMs to "see" the images alongside the text.
            """
            # Cast to proper Literal types (FastMCP validates these at the boundary)
            input_obj = ConvertToMarkdownInput(
                source_path=source_path,
                source_content=source_content,
                content_encoding=cast(ContentEncoding | None, content_encoding),
                source_format=cast(SourceFormat, source_format),
                flavor=cast(MarkdownFlavor | None, flavor),
                pdf_pages=pdf_pages
            )

            # Return list directly - FastMCP converts to content blocks
            return convert_impl(input_obj, config)

        logger.info("Registered tool: convert_to_markdown")

    # Conditionally register render_from_markdown tool
    if config.enable_from_md:
        @mcp.tool(name="render_from_markdown")
        def render_from_markdown(
            target_format: Annotated[
                str,
                "Target output format. Options: html, pdf, docx, pptx, rst, epub, markdown. REQUIRED."
            ],
            markdown: Annotated[
                str | None,
                "Markdown content as a string to convert. Mutually exclusive with markdown_path."
            ] = None,
            markdown_path: Annotated[
                str | None,
                "Path to markdown file to convert. Must be within read allowlist. Mutually exclusive with markdown."
            ] = None,
            output_path: Annotated[
                str | None,
                "Output file path. Must be within write allowlist. If not provided, content is "
                "returned (base64-encoded for binary formats like PDF/DOCX)."
            ] = None,
            flavor: Annotated[
                str | None,
                "Markdown flavor for parsing input. Options: gfm (default), commonmark, "
                "multimarkdown, pandoc, kramdown, markdown_plus."
            ] = None
        ) -> dict:
            """Convert Markdown content to another format.

            Supports rendering to HTML, PDF, DOCX, PPTX, RST, EPUB, and Markdown.

            Source must be provided as either markdown OR markdown_path (not both).
            This tool requires --enable-from-md flag (disabled by default for security).

            Returns a dictionary with:
            - content: Rendered content (if output_path not specified). Binary formats are base64-encoded.
            - output_path: File path where content was written (if output_path was specified)
            - warnings: List of warning messages from the rendering process
            """
            # Cast to proper Literal types (FastMCP validates these at the boundary)
            input_obj = RenderFromMarkdownInput(
                target_format=cast(TargetFormat, target_format),
                markdown=markdown,
                markdown_path=markdown_path,
                output_path=output_path,
                flavor=cast(MarkdownFlavor | None, flavor)
            )

            result = render_impl(input_obj, config)

            return {
                "content": result.content,
                "output_path": result.output_path,
                "warnings": result.warnings
            }

        logger.info("Registered tool: render_from_markdown")

    # Conditionally register edit_document_ast tool
    if config.enable_doc_edit:
        @mcp.tool(name="edit_document_ast")
        def edit_document_ast(
            operation: Annotated[
                str,
                "Operation to perform: list_sections, get_section, add_section, remove_section, "
                "replace_section, insert_content, generate_toc, split_document. REQUIRED."
            ],
            source_path: Annotated[
                str | None,
                "File path to document (must be within read allowlist). Mutually exclusive with source_content."
            ] = None,
            source_content: Annotated[
                str | None,
                "Document content as string (markdown or AST JSON). Mutually exclusive with source_path."
            ] = None,
            content_encoding: Annotated[
                str | None,
                "Encoding of source_content: 'plain' (default) or 'base64'."
            ] = None,
            source_format: Annotated[
                str,
                "Format of source content: 'markdown' (default) or 'ast_json'."
            ] = "markdown",
            target_heading: Annotated[
                str | None,
                "Heading text to target for section operations. Mutually exclusive with target_index."
            ] = None,
            target_index: Annotated[
                int | None,
                "Zero-based section index to target. Mutually exclusive with target_heading."
            ] = None,
            content: Annotated[
                str | None,
                "Content to add/insert (markdown format). Required for add_section, replace_section, insert_content."
            ] = None,
            position: Annotated[
                str | None,
                "Position for add/insert operations: 'before', 'after', 'start', 'end', 'after_heading'."
            ] = None,
            case_sensitive: Annotated[
                bool,
                "Whether heading text matching is case-sensitive (default: false)."
            ] = False,
            max_toc_level: Annotated[
                int,
                "Maximum heading level for TOC generation (default: 3)."
            ] = 3,
            toc_style: Annotated[
                str,
                "Style for TOC generation: 'markdown', 'list', 'nested' (default: 'markdown')."
            ] = "markdown",
            flavor: Annotated[
                str | None,
                "Markdown flavor for parsing/rendering: gfm (default), commonmark, multimarkdown, etc."
            ] = None,
            output_path: Annotated[
                str | None,
                "Output file path (must be within write allowlist). If not provided, content is returned."
            ] = None,
            output_format: Annotated[
                str,
                "Format for output content: 'markdown' (default) or 'ast_json'."
            ] = "markdown"
        ) -> dict:
            """Manipulate document structure at the AST level.

            This tool allows structural document manipulation including:
            - list_sections: Get metadata about all sections in the document
            - get_section: Extract a specific section by heading text or index
            - add_section: Add new section before or after a target section
            - remove_section: Delete a section from the document
            - replace_section: Replace section content with new content
            - insert_content: Insert content into an existing section
            - generate_toc: Generate table of contents from headings
            - split_document: Split document into separate documents by sections

            Requires --enable-doc-edit flag (disabled by default for security).

            Returns a dictionary with:
            - content: Modified document (if output_path not specified)
            - sections: Section metadata (for list_sections operation)
            - section_count: Number of sections (for list_sections)
            - sections_modified: Number of sections affected by operation
            - output_path: File path where content was written (if output_path specified)
            - warnings: List of warning messages
            """
            # Cast to proper Literal types (FastMCP validates these at the boundary)
            input_obj = EditDocumentInput(
                operation=cast(EditOperation, operation),
                source_path=source_path,
                source_content=source_content,
                content_encoding=cast(ContentEncoding | None, content_encoding),
                source_format=cast(Any, source_format),
                target_heading=target_heading,
                target_index=target_index,
                content=content,
                position=cast(InsertPosition | None, position),
                case_sensitive=case_sensitive,
                max_toc_level=max_toc_level,
                toc_style=cast(TOCStyle, toc_style),
                flavor=cast(MarkdownFlavor | None, flavor),
                output_path=output_path,
                output_format=cast(OutputFormat, output_format)
            )

            result = edit_doc_impl(input_obj, config)

            return {
                "content": result.content,
                "sections": [
                    {
                        "index": s.index,
                        "heading_text": s.heading_text,
                        "level": s.level,
                        "content_nodes": s.content_nodes,
                        "start_index": s.start_index,
                        "end_index": s.end_index
                    }
                    for s in (result.sections or [])
                ],
                "section_count": result.section_count,
                "sections_modified": result.sections_modified,
                "output_path": result.output_path,
                "warnings": result.warnings
            }

        logger.info("Registered tool: edit_document_ast")

    return mcp


def configure_logging(level: str) -> None:
    """Configure logging for the MCP server.

    Parameters
    ----------
    level : str
        Logging level (DEBUG|INFO|WARNING|ERROR)

    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stderr)]  # Log to stderr, not stdout (MCP uses stdout)
    )


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
        logger.info(f"Configuration: enable_to_md={config.enable_to_md}, enable_from_md={config.enable_from_md}, enable_doc_edit={config.enable_doc_edit}")
        logger.info(f"Attachment mode: {config.attachment_mode}")

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
            os.environ['ALL2MD_DISABLE_NETWORK'] = 'true'
            logger.info("Network access disabled")
        else:
            logger.warning("Network access enabled - ensure this is intentional!")

        # Import tool implementations after setting env vars
        from all2md.mcp.tools import convert_to_markdown_impl, render_from_markdown_impl
        from all2md.mcp.document_tools import edit_document_ast_impl

        # Create and run server
        mcp = create_server(config, convert_to_markdown_impl, render_from_markdown_impl, edit_document_ast_impl)

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
