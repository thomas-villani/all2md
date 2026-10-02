#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/man.py
"""Configuration options for man page parsing.

This module defines the options class for reading Unix manual pages written
with the man(7) macro package.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.options.base import BaseParserOptions


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
