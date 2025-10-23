# Copyright (c) 2025 Tom Villani, Ph.D.
"""Configuration options for FB2 (FictionBook 2.0) parsing.

This module defines parser options for FictionBook 2.0 ebook conversion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.options.base import BaseParserOptions
from all2md.options.common import AttachmentOptionsMixin


@dataclass(frozen=True)
class Fb2Options(BaseParserOptions, AttachmentOptionsMixin):
    """Configuration options for FB2-to-AST conversion.

    Inherits attachment handling from AttachmentOptionsMixin for embedded images
    in FictionBook 2.0 ebooks.

    Parameters
    ----------
    include_notes : bool, default True
        Whether to include bodies/sections marked as notes in the output.
    notes_section_title : str, default "Notes"
        Heading text to use when appending collected note sections.
    fallback_encodings : tuple[str, ...], default ("utf-8", "windows-1251", "koi8-r")
        Additional encodings to try when the XML declaration is missing or
        parsing fails with the declared encoding.

    """

    include_notes: bool = field(
        default=True,
        metadata={
            "help": "Include bodies/sections marked as notes in the output",
            "cli_name": "no-include-notes",
            "importance": "core",
        },
    )
    notes_section_title: str = field(
        default="Notes",
        metadata={
            "help": "Heading text used when appending collected notes",
            "importance": "advanced",
        },
    )
    fallback_encodings: tuple[str, ...] = field(
        default=("utf-8", "windows-1251", "koi8-r"),
        metadata={
            "help": "Additional encodings to try if XML parsing fails",
            "importance": "advanced",
        },
    )

    def __post_init__(self) -> None:
        """Validate base parser options and normalize fallback encodings."""
        super().__post_init__()
        object.__setattr__(self, "fallback_encodings", tuple(self.fallback_encodings))
