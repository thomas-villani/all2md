#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# all2md/options/outlook.py
"""Configuration options for Outlook (MSG/PST/OST) parsing.

This module defines options for parsing Microsoft Outlook format files.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_INCLUDE_SUBFOLDERS,
    DEFAULT_MAX_MESSAGES,
    DEFAULT_OUTLOOK_SKIP_FOLDERS,
    DEFAULT_OUTPUT_STRUCTURE,
    OutputStructureMode,
)
from all2md.options.eml import EmlOptions


@dataclass(frozen=True)
class OutlookOptions(EmlOptions):
    """Configuration options for Outlook-to-Markdown conversion.

    This dataclass contains settings specific to Outlook format processing (MSG, PST, OST),
    extending EmlOptions with Outlook-specific features like folder filtering,
    PST/OST archive handling, and advanced message selection.

    Parameters
    ----------
    output_structure : {"flat", "hierarchical"}, default "flat"
        Output structure mode:
        - "flat": All messages sequentially with H1 headings
        - "hierarchical": Preserve folder structure with nested headings (PST/OST only)
    max_messages : int or None, default None
        Maximum number of messages to process. None means no limit.
        Useful for testing or processing large PST/OST files in chunks.
    date_range_start : datetime.datetime or None, default None
        Only process messages sent on or after this date.
    date_range_end : datetime.datetime or None, default None
        Only process messages sent on or before this date.
    folder_filter : list[str] or None, default None
        For PST/OST, only process messages from these folders.
        Examples: ["Inbox", "Sent Items"]
        None means process all folders except those in skip_folders.
    skip_folders : list[str] or None, default None
        For PST/OST, skip messages from these folders.
        Default skips: ["Deleted Items", "Junk Email", "Trash", "Drafts"]
        Set to empty list [] to process all folders.
    include_subfolders : bool, default True
        For PST/OST, include messages from subfolders when processing a folder.
    preserve_folder_metadata : bool, default True
        Include folder name in message metadata when using flat output structure.

    Examples
    --------
    Process only Inbox and Sent Items:
        >>> options = OutlookOptions(folder_filter=["Inbox", "Sent Items"])

    Limit to 100 most recent messages:
        >>> options = OutlookOptions(max_messages=100)

    Filter by date range:
        >>> from datetime import datetime
        >>> options = OutlookOptions(
        ...     date_range_start=datetime(2024, 1, 1),
        ...     date_range_end=datetime(2024, 12, 31)
        ... )

    Hierarchical output with folder structure (PST/OST):
        >>> options = OutlookOptions(output_structure="hierarchical")

    Process all folders including deleted items:
        >>> options = OutlookOptions(skip_folders=[])

    """

    output_structure: OutputStructureMode = field(
        default=DEFAULT_OUTPUT_STRUCTURE,
        metadata={
            "help": "Output structure: 'flat' (sequential) or 'hierarchical' (preserve folders)",
            "choices": ["flat", "hierarchical"],
            "importance": "core",
        },
    )
    max_messages: int | None = field(
        default=DEFAULT_MAX_MESSAGES,
        metadata={"help": "Maximum number of messages to process (None for unlimited)", "importance": "advanced"},
    )
    date_range_start: datetime.datetime | None = field(
        default=None,
        metadata={"help": "Only process messages on or after this date", "importance": "advanced"},
    )
    date_range_end: datetime.datetime | None = field(
        default=None,
        metadata={"help": "Only process messages on or before this date", "importance": "advanced"},
    )
    folder_filter: list[str] | None = field(
        default=None,
        metadata={"help": "For PST/OST, only process these folders (None for all)", "importance": "advanced"},
    )
    skip_folders: list[str] | None = field(
        default_factory=lambda: DEFAULT_OUTLOOK_SKIP_FOLDERS.copy(),
        metadata={"help": "For PST/OST, skip these folders (empty list to process all)", "importance": "advanced"},
    )
    include_subfolders: bool = field(
        default=DEFAULT_INCLUDE_SUBFOLDERS,
        metadata={
            "help": "Include messages from subfolders when processing a folder (PST/OST)",
            "cli_name": "no-include-subfolders",
            "importance": "advanced",
        },
    )
    preserve_folder_metadata: bool = field(
        default=True,
        metadata={
            "help": "Include folder name in message metadata",
            "cli_name": "no-preserve-folder-metadata",
            "importance": "advanced",
        },
    )

    def __post_init__(self) -> None:
        """Validate and ensure immutability by defensively copying mutable collections.

        Calls parent class validation and adds defensive copying for folder lists.
        """
        # Call parent's __post_init__ for validation
        super().__post_init__()

        # Defensive copy of mutable collections to ensure immutability
        if self.folder_filter is not None:
            object.__setattr__(self, "folder_filter", list(self.folder_filter))
        if self.skip_folders is not None:
            object.__setattr__(self, "skip_folders", list(self.skip_folders))

        # Validate date range
        if (
            self.date_range_start is not None
            and self.date_range_end is not None
            and self.date_range_start > self.date_range_end
        ):
            raise ValueError("date_range_start must be before or equal to date_range_end")

        # Validate max_messages
        if self.max_messages is not None and self.max_messages <= 0:
            raise ValueError("max_messages must be a positive integer or None")
