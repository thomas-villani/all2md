#  Copyright (c) 2025 Tom Villani, Ph.D.
"""``--files-from``: take the input paths from a list rather than the command line.

The flag follows ``tar -T`` / ``rsync --files-from``: the argument names a file holding
one path per line, and ``-`` means standard input, so a picker can feed a command::

    fzf | all2md read --files-from -
    fzf -m --print0 | all2md grep invoice --files-from - --null
    find . -name '*.docx' -print0 | all2md --files-from - --null --output-dir out/

``--null`` reads NUL-separated paths instead (``find -print0``, ``fzf --print0``), the
only separator that cannot occur in a file name. It is spelled out rather than ``-0``:
a digit-shaped option makes argparse read every negative number as an option.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

FILES_FROM_HELP = (
    "Read input paths from FILE, one per line ('#' starts a comment), or from stdin with '-': "
    "`fzf | all2md read --files-from -`. Relative paths resolve against FILE's folder (stdin: the current folder)"
)
NULL_HELP = "With --files-from, paths are separated by NUL characters (find -print0, fzf --print0), not lines"


def add_files_from_arguments(parser: argparse.ArgumentParser | argparse._ArgumentGroup) -> None:
    """Add ``--files-from`` and ``--null`` to a subcommand's parser."""
    parser.add_argument("--files-from", metavar="FILE", default=None, help=FILES_FROM_HELP)
    parser.add_argument("--null", action="store_true", help=NULL_HELP)


def read_files_from(spec: str, *, null: bool = False) -> list[str]:
    """Return the paths listed in ``spec`` (a file, or ``-`` for stdin).

    Parameters
    ----------
    spec : str
        Path of the list file, or ``-`` to read the list from standard input.
    null : bool, default False
        Split on NUL characters rather than lines. Entries are then taken exactly as
        written: no comments, no trimming beyond a trailing newline.

    Returns
    -------
    list of str
        Each listed path, resolved against the list file's folder when relative.

    Raises
    ------
    argparse.ArgumentTypeError
        If the list cannot be read, is empty, or names a path that does not exist.

    """
    from_stdin = spec == "-"
    source = "stdin" if from_stdin else spec
    try:
        if from_stdin:
            if sys.stdin is None:
                raise argparse.ArgumentTypeError("--files-from -: there is no standard input to read")
            text = sys.stdin.buffer.read().decode("utf-8")
            base = Path.cwd()
        else:
            list_path = Path(spec)
            if not list_path.is_file():
                raise argparse.ArgumentTypeError(f"--files-from: list file not found: {spec}")
            text = list_path.read_text(encoding="utf-8")
            base = list_path.parent
    except (OSError, UnicodeDecodeError) as e:
        raise argparse.ArgumentTypeError(f"--files-from: cannot read {source}: {e}") from e

    if null:
        entries = [entry.rstrip("\r\n") for entry in text.split("\0")]
        entries = [entry for entry in entries if entry]
    else:
        entries = [line.strip() for line in text.splitlines()]
        entries = [line for line in entries if line and not line.startswith("#")]

    paths: list[str] = []
    missing: list[str] = []
    for entry in entries:
        path = Path(entry)
        if not path.is_absolute():
            path = base / path
        if not path.exists():
            missing.append(entry)
        paths.append(str(path))
    if missing:
        listed = "\n  ".join(missing)
        raise argparse.ArgumentTypeError(f"--files-from: not found ({source}):\n  {listed}")
    if not paths:
        raise argparse.ArgumentTypeError(f"--files-from: no paths in {source}")
    return paths


def apply_files_from(parsed: argparse.Namespace, dest: str, *, single: bool = False) -> str | None:
    """Merge ``--files-from`` into ``parsed.<dest>``; return an error message, or None.

    Parameters
    ----------
    parsed : argparse.Namespace
        The subcommand's parsed arguments, carrying ``files_from`` and ``null``.
    dest : str
        The positional the paths join: a list (``nargs="*"``), or with ``single`` one
        path (``nargs="?"``).
    single : bool, default False
        The command takes exactly one input; the list must then name exactly one path.

    """
    spec = getattr(parsed, "files_from", None)
    current = getattr(parsed, dest)
    if spec is None:
        if getattr(parsed, "null", False):
            return "--null only applies with --files-from"
        return None
    stdin_named = current == "-" if single else "-" in (current or [])
    if spec == "-" and stdin_named:
        return "'-' cannot be both the document and the --files-from list; both would read stdin"
    try:
        listed = read_files_from(spec, null=parsed.null)
    except argparse.ArgumentTypeError as e:
        return str(e)
    if single:
        if current is not None:
            return "give the input either on the command line or with --files-from, not both"
        if len(listed) != 1:
            return f"this command opens one file, and --files-from listed {len(listed)}"
        setattr(parsed, dest, listed[0])
    else:
        setattr(parsed, dest, [*(current or []), *listed])
    return None


def resolve_files_from(
    parsed: argparse.Namespace, dest: str, *, single: bool = False, required: bool = True
) -> int | None:
    """Apply ``--files-from`` for a subcommand, printing any error.

    Parameters
    ----------
    parsed : argparse.Namespace
        The subcommand's parsed arguments.
    dest : str
        The positional the listed paths join.
    single : bool, default False
        The command takes exactly one input.
    required : bool, default True
        Some input is required. The positional is optional on the command line so
        that ``--files-from`` can supply it, so this restores the check.

    Returns
    -------
    int or None
        The exit code to return, or None to carry on.

    """
    error = apply_files_from(parsed, dest, single=single)
    if error is None and required and not getattr(parsed, dest):
        error = "no input given: name a file, or list them with --files-from"
    if error is None:
        return None
    print(f"Error: {error}", file=sys.stderr)
    return EXIT_VALIDATION_ERROR


#: Mirrors ``all2md.cli.builder.EXIT_VALIDATION_ERROR``; importing the builder here
#: would load the whole parser for every subcommand.
EXIT_VALIDATION_ERROR = 3
