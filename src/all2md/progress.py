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
    >>> markdown = to_markdown("document.pdf", progress=my_progress_handler)

Advanced progress handling with metadata:

    >>> def detailed_handler(event: ProgressEvent):
    ...     if event.event_type == "table_detected":
    ...         print(f"Found {event.metadata['table_count']} tables on page {event.current}")
    ...     elif event.event_type == "error":
    ...         print(f"Error: {event.metadata.get('error', 'Unknown error')}")
    ...     else:
    ...         print(f"{event.message}")
    >>>
    >>> markdown = to_markdown("document.pdf", progress=detailed_handler)

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

# Event type literals for type safety
EventType = Literal["started", "page_done", "table_detected", "finished", "error"]


@dataclass
class ProgressEvent:
    """Progress event for document conversion operations.

    This class represents a single progress event emitted during document conversion.
    Events track various stages of conversion including start, page completion,
    table detection, completion, and errors.

    Parameters
    ----------
    event_type : EventType
        Type of progress event:
        - "started": Conversion has begun
        - "page_done": A page/section has been processed
        - "table_detected": Table structure detected
        - "finished": Conversion completed successfully
        - "error": An error occurred
    message : str
        Human-readable description of the event
    current : int, default 0
        Current progress position (e.g., current page number)
    total : int, default 0
        Total items to process (e.g., total pages)
    metadata : dict, default empty
        Additional event-specific information:
        - For "table_detected": {"table_count": int, "page": int}
        - For "error": {"error": str, "page": int}
        - For format-specific data: any relevant information

    Examples
    --------
    Started event:
        >>> event = ProgressEvent("started", "Converting document.pdf", current=0, total=10)

    Page completed:
        >>> event = ProgressEvent("page_done", "Page 3 of 10", current=3, total=10)

    Table detected:
        >>> event = ProgressEvent(
        ...     "table_detected",
        ...     "Table found on page 5",
        ...     current=5,
        ...     total=10,
        ...     metadata={"table_count": 2, "page": 5}
        ... )

    Error:
        >>> event = ProgressEvent(
        ...     "error",
        ...     "Failed to parse page 7",
        ...     current=7,
        ...     total=10,
        ...     metadata={"error": "Invalid PDF structure", "page": 7}
        ... )

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
