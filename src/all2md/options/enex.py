#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/enex.py
"""Configuration options for ENEX (Evernote Export) parsing.

This module defines options for parsing Evernote Export (.enex) files,
including note metadata, tags, and attachment handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_DATE_FORMAT_MODE,
    DEFAULT_DATE_STRFTIME_PATTERN,
    DEFAULT_INCLUDE_NOTE_METADATA,
    DEFAULT_INCLUDE_TAGS,
    DEFAULT_NOTE_SORT_MODE,
    DEFAULT_NOTE_TITLE_LEVEL,
    DEFAULT_NOTEBOOK_AS_HEADING,
    DEFAULT_NOTES_SECTION_TITLE,
    DEFAULT_TAGS_FORMAT_MODE,
    DateFormatMode,
    NoteSortMode,
    TagsFormatMode,
)
from all2md.options.base import BaseParserOptions
from all2md.options.common import AttachmentOptionsMixin


@dataclass(frozen=True)
class EnexOptions(BaseParserOptions, AttachmentOptionsMixin):
    """Configuration options for ENEX-to-Markdown conversion.

    This dataclass contains settings specific to Evernote Export file processing,
    including note title formatting, metadata handling, tag rendering, and
    attachment processing. Inherits attachment handling from AttachmentOptionsMixin.

    Parameters
    ----------
    note_title_level : int, default 1
        Heading level for note titles (1-6). Each note's title will be rendered
        as a heading at this level.
    include_note_metadata : bool, default True
        Whether to include note metadata (created date, updated date, source URL, etc.)
        as a paragraph below the note title.
    include_tags : bool, default True
        Whether to include note tags in the output.
    tags_format : {"frontmatter", "inline", "heading", "skip"}, default "inline"
        How to render note tags:
        - "frontmatter": Add as YAML frontmatter (tags: [tag1, tag2])
        - "inline": Add as inline text (Tags: tag1, tag2)
        - "heading": Add as a heading section with tags listed
        - "skip": Don't include tags in output
    notebook_as_heading : bool, default False
        Whether to add notebook name as a top-level heading above notes.
        Useful when exporting multiple notebooks to a single ENEX file.
    date_format_mode : {"iso8601", "locale", "strftime"}, default "strftime"
        How to format dates in output:
        - "iso8601": Use ISO 8601 format (2023-01-01T10:00:00Z)
        - "locale": Use system locale-aware formatting
        - "strftime": Use custom strftime pattern
    date_strftime_pattern : str, default "%m/%d/%y %H:%M"
        Custom strftime pattern when date_format_mode is "strftime".
    sort_notes_by : {"created", "updated", "title", "none"}, default "none"
        Sort notes by this criterion:
        - "created": Sort by creation date (oldest first)
        - "updated": Sort by last updated date (most recent first)
        - "title": Sort alphabetically by title
        - "none": Preserve order from ENEX file
    notes_section_title : str, default "Notes"
        Title for the notes section when rendering multiple notes.

    Examples
    --------
    Convert ENEX with frontmatter tags and ISO dates:
        >>> options = EnexOptions(
        ...     tags_format="frontmatter",
        ...     date_format_mode="iso8601"
        ... )

    Convert with custom date formatting and notebook headings:
        >>> options = EnexOptions(
        ...     notebook_as_heading=True,
        ...     date_strftime_pattern="%B %d, %Y",
        ...     date_format_mode="strftime"
        ... )

    Skip metadata and tags for cleaner output:
        >>> options = EnexOptions(
        ...     include_note_metadata=False,
        ...     tags_format="skip"
        ... )

    """

    note_title_level: int = field(
        default=DEFAULT_NOTE_TITLE_LEVEL,
        metadata={
            "help": "Heading level for note titles (1-6)",
            "type": int,
            "importance": "core",
        },
    )
    include_note_metadata: bool = field(
        default=DEFAULT_INCLUDE_NOTE_METADATA,
        metadata={
            "help": "Include note metadata (created/updated dates, source URL, etc.)",
            "cli_name": "no-include-note-metadata",
            "importance": "core",
        },
    )
    include_tags: bool = field(
        default=DEFAULT_INCLUDE_TAGS,
        metadata={
            "help": "Include note tags in output",
            "cli_name": "no-include-tags",
            "importance": "core",
        },
    )
    tags_format: TagsFormatMode = field(
        default=DEFAULT_TAGS_FORMAT_MODE,
        metadata={
            "help": "How to render tags: frontmatter, inline, heading, or skip",
            "importance": "core",
        },
    )
    notebook_as_heading: bool = field(
        default=DEFAULT_NOTEBOOK_AS_HEADING,
        metadata={
            "help": "Add notebook name as top-level heading above notes",
            "cli_name": "notebook-as-heading",
            "importance": "advanced",
        },
    )
    date_format_mode: DateFormatMode = field(
        default=DEFAULT_DATE_FORMAT_MODE,
        metadata={
            "help": "Date formatting mode: iso8601, locale, or strftime",
            "importance": "advanced",
        },
    )
    date_strftime_pattern: str = field(
        default=DEFAULT_DATE_STRFTIME_PATTERN,
        metadata={
            "help": "Custom strftime pattern when date_format_mode is 'strftime'",
            "importance": "advanced",
        },
    )
    sort_notes_by: NoteSortMode = field(
        default=DEFAULT_NOTE_SORT_MODE,
        metadata={
            "help": "Sort notes by: created, updated, title, or none",
            "importance": "advanced",
        },
    )
    notes_section_title: str = field(
        default=DEFAULT_NOTES_SECTION_TITLE,
        metadata={
            "help": "Title for the notes section when rendering multiple notes",
            "importance": "advanced",
        },
    )

    def __post_init__(self) -> None:
        """Validate ENEX-specific options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        super().__post_init__()

        # Validate heading level range
        if not 1 <= self.note_title_level <= 6:
            raise ValueError(f"note_title_level must be between 1 and 6, got {self.note_title_level}")

        # Validate date_strftime_pattern is non-empty when using strftime mode
        if self.date_format_mode == "strftime" and not self.date_strftime_pattern:
            raise ValueError("date_strftime_pattern cannot be empty when date_format_mode is 'strftime'")
