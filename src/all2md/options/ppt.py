#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/ppt.py
"""Configuration options for PowerPoint 97-2003 (.ppt) parsing.

The options and their defaults are the PPTX parser's, so a ``.ppt`` and the
``.pptx`` PowerPoint saves from it convert alike.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_PPTX_INCLUDE_TITLES_AS_H2,
    DEFAULT_PPTX_PARSER_COMMENT_MODE,
    DEFAULT_SLIDE_NUMBERS,
    PptxParserCommentMode,
)
from all2md.options.base import BaseParserOptions


@dataclass(frozen=True)
class PptOptions(BaseParserOptions):
    """Configuration options for PowerPoint 97-2003 (.ppt) to AST parsing.

    Parameters
    ----------
    include_slide_numbers : bool, default False
        Prefix each slide title with ``Slide N:``.
    include_notes : bool, default True
        Read each slide's speaker notes.
    comment_mode : {"content", "comment", "ignore"}, default "content"
        How speaker notes are parsed: as paragraphs under a "Speaker Notes"
        heading, as Comment nodes, or not at all.
    slides : str or None, default None
        The slides to read, e.g. ``"1,3-5"``; all of them when None.
    include_titles_as_h2 : bool, default True
        Make each slide's title a level 2 heading; otherwise it is a paragraph.

    Examples
    --------
    Read slides 2 to 4 without their notes:
        >>> options = PptOptions(slides="2-4", include_notes=False)

    """

    include_slide_numbers: bool = field(
        default=DEFAULT_SLIDE_NUMBERS, metadata={"help": "Include slide numbers in output", "importance": "core"}
    )
    include_notes: bool = field(
        default=True,
        metadata={"help": "Include speaker notes from slides", "cli_name": "no-include-notes", "importance": "core"},
    )
    comment_mode: PptxParserCommentMode = field(
        default=DEFAULT_PPTX_PARSER_COMMENT_MODE,
        metadata={
            "help": "How to parse speaker notes: content (regular nodes with H3 heading), "
            "comment (Comment AST nodes with metadata), or ignore (skip entirely)",
            "choices": ["content", "comment", "ignore"],
            "importance": "core",
        },
    )
    slides: str | None = field(
        default=None,
        metadata={"help": "Slide selection (e.g., '1,3-5,8' for slides 1, 3-5, and 8)", "importance": "core"},
    )
    include_titles_as_h2: bool = field(
        default=DEFAULT_PPTX_INCLUDE_TITLES_AS_H2,
        metadata={
            "help": "Include slide titles as H2 headings",
            "cli_name": "no-include-titles-as-h2",
            "importance": "core",
        },
    )
