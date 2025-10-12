#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/org.py
"""Configuration options for Org-Mode parsing and rendering.

This module defines options for Org-Mode document conversion.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_ORG_HEADING_STYLE,
    DEFAULT_ORG_PARSE_DRAWERS,
    DEFAULT_ORG_PARSE_PROPERTIES,
    DEFAULT_ORG_PARSE_TAGS,
    DEFAULT_ORG_PRESERVE_DRAWERS,
    DEFAULT_ORG_PRESERVE_PROPERTIES,
    DEFAULT_ORG_PRESERVE_TAGS,
    DEFAULT_ORG_TODO_KEYWORDS,
    OrgHeadingStyle,
)
from all2md.options.base import BaseParserOptions, BaseRendererOptions


@dataclass(frozen=True)
class OrgParserOptions(BaseParserOptions):
    """Configuration options for Org-Mode-to-AST parsing.

    This dataclass contains settings specific to parsing Org-Mode documents
    into AST representation using orgparse.

    Parameters
    ----------
    parse_drawers : bool, default True
        Whether to parse Org drawers (e.g., :PROPERTIES:, :LOGBOOK:).
        When True, drawer contents are preserved in metadata.
        When False, drawers are ignored.
    parse_properties : bool, default True
        Whether to parse Org properties within drawers.
        When True, properties are extracted and stored in metadata.
    parse_tags : bool, default True
        Whether to parse heading tags (e.g., :work:urgent:).
        When True, tags are extracted and stored in heading metadata.
    todo_keywords : list[str], default ["TODO", "DONE"]
        List of TODO keywords to recognize in headings.
        Common keywords: TODO, DONE, IN-PROGRESS, WAITING, CANCELLED, etc.

    Examples
    --------
    Basic usage:
        >>> options = OrgParserOptions()
        >>> parser = OrgParser(options)

    Custom TODO keywords:
        >>> options = OrgParserOptions(
        ...     todo_keywords=["TODO", "IN-PROGRESS", "DONE", "CANCELLED"]
        ... )

    """

    parse_drawers: bool = field(
        default=DEFAULT_ORG_PARSE_DRAWERS,
        metadata={
            "help": "Parse Org drawers (e.g., :PROPERTIES:, :LOGBOOK:)",
            "cli_name": "parse-drawers"
        }
    )
    parse_properties: bool = field(
        default=DEFAULT_ORG_PARSE_PROPERTIES,
        metadata={
            "help": "Parse Org properties within drawers",
            "cli_name": "parse-properties"
        }
    )
    parse_tags: bool = field(
        default=DEFAULT_ORG_PARSE_TAGS,
        metadata={
            "help": "Parse heading tags (e.g., :work:urgent:)",
            "cli_name": "parse-tags"
        }
    )
    todo_keywords: list[str] = field(
        default_factory=lambda: list(DEFAULT_ORG_TODO_KEYWORDS),
        metadata={
            "help": "List of TODO keywords to recognize",
            "cli_name": "todo-keywords"
        }
    )


@dataclass(frozen=True)
class OrgRendererOptions(BaseRendererOptions):
    """Configuration options for AST-to-Org-Mode rendering.

    This dataclass contains settings for rendering AST documents as
    Org-Mode output.

    Parameters
    ----------
    heading_style : {"stars"}, default "stars"
        Style for rendering headings. Currently only "stars" is supported
        (e.g., * Level 1, ** Level 2, *** Level 3).
    preserve_drawers : bool, default False
        Whether to preserve drawer content in rendered output.
        When True, drawers stored in metadata are rendered back.
    preserve_properties : bool, default True
        Whether to preserve properties in rendered output.
        When True, properties stored in metadata are rendered in :PROPERTIES: drawer.
    preserve_tags : bool, default True
        Whether to preserve heading tags in rendered output.
        When True, tags stored in metadata are rendered (e.g., :work:urgent:).
    todo_keywords : list[str], default ["TODO", "DONE"]
        List of TODO keywords that may appear in headings.
        Used for validation and rendering.

    Notes
    -----
    **Heading Rendering:**
        Headings are rendered with stars (*, **, ***, etc.) based on level.
        TODO states and tags are preserved if present in metadata.

    **TODO States:**
        If a heading has metadata["org_todo_state"], it's rendered before the heading text.
        Example: * TODO Write documentation

    **Tags:**
        If preserve_tags is True and metadata["org_tags"] exists, tags are rendered.
        Example: * Heading :work:urgent:

    **Properties:**
        If preserve_properties is True and metadata["org_properties"] exists,
        a :PROPERTIES: drawer is rendered under the heading.

    """

    heading_style: OrgHeadingStyle = field(
        default=DEFAULT_ORG_HEADING_STYLE,
        metadata={
            "help": "Style for rendering headings",
            "choices": ["stars"]
        }
    )
    preserve_drawers: bool = field(
        default=DEFAULT_ORG_PRESERVE_DRAWERS,
        metadata={
            "help": "Preserve drawer content in rendered output",
            "cli_name": "preserve-drawers"
        }
    )
    preserve_properties: bool = field(
        default=DEFAULT_ORG_PRESERVE_PROPERTIES,
        metadata={
            "help": "Preserve properties in rendered output",
            "cli_name": "preserve-properties"
        }
    )
    preserve_tags: bool = field(
        default=DEFAULT_ORG_PRESERVE_TAGS,
        metadata={
            "help": "Preserve heading tags in rendered output",
            "cli_name": "preserve-tags"
        }
    )
    todo_keywords: list[str] = field(
        default_factory=lambda: list(DEFAULT_ORG_TODO_KEYWORDS),
        metadata={
            "help": "List of TODO keywords",
            "cli_name": "todo-keywords"
        }
    )
