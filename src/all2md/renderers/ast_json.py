#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/ast_json.py
"""JSON AST rendering from Document.

This module provides the AstJsonRenderer class which converts Document
nodes to JSON-serialized AST format. This is useful for:
- Debugging and inspecting document structure
- Programmatic document generation and manipulation
- Interoperability with other tools and languages
- Testing transforms with JSON fixtures

The renderer uses the ast.serialization module for conversion.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import IO, Union

from all2md.ast import Document
from all2md.ast.serialization import ast_to_dict
from all2md.options.ast_json import AstJsonRendererOptions
from all2md.renderers.base import BaseRenderer


class AstJsonRenderer(BaseRenderer):
    """Render Document nodes to JSON AST format.

    This class serializes AST Document nodes to JSON format using
    the ast.serialization module. The output includes schema versioning
    and preserves all node structure and metadata.

    Parameters
    ----------
    options : AstJsonRendererOptions or None, default = None
        JSON rendering options

    Examples
    --------
    Basic usage:
        >>> from all2md.ast import Document, Paragraph, Text
        >>> from all2md.renderers.ast_json import AstJsonRenderer
        >>> doc = Document(children=[
        ...     Paragraph(content=[Text(content="Hello, world!")])
        ... ])
        >>> renderer = AstJsonRenderer()
        >>> json_str = renderer.render_to_string(doc)
        >>> print(json_str)

    Compact JSON output:
        >>> from all2md.options.ast_json import AstJsonRendererOptions
        >>> renderer = AstJsonRenderer(AstJsonRendererOptions(indent=None))
        >>> json_str = renderer.render_to_string(doc)

    """

    def __init__(self, options: AstJsonRendererOptions | None = None):
        """Initialize the AST JSON renderer with options."""
        BaseRenderer._validate_options_type(options, AstJsonRendererOptions, "ast")
        options = options or AstJsonRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: AstJsonRendererOptions = options

    def render_to_string(self, document: Document) -> str:
        """Render a Document to JSON AST string.

        Parameters
        ----------
        document : Document
            The document node to render

        Returns
        -------
        str
            JSON AST output

        Examples
        --------
        >>> from all2md.ast import Document
        >>> doc = Document(children=[])
        >>> renderer = AstJsonRenderer()
        >>> json_str = renderer.render_to_string(doc)

        """
        # Convert AST to dict
        node_dict = ast_to_dict(document)

        # Add schema version at root level
        versioned_dict = {"schema_version": 1, **node_dict}

        # Use json.dumps with options for more control
        return json.dumps(
            versioned_dict,
            indent=self.options.indent,
            ensure_ascii=self.options.ensure_ascii,
            sort_keys=self.options.sort_keys,
        )

    def render(self, doc: Document, output: Union[str, Path, IO[bytes], IO[str]]) -> None:
        """Render AST to JSON and write to output.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, IO[bytes], or IO[str]
            Output destination (file path or file-like object)

        """
        # Render to string and use write_text_output for consistent handling
        json_text = self.render_to_string(doc)
        self.write_text_output(json_text, output)
