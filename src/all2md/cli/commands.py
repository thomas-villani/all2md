#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/cli/commands.py
"""CLI command handlers and utilities for all2md.

This module provides command-line interface implementation for the all2md
document conversion library, including command handlers, version info,
and system diagnostics.
"""

import argparse
import fnmatch
import json
import logging
import os
import platform
import sys
import textwrap
from dataclasses import fields, is_dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import unquote, urlparse

from all2md.cli.builder import (
    EXIT_DEPENDENCY_ERROR,
    EXIT_ERROR,
    EXIT_FILE_ERROR,
    EXIT_SUCCESS,
    EXIT_VALIDATION_ERROR,
    DynamicCLIBuilder,
)
from all2md.cli.config import get_config_search_paths, load_config_file, load_config_with_priority
from all2md.cli.help_formatter import display_help
from all2md.cli.input_items import CLIInputItem
from all2md.cli.processors import (
    process_multi_file,
    setup_and_validate_options,
)
from all2md.cli.validation import (
    validate_arguments,
)
from all2md.converter_registry import registry
from all2md.dependencies import main as deps_main
from all2md.exceptions import DependencyError
from all2md.logging_utils import configure_logging as configure_root_logging
from all2md.options.search import SearchOptions
from all2md.renderers.markdown import MarkdownRenderer
from all2md.search import SearchDocumentInput, SearchMode, SearchResult, SearchService
from all2md.transforms import transform_registry as transform_registry
from all2md.utils.attachments import ensure_unique_attachment_path
from all2md.utils.packages import check_version_requirement, get_package_version
from all2md.utils.static_site import (
    FrontmatterFormat,
    FrontmatterGenerator,
    SiteScaffolder,
    StaticSiteGenerator,
    copy_document_assets,
    generate_output_filename,
)

logger = logging.getLogger(__name__)


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


def _serialize_config_value(value: Any) -> Any:
    """Convert dataclass default values into config-friendly primitives."""
    if is_dataclass(value):
        result: Dict[str, Any] = {}
        for field in fields(value):
            serialized = _serialize_config_value(getattr(value, field.name))
            if serialized is None:
                continue
            result[field.name] = serialized
        return result

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        items = {}
        for k, v in value.items():
            serialized = _serialize_config_value(v)
            if serialized is None:
                continue
            items[str(k)] = serialized
        return items

    if isinstance(value, (list, tuple, set)):
        serialized_items = [_serialize_config_value(v) for v in value]
        return [item for item in serialized_items if item is not None]

    if hasattr(value, "value") and not isinstance(value, (str, bytes)):
        try:
            return _serialize_config_value(value.value)
        except AttributeError:  # pragma: no cover - defensive
            pass

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


def _collect_defaults_from_options_class(options_class: Optional[type]) -> Dict[str, Any]:
    """Instantiate an options dataclass and extract CLI-relevant defaults."""
    if options_class is None or not is_dataclass(options_class):
        return {}

    try:
        instance = options_class()
    except (TypeError, ValueError):
        logger.debug("Skipping %s: could not instantiate without arguments", options_class)
        return {}

    defaults: Dict[str, Any] = {}

    for field in fields(instance):
        metadata: Dict[str, Any] = dict(field.metadata) if field.metadata else {}
        if metadata.get("exclude_from_cli", False):
            continue

        serialized = _serialize_config_value(getattr(instance, field.name))
        if serialized is None:
            continue

        if isinstance(serialized, dict) and not serialized:
            continue

        if isinstance(serialized, list) and not serialized:
            continue

        defaults[field.name] = serialized

    return defaults


def _build_default_config_data() -> Dict[str, Any]:
    """Assemble default configuration from registered option classes."""
    builder = DynamicCLIBuilder()
    options_map = builder.get_options_class_map()
    config: Dict[str, Any] = {}

    base_defaults = _collect_defaults_from_options_class(options_map.get("base"))
    config.update(base_defaults)

    ordered_keys = sorted(options_map.keys())
    for key in ordered_keys:
        if key == "base":
            continue

        defaults = _collect_defaults_from_options_class(options_map.get(key))
        if defaults:
            config[key] = defaults

    config["search"] = _serialize_config_value(SearchOptions())

    return config


def _format_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "null"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        items = ", ".join(_format_toml_value(item) for item in value)
        return f"[{items}]"
    if isinstance(value, dict):
        # Should not hit here; dicts are handled at section level
        return "{}"
    return f'"{value}"'


def _emit_toml_section(name: str, data: Dict[str, Any]) -> List[str]:
    lines: List[str] = [f"[{name}]"]

    scalar_keys = [k for k, v in data.items() if not isinstance(v, dict)]
    for key in sorted(scalar_keys):
        lines.append(f"{key} = {_format_toml_value(data[key])}")

    nested_keys = [k for k, v in data.items() if isinstance(v, dict)]
    for key in sorted(nested_keys):
        lines.append("")
        nested_name = f"{name}.{key}"
        lines.extend(_emit_toml_section(nested_name, data[key]))

    return lines


def _format_config_as_toml(config: Dict[str, Any]) -> str:
    lines = [
        "# all2md configuration file",
        "# Generated from current converter defaults",
        "# Edit values as needed and remove sections you do not use.",
    ]

    scalar_keys = [k for k, v in config.items() if not isinstance(v, dict)]
    for key in sorted(scalar_keys):
        lines.append(f"{key} = {_format_toml_value(config[key])}")

    section_keys = [k for k, v in config.items() if isinstance(v, dict)]
    for key in sorted(section_keys):
        lines.append("")
        lines.extend(_emit_toml_section(key, config[key]))

    return "\n".join(lines)


def _get_version() -> str:
    """Get the version of all2md package."""
    try:
        return version("all2md")
    except Exception:
        return "unknown"


def _get_about_info() -> str:
    """Get detailed information about all2md including system info and dependencies."""
    version_str = _get_version()

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

Installed Dependencies ({len([d for d in all_deps.values() if d['status'] == 'installed'])}/{len(all_deps)}):
{dependencies_report}

Available Formats ({available_count}/{total_formats} ready):
  Ready:   {', '.join(sorted(available_formats))}
  Missing: {', '.join(sorted(unavailable_formats)) if unavailable_formats else '(none)'}

Features:
  • Advanced PDF parsing with table detection
  • AST-based transformation pipeline
  • Plugin system for custom transforms
  • Intelligent format detection from content
  • Configurable Markdown output options
  • Attachment handling (download, embed, skip)
  • Command-line interface with stdin support
  • Python API for programmatic use
  • Multi-file and directory processing
  • Rich terminal output and progress bars

Install all dependencies: pip install all2md[all]
Install specific format:   pip install all2md[pdf,docx,html]

Documentation: https://github.com/thomas.villani/all2md
License: MIT License
Author: Thomas Villani <thomas.villani@gmail.com>"""


def _configure_logging(log_level: int, log_file: Optional[str] = None, trace_mode: bool = False) -> None:
    """Backward-compatible wrapper around shared logging configuration."""
    configure_root_logging(log_level, log_file=log_file, trace_mode=trace_mode)


def save_config_to_file(args: argparse.Namespace, config_path: str) -> None:
    """Save CLI arguments to a JSON configuration file.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command line arguments
    config_path : str
        Path to save the configuration file

    Raises
    ------
    Exception
        If the configuration file cannot be written

    """
    # Exclude special arguments that shouldn't be saved
    exclude_args = {
        "input",
        "out",
        "save_config",
        "about",
        "version",
        "dry_run",
        "format",
        "_env_checked",
        "_provided_args",
    }
    # Note: 'exclude' is intentionally NOT excluded so it can be saved in config

    # Get set of explicitly provided arguments from tracking actions
    provided_args: set[str] = getattr(args, "_provided_args", set())

    # Convert namespace to dict and filter
    args_dict = vars(args)
    config = {}

    for key, value in args_dict.items():
        if key not in exclude_args and value is not None:
            # Only include arguments that were explicitly provided by the user
            # This prevents saving default values that may change in future versions
            if key not in provided_args:
                continue

            # Skip empty lists
            if isinstance(value, list) and not value:
                continue
            # Skip sentinel values that aren't JSON serializable
            # Check for dataclasses._MISSING_TYPE
            if hasattr(value, "__class__") and value.__class__.__name__ == "_MISSING_TYPE":
                continue
            # Check for plain object() sentinels (used for UNSET in MarkdownRendererOptions)
            if type(value) is object:
                continue
            # Skip non-serializable types
            if isinstance(value, (set, frozenset)):
                continue

            # Include the explicitly provided value
            config[key] = value

    # Write to file
    config_path_obj = Path(config_path)
    config_path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path_obj, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"Configuration saved to {config_path}")


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

    Returns
    -------
    list[Path]
        List of matched file paths that pass extension filter

    """
    input_path = Path(raw_argument)
    matched_paths: List[Path] = []

    # Handle glob patterns
    if any(char in raw_argument for char in "*?["):
        matched_paths.extend(Path.cwd().glob(raw_argument))
    # Handle single file
    elif input_path.is_file():
        matched_paths.append(input_path)
    # Handle directory
    elif input_path.is_dir():
        iterator = input_path.rglob("*") if recursive else input_path.iterdir()
        for child in iterator:
            if child.is_file():
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
            display_name=str(path),
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
) -> List[CLIInputItem]:
    """Collect CLI input items from provided arguments.

    Supports local filesystem paths, directories, shell globs, URIs, and stdin.
    Local paths are expanded to files, filtered by extension when requested, and
    deduplicated. Remote inputs are preserved as strings to maintain compatibility
    with the document loader infrastructure.
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
        matched_files = _handle_local_path_input(raw_argument, recursive, extension_allowed)
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
                    f"File not found in batch list (line {line_num}): {file_path_str}\n" f"Resolved path: {file_path}"
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


def _create_list_formats_parser() -> argparse.ArgumentParser:
    """Create argparse parser for list-formats command.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser for list-formats command

    """
    parser = argparse.ArgumentParser(
        prog="all2md list-formats", description="Show information about available document parsers.", add_help=True
    )
    parser.add_argument("format", nargs="?", help="Show details for specific format only")
    parser.add_argument("--available-only", action="store_true", help="Show only formats with satisfied dependencies")
    parser.add_argument("--rich", action="store_true", help="Use rich terminal output with formatting")
    return parser


def _create_list_transforms_parser() -> argparse.ArgumentParser:
    """Create argparse parser for list-transforms command.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser for list-transforms command

    """
    parser = argparse.ArgumentParser(
        prog="all2md list-transforms", description="Show available AST transforms.", add_help=True
    )
    parser.add_argument("transform", nargs="?", help="Show details for specific transform")
    parser.add_argument("--rich", action="store_true", help="Use rich terminal output")
    return parser


def _gather_format_info_data(formats: list[str], available_only: bool) -> list[dict[str, Any]]:
    """Gather format information and dependency status.

    Parameters
    ----------
    formats : list[str]
        List of format names to gather info for
    available_only : bool
        Whether to filter for available formats only

    Returns
    -------
    list[dict]
        List of format info dictionaries

    """
    format_info_list: list[dict[str, Any]] = []
    for format_name in formats:
        metadata_list = registry.get_format_info(format_name)
        if not metadata_list or len(metadata_list) == 0:
            continue

        # Use the highest priority (first) converter
        metadata = metadata_list[0]

        # Check dependency status
        all_available = True
        dep_status: list[tuple[str, str | None, str, str | None]] = []

        for install_name, _import_name, version_spec in metadata.required_packages:
            if version_spec:
                meets_req, installed_version = check_version_requirement(install_name, version_spec)
                if not meets_req:
                    all_available = False
                    if installed_version:
                        dep_status.append((install_name, version_spec, "mismatch", installed_version))
                    else:
                        dep_status.append((install_name, version_spec, "missing", None))
                else:
                    dep_status.append((install_name, version_spec, "ok", installed_version))
            else:
                installed_version = get_package_version(install_name)
                if installed_version:
                    dep_status.append((install_name, version_spec, "ok", installed_version))
                else:
                    all_available = False
                    dep_status.append((install_name, version_spec, "missing", None))

        # Skip if filtering for available only
        if available_only and not all_available:
            continue

        format_info_list.append(
            {
                "name": format_name,
                "metadata": metadata,
                "all_available": all_available,
                "dep_status": dep_status,
            }
        )

    return format_info_list


def _render_rich_detailed_format(console: Any, info: dict[str, Any]) -> None:
    """Render detailed format information using Rich.

    Parameters
    ----------
    console : Console
        Rich console instance
    info : dict
        Format information dictionary

    """
    from rich.panel import Panel
    from rich.table import Table

    fmt_metadata = info["metadata"]
    assert fmt_metadata is not None

    # Create main panel
    content = [
        f"[bold]Format:[/bold] {info['name'].upper()}",
        f"[bold]Description:[/bold] {fmt_metadata.description or 'N/A'}",
        f"[bold]Extensions:[/bold] {', '.join(fmt_metadata.extensions) or 'N/A'}",
        f"[bold]MIME Types:[/bold] {', '.join(fmt_metadata.mime_types) or 'N/A'}",
        f"[bold]Converter:[/bold] {fmt_metadata.get_converter_display_string()}",
        f"[bold]Priority:[/bold] {fmt_metadata.priority}",
    ]

    console.print(Panel("\n".join(content), title=f"{info['name'].upper()} Format Details"))

    # Dependencies table
    if info["dep_status"]:
        dep_table = Table(title="Dependencies")
        dep_table.add_column("Package", style="cyan")
        dep_table.add_column("Required", style="yellow")
        dep_table.add_column("Status", style="magenta")
        dep_table.add_column("Installed", style="green")

        for pkg_name, version_spec, status, installed_version in info["dep_status"]:
            status_icon = {
                "ok": "[green][OK] Available[/green]",
                "missing": "[red][X] Missing[/red]",
                "mismatch": "[yellow][!] Version Mismatch[/yellow]",
            }[status]

            dep_table.add_row(pkg_name, version_spec or "any", status_icon, installed_version or "N/A")

        console.print(dep_table)

        if not info["all_available"]:
            install_cmd = fmt_metadata.get_install_command()
            console.print(f"\n[yellow]Install with:[/yellow] {install_cmd}")
    else:
        console.print("[green]No dependencies required[/green]")


def _render_rich_summary_formats(console: Any, format_info_list: list[dict[str, Any]]) -> None:
    """Render summary table of all formats using Rich.

    Parameters
    ----------
    console : Console
        Rich console instance
    format_info_list : list[dict]
        List of format information dictionaries

    """
    from rich.table import Table

    table = Table(title=f"All2MD Supported Formats ({len(format_info_list)} formats)")
    table.add_column("Format", style="cyan", no_wrap=True)
    table.add_column("Extensions", style="yellow")
    table.add_column("Capabilities", style="blue")
    table.add_column("Status", style="magenta")
    table.add_column("Dependencies", style="white")

    for info in format_info_list:
        metadata = info["metadata"]

        # Status indicator
        status = "[green][OK] Available[/green]" if info["all_available"] else "[red][X] Unavailable[/red]"

        # Extensions
        ext_str = ", ".join(metadata.extensions[:4])
        if len(metadata.extensions) > 4:
            ext_str += f" +{len(metadata.extensions) - 4}"

        # Capabilities
        has_parser = metadata.parser_class is not None
        has_renderer = metadata.renderer_class is not None
        if has_parser and has_renderer:
            capabilities = "Parse+Render"
        elif has_parser:
            capabilities = "Parse"
        elif has_renderer:
            capabilities = "Render"
        else:
            capabilities = "None"

        # Dependencies summary
        if info["dep_status"]:
            ok_count = sum(1 for _, _, s, _ in info["dep_status"] if s == "ok")
            total_count = len(info["dep_status"])
            dep_str = f"{ok_count}/{total_count}"
        else:
            dep_str = "none"

        table.add_row(info["name"].upper(), ext_str, capabilities, status, dep_str)

    console.print(table)
    console.print("\n[dim]Use 'all2md list-formats <format>' for detailed information[/dim]")


def _render_plain_detailed_format(info: dict[str, Any]) -> None:
    """Render detailed format information as plain text.

    Parameters
    ----------
    info : dict
        Format information dictionary

    """
    metadata_obj = info["metadata"]
    assert metadata_obj is not None

    print(f"\n{info['name'].upper()} Format")
    print("=" * 60)
    print(f"Description: {metadata_obj.description or 'N/A'}")
    print(f"Extensions: {', '.join(metadata_obj.extensions) or 'N/A'}")
    print(f"MIME Types: {', '.join(metadata_obj.mime_types) or 'N/A'}")
    print(f"Converter: {metadata_obj.get_converter_display_string()}")
    print(f"Priority: {metadata_obj.priority}")

    if info["dep_status"]:
        print("\nDependencies:")
        for pkg_name, version_spec, status, installed_version in info["dep_status"]:
            status_str = {"ok": "[OK]", "missing": "[MISSING]", "mismatch": "[VERSION MISMATCH]"}[status]
            version_str = f" {version_spec}" if version_spec else ""
            installed_str = f" (installed: {installed_version})" if installed_version else ""
            print(f"  {status_str} {pkg_name}{version_str}{installed_str}")

        if not info["all_available"]:
            install_cmd = metadata_obj.get_install_command()
            print(f"\nInstall with: {install_cmd}")
    else:
        print("\nNo dependencies required")


def _render_plain_summary_formats(format_info_list: list[dict[str, Any]]) -> None:
    """Render summary of all formats as plain text.

    Parameters
    ----------
    format_info_list : list[dict]
        List of format information dictionaries

    """
    print("\nAll2MD Supported Formats")
    print("=" * 60)
    for info in format_info_list:
        format_meta = info["metadata"]
        assert format_meta is not None

        status = "[OK]" if info["all_available"] else "[X]"
        ext_str = ", ".join(format_meta.extensions[:4])
        if len(format_meta.extensions) > 4:
            ext_str += f" +{len(format_meta.extensions) - 4}"

        # Capabilities
        has_parser = format_meta.parser_class is not None
        has_renderer = format_meta.renderer_class is not None
        if has_parser and has_renderer:
            capabilities = "[R+W]"
        elif has_parser:
            capabilities = "[R]  "
        elif has_renderer:
            capabilities = "[W]  "
        else:
            capabilities = "     "

        print(f"{status} {info['name'].upper():12} {capabilities} {ext_str}")

    print(f"\nTotal: {len(format_info_list)} formats")


def handle_list_formats_command(args: list[str] | None = None) -> int:
    """Handle list-formats command to show available parsers.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'list-formats')

    Returns
    -------
    int
        Exit code (0 for success)

    """
    # Parse command line arguments using dedicated parser
    parser = _create_list_formats_parser()
    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        # argparse calls sys.exit() on --help or error
        # Return the exit code
        return e.code if isinstance(e.code, int) else 0

    # Extract parsed arguments
    specific_format = parsed.format
    available_only = parsed.available_only
    use_rich = parsed.rich

    # Auto-discover parsers
    registry.auto_discover()

    # Get all formats
    formats = registry.list_formats()
    if specific_format:
        if specific_format not in formats:
            print(f"Error: Format '{specific_format}' not found", file=sys.stderr)
            print(f"Available formats: {', '.join(formats)}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR
        formats = [specific_format]

    # Gather format information
    format_info_list = _gather_format_info_data(formats, available_only)

    # Display results
    if use_rich:
        try:
            from rich.console import Console

            console = Console()

            if specific_format and format_info_list:
                _render_rich_detailed_format(console, format_info_list[0])
            else:
                _render_rich_summary_formats(console, format_info_list)

        except ImportError:
            # Fall back to plain text
            use_rich = False

    if not use_rich:
        # Plain text output
        if specific_format and format_info_list:
            _render_plain_detailed_format(format_info_list[0])
        else:
            _render_plain_summary_formats(format_info_list)
            print("Use 'all2md list-formats <format>' for detailed information")

    return 0


def handle_list_transforms_command(args: list[str] | None = None) -> int:
    """Handle list-transforms command.

    Parameters
    ----------
    args : list[str], optional
        Additional arguments

    Returns
    -------
    int
        Exit code (0 for success)

    """
    # Parse command line arguments using dedicated parser
    parser = _create_list_transforms_parser()
    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        # argparse calls sys.exit() on --help or error
        # Return the exit code
        return e.code if isinstance(e.code, int) else 0

    # Extract parsed arguments
    specific_transform = parsed.transform
    use_rich = parsed.rich

    # List transforms (auto-discovers on first access)
    transforms = transform_registry.list_transforms()

    if specific_transform:
        if specific_transform not in transforms:
            print(f"Error: Transform '{specific_transform}' not found", file=sys.stderr)
            print(f"Available: {', '.join(transforms)}", file=sys.stderr)
            return 1
        transforms = [specific_transform]

    # Display transforms
    if use_rich:
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table

            console = Console()

            if specific_transform:
                # Detailed view
                metadata = transform_registry.get_metadata(specific_transform)

                content = []
                content.append(f"[bold]Name:[/bold] {metadata.name}")
                content.append(f"[bold]Description:[/bold] {metadata.description}")
                content.append(f"[bold]Priority:[/bold] {metadata.priority}")
                if metadata.dependencies:
                    content.append(f"[bold]Dependencies:[/bold] {', '.join(metadata.dependencies)}")
                if metadata.tags:
                    content.append(f"[bold]Tags:[/bold] {', '.join(metadata.tags)}")

                console.print(Panel("\n".join(content), title=f"Transform: {metadata.name}"))

                # Parameters table
                if metadata.parameters:
                    table = Table(title="Parameters")
                    table.add_column("Name", style="cyan")
                    table.add_column("Type", style="yellow")
                    table.add_column("Default", style="green")
                    table.add_column("CLI Flag", style="magenta")
                    table.add_column("Description", style="white")

                    for name, spec in metadata.parameters.items():
                        type_str = spec.type.__name__ if hasattr(spec.type, "__name__") else str(spec.type)
                        flag: str = spec.get_cli_flag(name) if spec.should_expose() else "N/A"
                        table.add_row(
                            name,
                            type_str,
                            str(spec.default) if spec.default is not None else "None",
                            flag,
                            spec.help or "",
                        )

                    console.print(table)
            else:
                # Summary table
                table = Table(title=f"Available Transforms ({len(transforms)})")
                table.add_column("Name", style="cyan")
                table.add_column("Description", style="white")
                table.add_column("Tags", style="yellow")

                for name in transforms:
                    metadata = transform_registry.get_metadata(name)
                    table.add_row(
                        metadata.name, metadata.description, ", ".join(metadata.tags) if metadata.tags else ""
                    )

                console.print(table)
        except ImportError:
            use_rich = False

    if not use_rich:
        # Plain text output
        if specific_transform:
            metadata = transform_registry.get_metadata(specific_transform)
            print(f"\n{metadata.name}")
            print("=" * 60)
            print(f"Description: {metadata.description}")
            print(f"Priority: {metadata.priority}")
            if metadata.dependencies:
                print(f"Dependencies: {', '.join(metadata.dependencies)}")
            if metadata.tags:
                print(f"Tags: {', '.join(metadata.tags)}")

            if metadata.parameters:
                print("\nParameters:")
                for name, spec in metadata.parameters.items():
                    type_str = spec.type.__name__ if hasattr(spec.type, "__name__") else str(spec.type)
                    default_str = f"(default: {spec.default})" if spec.default is not None else ""
                    cli_flag: str | None = spec.get_cli_flag(name) if spec.should_expose() else None
                    print(f"  {name} ({type_str}) {default_str}")
                    if spec.help:
                        print(f"    {spec.help}")
                    if cli_flag:
                        print(f"  CLI: {cli_flag}")
        else:
            print("\nAvailable Transforms")
            print("=" * 60)
            for name in transforms:
                metadata = transform_registry.get_metadata(name)
                tags_str = f" [{', '.join(metadata.tags)}]" if metadata.tags else ""
                print(f"  {metadata.name:20} {metadata.description}{tags_str}")
            print(f"\nTotal: {len(transforms)} transforms")
            print("Use 'all2md list-transforms <transform>' for details")

    return 0


def handle_help_command(args: list[str] | None = None) -> int | None:
    """Handle the ``help`` subcommand for tiered CLI documentation."""
    if not args:
        args = sys.argv[1:]

    if not args or args[0] != "help":
        return None

    help_args = args[1:]

    parser = argparse.ArgumentParser(
        prog="all2md help",
        description="Show all2md CLI help sections (quick, full, or format-specific).",
    )
    parser.add_argument(
        "section",
        nargs="?",
        default="quick",
        help="Help selector (quick, full, pdf, docx, html, etc.). Default: quick.",
    )
    parser.add_argument(
        "--rich",
        action="store_true",
        help="Render help with rich formatting when the rich package is installed.",
    )

    parsed = parser.parse_args(help_args)

    requested_rich: Optional[bool]
    if parsed.rich:
        requested_rich = True
    else:
        requested_rich = None

    display_help(parsed.section, use_rich=requested_rich)
    return 0


def _run_convert_command(parsed_args: argparse.Namespace) -> int:
    options, format_arg, transforms = setup_and_validate_options(parsed_args)

    # Set up logging level
    if parsed_args.trace:
        log_level = logging.DEBUG
    elif parsed_args.verbose and parsed_args.log_level == "WARNING":
        log_level = logging.DEBUG
    else:
        log_level = getattr(logging, parsed_args.log_level.upper())

    # Configure logging with file handler if --log-file is specified
    _configure_logging(log_level, log_file=parsed_args.log_file, trace_mode=parsed_args.trace)

    if not validate_arguments(parsed_args, logger=logger):
        return EXIT_VALIDATION_ERROR

    items = collect_input_files(parsed_args.input, parsed_args.recursive, exclude_patterns=parsed_args.exclude)

    if not items:
        print("Error: No valid input files found", file=sys.stderr)
        return EXIT_FILE_ERROR

    return process_multi_file(items, parsed_args, options, format_arg, transforms)


def handle_config_generate_command(args: list[str] | None = None) -> int:
    """Handle ``config generate`` to create default configuration files."""
    parser = argparse.ArgumentParser(
        prog="all2md config generate",
        description="Generate a default configuration file with all available options.",
    )
    parser.add_argument(
        "--format",
        choices=("toml", "json"),
        default="toml",
        help="Output format for the generated configuration (default: toml).",
    )
    parser.add_argument(
        "--out",
        dest="out",
        help="Write configuration to the given path instead of stdout.",
    )

    try:
        parsed_args = parser.parse_args(args or [])
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0

    config_data = _build_default_config_data()

    if parsed_args.format == "toml":
        output_text = _format_config_as_toml(config_data)
    else:
        output_text = json.dumps(config_data, indent=2, ensure_ascii=False, sort_keys=True)

    if parsed_args.out:
        try:
            output_path = Path(parsed_args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output_text, encoding="utf-8")
            print(f"Configuration written to {parsed_args.out}")
        except Exception as exc:
            print(f"Error writing configuration file: {exc}", file=sys.stderr)
            return 1
        return 0

    print(output_text)
    return 0


def handle_config_show_command(args: list[str] | None = None) -> int:
    """Handle ``config show`` command to display effective configuration."""
    parser = argparse.ArgumentParser(
        prog="all2md config show",
        description="Display the effective configuration that all2md will use.",
    )
    parser.add_argument(
        "--format",
        choices=("toml", "json"),
        default="toml",
        help="Output format for the configuration (default: toml).",
    )
    parser.add_argument(
        "--no-source",
        dest="show_source",
        action="store_false",
        default=True,
        help="Hide configuration source information.",
    )

    try:
        parsed_args = parser.parse_args(args or [])
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0

    env_config_path = os.environ.get("ALL2MD_CONFIG")
    config = load_config_with_priority(
        explicit_path=None,
        env_var_path=env_config_path,
    )

    if parsed_args.show_source:
        print("Configuration Sources (in priority order):")
        print("-" * 60)

        if env_config_path:
            exists = Path(env_config_path).exists()
            status = "FOUND" if exists else "NOT FOUND"
            print(f"1. ALL2MD_CONFIG env var: {env_config_path} [{status}]")
        else:
            print("1. ALL2MD_CONFIG env var: (not set)")

        for index, path in enumerate(get_config_search_paths(), start=2):
            status = "FOUND" if path.exists() else "-"
            print(f"{index}. {path} [{status}]")

        print()

    if not config:
        print("No configuration found. Using defaults.")
        print("\nTo create a config file, run: all2md config generate --out .all2md.toml")
        return 0

    print("Effective Configuration:")
    print("=" * 60)

    if parsed_args.format == "toml":
        import tomli_w

        output_text = tomli_w.dumps(config)
    else:
        output_text = json.dumps(config, indent=2, ensure_ascii=False)

    print(output_text)
    return 0


def handle_config_validate_command(args: list[str] | None = None) -> int:
    """Handle config validate command to check configuration file syntax.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'config validate')

    Returns
    -------
    int
        Exit code (0 for success, 1 for invalid config)

    """
    # Parse arguments
    config_file = None

    if args:
        for arg in args:
            if arg in ("--help", "-h"):
                print(
                    """Usage: all2md config validate <config-file>

Validate a configuration file for syntax errors.

Arguments:
  config-file        Path to configuration file (.toml or .json)

Options:
  -h, --help        Show this help message

Examples:
  all2md config validate .all2md.toml
  all2md config validate ~/.all2md.json
"""
                )
                return 0
            elif not arg.startswith("-"):
                config_file = arg
                break

    if not config_file:
        print("Error: Config file path required", file=sys.stderr)
        print("Usage: all2md config validate <config-file>", file=sys.stderr)
        return 1

    # Attempt to load and validate
    try:
        config = load_config_file(config_file)
        print(f"Configuration file is valid: {config_file}")
        print(f"Format: {Path(config_file).suffix}")
        print(f"Keys found: {', '.join(config.keys()) if config else '(empty)'}")
        return 0
    except argparse.ArgumentTypeError as e:
        print(f"Invalid configuration file: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error validating configuration: {e}", file=sys.stderr)
        return 1


def handle_config_command(args: list[str] | None = None) -> int | None:
    """Handle config subcommands.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments

    Returns
    -------
    int or None
        Exit code if config command was handled, None otherwise

    """
    if not args:
        args = sys.argv[1:]

    if not args or args[0] != "config":
        return None

    # Get subcommand
    if len(args) < 2:
        print(
            """Usage: all2md config <subcommand> [OPTIONS]

Configuration management commands.

Subcommands:
  generate           Generate a default configuration file
  show              Display effective configuration from all sources
  validate          Validate a configuration file

Use 'all2md config <subcommand> --help' for more information.

Examples:
  all2md config generate --out .all2md.toml
  all2md config show
  all2md config validate .all2md.toml
""",
            file=sys.stderr,
        )
        return 1

    subcommand = args[1]
    subcommand_args = args[2:]

    if subcommand == "generate":
        return handle_config_generate_command(subcommand_args)
    elif subcommand == "show":
        return handle_config_show_command(subcommand_args)
    elif subcommand == "validate":
        return handle_config_validate_command(subcommand_args)
    else:
        print(f"Error: Unknown config subcommand '{subcommand}'", file=sys.stderr)
        print("Valid subcommands: generate, show, validate", file=sys.stderr)
        return 1


def handle_generate_site_command(args: list[str] | None = None) -> int:
    """Handle generate-site command for Hugo/Jekyll static site generation.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'generate-site')

    Returns
    -------
    int
        Exit code (0 for success)

    """
    parser = argparse.ArgumentParser(
        prog="all2md generate-site",
        description="Generate Hugo or Jekyll static site from documents.",
    )
    parser.add_argument("input", nargs="+", help="Input files or directories to convert")
    parser.add_argument("--output-dir", required=True, help="Output directory for the static site")
    parser.add_argument(
        "--generator", choices=["hugo", "jekyll"], required=True, help="Static site generator (hugo or jekyll)"
    )
    parser.add_argument(
        "--scaffold", action="store_true", help="Create full site structure with config files and layouts"
    )
    parser.add_argument(
        "--frontmatter-format",
        choices=["yaml", "toml"],
        help="Frontmatter format (default: toml for Hugo, yaml for Jekyll)",
    )
    parser.add_argument(
        "--content-subdir", default="", help="Subdirectory within content/ or _posts/ (e.g., 'posts', 'docs')"
    )
    parser.add_argument("--recursive", action="store_true", help="Process directories recursively")
    parser.add_argument("--exclude", action="append", help="Glob patterns to exclude (can be used multiple times)")

    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0

    # Parse generator type
    generator = StaticSiteGenerator(parsed.generator)

    # Determine frontmatter format
    if parsed.frontmatter_format:
        fm_format = FrontmatterFormat(parsed.frontmatter_format)
    else:
        fm_format = FrontmatterFormat.TOML if generator == StaticSiteGenerator.HUGO else FrontmatterFormat.YAML

    # Create output directory
    output_dir = Path(parsed.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Scaffold site structure if requested
    if parsed.scaffold:
        scaffolder = SiteScaffolder(generator)
        scaffolder.scaffold(output_dir)
        print(f"Created {generator.value} site structure at {output_dir}")

    # Collect input files
    items = collect_input_files(parsed.input, parsed.recursive, exclude_patterns=parsed.exclude)

    if not items:
        print("Error: No valid input files found", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    # Determine content directory
    if generator == StaticSiteGenerator.HUGO:
        content_dir = output_dir / "content"
        if parsed.content_subdir:
            content_dir = content_dir / parsed.content_subdir
    else:  # Jekyll
        content_dir = output_dir / "_posts"
        if parsed.content_subdir:
            content_dir = output_dir / parsed.content_subdir

    content_dir.mkdir(parents=True, exist_ok=True)

    # Process each file
    frontmatter_gen = FrontmatterGenerator(generator, fm_format)
    markdown_renderer = MarkdownRenderer()
    success_count = 0
    error_count = 0

    print(f"Converting {len(items)} file(s) to {generator.value} site...")
    from all2md.api import to_ast

    for index, item in enumerate(items, start=1):
        try:
            # Get source path
            source_path = item.best_path()
            if not source_path:
                logger.warning(f"Skipping item with no path: {item.display_name}")
                continue

            # Convert to AST
            logger.debug(f"Processing {source_path}")
            doc = to_ast(source_path)

            # Generate frontmatter from metadata
            frontmatter = frontmatter_gen.generate(doc.metadata)

            # Copy assets and update image URLs
            doc, copied_assets = copy_document_assets(doc, output_dir, generator, source_path)
            if copied_assets:
                logger.debug(f"Copied {len(copied_assets)} asset(s) for {source_path.name}")

            # Render markdown content
            markdown_content = markdown_renderer.render_to_string(doc)

            # Combine frontmatter and content
            full_content = frontmatter + markdown_content

            # Generate output filename
            output_filename = generate_output_filename(source_path, doc.metadata, generator, index)
            output_path = content_dir / f"{output_filename}.md"

            # Ensure unique filename
            output_path = ensure_unique_attachment_path(output_path)

            # Write output file
            output_path.write_text(full_content, encoding="utf-8")
            print(f"  [{index}/{len(items)}] {source_path.name} -> {output_path.relative_to(output_dir)}")
            success_count += 1

        except Exception as e:
            logger.error(f"Failed to process {item.display_name}: {e}")
            print(f"  [ERROR] {item.display_name}: {e}", file=sys.stderr)
            error_count += 1
            continue

    # Summary
    print(f"\nCompleted: {success_count} successful, {error_count} errors")
    print(f"Site created at: {output_dir}")

    if generator == StaticSiteGenerator.HUGO:
        print("\nTo preview your Hugo site:")
        print(f"  cd {output_dir}")
        print("  hugo server")
    else:
        print("\nTo preview your Jekyll site:")
        print(f"  cd {output_dir}")
        print("  jekyll serve")

    return EXIT_SUCCESS if error_count == 0 else EXIT_ERROR


def handle_search_command(args: list[str] | None = None) -> int:
    """Handle ``all2md search`` for keyword/vector/hybrid queries."""
    parser = argparse.ArgumentParser(
        prog="all2md search",
        description="Search documents using keyword, vector, or hybrid retrieval.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("query", help="Search query text")
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Files, directories, or globs to index. Omit when reusing persisted index.",
    )
    parser.add_argument("--config", help="Optional configuration file overriding defaults")
    parser.add_argument("--index-dir", help="Directory containing or storing persisted index data")
    parser.add_argument("--persist", action="store_true", help="Persist index state to --index-dir")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild even if cached index exists")
    parser.add_argument("--top-k", type=int, default=10, help="Maximum number of results to return")
    parser.add_argument("--json", action="store_true", help="Emit search results as JSON")
    parser.add_argument("--progress", action="store_true", help="Print progress updates during indexing/search")
    parser.add_argument("--recursive", action="store_true", help="Recurse into directories when indexing inputs")
    parser.add_argument("--exclude", action="append", help="Glob pattern to exclude (repeatable)")
    parser.add_argument("--rich", action="store_true", help="Enable rich-style output formatting when printing")
    parser.add_argument(
        "-A",
        "--after-context",
        dest="grep_context_after",
        type=int,
        help="Print NUM lines of trailing context (grep mode)",
    )
    parser.add_argument(
        "-B",
        "--before-context",
        dest="grep_context_before",
        type=int,
        help="Print NUM lines of leading context (grep mode)",
    )
    parser.add_argument(
        "-C",
        "--context",
        dest="grep_context",
        type=int,
        help="Print NUM lines of leading and trailing context (equivalent to -A NUM -B NUM)",
    )
    parser.add_argument(
        "-e",
        "--regex",
        dest="grep_regex",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Interpret query as a regular expression when using grep mode",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--mode",
        dest="mode",
        choices=["grep", "keyword", "vector", "hybrid"],
        help="Explicit search mode to execute",
    )
    mode_group.add_argument("--grep", dest="mode", action="store_const", const="grep", help="Shortcut for --mode grep")
    mode_group.add_argument(
        "--keyword", dest="mode", action="store_const", const="keyword", help="Shortcut for --mode keyword"
    )
    mode_group.add_argument(
        "--vector", dest="mode", action="store_const", const="vector", help="Shortcut for --mode vector"
    )
    mode_group.add_argument(
        "--hybrid", dest="mode", action="store_const", const="hybrid", help="Shortcut for --mode hybrid"
    )

    parser.add_argument("--chunk-size", dest="chunk_size_tokens", type=int, help="Maximum tokens per chunk")
    parser.add_argument("--chunk-overlap", dest="chunk_overlap_tokens", type=int, help="Token overlap per chunk")
    parser.add_argument("--min-chunk-tokens", dest="min_chunk_tokens", type=int, help="Minimum chunk size")
    parser.add_argument(
        "--include-preamble",
        dest="include_preamble",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include content that appears before the first heading",
    )
    parser.add_argument(
        "--max-heading-level",
        dest="max_heading_level",
        type=int,
        help="Limit chunking to headings at or below this level",
    )
    parser.add_argument("--bm25-k1", dest="bm25_k1", type=float, help="BM25 k1 parameter")
    parser.add_argument("--bm25-b", dest="bm25_b", type=float, help="BM25 b parameter")
    parser.add_argument(
        "--vector-model",
        dest="vector_model_name",
        help="Sentence-transformers model used for embedding generation",
    )
    parser.add_argument(
        "--vector-batch-size",
        dest="vector_batch_size",
        type=int,
        help="Batch size for embedding generation",
    )
    parser.add_argument("--vector-device", dest="vector_device", help="Torch device string for embeddings")
    parser.add_argument(
        "--vector-normalize",
        dest="vector_normalize_embeddings",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Normalize embeddings before FAISS indexing",
    )
    parser.add_argument(
        "--hybrid-keyword-weight",
        dest="hybrid_keyword_weight",
        type=float,
        help="Keyword contribution in hybrid mode",
    )
    parser.add_argument(
        "--hybrid-vector-weight",
        dest="hybrid_vector_weight",
        type=float,
        help="Vector contribution in hybrid mode",
    )
    parser.add_argument(
        "--default-mode",
        dest="default_mode",
        choices=["grep", "keyword", "vector", "hybrid"],
        help="Update the default mode recorded with persisted indexes",
    )

    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0

    if parsed.persist and not parsed.index_dir:
        parser.error("--persist requires --index-dir")

    if getattr(parsed, "grep_context", None) is not None:
        if parsed.grep_context_before is None:
            parsed.grep_context_before = parsed.grep_context
        if parsed.grep_context_after is None:
            parsed.grep_context_after = parsed.grep_context

    if parsed.grep_context_before is not None and parsed.grep_context_before < 0:
        parser.error("--before-context must be non-negative")
    if parsed.grep_context_after is not None and parsed.grep_context_after < 0:
        parser.error("--after-context must be non-negative")

    if parsed.top_k <= 0:
        parser.error("--top-k must be a positive integer")

    env_config_path = os.environ.get("ALL2MD_CONFIG")
    try:
        config_data = load_config_with_priority(explicit_path=parsed.config, env_var_path=env_config_path)
    except argparse.ArgumentTypeError as exc:
        print(f"Error loading configuration: {exc}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    search_section = {}
    if config_data and isinstance(config_data, dict):
        search_section = config_data.get("search", {}) or {}

    options = _apply_search_config(SearchOptions(), search_section)
    overrides = _collect_search_overrides(parsed)
    if overrides:
        try:
            options = options.create_updated(**overrides)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR

    try:
        resolved_mode = _parse_search_mode(parsed.mode, options)
    except argparse.ArgumentTypeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    index_path = Path(parsed.index_dir).expanduser() if parsed.index_dir else None

    service: SearchService | None = None
    using_existing = False
    # Skip index persistence for grep mode (grep doesn't need indexing)
    if index_path and index_path.exists() and not parsed.rebuild and resolved_mode != "grep":
        try:
            service = SearchService.load(index_path, options=options)
            using_existing = True
        except FileNotFoundError:
            using_existing = False

    if using_existing and parsed.inputs:
        print(
            "Error: Cannot specify inputs when reusing an existing index. Use --rebuild to regenerate it.",
            file=sys.stderr,
        )
        return EXIT_VALIDATION_ERROR

    items: List[CLIInputItem] = []
    if parsed.inputs:
        items = collect_input_files(parsed.inputs, recursive=parsed.recursive, exclude_patterns=parsed.exclude)
        if not items and not using_existing:
            print("Error: No valid input files found", file=sys.stderr)
            return EXIT_FILE_ERROR

    # Enable progress by default for vector search (which is typically slow)
    enable_progress = parsed.progress or resolved_mode == "vector"
    progress_callback = _make_search_progress_callback(enable_progress)
    service = service or SearchService(options=options)

    if not using_existing:
        documents = _create_search_documents(items)
        if not documents:
            print("Error: No input documents available for indexing", file=sys.stderr)
            return EXIT_FILE_ERROR
        try:
            service.build_indexes(documents, modes={resolved_mode}, progress_callback=progress_callback)
        except DependencyError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_DEPENDENCY_ERROR
        except Exception as exc:
            print(f"Error building index: {exc}", file=sys.stderr)
            return EXIT_ERROR

        # Skip saving index for grep mode (grep doesn't need indexing)
        if index_path and parsed.persist and resolved_mode != "grep":
            try:
                service.save(index_path)
            except Exception as exc:
                print(f"Error saving index: {exc}", file=sys.stderr)
                return EXIT_ERROR

    try:
        results = service.search(
            parsed.query, mode=resolved_mode, top_k=parsed.top_k, progress_callback=progress_callback
        )
    except DependencyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_DEPENDENCY_ERROR
    except Exception as exc:
        print(f"Error executing search: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if parsed.json:
        print(json.dumps([_result_to_dict(result) for result in results], indent=2, ensure_ascii=False))
    else:
        _render_search_results(results, use_rich=parsed.rich)

    return EXIT_SUCCESS


def handle_grep_command(args: list[str] | None = None) -> int:
    """Handle ``all2md grep`` for simple text search in documents.

    This is a simplified interface to the search system that only uses grep mode,
    making it work like traditional grep but for binary document formats.
    """
    parser = argparse.ArgumentParser(
        prog="all2md grep",
        description="Search for text patterns in documents (works on binary formats too).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("query", help="Search query text or pattern")
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Files, directories, or globs to search",
    )
    parser.add_argument(
        "-e",
        "--regex",
        dest="grep_regex",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Interpret query as a regular expression",
    )
    parser.add_argument(
        "-A",
        "--after-context",
        dest="grep_context_after",
        type=int,
        help="Print NUM lines of trailing context",
    )
    parser.add_argument(
        "-B",
        "--before-context",
        dest="grep_context_before",
        type=int,
        help="Print NUM lines of leading context",
    )
    parser.add_argument(
        "-C",
        "--context",
        dest="grep_context",
        type=int,
        help="Print NUM lines of leading and trailing context (equivalent to -A NUM -B NUM)",
    )
    parser.add_argument(
        "-n",
        "--line-number",
        dest="grep_show_line_numbers",
        action="store_true",
        help="Show line numbers for matching lines",
    )
    parser.add_argument(
        "-i",
        "--ignore-case",
        dest="grep_ignore_case",
        action="store_true",
        help="Perform case-insensitive matching",
    )
    parser.add_argument(
        "-M",
        "--max-columns",
        dest="grep_max_columns",
        type=int,
        help="Maximum display width for long lines (default: 150, 0 = unlimited)",
    )
    parser.add_argument("--recursive", action="store_true", help="Recurse into directories when searching")
    parser.add_argument("--exclude", action="append", help="Glob pattern to exclude (repeatable)")
    parser.add_argument("--rich", action="store_true", help="Enable rich-style output formatting")

    parsed = parser.parse_args(args)

    # Apply context shortcuts
    if parsed.grep_context is not None:
        if parsed.grep_context_before is None:
            parsed.grep_context_before = parsed.grep_context
        if parsed.grep_context_after is None:
            parsed.grep_context_after = parsed.grep_context

    # Create search options with grep-specific settings
    options = SearchOptions()
    overrides = {}
    if parsed.grep_context_before is not None:
        overrides["grep_context_before"] = parsed.grep_context_before
    if parsed.grep_context_after is not None:
        overrides["grep_context_after"] = parsed.grep_context_after
    if parsed.grep_regex is not None:
        overrides["grep_regex"] = parsed.grep_regex
    if parsed.grep_show_line_numbers:
        overrides["grep_show_line_numbers"] = parsed.grep_show_line_numbers
    if parsed.grep_ignore_case:
        overrides["grep_ignore_case"] = parsed.grep_ignore_case
    if parsed.grep_max_columns is not None:
        overrides["grep_max_columns"] = parsed.grep_max_columns

    if overrides:
        try:
            options = options.create_updated(**overrides)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR

    # Collect input files
    items = collect_input_files(parsed.inputs, recursive=parsed.recursive, exclude_patterns=parsed.exclude)
    if not items:
        print("Error: No valid input files found", file=sys.stderr)
        return EXIT_FILE_ERROR

    # Create documents
    documents = _create_search_documents(items)
    if not documents:
        print("Error: No input documents available for searching", file=sys.stderr)
        return EXIT_FILE_ERROR

    # Build index and search (grep mode, no persistence)
    service = SearchService(options=options)
    try:
        service.build_indexes(documents, modes={"grep"})
    except DependencyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_DEPENDENCY_ERROR
    except Exception as exc:
        print(f"Error building index: {exc}", file=sys.stderr)
        return EXIT_ERROR

    try:
        # Grep mode returns all results (no top_k limit)
        results = service.search(parsed.query, mode="grep", top_k=999999)
    except DependencyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_DEPENDENCY_ERROR
    except Exception as exc:
        print(f"Error during search: {exc}", file=sys.stderr)
        return EXIT_ERROR

    # Render results
    _render_search_results(results, use_rich=parsed.rich)
    return EXIT_SUCCESS


def _apply_search_config(options: SearchOptions, config_section: Mapping[str, object]) -> SearchOptions:
    if not config_section:
        return options
    valid_fields = {field.name for field in fields(SearchOptions)}
    filtered = {key: value for key, value in config_section.items() if key in valid_fields}
    if not filtered:
        return options
    return options.create_updated(**filtered)


def _collect_search_overrides(parsed: argparse.Namespace) -> Dict[str, object]:
    overrides: Dict[str, object] = {}
    for field_name in (
        "chunk_size_tokens",
        "chunk_overlap_tokens",
        "min_chunk_tokens",
        "include_preamble",
        "max_heading_level",
        "bm25_k1",
        "bm25_b",
        "vector_model_name",
        "vector_batch_size",
        "vector_device",
        "vector_normalize_embeddings",
        "hybrid_keyword_weight",
        "hybrid_vector_weight",
        "default_mode",
        "grep_context_before",
        "grep_context_after",
        "grep_regex",
    ):
        if hasattr(parsed, field_name):
            value = getattr(parsed, field_name)
            if value is not None:
                overrides[field_name] = value
    return overrides


def _parse_search_mode(mode_value: str | None, options: SearchOptions) -> SearchMode:
    mapping = {
        "grep": SearchMode.GREP,
        "keyword": SearchMode.KEYWORD,
        "bm25": SearchMode.KEYWORD,
        "vector": SearchMode.VECTOR,
        "hybrid": SearchMode.HYBRID,
    }
    selected = mode_value or options.default_mode
    normalized = selected.strip().lower()
    if normalized not in mapping:
        raise argparse.ArgumentTypeError(f"Unknown search mode: {selected}")
    return mapping[normalized]


def _create_search_documents(items: List[CLIInputItem]) -> list[SearchDocumentInput]:
    documents: list[SearchDocumentInput] = []
    for index, item in enumerate(items, start=1):
        metadata = {
            "display_name": item.display_name,
            "input_index": index,
        }
        metadata.update(item.metadata)
        if item.path_hint:
            metadata["path_hint"] = str(item.path_hint)
        documents.append(
            SearchDocumentInput(
                source=item.raw_input,
                document_id=item.stem,
                source_format="auto",
                metadata=metadata,
            )
        )
    return documents


def _result_to_dict(result: SearchResult) -> Dict[str, object]:
    return {
        "score": result.score,
        "chunk_id": result.chunk.chunk_id,
        "text": result.chunk.text,
        "chunk_metadata": dict(result.chunk.metadata),
        "result_metadata": dict(result.metadata),
    }


def _render_grep_results(results: List[SearchResult], *, use_rich: bool) -> None:
    """Render grep results in ripgrep-style format.

    Groups matches by file, showing file path as a header followed by
    matching lines with line numbers.

    Parameters
    ----------
    results : List[SearchResult]
        Search results from grep mode
    use_rich : bool
        Whether to use rich formatting

    """
    console = None
    if use_rich:
        try:
            from rich.console import Console

            console = Console()
        except ImportError:
            use_rich = False

    # Group results by document path and section
    grouped: dict[str, dict[str, list[SearchResult]]] = {}
    for result in results:
        metadata = result.chunk.metadata
        doc_label = (
            metadata.get("document_path") or metadata.get("path_hint") or metadata.get("document_id") or "unknown"
        )
        section = metadata.get("section_heading") or "(preamble)"

        if doc_label not in grouped:
            grouped[doc_label] = {}
        if section not in grouped[doc_label]:
            grouped[doc_label][section] = []
        grouped[doc_label][section].append(result)

    # Render each file and its sections
    for doc_path, sections in grouped.items():
        if use_rich and console is not None:
            from rich.text import Text

            # File header
            header = Text(str(doc_path), style="bold magenta")
            console.print(header)
            console.print()

            # Print each section
            for section_name, section_results in sections.items():
                # Section heading
                console.print(Text(section_name, style="bold cyan"))

                # Print matches for this section
                for result in section_results:
                    snippet = result.chunk.text
                    if snippet:
                        # Indent each line
                        for line in snippet.splitlines():
                            snippet_text = _rich_snippet(line)
                            if snippet_text:
                                console.print(Text("  ") + snippet_text)
                            else:
                                console.print(f"  {line}")

                console.print()

        else:
            # Plain text output
            print(str(doc_path))
            print()

            # Print each section
            for section_name, section_results in sections.items():
                # Section heading
                print(section_name)

                # Print matches for this section
                for result in section_results:
                    snippet = result.chunk.text
                    if snippet:
                        # Indent each line of the snippet
                        for line in snippet.splitlines():
                            # Strip highlighting markers in plain mode
                            plain_line = line.replace("<<", "").replace(">>", "")
                            print(f"  {plain_line}")

                print()


def _render_search_results(results: List[SearchResult], *, use_rich: bool) -> None:
    if not results:
        print("No results found.")
        return

    # Check if this is grep mode
    is_grep = False
    if results:
        first_backend = results[0].metadata.get("backend", "") if isinstance(results[0].metadata, Mapping) else ""
        is_grep = first_backend == "grep"

    if is_grep:
        _render_grep_results(results, use_rich=use_rich)
        return

    console = None
    if use_rich:
        try:
            from rich.console import Console

            console = Console()
        except ImportError:
            print("Rich output requested but `rich` is not installed. Falling back to plain output.")
            use_rich = False

    for rank, result in enumerate(results, start=1):
        metadata = result.chunk.metadata
        doc_label = metadata.get("document_path") or metadata.get("path_hint") or metadata.get("document_id")
        heading = metadata.get("section_heading") or ""
        backend = str(result.metadata.get("backend", "")) if isinstance(result.metadata, Mapping) else ""
        occurrences = result.metadata.get("occurrences") if isinstance(result.metadata, Mapping) else None
        lines = result.metadata.get("lines") if isinstance(result.metadata, Mapping) else None
        show_score = backend != "grep"

        if use_rich and console is not None:
            from rich.text import Text

            header = Text(f"{rank:>2}. ", style="bold cyan")
            if show_score:
                header.append(f"score={result.score:.4f} ", style="green")
            if backend:
                header.append(f"[{backend}] ")
            if doc_label:
                header.append(str(doc_label))
            console.print(header)

            if heading:
                console.print(Text(f"  Heading: {heading}", style="bold"))
            if lines:
                console.print(Text(f"  Lines: {', '.join(str(line) for line in lines)}", style="dim"))
            if occurrences and backend == "grep":
                console.print(Text(f"  Matches: {occurrences}", style="dim"))

            snippet_text = _rich_snippet(result.chunk.text)
            if snippet_text:
                snippet_lines = snippet_text.wrap(console, width=console.width - 15)
                for line in snippet_lines:
                    line.pad_left(4)
                console.print(snippet_lines)

            console.print()
            continue

        line = f"{rank:>2}."
        if show_score:
            line += f" score={result.score:.4f}"
        if backend:
            line += f" [{backend}]"
        if doc_label:
            line += f" {doc_label}"
        print(line)
        if heading:
            print(f"    Heading: {heading}")
        if lines:
            print(f"    Lines: {', '.join(str(line) for line in lines)}")
        if occurrences and backend == "grep":
            print(f"    Matches: {occurrences}")
        snippet = result.chunk.text
        if snippet:
            for line in _format_plain_snippet(snippet):
                print(line)


def _rich_snippet(snippet: str):
    if not snippet:
        return None
    from rich.text import Text

    text = Text()
    cursor = 0
    while cursor < len(snippet):
        start = snippet.find("<<", cursor)
        if start == -1:
            text.append(snippet[cursor:])
            break
        text.append(snippet[cursor:start])
        end = snippet.find(">>", start)
        if end == -1:
            text.append(snippet[start:])
            break
        text.append(snippet[start + 2 : end], style="bold yellow")
        cursor = end + 2
    return text


def _format_plain_snippet(snippet: str, width: int = 100, indent: str = "      ") -> list[str]:
    formatted: list[str] = []
    for raw_line in snippet.splitlines():
        if not raw_line:
            formatted.append(indent)
            continue
        wrapped = textwrap.wrap(
            raw_line,
            width=width,
            initial_indent=indent,
            subsequent_indent=indent,
            break_long_words=False,
            break_on_hyphens=False,
        )
        if wrapped:
            formatted.extend(wrapped)
        else:
            formatted.append(indent + raw_line)
    return formatted


def _make_search_progress_callback(enabled: bool):
    if not enabled:
        return None

    def callback(event) -> None:
        if getattr(event, "event_type", None) == "error":
            print(f"[ERROR] {event.message}", file=sys.stderr)
            return
        if getattr(event, "event_type", None) == "item_done" and event.metadata.get("item_type") not in {
            "document",
            "search",
        }:
            return
        print(f"[{event.event_type.upper()}] {event.message}", file=sys.stderr)

    return callback


def _validate_similarity_threshold(value: str) -> float:
    """Validate similarity threshold is in [0.0, 1.0] range.

    Parameters
    ----------
    value : str
        Threshold value as string

    Returns
    -------
    float
        Validated threshold value

    Raises
    ------
    argparse.ArgumentTypeError
        If value is not in valid range

    """
    try:
        fvalue = float(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"similarity threshold must be a number, got '{value}'") from e

    if not 0.0 <= fvalue <= 1.0:
        raise argparse.ArgumentTypeError(f"similarity threshold must be between 0.0 and 1.0, got {fvalue}")

    return fvalue


def _validate_context_lines(value: str) -> int:
    """Validate context lines is a positive integer.

    Parameters
    ----------
    value : str
        Context lines value as string

    Returns
    -------
    int
        Validated context lines value

    Raises
    ------
    argparse.ArgumentTypeError
        If value is not a positive integer

    """
    try:
        ivalue = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"context lines must be an integer, got '{value}'") from e

    if ivalue < 0:
        raise argparse.ArgumentTypeError(f"context lines must be non-negative, got {ivalue}")

    return ivalue


def _colorize_diff_output(text: str) -> str:
    """Add rich markup to colorize diff output.

    Parameters
    ----------
    text : str
        Plain text diff output

    Returns
    -------
    str
        Text with rich markup for colors

    """
    lines = text.split("\n")
    colored_lines = []

    for line in lines:
        if line.startswith("+ "):
            # Added lines - green
            colored_lines.append(f"[green]{line}[/green]")
        elif line.startswith("- "):
            # Deleted lines - red
            colored_lines.append(f"[red]{line}[/red]")
        elif line.startswith("~ "):
            # Modified lines - yellow
            colored_lines.append(f"[yellow]{line}[/yellow]")
        elif line.startswith("> "):
            # Moved lines - blue
            colored_lines.append(f"[blue]{line}[/blue]")
        elif line.startswith("  "):
            # Context lines - dim
            colored_lines.append(f"[dim]{line}[/dim]")
        else:
            # Headers and other content - keep as is
            colored_lines.append(line)

    return "\n".join(colored_lines)


def _colorize_unified_diff(text: str, use_ansi: bool = True) -> str:
    """Add ANSI color codes to unified diff output.

    Parameters
    ----------
    text : str
        Plain unified diff output
    use_ansi : bool, default = True
        If True, use ANSI escape codes; if False, use rich markup

    Returns
    -------
    str
        Colorized diff output

    """
    if use_ansi:
        # ANSI color codes
        RED = "\033[31m"
        GREEN = "\033[32m"
        CYAN = "\033[36m"
        BOLD = "\033[1m"
        RESET = "\033[0m"
    else:
        # Rich markup (for when rich is available)
        RED = "[red]"
        GREEN = "[green]"
        CYAN = "[cyan]"
        BOLD = "[bold]"
        RESET = "[/red][/green][/cyan][/bold]"

    lines = text.split("\n")
    colored_lines = []

    for line in lines:
        if line.startswith("+++") or line.startswith("---"):
            # File headers - bold
            if use_ansi:
                colored_lines.append(f"{BOLD}{line}{RESET}")
            else:
                colored_lines.append(f"{BOLD}{line}{RESET}")
        elif line.startswith("@@"):
            # Hunk headers - cyan
            if use_ansi:
                colored_lines.append(f"{CYAN}{line}{RESET}")
            else:
                colored_lines.append(f"{CYAN}{line}{RESET}")
        elif line.startswith("+"):
            # Added lines - green
            if use_ansi:
                colored_lines.append(f"{GREEN}{line}{RESET}")
            else:
                colored_lines.append(f"{GREEN}{line}{RESET}")
        elif line.startswith("-"):
            # Deleted lines - red
            if use_ansi:
                colored_lines.append(f"{RED}{line}{RESET}")
            else:
                colored_lines.append(f"{RED}{line}{RESET}")
        else:
            # Context lines - no color
            colored_lines.append(line)

    return "\n".join(colored_lines)


def _create_diff_parser() -> argparse.ArgumentParser:
    """Create argparse parser for diff command.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser for diff command

    """
    parser = argparse.ArgumentParser(
        prog="all2md diff",
        description="Compare two documents and generate a unified diff (like diff but for any document format)",
        add_help=True,
    )

    # Positional arguments
    parser.add_argument("source1", help="First document (any supported format)")
    parser.add_argument("source2", help="Second document (any supported format)")

    # Output options
    parser.add_argument(
        "--format",
        "-f",
        choices=["unified", "html", "json"],
        default="unified",
        help="Output format: unified (default, like diff -u), html (visual), json (structured)",
    )
    parser.add_argument("--output", "-o", help="Write diff to file (default: stdout)")
    parser.add_argument(
        "--color",
        "--colour",
        dest="color",
        choices=["auto", "always", "never"],
        default="auto",
        help="Colorize output: auto (default, if terminal), always, never",
    )

    # Comparison options
    parser.add_argument(
        "--ignore-whitespace",
        "-w",
        action="store_true",
        help="Ignore whitespace changes (like diff -w)",
    )
    parser.add_argument(
        "--context",
        "-C",
        type=_validate_context_lines,
        default=3,
        help="Number of context lines (default: 3, like diff -C)",
    )

    # HTML-specific options
    parser.add_argument(
        "--no-context",
        dest="show_context",
        action="store_false",
        default=True,
        help="Hide context lines in HTML output",
    )

    return parser


def handle_diff_command(args: list[str] | None = None) -> int:
    """Handle diff command to compare two documents.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'diff')

    Returns
    -------
    int
        Exit code (0 for success)

    """
    from pathlib import Path

    from all2md.cli.builder import EXIT_ERROR, EXIT_FILE_ERROR
    from all2md.diff.renderers.html import HtmlDiffRenderer
    from all2md.diff.renderers.json import JsonDiffRenderer
    from all2md.diff.renderers.unified import UnifiedDiffRenderer
    from all2md.diff.text_diff import compare_files

    # Parse arguments
    parser = _create_diff_parser()
    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0

    # Validate source files
    source1_path = Path(parsed.source1)
    source2_path = Path(parsed.source2)

    if not source1_path.exists():
        print(f"Error: Source file not found: {parsed.source1}", file=sys.stderr)
        return EXIT_FILE_ERROR

    if not source2_path.exists():
        print(f"Error: Source file not found: {parsed.source2}", file=sys.stderr)
        return EXIT_FILE_ERROR

    try:
        # Compare documents using simple text-based diff
        print(f"Comparing {source1_path.name} and {source2_path.name}...", file=sys.stderr)
        diff_lines = compare_files(
            source1_path,
            source2_path,
            old_label=str(source1_path),
            new_label=str(source2_path),
            context_lines=parsed.context,
            ignore_whitespace=parsed.ignore_whitespace,
        )

        # Convert iterator to list for multiple passes (needed for some renderers)
        diff_lines_list = list(diff_lines)

        # Check if there are any changes
        has_changes = any(
            line.startswith("+") or line.startswith("-")
            for line in diff_lines_list
            if not line.startswith("+++") and not line.startswith("---")
        )

        if not has_changes:
            print("No differences found.", file=sys.stderr)
            # Still output empty diff in requested format
            if parsed.output:
                output_path = Path(parsed.output)
                if parsed.format == "html":
                    output = HtmlDiffRenderer(show_context=parsed.show_context).render(iter(diff_lines_list))
                elif parsed.format == "json":
                    output = JsonDiffRenderer().render(iter(diff_lines_list))
                else:
                    output = "\n".join(diff_lines_list)
                output_path.write_text(output, encoding="utf-8")
            return 0

        # Render diff based on format
        if parsed.format == "html":
            renderer = HtmlDiffRenderer(show_context=parsed.show_context)
            output = renderer.render(iter(diff_lines_list))

            # Write HTML output
            if parsed.output:
                output_path = Path(parsed.output)
                print(f"Writing HTML diff to {output_path}...", file=sys.stderr)
                output_path.write_text(output, encoding="utf-8")
                print(f"Diff written to: {output_path}", file=sys.stderr)
            else:
                print(output)

        elif parsed.format == "json":
            renderer = JsonDiffRenderer()
            output = renderer.render(iter(diff_lines_list))

            # Write JSON output
            if parsed.output:
                output_path = Path(parsed.output)
                print(f"Writing JSON diff to {output_path}...", file=sys.stderr)
                output_path.write_text(output, encoding="utf-8")
                print(f"Diff written to: {output_path}", file=sys.stderr)
            else:
                print(output)

        else:  # unified format (default)
            # Determine if we should use colors
            use_colors = False
            if parsed.color == "always":
                use_colors = True
            elif parsed.color == "auto" and not parsed.output:
                # Auto-detect: use colors if stdout is a TTY
                use_colors = sys.stdout.isatty()

            # Render with optional colors
            renderer = UnifiedDiffRenderer(use_color=use_colors)
            colored_lines = list(renderer.render(iter(diff_lines_list)))

            # Write output
            if parsed.output:
                output_path = Path(parsed.output)
                print(f"Writing unified diff to {output_path}...", file=sys.stderr)
                # Don't use colors when writing to file
                plain_renderer = UnifiedDiffRenderer(use_color=False)
                plain_lines = list(plain_renderer.render(iter(diff_lines_list)))
                output_path.write_text("\n".join(plain_lines), encoding="utf-8")
                print(f"Diff written to: {output_path}", file=sys.stderr)
            else:
                for line in colored_lines:
                    print(line)

        return 0

    except Exception as e:
        print(f"Error comparing documents: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        return EXIT_ERROR


def handle_dependency_commands(args: list[str] | None = None) -> int | None:
    """Handle dependency management commands.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments

    Returns
    -------
    int or None
        Exit code if dependency command was handled, None otherwise

    """
    if not args:
        args = sys.argv[1:]

    if not args:
        return None

    # Check for config command
    if args[0] == "config":
        return handle_config_command(args)

    # Check for generate-site command
    if args[0] == "generate-site":
        return handle_generate_site_command(args[1:])

    if args[0] == "search":
        return handle_search_command(args[1:])

    # Check for grep command
    if args[0] == "grep":
        return handle_grep_command(args[1:])

    # Check for diff command
    if args[0] == "diff":
        return handle_diff_command(args[1:])

    # Check for list-formats command
    if args[0] in ("list-formats", "formats"):
        return handle_list_formats_command(args[1:])

    # Check for list-transforms command
    if args[0] in ("list-transforms", "transforms"):
        return handle_list_transforms_command(args[1:])

    # Check for dependency management commands
    if args[0] == "check-deps":
        # Convert to standard deps CLI format
        deps_args = ["check"]

        # Parse remaining arguments
        remaining_args = args[1:]
        format_arg = None
        has_json = False
        has_rich = False
        has_help = False

        for arg in remaining_args:
            if arg in ("--help", "-h"):
                has_help = True
            elif arg == "--json":
                has_json = True
            elif arg == "--rich":
                has_rich = True
            elif not arg.startswith("-"):
                # This is the format argument
                format_arg = arg

        # Add arguments in the correct order
        if has_help:
            deps_args.append("--help")
        elif format_arg:
            deps_args.extend(["--format", format_arg])
            if has_json:
                deps_args.append("--json")
            if has_rich:
                deps_args.append("--rich")
        else:
            if has_json:
                deps_args.append("--json")
            if has_rich:
                deps_args.append("--rich")

        return deps_main(deps_args)

    return None
