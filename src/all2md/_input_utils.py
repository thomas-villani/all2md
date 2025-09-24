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

import os
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, BinaryIO, Union

from .constants import MARKDOWN_SPECIAL_CHARS
from .exceptions import MdparseInputError

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
    return hasattr(obj, 'read') and callable(obj.read)


def validate_page_range(pages: list[int] | None, max_pages: int | None = None) -> list[int] | None:
    """Validate and normalize a page range specification.

    Parameters
    ----------
    pages : list[int] or None
        List of 0-based page numbers to validate
    max_pages : int or None, optional
        Maximum number of pages available for validation

    Returns
    -------
    list[int] or None
        Validated list of page numbers, or None if input was None

    Raises
    ------
    MdparseInputError
        If page numbers are invalid or out of range

    Examples
    --------
    >>> validate_page_range([0, 1, 2], max_pages=5)
    [0, 1, 2]
    >>> validate_page_range([-1], max_pages=5)
    Traceback (most recent call last):
    ...
    all2md.exceptions.MdparseInputError: Invalid page number: -1. Pages must be 0-based.
    """
    if pages is None:
        return None

    if not isinstance(pages, list):
        raise MdparseInputError(
            f"Pages must be a list of integers, got {type(pages).__name__}",
            parameter_name="pages",
            parameter_value=pages
        )

    for page_num in pages:
        if not isinstance(page_num, int):
            raise MdparseInputError(
                f"Page numbers must be integers, got {type(page_num).__name__}: {page_num}",
                parameter_name="pages",
                parameter_value=pages
            )

        if page_num < 0:
            raise MdparseInputError(
                f"Invalid page number: {page_num}. Pages must be 0-based (>= 0).",
                parameter_name="pages",
                parameter_value=pages
            )

        if max_pages is not None and page_num >= max_pages:
            raise MdparseInputError(
                f"Page number {page_num} is out of range. Document has {max_pages} pages (0-{max_pages-1}).",
                parameter_name="pages",
                parameter_value=pages
            )

    return pages


def validate_and_convert_input(
    input_data: InputType,
    supported_types: list[str] | None = None,
    require_binary: bool = False
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
    MdparseInputError
        If the input type is not supported or if file operations fail

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
            raise MdparseInputError(
                f"File does not exist: {path_str}",
                parameter_name="input_data",
                parameter_value=input_data
            )

        if not os.path.isfile(path_str):
            raise MdparseInputError(
                f"Path is not a file: {path_str}",
                parameter_name="input_data",
                parameter_value=input_data
            )

        return input_data, "path"

    # Handle bytes input
    elif isinstance(input_data, bytes):
        return BytesIO(input_data), "bytes"

    # Handle file-like objects
    elif is_file_like(input_data):
        # Check if it's the right mode (binary vs text)
        if require_binary and hasattr(input_data, 'mode'):
            if 'b' not in str(input_data.mode):
                raise MdparseInputError(
                    f"File must be opened in binary mode, got mode: {input_data.mode}",
                    parameter_name="input_data",
                    parameter_value=input_data
                )

        return input_data, "file"

    # Handle document objects (e.g., PyMuPDF Document, python-docx Document)
    elif hasattr(input_data, '__class__'):
        # This is likely a document object from a library
        class_name = input_data.__class__.__name__

        # Accept common document objects
        known_document_types = [
            'Document',  # python-docx, PyMuPDF
            'Presentation',  # python-pptx
            'Workbook',  # openpyxl
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
        raise MdparseInputError(
            f"Unsupported input type: {type_name}. Supported types: {supported_str}",
            parameter_name="input_data",
            parameter_value=input_data
        )


def escape_markdown_special(text: str, escape_chars: str | None = None) -> str:
    """Escape special Markdown characters in text to prevent formatting.

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
    text = text.replace('\\', '\\\\')

    # Escape each special character
    for char in escape_chars:
        if char != '\\':  # Already handled backslashes
            text = text.replace(char, f'\\{char}')

    return text


def format_special_text(
    text: str,
    format_type: str,
    mode: str = "html"
) -> str:
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
        "html": {
            "underline": f"<u>{text}</u>",
            "superscript": f"<sup>{text}</sup>",
            "subscript": f"<sub>{text}</sub>"
        },
        "markdown": {
            "underline": f"__{text}__",
            "superscript": f"^{text}^",
            "subscript": f"~{text}~"
        }
    }

    if mode not in format_map:
        raise MdparseInputError(
            f"Invalid mode: {mode}. Must be 'html', 'markdown', or 'ignore'",
            parameter_name="mode",
            parameter_value=mode
        )

    if format_type not in format_map[mode]:
        raise MdparseInputError(
            f"Invalid format_type: {format_type}. Must be 'underline', 'superscript', or 'subscript'",
            parameter_name="format_type",
            parameter_value=format_type
        )

    return format_map[mode][format_type]

