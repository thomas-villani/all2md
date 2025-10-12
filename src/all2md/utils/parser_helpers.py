#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/parser_helpers.py
"""Parser helper utilities for reducing code duplication across parsers.

This module provides reusable helper functions for common patterns in document
parsers, including zip validation, temp file management, and footnote handling.

Functions
---------
- validate_zip_input: Validate zip archives across different input types
- validated_zip_input: Context manager for validated zip input with cleanup
- append_attachment_footnotes: Append attachment footnote definitions to document
"""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import IO, TYPE_CHECKING, Generator, Union

from all2md.utils.security import validate_zip_archive

if TYPE_CHECKING:
    from all2md.ast import Node


def validate_zip_input(
        input_data: Union[str, Path, IO[bytes], bytes],
        suffix: str = '.zip'
) -> None:
    """Validate a zip archive across different input types.

    This function handles zip validation for Path, bytes, and IO[bytes] inputs
    by creating temporary files when necessary and cleaning them up properly.

    Parameters
    ----------
    input_data : str, Path, IO[bytes], or bytes
        The input data to validate
    suffix : str, default '.zip'
        File suffix for temporary files (e.g., '.docx', '.xlsx', '.epub')

    Raises
    ------
    ZipFileSecurityError
        If the zip archive contains security threats
    MalformedFileError
        If the zip archive is corrupted or invalid

    Examples
    --------
    Validate a file path:

        >>> validate_zip_input("/path/to/file.docx", suffix='.docx')

    Validate bytes:

        >>> with open("file.docx", "rb") as f:
        ...     data = f.read()
        >>> validate_zip_input(data, suffix='.docx')

    Notes
    -----
    This function creates temporary files for bytes and IO[bytes] inputs
    to enable validation, and ensures proper cleanup even on errors.

    """
    if isinstance(input_data, (str, Path)):
        # Path/str inputs - validate directly
        validate_zip_archive(input_data)

    elif isinstance(input_data, bytes):
        # Bytes inputs - create temp file, validate, cleanup
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(input_data)
            tmp_path = tmp.name
        try:
            validate_zip_archive(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    elif hasattr(input_data, 'read'):
        # File-like inputs - read, validate, reset position
        original_position = input_data.tell() if hasattr(input_data, 'tell') else 0
        input_data.seek(0)
        data = input_data.read()
        input_data.seek(original_position)

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            validate_zip_archive(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@contextmanager
def validated_zip_input(
        input_data: Union[str, Path, IO[bytes], bytes],
        suffix: str = '.zip'
) -> Generator[Union[str, Path, IO[bytes], bytes], None, None]:
    """Context manager for validated zip input with automatic cleanup.

    This context manager validates zip archives and yields the input for parsing,
    ensuring proper cleanup of temporary files. For bytes/IO inputs, it creates
    a temporary file that can be reused, avoiding double-reading.

    Parameters
    ----------
    input_data : str, Path, IO[bytes], or bytes
        The input data to validate and parse
    suffix : str, default '.zip'
        File suffix for temporary files (e.g., '.docx', '.xlsx', '.epub')

    Yields
    ------
    Union[str, Path, IO[bytes], bytes]
        The validated input data (may be a temp file path for bytes/IO inputs)

    Raises
    ------
    ZipFileSecurityError
        If the zip archive contains security threats
    MalformedFileError
        If the zip archive is corrupted or invalid

    Examples
    --------
    Use with path input:

        >>> with validated_zip_input("/path/to/file.docx", '.docx') as validated:
        ...     doc = docx.Document(validated)

    Use with bytes input:

        >>> data = open("file.docx", "rb").read()
        >>> with validated_zip_input(data, '.docx') as validated:
        ...     # validated is a temp file path that's already been validated
        ...     doc = docx.Document(validated)

    Notes
    -----
    This context manager optimizes memory usage by avoiding double-reading
    of the input data. For bytes/IO inputs, it creates a single temp file
    that's validated once and can be reused for parsing.

    """
    temp_path = None

    try:
        if isinstance(input_data, (str, Path)):
            # Path/str inputs - validate directly and yield original
            validate_zip_archive(input_data)
            yield input_data

        elif isinstance(input_data, bytes):
            # Bytes inputs - create temp file, validate, yield path
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(input_data)
                temp_path = tmp.name
            validate_zip_archive(temp_path)
            yield temp_path

        elif hasattr(input_data, 'read'):
            # File-like inputs - read, create temp file, validate, yield path
            original_position = input_data.tell() if hasattr(input_data, 'tell') else 0
            input_data.seek(0)
            data = input_data.read()
            input_data.seek(original_position)

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(data)
                temp_path = tmp.name
            validate_zip_archive(temp_path)
            yield temp_path

        else:
            # Unsupported type - yield as-is (will likely fail downstream)
            yield input_data

    finally:
        # Clean up temp file if created
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def append_attachment_footnotes(
        children: list[Node],
        attachment_footnotes: dict[str, str],
        section_title: str = "Attachments"
) -> None:
    """Append attachment footnote definitions to document children.

    This function appends a heading and footnote definitions for attachments
    to the document's children list, following the standard pattern used across
    all parsers.

    Parameters
    ----------
    children : list[Node]
        The document's children list to append footnotes to
    attachment_footnotes : dict[str, str]
        Dictionary mapping footnote labels to content text
    section_title : str, default "Attachments"
        Title for the footnotes section heading

    Examples
    --------
    Append attachment footnotes to a document:

        >>> children = [Paragraph(...), ...]
        >>> footnotes = {"img1": "image1.png", "img2": "image2.jpg"}
        >>> append_attachment_footnotes(children, footnotes, "Image References")

    Notes
    -----
    This function modifies the children list in-place. If attachment_footnotes
    is empty, no changes are made.

    The footnotes are appended in sorted order by label to ensure consistent
    output across runs.

    """
    if not attachment_footnotes:
        return

    # Import AST nodes here to avoid circular dependencies
    from all2md.ast import FootnoteDefinition, Heading, Paragraph, Text

    # Add section heading
    children.append(
        Heading(level=2, content=[Text(content=section_title)])
    )

    # Add footnote definitions sorted by label
    for label in sorted(attachment_footnotes.keys()):
        content_text = attachment_footnotes[label]
        definition = FootnoteDefinition(
            identifier=label,
            content=[Paragraph(content=[Text(content=content_text)])]
        )
        children.append(definition)
