#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Configuration options for Jinja2 template-based rendering.

This module defines options for rendering AST documents using custom Jinja2
templates, enabling users to create arbitrary text-based output formats.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from all2md.constants import (
    DEFAULT_JINJA_AUTOESCAPE,
    DEFAULT_JINJA_ENABLE_ESCAPE_FILTERS,
    DEFAULT_JINJA_ENABLE_RENDER_FILTER,
    DEFAULT_JINJA_ENABLE_TRAVERSAL_HELPERS,
    DEFAULT_JINJA_ESCAPE_STRATEGY,
    DEFAULT_JINJA_RENDER_FORMAT,
    DEFAULT_JINJA_STRICT_UNDEFINED,
    JinjaEscapeStrategy,
    JinjaRenderFormat,
)
from all2md.options.base import BaseRendererOptions


@dataclass(frozen=True)
class JinjaRendererOptions(BaseRendererOptions):
    """Configuration options for Jinja2 template-based rendering.

    This dataclass contains settings for rendering AST documents using custom
    Jinja2 templates. Templates have full access to the document AST and can
    produce any text-based output format (XML, YAML, custom markup, etc.).

    Parameters
    ----------
    template_file : str or None, default None
        Path to Jinja2 template file. Either template_file or template_string
        must be provided.
    template_string : str or None, default None
        Inline Jinja2 template as a string. Either template_file or
        template_string must be provided. If both are provided, template_file
        takes precedence.
    template_dir : str or None, default None
        Directory for template includes and extends. If None and template_file
        is provided, uses the directory containing template_file. Required when
        using template_string with includes/extends.
    escape_strategy : {"xml", "html", "latex", "yaml", "markdown", "none", "custom"} or None, default None
        Default escaping strategy for the output format:
        - "xml": XML/HTML entity escaping
        - "html": Same as xml
        - "latex": LaTeX special character escaping
        - "yaml": YAML string escaping
        - "markdown": Markdown special character escaping
        - "none": No escaping
        - "custom": Use custom_escape_function
        - None: No default strategy (templates must handle escaping explicitly)
        This affects the default ``|render`` filter behavior.
    custom_escape_function : Callable[[str], str] or None, default None
        Custom escape function when escape_strategy="custom".
        Function signature: (text: str) -> str
    autoescape : bool, default False
        Enable Jinja2 autoescape for the template environment. When True,
        uses the escape_strategy for automatic escaping. Default is False
        to give templates full control.
    enable_render_filter : bool, default True
        Enable the render filter for rendering nodes with default logic.
        When enabled, templates can use ``{{ node|render }}`` for convenience.
    enable_escape_filters : bool, default True
        Enable format-specific escape filters (escape_xml, escape_latex, etc.).
        When enabled, templates can use ``{{ text|escape_xml }}``.
    enable_traversal_helpers : bool, default True
        Enable AST traversal helper functions (get_headings, get_links, etc.).
        When enabled, templates can use ``{{ get_headings(document) }}``.
    default_render_format : {"markdown", "plain", "html"}, default "markdown"
        Default format for the render filter when no escape_strategy is set.
        Determines how nodes are rendered when using ``{{ node|render }}``.
    extra_context : dict[str, Any] or None, default None
        Additional context variables to make available in templates.
        These will be merged into the template context.
    strict_undefined : bool, default True
        Raise errors for undefined variables in templates (Jinja2 StrictUndefined).
        When False, undefined variables render as empty strings.

    Examples
    --------
    Render using a template file:
        >>> from all2md.options import JinjaRendererOptions
        >>> options = JinjaRendererOptions(
        ...     template_file="templates/docbook.xml.jinja2",
        ...     escape_strategy="xml"
        ... )

    Render using an inline template string:
        >>> template = '''
        ... <doc>
        ... {% for node in document.children -%}
        ...   {{ node|render }}
        ... {%- endfor %}
        ... </doc>
        ... '''
        >>> options = JinjaRendererOptions(
        ...     template_string=template,
        ...     escape_strategy="xml"
        ... )

    Use custom escape function:
        >>> def my_escape(text: str) -> str:
        ...     return text.replace("&", "&amp;")
        >>> options = JinjaRendererOptions(
        ...     template_file="custom.jinja2",
        ...     escape_strategy="custom",
        ...     custom_escape_function=my_escape
        ... )

    Add extra context variables:
        >>> options = JinjaRendererOptions(
        ...     template_file="report.jinja2",
        ...     extra_context={"version": "1.0", "author": "Tool"}
        ... )

    Notes
    -----
    Templates receive the following context:
    - document: The Document node (typed AST object)
    - ast: The document as a dictionary (template-friendly)
    - metadata: Document metadata dictionary
    - title: Document title (metadata.get("title", ""))
    - headings: List of all headings (if enable_traversal_helpers=True)
    - links: List of all links (if enable_traversal_helpers=True)
    - images: List of all images (if enable_traversal_helpers=True)
    - footnotes: List of all footnote definitions (if enable_traversal_helpers=True)
    - Any keys from extra_context

    Available filters (if enabled):
      - render: Render a node with default logic
      - render_inline: Render inline content
      - to_dict: Convert Node to dictionary
      - escape_xml, escape_html: XML/HTML escaping
      - escape_latex: LaTeX escaping
      - escape_yaml: YAML escaping
      - escape_markdown: Markdown escaping
      - node_type: Get node type name as string

    Available functions (if enabled):
    - get_headings(doc): Extract all heading nodes
    - get_links(doc): Extract all link nodes
    - get_images(doc): Extract all image nodes
    - get_footnotes(doc): Extract all footnote definitions
    - find_nodes(doc, node_type): Find all nodes of specified type
    - filter_nodes(doc, predicate): Filter nodes by custom predicate

    """

    template_file: str | None = field(
        default=None,
        metadata={
            "help": "Path to Jinja2 template file",
            "type": str,
            "importance": "core",
        },
    )

    template_string: str | None = field(
        default=None,
        metadata={
            "help": "Inline Jinja2 template string",
            "type": str,
            "importance": "core",
        },
    )

    template_dir: str | None = field(
        default=None,
        metadata={
            "help": "Directory for template includes/extends",
            "type": str,
            "importance": "advanced",
        },
    )

    escape_strategy: JinjaEscapeStrategy | None = field(
        default=DEFAULT_JINJA_ESCAPE_STRATEGY,
        metadata={
            "help": "Default escaping strategy for output format",
            "choices": ["xml", "html", "latex", "yaml", "markdown", "none", "custom"],
            "importance": "core",
        },
    )

    custom_escape_function: Callable[[str], str] | None = field(
        default=None,
        metadata={
            "help": "Custom escape function (for escape_strategy='custom')",
            "type": "callable",
            "importance": "advanced",
        },
    )

    autoescape: bool = field(
        default=DEFAULT_JINJA_AUTOESCAPE,
        metadata={
            "help": "Enable Jinja2 autoescape using escape_strategy",
            "importance": "core",
        },
    )

    enable_render_filter: bool = field(
        default=DEFAULT_JINJA_ENABLE_RENDER_FILTER,
        metadata={
            "help": "Enable |render filter for nodes",
            "cli_name": "no-enable-render-filter",
            "importance": "core",
        },
    )

    enable_escape_filters: bool = field(
        default=DEFAULT_JINJA_ENABLE_ESCAPE_FILTERS,
        metadata={
            "help": "Enable escape filters (escape_xml, etc.)",
            "cli_name": "no-enable-escape-filters",
            "importance": "core",
        },
    )

    enable_traversal_helpers: bool = field(
        default=DEFAULT_JINJA_ENABLE_TRAVERSAL_HELPERS,
        metadata={
            "help": "Enable AST traversal helpers (get_headings, etc.)",
            "cli_name": "no-enable-traversal-helpers",
            "importance": "core",
        },
    )

    default_render_format: JinjaRenderFormat = field(
        default=DEFAULT_JINJA_RENDER_FORMAT,
        metadata={
            "help": "Default format for |render filter",
            "choices": ["markdown", "plain", "html"],
            "importance": "advanced",
        },
    )

    extra_context: dict[str, Any] | None = field(
        default=None,
        metadata={
            "help": "Additional template context variables",
            "type": dict,
            "importance": "advanced",
        },
    )

    strict_undefined: bool = field(
        default=DEFAULT_JINJA_STRICT_UNDEFINED,
        metadata={
            "help": "Raise errors for undefined template variables",
            "cli_name": "no-strict-undefined",
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate configuration options.

        Raises
        ------
        ValueError
            If neither template_file nor template_string is provided,
            or if escape_strategy is 'custom' but custom_escape_function is None.

        """
        super().__post_init__()

        # Check that at least one template source is provided
        if self.template_file is None and self.template_string is None:
            raise ValueError("Either template_file or template_string must be provided")

        # Validate custom escape function
        if self.escape_strategy == "custom" and self.custom_escape_function is None:
            raise ValueError("custom_escape_function must be provided when escape_strategy='custom'")

        # Validate that custom_escape_function is only used with custom strategy
        if self.custom_escape_function is not None and self.escape_strategy != "custom":
            raise ValueError("custom_escape_function can only be used with escape_strategy='custom'")
