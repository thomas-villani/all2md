#  Copyright (c) 2025 Tom Villani, Ph.D.
# ${DIR_PATH}/${FILE_NAME}
"""Shared utilities for all2md CLI commands.

This module provides common functionality used across multiple CLI commands,
including input file collection from various sources (filesystem, URIs, stdin),
version information, system diagnostics, and batch file list parsing.
"""

import argparse
import contextlib
import fnmatch
import logging
import os
import platform
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import unquote, urlparse

from all2md.cli.input_items import CLIInputItem
from all2md.converter_registry import registry
from all2md.utils.packages import check_version_requirement, get_package_version

_GLOB_CHARS = "*?["


@contextlib.contextmanager
def protect_stdout() -> Iterator[None]:
    """Redirect OS-level stdout (fd 1) to stderr for the duration.

    Some libraries in the conversion pipeline (notably PyMuPDF) print advisories
    straight to stdout, which would corrupt a command's own output stream --
    especially a machine-readable ``--json`` one. We point fd 1 at stderr while
    parsing, then restore it before emitting results. This catches both
    Python-level ``print`` and C-level writes. Falls back to a no-op if fd
    duplication is unavailable (e.g. a captured stdout with no real descriptor).
    """
    try:
        saved_fd = os.dup(1)
    except (OSError, ValueError):
        yield
        return
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        os.dup2(2, 1)
        yield
    finally:
        sys.stdout.flush()
        os.dup2(saved_fd, 1)
        os.close(saved_fd)


def add_cache_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the shared opt-in conversion-cache flags to a subcommand parser.

    Commands that convert documents (grep, search, chunk, view, serve) share this
    so the flag names and help text stay consistent.
    """
    group = parser.add_argument_group("Conversion cache")
    group.add_argument(
        "--cache",
        action="store_true",
        default=False,
        help=(
            "Reuse parsed documents from an on-disk cache, skipping re-conversion of "
            "unchanged files (keyed by content signature + options). Also enabled by "
            "ALL2MD_CACHE=1."
        ),
    )
    group.add_argument(
        "--cache-dir",
        metavar="DIR",
        default=None,
        help="Directory for the conversion cache (default: per-OS user cache dir, or $ALL2MD_CACHE_DIR).",
    )


def conversion_cache_from_args(parsed: "argparse.Namespace") -> Any:
    """Return the ``use_conversion_cache`` context configured from parsed args.

    ``--cache`` forces caching on; without it the ``ALL2MD_CACHE`` environment
    variable still applies (``enabled=None`` defers to the env). Safe to call on a
    namespace lacking the attributes (returns an inert, disabled context).
    """
    from all2md.conversion_cache import use_conversion_cache

    enabled = True if getattr(parsed, "cache", False) else None
    return use_conversion_cache(enabled=enabled, cache_dir=getattr(parsed, "cache_dir", None))


def split_glob_pattern(raw: str) -> tuple[Path, str, bool]:
    """Split a glob pattern into ``(anchor_dir, name_pattern, recursive)``.

    The anchor is the longest leading run of path components that contain no
    glob metacharacters; it is the concrete directory the pattern is rooted in.
    ``name_pattern`` is the trailing filename component (an ``fnmatch`` pattern),
    and ``recursive`` is ``True`` when the pattern contains a ``**`` segment.

    Examples
    --------
    ``subdir/*.docx``     -> ``(Path('subdir'), '*.docx', False)``
    ``subdir/**/*.docx``  -> ``(Path('subdir'), '*.docx', True)``
    ``*.docx``            -> ``(Path('.'), '*.docx', False)``

    """
    parts = Path(raw).parts
    anchor_parts: list[str] = []
    remainder: list[str] = []
    hit_wildcard = False
    for part in parts:
        if not hit_wildcard and not any(char in part for char in _GLOB_CHARS):
            anchor_parts.append(part)
        else:
            hit_wildcard = True
            remainder.append(part)

    anchor = Path(*anchor_parts) if anchor_parts else Path(".")
    name_pattern = Path(raw).name or "*"
    recursive = "**" in remainder
    return anchor, name_pattern, recursive


def has_hidden_component(path: Path, root: Path) -> bool:
    """Return ``True`` if ``path`` has a dot-prefixed component below ``root``.

    Only components *discovered* relative to ``root`` are considered, so an
    explicitly provided hidden root (e.g. ``.config/``) does not by itself mark
    everything underneath as hidden.
    """
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = Path(path.name)
    return any(part.startswith(".") for part in rel.parts)


def _handle_stdin_input(stdin_data_ref: list[bytes | None], raw_argument: str) -> Optional[CLIInputItem]:
    """Process stdin input and return CLIInputItem if valid.

    Parameters
    ----------
    stdin_data_ref : list[bytes | None]
        Reference to stdin data buffer (single-element list for mutability)
    raw_argument : str
        Original argument string

    Returns
    -------
    CLIInputItem or None
        CLIInputItem for stdin or None if empty/already processed

    """
    if stdin_data_ref[0] is None:
        stdin_data_ref[0] = sys.stdin.buffer.read()

    stdin_data = stdin_data_ref[0]
    if stdin_data and len(stdin_data) > 0:
        return CLIInputItem(
            raw_input=stdin_data,
            kind="stdin_bytes",
            display_name="<stdin>",
            original_argument=raw_argument,
        )
    return None


def _handle_remote_uri_input(raw_argument: str, remote_items: Dict[str, CLIInputItem]) -> bool:
    """Process remote URI input and add to remote_items dict.

    Parameters
    ----------
    raw_argument : str
        Original argument string
    remote_items : dict
        Dictionary of remote items keyed by normalized URI

    Returns
    -------
    bool
        True if URI was processed and added (or duplicate), False if not a URI

    """
    if not _is_probable_uri(raw_argument):
        return False

    path_hint, metadata = _derive_path_hint_from_uri(raw_argument)
    key = _normalize_uri_key(raw_argument)
    if key not in remote_items:
        remote_items[key] = CLIInputItem(
            raw_input=raw_argument,
            kind="remote_uri",
            display_name=raw_argument,
            path_hint=path_hint,
            original_argument=raw_argument,
            metadata=metadata,
        )
    return True


def _handle_local_path_input(
    raw_argument: str,
    recursive: bool,
    extension_allowed: Any,
    include_hidden: bool = False,
) -> List[Path]:
    """Process local path input (file, directory, or glob) and return matched files.

    Parameters
    ----------
    raw_argument : str
        Original argument string (path or glob pattern)
    recursive : bool
        Whether to process directories recursively
    extension_allowed : callable
        Function to check if path extension is allowed
    include_hidden : bool
        Whether to include dot-files/dot-folders discovered during directory or
        glob expansion. Explicitly named files are always included.

    Returns
    -------
    list[Path]
        List of matched file paths that pass extension filter

    """
    input_path = Path(raw_argument)
    matched_paths: List[Path] = []

    # Handle glob patterns
    if any(char in raw_argument for char in _GLOB_CHARS):
        anchor, _, _ = split_glob_pattern(raw_argument)
        hidden_root = Path.cwd() / anchor
        for match in Path.cwd().glob(raw_argument):
            if include_hidden or not has_hidden_component(match, hidden_root):
                matched_paths.append(match)
    # Handle single file
    elif input_path.is_file():
        matched_paths.append(input_path)
    # Handle directory
    elif input_path.is_dir():
        iterator = input_path.rglob("*") if recursive else input_path.iterdir()
        for child in iterator:
            if child.is_file() and (include_hidden or not has_hidden_component(child, input_path)):
                matched_paths.append(child)
    else:
        logging.warning(f"Path does not exist: {input_path}")
        return []

    # Filter by extension and file status
    filtered_paths: List[Path] = []
    for candidate in matched_paths:
        if candidate.is_file() and extension_allowed(candidate):
            filtered_paths.append(candidate)

    return filtered_paths


def _deduplicate_and_create_items(
    local_candidates: List[Path],
) -> List[CLIInputItem]:
    """Deduplicate local paths and create CLIInputItem objects.

    Parameters
    ----------
    local_candidates : list[Path]
        List of local file paths (may contain duplicates)

    Returns
    -------
    list[CLIInputItem]
        Sorted list of unique CLIInputItem objects

    """
    # Deduplicate by resolved path
    unique_local: Dict[str, Path] = {}
    for candidate in local_candidates:
        try:
            key = str(candidate.resolve())
        except OSError:
            key = str(candidate)
        unique_local[key] = candidate

    sorted_local_paths = sorted(unique_local.values())

    return [
        CLIInputItem(
            raw_input=path,
            kind="local_file",
            display_name=path.as_posix(),
            path_hint=path,
            original_argument=str(path),
        )
        for path in sorted_local_paths
    ]


def collect_input_files(
    input_paths: List[str],
    recursive: bool = False,
    extensions: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    include_hidden: bool = False,
) -> List[CLIInputItem]:
    """Collect CLI input items from provided arguments.

    Supports local filesystem paths, directories, shell globs, URIs, and stdin.
    Local paths are expanded to files, filtered by extension when requested, and
    deduplicated. Remote inputs are preserved as strings to maintain compatibility
    with the document loader infrastructure.

    Dot-files and dot-folders discovered while scanning directories or expanding
    globs are skipped unless ``include_hidden`` is ``True``. Explicitly named
    files are always included.
    """
    if extensions is None:
        # Get all supported extensions dynamically from registry
        extensions = list(registry.get_all_extensions())

    normalized_exts = {ext.lower() for ext in extensions} if extensions else None

    def extension_allowed(path: Path) -> bool:
        if normalized_exts is None:
            return True
        return path.suffix.lower() in normalized_exts

    local_candidates: List[Path] = []
    remote_items: Dict[str, CLIInputItem] = {}
    stdin_item: Optional[CLIInputItem] = None
    stdin_data_ref: list[bytes | None] = [None]  # Use list for mutability in helper

    # Process each input argument
    for raw_argument in input_paths:
        # Handle stdin
        if raw_argument == "-":
            if stdin_item is None:
                stdin_item = _handle_stdin_input(stdin_data_ref, raw_argument)
            continue

        # Handle remote URIs
        if _handle_remote_uri_input(raw_argument, remote_items):
            continue

        # Handle local paths (files, directories, globs)
        matched_files = _handle_local_path_input(raw_argument, recursive, extension_allowed, include_hidden)
        local_candidates.extend(matched_files)

    # Deduplicate and create items
    local_items = _deduplicate_and_create_items(local_candidates)

    # Combine all items
    all_items: List[CLIInputItem] = []
    all_items.extend(remote_items.values())
    all_items.extend(local_items)
    if stdin_item is not None:
        all_items.append(stdin_item)

    # Apply exclusion patterns
    if exclude_patterns:
        all_items = [
            item for item in all_items if not any(_matches_exclusion(item, pattern) for pattern in exclude_patterns)
        ]

    # Deterministic ordering for downstream processing
    all_items.sort(key=lambda item: item.display_name.lower())

    return all_items


def _is_probable_uri(candidate: str) -> bool:
    """Return True when the candidate string looks like a URI input."""
    if "://" not in candidate:
        lowered = candidate.lower()
        return lowered.startswith("http:/") or lowered.startswith("https:/")

    parsed = urlparse(candidate)
    return bool(parsed.scheme and parsed.netloc)


def _derive_path_hint_from_uri(uri: str) -> tuple[Path | None, dict[str, str]]:
    """Extract best-effort Path hint and metadata from a URI."""
    parsed = urlparse(uri)
    metadata: dict[str, str] = {}
    if parsed.netloc:
        metadata["remote_host"] = parsed.netloc

    path_text = unquote(parsed.path or "")
    if not path_text:
        return None, metadata

    name = Path(path_text).name
    if not name:
        return None, metadata

    return Path(name), metadata


def _normalize_uri_key(uri: str) -> str:
    """Return a normalized key for URI de-duplication."""
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or ""
    # Preserve query/fragment as they affect resource identity
    query = f"?{parsed.query}" if parsed.query else ""
    fragment = f"#{parsed.fragment}" if parsed.fragment else ""
    return f"{scheme}://{netloc}{path}{query}{fragment}"


def _matches_exclusion(item: CLIInputItem, pattern: str) -> bool:
    """Check if the item should be excluded based on the provided glob pattern."""
    candidates = [item.display_name]

    if item.path_hint:
        candidates.append(str(item.path_hint))
        candidates.append(item.path_hint.name)

    best_path = item.best_path()
    if best_path:
        candidates.append(str(best_path))
        try:
            relative = best_path.relative_to(Path.cwd())
            candidates.append(str(relative))
        except ValueError:
            pass
        candidates.append(best_path.name)

    return any(fnmatch.fnmatch(candidate, pattern) for candidate in candidates)


def get_version() -> str:
    """Get the version of all2md package."""
    try:
        return version("all2md")
    except Exception:
        return "unknown"


def get_about_info() -> str:
    """Get detailed information about all2md including system info and dependencies."""
    version_str = get_version()

    # System information
    python_version = platform.python_version()
    python_path = sys.executable
    os_info = platform.platform()
    architecture = platform.machine()

    # Get dependency information
    registry.auto_discover()
    formats = registry.list_formats()

    # Count available formats
    available_formats = []
    unavailable_formats = []

    for format_name in formats:
        metadata_list = registry.get_format_info(format_name)
        if not metadata_list or len(metadata_list) == 0:
            continue

        # Use the highest priority (first) converter
        metadata = metadata_list[0]

        # Check if all dependencies are satisfied
        all_available = True
        if metadata.required_packages:
            for install_name, _import_name, version_spec in metadata.required_packages:
                if version_spec:
                    meets_req, _ = check_version_requirement(install_name, version_spec)
                    if not meets_req:
                        all_available = False
                        break
                else:
                    installed_version = get_package_version(install_name)
                    if not installed_version:
                        all_available = False
                        break

        if all_available:
            available_formats.append(format_name)
        else:
            unavailable_formats.append(format_name)

    # Get unique dependencies across all formats
    all_deps = {}
    for format_name in formats:
        metadata_list = registry.get_format_info(format_name)
        if metadata_list and len(metadata_list) > 0:
            # Use the highest priority (first) converter
            metadata = metadata_list[0]
            if metadata.required_packages:
                for install_name, _import_name, version_spec in metadata.required_packages:
                    if install_name not in all_deps:
                        installed_version = get_package_version(install_name)
                        if version_spec:
                            meets_req, _ = check_version_requirement(install_name, version_spec)
                            status = "installed" if meets_req else "version_mismatch"
                        else:
                            meets_req = installed_version is not None
                            status = "installed" if meets_req else "not_installed"

                        all_deps[install_name] = {
                            "version": installed_version,
                            "required": version_spec,
                            "status": status,
                        }

    # Build dependency report
    dep_lines = []
    for pkg_name, dep_info in sorted(all_deps.items()):
        if dep_info["status"] == "installed":
            check = "✓"
            version_info = f"{dep_info['version']}"
            if dep_info["required"]:
                version_info += f" (required: {dep_info['required']})"
        elif dep_info["status"] == "version_mismatch":
            check = "✗"
            version_info = f"{dep_info['version']} (required: {dep_info['required']})"
        else:
            check = "✗"
            version_info = "not installed"

        dep_lines.append(f"  {check} {pkg_name:20} {version_info}")

    dependencies_report = "\n".join(dep_lines) if dep_lines else "  (none)"

    # Build format availability report
    total_formats = len(available_formats) + len(unavailable_formats)
    available_count = len(available_formats)

    return f"""all2md {version_str}

A Python document conversion library for transformation
between various file formats and Markdown.

System Information:
  Python:        {python_version} ({python_path})
  Platform:      {os_info}
  Architecture:  {architecture}

Installed Dependencies ({len([d for d in all_deps.values() if d["status"] == "installed"])}/{len(all_deps)}):
{dependencies_report}

Available Formats ({available_count}/{total_formats} ready):
  Ready:   {", ".join(sorted(available_formats))}
  Missing: {", ".join(sorted(unavailable_formats)) if unavailable_formats else "(none)"}

Features:
  • Advanced PDF parsing with table detection
  • AST-based transformation pipeline
  • Plugin system for custom transforms
  • Intelligent format detection from content
  • Configurable Markdown output options
  • Attachment handling (save, embed, skip)
  • Command-line interface with stdin support
  • Python API for programmatic use
  • Multi-file and directory processing
  • Rich terminal output and progress bars

Install all dependencies: pip install all2md[all]
Install specific format:  pip install all2md[pdf,docx,html]

Documentation: https://github.com/thomas.villani/all2md
License: MIT License
Author: Thomas Villani <thomas.villani@njii.com>"""


def parse_batch_list(list_path: Path | str) -> List[str]:
    """Parse batch list file and return file paths.

    Parameters
    ----------
    list_path : Path or str
        Path to the list file containing file paths (one per line), or '-' to read from stdin

    Returns
    -------
    List[str]
        List of file path strings ready for collect_input_files()

    Raises
    ------
    argparse.ArgumentTypeError
        If the list file cannot be read or contains invalid entries

    Notes
    -----
    List file format:
    - One file path per line
    - Lines starting with # are comments
    - Blank lines are ignored
    - File paths are resolved relative to the list file directory (or cwd if stdin)
    - All paths are validated to exist
    - Use '-' as the path to read the list from stdin

    Examples
    --------
    List file content:

        # Input files for processing
        chapter1.pdf
        chapter2.pdf
        /absolute/path/to/file.docx

    Reading from stdin:

        $ echo "file1.pdf" | all2md --batch-from-list - --output-dir ./out

    """
    try:
        # Check if reading from stdin
        if list_path == "-" or str(list_path) == "-":
            # Read from stdin
            lines = sys.stdin.readlines()
            # Resolve paths relative to current working directory
            list_dir = Path.cwd()
            source_desc = "stdin"
        else:
            # Read from file
            list_path = Path(list_path)
            if not list_path.exists():
                raise argparse.ArgumentTypeError(f"Batch list file does not exist: {list_path}")

            with open(list_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Resolve paths relative to list file directory
            list_dir = list_path.parent
            source_desc = str(list_path)

        # Parse entries
        file_paths: List[str] = []

        for line_num, line in enumerate(lines, 1):
            # Strip whitespace
            line = line.strip()

            # Skip comments and blank lines
            if not line or line.startswith("#"):
                continue

            # Use the line as the file path (no separator like in merge-from-list)
            file_path_str = line

            # Resolve file path (relative to list file directory)
            file_path = Path(file_path_str)
            if not file_path.is_absolute():
                file_path = list_dir / file_path

            # Validate file exists
            if not file_path.exists():
                raise argparse.ArgumentTypeError(
                    f"File not found in batch list (line {line_num}): {file_path_str}\nResolved path: {file_path}"
                )

            # Add to list as string (collect_input_files expects strings)
            file_paths.append(str(file_path))

        if not file_paths:
            raise argparse.ArgumentTypeError(f"Batch list is empty or contains no valid entries: {source_desc}")

        return file_paths

    except argparse.ArgumentTypeError:
        raise
    except Exception as e:
        source_desc = "stdin" if (list_path == "-" or str(list_path) == "-") else str(list_path)
        raise argparse.ArgumentTypeError(f"Error reading batch list from {source_desc}: {e}") from e
