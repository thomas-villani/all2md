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
#  documentation files (the “Software”), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the "Software"), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#
import base64
import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from all2md.constants import AttachmentMode

logger = logging.getLogger(__name__)


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
        logger.debug(f"Skipping attachment: {attachment_name}")
        return ""

    if attachment_mode == "alt_text":
        if is_image:
            return f"![{alt_text or attachment_name}]"
        else:
            return f"[{attachment_name}]"

    if attachment_mode == "base64" and is_image:
        if not attachment_data:
            logger.info(f"No attachment data available for base64 mode: {attachment_name}")
        else:
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

    # Fallback to alt_text mode if attachment data is missing or mode is unsupported
    logger.info(f"Falling back to alt_text mode for attachment: {attachment_name} "
                f"(mode: {attachment_mode}, has_data: {attachment_data is not None})")
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


def extract_docx_image_data(parent: Any, blip_rId: str) -> tuple[bytes | None, str | None]:
    """Extract image data and format information from Word document relationships.

    Parameters
    ----------
    parent : Any
        Word document parent element
    blip_rId : str
        Relationship ID for the image

    Returns
    -------
    tuple[bytes | None, str | None]
        Tuple of (raw image bytes, file extension), or (None, None) if extraction fails
    """
    try:
        # Get the relationship target
        image_part = parent.part.related_parts[blip_rId]

        # Get image bytes
        image_bytes = image_part.blob

        # Detect format from content type or part name
        extension = "png"  # default fallback

        # Try to get extension from content type
        if hasattr(image_part, 'content_type') and image_part.content_type:
            content_type = image_part.content_type.lower()
            if 'jpeg' in content_type or 'jpg' in content_type:
                extension = "jpg"
            elif 'gif' in content_type:
                extension = "gif"
            elif 'png' in content_type:
                extension = "png"
            elif 'bmp' in content_type:
                extension = "bmp"
            elif 'tiff' in content_type:
                extension = "tiff"

        # Try to get extension from part name if content type didn't work
        elif hasattr(image_part, 'partname') and image_part.partname:
            part_name = str(image_part.partname).lower()
            if '.jpg' in part_name or '.jpeg' in part_name:
                extension = "jpg"
            elif '.gif' in part_name:
                extension = "gif"
            elif '.png' in part_name:
                extension = "png"
            elif '.bmp' in part_name:
                extension = "bmp"
            elif '.tiff' in part_name or '.tif' in part_name:
                extension = "tiff"

        return image_bytes, extension
    except Exception:
        return None, None


def generate_attachment_filename(
        base_stem: str,
        attachment_type: str = "img",
        format_type: str = "general",
        page_num: int | None = None,
        slide_num: int | None = None,
        sequence_num: int = 1,
        extension: str = "png"
) -> str:
    """Generate standardized attachment filenames across all converters.

    Parameters
    ----------
    base_stem : str
        Base filename stem (without extension) from the source document
    attachment_type : str, default "img"
        Type of attachment (e.g., "img", "file")
    format_type : str, default "general"
        Format context - one of:
        - "pdf": For PDF pages - generates {stem}_p{page}_img{n}.{ext}
        - "pptx": For PowerPoint slides - generates {stem}_slide{n}_img{m}.{ext}
        - "general": For other formats - generates {stem}_img{n}.{ext}
    page_num : int | None, default None
        Page number (1-based) for PDF format
    slide_num : int | None, default None
        Slide number (1-based) for PPTX format
    sequence_num : int, default 1
        Sequence number for multiple attachments
    extension : str, default "png"
        File extension without dot

    Returns
    -------
    str
        Standardized filename

    Examples
    --------
    >>> generate_attachment_filename("document", format_type="pdf", page_num=1, sequence_num=2)
    'document_p1_img2.png'
    >>> generate_attachment_filename("presentation", format_type="pptx", slide_num=3, sequence_num=1)
    'presentation_slide3_img1.png'
    >>> generate_attachment_filename("article", format_type="general", sequence_num=5)
    'article_img5.png'
    """
    if format_type == "pdf":
        if page_num is None:
            raise ValueError("page_num is required for PDF format")
        return f"{base_stem}_p{page_num}_{attachment_type}{sequence_num}.{extension}"
    elif format_type == "pptx":
        if slide_num is None:
            raise ValueError("slide_num is required for PPTX format")
        return f"{base_stem}_slide{slide_num}_{attachment_type}{sequence_num}.{extension}"
    else:  # general format for DOCX, HTML, RTF, IPYNB, EML
        return f"{base_stem}_{attachment_type}{sequence_num}.{extension}"


def create_attachment_sequencer():
    """Create a closure that tracks attachment sequence numbers to prevent duplicates.

    Returns
    -------
    callable
        Function that generates sequential attachment filenames and tracks usage

    Examples
    --------
    >>> sequencer = create_attachment_sequencer()
    >>> sequencer("doc", "pdf", page_num=1)  # Returns: ('doc_p1_img1.png', 1)
    >>> sequencer("doc", "pdf", page_num=1)  # Returns: ('doc_p1_img2.png', 2)
    >>> sequencer("doc", "pdf", page_num=2)  # Returns: ('doc_p2_img1.png', 1)
    """
    used_filenames = set()
    sequence_counters = {}

    def get_next_filename(base_stem: str, format_type: str = "general", **kwargs) -> tuple[str, int]:
        """Generate next available filename with sequence number.

        Returns
        -------
        tuple[str, int]
            Tuple of (filename, sequence_number)
        """
        # Create a key for this specific context
        if format_type == "pdf":
            key = f"{base_stem}_p{kwargs.get('page_num', 1)}"
        elif format_type == "pptx":
            key = f"{base_stem}_slide{kwargs.get('slide_num', 1)}"
        else:
            key = base_stem

        # Get next sequence number for this key
        sequence_num = sequence_counters.get(key, 0) + 1
        sequence_counters[key] = sequence_num

        # Generate filename
        filename = generate_attachment_filename(
            base_stem=base_stem,
            format_type=format_type,
            sequence_num=sequence_num,
            **kwargs
        )

        # Ensure uniqueness (failsafe)
        while filename in used_filenames:
            sequence_num += 1
            sequence_counters[key] = sequence_num
            filename = generate_attachment_filename(
                base_stem=base_stem,
                format_type=format_type,
                sequence_num=sequence_num,
                **kwargs
            )

        used_filenames.add(filename)
        return filename, sequence_num

    return get_next_filename
