#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/base.py
"""Base classes for document parsers.

This module defines the abstract base class that all document parsers must inherit from.
The BaseParser provides a consistent interface for converting various document formats
into the all2md AST (Abstract Syntax Tree).

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, IO, Union

from all2md.ast import Document
from all2md.options import BaseParserOptions
from all2md.utils.metadata import DocumentMetadata


class BaseParser(ABC):
    """Abstract base class for all document parsers.

    All parsers in the all2md library must inherit from this class and implement
    the parse() method. This ensures a consistent interface for converting documents
    from various formats into the unified AST representation.

    Parameters
    ----------
    options : BaseParserOptions or None, default = None
        Format-specific parsing options

    Examples
    --------
    Creating a custom parser:

        >>> from all2md.parsers.base import BaseParser
        >>> from all2md.ast import Document
        >>> from all2md.options import BaseParserOptions
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

    def __init__(self, options: BaseParserOptions | None = None):
        """Initialize the parser with optional configuration.

        Parameters
        ----------
        options : BaseParserOptions or None, default = None
            Format-specific parsing options. If None, default options will be used.

        """
        self.options: BaseParserOptions = options

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
        MarkdownConversionError
            If parsing fails due to invalid format or corruption
        DependencyError
            If required dependencies are not installed
        InputError
            If input data is invalid or inaccessible

        """
        pass

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
        pass
