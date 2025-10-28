#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/base.py
"""Base classes for AST renderers.

This module defines the abstract base class that all AST renderers must inherit from.
The BaseRenderer provides a consistent interface for converting the all2md AST
into various output formats.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import IO, Any, Dict, Mapping, Union

from all2md.ast import Document
from all2md.ast.nodes import Node, TableRow
from all2md.exceptions import InvalidOptionsError
from all2md.options.base import BaseRendererOptions
from all2md.utils.io_utils import write_content
from all2md.utils.metadata import DocumentMetadata, MetadataRenderPolicy, prepare_metadata_for_render


class BaseRenderer(ABC):
    """Abstract base class for all AST renderers.

    All renderers in the all2md library must inherit from this class and implement
    the render() method. This ensures a consistent interface for converting the
    unified AST representation into various output formats.

    Parameters
    ----------
    options : BaseRendererOptions or None, default = None
        Format-specific rendering options

    Examples
    --------
    Creating a custom renderer:

        >>> from all2md.options.base import BaseRendererOptions
        >>> from all2md.renderers.base import BaseRenderer
        >>> from all2md.ast import Document
        >>>
        >>> class MyCustomRenderer(BaseRenderer):
        ...     def render(self, doc, output):
        ...         # Custom rendering logic here
        ...         pass
        ...
        ...     def render_to_string(self, doc):
        ...         # Return string representation
        ...         return "rendered output"

    """

    def __init__(self, options: BaseRendererOptions | None = None):
        """Initialize the renderer with optional configuration.

        Parameters
        ----------
        options : BaseRendererOptions or None, default = None
            Format-specific rendering options. If None, default options will be used.

        """
        self.options = options
        self.metadata_policy: MetadataRenderPolicy = options.metadata_policy if options else MetadataRenderPolicy()

    @abstractmethod
    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render the AST to the specified output format.

        This method must be implemented by all renderer subclasses. It should
        write the rendered output to a file or file-like object.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination. Can be:
            - File path (str or Path)
            - File-like object in binary mode

        Raises
        ------
        RenderingError
            If rendering fails
        IOError
            If output cannot be written

        """
        pass

    def render_to_string(self, doc: Document) -> str:
        """Render the AST to a string (if applicable).

        This method is optional and should be implemented by renderers
        that produce text-based output formats.

        Parameters
        ----------
        doc : Document
            AST Document node to render

        Returns
        -------
        str
            Rendered document as a string

        Raises
        ------
        NotImplementedError
            If the renderer does not support string output

        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support rendering to a string.")

    def render_to_bytes(self, doc: Document) -> bytes:
        """Render the AST to bytes (if applicable).

        This method is provided as a default implementation for binary renderers.
        It creates a BytesIO buffer, calls render() with it, and returns the bytes.

        Binary renderers can use this default implementation if their render()
        method properly supports IO[bytes] output. Alternatively, they can
        override this method for custom behavior.

        Parameters
        ----------
        doc : Document
            AST Document node to render

        Returns
        -------
        bytes
            Rendered document as bytes

        Raises
        ------
        NotImplementedError
            If the renderer does not support binary output

        Notes
        -----
        The returned bytes can be used in various ways:
        - Write to file: `Path("out.ext").write_bytes(result)`
        - Pass to IO functions: `BytesIO(result)`
        - Send over network or process further

        Examples
        --------
        Default usage (if render() supports IO[bytes]):
            >>> from all2md.renderers.docx import DocxRenderer
            >>> from all2md.ast import Document, Paragraph, Text
            >>> doc = Document(children=[Paragraph(content=[Text(content="test")])])
            >>> renderer = DocxRenderer()
            >>> content = renderer.render_to_bytes(doc)
            >>> assert content.startswith(b'PK')  # DOCX is a ZIP file

        """
        buffer = BytesIO()
        try:
            self.render(doc, buffer)
            return buffer.getvalue()
        except (NotImplementedError, AttributeError, TypeError):
            raise NotImplementedError(f"{self.__class__.__name__} does not support rendering to bytes.") from None

    def _prepare_metadata(self, metadata: Union[Mapping[str, Any], "DocumentMetadata", None]) -> Dict[str, Any]:
        """Normalize and filter metadata according to the renderer policy."""
        return prepare_metadata_for_render(metadata, self.metadata_policy)

    @staticmethod
    def _compute_table_columns(rows: list[TableRow]) -> int:
        """Compute the maximum number of columns needed for a table.

        Parameters
        ----------
        rows : list[TableRow]
            All table rows (including header)

        Returns
        -------
        int
            Maximum column count accounting for colspan

        """
        max_cols = 0
        for row in rows:
            col_count = sum(cell.colspan for cell in row.cells)
            max_cols = max(max_cols, col_count)
        return max_cols

    @staticmethod
    def _validate_options_type(options: BaseRendererOptions | None, expected_type: type, renderer_name: str) -> None:
        """Validate that options are of the correct type for this parser.

        Parameters
        ----------
        options : BaseParserOptions or None
            The options object to validate
        expected_type : type
            The expected options class type
        renderer_name : str
            Name of the parser (for error messages)

        Raises
        ------
        InvalidOptionsError
            If options are not None and not an instance of expected_type

        """
        if options is not None and not isinstance(options, expected_type):
            raise InvalidOptionsError(
                converter_name=renderer_name,
                expected_type=expected_type,
                received_type=type(options),
            )

    @staticmethod
    def write_text_output(text: str, output: Union[str, Path, IO[bytes], IO[str]]) -> None:
        """Write text output to file or IO stream.

        Helper method to handle text output writing for text-based renderers.
        Centralizes the logic for writing to different output destinations,
        automatically handling both text and binary streams.

        Parameters
        ----------
        text : str
            Rendered text to write
        output : str, Path, IO[bytes], or IO[str]
            Output destination. Can be:
            - File path (str or Path)
            - File-like object in binary mode (IO[bytes])
            - File-like object in text mode (IO[str])

        Raises
        ------
        IOError
            If output cannot be written
        TypeError
            If output type is not supported

        Examples
        --------
        Write to file:
            >>> from all2md.renderers.base import BaseRenderer
            >>> BaseRenderer.write_text_output("# Hello", "output.md")

        Write to BytesIO:
            >>> from io import BytesIO
            >>> buffer = BytesIO()
            >>> BaseRenderer.write_text_output("# Hello", buffer)
            >>> print(buffer.getvalue())
            b'# Hello'

        Write to StringIO:
            >>> from io import StringIO
            >>> buffer = StringIO()
            >>> BaseRenderer.write_text_output("# Hello", buffer)
            >>> print(buffer.getvalue())
            # Hello

        """
        write_content(text, output)


class InlineContentMixin:
    """Mixin providing inline content rendering pattern for text-based renderers.

    This mixin provides the `_render_inline_content()` method, which is a
    common pattern used by text-based renderers to render inline nodes
    (like emphasis, strong, links) to a string by temporarily capturing
    their output.

    The implementing class must have:
    - A `_output` attribute (list[str]) for accumulating output
    - Visitor methods that append to `_output`

    Examples
    --------
    Using the mixin in a renderer:

        >>> from all2md.renderers.base import BaseRenderer, InlineContentMixin
        >>> from all2md.ast.visitors import NodeVisitor
        >>> from all2md.options.base import BaseRendererOptions
        >>>
        >>> class MyRenderer(NodeVisitor, InlineContentMixin, BaseRenderer):
        ...     def __init__(self, options=None):
        ...         BaseRenderer.__init__(self, options or BaseRendererOptions())
        ...         self._output = []
        ...
        ...     def visit_emphasis(self, node):
        ...         content = self._render_inline_content(node.content)
        ...         self._output.append(f"*{content}*")

    """

    _output: list[str]  # Type hint for the required attribute

    def _render_inline_content(self, content: list[Node]) -> str:
        """Render a list of inline nodes to text.

        This method temporarily captures the output from rendering inline
        nodes and returns it as a string. This is useful for rendering
        nested inline elements (like emphasis within a link).

        Parameters
        ----------
        content : list of Node
            Inline nodes to render

        Returns
        -------
        str
            Rendered inline content as a string

        """
        # Save current output state
        saved_output = self._output
        self._output = []

        # Render inline nodes
        for node in content:
            node.accept(self)

        # Capture result and restore output state
        result = "".join(self._output)
        self._output = saved_output
        return result
