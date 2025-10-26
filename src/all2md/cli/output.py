"""Utility functions for cli output."""

#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/cli/output.py
import argparse
import sys
from io import TextIOWrapper

from all2md.exceptions import DependencyError


def check_rich_available() -> bool:
    """Check if Rich library is available.

    Returns
    -------
    bool
        True if Rich is available, False otherwise

    """
    try:
        import rich  # noqa: F401

        return True
    except ImportError:
        return False


def should_use_rich_output(
    args: argparse.Namespace, raise_on_missing: bool = False, stream: TextIOWrapper | None = None
) -> bool:
    """Determine if Rich output should be used based on TTY and args.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command line arguments
    raise_on_missing : bool, default False
        Raise DependencyError if rich is not installed
    stream : optional, default None
        Uses sys.stdout unless otherwise specified.

    Returns
    -------
    bool
        True if Rich output should be used

    Notes
    -----
    Rich output is used when:
    - The --rich flag is set
    - AND either --force-rich is set OR stdout is a TTY
    - AND Rich library is available

    """
    if not args.rich:
        return False

    # Check if Rich is available
    if not check_rich_available():
        if raise_on_missing:
            raise DependencyError(
                converter_name="rich-output",
                missing_packages=[("rich", "")],
                message="Rich output requires the optional 'rich' dependency. Install with: pip install all2md[rich]",
            )
        else:
            return False

    # Force rich output regardless of TTY if explicitly requested
    if hasattr(args, "force_rich") and args.force_rich:
        return True

    target = stream or sys.stdout
    isatty = getattr(target, "isatty", None)
    if callable(isatty):
        try:
            if isatty():
                return True
        except Exception:  # pragma: no cover - defensive: respect failures
            return False

    return False
