#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# all2md/options/mbox.py
"""Configuration options for MBOX (mailbox archive) parsing.

This module defines options for parsing Unix mailbox format files.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_MAILBOX_FORMAT,
    DEFAULT_MAX_MESSAGES,
    DEFAULT_OUTPUT_STRUCTURE,
    MailboxFormatType,
    OutputStructureMode,
)
from all2md.options.eml import EmlOptions


@dataclass(frozen=True)
class MboxOptions(EmlOptions):
    """Configuration options for MBOX-to-Markdown conversion.

    This dataclass contains settings specific to mailbox archive processing,
    extending EmlOptions with mailbox-specific features like format detection,
    message filtering, and folder handling.

    Parameters
    ----------
    mailbox_format : {"auto", "mbox", "maildir", "mh", "babyl", "mmdf"}, default "auto"
        Mailbox format type. "auto" detects format based on file structure.
    output_structure : {"flat", "hierarchical"}, default "flat"
        Output structure mode:
        - "flat": All messages sequentially with H1 headings
        - "hierarchical": Preserve folder structure with nested headings
    max_messages : int or None, default None
        Maximum number of messages to process. None means no limit.
        Useful for testing or processing large mailboxes in chunks.
    date_range_start : datetime.datetime or None, default None
        Only process messages sent on or after this date.
    date_range_end : datetime.datetime or None, default None
        Only process messages sent on or before this date.
    folder_filter : list[str] or None, default None
        For maildir format, only process messages from these folders.
        None means process all folders.
    preserve_folder_metadata : bool, default True
        Include folder name in message metadata when using flat output structure.

    Examples
    --------
    Convert mailbox with specific format:
        >>> options = MboxOptions(mailbox_format="maildir")

    Limit to 100 most recent messages:
        >>> options = MboxOptions(max_messages=100)

    Filter by date range:
        >>> from datetime import datetime
        >>> options = MboxOptions(
        ...     date_range_start=datetime(2024, 1, 1),
        ...     date_range_end=datetime(2024, 12, 31)
        ... )

    Hierarchical output with folder structure:
        >>> options = MboxOptions(output_structure="hierarchical")

    """

    mailbox_format: MailboxFormatType = field(
        default=DEFAULT_MAILBOX_FORMAT,
        metadata={"help": "Mailbox format type (auto, mbox, maildir, mh, babyl, mmdf)", "importance": "core"},
    )
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
        metadata={"help": "For maildir, only process these folders (None for all)", "importance": "advanced"},
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

        Calls parent class validation and adds defensive copying for folder_filter.
        """
        # Call parent's __post_init__ for validation
        super().__post_init__()

        # Defensive copy of mutable collections to ensure immutability
        if self.folder_filter is not None:
            object.__setattr__(self, "folder_filter", list(self.folder_filter))

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
