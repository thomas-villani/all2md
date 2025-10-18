"""Utilities for uniform input handling across all2md modules.

This module provides standardized input validation and conversion functions
that are used across all conversion modules in all2md. This ensures
consistent behavior when handling different input types (paths, file-like
objects, bytes, etc.) and provides clear error messages for unsupported inputs.

The functions in this module handle the conversion between different input
types and perform validation to ensure that inputs are suitable for
the requested conversion operations.

Functions
---------
- validate_and_convert_input: Main input validation and conversion function
- is_path_like: Check if input is path-like (string or Path object)
- is_file_like: Check if input is a file-like object
- escape_markdown_special: Escape special Markdown characters in text
- format_special_text: Format special text (underline, superscript, subscript)
- format_markdown_heading: Format headings in hash or underline style
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/inputs.py
import os
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, BinaryIO, Union

from all2md.constants import MARKDOWN_SPECIAL_CHARS
from all2md.exceptions import FileNotFoundError as All2MdFileNotFoundError
from all2md.exceptions import PageRangeError, ValidationError

# Type aliases for clarity
PathLike = Union[str, Path]
FileLike = Union[BinaryIO, BytesIO, StringIO]
InputType = Union[PathLike, FileLike, bytes, Any]


def is_path_like(obj: Any) -> bool:
    """Check if an object is path-like (string or pathlib.Path).

    Parameters
    ----------
    obj : Any
        Object to check

    Returns
    -------
    bool
        True if object is path-like, False otherwise

    Examples
    --------
    >>> is_path_like("document.pdf")
    True
    >>> is_path_like(Path("document.pdf"))
    True
    >>> is_path_like(BytesIO(b"data"))
    False

    """
    return isinstance(obj, (str, Path))


def is_file_like(obj: Any) -> bool:
    """Check if an object is file-like (has read method).

    Parameters
    ----------
    obj : Any
        Object to check

    Returns
    -------
    bool
        True if object appears to be file-like, False otherwise

    Examples
    --------
    >>> from io import BytesIO
    >>> is_file_like(BytesIO(b"data"))
    True
    >>> is_file_like("not_file_like")
    False

    """
    return hasattr(obj, "read") and callable(obj.read)


def validate_page_range(pages: list[int] | str | None, max_pages: int | None = None) -> list[int] | None:
    """Validate and normalize a page range specification.

    All page numbers are 1-based (like "page 1", "page 2") and converted to 0-based internally.

    Parameters
    ----------
    pages : list[int], str, or None
        Page specification (1-based):
        - list[int]: List of page numbers [1, 2, 3]
        - str: Page range string, e.g. "1-3,5,10-"
        - None: Use all pages
    max_pages : int or None, optional
        Maximum number of pages available for validation

    Returns
    -------
    list[int] or None
        Validated list of 0-based page indices, or None if input was None

    Raises
    ------
    PageRangeError
        If page numbers are invalid or out of range

    Examples
    --------
    >>> validate_page_range([1, 2, 3], max_pages=5)
    [0, 1, 2]
    >>> validate_page_range("1-3,5", max_pages=10)
    [0, 1, 2, 4]
    >>> validate_page_range("10-", max_pages=12)
    [9, 10, 11]
    >>> validate_page_range([0], max_pages=5)
    Traceback (most recent call last):
    ...
    all2md.exceptions.PageRangeError: Invalid page number: 0. Pages must be >= 1.

    """
    if pages is None:
        return None

    # Handle string page ranges
    if isinstance(pages, str):
        if max_pages is None:
            raise PageRangeError(
                "Cannot parse page range string without knowing document page count",
                parameter_value=pages,
            )
        try:
            # Use utility function to parse page range string
            pages = parse_page_ranges(pages, max_pages)
        except (ValueError, IndexError) as e:
            raise PageRangeError(
                f"Invalid page range format: {str(e)}. Use format like '1-3,5,10-'",
                parameter_value=pages,
            ) from e

    if not isinstance(pages, list):
        raise PageRangeError(
            f"Pages must be a list of integers or a string range, got {type(pages).__name__}",
            parameter_value=pages,
        )

    # Convert from 1-based to 0-based and validate
    converted_pages = []
    for page_num in pages:
        if not isinstance(page_num, int):
            raise PageRangeError(
                f"Page numbers must be integers, got {type(page_num).__name__}: {page_num}",
                parameter_value=pages,
            )

        if page_num < 1:
            raise PageRangeError(
                f"Invalid page number: {page_num}. Pages must be >= 1 (1-based indexing).",
                parameter_value=pages,
            )

        if max_pages is not None and page_num > max_pages:
            raise PageRangeError(
                f"Page number {page_num} is out of range. Document has {max_pages} pages (1-{max_pages}).",
                parameter_value=pages,
            )

        # Convert to 0-based
        converted_pages.append(page_num - 1)

    return converted_pages


def validate_and_convert_input(
    input_data: InputType, supported_types: list[str] | None = None, require_binary: bool = False
) -> tuple[Any, str]:
    """Validate input and convert to appropriate format for processing.

    This function handles the common pattern of accepting different input
    types (paths, file-like objects, bytes, document objects) and converting
    them to a format suitable for the conversion functions.

    Parameters
    ----------
    input_data : InputType
        Input data to validate and convert
    supported_types : list[str] or None, optional
        List of supported input type names for error messages
    require_binary : bool, default False
        Whether the input must be in binary mode (vs text mode)

    Returns
    -------
    tuple[Any, str]
        Tuple of (converted_input, input_type_description)
        where input_type_description is one of: "path", "file", "bytes", "object"

    Raises
    ------
    FileNotFoundError
        If the file does not exist
    ValidationError
        If the input type is not supported

    Examples
    --------
    >>> # Path input
    >>> data, type_desc = validate_and_convert_input("document.pdf")
    >>> print(type_desc)
    path

    >>> # File-like input
    >>> from io import BytesIO
    >>> data, type_desc = validate_and_convert_input(BytesIO(b"content"))
    >>> print(type_desc)
    file

    """
    if supported_types is None:
        supported_types = ["path-like", "file-like", "bytes", "document objects"]

    # Handle path-like inputs (strings, Path objects)
    if is_path_like(input_data):
        path_str = str(input_data)
        if not os.path.exists(path_str):
            raise All2MdFileNotFoundError(file_path=path_str)

        if not os.path.isfile(path_str):
            raise ValidationError(
                f"Path is not a file: {path_str}", parameter_name="input_data", parameter_value=input_data
            )

        return input_data, "path"

    # Handle bytes input
    elif isinstance(input_data, bytes):
        return BytesIO(input_data), "bytes"

    # Handle file-like objects
    elif is_file_like(input_data):
        # Check if it's the right mode (binary vs text)
        if require_binary and hasattr(input_data, "mode"):
            if "b" not in str(input_data.mode):
                raise ValidationError(
                    f"File must be opened in binary mode, got mode: {input_data.mode}",
                    parameter_name="input_data",
                    parameter_value=input_data,
                )

        return input_data, "file"

    # Handle document objects (e.g., PyMuPDF Document, python-docx Document)
    elif hasattr(input_data, "__class__"):
        # This is likely a document object from a library
        class_name = input_data.__class__.__name__

        # Accept common document objects
        known_document_types = [
            "Document",  # python-docx, PyMuPDF
            "Presentation",  # python-pptx
            "Workbook",  # openpyxl
        ]

        if class_name in known_document_types:
            return input_data, "object"

        # If it's an unknown object type, it might still be valid
        # Let the calling function decide
        return input_data, "object"

    else:
        # Unsupported input type
        type_name = type(input_data).__name__
        supported_str = ", ".join(supported_types)
        raise ValidationError(
            f"Unsupported input type: {type_name}. Supported types: {supported_str}",
            parameter_name="input_data",
            parameter_value=input_data,
        )


def escape_markdown_special(text: str, escape_chars: str | None = None) -> str:
    r"""Escape special Markdown characters in text to prevent formatting.

    Parameters
    ----------
    text : str
        Text containing potential Markdown special characters
    escape_chars : str or None, optional
        Characters to escape. If None, uses default set from constants

    Returns
    -------
    str
        Text with special characters escaped with backslashes

    Examples
    --------
    >>> escape_markdown_special("This *should* not be italic")
    'This \\*should\\* not be italic'
    >>> escape_markdown_special("Link: [text](url)")
    'Link: \\[text\\]\\(url\\)'

    """
    if escape_chars is None:
        escape_chars = MARKDOWN_SPECIAL_CHARS

    # Escape backslashes first to avoid double-escaping
    text = text.replace("\\", "\\\\")

    # Escape each special character
    for char in escape_chars:
        if char != "\\":  # Already handled backslashes
            text = text.replace(char, f"\\{char}")

    return text


def format_special_text(text: str, format_type: str, mode: str = "html") -> str:
    """Format special text (underline, superscript, subscript) according to mode.

    Parameters
    ----------
    text : str
        Text content to format
    format_type : {"underline", "superscript", "subscript"}
        Type of special formatting to apply
    mode : {"html", "markdown", "ignore"}, default "html"
        Output format mode:
        - "html": Use HTML tags (<u>, <sup>, <sub>)
        - "markdown": Use Markdown-style syntax (__, ^, ~)
        - "ignore": Return plain text without formatting

    Returns
    -------
    str
        Formatted text according to the specified mode

    Examples
    --------
    >>> format_special_text("underlined", "underline", "html")
    '<u>underlined</u>'
    >>> format_special_text("superscript", "superscript", "markdown")
    '^superscript^'
    >>> format_special_text("subscript", "subscript", "ignore")
    'subscript'

    """
    if mode == "ignore":
        return text

    format_map = {
        "html": {"underline": f"<u>{text}</u>", "superscript": f"<sup>{text}</sup>", "subscript": f"<sub>{text}</sub>"},
        "markdown": {"underline": f"__{text}__", "superscript": f"^{text}^", "subscript": f"~{text}~"},
    }

    if mode not in format_map:
        raise ValidationError(
            f"Invalid mode: {mode}. Must be 'html', 'markdown', or 'ignore'",
            parameter_name="mode",
            parameter_value=mode,
        )

    if format_type not in format_map[mode]:
        raise ValidationError(
            f"Invalid format_type: {format_type}. Must be 'underline', 'superscript', or 'subscript'",
            parameter_name="format_type",
            parameter_value=format_type,
        )

    return format_map[mode][format_type]


def format_markdown_heading(text: str, level: int, use_hash: bool = True) -> str:
    r"""Format a heading in Markdown using either hash or underline style.

    This function formats only the heading itself, without adding trailing blank
    lines. Block-level spacing should be handled by the caller (e.g., document
    renderers that add spacing between block elements).

    Parameters
    ----------
    text : str
        The heading text content
    level : int
        The heading level (1-6 for hash style, 1-2 for underline style)
    use_hash : bool, default True
        Whether to use hash-style headings (# Heading) or underline style (Heading\n=======)

    Returns
    -------
    str
        Formatted heading string ending with a single newline

    Examples
    --------
    >>> format_markdown_heading("Main Title", 1, use_hash=True)
    '# Main Title\n'
    >>> format_markdown_heading("Main Title", 1, use_hash=False)
    'Main Title\n==========\n'
    >>> format_markdown_heading("Subtitle", 2, use_hash=False)
    'Subtitle\n--------\n'

    Notes
    -----
    For underline style:
    - Level 1 headings use '=' characters for underline
    - Level 2+ headings use '-' characters for underline
    - Only levels 1-2 are supported for underline style; higher levels fall back to hash style

    For hash style:
    - Supports levels 1-6 (# to ######)
    - Levels beyond 6 are clamped to 6

    Spacing between blocks should be handled externally. This function does NOT
    add trailing blank lines to avoid conflicts with document-level spacing logic.

    """
    # Clamp level to valid ranges
    level = max(1, min(level, 6))

    # Strip and clean the text
    text = text.strip()

    if use_hash:
        # Hash-style: # Heading, ## Heading, etc.
        return f"{'#' * level} {text}\n"
    else:
        # Underline style: only supported for levels 1-2
        if level == 1:
            underline_char = "="
        elif level == 2:
            underline_char = "-"
        else:
            # Fall back to hash style for levels 3+
            return f"{'#' * level} {text}\n"

        underline = underline_char * len(text)
        return f"{text}\n{underline}\n"


def parse_page_ranges(page_spec: str, total_pages: int) -> list[int]:
    """Parse page range specification into list of 0-based page indices.

    Supports various formats:
    - "1-3" → [0, 1, 2]
    - "5" → [4]
    - "10-" → [9, 10, ..., total_pages-1]
    - "1-3,5,10-" → combined ranges
    - "5-3" → [2, 3, 4] (automatically swaps to "3-5")

    Reversed ranges (where start > end) are automatically corrected by swapping
    the values. For example, "10-5" is treated as "5-10".

    Parameters
    ----------
    page_spec : str
        Page range specification (1-based page numbers)
    total_pages : int
        Total number of pages in document

    Returns
    -------
    list of int
        Sorted list of 0-based page indices

    Examples
    --------
    >>> parse_page_ranges("1-3,5", 10)
    [0, 1, 2, 4]
    >>> parse_page_ranges("8-", 10)
    [7, 8, 9]
    >>> parse_page_ranges("10-5", 10)
    [4, 5, 6, 7, 8, 9]

    """
    pages = set()

    # Split by comma to handle multiple ranges
    parts = page_spec.split(",")

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Handle range (e.g., "1-3" or "10-")
        if "-" in part:
            range_parts = part.split("-", 1)
            start_str = range_parts[0].strip()
            end_str = range_parts[1].strip()

            # Parse start (1-based to 0-based)
            if start_str:
                start = int(start_str) - 1
            else:
                start = 0

            # Parse end (1-based to 0-based, or use total_pages if empty)
            if end_str:
                end = int(end_str) - 1
            else:
                end = total_pages - 1

            # Swap if reversed range (e.g., "10-5" becomes "5-10")
            if start > end:
                start, end = end, start

            # Add all pages in range
            for p in range(start, end + 1):
                if 0 <= p < total_pages:
                    pages.add(p)
        else:
            # Single page (1-based to 0-based)
            page = int(part) - 1
            if 0 <= page < total_pages:
                pages.add(page)

    # Return sorted list
    return sorted(pages)
