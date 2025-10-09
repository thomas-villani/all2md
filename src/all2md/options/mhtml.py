#  Copyright (c) 2025 Tom Villani, Ph.D.

# ${DIR_PATH}/${FILE_NAME}
from __future__ import annotations

from dataclasses import dataclass

from all2md.options.html import HtmlOptions


@dataclass(frozen=True)
class MhtmlOptions(HtmlOptions):
    """Configuration options for MHTML-to-Markdown conversion.

    This dataclass contains settings specific to MHTML file processing,
    primarily for handling embedded assets like images and local file security.

    Parameters
    ----------
    Inherited from HtmlOptions

    """

    pass
