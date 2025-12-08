#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/parser_helpers.py
"""Parser helper utilities for reducing code duplication across parsers.

This module provides reusable helper functions for common patterns in document
parsers, including zip validation, temp file management, footnote handling,
attachment processing, and text formatting.

Functions
---------
- validate_zip_input: Validate zip archives across different input types
- validated_zip_input: Context manager for validated zip input with cleanup
- append_attachment_footnotes: Append attachment footnote definitions to document
- attachment_result_to_image_node: Convert process_attachment result to Image AST node
- group_and_format_runs: Group text runs by formatting and build formatted AST nodes
- parse_delimited_block: Parse delimited blocks with opening/closing delimiters
"""

from __future__ import annotations

import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any, Callable, Generator, Iterable, Union

from all2md.ast import Emphasis, FootnoteDefinition, Heading, Image, Node, Paragraph, Strong, Text, Underline
from all2md.utils.security import validate_zip_archive


def validate_zip_input(input_data: Union[str, Path, IO[bytes], bytes], suffix: str = ".zip") -> None:
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

    elif hasattr(input_data, "read"):
        # File-like inputs - read, validate, reset position (if seekable)
        if hasattr(input_data, "seek"):
            # Seekable stream - preserve position
            original_position = input_data.tell() if hasattr(input_data, "tell") else 0
            input_data.seek(0)
            data = input_data.read()
            input_data.seek(original_position)
        else:
            # Non-seekable stream - read once
            data = input_data.read()

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
    input_data: Union[str, Path, IO[bytes], bytes], suffix: str = ".zip"
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

        elif hasattr(input_data, "read"):
            # File-like inputs - read, create temp file, validate, yield path
            if hasattr(input_data, "seek"):
                # Seekable stream - preserve position
                original_position = input_data.tell() if hasattr(input_data, "tell") else 0
                input_data.seek(0)
                data = input_data.read()
                input_data.seek(original_position)
            else:
                # Non-seekable stream - read once
                data = input_data.read()

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
    children: list[Node], attachment_footnotes: dict[str, str], section_title: str = "Attachments"
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

    # Add section heading
    children.append(Heading(level=2, content=[Text(content=section_title)]))

    # Add footnote definitions sorted by label
    for label in sorted(attachment_footnotes.keys()):
        content_text = attachment_footnotes[label]
        definition = FootnoteDefinition(identifier=label, content=[Paragraph(content=[Text(content=content_text)])])
        children.append(definition)


def attachment_result_to_image_node(
    attachment_result: dict[str, Any], fallback_alt_text: str = "image"
) -> "Node | None":
    """Convert process_attachment result dict to Image AST node.

    This helper eliminates the need for parsers to manually parse markdown
    strings with regex to extract URL and alt-text. It directly uses the
    structured data from process_attachment.

    Parameters
    ----------
    attachment_result : dict[str, Any]
        Result dictionary from process_attachment containing:
        - "url": str - Image URL or data URI
        - "markdown": str - Markdown representation (used as fallback)
        - "footnote_label": str | None - Footnote label if applicable
        - "footnote_content": str | None - Footnote content if applicable
        - "source_data": str | None - Source of image data (e.g., "base64", "downloaded")
    fallback_alt_text : str, default "image"
        Alt text to use if not extractable from markdown

    Returns
    -------
    Node or None
        Image AST node, or None if attachment result is empty/invalid

    Examples
    --------
    Convert attachment result to Image node:

        >>> result = process_attachment(
        ...     attachment_data=image_bytes,
        ...     attachment_name="photo.jpg",
        ...     alt_text="Photo",
        ...     attachment_mode="base64"
        ... )
        >>> image_node = attachment_result_to_image_node(result, "image")

    Notes
    -----
    This function handles all attachment modes (skip, alt_text, save, base64)
    consistently. It extracts URL directly from the result dict when available,
    and only falls back to markdown parsing when necessary.

    """
    # Check if result has content
    markdown = attachment_result.get("markdown", "")
    if not markdown:
        return None

    # Get URL directly from result (available for save/base64 modes)
    url = attachment_result.get("url", "")

    # Extract alt text from markdown using simple regex
    # Pattern: ![alt_text](url) or ![alt_text] or ![alt_text][^footnote]
    match = re.match(r"^!\[([^]]*)]", markdown)
    if match:
        alt_text = match.group(1) or fallback_alt_text
    else:
        alt_text = fallback_alt_text

    # Create Image node
    # For alt_text mode without URL, pass empty string (renderer will handle)
    image_node = Image(url=url, alt_text=alt_text, title=None)

    source_data = attachment_result.get("source_data")
    if source_data:
        image_node.metadata["source_data"] = source_data

    return image_node


def group_and_format_runs(
    runs: Iterable[Any],
    text_extractor: Callable[[Any], str],
    format_extractor: Callable[[Any], tuple[bool, ...]],
    format_builders: tuple[Callable[[list["Node"]], "Node"], ...] | None = None,
) -> list["Node"]:
    """Group text runs by formatting and build formatted AST nodes.

    This helper consolidates the common pattern across DOCX, PPTX, ODT, and ODP
    parsers for processing text runs with formatting. It:
    1. Groups consecutive runs with identical formatting
    2. Builds formatted inline nodes with appropriate wrappers

    Parameters
    ----------
    runs : Iterable[Any]
        Iterable of run objects (format-specific, e.g., docx.Run, pptx Run)
    text_extractor : Callable[[Any], str]
        Function to extract text from a run object
    format_extractor : Callable[[Any], tuple[bool, ...]]
        Function to extract formatting flags from a run object.
        Should return tuple of booleans in order: (bold, italic, underline, ...)
    format_builders : tuple[Callable, ...] | None, default None
        Optional tuple of functions to build formatted nodes. Each function takes
        list[Node] and returns Node. Default order: (Strong, Emphasis, Underline).
        Length must match format_extractor tuple length.

    Returns
    -------
    list[Node]
        List of inline AST nodes with appropriate formatting applied

    Examples
    --------
    Use with DOCX runs:

        >>> def get_text(run):
        ...     return run.text
        >>> def get_format(run):
        ...     return (bool(run.font.bold), bool(run.font.italic))
        >>> nodes = group_and_format_runs(
        ...     paragraph.runs,
        ...     text_extractor=get_text,
        ...     format_extractor=get_format
        ... )

    Use with custom format builders:

        >>> from all2md.ast import Strong, Emphasis, Strikethrough
        >>> nodes = group_and_format_runs(
        ...     runs,
        ...     text_extractor=lambda r: r.text,
        ...     format_extractor=lambda r: (r.bold, r.italic, r.strike),
        ...     format_builders=(
        ...         lambda nodes: Strong(content=nodes),
        ...         lambda nodes: Emphasis(content=nodes),
        ...         lambda nodes: Strikethrough(content=nodes)
        ...     )
        ... )

    Notes
    -----
    The function applies formatting layers from outermost to innermost based on
    the order of format flags. For example, with (bold=True, italic=True):
    - Text node is created
    - Wrapped in Emphasis (italic)
    - Wrapped in Strong (bold)

    This matches the rendering order where bold appears before italic in markdown.

    """
    # Default format builders if not provided
    if format_builders is None:
        format_builders = (
            lambda nodes: Strong(content=nodes),
            lambda nodes: Emphasis(content=nodes),
            lambda nodes: Underline(content=nodes),
        )

    result: list[Node] = []
    current_text: list[str] = []
    current_format: tuple[bool, ...] | None = None

    def flush_group() -> None:
        """Flush current text group as formatted node."""
        if not current_text:
            return

        # Join text and strip only at the group level to preserve inter-run whitespace
        text_value = "".join(current_text).strip()
        if not text_value:
            # Skip whitespace-only groups
            current_text.clear()
            return

        # Build inline node with formatting
        inline_node: Node = Text(content=text_value)

        if current_format:
            # Apply formatting layers in reverse order (innermost first)
            # This ensures proper nesting: Text -> Underline -> Strong -> Emphasis
            for i in range(len(current_format) - 1, -1, -1):
                if current_format[i] and i < len(format_builders):
                    inline_node = format_builders[i]([inline_node])

        result.append(inline_node)
        current_text.clear()

    # Process runs
    for run in runs:
        # Extract text and skip completely empty runs
        text = text_extractor(run)
        if not text:
            continue

        # Extract formatting
        format_key = format_extractor(run)

        # Check if format changed
        if format_key != current_format:
            flush_group()
            current_format = format_key

        # Append original text (not stripped) to preserve inter-run whitespace
        current_text.append(text)

    # Flush final group
    flush_group()

    return result


def parse_delimited_block(
    current_token_fn: Callable[[], Any],
    advance_fn: Callable[[], Any],
    opening_delimiter_type: Any,
    closing_delimiter_type: Any,
    eof_type: Any,
    collect_mode: str = "lines",
    parse_block_fn: Callable[[], Any] | None = None,
) -> tuple[list[str] | list[Any], bool]:
    r"""Parse a delimited block with opening and closing delimiters.

    This helper consolidates the common pattern in AsciiDoc parser for parsing
    delimited blocks (code blocks, quote blocks, literal blocks, etc.) that have:
    - An opening delimiter line
    - Content (lines or blocks)
    - A closing delimiter line (or EOF)

    Parameters
    ----------
    current_token_fn : Callable[[], Any]
        Function that returns the current token
    advance_fn : Callable[[], Any]
        Function that advances to the next token and returns the previous one
    opening_delimiter_type : Any
        Token type for the opening delimiter (not used, assumed already consumed)
    closing_delimiter_type : Any
        Token type for the closing delimiter to watch for
    eof_type : Any
        Token type representing end of file
    collect_mode : str, default "lines"
        Mode for collecting content:
        - "lines": Collect text lines (returns list[str])
        - "blocks": Parse blocks using parse_block_fn (returns list[Node])
    parse_block_fn : Callable[[], Any] | None, default None
        Function to parse individual blocks (required if collect_mode="blocks")

    Returns
    -------
    tuple[list[str] | list[Any], bool]
        Tuple of (collected content, found_closing_delimiter)
        - content: List of strings (if mode="lines") or list of Nodes (if mode="blocks")
        - found_closing_delimiter: True if closing delimiter was found, False if EOF

    Raises
    ------
    ValueError
        If collect_mode="blocks" but parse_block_fn is not provided

    Examples
    --------
    Use with AsciiDoc parser for code blocks:

        >>> content, found_closing = parse_delimited_block(
        ...     current_token_fn=self._current_token,
        ...     advance_fn=self._advance,
        ...     opening_delimiter_type=TokenType.CODE_BLOCK_DELIMITER,
        ...     closing_delimiter_type=TokenType.CODE_BLOCK_DELIMITER,
        ...     eof_type=TokenType.EOF,
        ...     collect_mode="lines"
        ... )
        >>> code_content = '\\n'.join(content)

    Use for quote blocks:

        >>> children, found_closing = parse_delimited_block(
        ...     current_token_fn=self._current_token,
        ...     advance_fn=self._advance,
        ...     opening_delimiter_type=TokenType.QUOTE_BLOCK_DELIMITER,
        ...     closing_delimiter_type=TokenType.QUOTE_BLOCK_DELIMITER,
        ...     eof_type=TokenType.EOF,
        ...     collect_mode="blocks",
        ...     parse_block_fn=self._parse_block
        ... )

    Notes
    -----
    This helper assumes the opening delimiter has already been consumed before
    calling this function. It will:
    1. Collect content until closing delimiter or EOF
    2. Consume the closing delimiter if found
    3. Return the collected content and a flag indicating if delimiter was found

    """
    if collect_mode == "blocks" and parse_block_fn is None:
        raise ValueError("parse_block_fn is required when collect_mode='blocks'")

    collected: list[str] | list[Any]
    if collect_mode == "lines":
        collected = []
    else:
        collected = []

    found_closing = False

    # Collect content until closing delimiter or EOF
    while True:
        current = current_token_fn()

        # Check for closing delimiter
        if current.type == closing_delimiter_type:
            found_closing = True
            break

        # Check for EOF
        if current.type == eof_type:
            break

        if collect_mode == "lines":
            # Collect lines
            token = advance_fn()
            if hasattr(token, "type"):
                # AsciiDoc-style token with type attribute
                if hasattr(token, "content"):
                    # TEXT_LINE token
                    collected.append(token.content)
                else:
                    # BLANK_LINE or other
                    collected.append("")
        else:
            # Parse and collect blocks
            if parse_block_fn:
                node = parse_block_fn()
                if node is not None:
                    if isinstance(node, list):
                        collected.extend(node)
                    else:
                        collected.append(node)

    # Consume closing delimiter if found
    if found_closing:
        advance_fn()

    return collected, found_closing
