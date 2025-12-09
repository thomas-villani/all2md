"""Tool implementations for MCP server.

This module implements the simplified tool functions for reading documents
as markdown and saving markdown to other formats.

Functions
---------
- read_document_as_markdown_impl: Implementation of read_document_as_markdown tool
- save_document_from_markdown_impl: Implementation of save_document_from_markdown tool

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import base64
import logging
import re
from pathlib import Path
from typing import Any, cast, get_args
from urllib.parse import unquote

from all2md.api import from_ast, from_markdown, to_ast
from all2md.ast.nodes import Document, Image
from all2md.ast.sections import extract_sections
from all2md.ast.transforms import NodeCollector
from all2md.constants import DocumentFormat
from all2md.exceptions import All2MdError
from all2md.mcp.config import MCPConfig
from all2md.mcp.schemas import (
    ReadDocumentAsMarkdownInput,
    SaveDocumentFromMarkdownInput,
    SaveDocumentFromMarkdownOutput,
    SourceFormat,
)
from all2md.mcp.security import secure_open_for_write, validate_read_path, validate_write_path

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

        match = re.match(r"data:image/(\w+);base64,(.+)", img_node.url)
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


def _detect_source_type(source: str, config: MCPConfig) -> tuple[Path | bytes, str]:
    """Detect and prepare source from unified source parameter.

    Parameters
    ----------
    source : str
        Unified source string (path, data URI, base64, or plain text)
    config : MCPConfig
        Server configuration for allowlist validation

    Returns
    -------
    tuple[Path | bytes, str]
        Tuple of (prepared_source, detection_type) where detection_type is
        one of: "path", "data_uri", "base64", "plain_text"

    Raises
    ------
    MCPSecurityError
        If path validation fails

    """
    # Quick checks to skip path detection for obvious content types
    if source.startswith("<") or "<" in source[:100]:  # HTML/XML content
        logger.debug("Skipping path detection: appears to be HTML/XML content")
    elif source.startswith("data:"):  # Data URI
        logger.debug("Skipping path detection: appears to be data URI")
    # 1. Try to resolve as file path (if looks plausible and not HTML/JSON/etc)
    elif (
        "/" in source or "\\" in source or ("." in source and len(source) < 500)  # Has path separators
    ):  # Or has dot and reasonable length
        try:
            path_obj = Path(source)
            # Only validate if the path actually exists on the filesystem
            # This prevents false positives when text happens to contain path-like strings
            if path_obj.exists():
                validated_path = validate_read_path(path_obj, config.read_allowlist)
                logger.info(f"Detected as file path: {validated_path}")
                return validated_path, "path"
            else:
                # Path doesn't exist, continue to other detection methods
                logger.debug(f"Path does not exist: {path_obj}, treating as content")
        except (OSError, ValueError):
            # Not a valid path, continue to other detection methods
            pass

    # 2. Check for data URI format (data:...)
    if source.startswith("data:"):
        # Parse data URI: data:[<mediatype>][;base64],<data>
        match = re.match(r"data:([^;,]+)?(;base64)?,(.+)", source)
        if match:
            is_base64 = match.group(2) is not None
            data_part = match.group(3)
            try:
                if is_base64:
                    decoded = base64.b64decode(data_part)
                    logger.info(f"Detected as data URI (base64, {len(decoded)} bytes)")
                    return decoded, "data_uri"
                else:
                    # URL-decode the data part for non-base64 data URIs

                    decoded_str = unquote(data_part)
                    logger.info(f"Detected as data URI (plain, {len(decoded_str)} chars)")
                    return decoded_str.encode("utf-8"), "data_uri"
            except Exception as e:
                logger.warning(f"Failed to decode data URI: {e}")
                # Fall through to next detection method

    # 3. Attempt base64 decode (if looks like base64)
    # Use strict heuristics to avoid misidentifying plain text as base64
    # Base64 strings are typically:
    # - Long (files are hundreds+ chars when base64 encoded)
    # - Have diverse character set (not just AAAABBBB...)
    # - Length is multiple of 4 (after removing whitespace)
    # - Have proper padding with = at end (if not multiple of 4)
    if len(source) > 100 and re.match(r"^[A-Za-z0-9+/=\s]+$", source):
        try:
            # Remove whitespace before decoding
            cleaned = re.sub(r"\s", "", source)

            # Validate base64 structure:
            # 1. Length must be multiple of 4
            if len(cleaned) % 4 != 0:
                logger.debug("Rejecting as base64: length not multiple of 4")
            # 2. Check character diversity (entropy check)
            # Plain text like "AAAAAABBBBBB" would have low diversity
            elif len(set(cleaned.replace("=", ""))) < 4:
                logger.debug("Rejecting as base64: insufficient character diversity")
            else:
                # Attempt decode with validation
                decoded = base64.b64decode(cleaned, validate=True)
                # Only accept if decoded size makes sense (meaningful file content)
                # Minimum 50 bytes to avoid treating short passwords as base64
                if len(decoded) >= 50:
                    logger.info(f"Detected as base64 ({len(decoded)} bytes)")
                    return decoded, "base64"
                else:
                    logger.debug(f"Rejecting as base64: decoded size too small ({len(decoded)} bytes)")
        except Exception as e:
            # Not valid base64, continue
            logger.debug(f"Base64 decode failed: {e}")

    # 4. Otherwise, treat as plain text content
    logger.info(f"Detected as plain text content ({len(source)} chars)")
    return source.encode("utf-8"), "plain_text"


def read_document_as_markdown_impl(input_data: ReadDocumentAsMarkdownInput, config: MCPConfig) -> list[Any]:
    """Implement read_document_as_markdown tool with simplified API.

    This implementation uses automatic source detection and AST-based processing
    to extract images as FastMCP Image objects, allowing vLLMs to "see" the
    images alongside markdown text.

    Parameters
    ----------
    input_data : ReadDocumentAsMarkdownInput
        Tool input parameters
    config : MCPConfig
        Server configuration (for allowlists, attachment mode, etc.)

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
    # Auto-detect source type and prepare source
    source, detection_type = _detect_source_type(input_data.source, config)

    # Prepare conversion options
    kwargs: dict[str, Any] = {}

    # Add PDF-specific options if needed
    if input_data.pdf_pages:
        # Validate page specification format before passing to converter
        # (Full validation with page count happens in converter)
        page_spec = input_data.pdf_pages.strip()
        if not re.match(r"^[\d\s,\-]+$", page_spec):
            raise ValueError(
                f"Invalid page range format: '{input_data.pdf_pages}'. "
                "Expected format like '1-3,5,10-' with only digits, commas, and hyphens."
            )
        kwargs["pages"] = page_spec

    # Set attachment mode from server config (convert include_images bool to attachment_mode)
    # include_images=True -> base64 (include images for vLLM)
    # include_images=False -> alt_text (no images, just alt text)
    kwargs["attachment_mode"] = "base64" if config.include_images else "alt_text"

    # Validate format_hint if provided (defense in depth against invalid format strings)
    # Even though FastMCP validates the Literal type, we add runtime validation to ensure
    # the value is actually valid before passing to to_ast
    if input_data.format_hint is not None:
        valid_formats = get_args(SourceFormat)
        if input_data.format_hint not in valid_formats:
            raise ValueError(
                f"Invalid format_hint: '{input_data.format_hint}'. " f"Must be one of: {', '.join(valid_formats)}"
            )

    # Perform conversion using AST approach
    try:
        # Convert to AST first (allows us to extract images and sections)
        # format_hint has been validated above, safe to cast to DocumentFormat
        doc = to_ast(source, source_format=cast(DocumentFormat, input_data.format_hint or "auto"), **kwargs)

        # Validate return type
        if not isinstance(doc, Document):
            raise TypeError(f"Expected Document from to_ast, got {type(doc)}")

        # Extract section if requested
        if input_data.section:
            logger.info(f"Extracting section: {input_data.section}")
            doc = extract_sections(doc, input_data.section, case_sensitive=False, combine=False)
            if not isinstance(doc, Document):
                raise TypeError(f"Expected Document from extract_sections, got {type(doc)}")

        # Extract images if include_images is enabled (base64 mode for vLLM visibility)
        images: list[Any] = []
        if config.include_images:
            images = _extract_images_from_ast(doc)
            if images:
                logger.info(f"Extracted {len(images)} images for vLLM")

        # Convert AST to markdown (server-level flavor from config)
        markdown = from_ast(doc, target_format="markdown", flavor=config.flavor)

        # Validate return type
        if not isinstance(markdown, str):
            raise TypeError(f"Expected str from from_ast, got {type(markdown)}")

        logger.info(f"Conversion successful ({len(markdown)} characters)")

        # Return list with markdown + images (FastMCP handles content blocks)
        return [markdown] + images

    except All2MdError as e:
        logger.error(f"Conversion failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during conversion: {e}")
        raise All2MdError(f"Conversion failed: {e}") from e


def save_document_from_markdown_impl(
    input_data: SaveDocumentFromMarkdownInput, config: MCPConfig
) -> SaveDocumentFromMarkdownOutput:
    """Implement save_document_from_markdown tool with simplified API.

    This tool always writes to disk (no content return). The filename
    parameter is required and must pass write allowlist validation.

    Parameters
    ----------
    input_data : SaveDocumentFromMarkdownInput
        Tool input parameters
    config : MCPConfig
        Server configuration (for allowlists, etc.)

    Returns
    -------
    SaveDocumentFromMarkdownOutput
        Result with output path and warnings

    Raises
    ------
    MCPSecurityError
        If security validation fails
    All2MdError
        If rendering fails

    Notes
    -----
    This function uses secure file opening with TOCTOU protection to prevent
    symlink attacks. The file is opened immediately after validation using
    OS-level flags (O_NOFOLLOW) to ensure the validated path is actually
    being written to, not a symlink that was swapped in between validation
    and write operations.

    """
    warnings: list[str] = []

    # Validate write access for output file
    validated_output = validate_write_path(input_data.filename, config.write_allowlist)
    output_path = str(validated_output)
    logger.info(f"Writing output to: {validated_output}")

    # Perform rendering (always write to disk)
    # Use secure file handle to prevent TOCTOU attacks
    try:
        # Open file securely with TOCTOU protection (immediately after validation)
        # This prevents symlink attacks where file is replaced between validation and write
        with secure_open_for_write(validated_output) as output_file:
            # Cast format (TargetFormat is a subset of DocumentFormat)
            # Use server-level flavor from config
            # Pass file handle instead of path to ensure we write to the validated location
            from_markdown(
                input_data.source,
                target_format=cast(DocumentFormat, input_data.format),
                output=output_file,
                flavor=config.flavor,
            )

        logger.info(f"Rendering successful, written to {output_path}")
        return SaveDocumentFromMarkdownOutput(output_path=output_path, warnings=warnings)

    except All2MdError as e:
        logger.error(f"Rendering failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during rendering: {e}")
        raise All2MdError(f"Rendering failed: {e}") from e
