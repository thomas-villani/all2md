"""Unified attachment handling utilities for all2md conversion modules.

This module provides common functions for handling attachments (images and files)
across all conversion modules in the all2md library. It implements the unified
AttachmentMode system with consistent behavior across different parsers.

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
# src/all2md/utils/attachments.py

import base64
import logging
import os
import re
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote as url_quote, urljoin

import unicodedata

from all2md.constants import DEFAULT_ALT_TEXT_MODE, AltTextMode, AttachmentMode
from all2md.utils.escape import escape_markdown_context_aware

logger = logging.getLogger(__name__)


def sanitize_footnote_label(attachment_name: str) -> str:
    """Sanitize attachment name for use as a Markdown footnote label.

    Footnote labels in Markdown cannot contain spaces or many special
    characters without breaking rendering. This function creates a safe
    label by normalizing the attachment name.

    Parameters
    ----------
    attachment_name : str
        Original attachment filename

    Returns
    -------
    str
        Sanitized footnote label safe for Markdown

    Examples
    --------
    >>> sanitize_footnote_label("my image.png")
    'my_image'
    >>> sanitize_footnote_label("file (1).jpg")
    'file_1'
    >>> sanitize_footnote_label("document%20name.pdf")
    'document_20name'

    """
    if not attachment_name:
        return "attachment"

    # Use existing sanitization logic to normalize the filename
    safe_name = sanitize_attachment_filename(attachment_name)

    # Remove file extension to create a cleaner label
    label = Path(safe_name).stem

    # Ensure we have something meaningful
    if not label or label == ".":
        label = "attachment"

    return label


def sanitize_attachment_filename(
        filename: str, max_length: int = 255, preserve_case: bool = False, allow_unicode: bool = False
) -> str:
    """Sanitize an attachment filename for secure file system storage.

    This function normalizes Unicode characters, removes dangerous patterns,
    and ensures cross-platform compatibility while preventing security issues.

    By default, this function is conservative and may be lossy:
    - Converts to lowercase (unless preserve_case=True)
    - Removes non-ASCII characters (unless allow_unicode=True)
    - Removes special characters except [a-zA-Z0-9_.-]

    Parameters
    ----------
    filename : str
        Original filename to sanitize
    max_length : int, default 255
        Maximum length for the sanitized filename
    preserve_case : bool, default False
        If True, preserve original case. If False, convert to lowercase for
        cross-platform compatibility (case-insensitive filesystems).
    allow_unicode : bool, default False
        If True, allow Unicode letters and numbers (e.g., Chinese, Arabic).
        If False, only allow ASCII alphanumeric characters.
        Note: Unicode filenames may cause issues on some systems.

    Returns
    -------
    str
        Sanitized filename safe for file system use

    Raises
    ------
    ValueError
        If the filename contains potentially malicious patterns that cannot be sanitized

    Examples
    --------
    >>> sanitize_attachment_filename("test\u0301.png")  # test with combining accent
    'test.png'
    >>> sanitize_attachment_filename("../../../etc/passwd")
    'passwd'
    >>> sanitize_attachment_filename("file<>|name?.txt")
    'filename.txt'
    >>> sanitize_attachment_filename("Test.PNG", preserve_case=True)
    'Test.PNG'
    >>> sanitize_attachment_filename("文件.txt", allow_unicode=True)
    '文件.txt'

    """
    if not filename or not filename.strip():
        return "attachment"

    original_filename = filename

    # Security check: detect potentially malicious patterns
    malicious_patterns = [
        r"\.\.[\\/]",  # Directory traversal
        r"^[\\/]",  # Absolute paths
        r"[\x00-\x1f\x7f]",  # Control characters
        r"^\s*$",  # Only whitespace
    ]

    for pattern in malicious_patterns:
        if re.search(pattern, filename):
            logger.warning(f"Potentially malicious filename pattern detected: {filename}")
            # Continue with sanitization rather than rejecting

    # Check for excessive length before processing
    if len(filename) > max_length * 2:  # Arbitrary threshold
        logger.warning(f"Filename extremely long ({len(filename)} chars), truncating: {filename[:50]}...")

    # Normalize Unicode to prevent visually confusable names
    # NFKC removes compatibility characters and combines decomposed characters
    normalized = unicodedata.normalize("NFKC", filename)

    # Convert to lowercase for case normalization (unless preserve_case is True)
    if not preserve_case:
        normalized = normalized.lower()

    # Handle directory traversal attempts and path separators FIRST
    # Split by path separators and take only the last part (filename)
    path_parts = re.split(r"[/\\]", normalized)
    safe_chars = path_parts[-1] if path_parts else "attachment"

    # Remove or replace dangerous characters
    # Keep only alphanumeric, dots, hyphens, underscores, and spaces
    if allow_unicode:
        # \w includes Unicode word characters (letters, digits, underscore)
        # This allows Chinese, Arabic, Cyrillic, etc.
        safe_chars = re.sub(r"[^\w.\-\s]", "", safe_chars, flags=re.UNICODE)
    else:
        # Only allow ASCII alphanumeric characters for maximum compatibility
        safe_chars = re.sub(r"[^a-zA-Z0-9_.\-\s]", "", safe_chars)

    # Replace multiple spaces/dots with single versions
    safe_chars = re.sub(r"\s+", "_", safe_chars)
    safe_chars = re.sub(r"\.+", ".", safe_chars)

    # Before stripping, detect if we only have a leading dot followed by alphanumeric
    # This helps detect cases like "文件.txt" -> ".txt" -> "txt" (just extension)
    # Pattern: starts with dot, followed by 2-5 alphanumeric chars (typical extension)
    is_likely_extension_only = bool(re.match(r"^\.[a-zA-Z0-9]{2,5}$", safe_chars))

    # Remove leading/trailing dots and spaces (Windows restrictions)
    safe_chars = safe_chars.strip(". ")

    # Check if we're left with only an extension (no base name)
    # This can happen when Unicode-only filenames have their Unicode chars removed
    if is_likely_extension_only:
        # We had only ".ext" pattern before stripping
        # safe_chars is now the extension without the dot (e.g., "txt")
        # Preserve the extension by using "attachment" as the base
        safe_chars = f"attachment.{safe_chars}"

    # Additional security: remove any remaining path-like constructs
    safe_chars = re.sub(r"\.\.+", ".", safe_chars)

    # Remove Windows reserved names (case-insensitive check)
    windows_reserved = {
        "con",
        "prn",
        "aux",
        "nul",
        "com1",
        "com2",
        "com3",
        "com4",
        "com5",
        "com6",
        "com7",
        "com8",
        "com9",
        "lpt1",
        "lpt2",
        "lpt3",
        "lpt4",
        "lpt5",
        "lpt6",
        "lpt7",
        "lpt8",
        "lpt9",
    }

    name_parts = safe_chars.split(".")
    base_name_lower = name_parts[0].lower()
    if base_name_lower in windows_reserved:
        # Preserve case of the original if preserve_case=True
        name_parts[0] = f"file_{name_parts[0]}"
        safe_chars = ".".join(name_parts)

    # Security check: ensure the filename isn't just dots
    if re.match(r"^\.*$", safe_chars):
        safe_chars = "attachment"

    # Ensure we have something meaningful
    if not safe_chars or safe_chars == ".":
        safe_chars = "attachment"

    # Security: prevent filenames that are all underscores (edge case)
    if re.match(r"^_+$", safe_chars):
        safe_chars = "attachment"

    # Truncate if too long, preserving extension
    if len(safe_chars) > max_length:
        if "." in safe_chars:
            name, ext = safe_chars.rsplit(".", 1)
            max_name_length = max_length - len(ext) - 1  # -1 for the dot
            if max_name_length > 0:
                safe_chars = f"{name[:max_name_length]}.{ext}"
            else:
                safe_chars = f"file.{ext}"
        else:
            safe_chars = safe_chars[:max_length]

    # Final security check: ensure we still have a valid filename
    if not safe_chars or len(safe_chars.strip()) == 0:
        safe_chars = "attachment"

    # Log the transformation if it was significant
    if safe_chars != original_filename:
        logger.debug(f"Sanitized filename: '{original_filename}' -> '{safe_chars}'")

    return safe_chars


def ensure_unique_attachment_path(base_path: Path, max_attempts: int = 1000) -> Path:
    """Ensure a unique file path by adding numeric suffixes for collisions.

    Thread Safety and Race Conditions
    ----------------------------------
    WARNING: This function is susceptible to TOCTOU (Time-of-Check to Time-of-Use)
    race conditions. Between checking if a path exists and when the caller actually
    creates the file, another process or thread could create a file at that path,
    leading to potential file overwrites.

    This implementation is safe for:
    - Single-process, single-threaded usage (typical use case)
    - Scenarios where file collisions are acceptable

    This implementation is NOT safe for:
    - Concurrent file creation from multiple processes
    - Concurrent file creation from multiple threads
    - Security-critical applications requiring guaranteed uniqueness

    For production concurrent use, callers should implement atomic file operations:
    - Use os.open() with O_CREAT | O_EXCL flags (POSIX)
    - Retry on FileExistsError when opening the file
    - Use NamedTemporaryFile with delete=False for temporary files

    Parameters
    ----------
    base_path : Path
        The desired base path for the attachment
    max_attempts : int, default 1000
        Maximum number of collision resolution attempts

    Returns
    -------
    Path
        A unique file path that doesn't exist on the filesystem at check time

    Raises
    ------
    RuntimeError
        If unable to find a unique path after max_attempts

    Examples
    --------
    >>> # If image.png exists, returns image-1.png
    >>> ensure_unique_attachment_path(Path("./attachments/image.png"))
    Path('./attachments/image-1.png')

    Notes
    -----
    For typical single-process document conversion, this function is adequate.
    The race window is small and the consequences of collision are minimal
    (one attachment overwrites another in the same conversion run).

    """
    if not base_path.exists():
        return base_path

    # Extract name and extension
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent

    # Try numbered suffixes
    for i in range(1, max_attempts + 1):
        new_path = parent / f"{stem}-{i}{suffix}"
        if not new_path.exists():
            return new_path

    # If we get here, we couldn't find a unique path
    raise RuntimeError(f"Unable to find unique path after {max_attempts} attempts for {base_path}")


def process_attachment(
        attachment_data: bytes | None,
        attachment_name: str,
        alt_text: str = "",
        attachment_mode: AttachmentMode = "alt_text",
        attachment_output_dir: str | None = None,
        attachment_base_url: str | None = None,
        is_image: bool = True,
        alt_text_mode: AltTextMode = DEFAULT_ALT_TEXT_MODE,
) -> dict[str, Any]:
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
        Base URL for resolving relative URLs in download mode.
        Note: Only the filename (not the directory structure) is appended to this URL.
        For example, if attachment_output_dir="attachments/images" and
        attachment_base_url="https://example.com/assets/", the resulting URL will be
        "https://example.com/assets/filename.png" (not ".../assets/attachments/images/filename.png")
    is_image : bool, default True
        Whether this is an image attachment
    alt_text_mode : AltTextMode, default "default"
        How to render alt-text content:
        - "default": Current behavior - ![alt] for images, [filename] for files
        - "plain_filename": Render non-images as plain filename text
        - "strict_markdown": Use ![alt](#) format for proper Markdown structure
        - "footnote": Use footnote references for accessibility

    Returns
    -------
    dict[str, Any]
        Dictionary with keys:
        - "markdown": str - Markdown representation of the attachment
        - "footnote_label": str | None - Footnote label if alt_text_mode is "footnote"
        - "footnote_content": str | None - Content for footnote definition
        - "url": str - URL/path for the attachment (empty for alt_text mode)

    """

    # Helper function to create result dict
    def _make_result(
            markdown: str, url: str = "", footnote_label: str | None = None, footnote_content: str | None = None
    ) -> dict[str, Any]:
        return {
            "markdown": markdown,
            "url": url,
            "footnote_label": footnote_label,
            "footnote_content": footnote_content,
        }

    # Helper function to build attachment markdown (centralized logic)
    def _build_attachment_markdown(
            is_image: bool, alt_text_mode: AltTextMode, text_content: str, attachment_name: str
    ) -> tuple[str, str | None, str | None]:
        """Build attachment markdown based on mode.

        Parameters
        ----------
        is_image : bool
            Whether this is an image attachment
        alt_text_mode : AltTextMode
            How to render alt-text content
        text_content : str
            Text to display (alt text for images, filename for files)
        attachment_name : str
            Attachment filename (used for footnote labels)

        Returns
        -------
        tuple[str, str | None, str | None]
            Tuple of (markdown, footnote_label, footnote_content)

        """
        if is_image:
            # Escape alt text for images to prevent Markdown injection
            escaped_text = escape_markdown_context_aware(text_content, context="image_alt")

            if alt_text_mode == "strict_markdown":
                return (f"![{escaped_text}](#)", None, None)
            elif alt_text_mode == "footnote":
                footnote_label = sanitize_footnote_label(attachment_name)
                markdown = f"![{escaped_text}] [^{footnote_label}]"
                return (markdown, footnote_label, text_content)
            else:  # default mode
                return (f"![{escaped_text}]", None, None)
        else:
            # Escape link text for files to prevent Markdown injection
            escaped_text = escape_markdown_context_aware(text_content, context="link")

            if alt_text_mode == "plain_filename":
                return (text_content, None, None)
            elif alt_text_mode == "strict_markdown":
                return (f"[{escaped_text}](#)", None, None)
            elif alt_text_mode == "footnote":
                footnote_label = sanitize_footnote_label(attachment_name)
                markdown = f"[{escaped_text}] [^{footnote_label}]"
                return (markdown, footnote_label, text_content)
            else:  # default mode
                return (f"[{escaped_text}]", None, None)

    # Helper function for fallback mode (replicates alt_text logic)
    def _make_fallback_result() -> dict[str, Any]:
        # For images: use alt_text if available, otherwise filename
        # For files: always use filename (alt_text is only for images)
        if is_image:
            text_content = alt_text or attachment_name
        else:
            text_content = attachment_name

        markdown, footnote_label, footnote_content = _build_attachment_markdown(
            is_image, alt_text_mode, text_content, attachment_name
        )
        # For strict_markdown mode, set url to "#"
        url = "#" if alt_text_mode == "strict_markdown" else ""
        return _make_result(markdown, url=url, footnote_label=footnote_label, footnote_content=footnote_content)

    if attachment_mode == "skip":
        logger.debug(f"Skipping attachment: {attachment_name}")
        return _make_result("")

    if attachment_mode == "alt_text":
        # Use the same logic as fallback mode - they are identical
        return _make_fallback_result()

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

            # Escape alt text for images to prevent Markdown injection
            escaped_alt = escape_markdown_context_aware(alt_text or attachment_name, context="image_alt")
            markdown = f"![{escaped_alt}]({data_uri})"
            return _make_result(markdown, url=data_uri)

    if attachment_mode == "download":
        if not attachment_output_dir:
            attachment_output_dir = "attachments"

        # Create output directory if it doesn't exist
        try:
            os.makedirs(attachment_output_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create attachment directory {attachment_output_dir}: {e}")
            # Fall back to alt-text mode if directory creation fails
            return _make_fallback_result()

        # Check if attachment data is available - cannot create download link without data
        if not attachment_data:
            logger.warning(
                f"No attachment data available for download mode: {attachment_name}. "
                f"Falling back to alt_text mode (alt_text_mode={alt_text_mode}, is_image={is_image})."
            )
            return _make_fallback_result()

        # Sanitize the filename for security
        safe_name = sanitize_attachment_filename(attachment_name)

        # Create the initial attachment path
        base_path = Path(attachment_output_dir) / safe_name

        # Ensure the path is unique to prevent collisions
        unique_path = ensure_unique_attachment_path(base_path)

        # Write attachment data to file
        try:
            with open(unique_path, "wb") as f:
                f.write(attachment_data)
            logger.debug(f"Wrote attachment to: {unique_path}")
        except OSError as e:
            logger.error(f"Failed to write attachment {unique_path}: {e}")
            # Fall back to alt-text mode if writing fails
            return _make_fallback_result()

        # Build URL using the final filename
        final_filename = unique_path.name

        # URL-encode the filename to handle special characters (spaces, &, #, etc.)
        # Use safe='' to encode all special characters
        encoded_filename = url_quote(final_filename, safe="")

        if attachment_base_url:
            # When using base URL, construct URL with encoded filename
            url = urljoin(attachment_base_url.rstrip("/") + "/", encoded_filename)
        else:
            # For local paths (no base URL), use POSIX-style paths with forward slashes
            # This ensures URLs work correctly even on Windows
            url = str(unique_path.as_posix())

        # Use the sanitized filename for display if no alt_text provided
        display_name = alt_text or safe_name

        # Escape display name to prevent Markdown injection
        if is_image:
            escaped_display = escape_markdown_context_aware(display_name, context="image_alt")
            markdown = f"![{escaped_display}]({url})"
        else:
            escaped_display = escape_markdown_context_aware(display_name, context="link")
            markdown = f"[{escaped_display}]({url})"

        return _make_result(markdown, url=url)

    # Fallback to alt_text mode if attachment data is missing or mode is unsupported
    logger.debug(
        f"Falling back to alt_text mode for attachment: {attachment_name} "
        f"(mode: {attachment_mode}, alt_text_mode: {alt_text_mode}, "
        f"has_data: {attachment_data is not None}, is_image: {is_image})"
    )
    return _make_fallback_result()


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
    except AttributeError as e:
        # Shape might not have image property or image might not have blob
        shape_id = getattr(shape, "shape_id", "unknown")
        logger.debug(f"Failed to extract image from PPTX shape {shape_id}: {e}")
        return None
    except Exception as e:
        # Catch other unexpected errors
        shape_id = getattr(shape, "shape_id", "unknown")
        logger.warning(f"Unexpected error extracting image from PPTX shape {shape_id}: {type(e).__name__}: {e}")
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
        if hasattr(image_part, "content_type") and image_part.content_type:
            content_type = image_part.content_type.lower()
            if "jpeg" in content_type or "jpg" in content_type:
                extension = "jpg"
            elif "gif" in content_type:
                extension = "gif"
            elif "png" in content_type:
                extension = "png"
            elif "bmp" in content_type:
                extension = "bmp"
            elif "tiff" in content_type:
                extension = "tiff"

        # Try to get extension from part name if content type didn't work
        elif hasattr(image_part, "partname") and image_part.partname:
            part_name = str(image_part.partname).lower()
            if ".jpg" in part_name or ".jpeg" in part_name:
                extension = "jpg"
            elif ".gif" in part_name:
                extension = "gif"
            elif ".png" in part_name:
                extension = "png"
            elif ".bmp" in part_name:
                extension = "bmp"
            elif ".tiff" in part_name or ".tif" in part_name:
                extension = "tiff"

        return image_bytes, extension
    except KeyError as e:
        # Relationship ID not found in related_parts
        logger.debug(f"Failed to extract image from DOCX: relationship ID '{blip_rId}' not found: {e}")
        return None, None
    except AttributeError as e:
        # Missing expected attributes (parent.part, related_parts, blob, etc.)
        logger.debug(f"Failed to extract image from DOCX with rId '{blip_rId}': missing attribute: {e}")
        return None, None
    except Exception as e:
        # Catch other unexpected errors
        logger.warning(f"Unexpected error extracting image from DOCX with rId '{blip_rId}': {type(e).__name__}: {e}")
        return None, None


def generate_attachment_filename(
        base_stem: str,
        attachment_type: str = "img",
        format_type: str = "general",
        page_num: int | None = None,
        slide_num: int | None = None,
        sequence_num: int = 1,
        extension: str = "png",
) -> str:
    """Generate standardized attachment filenames across all parsers.

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


class AttachmentSequencer(Protocol):
    """Protocol for attachment filename sequencer callables.

    This protocol defines the signature for functions returned by
    create_attachment_sequencer(). The sequencer generates unique,
    sequential filenames for attachments based on format-specific rules.

    Thread Safety Warning
    ---------------------
    Sequencers created by create_attachment_sequencer() are NOT thread-safe.
    They use shared mutable state without synchronization. Each conversion
    should create its own sequencer instance, and concurrent conversions
    must not share the same sequencer.

    Parameters
    ----------
    base_stem : str
        Base filename stem (without extension) from the source document
    format_type : str, default "general"
        Format context - one of "pdf", "pptx", or "general"
    **kwargs : Any
        Additional keyword arguments:
        - page_num : int | None - Page number for PDF format (required if format_type="pdf")
        - slide_num : int | None - Slide number for PPTX format (required if format_type="pptx")
        - extension : str - File extension without dot (default: "png")
        - attachment_type : str - Type of attachment (default: "img")

    Returns
    -------
    tuple[str, int]
        Tuple of (generated filename, sequence number)

    """

    def __call__(
            self,
            base_stem: str,
            format_type: str = "general",
            **kwargs: Any,
    ) -> tuple[str, int]:
        """Generate unique sequential filename for attachment."""
        ...


def create_attachment_sequencer() -> AttachmentSequencer:
    """Create a closure that tracks attachment sequence numbers to prevent duplicates.

    Thread Safety Warning
    ---------------------
    The returned sequencer is NOT thread-safe. It maintains shared mutable state
    (used_filenames set and sequence_counters dict) without locks or synchronization.

    To use in concurrent scenarios, either:
    1. Create a separate sequencer for each thread/conversion (recommended)
    2. Wrap the sequencer calls with external synchronization (e.g., threading.Lock)

    Each document conversion should use its own sequencer instance.

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
    used_filenames: set[str] = set()
    sequence_counters: dict[str, int] = {}

    def get_next_filename(base_stem: str, format_type: str = "general", **kwargs: Any) -> tuple[str, int]:
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
            base_stem=base_stem, format_type=format_type, sequence_num=sequence_num, **kwargs
        )

        # Ensure uniqueness (failsafe)
        while filename in used_filenames:
            sequence_num += 1
            sequence_counters[key] = sequence_num
            filename = generate_attachment_filename(
                base_stem=base_stem, format_type=format_type, sequence_num=sequence_num, **kwargs
            )

        used_filenames.add(filename)
        return filename, sequence_num

    return get_next_filename
