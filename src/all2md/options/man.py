#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/man.py
"""Configuration options for man page parsing and rendering.

This module defines the options classes for reading Unix manual pages written
with the man(7) macro package, and for writing them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.options.base import BaseParserOptions, BaseRendererOptions


@dataclass(frozen=True)
class ManParserOptions(BaseParserOptions):
    """Configuration options for man(7) page to AST parsing.

    Parameters
    ----------
    title_heading : bool, default True
        Emit a level-1 heading such as ``LS(1)`` from the ``.TH`` line. Section
        headings (``.SH``) then become level 2 and subsections (``.SS``) level 3.
        When False, ``.SH`` is level 1 and ``.SS`` level 2.
    normalize_heading_case : bool, default False
        Rewrite all-uppercase section headings such as ``SEE ALSO`` in title case
        (``See Also``). Mixed-case headings are left alone.

    Examples
    --------
    Section headings at level 1, in title case:
        >>> options = ManParserOptions(title_heading=False, normalize_heading_case=True)

    """

    title_heading: bool = field(
        default=True,
        metadata={
            "help": "Emit a level-1 heading such as LS(1) from the .TH line",
            "cli_name": "no-title-heading",
            "importance": "core",
        },
    )
    normalize_heading_case: bool = field(
        default=False,
        metadata={
            "help": "Rewrite all-uppercase section headings in title case (SEE ALSO -> See Also)",
            "importance": "advanced",
        },
    )


@dataclass(frozen=True)
class ManRendererOptions(BaseRendererOptions):
    """Configuration options for AST to man(7) page rendering.

    The ``.TH`` line is built from the document: the name (and section) come from
    a leading level-1 heading such as ``LS(1)``, else from the ``title`` metadata;
    the date, source and manual come from the ``modification_date``, ``source``
    and ``manual`` metadata a parsed man page carries. Each option below
    overrides the value read from the document.

    Parameters
    ----------
    section : str or None, default None
        Manual section for ``.TH`` (``1`` for user commands, ``3`` for library
        calls, ...). Defaults to the section in the title or metadata, else ``1``.
    date : str or None, default None
        Date for ``.TH``, conventionally ``YYYY-MM-DD``.
    source : str or None, default None
        Source of the page for ``.TH``, such as ``GNU coreutils 9.4``.
    manual : str or None, default None
        Manual title for ``.TH``, such as ``User Commands``.
    uppercase_section_headings : bool, default True
        Write ``.SH`` headings in uppercase, as man pages conventionally do.

    Examples
    --------
    A page in section 8 with a fixed date:
        >>> options = ManRendererOptions(section="8", date="2026-10-03")

    """

    section: str | None = field(
        default=None,
        metadata={"help": "Manual section for .TH (default: from the title or metadata, else 1)", "importance": "core"},
    )
    date: str | None = field(
        default=None,
        metadata={"help": "Date for .TH (default: the document's modification date)", "importance": "core"},
    )
    source: str | None = field(
        default=None,
        metadata={"help": "Source for .TH, such as 'GNU coreutils 9.4'", "importance": "advanced"},
    )
    manual: str | None = field(
        default=None,
        metadata={"help": "Manual title for .TH, such as 'User Commands'", "importance": "advanced"},
    )
    uppercase_section_headings: bool = field(
        default=True,
        metadata={
            "help": "Write .SH headings in uppercase",
            "cli_name": "no-uppercase-section-headings",
            "importance": "advanced",
        },
    )
