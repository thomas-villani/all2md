#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/rtf.py
from __future__ import annotations

from dataclasses import dataclass

from all2md import BaseParserOptions


@dataclass(frozen=True)
class RtfOptions(BaseParserOptions):
    """Configuration options for RTF-to-Markdown conversion.

    This dataclass contains settings specific to Rich Text Format processing,
    primarily for handling embedded images and other attachments.

    Parameters
    ----------
    Inherited from `BaseParserOptions`

    """

    pass
