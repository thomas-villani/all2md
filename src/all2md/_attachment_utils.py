"""Unified attachment handling utilities for all2md conversion modules.

This module provides common functions for handling attachments (images and files)
across all conversion modules in the all2md library. It implements the unified
AttachmentMode system with consistent behavior across different converters.

The attachment handling modes are:
- "skip": Remove attachments completely
- "alt_text": Use alt-text for images, filename for files
- "download": Save to folder and reference with markdown links
- "base64": Embed as base64 data URIs (images only)

Functions
---------
- process_attachment: Main function for processing attachments based on mode
- extract_pptx_image_data: Extract image data from PowerPoint shapes
- extract_docx_image_data: Extract image data from Word document relationships
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the "Software"), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import base64
import os
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from .constants import AttachmentMode


def process_attachment(
    attachment_data: bytes | None,
    attachment_name: str,
    alt_text: str = "",
    attachment_mode: AttachmentMode = "alt_text",
    attachment_output_dir: str | None = None,
    attachment_base_url: str | None = None,
    is_image: bool = True,
) -> str:
    """Process an attachment according to the specified mode.

    Parameters
    ----------
    attachment_data : bytes | None
        Raw attachment data, or None if not available
    attachment_name : str
        Name/filename of the attachment
    alt_text : str, default ""
        Alt text for images or description for files
    attachment_mode : AttachmentMode, default "alt_text"
        How to handle the attachment
    attachment_output_dir : str | None, default None
        Directory to save attachments in download mode
    attachment_base_url : str | None, default None
        Base URL for resolving relative URLs
    is_image : bool, default True
        Whether this is an image attachment

    Returns
    -------
    str
        Markdown representation of the attachment
    """
    if attachment_mode == "skip":
        return ""

    if attachment_mode == "alt_text":
        if is_image:
            return f"![{alt_text or attachment_name}]"
        else:
            return f"[{attachment_name}]"

    if attachment_mode == "base64" and is_image and attachment_data:
        # Determine MIME type from file extension
        ext = Path(attachment_name).suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
        }
        mime_type = mime_types.get(ext, "image/png")

        b64_data = base64.b64encode(attachment_data).decode("utf-8")
        data_uri = f"data:{mime_type};base64,{b64_data}"
        return f"![{alt_text or attachment_name}]({data_uri})"

    if attachment_mode == "download":
        if not attachment_output_dir:
            attachment_output_dir = "attachments"

        # Create output directory if it doesn't exist
        os.makedirs(attachment_output_dir, exist_ok=True)

        # Generate safe filename
        safe_name = "".join(c for c in attachment_name if c.isalnum() or c in "._-")
        if not safe_name:
            safe_name = "attachment"

        attachment_path = Path(attachment_output_dir) / safe_name

        # Write attachment data if available
        if attachment_data:
            with open(attachment_path, "wb") as f:
                f.write(attachment_data)

        # Build URL
        if attachment_base_url:
            url = urljoin(attachment_base_url.rstrip("/") + "/", safe_name)
        else:
            url = str(attachment_path)

        if is_image:
            return f"![{alt_text or attachment_name}]({url})"
        else:
            return f"[{attachment_name}]({url})"

    # Fallback to alt_text mode
    if is_image:
        return f"![{alt_text or attachment_name}]"
    else:
        return f"[{attachment_name}]"


def extract_pptx_image_data(shape: Any) -> bytes | None:
    """Extract raw image data from a PowerPoint shape.

    Parameters
    ----------
    shape : Any
        PowerPoint shape object with image property

    Returns
    -------
    bytes | None
        Raw image bytes, or None if extraction fails
    """
    try:
        image = shape.image
        image_bytes = image.blob
        return image_bytes
    except Exception:
        return None


def extract_docx_image_data(parent: Any, blip_rId: str) -> bytes | None:
    """Extract image data from Word document relationships.

    Parameters
    ----------
    parent : Any
        Word document parent element
    blip_rId : str
        Relationship ID for the image

    Returns
    -------
    bytes | None
        Raw image bytes, or None if extraction fails
    """
    try:
        # Get the relationship target
        image_part = parent.part.related_parts[blip_rId]

        # Get image bytes
        image_bytes = image_part.blob

        # Return raw image bytes - let attachment processing handle the format
        return image_bytes
    except Exception:
        return None
