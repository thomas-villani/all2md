"""Tool implementations for MCP server.

This module implements the actual tool functions that handle convert_to_markdown
and render_from_markdown requests. These functions validate inputs, apply
security checks, and delegate to all2md's core API.

Functions
---------
- convert_to_markdown_impl: Implementation of convert_to_markdown tool
- render_from_markdown_impl: Implementation of render_from_markdown tool

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import base64
import logging
import re
from pathlib import Path
from typing import Any, cast

from all2md import from_ast, from_markdown, to_ast
from all2md.ast.nodes import Image
from all2md.ast.transforms import NodeCollector
from all2md.constants import DocumentFormat
from all2md.exceptions import All2MdError
from all2md.mcp.config import MCPConfig
from all2md.mcp.schemas import (
    ConvertToMarkdownInput,
    RenderFromMarkdownInput,
    RenderFromMarkdownOutput,
)
from all2md.mcp.security import validate_read_path, validate_write_path

try:
    from fastmcp.utilities.types import Image as FastMCPImage
except ImportError:
    FastMCPImage = None  # type: ignore[misc, assignment]

logger = logging.getLogger(__name__)


def _extract_images_from_ast(doc: Any) -> list[Any]:
    """Extract base64-encoded images from AST as FastMCP Image objects.

    Parameters
    ----------
    doc : Document
        AST Document node to extract images from

    Returns
    -------
    list[FastMCPImage]
        List of FastMCP Image objects extracted from data URIs in the AST.
        Returns empty list if FastMCP is not available or no images found.

    Notes
    -----
    This function looks for Image nodes in the AST with data URI urls
    (format: data:image/FORMAT;base64,DATA) and converts them to FastMCP
    Image objects that can be sent to vLLMs alongside markdown text.

    """
    if FastMCPImage is None:
        logger.warning("FastMCP not available, cannot extract images")  # type: ignore[unreachable]
        return []

    # Collect all Image nodes from AST
    collector = NodeCollector(predicate=lambda n: isinstance(n, Image))
    doc.accept(collector)

    fastmcp_images = []
    for img_node in collector.collected:
        # Parse data URI: data:image/png;base64,iVBOR...
        if not isinstance(img_node, Image):
            continue

        match = re.match(r'data:image/(\w+);base64,(.+)', img_node.url)
        if match:
            img_format = match.group(1)
            b64_data = match.group(2)
            try:
                img_bytes = base64.b64decode(b64_data)
                fastmcp_images.append(FastMCPImage(data=img_bytes, format=img_format))
                logger.debug(f"Extracted {img_format} image ({len(img_bytes)} bytes)")
            except Exception as e:
                logger.warning(f"Failed to decode image data URI: {e}")

    logger.info(f"Extracted {len(fastmcp_images)} images from AST")
    return fastmcp_images


def convert_to_markdown_impl(
    input_data: ConvertToMarkdownInput,
    config: MCPConfig
) -> list[Any]:
    """Implement convert_to_markdown tool.

    This implementation uses AST-based processing to extract images as FastMCP
    Image objects, allowing vLLMs to "see" the images alongside markdown text.

    Parameters
    ----------
    input_data : ConvertToMarkdownInput
        Tool input parameters
    config : MCPConfig
        Server configuration (for allowlists, etc.)
        Note: attachment_mode is overridden to "base64" for MCP compatibility

    Returns
    -------
    list
        List with markdown string as first element, followed by FastMCP Image
        objects for any images found in the document. FastMCP automatically
        converts this to appropriate MCP content blocks.

    Raises
    ------
    MCPSecurityError
        If security validation fails
    All2MdError
        If conversion fails

    """
    # Validate mutually exclusive inputs
    if input_data.source_path and input_data.source_content:
        raise ValueError("Cannot specify both source_path and source_content")

    if not input_data.source_path and not input_data.source_content:
        raise ValueError("Must specify either source_path or source_content")

    # Prepare source
    source: Path | bytes
    if input_data.source_path:
        # Validate read access
        validated_path = validate_read_path(
            input_data.source_path,
            config.read_allowlist
        )
        source = validated_path
        logger.info(f"Converting file: {validated_path}")

    else:
        # Handle inline content (plain text or base64-encoded)
        encoding = input_data.content_encoding or "plain"

        if encoding == "base64":
            # Decode base64 content
            if not input_data.source_content:
                raise ValueError("source_content cannot be empty for base64 encoding")
            try:
                source_bytes = base64.b64decode(input_data.source_content)
                source = source_bytes
                logger.info(f"Converting base64 content ({len(source_bytes)} bytes)")
            except Exception as e:
                raise ValueError(f"Invalid base64 encoding: {e}") from e
        else:
            # Use plain text content (for text-based formats like HTML, Markdown, etc.)
            if not input_data.source_content:
                raise ValueError("source_content cannot be empty")
            source = input_data.source_content.encode('utf-8')
            logger.info(f"Converting text content ({len(input_data.source_content)} characters)")

    # Prepare conversion options
    kwargs: dict[str, Any] = {}

    # Add PDF-specific options if needed
    if input_data.pdf_pages:
        # Validate page specification format before passing to converter
        # (Full validation with page count happens in converter)
        page_spec = input_data.pdf_pages.strip()
        if not re.match(r'^[\d\s,\-]+$', page_spec):
            raise ValueError(
                f"Invalid page range format: '{input_data.pdf_pages}'. "
                "Expected format like '1-3,5,10-' with only digits, commas, and hyphens."
            )
        kwargs['pages'] = page_spec

    # Set markdown flavor if specified
    if input_data.flavor:
        kwargs['flavor'] = input_data.flavor

    # Set attachment mode from server config (only skip, alt_text, or base64 allowed)
    kwargs['attachment_mode'] = config.attachment_mode

    # Perform conversion using AST approach
    try:
        # Convert to AST first (allows us to extract images)
        doc = to_ast(
            source,
            source_format=cast(DocumentFormat, input_data.source_format),
            **kwargs
        )

        # Extract images if in base64 mode (for vLLM visibility)
        images: list[Any] = []
        if config.attachment_mode == "base64":
            images = _extract_images_from_ast(doc)
            if images:
                logger.info(f"Extracted {len(images)} images for vLLM")

        # Convert AST to markdown
        flavor_kwargs: dict[str, Any] = {'flavor': input_data.flavor} if input_data.flavor else {}
        markdown = from_ast(
            doc,
            target_format="markdown",
            **cast(Any, flavor_kwargs)
        )

        if not isinstance(markdown, str):
            raise TypeError(f"Expected markdown string, got {type(markdown)}")

        logger.info(f"Conversion successful ({len(markdown)} characters)")

        # Return list with markdown + images (FastMCP handles content blocks)
        return [markdown] + images

    except All2MdError as e:
        logger.error(f"Conversion failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during conversion: {e}")
        raise All2MdError(f"Conversion failed: {e}") from e


def render_from_markdown_impl(
    input_data: RenderFromMarkdownInput,
    config: MCPConfig
) -> RenderFromMarkdownOutput:
    """Implement render_from_markdown tool.

    Parameters
    ----------
    input_data : RenderFromMarkdownInput
        Tool input parameters
    config : MCPConfig
        Server configuration (for allowlists, etc.)

    Returns
    -------
    RenderFromMarkdownOutput
        Rendering result with content or output path

    Raises
    ------
    MCPSecurityError
        If security validation fails
    All2MdError
        If rendering fails

    """
    warnings: list[str] = []

    # Validate mutually exclusive inputs
    if input_data.markdown and input_data.markdown_path:
        raise ValueError("Cannot specify both markdown and markdown_path")

    if not input_data.markdown and not input_data.markdown_path:
        raise ValueError("Must specify either markdown or markdown_path")

    # Prepare markdown source
    markdown_source: str
    if input_data.markdown_path:
        # Validate read access
        validated_path = validate_read_path(
            input_data.markdown_path,
            config.read_allowlist
        )
        markdown_source = str(validated_path)
        logger.info(f"Rendering from file: {validated_path}")

    else:
        # Use provided markdown content
        markdown_source = input_data.markdown or ""
        logger.info(f"Rendering from markdown content ({len(markdown_source)} characters)")

    # Prepare output
    output_arg = None
    if input_data.output_path:
        # Validate write access
        validated_output = validate_write_path(
            input_data.output_path,
            config.write_allowlist
        )
        output_arg = str(validated_output)
        logger.info(f"Writing output to: {validated_output}")

    # Prepare rendering options
    kwargs: dict[str, Any] = {}
    if input_data.flavor:
        kwargs['flavor'] = input_data.flavor

    # Perform rendering
    try:
        # Cast target_format (TargetFormat is a subset of DocumentFormat)
        result = from_markdown(
            markdown_source,
            target_format=cast(DocumentFormat, input_data.target_format),
            output=output_arg,
            **kwargs
        )

        # If output_path was specified, result is None (file written)
        if output_arg:
            logger.info(f"Rendering successful, written to {output_arg}")
            return RenderFromMarkdownOutput(
                output_path=output_arg,
                warnings=warnings
            )

        # Otherwise, return content
        else:
            # Handle different content types
            if result is None:
                raise ValueError("Rendering returned None unexpectedly")
            elif isinstance(result, str):
                content = result
            elif isinstance(result, bytes):
                # Base64 encode binary content
                content = base64.b64encode(result).decode('ascii')
                warnings.append("Binary content returned as base64-encoded string")
            elif hasattr(result, 'read'):  # type: ignore[unreachable]
                # Handle BytesIO and other file-like objects from binary renderers
                binary_content = result.read()
                content = base64.b64encode(binary_content).decode('ascii')
                warnings.append("Binary content returned as base64-encoded string")
            else:
                raise TypeError(f"Unexpected result type: {type(result)}")

            logger.info(f"Rendering successful ({len(content)} characters)")
            return RenderFromMarkdownOutput(
                content=content,
                warnings=warnings
            )

    except All2MdError as e:
        logger.error(f"Rendering failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during rendering: {e}")
        raise All2MdError(f"Rendering failed: {e}") from e
