#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/asciidoc.py
"""Configuration options for AsciiDoc parsing and rendering.

This module defines options classes for AsciiDoc format conversion,
supporting both AST parsing and rendering operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_ASCIIDOC_ATTRIBUTE_MISSING_POLICY,
    DEFAULT_ASCIIDOC_COMMENT_MODE,
    DEFAULT_ASCIIDOC_HONOR_HARD_BREAKS,
    DEFAULT_ASCIIDOC_LINE_LENGTH,
    DEFAULT_ASCIIDOC_LIST_INDENT,
    DEFAULT_ASCIIDOC_PARSE_ADMONITIONS,
    DEFAULT_ASCIIDOC_PARSE_ATTRIBUTES,
    DEFAULT_ASCIIDOC_PARSE_INCLUDES,
    DEFAULT_ASCIIDOC_PARSE_TABLE_SPANS,
    DEFAULT_ASCIIDOC_RESOLVE_ATTRIBUTE_REFS,
    DEFAULT_ASCIIDOC_STRICT_MODE,
    DEFAULT_ASCIIDOC_STRIP_COMMENTS,
    DEFAULT_ASCIIDOC_SUPPORT_UNCONSTRAINED_FORMATTING,
    DEFAULT_ASCIIDOC_TABLE_HEADER_DETECTION,
    DEFAULT_ASCIIDOC_USE_ATTRIBUTES,
    DEFAULT_HTML_PASSTHROUGH_MODE,
    HTML_PASSTHROUGH_MODES,
    AsciiDocCommentMode,
    AttributeMissingPolicy,
    HtmlPassthroughMode,
    TableHeaderDetection,
)
from all2md.options.base import BaseParserOptions, BaseRendererOptions


@dataclass(frozen=True)
class AsciiDocOptions(BaseParserOptions):
    """Configuration options for AsciiDoc-to-AST parsing.

    This dataclass contains settings specific to parsing AsciiDoc documents
    into AST representation using a custom parser.

    Parameters
    ----------
    parse_attributes : bool, default True
        Whether to parse document attributes (:name: value syntax).
        When True, attributes are collected and can be referenced.
    parse_admonitions : bool, default True
        Whether to parse admonition blocks ([NOTE], [IMPORTANT], etc.).
        When True, admonitions are converted to appropriate AST nodes.
    parse_includes : bool, default False
        Whether to process include directives (include::file[]).
        SECURITY: Disabled by default to prevent file system access.
    strict_mode : bool, default False
        Whether to raise errors on invalid AsciiDoc syntax.
        When False, attempts to recover gracefully.
    resolve_attribute_refs : bool, default True
        Whether to resolve attribute references ({name}) in text.
        When True, {name} is replaced with attribute value.
    strip_comments : bool, default False
        Whether to strip comments (// syntax) instead of preserving as Comment nodes.
        When False, comments are preserved as Comment AST nodes with comment_type='asciidoc'.

    """

    parse_attributes: bool = field(
        default=DEFAULT_ASCIIDOC_PARSE_ATTRIBUTES,
        metadata={"help": "Parse document attributes", "cli_name": "no-parse-attributes", "importance": "core"},
    )
    parse_admonitions: bool = field(
        default=DEFAULT_ASCIIDOC_PARSE_ADMONITIONS,
        metadata={
            "help": "Parse admonition blocks ([NOTE], [IMPORTANT], etc.)",
            "cli_name": "no-parse-admonitions",
            "importance": "core",
        },
    )
    parse_includes: bool = field(
        default=DEFAULT_ASCIIDOC_PARSE_INCLUDES,
        metadata={
            "help": "Process include directives (SECURITY: disabled by default)",
            "cli_name": "parse-includes",
            "importance": "security",
        },
    )
    strict_mode: bool = field(
        default=DEFAULT_ASCIIDOC_STRICT_MODE,
        metadata={"help": "Raise errors on invalid AsciiDoc syntax", "importance": "advanced"},
    )
    resolve_attribute_refs: bool = field(
        default=DEFAULT_ASCIIDOC_RESOLVE_ATTRIBUTE_REFS,
        metadata={
            "help": "Resolve attribute references ({name}) in text",
            "cli_name": "no-resolve-attributes",
            "importance": "advanced",
        },
    )
    attribute_missing_policy: AttributeMissingPolicy = field(
        default=DEFAULT_ASCIIDOC_ATTRIBUTE_MISSING_POLICY,
        metadata={
            "help": "Policy for undefined attribute references: keep literal, use blank, or warn",
            "choices": ["keep", "blank", "warn"],
            "importance": "advanced",
        },
    )
    support_unconstrained_formatting: bool = field(
        default=DEFAULT_ASCIIDOC_SUPPORT_UNCONSTRAINED_FORMATTING,
        metadata={
            "help": "Support unconstrained formatting (e.g., **b**old for mid-word)",
            "cli_name": "no-unconstrained-formatting",
            "importance": "advanced",
        },
    )
    table_header_detection: TableHeaderDetection = field(
        default=DEFAULT_ASCIIDOC_TABLE_HEADER_DETECTION,
        metadata={
            "help": "How to detect table headers: always first-row, use block attributes, or auto-detect",
            "choices": ["first-row", "attribute-based", "auto"],
            "importance": "core",
        },
    )
    honor_hard_breaks: bool = field(
        default=DEFAULT_ASCIIDOC_HONOR_HARD_BREAKS,
        metadata={
            "help": "Honor explicit line breaks (trailing space + plus)",
            "cli_name": "no-honor-hard-breaks",
            "importance": "advanced",
        },
    )
    parse_table_spans: bool = field(
        default=DEFAULT_ASCIIDOC_PARSE_TABLE_SPANS,
        metadata={
            "help": "Parse table colspan/rowspan syntax (e.g., 2+|cell)",
            "cli_name": "no-parse-table-spans",
            "importance": "advanced",
        },
    )
    strip_comments: bool = field(
        default=DEFAULT_ASCIIDOC_STRIP_COMMENTS,
        metadata={
            "help": "Strip comments (// syntax) instead of preserving as Comment nodes",
            "cli_name": "strip-comments",
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()


@dataclass(frozen=True)
class AsciiDocRendererOptions(BaseRendererOptions):
    """Configuration options for AST-to-AsciiDoc rendering.

    This dataclass contains settings for rendering AST documents as
    AsciiDoc output.

    Parameters
    ----------
    list_indent : int, default 2
        Number of spaces for nested list indentation.
    use_attributes : bool, default True
        Whether to include document attributes in output.
        When True, renders :name: value attributes at document start.
    line_length : int, default 0
        Target line length for wrapping text (0 = no wrapping).
    html_passthrough_mode : {"pass-through", "escape", "drop", "sanitize"}, default "pass-through"
        How to handle HTMLBlock and HTMLInline nodes:
        - "pass-through": Pass through unchanged (use only with trusted content)
        - "escape": HTML-escape the content
        - "drop": Remove HTML content entirely
        - "sanitize": Remove dangerous elements/attributes (requires bleach for best results)
    comment_mode : {"comment", "note", "ignore"}, default "comment"
        How to render Comment and CommentInline AST nodes:
        - "comment": Render as AsciiDoc comments (// Comment text)
        - "note": Render as NOTE admonition blocks (visible annotations)
        - "ignore": Skip comment nodes entirely
        This is the sole option controlling comment rendering behavior.

    """

    list_indent: int = field(
        default=DEFAULT_ASCIIDOC_LIST_INDENT,
        metadata={"help": "Spaces for nested list indentation", "type": int},
    )
    use_attributes: bool = field(
        default=DEFAULT_ASCIIDOC_USE_ATTRIBUTES,
        metadata={
            "help": "Include document attributes in output",
            "cli_name": "no-use-attributes",
            "importance": "core",
        },
    )
    line_length: int = field(
        default=DEFAULT_ASCIIDOC_LINE_LENGTH,
        metadata={"help": "Target line length for wrapping (0 = no wrapping)", "type": int, "importance": "core"},
    )
    html_passthrough_mode: HtmlPassthroughMode = field(
        default=DEFAULT_HTML_PASSTHROUGH_MODE,
        metadata={
            "help": "How to handle raw HTML content: pass-through, escape, drop, or sanitize",
            "choices": HTML_PASSTHROUGH_MODES,
            "importance": "security",
        },
    )
    comment_mode: AsciiDocCommentMode = field(
        default=DEFAULT_ASCIIDOC_COMMENT_MODE,
        metadata={
            "help": "How to render Comment and CommentInline nodes: "
            "comment (// comments), note (NOTE admonitions), "
            "ignore (skip comment nodes entirely). Controls presentation of source document comments.",
            "choices": ["comment", "note", "ignore"],
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges for AsciiDoc renderer options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        # Call parent validation
        super().__post_init__()

        # Validate non-negative indentation
        if self.list_indent < 0:
            raise ValueError(f"list_indent must be non-negative, got {self.list_indent}")

        # Validate non-negative line length
        if self.line_length < 0:
            raise ValueError(f"line_length must be non-negative, got {self.line_length}")
