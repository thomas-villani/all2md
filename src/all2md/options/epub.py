#  Copyright (c) 2025 Tom Villani, Ph.D.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from all2md.options.base import BaseParserOptions, BaseRendererOptions
from all2md.options.html import HtmlOptions


# all2md/options/epub.py
@dataclass(frozen=True)
class EpubRendererOptions(BaseRendererOptions):
    """Configuration options for rendering AST to EPUB format.

    This dataclass contains settings specific to EPUB generation from AST,
    including chapter splitting strategies, metadata, and EPUB structure.

    Parameters
    ----------
    chapter_split_mode : {"separator", "heading", "auto"}, default "auto"
        How to split the AST into chapters:
        - "separator": Split on ThematicBreak nodes (mirrors parser behavior)
        - "heading": Split on specific heading level
        - "auto": Try separator first, fallback to heading-based splitting
    chapter_split_heading_level : int, default 1
        Heading level to use for chapter splits when using heading mode.
        Level 1 (H1) typically represents chapter boundaries.
    title : str or None, default None
        EPUB book title. If None, extracted from document metadata.
    author : str or None, default None
        EPUB book author. If None, extracted from document metadata.
    language : str, default "en"
        EPUB book language code (ISO 639-1).
    identifier : str or None, default None
        Unique identifier (ISBN, UUID, etc.). Auto-generated if None.
    chapter_title_template : str, default "Chapter {num}"
        Template for auto-generated chapter titles. Supports {num} placeholder.
    use_heading_as_chapter_title : bool, default True
        Use first heading in chapter as chapter title in NCX/navigation.
    generate_toc : bool, default True
        Generate table of contents (NCX and nav.xhtml files).
    include_cover : bool, default False
        Include cover image in EPUB package.
    cover_image_path : str or None, default None
        Path to cover image file. Only used if include_cover=True.

    """

    chapter_split_mode: Literal["separator", "heading", "auto"] = field(
        default="auto",
        metadata={
            "help": "Chapter splitting strategy: separator, heading, or auto",
            "choices": ["separator", "heading", "auto"]
        }
    )
    chapter_split_heading_level: int = field(
        default=1,
        metadata={
            "help": "Heading level for chapter splits (H1 = level 1)",
            "type": int
        }
    )
    title: str | None = field(
        default=None,
        metadata={"help": "EPUB book title (None = use document metadata)"}
    )
    author: str | None = field(
        default=None,
        metadata={"help": "EPUB book author (None = use document metadata)"}
    )
    language: str = field(
        default="en",
        metadata={"help": "EPUB language code (ISO 639-1)"}
    )
    identifier: str | None = field(
        default=None,
        metadata={"help": "Unique identifier (ISBN, UUID, etc.)"}
    )
    chapter_title_template: str = field(
        default="Chapter {num}",
        metadata={"help": "Template for auto-generated chapter titles"}
    )
    use_heading_as_chapter_title: bool = field(
        default=True,
        metadata={
            "help": "Use first heading as chapter title in navigation",
            "cli_name": "no-use-heading-as-chapter-title"
        }
    )
    generate_toc: bool = field(
        default=True,
        metadata={
            "help": "Generate table of contents (NCX and nav.xhtml)",
            "cli_name": "no-generate-toc"
        }
    )
    include_cover: bool = field(
        default=False,
        metadata={"help": "Include cover image in EPUB"}
    )
    cover_image_path: str | None = field(
        default=None,
        metadata={"help": "Path to cover image file"}
    )


@dataclass(frozen=True)
class EpubOptions(BaseParserOptions):
    """Configuration options for EPUB-to-Markdown conversion.

    This dataclass contains settings specific to EPUB document processing,
    including chapter handling, table of contents generation, and image handling.

    Parameters
    ----------
    merge_chapters : bool, default True
        Whether to merge chapters into a single continuous document. If False,
        a separator is placed between chapters.
    include_toc : bool, default True
        Whether to generate and prepend a Markdown Table of Contents.

    """

    merge_chapters: bool = field(
        default=True,
        metadata={
            "help": "Merge chapters into a single continuous document",
            "cli_name": "no-merge-chapters"
        }
    )
    include_toc: bool = field(
        default=True,
        metadata={
            "help": "Generate and prepend a Markdown Table of Contents",
            "cli_name": "no-include-toc"
        }
    )

    html_options: HtmlOptions | None = field(
        default=None,
        metadata={"exclude_from_cli": True}  # Special field, handled separately
    )
