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
from pathlib import Path
from typing import IO, Union

from all2md.ast import Document
from all2md.options import BaseRendererOptions


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

        >>> from all2md.renderers.base import BaseRenderer
        >>> from all2md.ast import Document
        >>> from all2md.options import BaseRendererOptions
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
        MarkdownConversionError
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
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support rendering to a string."
        )

    def render_to_bytes(self, doc: Document) -> bytes:
        """Render the AST to bytes (if applicable).

        This method is optional and should be implemented by renderers
        that produce binary output formats.

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

        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support rendering to bytes."
        )
