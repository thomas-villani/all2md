#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/base.py
"""Base classes for document parsers.

This module defines the abstract base class that all document parsers must inherit from.
The BaseParser provides a consistent interface for converting various document formats
into the all2md AST (Abstract Syntax Tree).

"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast import Document, Node
from all2md.exceptions import InvalidOptionsError, ValidationError
from all2md.options.base import BaseParserOptions
from all2md.progress import ProgressCallback, ProgressEvent
from all2md.utils.encoding import normalize_stream_to_bytes, normalize_stream_to_text, read_text_with_encoding_detection
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.parser_helpers import (
    append_attachment_footnotes as _append_attachment_footnotes_helper,
)
from all2md.utils.parser_helpers import (
    validate_zip_input as _validate_zip_input_helper,
)
from all2md.utils.parser_helpers import (
    validated_zip_input as _validated_zip_input_helper,
)

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """Abstract base class for all document parsers.

    All parsers in the all2md library must inherit from this class and implement
    the parse() method. This ensures a consistent interface for converting documents
    from various formats into the unified AST representation.

    Parameters
    ----------
    options : BaseParserOptions or None, default = None
        Format-specific parsing options
    progress_callback : ProgressCallback or None, default = None
        Optional callback for progress updates during parsing

    Examples
    --------
    Creating a custom parser:

        >>> from all2md.options.base import BaseParserOptions        >>> from all2md.parsers.base import BaseParser
        >>> from all2md.ast import Document
        >>>
        >>> class MyCustomParser(BaseParser):
        ...     def parse(self, input_data):
        ...         # Custom parsing logic here
        ...         return Document(children=[])

    Notes
    -----
    The parse() method should handle all supported input types:
    - str or Path: File path to read
    - IO[bytes]: File-like object in binary mode
    - bytes: Raw document bytes

    """

    def __init__(self, options: BaseParserOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the parser with optional configuration.

        Parameters
        ----------
        options : BaseParserOptions or None, default = None
            Format-specific parsing options. If None, default options will be used.
        progress_callback : ProgressCallback or None, default = None
            Optional callback for progress updates during parsing.

        """
        self.options: BaseParserOptions | None = options
        self.progress_callback: Optional[ProgressCallback] = progress_callback

    @staticmethod
    def _validate_options_type(options: BaseParserOptions | None, expected_type: type, parser_name: str) -> None:
        """Validate that options are of the correct type for this parser.

        Parameters
        ----------
        options : BaseParserOptions or None
            The options object to validate
        expected_type : type
            The expected options class type
        parser_name : str
            Name of the parser (for error messages)

        Raises
        ------
        InvalidOptionsError
            If options are not None and not an instance of expected_type

        """
        if options is not None and not isinstance(options, expected_type):
            raise InvalidOptionsError(
                converter_name=parser_name,
                expected_type=expected_type,
                received_type=type(options),
            )

    @abstractmethod
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse the input document into an AST.

        This method must be implemented by all parser subclasses. It should
        handle all supported input types and return a Document AST node.

        Implementations should typically:
        1. Load the document from input_data
        2. Extract metadata via extract_metadata()
        3. Parse content to AST
        4. Set metadata on the Document node
        5. Return the Document

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input document to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw document bytes

        Returns
        -------
        Document
            AST Document node representing the parsed document structure

        Raises
        ------
        ParsingError
            If parsing fails due to invalid format or corruption
        DependencyError
            If required dependencies are not installed
        ValidationError
            If input data is invalid or inaccessible

        """
        raise NotImplementedError

    @abstractmethod
    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from the source document.

        This method must be implemented by all parser subclasses. It should
        extract format-specific metadata (title, author, dates, etc.) from
        the loaded document object.

        Parameters
        ----------
        document : Any
            The loaded document object (format-specific type, e.g.,
            docx.Document, fitz.Document, email.message.Message, etc.)

        Returns
        -------
        DocumentMetadata
            Extracted metadata including title, author, dates, keywords, etc.
            Returns empty DocumentMetadata if no metadata is available.

        Notes
        -----
        Implementations should handle missing or invalid metadata gracefully
        and return a valid DocumentMetadata object even if empty.

        """
        raise NotImplementedError

    def _emit_progress(self, event_type: str, message: str, current: int = 0, total: int = 0, **metadata: Any) -> None:
        """Emit a progress event to the callback if registered.

        This helper method safely emits progress events, handling cases where
        no callback is registered or the callback raises an exception.

        Parameters
        ----------
        event_type : str
            Type of progress event (started, item_done, detected, finished, error)
        message : str
            Human-readable description of the event
        current : int, default 0
            Current progress position
        total : int, default 0
            Total items to process
        **metadata
            Additional event-specific information

        Notes
        -----
        If the callback raises an exception, it will be caught and logged to
        prevent interrupting the conversion process.

        Examples
        --------
        Emit a started event:
            >>> self._emit_progress("started", "Converting document", total=10)

        Emit an item done event (page):
            >>> self._emit_progress("item_done", f"Page {n}", current=n, total=10, item_type="page", page=n)

        Emit a detected event (table):
            >>> self._emit_progress(
            ...     "detected",
            ...     "Table found",
            ...     current=page_num,
            ...     total=total_pages,
            ...     detected_type="table",
            ...     table_count=2
            ... )

        """
        if not self.progress_callback:
            return

        try:
            event = ProgressEvent(
                event_type=event_type,  # type: ignore[arg-type]
                message=message,
                current=current,
                total=total,
                metadata=metadata,
            )
            self.progress_callback(event)
        except Exception as e:
            # Log but don't interrupt conversion if callback fails
            logger.warning(f"Progress callback raised exception: {e}", exc_info=True)

    @staticmethod
    def _validate_zip_security(input_data: Union[str, Path, IO[bytes], bytes], suffix: str = ".zip") -> None:
        """Validate security of a zip archive across different input types.

        This helper method delegates to the parser_helpers module to perform
        security validation for zip archives. This method only performs validation
        and does not return a usable input object.

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

        Notes
        -----
        This method should be called early in the parse() method to validate
        zip-based formats before processing. For parsers that need to use the
        validated input, prefer _validated_zip_input() which provides a context
        manager that yields a usable input object.

        """
        _validate_zip_input_helper(input_data, suffix)

    @staticmethod
    def _validated_zip_input(input_data: Union[str, Path, IO[bytes], bytes], suffix: str = ".zip") -> Any:
        """Context manager for validated zip input with automatic cleanup.

        This helper method delegates to the parser_helpers module to provide
        a context manager for zip validation with temp file cleanup.

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

        Notes
        -----
        This method optimizes memory usage by avoiding double-reading of input data.
        Prefer this over _validate_zip_security() when you need to reuse the validated input.

        """
        return _validated_zip_input_helper(input_data, suffix)

    @staticmethod
    def _append_attachment_footnotes(
        children: list[Node], attachment_footnotes: dict[str, str], section_title: str = "Attachments"
    ) -> None:
        """Append attachment footnote definitions to document children.

        This helper method delegates to the parser_helpers module to append
        footnote definitions following the standard pattern.

        Parameters
        ----------
        children : list[Node]
            The document's children list to append footnotes to
        attachment_footnotes : dict[str, str]
            Dictionary mapping footnote labels to content text
        section_title : str, default "Attachments"
            Title for the footnotes section heading

        Notes
        -----
        This method modifies the children list in-place. If attachment_footnotes
        is empty, no changes are made.

        """
        _append_attachment_footnotes_helper(children, attachment_footnotes, section_title)

    @staticmethod
    def _load_text_content(input_data: Union[str, Path, IO[bytes], bytes]) -> str:
        """Load content from various input types with encoding detection.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Input data to load

        Returns
        -------
        str
            AsciiDoc content as string

        """
        if isinstance(input_data, bytes):
            return read_text_with_encoding_detection(input_data)
        elif isinstance(input_data, Path):
            with open(input_data, "rb") as f:
                return read_text_with_encoding_detection(f.read())
        elif isinstance(input_data, str):
            # Could be file path or content
            # Check length first - Linux has 255 char limit for path components,
            # and calling path.exists() on very long strings raises OSError
            if len(input_data) <= 260 and "\n" not in input_data:
                try:
                    path = Path(input_data)
                    if path.exists() and path.is_file():
                        with open(path, "rb") as f:
                            return read_text_with_encoding_detection(f.read())
                except OSError:
                    # Path too long or invalid - treat as content
                    pass
            # Assume it's content
            return input_data
        else:
            # File-like object (handles both binary and text mode)
            input_data.seek(0)
            return normalize_stream_to_text(input_data)

    @staticmethod
    def _load_bytes_content(input_data: Union[str, Path, IO[bytes], bytes]) -> bytes:
        """Load data as bytes from various input types.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Input data to load

        Returns
        -------
        bytes
            Raw bytes

        """
        if isinstance(input_data, bytes):
            return input_data
        elif isinstance(input_data, (str, Path)):
            path = Path(input_data)
            return path.read_bytes()
        elif hasattr(input_data, "read"):
            return normalize_stream_to_bytes(input_data)
        else:
            raise ValidationError(
                f"Unsupported input type: {type(input_data).__name__}",
                parameter_name="input_data",
                parameter_value=input_data,
            )
