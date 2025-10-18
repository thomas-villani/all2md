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
from dataclasses import fields, is_dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse

from all2md.cli.builder import (
    EXIT_FILE_ERROR,
    EXIT_VALIDATION_ERROR,
    DynamicCLIBuilder,
    create_parser,
)
from all2md.cli.help_formatter import display_help
from all2md.cli.input_items import CLIInputItem
from all2md.cli.processors import (
    process_multi_file,
    setup_and_validate_options,
)
from all2md.cli.validation import (
    validate_arguments,
)
from all2md.constants import DOCUMENT_EXTENSIONS, PLAINTEXT_EXTENSIONS
from all2md.converter_metadata import ConverterMetadata
from all2md.converter_registry import registry
from all2md.dependencies import check_version_requirement, get_package_version
from all2md.logging_utils import configure_logging as configure_root_logging
from all2md.transforms import registry as transform_registry

logger = logging.getLogger(__name__)

ALL_ALLOWED_EXTENSIONS = PLAINTEXT_EXTENSIONS + DOCUMENT_EXTENSIONS


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
    except TypeError:
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
            # Check for plain object() sentinels (used for UNSET in MarkdownOptions)
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
        extensions = ALL_ALLOWED_EXTENSIONS.copy()

    normalized_exts = {ext.lower() for ext in extensions} if extensions else None

    local_candidates: List[Path] = []
    remote_items: Dict[str, CLIInputItem] = {}
    stdin_item: Optional[CLIInputItem] = None
    stdin_data: bytes | None = None

    def extension_allowed(path: Path) -> bool:
        if normalized_exts is None:
            return True
        return path.suffix.lower() in normalized_exts

    for raw_argument in input_paths:
        if raw_argument == "-":
            if stdin_item is not None:
                continue
            if stdin_data is None:
                stdin_data = sys.stdin.buffer.read()
            if len(stdin_data) > 0:
                stdin_item = CLIInputItem(
                    raw_input=stdin_data or b"",
                    kind="stdin_bytes",
                    display_name="<stdin>",
                    original_argument=raw_argument,
                )
            continue

        if _is_probable_uri(raw_argument):
            path_hint, metadata = _derive_path_hint_from_uri(raw_argument)
            key = _normalize_uri_key(raw_argument)
            if key in remote_items:
                continue
            remote_items[key] = CLIInputItem(
                raw_input=raw_argument,
                kind="remote_uri",
                display_name=raw_argument,
                path_hint=path_hint,
                original_argument=raw_argument,
                metadata=metadata,
            )
            continue

        input_path = Path(raw_argument)
        matched_paths: List[Path] = []

        if any(char in raw_argument for char in "*?["):
            matched_paths.extend(Path.cwd().glob(raw_argument))
        elif input_path.is_file():
            matched_paths.append(input_path)
        elif input_path.is_dir():
            iterator = input_path.rglob("*") if recursive else input_path.iterdir()
            for child in iterator:
                if child.is_file():
                    matched_paths.append(child)
        else:
            logging.warning(f"Path does not exist: {input_path}")
            continue

        for candidate in matched_paths:
            if not candidate.is_file():
                continue
            if not extension_allowed(candidate):
                continue
            local_candidates.append(candidate)

    # Deduplicate and sort local paths for deterministic ordering
    unique_local: Dict[str, Path] = {}
    for candidate in local_candidates:
        try:
            key = str(candidate.resolve())
        except OSError:
            key = str(candidate)
        unique_local[key] = candidate

    sorted_local_paths = sorted(unique_local.values())

    local_items: List[CLIInputItem] = [
        CLIInputItem(
            raw_input=path,
            kind="local_file",
            display_name=str(path),
            path_hint=path,
            original_argument=str(path),
        )
        for path in sorted_local_paths
    ]

    all_items: List[CLIInputItem] = []

    all_items.extend(remote_items.values())
    all_items.extend(local_items)
    if stdin_item is not None:
        all_items.append(stdin_item)

    if exclude_patterns:
        filtered: List[CLIInputItem] = []
        for item in all_items:
            if any(_matches_exclusion(item, pattern) for pattern in exclude_patterns):
                continue
            filtered.append(item)
        all_items = filtered

    # Deterministic ordering for downstream processing
    all_items.sort(key=lambda item: item.display_name.lower())

    return all_items


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

        # required_packages is now a list of 3-tuples: (install_name, import_name, version_spec)
        for install_name, _import_name, version_spec in metadata.required_packages:
            if version_spec:
                # Use install_name for version checking (pip/metadata lookup)
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
                # Use install_name for version lookup (consistent with version checking)
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

    # Display results
    if use_rich:
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table

            console = Console()

            if specific_format:
                # Detailed view for specific format
                info = format_info_list[0] if format_info_list else None
                if info:
                    fmt_metadata: ConverterMetadata | None = info["metadata"]
                    assert fmt_metadata is not None  # Already filtered in list construction

                    # Create main panel
                    content = []
                    content.append(f"[bold]Format:[/bold] {info['name'].upper()}")
                    content.append(f"[bold]Description:[/bold] {fmt_metadata.description or 'N/A'}")
                    content.append(f"[bold]Extensions:[/bold] {', '.join(fmt_metadata.extensions) or 'N/A'}")
                    content.append(f"[bold]MIME Types:[/bold] {', '.join(fmt_metadata.mime_types) or 'N/A'}")
                    content.append(f"[bold]Converter:[/bold] {fmt_metadata.get_converter_display_string()}")
                    content.append(f"[bold]Priority:[/bold] {fmt_metadata.priority}")

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

                        # Show install command if needed
                        if not info["all_available"]:
                            install_cmd = fmt_metadata.get_install_command()
                            console.print(f"\n[yellow]Install with:[/yellow] {install_cmd}")
                    else:
                        console.print("[green]No dependencies required[/green]")

            else:
                # Summary table for all formats
                table = Table(title=f"All2MD Supported Formats ({len(format_info_list)} formats)")
                table.add_column("Format", style="cyan", no_wrap=True)
                table.add_column("Extensions", style="yellow")
                table.add_column("Capabilities", style="blue")
                table.add_column("Status", style="magenta")
                table.add_column("Dependencies", style="white")

                for info in format_info_list:
                    metadata = info["metadata"]

                    # Status indicator
                    if info["all_available"]:
                        status = "[green][OK] Available[/green]"
                    else:
                        status = "[red][X] Unavailable[/red]"

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

        except ImportError:
            # Fall back to plain text
            use_rich = False

    if not use_rich:
        # Plain text output
        if specific_format:
            info = format_info_list[0] if format_info_list else None
            if info:
                metadata_obj: ConverterMetadata | None = info["metadata"]
                assert metadata_obj is not None  # Already filtered in list construction
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
        else:
            print("\nAll2MD Supported Formats")
            print("=" * 60)
            for info in format_info_list:
                format_meta: ConverterMetadata | None = info["metadata"]
                assert format_meta is not None  # Already filtered in list construction
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


def handle_convert_command(args: list[str] | None = None) -> int | None:
    """Handle the `convert` subcommand for bidirectional conversions."""
    # TODO: remove this legacy command once users have fully transitioned to the top-level CLI.
    if not args:
        args = sys.argv[1:]

    if not args or args[0] != "convert":
        return None

    convert_args = args[1:]
    parser = create_parser()
    parsed_args = parser.parse_args(convert_args)

    provided_args: set[str] = getattr(parsed_args, "_provided_args", set())

    if "output_type" not in provided_args:
        parsed_args.output_type = "auto"

    if not parsed_args.out and not parsed_args.output_dir and len(parsed_args.input) == 2:
        parsed_args.out = parsed_args.input[-1]
        parsed_args.input = parsed_args.input[:1]

    if not parsed_args.config:
        env_config = os.environ.get("ALL2MD_CONFIG")
        if env_config:
            parsed_args.config = env_config

    if parsed_args.about:
        print(_get_about_info())
        return 0

    if parsed_args.save_config:
        try:
            save_config_to_file(parsed_args, parsed_args.save_config)
            return 0
        except Exception as exc:
            print(f"Error saving configuration: {exc}", file=sys.stderr)
            return 1

    return _run_convert_command(parsed_args)


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
    from all2md.cli.config import get_config_search_paths, load_config_with_priority

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
    from all2md.cli.config import load_config_file

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

    # Check for list-formats command
    if args[0] in ("list-formats", "formats"):
        return handle_list_formats_command(args[1:])

    # Check for list-transforms command
    if args[0] in ("list-transforms", "transforms"):
        return handle_list_transforms_command(args[1:])

    # Check for dependency management commands
    if args[0] == "check-deps":
        from all2md.dependencies import main as deps_main

        # Convert to standard deps CLI format
        deps_args = ["check"]

        # Check for help flags first
        if len(args) > 1 and args[1] in ("--help", "-h"):
            deps_args.append("--help")
        elif len(args) > 1 and args[1] not in ("--help", "-h"):
            # Only add format if it's not a help flag
            deps_args.extend(["--format", args[1]])
            # Check for help flags after format
            if len(args) > 2 and args[2] in ("--help", "-h"):
                deps_args.append("--help")

        return deps_main(deps_args)

    return None
