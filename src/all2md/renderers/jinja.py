#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Jinja2 template-based rendering from AST.

This module provides a generic Jinja2 template-based renderer that allows users
to define custom output formats using templates. Templates have full access to
the document AST and can produce any text-based format.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Callable, Union, cast

from all2md.renderers.html import HtmlRenderer
from all2md.renderers.markdown import MarkdownRenderer
from all2md.renderers.plaintext import PlainTextRenderer

if TYPE_CHECKING:
    from jinja2 import Environment, Template

from all2md.ast import Document
from all2md.ast.nodes import (
    FootnoteDefinition,
    Heading,
    Image,
    Link,
    Node,
)
from all2md.ast.serialization import ast_to_dict
from all2md.constants import DEPS_JINJA
from all2md.converter_metadata import ConverterMetadata
from all2md.options.jinja import JinjaRendererOptions
from all2md.renderers.base import BaseRenderer
from all2md.utils.decorators import requires_dependencies
from all2md.utils.escape import (
    escape_html_entities,
    escape_markdown_context_aware,
)

logger = logging.getLogger(__name__)


# Escape functions for template filters
def escape_xml(text: str) -> str:
    """Escape text for XML/HTML output.

    Parameters
    ----------
    text : str
        Text to escape

    Returns
    -------
    str
        XML-escaped text

    """
    if not text:
        return text
    return escape_html_entities(text)


def escape_html(text: str) -> str:
    """Escape text for HTML output (alias for escape_xml).

    Parameters
    ----------
    text : str
        Text to escape

    Returns
    -------
    str
        HTML-escaped text

    """
    return escape_xml(text)


def escape_latex(text: str) -> str:
    r"""Escape text for LaTeX output.

    Parameters
    ----------
    text : str
        Text to escape

    Returns
    -------
    str
        LaTeX-escaped text

    """
    if not text:
        return text

    # LaTeX special characters: \ { } $ & # ^ _ % ~
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
        "&": r"\&",
        "#": r"\#",
        "^": r"\^{}",
        "_": r"\_",
        "%": r"\%",
        "~": r"\textasciitilde{}",
    }

    result = text
    # Replace backslash first to avoid double-escaping
    for char, escaped in replacements.items():
        result = result.replace(char, escaped)

    return result


def escape_yaml(text: str) -> str:
    """Escape text for YAML string values.

    Parameters
    ----------
    text : str
        Text to escape

    Returns
    -------
    str
        YAML-escaped text (returns quoted string if needed)

    """
    if not text:
        return '""'

    # Check if we need to quote the string
    needs_quotes = any(
        [
            text.startswith((" ", "\t")),
            text.endswith((" ", "\t")),
            ":" in text,
            "#" in text,
            "[" in text,
            "]" in text,
            "{" in text,
            "}" in text,
            "," in text,
            "&" in text,
            "*" in text,
            "!" in text,
            "|" in text,
            ">" in text,
            "'" in text,
            '"' in text,
            "%" in text,
            "@" in text,
            "`" in text,
            "\n" in text,
            "\r" in text,
        ]
    )

    if needs_quotes:
        # Use double quotes and escape internal quotes
        escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
        return f'"{escaped}"'

    return text


def escape_markdown(text: str, context: str = "text") -> str:
    r"""Escape text for Markdown output.

    Parameters
    ----------
    text : str
        Text to escape
    context : {"text", "table", "link", "image_alt"}, default = "text"
        Context where text will be used

    Returns
    -------
    str
        Markdown-escaped text

    """
    if not text:
        return text
    return escape_markdown_context_aware(text, context)


# AST traversal helper functions
def _extract_text_from_nodes(nodes: list[Node]) -> str:
    """Extract plain text from a list of nodes.

    Parameters
    ----------
    nodes : list[Node]
        List of nodes to extract text from

    Returns
    -------
    str
        Extracted text

    """
    text_parts = []
    for node in nodes:
        if hasattr(node, "content"):
            if isinstance(node.content, str):
                text_parts.append(node.content)
            elif isinstance(node.content, list):
                text_parts.append(_extract_text_from_nodes(node.content))
    return "".join(text_parts)


def _walk_nodes(node: Node, predicate: Callable[[Node], bool]) -> list[Node]:
    """Walk AST and collect nodes matching predicate.

    Parameters
    ----------
    node : Node
        Root node to start walking from
    predicate : Callable[[Node], bool]
        Function that takes a node and returns True if it should be collected

    Returns
    -------
    list[Node]
        List of matching nodes

    """
    result = []

    if predicate(node):
        result.append(node)

    # Walk children
    if hasattr(node, "children") and isinstance(node.children, list):
        for child in node.children:
            if isinstance(child, Node):
                result.extend(_walk_nodes(child, predicate))

    # Walk content if it's a list
    if hasattr(node, "content") and isinstance(node.content, list):
        for child in node.content:
            if isinstance(child, Node):
                result.extend(_walk_nodes(child, predicate))

    # Walk table rows and cells
    if hasattr(node, "rows") and isinstance(node.rows, list):
        for row in node.rows:
            if isinstance(row, Node):
                result.extend(_walk_nodes(row, predicate))

    if hasattr(node, "cells") and isinstance(node.cells, list):
        for cell in node.cells:
            if isinstance(cell, Node):
                result.extend(_walk_nodes(cell, predicate))

    # Walk list items
    if hasattr(node, "items") and isinstance(node.items, list):
        for item in node.items:
            if isinstance(item, Node):
                result.extend(_walk_nodes(item, predicate))

    return result


def get_all_headings(document: Document) -> list[dict[str, Any]]:
    """Extract all headings from document.

    Parameters
    ----------
    document : Document
        Document to extract headings from

    Returns
    -------
    list[dict[str, Any]]
        List of heading dictionaries with keys: level, text, node

    """
    headings = _walk_nodes(document, lambda n: isinstance(n, Heading))
    return [
        {"level": cast(Heading, h).level, "text": _extract_text_from_nodes(cast(Heading, h).content), "node": h}
        for h in headings
    ]


def get_all_links(document: Document) -> list[dict[str, Any]]:
    """Extract all links from document.

    Parameters
    ----------
    document : Document
        Document to extract links from

    Returns
    -------
    list[dict[str, Any]]
        List of link dictionaries with keys: url, title, text, node

    """
    links = _walk_nodes(document, lambda n: isinstance(n, Link))
    return [
        {
            "url": cast(Link, link).url,
            "title": cast(Link, link).title,
            "text": _extract_text_from_nodes(cast(Link, link).content),
            "node": link,
        }
        for link in links
    ]


def get_all_images(document: Document) -> list[dict[str, Any]]:
    """Extract all images from document.

    Parameters
    ----------
    document : Document
        Document to extract images from

    Returns
    -------
    list[dict[str, Any]]
        List of image dictionaries with keys: url, alt_text, title, width, height, node

    """
    images = _walk_nodes(document, lambda n: isinstance(n, Image))
    return [
        {
            "url": cast(Image, img).url,
            "alt_text": cast(Image, img).alt_text,
            "title": cast(Image, img).title,
            "width": cast(Image, img).width,
            "height": cast(Image, img).height,
            "node": img,
        }
        for img in images
    ]


def get_all_footnotes(document: Document) -> list[dict[str, Any]]:
    """Extract all footnote definitions from document.

    Parameters
    ----------
    document : Document
        Document to extract footnotes from

    Returns
    -------
    list[dict[str, Any]]
        List of footnote dictionaries with keys: identifier, node

    """
    footnotes = _walk_nodes(document, lambda n: isinstance(n, FootnoteDefinition))
    return [{"identifier": cast(FootnoteDefinition, fn).identifier, "node": fn} for fn in footnotes]


def find_nodes_by_type(document: Document, node_type: str) -> list[Node]:
    """Find all nodes of a specific type.

    Parameters
    ----------
    document : Document
        Document to search
    node_type : str
        Node type name (e.g., "Heading", "Paragraph", "CodeBlock")

    Returns
    -------
    list[Node]
        List of matching nodes

    """
    return _walk_nodes(document, lambda n: type(n).__name__ == node_type)


def node_type_name(node: Node | dict) -> str:
    """Get the type name of a node.

    Parameters
    ----------
    node : Node or dict
        Node object or dictionary representation

    Returns
    -------
    str
        Node type name

    """
    if isinstance(node, dict):
        return node.get("type", "Unknown")
    return type(node).__name__


class JinjaRenderer(BaseRenderer):
    """Render AST using Jinja2 templates.

    This renderer provides maximum flexibility by allowing users to define
    custom output formats using Jinja2 templates. Templates have full access
    to the document AST and can use helper filters and functions for common
    operations.

    Parameters
    ----------
    options : JinjaRendererOptions or None, default = None
        Jinja2 rendering options including template path and configuration

    Examples
    --------
    Render using a template file:
        >>> from all2md.renderers.jinja import JinjaRenderer
        >>> from all2md.options import JinjaRendererOptions
        >>> options = JinjaRendererOptions(
        ...     template_file="templates/docbook.xml.jinja2",
        ...     escape_strategy="xml"
        ... )
        >>> renderer = JinjaRenderer(options)
        >>> output = renderer.render_to_string(document)

    Render using an inline template:
        >>> template = "Title: {{ metadata.title }}"
        >>> options = JinjaRendererOptions(template_string=template)
        >>> renderer = JinjaRenderer(options)
        >>> output = renderer.render_to_string(document)

    """

    def __init__(self, options: JinjaRendererOptions | None = None):
        """Initialize the Jinja2 renderer with options."""
        BaseRenderer._validate_options_type(options, JinjaRendererOptions, "jinja")
        options = options or JinjaRendererOptions(template_string="{{ document }}")
        BaseRenderer.__init__(self, options)
        self.options: JinjaRendererOptions = options
        self._env: Environment | None = None
        self._template: Template | None = None

    def _get_escape_function(self) -> Callable[[str], str] | None:
        """Get the escape function based on escape_strategy.

        Returns
        -------
        Callable[[str], str] or None
            Escape function or None for no escaping

        """
        if self.options.escape_strategy == "xml" or self.options.escape_strategy == "html":
            return escape_xml
        elif self.options.escape_strategy == "latex":
            return escape_latex
        elif self.options.escape_strategy == "yaml":
            return escape_yaml
        elif self.options.escape_strategy == "markdown":
            return escape_markdown
        elif self.options.escape_strategy == "custom":
            return self.options.custom_escape_function
        else:
            return None

    def _reset_jinja_env(self) -> None:
        """Reset the jinja environment before use."""
        self._env = None
        self._template = None

    def _setup_jinja_env(self) -> None:
        """Set up the Jinja2 environment with custom filters and functions."""
        self._reset_jinja_env()

        from jinja2 import Environment, FileSystemLoader, StrictUndefined

        # Determine template directory
        template_dir = None
        if self.options.template_file:
            template_path = Path(self.options.template_file)
            template_dir = str(template_path.parent) if template_path.parent else "."
        if self.options.template_dir:
            template_dir = self.options.template_dir

        # Create environment (autoescape=False is intentional - we output Markdown, not HTML)
        if template_dir:
            loader = FileSystemLoader(template_dir)
            # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
            self._env = Environment(loader=loader, autoescape=False)  # nosec B701
        else:
            # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
            self._env = Environment(autoescape=False)  # nosec B701

        # Set undefined behavior
        if self.options.strict_undefined:
            self._env.undefined = StrictUndefined

        # Configure autoescape
        if self.options.autoescape:
            escape_func = self._get_escape_function()
            if escape_func:
                self._env.autoescape = True
                self._env.finalize = lambda x: escape_func(str(x)) if x is not None else ""

        # Add custom filters
        if self.options.enable_render_filter:
            self._env.filters["render"] = self._render_node_filter
            self._env.filters["render_inline"] = self._render_inline_filter

        if self.options.enable_escape_filters:
            self._env.filters["escape_xml"] = escape_xml
            self._env.filters["escape_html"] = escape_html
            self._env.filters["escape_latex"] = escape_latex
            self._env.filters["escape_yaml"] = escape_yaml
            self._env.filters["escape_markdown"] = escape_markdown

        self._env.filters["to_dict"] = ast_to_dict
        self._env.filters["node_type"] = node_type_name

        # Add custom functions
        if self.options.enable_traversal_helpers:
            self._env.globals["get_headings"] = get_all_headings
            self._env.globals["get_links"] = get_all_links
            self._env.globals["get_images"] = get_all_images
            self._env.globals["get_footnotes"] = get_all_footnotes
            self._env.globals["find_nodes"] = find_nodes_by_type

        # Load template
        if self.options.template_file:
            template_name = Path(self.options.template_file).name
            self._template = self._env.get_template(template_name)
        elif self.options.template_string:
            self._template = self._env.from_string(self.options.template_string)

    def _render_node_filter(self, node: Node | dict) -> str:
        """Jinja2 filter to render a node with default logic.

        Parameters
        ----------
        node : Node or dict
            Node to render (can be Node object or dict representation)

        Returns
        -------
        str
            Rendered node content

        """
        # Convert dict to Node if needed
        if isinstance(node, dict):
            # For dict nodes, we can't easily reconstruct the full Node object
            # So we'll render a simple representation
            node_type = node.get("type", "Unknown")
            if node_type == "Text":
                return node.get("content", "")
            elif node_type == "Code":
                return f"`{node.get('content', '')}`"
            else:
                # For complex nodes, just return empty string
                # Users should access the node directly in template
                return ""

        # At this point, node must be a Node object due to type narrowing

        # Use appropriate renderer based on default_render_format
        format_type = self.options.default_render_format

        # Create a minimal document with just this node

        temp_doc = Document(children=[node] if hasattr(node, "accept") else [])

        try:
            if format_type == "markdown":
                return MarkdownRenderer().render_to_string(temp_doc).strip()
            elif format_type == "plain":
                return PlainTextRenderer().render_to_string(temp_doc).strip()
            else:  # format_type == "html"
                return HtmlRenderer().render_to_string(temp_doc).strip()
        except Exception as e:
            logger.warning(f"Failed to render node {type(node).__name__}: {e}")
            return ""

    def _render_inline_filter(self, content: list) -> str:
        """Jinja2 filter to render inline content.

        Parameters
        ----------
        content : list
            List of inline nodes

        Returns
        -------
        str
            Rendered inline content

        """
        if not content:
            return ""

        parts = []
        for item in content:
            if isinstance(item, dict):
                # Dict representation
                if item.get("type") == "Text":
                    parts.append(item.get("content", ""))
                else:
                    parts.append(self._render_node_filter(item))
            elif isinstance(item, Node):
                parts.append(self._render_node_filter(item))
            else:
                parts.append(str(item))

        return "".join(parts)

    def _build_context(self, document: Document) -> dict[str, Any]:
        """Build the template context from document.

        Parameters
        ----------
        document : Document
            Document to build context from

        Returns
        -------
        dict[str, Any]
            Template context dictionary

        """
        metadata = document.metadata or {}
        context = {
            "document": document,
            "ast": ast_to_dict(document),
            "metadata": metadata,
            "title": metadata.get("title", ""),
        }

        # Add traversal helpers if enabled
        if self.options.enable_traversal_helpers:
            context["headings"] = get_all_headings(document)
            context["links"] = get_all_links(document)
            context["images"] = get_all_images(document)
            context["footnotes"] = get_all_footnotes(document)

        # Add extra context
        if self.options.extra_context:
            context.update(self.options.extra_context)

        return context

    @requires_dependencies("jinja", DEPS_JINJA)
    def render_to_string(self, document: Document) -> str:
        """Render document to string using Jinja2 template.

        Parameters
        ----------
        document : Document
            Document to render

        Returns
        -------
        str
            Rendered output

        """
        self._setup_jinja_env()
        if not self._template:
            raise ValueError("No template loaded")

        context = self._build_context(document)
        rendered = self._template.render(**context)
        return rendered

    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render document to file or file-like object.

        Parameters
        ----------
        doc : Document
            Document to render
        output : str, Path, or IO[bytes]
            Output destination

        """
        text = self.render_to_string(doc)
        self.write_text_output(text, output)


# Converter Metadata Registration
# =============================================================================

CONVERTER_METADATA = ConverterMetadata(
    format_name="jinja",
    extensions=[],  # No specific extension - used programmatically
    mime_types=[],
    magic_bytes=[],
    parser_class=None,  # No parser - this is renderer-only
    renderer_class=JinjaRenderer,
    renders_as_string=True,
    parser_required_packages=[],
    renderer_required_packages=[("jinja2", "jinja2", ">=3.1.0")],
    optional_packages=[],
    import_error_message="Jinja2 template renderer requires jinja2 package. Install with: pip install jinja2>=3.0.0",
    parser_options_class=None,
    renderer_options_class=JinjaRendererOptions,
    description="Generic Jinja2 template-based renderer for custom output formats",
    priority=10,
)
