#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/images.py
"""Image handling utilities for renderers.

This module provides utilities for working with images in various formats,
including base64-encoded data URIs and temporary file management.

"""

from __future__ import annotations

import atexit
import base64
import binascii
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def decode_base64_image(data_uri: str) -> tuple[bytes | None, str | None]:
    """Decode a base64-encoded data URI to image bytes.

    Extracts and decodes base64 image data from a data URI.
    Supports common image formats (png, jpeg, jpg, gif, webp, svg).

    Parameters
    ----------
    data_uri : str
        Data URI string in format: data:image/{format};base64,{data}

    Returns
    -------
    tuple[bytes or None, str or None]
        Tuple of (image_data, image_format) or (None, None) if decoding fails.
        image_format is the file extension without dot (e.g., "png", "jpeg")

    Examples
    --------
        >>> data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA..."
        >>> image_bytes, fmt = decode_base64_image(data)
        >>> print(fmt)
        png
        >>> print(len(image_bytes))
        85

    Notes
    -----
    This function validates the data URI format and safely handles
    malformed or invalid base64 data.

    """
    if not data_uri or not isinstance(data_uri, str):
        logger.debug("Invalid input to decode_base64_image: not a string or empty")
        return None, None

    # Match data URI pattern: data:{mime};base64,{data}
    # Use a more robust regex that captures the full MIME type (e.g., image/svg+xml)
    match = re.match(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)", data_uri)
    if not match:
        logger.debug(f"Invalid data URI format: regex match failed for URI starting with '{data_uri[:50]}...'")
        return None, None

    mime_type = match.group("mime").lower()
    base64_data = match.group("data")

    # Map MIME types to file extensions
    mime_to_ext = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/gif": "gif",
        "image/webp": "webp",
        "image/svg+xml": "svg",
        "image/bmp": "bmp",
        "image/tiff": "tiff",
        "image/tif": "tif",
        "image/x-icon": "ico",
        "image/vnd.microsoft.icon": "ico",
    }

    # Get extension from MIME type, or try to extract from simple MIME types
    image_format = mime_to_ext.get(mime_type)
    if not image_format:
        # Try to extract format from MIME type if it's simple (e.g., "image/png" -> "png")
        if mime_type.startswith("image/"):
            potential_format = mime_type.split("/")[-1].lower()
            # Only accept if it's alphanumeric (no special chars except hyphen)
            if re.match(r"^[a-z0-9\-]+$", potential_format):
                # Remove common MIME type prefixes
                potential_format = potential_format.replace("x-", "")
                image_format = potential_format

        if not image_format:
            # Unknown or invalid MIME type
            logger.debug(f"Unknown or unsupported MIME type: {mime_type}")
            return None, None

    # Validate format is a known image type
    valid_formats = {"png", "jpeg", "jpg", "gif", "webp", "svg", "bmp", "tiff", "tif", "ico"}
    if image_format not in valid_formats:
        logger.debug(f"Invalid image format: {image_format} (not in valid formats list)")
        return None, None

    try:
        # Decode base64 data with validation
        image_data = base64.b64decode(base64_data, validate=True)
        return image_data, image_format
    except (ValueError, binascii.Error) as e:
        # Invalid base64 data
        logger.debug(f"Invalid base64 encoding: failed to decode ({type(e).__name__}: {e})")
        return None, None


def decode_base64_image_to_file(
    data_uri: str, output_dir: str | Path | None = None, delete_on_exit: bool = True
) -> str | None:
    """Decode a base64 data URI and write to a temporary file.

    Convenience function that decodes base64 image data and writes it
    to a temporary file. Useful for renderers that require file paths
    rather than in-memory bytes.

    Parameters
    ----------
    data_uri : str
        Data URI string in format: data:image/{format};base64,{data}
    output_dir : str, Path, or None, default = None
        Directory for temporary file. If None, uses system temp directory.
    delete_on_exit : bool, default = True
        If True, file will be automatically deleted when Python exits.
        If False, caller is responsible for cleanup.

    Returns
    -------
    str or None
        Path to temporary file, or None if decoding failed

    Examples
    --------
        >>> data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA..."
        >>> temp_path = decode_base64_image_to_file(data)
        >>> print(temp_path)
        /tmp/tmpxyz123.png

    Notes
    -----
    If delete_on_exit is False, the caller MUST manually delete the
    temporary file to avoid disk space issues. Track the file path
    and use Path(temp_path).unlink() when done.

    """
    # Decode image data
    image_data, image_format = decode_base64_image(data_uri)
    if image_data is None or image_format is None:
        return None

    try:
        # Create temporary file
        suffix = f".{image_format}"
        dir_path = str(output_dir) if output_dir else None

        # Use mkstemp to create temp file that persists after creation
        fd, temp_path = tempfile.mkstemp(suffix=suffix, dir=dir_path)

        # Write the image data
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(image_data)
        except Exception:
            # If writing fails, clean up the file
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            raise

        # Register cleanup handler if delete_on_exit is True
        if delete_on_exit:

            def cleanup_temp_file(path: str = temp_path) -> None:
                Path(path).unlink(missing_ok=True)

            atexit.register(cleanup_temp_file)

        return temp_path

    except (OSError, IOError):
        return None


def parse_image_data_uri(data_uri: str) -> dict[str, Any] | None:
    """Parse a data URI and extract metadata.

    Extracts format, encoding, and data from a data URI without decoding.
    Supports data URIs with parameters like charset, base64 encoding marker, etc.

    Parameters
    ----------
    data_uri : str
        Data URI string (any format, not just base64)

    Returns
    -------
    dict or None
        Dictionary with keys: 'mime_type', 'format', 'encoding', 'data', 'params', 'charset'
        Returns None if URI is malformed

    Examples
    --------
        >>> uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA..."
        >>> info = parse_image_data_uri(uri)
        >>> print(info['format'])
        png
        >>> print(info['encoding'])
        base64

        >>> uri = "data:text/plain;charset=utf-8;base64,SGVsbG8="
        >>> info = parse_image_data_uri(uri)
        >>> print(info['charset'])
        utf-8

    """
    if not data_uri or not isinstance(data_uri, str):
        return None

    # Parse data URI without backtracking-prone regex
    # Format: data:{mime}[;param1][;param2]...,{data}
    if not data_uri.startswith("data:"):
        return None

    # Find the comma separating metadata from data (split only on first comma)
    comma_idx = data_uri.find(",", 5)  # Start after "data:"
    if comma_idx == -1:
        return None

    metadata = data_uri[5:comma_idx]  # Everything between "data:" and first comma
    data = data_uri[comma_idx + 1 :]  # Everything after the comma

    # Split metadata by semicolon to get mime type and params
    parts = metadata.split(";")
    if not parts:
        return None

    mime_type = parts[0]
    params_str = ";".join(parts[1:]) if len(parts) > 1 else ""

    # Parse parameters
    params = []
    charset = None
    encoding = None

    if params_str:
        # Split by semicolon and strip whitespace
        params = [p.strip() for p in params_str.split(";") if p.strip()]

        # Check for base64 encoding
        if "base64" in params:
            encoding = "base64"

        # Extract charset if present
        for param in params:
            if param.startswith("charset="):
                charset = param.split("=", 1)[1]
                break

    # If no encoding specified, assume URL-encoded (standard for data URIs without base64)
    if not encoding:
        encoding = "url"

    # Extract format from MIME type (e.g., "image/png" -> "png", "image/svg+xml" -> "svg")
    image_format = None
    if mime_type.startswith("image/"):
        # Handle complex MIME types like image/svg+xml
        format_part = mime_type.split("/")[-1].lower()
        # Map known formats
        format_map = {
            "svg+xml": "svg",
            "jpeg": "jpg",
        }
        image_format = format_map.get(format_part, format_part)

    return {
        "mime_type": mime_type,
        "format": image_format or "",
        "encoding": encoding,
        "data": data,
        "params": params,
        "charset": charset or "",
    }


def is_data_uri(uri: str) -> bool:
    """Check if a string is a data URI.

    Parameters
    ----------
    uri : str
        String to check

    Returns
    -------
    bool
        True if string is a data URI

    Examples
    --------
        >>> is_data_uri("data:image/png;base64,...")
        True
        >>> is_data_uri("https://example.com/image.png")
        False

    """
    if not uri or not isinstance(uri, str):
        return False

    return uri.startswith("data:")


def detect_image_format_from_bytes(data: bytes, max_bytes: int = 32) -> str | None:
    r"""Detect image format from file content using magic bytes.

    This function examines the first few bytes of image data to determine
    the format, providing more reliable detection than file extensions.

    Parameters
    ----------
    data : bytes
        Image file content (at least first 32 bytes for reliable detection)
    max_bytes : int, default 32
        Number of bytes to examine (default is sufficient for all formats)

    Returns
    -------
    str or None
        Image format (lowercase extension without dot) or None if unrecognized

    Examples
    --------
        >>> with open("photo.jpg", "rb") as f:
        ...     data = f.read(32)
        ...     fmt = detect_image_format_from_bytes(data)
        >>> print(fmt)
        jpg

    Notes
    -----
    Supported formats and their magic byte signatures:

    - **PNG**: Starts with `\x89PNG\r\n\x1a\n`
    - **JPEG**: Starts with `\xff\xd8\xff`
    - **GIF**: Starts with `GIF87a` or `GIF89a`
    - **WebP**: Contains `WEBP` at offset 8
    - **BMP**: Starts with `BM`
    - **TIFF**: Starts with `II*\x00` (little-endian) or `MM\x00*` (big-endian)
    - **ICO**: Starts with `\x00\x00\x01\x00`
    - **SVG**: Starts with `<svg` or `<?xml` (after whitespace)

    """
    if not data or len(data) < 4:
        return None

    # Check magic bytes for each format
    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"

    # JPEG: FF D8 FF
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"

    # GIF: "GIF87a" or "GIF89a"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "gif"

    # WebP: "RIFF" followed by file size, then "WEBP"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"

    # BMP: "BM"
    if data.startswith(b"BM"):
        return "bmp"

    # TIFF: Little-endian (II*\x00) or Big-endian (MM\x00*)
    if data.startswith(b"II*\x00") or data.startswith(b"MM\x00*"):
        return "tiff"

    # ICO: 00 00 01 00
    if data.startswith(b"\x00\x00\x01\x00"):
        return "ico"

    # SVG: XML-based, starts with "<svg" or "<?xml"
    # Strip leading whitespace and check
    stripped = data.lstrip()
    if stripped.startswith(b"<svg") or stripped.startswith(b"<?xml"):
        # For <?xml, we should check further for <svg but that's likely beyond first bytes
        return "svg"

    return None


def get_image_format_from_path(path: str | Path) -> str | None:
    """Extract image format from file path.

    Parameters
    ----------
    path : str or Path
        File path

    Returns
    -------
    str or None
        Image format (lowercase extension without dot) or None if not an image

    Examples
    --------
        >>> get_image_format_from_path("photo.jpg")
        'jpg'
        >>> get_image_format_from_path("document.pdf")
        None

    """
    if not path:
        return None

    path_obj = Path(path)
    suffix = path_obj.suffix.lower().lstrip(".")

    # List of common image formats
    image_formats = {"png", "jpeg", "jpg", "gif", "webp", "svg", "bmp", "tiff", "tif", "ico"}

    return suffix if suffix in image_formats else None
