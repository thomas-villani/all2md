#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Configuration options for EPUB parsing and rendering.

This module defines options for EPUB e-book format conversion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from all2md.options.base import BaseParserOptions, BaseRendererOptions
from all2md.options.common import AttachmentOptionsMixin, NetworkFetchOptions
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
    network : NetworkFetchOptions, default NetworkFetchOptions()
        Network security options for fetching remote images. By default,
        remote image fetching is disabled (allow_remote_fetch=False).
        Set network.allow_remote_fetch=True to enable secure remote image fetching.

    """

    chapter_split_mode: Literal["separator", "heading", "auto"] = field(
        default="auto",
        metadata={
            "help": "Chapter splitting strategy: separator, heading, or auto",
            "choices": ["separator", "heading", "auto"],
            "importance": "core",
        },
    )
    chapter_split_heading_level: int = field(
        default=1,
        metadata={"help": "Heading level for chapter splits (H1 = level 1)", "type": int, "importance": "advanced"},
    )
    title: str | None = field(
        default=None, metadata={"help": "EPUB book title (None = use document metadata)", "importance": "core"}
    )
    author: str | None = field(
        default=None, metadata={"help": "EPUB book author (None = use document metadata)", "importance": "core"}
    )
    language: str = field(default="en", metadata={"help": "EPUB language code (ISO 639-1)", "importance": "core"})
    identifier: str | None = field(
        default=None, metadata={"help": "Unique identifier (ISBN, UUID, etc.)", "importance": "advanced"}
    )
    chapter_title_template: str = field(
        default="Chapter {num}",
        metadata={"help": "Template for auto-generated chapter titles", "importance": "advanced"},
    )
    use_heading_as_chapter_title: bool = field(
        default=True,
        metadata={
            "help": "Use first heading as chapter title in navigation",
            "cli_name": "no-use-heading-as-chapter-title",
            "importance": "core",
        },
    )
    generate_toc: bool = field(
        default=True,
        metadata={
            "help": "Generate table of contents (NCX and nav.xhtml)",
            "cli_name": "no-generate-toc",
            "importance": "core",
        },
    )
    include_cover: bool = field(default=False, metadata={"help": "Include cover image in EPUB", "importance": "core"})
    cover_image_path: str | None = field(
        default=None, metadata={"help": "Path to cover image file", "importance": "advanced"}
    )
    network: NetworkFetchOptions = field(
        default_factory=NetworkFetchOptions,
        metadata={"help": "Network security options for fetching remote images", "importance": "security"},
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges for EPUB renderer options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        # Call parent validation
        super().__post_init__()

        # Validate heading level range
        if not 1 <= self.chapter_split_heading_level <= 6:
            raise ValueError(
                f"chapter_split_heading_level must be in range [1, 6], got {self.chapter_split_heading_level}"
            )


@dataclass(frozen=True)
class EpubOptions(BaseParserOptions, AttachmentOptionsMixin):
    """Configuration options for EPUB-to-Markdown conversion.

    This dataclass contains settings specific to EPUB document processing,
    including chapter handling, table of contents generation, and image handling.
    Inherits attachment handling from AttachmentOptionsMixin for embedded images.

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
            "cli_name": "no-merge-chapters",
            "importance": "core",
        },
    )
    include_toc: bool = field(
        default=True,
        metadata={
            "help": "Generate and prepend a Markdown Table of Contents",
            "cli_name": "no-include-toc",
            "importance": "core",
        },
    )

    html_options: HtmlOptions | None = field(default=None, metadata={"cli_flatten": True})  # Nested, handled separately

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
