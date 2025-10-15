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
import os
import re
import tempfile
from pathlib import Path


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
        return None, None

    # Match data URI pattern: data:image/{format};base64,{data}
    match = re.match(r'data:image/(\w+);base64,(.+)', data_uri)
    if not match:
        return None, None

    image_format = match.group(1).lower()
    base64_data = match.group(2)

    # Validate format is a known image type
    valid_formats = {'png', 'jpeg', 'jpg', 'gif', 'webp', 'svg', 'bmp', 'tiff', 'tif', 'ico'}
    if image_format not in valid_formats:
        return None, None

    try:
        # Decode base64 data
        image_data = base64.b64decode(base64_data)
        return image_data, image_format
    except (ValueError, binascii.Error):
        # Invalid base64 data
        return None, None


def decode_base64_image_to_file(
        data_uri: str,
        output_dir: str | Path | None = None,
        delete_on_exit: bool = True
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
        suffix = f'.{image_format}'
        dir_path = str(output_dir) if output_dir else None

        # Use mkstemp to create temp file that persists after creation
        fd, temp_path = tempfile.mkstemp(suffix=suffix, dir=dir_path)

        # Write the image data
        try:
            with os.fdopen(fd, 'wb') as f:
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
            atexit.register(lambda path=temp_path: Path(path).unlink(missing_ok=True))

        return temp_path

    except (OSError, IOError):
        return None


def parse_image_data_uri(data_uri: str) -> dict[str, str] | None:
    """Parse a data URI and extract metadata.

    Extracts format, encoding, and data from a data URI without decoding.

    Parameters
    ----------
    data_uri : str
        Data URI string (any format, not just base64)

    Returns
    -------
    dict or None
        Dictionary with keys: 'mime_type', 'format', 'encoding', 'data'
        Returns None if URI is malformed

    Examples
    --------
        >>> uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA..."
        >>> info = parse_image_data_uri(uri)
        >>> print(info['format'])
        png
        >>> print(info['encoding'])
        base64

    """
    if not data_uri or not isinstance(data_uri, str):
        return None

    # Match pattern: data:{mime};{encoding},{data}
    match = re.match(r'data:([^;]+);([^,]+),(.+)', data_uri)
    if not match:
        return None

    mime_type = match.group(1)
    encoding = match.group(2)
    data = match.group(3)

    # Extract format from MIME type (e.g., "image/png" -> "png")
    format_match = re.match(r'image/(\w+)', mime_type)
    image_format = format_match.group(1) if format_match else None

    return {
        'mime_type': mime_type,
        'format': image_format or '',
        'encoding': encoding,
        'data': data
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

    return uri.startswith('data:')


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
    suffix = path_obj.suffix.lower().lstrip('.')

    # List of common image formats
    image_formats = {'png', 'jpeg', 'jpg', 'gif', 'webp', 'svg', 'bmp', 'tiff', 'tif', 'ico'}

    return suffix if suffix in image_formats else None
