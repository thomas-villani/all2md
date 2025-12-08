#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/decorators.py
"""Utility decorators for all2md parsers and renderers.

This module provides reusable decorators that eliminate code duplication
across parsers and renderers, particularly for dependency management.

"""

from __future__ import annotations

import importlib
import logging
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator, List, Tuple

from all2md.exceptions import DependencyError
from all2md.utils.packages import check_version_requirement


def requires_dependencies(converter_name: str, packages: List[Tuple[str, str, str]]) -> Callable:
    """Check required dependencies and versions before method execution.

    This decorator eliminates repeated try/except ImportError blocks across
    parsers and renderers by centralizing dependency checking logic. It validates
    both package availability and version requirements, raising a DependencyError
    with helpful installation instructions if any dependencies are missing or
    have incompatible versions.

    Parameters
    ----------
    converter_name : str
        Name of the converter (e.g., "pdf", "docx", "html"). This appears
        in error messages to help users identify which converter needs dependencies.
    packages : list of tuple
        Required packages as (install_name, import_name, version_spec) tuples where:
        - install_name: Package name for pip install (e.g., "pymupdf")
        - import_name: Module name for import statement (e.g., "fitz")
        - version_spec: Version requirement (e.g., ">=1.26.4" or "" for any version)

    Returns
    -------
    Callable
        Decorated method that checks dependencies before execution

    Raises
    ------
    DependencyError
        If any required package is missing or has an incompatible version.
        The error includes:
        - List of missing packages
        - List of version mismatches (package, required version, installed version)
        - Installation command
        - Original ImportError for debugging

    Examples
    --------
    Apply to a parser's parse method:

        >>> @requires_dependencies("pdf", [("pymupdf", "fitz", ">=1.26.4")])
        ... def parse(self, input_data):
        ...     import fitz
        ...     # parsing logic here

    Apply to a renderer's render method:

        >>> @requires_dependencies("docx", [("python-docx", "docx", ">=1.2.0")])
        ... def render(self, doc, output):
        ...     from docx import Document
        ...     # rendering logic here

    Multiple dependencies:

        >>> @requires_dependencies("html", [
        ...     ("beautifulsoup4", "bs4", ">=4.9.0"),
        ...     ("lxml", "lxml", "")
        ... ])
        ... def parse(self, input_data):
        ...     import bs4
        ...     import lxml
        ...     # parsing logic here

    Notes
    -----
    - The decorator preserves the original ImportError for debugging
    - Uses importlib.import_module for standard, safe importing
    - Validates version requirements using packaging.specifiers
    - Collects all missing packages and version mismatches before raising error
    - Works with both parsers and renderers
    - Compatible with type hints and IDE autocomplete

    """

    def decorator(method: Callable) -> Callable:
        @wraps(method)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            missing = []
            version_mismatches = []
            original_error = None

            # Check each required package
            for install_name, import_name, version_spec in packages:
                try:
                    # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
                    importlib.import_module(import_name)

                    # If version spec is provided, validate the version
                    if version_spec:
                        meets_requirement, installed_version = check_version_requirement(install_name, version_spec)
                        if not meets_requirement:
                            # Package is installed but version doesn't match
                            version_str = installed_version or "unknown"
                            version_mismatches.append((install_name, version_spec, version_str))

                except ImportError as e:
                    # Package is not installed at all
                    missing.append((install_name, version_spec))
                    # Capture first import error for debugging
                    if original_error is None:
                        original_error = e

            # If any packages are missing or have version mismatches, raise comprehensive error
            if missing or version_mismatches:
                raise DependencyError(
                    converter_name=converter_name,
                    missing_packages=missing,
                    version_mismatches=version_mismatches,
                    original_import_error=original_error,
                ) from original_error

            # All dependencies present with correct versions, execute the method
            return method(*args, **kwargs)

        return wrapper

    return decorator


@contextmanager
def debug_timer(logger: logging.Logger, operation: str) -> Generator[None, None, None]:
    """Context manager for timing operations with DEBUG-level logging.

    This context manager eliminates duplicated timing code patterns where
    operations are timed only when DEBUG logging is enabled. It automatically
    measures elapsed time and logs the result.

    Parameters
    ----------
    logger : logging.Logger
        Logger instance to use for DEBUG messages
    operation : str
        Description of the operation being timed (e.g., "Parsing (pdf)")

    Yields
    ------
    None
        Control flow to the code block being timed

    Examples
    --------
    Basic usage with automatic timing:

        >>> logger = logging.getLogger(__name__)
        >>> with debug_timer(logger, "Parsing (pdf)"):
        ...     result = parser.parse(document)
        ... # Logs: "Parsing (pdf) completed in 1.23s" at DEBUG level

    Replacing duplicated if/else blocks:

        >>> # Before:
        >>> if logger.isEnabledFor(logging.DEBUG):
        ...     start_time = time.perf_counter()
        ...     result = expensive_operation()
        ...     elapsed = time.perf_counter() - start_time
        ...     logger.debug(f"Operation completed in {elapsed:.2f}s")
        ... else:
        ...     result = expensive_operation()
        >>>
        >>> # After:
        >>> with debug_timer(logger, "Operation"):
        ...     result = expensive_operation()

    Notes
    -----
    - Only measures time when logger has DEBUG level enabled
    - Uses perf_counter for high-resolution timing
    - Formats elapsed time to 2 decimal places
    - Zero overhead when DEBUG logging is disabled

    """
    if logger.isEnabledFor(logging.DEBUG):
        start_time = time.perf_counter()
        yield
        elapsed = time.perf_counter() - start_time
        logger.debug(f"{operation} completed in {elapsed:.2f}s")
    else:
        yield
