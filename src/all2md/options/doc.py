#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/doc.py
"""Configuration options for Word 97-2003 (.doc) parsing.

The defaults match the DOCX parser's, so a ``.doc`` and the ``.docx`` Word
saves from it convert alike.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_DOCX_COMMENTS_POSITION,
    DEFAULT_DOCX_INCLUDE_COMMENTS,
    DEFAULT_DOCX_INCLUDE_ENDNOTES,
    DEFAULT_DOCX_INCLUDE_FOOTNOTES,
    DocxCommentsPosition,
)
from all2md.options.base import BaseParserOptions


@dataclass(frozen=True)
class DocOptions(BaseParserOptions):
    """Configuration options for Word 97-2003 (.doc) to AST parsing.

    Parameters
    ----------
    include_footnotes : bool, default True
        Read footnotes as footnote definitions, referenced where their marks stand.
    include_endnotes : bool, default True
        Read endnotes as footnote definitions with ``end``-prefixed identifiers.
    include_comments : bool, default False
        Read review comments.
    comments_position : {"inline", "footnotes"}, default "footnotes"
        Where comments go: inline at their reference marks, or as Comment
        blocks after the body.
    include_headers_footers : bool, default False
        Read page headers and footers: each distinct header before the body and
        each distinct footer after it.

    Examples
    --------
    Keep comments, inline where they are anchored:
        >>> options = DocOptions(include_comments=True, comments_position="inline")

    """

    include_footnotes: bool = field(
        default=DEFAULT_DOCX_INCLUDE_FOOTNOTES,
        metadata={"help": "Include footnotes in output", "cli_name": "no-include-footnotes", "importance": "core"},
    )
    include_endnotes: bool = field(
        default=DEFAULT_DOCX_INCLUDE_ENDNOTES,
        metadata={"help": "Include endnotes in output", "cli_name": "no-include-endnotes", "importance": "core"},
    )
    include_comments: bool = field(
        default=DEFAULT_DOCX_INCLUDE_COMMENTS,
        metadata={"help": "Include document comments in output", "importance": "core"},
    )
    comments_position: DocxCommentsPosition = field(
        default=DEFAULT_DOCX_COMMENTS_POSITION,
        metadata={
            "help": (
                "Where to place Comment nodes in the AST: inline (CommentInline nodes at reference points) "
                "or footnotes (Comment block nodes appended at end)"
            ),
            "choices": ["inline", "footnotes"],
            "importance": "advanced",
        },
    )
    include_headers_footers: bool = field(
        default=False,
        metadata={
            "help": "Include page headers (before the body) and footers (after it), each distinct one once",
            "importance": "advanced",
        },
    )
