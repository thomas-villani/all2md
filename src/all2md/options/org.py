#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/org.py
"""Configuration options for Org-Mode parsing and rendering.

This module defines options for Org-Mode document conversion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_ORG_COMMENT_MODE,
    DEFAULT_ORG_HEADING_STYLE,
    DEFAULT_ORG_PARSE_CLOCK,
    DEFAULT_ORG_PARSE_CLOSED,
    DEFAULT_ORG_PARSE_LOGBOOK,
    DEFAULT_ORG_PARSE_PROPERTIES,
    DEFAULT_ORG_PARSE_SCHEDULING,
    DEFAULT_ORG_PARSE_TAGS,
    DEFAULT_ORG_PRESERVE_CLOCK,
    DEFAULT_ORG_PRESERVE_CLOSED,
    DEFAULT_ORG_PRESERVE_LOGBOOK,
    DEFAULT_ORG_PRESERVE_PROPERTIES,
    DEFAULT_ORG_PRESERVE_TAGS,
    DEFAULT_ORG_PRESERVE_TIMESTAMP_METADATA,
    DEFAULT_ORG_TODO_KEYWORDS,
    OrgCommentMode,
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
    parse_properties : bool, default True
        Whether to parse Org properties within drawers.
        When True, properties are extracted and stored in metadata.
    parse_tags : bool, default True
        Whether to parse heading tags (e.g., :work:urgent:).
        When True, tags are extracted and stored in heading metadata.
    parse_scheduling : bool, default True
        Whether to parse SCHEDULED and DEADLINE timestamps.
        When True, scheduling info is extracted and stored in metadata.
        For the first heading, scheduling is also added to Document.metadata.custom.
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

    parse_properties: bool = field(
        default=DEFAULT_ORG_PARSE_PROPERTIES,
        metadata={
            "help": "Parse Org properties within drawers",
            "cli_name": "no-parse-properties",
            "importance": "core",
        },
    )
    parse_tags: bool = field(
        default=DEFAULT_ORG_PARSE_TAGS,
        metadata={
            "help": "Parse heading tags (e.g., :work:urgent:)",
            "cli_name": "no-parse-tags",
            "importance": "core",
        },
    )
    parse_scheduling: bool = field(
        default=DEFAULT_ORG_PARSE_SCHEDULING,
        metadata={
            "help": "Parse SCHEDULED and DEADLINE timestamps",
            "cli_name": "no-parse-scheduling",
            "importance": "core",
        },
    )
    todo_keywords: list[str] = field(
        default_factory=lambda: list(DEFAULT_ORG_TODO_KEYWORDS),
        metadata={"help": "List of TODO keywords to recognize", "cli_name": "todo-keywords", "importance": "core"},
    )
    parse_logbook: bool = field(
        default=DEFAULT_ORG_PARSE_LOGBOOK,
        metadata={
            "help": "Parse LOGBOOK drawer entries into structured data",
            "cli_name": "no-parse-logbook",
            "importance": "core",
        },
    )
    parse_clock: bool = field(
        default=DEFAULT_ORG_PARSE_CLOCK,
        metadata={
            "help": "Parse CLOCK entries",
            "cli_name": "no-parse-clock",
            "importance": "core",
        },
    )
    parse_closed: bool = field(
        default=DEFAULT_ORG_PARSE_CLOSED,
        metadata={
            "help": "Parse CLOSED timestamps for completed tasks",
            "cli_name": "no-parse-closed",
            "importance": "core",
        },
    )
    preserve_timestamp_metadata: bool = field(
        default=DEFAULT_ORG_PRESERVE_TIMESTAMP_METADATA,
        metadata={
            "help": "Store full timestamp metadata (repeaters, warnings, time ranges)",
            "cli_name": "no-preserve-timestamp-metadata",
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()


@dataclass(frozen=True)
class OrgRendererOptions(BaseRendererOptions):
    r"""Configuration options for AST-to-Org-Mode rendering.

    This dataclass contains settings for rendering AST documents as
    Org-Mode output.

    Parameters
    ----------
    heading_style : {"stars"}, default "stars"
        Style for rendering headings. Currently only "stars" is supported
        (e.g., ``*`` Level 1, ``**`` Level 2, ``***`` Level 3).
    preserve_properties : bool, default True
        Whether to preserve properties in rendered output.
        When True, properties stored in metadata are rendered in :PROPERTIES: drawer.
    preserve_tags : bool, default True
        Whether to preserve heading tags in rendered output.
        When True, tags stored in metadata are rendered (e.g., :work:urgent:).
    todo_keywords : list[str], default ["TODO", "DONE"]
        List of TODO keywords that may appear in headings.
        Used for validation and rendering.
    comment_mode : {"comment", "drawer", "ignore"}, default "comment"
        How to render Comment and CommentInline AST nodes:
        - "comment": Render as Org-mode comments (# Comment text)
        - "drawer": Render as :COMMENT: drawer blocks (visible annotations)
        - "ignore": Skip comment nodes entirely
        This controls presentation of comments from source documents.

    Notes
    -----
    **Heading Rendering:**
        Headings are rendered with stars (``*``, ``**``, ``***``, etc.) based on level.
        TODO states and tags are preserved if present in metadata.

    **TODO States:**
        If a heading has ``metadata["org_todo_state"]``, it's rendered before the heading text.
        Example: ``* TODO Write documentation``

    **Tags:**
        If preserve_tags is True and ``metadata["org_tags"]`` exists, tags are rendered.
        Example: ``* Heading :work:urgent:``

    **Properties:**
        If preserve_properties is True and ``metadata["org_properties"]`` exists,
        a ``:PROPERTIES:`` drawer is rendered under the heading.

    """

    heading_style: OrgHeadingStyle = field(
        default=DEFAULT_ORG_HEADING_STYLE,
        metadata={"help": "Style for rendering headings", "choices": ["stars"], "importance": "advanced"},
    )
    preserve_properties: bool = field(
        default=DEFAULT_ORG_PRESERVE_PROPERTIES,
        metadata={
            "help": "Preserve properties in rendered output",
            "cli_name": "no-preserve-properties",
            "importance": "core",
        },
    )
    preserve_tags: bool = field(
        default=DEFAULT_ORG_PRESERVE_TAGS,
        metadata={
            "help": "Preserve heading tags in rendered output",
            "cli_name": "no-preserve-tags",
            "importance": "core",
        },
    )
    todo_keywords: list[str] = field(
        default_factory=lambda: list(DEFAULT_ORG_TODO_KEYWORDS),
        metadata={"help": "List of TODO keywords", "cli_name": "todo-keywords", "importance": "core"},
    )
    comment_mode: OrgCommentMode = field(
        default=DEFAULT_ORG_COMMENT_MODE,
        metadata={
            "help": "How to render Comment and CommentInline nodes: "
            "comment (# comments), drawer (:COMMENT: drawer), "
            "ignore (skip comment nodes entirely). Controls presentation of source document comments.",
            "choices": ["comment", "drawer", "ignore"],
            "importance": "core",
        },
    )
    preserve_logbook: bool = field(
        default=DEFAULT_ORG_PRESERVE_LOGBOOK,
        metadata={
            "help": "Render LOGBOOK drawer from metadata",
            "cli_name": "no-preserve-logbook",
            "importance": "core",
        },
    )
    preserve_clock: bool = field(
        default=DEFAULT_ORG_PRESERVE_CLOCK,
        metadata={
            "help": "Render CLOCK entries",
            "cli_name": "no-preserve-clock",
            "importance": "core",
        },
    )
    preserve_closed: bool = field(
        default=DEFAULT_ORG_PRESERVE_CLOSED,
        metadata={
            "help": "Render CLOSED timestamps",
            "cli_name": "no-preserve-closed",
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
