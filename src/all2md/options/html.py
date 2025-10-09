#  Copyright (c) 2025 Tom Villani, Ph.D.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from all2md.options.base import BaseParserOptions, BaseRendererOptions
from all2md.constants import DEFAULT_EXTRACT_TITLE, DEFAULT_CONVERT_NBSP, DEFAULT_STRIP_DANGEROUS_ELEMENTS, \
    DEFAULT_TABLE_ALIGNMENT_AUTO_DETECT, DEFAULT_PRESERVE_NESTED_STRUCTURE
from all2md.options import NetworkFetchOptions
from all2md.options.common import LocalFileAccessOptions


# src/all2md/options/html.py
@dataclass(frozen=True)
class HtmlRendererOptions(BaseRendererOptions):
    """Configuration options for rendering AST to HTML format.

    This dataclass contains settings specific to HTML generation,
    including document structure, styling, and feature toggles.

    Parameters
    ----------
    standalone : bool, default True
        Generate complete HTML document with <html>, <head>, <body> tags.
        If False, generates only the content fragment.
    css_style : {"inline", "embedded", "external", "none"}, default "embedded"
        How to include CSS styles:
        - "inline": Add style attributes to elements
        - "embedded": Include <style> block in <head>
        - "external": Reference external CSS file
        - "none": No styling
    css_file : str or None, default None
        Path to external CSS file (used when css_style="external").
    template : str or None, default None
        Path to custom Jinja2 template file. If None, uses built-in template.
    include_toc : bool, default False
        Generate table of contents from headings.
    syntax_highlighting : bool, default True
        Add language classes to code blocks for syntax highlighting.
    escape_html : bool, default True
        Escape HTML special characters in text content.
    math_renderer : {"mathjax", "katex", "none"}, default "mathjax"
        Math rendering library to use for MathML/LaTeX math:
        - "mathjax": Include MathJax CDN script
        - "katex": Include KaTeX CDN script
        - "none": Render math as plain text

    """

    standalone: bool = field(
        default=True,
        metadata={
            "help": "Generate complete HTML document (vs content fragment)",
            "cli_name": "no-standalone"
        }
    )
    css_style: Literal["inline", "embedded", "external", "none"] = field(
        default="embedded",
        metadata={
            "help": "CSS inclusion method: inline, embedded, external, or none",
            "choices": ["inline", "embedded", "external", "none"]
        }
    )
    css_file: str | None = field(
        default=None,
        metadata={"help": "Path to external CSS file (when css_style='external')"}
    )
    template: str | None = field(
        default=None,
        metadata={"help": "Path to custom Jinja2 template (None = use built-in)"}
    )
    include_toc: bool = field(
        default=False,
        metadata={"help": "Generate table of contents from headings"}
    )
    syntax_highlighting: bool = field(
        default=True,
        metadata={
            "help": "Add language classes for syntax highlighting",
            "cli_name": "no-syntax-highlighting"
        }
    )
    escape_html: bool = field(
        default=True,
        metadata={
            "help": "Escape HTML special characters in text",
            "cli_name": "no-escape-html"
        }
    )
    math_renderer: Literal["mathjax", "katex", "none"] = field(
        default="mathjax",
        metadata={
            "help": "Math rendering library: mathjax, katex, or none",
            "choices": ["mathjax", "katex", "none"]
        }
    )


@dataclass(frozen=True)
class HtmlOptions(BaseParserOptions):
    """Configuration options for HTML-to-Markdown conversion.

    This dataclass contains settings specific to HTML document processing,
    including heading styles, title extraction, image handling, content
    sanitization, and advanced formatting options.

    Parameters
    ----------
    extract_title : bool, default False
        Whether to extract and use the HTML <title> element.
    convert_nbsp : bool, default False
        Whether to convert non-breaking spaces (&nbsp;) to regular spaces in the output.
    strip_dangerous_elements : bool, default False
        Whether to remove potentially dangerous HTML elements (script, style, etc.).
    detect_table_alignment : bool, default True
        Whether to automatically detect table column alignment from CSS/attributes.
    preserve_nested_structure : bool, default True
        Whether to maintain proper nesting for blockquotes and other elements.

    Examples
    --------
    Convert and extract page title:
        >>> options = HtmlOptions(extract_title=True)

    Convert with content sanitization:
        >>> options = HtmlOptions(strip_dangerous_elements=True, convert_nbsp=True)

    """

    extract_title: bool = field(
        default=DEFAULT_EXTRACT_TITLE,
        metadata={"help": "Extract and use HTML <title> element as main heading"}
    )
    convert_nbsp: bool = field(
        default=DEFAULT_CONVERT_NBSP,
        metadata={"help": "Convert non-breaking spaces (&nbsp;) to regular spaces"}
    )
    strip_dangerous_elements: bool = field(
        default=DEFAULT_STRIP_DANGEROUS_ELEMENTS,
        metadata={"help": "Remove potentially dangerous HTML elements (script, style, etc.)"}
    )
    detect_table_alignment: bool = field(
        default=DEFAULT_TABLE_ALIGNMENT_AUTO_DETECT,
        metadata={
            "help": "Automatically detect table column alignment from CSS/attributes",
            "cli_name": "no-detect-table-alignment"  # default=True, use --no-*
        }
    )

    # Network security options
    network: NetworkFetchOptions = field(
        default_factory=NetworkFetchOptions,
        metadata={
            "help": "Network security settings for remote resource fetching",
            "exclude_from_cli": True  # Handled via flattened fields
        }
    )

    # Local file access options
    local_files: LocalFileAccessOptions = field(
        default_factory=LocalFileAccessOptions,
        metadata={
            "help": "Local file access security settings",
            "exclude_from_cli": True  # Handled via flattened fields
        }
    )

    preserve_nested_structure: bool = field(
        default=DEFAULT_PRESERVE_NESTED_STRUCTURE,
        metadata={
            "help": "Maintain proper nesting for blockquotes and other elements",
            "cli_name": "no-preserve-nested-structure"  # default=True, use --no-*
        }
    )

    # Advanced HTML processing options
    strip_comments: bool = field(
        default=True,
        metadata={
            "help": "Remove HTML comments from output",
            "cli_name": "no-strip-comments"
        },
    )
    collapse_whitespace: bool = field(
        default=True,
        metadata={
            "help": "Collapse multiple spaces/newlines into single spaces",
            "cli_name": "no-collapse-whitespace"
        }
    )
    br_handling: str = field(
        default="newline",
        metadata={"help": "How to handle <br> tags: 'newline' or 'space'"}
    )
    allowed_elements: tuple[str, ...] | None = field(
        default=None,
        metadata={
            "help": "Whitelist of allowed HTML elements (if set, only these are processed)",
            "action": "append"
        }
    )
    allowed_attributes: tuple[str, ...] | None = field(
        default=None,
        metadata={
            "help": "Whitelist of allowed HTML attributes (if set, only these are processed)",
            "action": "append"
        }
    )
    figure_rendering: str = field(
        default="blockquote",
        metadata={
            "help": "How to render <figure> elements: blockquote, image_with_caption, html",
            "choices": ["blockquote", "image_with_caption", "html"]
        }
    )
    details_rendering: str = field(
        default="blockquote",
        metadata={
            "help": "How to render <details>/<summary> elements: blockquote, html, ignore",
            "choices": ["blockquote", "html", "ignore"]
        }
    )
    extract_microdata: bool = field(
        default=True,
        metadata={
            "help": "Extract microdata and structured data to metadata",
            "cli_name": "no-extract-microdata"
        }
    )
