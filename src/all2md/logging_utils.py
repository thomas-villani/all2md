"""Centralized logging utilities for all2md entry points."""

from __future__ import annotations

import logging
import sys
from typing import Optional


def configure_logging(
    log_level: int | str,
    log_file: Optional[str] = None,
    trace_mode: bool = False,
) -> logging.Logger:
    """Configure root logging handlers shared across CLI and services.

    Parameters
    ----------
    log_level : int | str
        Numeric logging level or string name (e.g., "INFO").
    log_file : str, optional
        Optional path to a log file for teeing log output.
    trace_mode : bool, default False
        When true, emit timestamps and logger names for debugging traces.

    Returns
    -------
    logging.Logger
        The configured root logger instance.

    """
    resolved_level = log_level if isinstance(log_level, int) else getattr(logging, str(log_level).upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)
    root_logger.handlers.clear()

    format_str = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s" if trace_mode else "%(levelname)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S" if trace_mode else None
    formatter = logging.Formatter(format_str, datefmt=date_format)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(resolved_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
            file_handler.setLevel(resolved_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            root_logger.info("Logging to file: %s", log_file)
        except Exception as exc:  # pragma: no cover - handled at runtime
            root_logger.warning("Could not create log file %s: %s", log_file, exc)

    return root_logger
