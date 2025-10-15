#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/asciidoc.py
"""Configuration options for AsciiDoc parsing and rendering.

This module defines options classes for AsciiDoc format conversion,
supporting both AST parsing and rendering operations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from all2md.constants import HtmlPassthroughMode, DEFAULT_HTML_PASSTHROUGH_MODE, HTML_PASSTHROUGH_MODES
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

    """

    parse_attributes: bool = field(
        default=True,
        metadata={
            "help": "Parse document attributes",
            "cli_name": "no-parse-attributes",
            "importance": "core"
        }
    )
    parse_admonitions: bool = field(
        default=True,
        metadata={
            "help": "Parse admonition blocks ([NOTE], [IMPORTANT], etc.)",
            "cli_name": "no-parse-admonitions",
            "importance": "core"
        }
    )
    parse_includes: bool = field(
        default=False,
        metadata={
            "help": "Process include directives (SECURITY: disabled by default)",
            "cli_name": "parse-includes",
            "importance": "security"
        }
    )
    strict_mode: bool = field(
        default=False,
        metadata={
            "help": "Raise errors on invalid AsciiDoc syntax",
            "importance": "advanced"
        }
    )
    resolve_attribute_refs: bool = field(
        default=True,
        metadata={
            "help": "Resolve attribute references ({name}) in text",
            "cli_name": "no-resolve-attributes",
            "importance": "advanced"
        }
    )
    attribute_missing_policy: Literal["keep", "blank", "warn"] = field(
        default="keep",
        metadata={
            "help": "Policy for undefined attribute references: keep literal, use blank, or warn",
            "choices": ["keep", "blank", "warn"],
            "importance": "advanced"
        }
    )
    support_unconstrained_formatting: bool = field(
        default=True,
        metadata={
            "help": "Support unconstrained formatting (e.g., **b**old for mid-word)",
            "cli_name": "no-unconstrained-formatting",
            "importance": "advanced"
        }
    )
    table_header_detection: Literal["first-row", "attribute-based", "auto"] = field(
        default="attribute-based",
        metadata={
            "help": "How to detect table headers: always first-row, use block attributes, or auto-detect",
            "choices": ["first-row", "attribute-based", "auto"],
            "importance": "core"
        }
    )
    honor_hard_breaks: bool = field(
        default=True,
        metadata={
            "help": "Honor explicit line breaks (trailing space + plus)",
            "cli_name": "no-honor-hard-breaks",
            "importance": "advanced"
        }
    )


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
    preserve_comments : bool, default False
        Whether to include // comments in rendered output.
    line_length : int, default 0
        Target line length for wrapping text (0 = no wrapping).
    html_passthrough_mode : {"pass-through", "escape", "drop", "sanitize"}, default "pass-through"
        How to handle HTMLBlock and HTMLInline nodes:
        - "pass-through": Pass through unchanged (use only with trusted content)
        - "escape": HTML-escape the content
        - "drop": Remove HTML content entirely
        - "sanitize": Remove dangerous elements/attributes (requires bleach for best results)

    """

    list_indent: int = field(
        default=2,
        metadata={
            "help": "Spaces for nested list indentation",
            "type": int
        }
    )
    use_attributes: bool = field(
        default=True,
        metadata={
            "help": "Include document attributes in output",
            "cli_name": "no-use-attributes",
            "importance": "core"
        }
    )
    preserve_comments: bool = field(
        default=False,
        metadata={
            "help": "Include comments in rendered output",
            "cli_name": "preserve-comments",
            "importance": "core"
        }
    )
    line_length: int = field(
        default=0,
        metadata={
            "help": "Target line length for wrapping (0 = no wrapping)",
            "type": int,
            "importance": "core"
        }
    )
    html_passthrough_mode: HtmlPassthroughMode = field(
        default=DEFAULT_HTML_PASSTHROUGH_MODE,
        metadata={
            "help": "How to handle raw HTML content: pass-through, escape, drop, or sanitize",
            "choices": HTML_PASSTHROUGH_MODES,
            "importance": "security"
        }
    )
