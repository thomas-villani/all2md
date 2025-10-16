"""Timing and instrumentation utilities for all2md CLI.

This module provides utilities for timing operations and logging performance
metrics in trace mode.
"""

import functools
import logging
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional, TypeVar

logger = logging.getLogger(__name__)

# Type variable for generic function decoration
F = TypeVar("F", bound=Callable[..., Any])


class TimingContext:
    """Context manager for timing operations with automatic logging.

    Parameters
    ----------
    operation_name : str
        Name of the operation being timed
    logger_instance : logging.Logger, optional
        Logger to use for output. If None, uses module logger
    log_level : int, default logging.DEBUG
        Log level for timing messages

    Examples
    --------
    >>> with TimingContext("PDF parsing"):
    ...     parse_pdf(document)
    [DEBUG] PDF parsing completed in 2.45s

    """

    def __init__(
        self, operation_name: str, logger_instance: Optional[logging.Logger] = None, log_level: int = logging.DEBUG
    ) -> None:
        """Initialize the timing context for an operation."""
        self.operation_name = operation_name
        self.logger = logger_instance or logger
        self.log_level = log_level
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def __enter__(self) -> "TimingContext":
        """Enter the timing context and start the timer."""
        self.start_time = time.perf_counter()
        self.logger.log(self.log_level, f"Starting: {self.operation_name}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the timing context and log the elapsed time."""
        self.end_time = time.perf_counter()
        elapsed = self.elapsed

        if exc_type is None:
            self.logger.log(self.log_level, f"{self.operation_name} completed in {elapsed:.2f}s")
        else:
            self.logger.log(self.log_level, f"{self.operation_name} failed after {elapsed:.2f}s")

    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds.

        Returns
        -------
        float
            Elapsed time in seconds

        """
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time is not None else time.perf_counter()
        return end - self.start_time


def instrument_timing(
    operation_name: Optional[str] = None,
    logger_instance: Optional[logging.Logger] = None,
    log_level: int = logging.DEBUG,
) -> Callable[[F], F]:
    """Automatically time and log function execution.

    Parameters
    ----------
    operation_name : str, optional
        Name for the operation. If None, uses function name
    logger_instance : logging.Logger, optional
        Logger to use. If None, uses module logger
    log_level : int, default logging.DEBUG
        Log level for timing messages

    Returns
    -------
    Callable
        Decorated function with timing instrumentation

    Examples
    --------
    >>> @instrument_timing("PDF conversion")
    ... def convert_pdf(path):
    ...     return process(path)

    """

    def decorator(func: F) -> F:
        op_name = operation_name or func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with TimingContext(op_name, logger_instance, log_level):
                return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


@contextmanager
def timing(
    operation_name: str, logger_instance: Optional[logging.Logger] = None
) -> Generator[TimingContext, None, None]:
    """Context manager for timing operations.

    Parameters
    ----------
    operation_name : str
        Name of the operation being timed
    logger_instance : logging.Logger, optional
        Logger to use for output

    Yields
    ------
    TimingContext
        Timing context with elapsed time tracking

    Examples
    --------
    >>> with timing("File processing") as timer:
    ...     process_files()
    ...     print(f"Processed in {timer.elapsed:.2f}s")

    """
    with TimingContext(operation_name, logger_instance) as ctx:
        yield ctx


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format.

    Parameters
    ----------
    seconds : float
        Duration in seconds

    Returns
    -------
    str
        Formatted duration string

    Examples
    --------
    >>> format_duration(0.123)
    '123ms'
    >>> format_duration(65.5)
    '1m 5.5s'
    >>> format_duration(3665)
    '1h 1m 5s'

    """
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.0f}µs"
    elif seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs:.0f}s"


class OperationTimer:
    """Timer for tracking multiple operations with cumulative stats.

    Examples
    --------
    >>> timer = OperationTimer()
    >>> timer.start("parsing")
    >>> # ... do work ...
    >>> timer.stop("parsing")
    >>> timer.start("rendering")
    >>> # ... do work ...
    >>> timer.stop("rendering")
    >>> timer.report()

    """

    def __init__(self) -> None:
        """Initialize the operation timer with empty tracking dictionaries."""
        self.operations: dict[str, list[float]] = {}
        self._active: dict[str, float] = {}

    def start(self, operation_name: str) -> None:
        """Start timing an operation.

        Parameters
        ----------
        operation_name : str
            Name of the operation

        """
        self._active[operation_name] = time.perf_counter()

    def stop(self, operation_name: str) -> float:
        """Stop timing an operation and record duration.

        Parameters
        ----------
        operation_name : str
            Name of the operation

        Returns
        -------
        float
            Duration in seconds

        Raises
        ------
        ValueError
            If operation was not started

        """
        if operation_name not in self._active:
            raise ValueError(f"Operation '{operation_name}' was not started")

        start_time = self._active.pop(operation_name)
        duration = time.perf_counter() - start_time

        if operation_name not in self.operations:
            self.operations[operation_name] = []
        self.operations[operation_name].append(duration)

        return duration

    def get_stats(self, operation_name: str) -> dict[str, float]:
        """Get statistics for an operation.

        Parameters
        ----------
        operation_name : str
            Name of the operation

        Returns
        -------
        dict[str, float]
            Statistics including total, count, mean, min, max

        """
        if operation_name not in self.operations:
            return {"total": 0.0, "count": 0, "mean": 0.0, "min": 0.0, "max": 0.0}

        durations = self.operations[operation_name]
        return {
            "total": sum(durations),
            "count": len(durations),
            "mean": sum(durations) / len(durations),
            "min": min(durations),
            "max": max(durations),
        }

    def report(self, logger_instance: Optional[logging.Logger] = None) -> str:
        """Generate timing report.

        Parameters
        ----------
        logger_instance : logging.Logger, optional
            Logger to output report to

        Returns
        -------
        str
            Formatted timing report

        """
        log = logger_instance or logger

        lines = ["Timing Report", "=" * 60]

        for op_name, _durations in sorted(self.operations.items()):
            stats = self.get_stats(op_name)
            lines.append(
                f"{op_name:30} {format_duration(stats['total']):>12} "
                f"({stats['count']:>3} calls, avg: {format_duration(stats['mean'])})"
            )

        report = "\n".join(lines)
        log.info(report)
        return report
