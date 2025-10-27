#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unified progress tracking and summary rendering for CLI.

This module provides abstractions for progress bars and summary tables
that work with rich, tqdm, or plain text output, reducing code duplication
across different processing modes.
"""

from __future__ import annotations

import sys
from typing import Any

from all2md.progress import ProgressCallback, ProgressEvent


class ProgressContext:
    """Unified progress context for rich/tqdm/plain output.

    This class provides a consistent interface for progress tracking
    across different output modes (rich terminal, tqdm, or plain text).

    Parameters
    ----------
    use_rich : bool
        Whether to use Rich library for progress
    use_progress : bool
        Whether to show progress at all (if False, uses plain output)
    total : int
        Total number of items to process
    description : str
        Description for progress bar

    Examples
    --------
    >>> with ProgressContext(use_rich=True, use_progress=True, total=10, description="Processing") as progress:
    ...     for i in range(10):
    ...         # Do work
    ...         progress.update()
    ...         progress.log(f"Processed item {i}", level='info')

    """

    def __init__(self, use_rich: bool, use_progress: bool, total: int, description: str):
        """Initialize progress context."""
        self.use_rich = use_rich
        self.use_progress = use_progress
        self.total = total
        self.description = description

        # Progress tracking state
        self._progress_obj: Any = None
        self._task_id: Any = None
        self._console: Any = None
        self._current = 0

    def __enter__(self) -> ProgressContext:
        """Enter context manager and initialize progress tracking."""
        if self.use_rich and self.use_progress:
            try:
                from rich.console import Console
                from rich.progress import (
                    BarColumn,
                    Progress,
                    SpinnerColumn,
                    TaskProgressColumn,
                    TextColumn,
                )

                self._console = Console()
                self._progress_obj = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=self._console,
                )
                self._progress_obj.__enter__()
                self._task_id = self._progress_obj.add_task(f"[cyan]{self.description}...", total=self.total)
            except ImportError:
                # Fall back to tqdm or plain
                self.use_rich = False
                return self.__enter__()

        elif self.use_progress:
            try:
                from tqdm import tqdm

                # Create tqdm progress bar (will be iterable-like)
                self._progress_obj = tqdm(total=self.total, desc=self.description, unit="item")
            except ImportError:
                # Fall back to plain
                self.use_progress = False
                print(f"{self.description} ({self.total} items)...", file=sys.stderr)

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and cleanup progress tracking."""
        if self._progress_obj is not None:
            if self.use_rich:
                self._progress_obj.__exit__(exc_type, exc_val, exc_tb)
            else:
                # tqdm
                self._progress_obj.close()

    def update(self, advance: int = 1) -> None:
        """Update progress by advancing the specified amount.

        Parameters
        ----------
        advance : int, default=1
            Number of items to advance

        """
        self._current += advance

        if self._progress_obj is not None:
            if self.use_rich:
                self._progress_obj.update(self._task_id, advance=advance)
            else:
                # tqdm
                self._progress_obj.update(advance)

    def log(self, message: str, level: str = "info") -> None:
        """Log a message (with color if using rich).

        Parameters
        ----------
        message : str
            Message to log
        level : str, default='info'
            Log level: 'info', 'success', 'warning', 'error'

        """
        if self.use_rich and self._console:
            # Color-coded messages for rich
            if level == "success":
                self._console.print(f"[green]{message}[/green]")
            elif level == "error":
                self._console.print(f"[red]{message}[/red]")
            elif level == "warning":
                self._console.print(f"[yellow]{message}[/yellow]")
            else:
                self._console.print(message)
        else:
            # Plain text output
            print(message, file=sys.stderr)

    def set_postfix(self, text: str) -> None:
        """Set postfix text for progress bar (tqdm only).

        Parameters
        ----------
        text : str
            Postfix text to display

        """
        if self._progress_obj is not None and not self.use_rich:
            # tqdm has set_postfix_str
            if hasattr(self._progress_obj, "set_postfix_str"):
                self._progress_obj.set_postfix_str(text)


class SummaryRenderer:
    """Render summary tables in rich or plain text.

    This class provides a consistent interface for rendering summary
    tables across different output modes.

    Parameters
    ----------
    use_rich : bool
        Whether to use Rich library for table rendering

    Examples
    --------
    >>> renderer = SummaryRenderer(use_rich=True)
    >>> renderer.render_conversion_summary(successful=45, failed=5, total=50)

    """

    def __init__(self, use_rich: bool):
        """Initialize summary renderer."""
        self.use_rich = use_rich
        self._console: Any = None

        if self.use_rich:
            try:
                from rich.console import Console

                self._console = Console()
            except ImportError:
                self.use_rich = False

    def render_conversion_summary(
        self, successful: int, failed: int, total: int, title: str = "Conversion Summary"
    ) -> None:
        """Render a conversion summary table.

        Parameters
        ----------
        successful : int
            Number of successful conversions
        failed : int
            Number of failed conversions
        total : int
            Total number of files
        title : str, default="Conversion Summary"
            Table title

        """
        if self.use_rich and self._console:
            from rich.table import Table

            table = Table(title=title)
            table.add_column("Status", style="cyan", no_wrap=True)
            table.add_column("Count", style="magenta")

            table.add_row("+ Successful", str(successful))
            table.add_row("- Failed", str(failed))
            table.add_row("Total", str(total))

            self._console.print(table)
        else:
            # Plain text table
            print(f"\n{title}", file=sys.stderr)
            print("=" * 40, file=sys.stderr)
            print(f"  Successful: {successful}", file=sys.stderr)
            print(f"  Failed:     {failed}", file=sys.stderr)
            print(f"  Total:      {total}", file=sys.stderr)

    def render_two_column_table(
        self, rows: list[tuple[str, str]], title: str, col1_header: str = "Item", col2_header: str = "Status"
    ) -> None:
        """Render a generic two-column table.

        Parameters
        ----------
        rows : list[tuple[str, str]]
            List of (column1, column2) tuples
        title : str
            Table title
        col1_header : str, default="Item"
            First column header
        col2_header : str, default="Status"
            Second column header

        """
        if self.use_rich and self._console:
            from rich.table import Table

            table = Table(title=title)
            table.add_column(col1_header, style="cyan")
            table.add_column(col2_header, style="white")

            for col1, col2 in rows:
                table.add_row(col1, col2)

            self._console.print(table)
        else:
            # Plain text table
            print(f"\n{title}", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            print(f"{col1_header:30} {col2_header}", file=sys.stderr)
            print("-" * 60, file=sys.stderr)
            for col1, col2 in rows:
                print(f"{col1:30} {col2}", file=sys.stderr)


def create_progress_context_callback(progress: "ProgressContext") -> "ProgressCallback":
    """Create a callback that feeds progress events into ProgressContext.

    This wrapper translates progress events from parsers and retrievers into
    ProgressContext log messages, providing unified progress tracking across
    the CLI.

    Parameters
    ----------
    progress : ProgressContext
        The progress context to feed events into

    Returns
    -------
    ProgressCallback
        Callback function that handles progress events

    Examples
    --------
    >>> with ProgressContext(use_rich=True, use_progress=True, total=10, description="Processing") as progress:
    ...     callback = create_progress_context_callback(progress)
    ...     to_markdown("document.pdf", progress_callback=callback)

    """

    def callback(event: ProgressEvent) -> None:
        """Handle progress event and log to context."""
        if event.event_type == "started":
            if event.metadata.get("item_type") == "download":
                url = event.metadata.get("url", "")
                progress.log(f"Downloading: {url}", level="info")
        elif event.event_type == "item_done":
            if event.metadata.get("item_type") == "download":
                url = event.metadata.get("url", "")
                bytes_count = event.metadata.get("bytes", 0)
                size_kb = bytes_count / 1024 if bytes_count else 0
                progress.log(f"Downloaded: {url} ({size_kb:.1f} KB)", level="success")
        elif event.event_type == "error":
            if event.metadata.get("stage") == "download":
                url = event.metadata.get("url", "")
                error = event.metadata.get("error", "Unknown error")
                progress.log(f"Download failed: {url} - {error}", level="error")

    return callback


__all__ = ["ProgressContext", "SummaryRenderer", "create_progress_context_callback"]
