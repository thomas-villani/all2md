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
from pathlib import Path

from all2md import from_markdown, to_markdown
from all2md.exceptions import All2MdError
from all2md.mcp.config import MCPConfig
from all2md.mcp.schemas import (
    ConvertToMarkdownInput,
    ConvertToMarkdownOutput,
    RenderFromMarkdownInput,
    RenderFromMarkdownOutput,
)
from all2md.mcp.security import MCPSecurityError, validate_read_path, validate_write_path
from all2md.options import PdfOptions

logger = logging.getLogger(__name__)


def convert_to_markdown_impl(
    input_data: ConvertToMarkdownInput,
    config: MCPConfig
) -> ConvertToMarkdownOutput:
    """Implementation of convert_to_markdown tool.

    Parameters
    ----------
    input_data : ConvertToMarkdownInput
        Tool input parameters
    config : MCPConfig
        Server configuration (for attachment settings, allowlists, etc.)

    Returns
    -------
    ConvertToMarkdownOutput
        Conversion result with markdown content and metadata

    Raises
    ------
    MCPSecurityError
        If security validation fails
    All2MdError
        If conversion fails

    """
    warnings: list[str] = []

    # Validate mutually exclusive inputs
    if input_data.source_path and input_data.source_content:
        raise ValueError("Cannot specify both source_path and source_content")

    if not input_data.source_path and not input_data.source_content:
        raise ValueError("Must specify either source_path or source_content")

    # Prepare source
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
            try:
                source_bytes = base64.b64decode(input_data.source_content)  # type: ignore[arg-type]
                source = source_bytes
                logger.info(f"Converting base64 content ({len(source_bytes)} bytes)")
            except Exception as e:
                raise ValueError(f"Invalid base64 encoding: {e}") from e
        else:
            # Use plain text content (for text-based formats like HTML, Markdown, etc.)
            source = input_data.source_content.encode('utf-8')  # type: ignore[union-attr]
            logger.info(f"Converting text content ({len(input_data.source_content)} characters)")  # type: ignore[arg-type]

    # Prepare conversion options
    kwargs = {}

    # Add PDF-specific options if needed
    if input_data.pdf_pages:
        # Parse page spec and pass to PdfOptions
        kwargs['pages'] = input_data.pdf_pages

    # Set markdown flavor if specified
    if input_data.flavor:
        kwargs['flavor'] = input_data.flavor

    # Set attachment mode from server config (not per-call!)
    kwargs['attachment_mode'] = config.attachment_mode

    # Set attachment output dir if download mode
    if config.attachment_mode == "download":
        if not config.attachment_output_dir:
            raise ValueError("Server not configured for attachment download mode")

        # Validate write access to attachment dir
        validated_attachment_dir = validate_write_path(
            config.attachment_output_dir,
            config.write_allowlist
        )
        kwargs['attachment_output_dir'] = str(validated_attachment_dir)

    # Perform conversion
    try:
        markdown = to_markdown(
            source,
            source_format=input_data.source_format,  # type: ignore[arg-type]
            **kwargs
        )

        # Collect attachment paths if in download mode
        attachments: list[str] = []
        if config.attachment_mode == "download" and config.attachment_output_dir:
            # List files in attachment output dir (simplified - in production you'd
            # track which files were created by this conversion)
            attachment_dir = Path(config.attachment_output_dir)
            if attachment_dir.exists() and attachment_dir.is_dir():
                # For now, just return empty list - proper implementation would
                # require tracking attachment creation during conversion
                attachments = []
                warnings.append(
                    "Attachment tracking not fully implemented - check attachment_output_dir manually"
                )

        logger.info(f"Conversion successful ({len(markdown)} characters)")

        return ConvertToMarkdownOutput(
            markdown=markdown,
            attachments=attachments,
            warnings=warnings
        )

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
    """Implementation of render_from_markdown tool.

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
        markdown_source = input_data.markdown
        logger.info(f"Rendering from markdown content ({len(input_data.markdown)} characters)")

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
    kwargs = {}
    if input_data.flavor:
        kwargs['flavor'] = input_data.flavor

    # Perform rendering
    try:
        result = from_markdown(
            markdown_source,
            target_format=input_data.target_format,  # type: ignore[arg-type]
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
            if isinstance(result, str):
                content = result
            elif isinstance(result, bytes):
                # Base64 encode binary content
                content = base64.b64encode(result).decode('ascii')
                warnings.append("Binary content returned as base64-encoded string")
            elif hasattr(result, 'read'):
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
