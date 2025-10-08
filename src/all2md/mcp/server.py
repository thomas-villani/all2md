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
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from fastmcp import FastMCP

from all2md.mcp.config import MCPConfig, load_config
from all2md.mcp.schemas import (
    ConvertToMarkdownInput,
    RenderFromMarkdownInput,
)
from all2md.mcp.security import MCPSecurityError, prepare_allowlist_dirs
from all2md.mcp.tools import convert_to_markdown_impl, render_from_markdown_impl

logger = logging.getLogger(__name__)


def create_server(config: MCPConfig) -> "FastMCP":
    """Create and configure FastMCP server with tools.

    Parameters
    ----------
    config : MCPConfig
        Server configuration

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
        ) -> dict:
            """Convert a document to Markdown format.

            Supports PDF, Word (DOCX), PowerPoint (PPTX), HTML, email (EML), EPUB,
            Jupyter Notebooks (IPYNB), Excel (XLSX/CSV), ODF formats, and 200+ text formats.

            Source input must be provided as either source_path OR source_content (not both).
            Attachment handling (images, embedded files) is configured at server startup and cannot be changed per-call.

            Returns a dictionary with:
            - markdown: The converted markdown content as a string
            - attachments: List of attachment paths (if attachment_mode=download at server level)
            - warnings: List of warning messages from the conversion process
            """
            input_obj = ConvertToMarkdownInput(
                source_path=source_path,
                source_content=source_content,
                content_encoding=content_encoding,  # type: ignore[arg-type]
                source_format=source_format,  # type: ignore[arg-type]
                flavor=flavor,  # type: ignore[arg-type]
                pdf_pages=pdf_pages
            )

            result = convert_to_markdown_impl(input_obj, config)

            return {
                "markdown": result.markdown,
                "attachments": result.attachments,
                "warnings": result.warnings
            }

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
            input_obj = RenderFromMarkdownInput(
                target_format=target_format,  # type: ignore[arg-type]
                markdown=markdown,
                markdown_path=markdown_path,
                output_path=output_path,
                flavor=flavor  # type: ignore[arg-type]
            )

            result = render_from_markdown_impl(input_obj, config)

            return {
                "content": result.content,
                "output_path": result.output_path,
                "warnings": result.warnings
            }

        logger.info("Registered tool: render_from_markdown")

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


def main() -> None:
    """Run all2md-mcp server."""
    try:
        # Load configuration
        config = load_config()

        # Configure logging
        configure_logging(config.log_level)

        logger.info("Starting all2md MCP server")
        logger.info(f"Configuration: enable_to_md={config.enable_to_md}, enable_from_md={config.enable_from_md}")
        logger.info(f"Attachment mode: {config.attachment_mode}")
        if config.attachment_output_dir:
            logger.info(f"Attachment output dir: {config.attachment_output_dir}")

        # Validate and prepare allowlists
        try:
            config.read_allowlist = prepare_allowlist_dirs(config.read_allowlist)
            config.write_allowlist = prepare_allowlist_dirs(config.write_allowlist)
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

        # Set network disable env var if configured
        if config.disable_network:
            os.environ['ALL2MD_DISABLE_NETWORK'] = 'true'
            logger.info("Network access disabled")
        else:
            logger.warning("Network access enabled - ensure this is intentional!")

        # Create and run server
        mcp = create_server(config)

        logger.info("Server ready, listening on stdio")
        mcp.run()  # Run with default stdio transport

    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
