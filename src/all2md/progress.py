#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/progress.py
"""Progress callback system for document conversion.

This module provides a standardized way to report conversion progress to embedders,
enabling UI updates during long-running operations like PDF table detection or
multi-page document processing.

Examples
--------
Basic progress tracking:

    >>> from all2md import to_markdown
    >>> from all2md.progress import ProgressEvent
    >>>
    >>> def my_progress_handler(event: ProgressEvent):
    ...     print(f"{event.event_type}: {event.message} ({event.current}/{event.total})")
    >>>
    >>> markdown = to_markdown("document.pdf", progress_callback=my_progress_handler)

Advanced progress handling with metadata:

    >>> def detailed_handler(event: ProgressEvent):
    ...     if event.event_type == "detected" and event.metadata.get("detected_type") == "table":
    ...         print(f"Found {event.metadata['table_count']} tables on page {event.current}")
    ...     elif event.event_type == "error":
    ...         print(f"Error: {event.metadata.get('error', 'Unknown error')}")
    ...     else:
    ...         print(f"{event.message}")
    >>>
    >>> markdown = to_markdown("document.pdf", progress_callback=detailed_handler)

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

# Event type literals for type safety
EventType = Literal["started", "item_done", "detected", "finished", "error"]

# Legacy event types for backward compatibility (deprecated)
# Parsers should use canonical types above
LegacyEventType = Literal["page_done", "table_detected", "tokenization_done", "preamble_parsed", "latex_parsed"]


@dataclass
class ProgressEvent:
    """Progress event for document conversion operations.

    This class represents a single progress event emitted during document conversion.
    Events use a canonical set of event types with documented semantics to ensure
    predictable external integration and consistent progress reporting.

    Parameters
    ----------
    event_type : EventType
        Type of progress event (canonical types):

        - "started": Conversion/parsing has begun
            Use at the start of any conversion operation.
            Set total to expected number of items if known.

        - "item_done": A discrete unit has been completed
            Generic event for any completed unit: page, section, file, stage, etc.
            Use metadata["item_type"] to specify what was completed.
            Examples: page, slide, section, tokenization, preamble, structure

        - "detected": Something discovered during parsing
            Use when finding notable structures during parsing.
            Use metadata["detected_type"] to specify what was detected.
            Examples: table, image, chart, heading, reference

        - "finished": Conversion/parsing completed successfully
            Use at the end of successful conversion.
            Set current=total to indicate completion.

        - "error": An error occurred during conversion
            Use when errors occur. Include details in metadata["error"].
            Conversion may continue after errors for partial results.

    message : str
        Human-readable description of the event
    current : int, default 0
        Current progress position (e.g., current page number, items completed)
    total : int, default 0
        Total items to process (e.g., total pages). Set to 0 if unknown.
    metadata : dict, default empty
        Additional event-specific information:

        - For "started": Optional context about the operation
        - For "item_done": {"item_type": str} - type of item completed
        - For "detected": {"detected_type": str, additional context}
        - For "error": {"error": str, "stage": str, additional context}

    Examples
    --------
    Started event:
        >>> event = ProgressEvent("started", "Converting document.pdf", current=0, total=10)

    Item completed (page):
        >>> event = ProgressEvent(
        ...     "item_done",
        ...     "Page 3 of 10",
        ...     current=3,
        ...     total=10,
        ...     metadata={"item_type": "page"}
        ... )

    Item completed (parsing stage):
        >>> event = ProgressEvent(
        ...     "item_done",
        ...     "Tokenization complete",
        ...     current=30,
        ...     total=100,
        ...     metadata={"item_type": "tokenization"}
        ... )

    Structure detected:
        >>> event = ProgressEvent(
        ...     "detected",
        ...     "Found 2 tables on page 5",
        ...     current=5,
        ...     total=10,
        ...     metadata={"detected_type": "table", "table_count": 2, "page": 5}
        ... )

    Error:
        >>> event = ProgressEvent(
        ...     "error",
        ...     "Failed to parse page 7",
        ...     current=7,
        ...     total=10,
        ...     metadata={"error": "Invalid PDF structure", "stage": "page_parsing", "page": 7}
        ... )

    Finished:
        >>> event = ProgressEvent("finished", "Conversion complete", current=10, total=10)

    Notes
    -----
    Legacy event types ("page_done", "table_detected", "tokenization_done", etc.)
    are deprecated in favor of canonical types with metadata. Parsers should migrate:
    - "page_done" -> "item_done" with metadata={"item_type": "page"}
    - "table_detected" -> "detected" with metadata={"detected_type": "table"}
    - "tokenization_done" -> "item_done" with metadata={"item_type": "tokenization"}

    """

    event_type: EventType
    message: str
    current: int = 0
    total: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """Return human-readable string representation.

        Returns
        -------
        str
            Formatted event description

        """
        progress = f"({self.current}/{self.total})" if self.total > 0 else ""
        return f"[{self.event_type.upper()}] {self.message} {progress}".strip()


# Type alias for progress callback functions
ProgressCallback = Callable[[ProgressEvent], None]
"""Type alias for progress callback functions.

A progress callback is any callable that accepts a ProgressEvent and returns None.
Callbacks should not raise exceptions as this may interrupt conversion.

Examples
--------
    >>> def my_callback(event: ProgressEvent) -> None:
    ...     print(event)
"""
