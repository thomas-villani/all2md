#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/cli/_processors_detect.py
"""Detection and dry-run processing functions for all2md CLI.

This private module contains functions for format detection and dry-run mode.
"""

from __future__ import annotations

import argparse
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from all2md.cli.builder import EXIT_DEPENDENCY_ERROR
from all2md.cli.input_items import CLIInputItem
from all2md.converter_registry import check_package_installed, registry
from all2md.utils.packages import check_version_requirement

__all__ = [
    "_detect_format_for_item",
    "_check_converter_dependencies",
    "_render_detection_results_rich",
    "_render_detection_results_plain",
    "process_detect_only",
    "_collect_file_info_for_dry_run",
    "_determine_output_destination",
    "_render_dry_run_rich",
    "_render_dry_run_plain",
    "process_dry_run",
]


def _detect_format_for_item(item: CLIInputItem, format_arg: str) -> tuple[str, str]:
    """Detect format and detection method for a single item.

    Parameters
    ----------
    item : CLIInputItem
        Input item to detect format for
    format_arg : str
        Format argument from CLI

    Returns
    -------
    tuple[str, str]
        (detected_format, detection_method)

    """
    if format_arg != "auto":
        return format_arg, "explicit (--format)"

    detected_format = registry.detect_format(item.raw_input)

    # Determine detection method
    metadata_list = registry.get_format_info(detected_format)
    metadata = metadata_list[0] if metadata_list else None
    suffix = item.suffix.lower() if item.suffix else ""
    if metadata and suffix in metadata.extensions:
        return detected_format, "file extension"

    # Check MIME type
    guess_target = item.display_name
    if item.path_hint:
        guess_target = str(item.path_hint)
    mime_type, _ = mimetypes.guess_type(guess_target)
    if mime_type and metadata and mime_type in metadata.mime_types:
        return detected_format, "MIME type"

    return detected_format, "magic bytes/content"


def _check_converter_dependencies(
    converter_metadata: Any,
) -> tuple[bool, list[tuple[str, str, str | None, str | None]]]:
    """Check converter dependencies and return availability status.

    Parameters
    ----------
    converter_metadata : Any
        Converter metadata object

    Returns
    -------
    tuple[bool, list[tuple[str, str, str | None, str | None]]]
        (converter_available, dependency_status_list)

    """
    converter_available = True
    dependency_status: list[tuple[str, str, str | None, str | None]] = []

    if not converter_metadata or not converter_metadata.required_packages:
        return converter_available, dependency_status

    # required_packages is now a list of 3-tuples: (install_name, import_name, version_spec)
    for install_name, import_name, version_spec in converter_metadata.required_packages:
        if version_spec:
            # Use install_name for version checking (pip/metadata lookup)
            meets_req, installed_version = check_version_requirement(install_name, version_spec)
            if not meets_req:
                converter_available = False
                if installed_version:
                    dependency_status.append((install_name, "version mismatch", installed_version, version_spec))
                else:
                    dependency_status.append((install_name, "missing", None, version_spec))
            else:
                dependency_status.append((install_name, "ok", installed_version, version_spec))
        else:
            # Use import_name for import checking
            if not check_package_installed(import_name):
                converter_available = False
                dependency_status.append((install_name, "missing", None, None))
            else:
                dependency_status.append((install_name, "ok", None, None))

    return converter_available, dependency_status


def _render_detection_results_rich(detection_results: list[dict[str, Any]], any_issues: bool) -> None:
    """Render detection results using rich formatting.

    Parameters
    ----------
    detection_results : list[dict[str, Any]]
        List of detection results
    any_issues : bool
        Whether there were any dependency issues

    """
    from rich.console import Console
    from rich.table import Table

    console = Console()

    # Main detection table
    table = Table(title="Format Detection Results")
    table.add_column("Input", style="cyan", no_wrap=False)
    table.add_column("Detected Format", style="yellow")
    table.add_column("Detection Method", style="magenta")
    table.add_column("Converter Status", style="white")

    for result in detection_results:
        if result["available"]:
            status = "[green][OK] Available[/green]"
        else:
            status = "[red][X] Unavailable[/red]"

        table.add_row(result["item"].display_name, result["format"].upper(), result["method"], status)

    console.print(table)

    # Show dependency details if there are issues
    if any_issues:
        console.print("\n[bold yellow]Dependency Issues:[/bold yellow]")
        for result in detection_results:
            if not result["available"]:
                console.print(f"\n[cyan]{result['item'].display_name}[/cyan] ({result['format'].upper()}):")
                for pkg_name, status, installed, required in result["deps"]:
                    if status == "missing":
                        console.print(f"  [red][X] {pkg_name} - Not installed[/red]")
                    elif status == "version mismatch":
                        msg = f"  [yellow][!] {pkg_name} - Version mismatch"
                        msg += f" (requires {required}, installed: {installed})[/yellow]"
                        console.print(msg)

                if result["metadata"]:
                    install_cmd = result["metadata"].get_install_command()
                    console.print(f"  [dim]Install: {install_cmd}[/dim]")


def _render_detection_results_plain(detection_results: list[dict[str, Any]]) -> None:
    """Render detection results using plain text formatting.

    Parameters
    ----------
    detection_results : list[dict[str, Any]]
        List of detection results

    """
    for i, result in enumerate(detection_results, 1):
        status = "[OK]" if result["available"] else "[X]"
        print(f"{i:3d}. {status} {result['item'].display_name}")
        print(f"     Format: {result['format'].upper()}")
        print(f"     Detection: {result['method']}")

        if result["deps"]:
            print("     Dependencies:")
            for pkg_name, status_str, installed, required in result["deps"]:
                if status_str == "ok":
                    version_info = f" ({installed})" if installed else ""
                    print(f"       [OK] {pkg_name}{version_info}")
                elif status_str == "missing":
                    print(f"       [MISSING] {pkg_name}")
                elif status_str == "version mismatch":
                    print(f"       [MISMATCH] {pkg_name} (requires {required}, installed: {installed})")

            if not result["available"] and result["metadata"]:
                install_cmd = result["metadata"].get_install_command()
                print(f"     Install: {install_cmd}")
        else:
            print("     Dependencies: None required")

        print()


def process_detect_only(items: List[CLIInputItem], args: argparse.Namespace, format_arg: str) -> int:
    """Process inputs in detect-only mode - show format detection without conversion plan."""
    # Auto-discover parsers
    registry.auto_discover()

    print("DETECT-ONLY MODE - Format Detection Results")
    print(f"Analyzing {len(items)} input(s)")
    print()

    # Gather detection info
    detection_results: list[dict[str, Any]] = []
    any_issues = False

    for item in items:
        # Detect format and method
        detected_format, detection_method = _detect_format_for_item(item, format_arg)

        # Get converter info
        converter_metadata_list = registry.get_format_info(detected_format)
        converter_metadata = converter_metadata_list[0] if converter_metadata_list else None

        # Check dependencies
        converter_available, dependency_status = _check_converter_dependencies(converter_metadata)

        # Track if there are any issues
        if not converter_available:
            any_issues = True

        detection_results.append(
            {
                "item": item,
                "format": detected_format,
                "method": detection_method,
                "available": converter_available,
                "deps": dependency_status,
                "metadata": converter_metadata,
            }
        )

    # Display results
    if args.rich:
        try:
            _render_detection_results_rich(detection_results, any_issues)
        except ImportError:
            # Fall back to plain text
            args.rich = False

    if not args.rich:
        _render_detection_results_plain(detection_results)

    # Print summary
    print(f"\nTotal inputs analyzed: {len(detection_results)}")
    if any_issues:
        unavailable_count = sum(1 for r in detection_results if not r["available"])
        print(f"Inputs with unavailable parsers: {unavailable_count}")
        return EXIT_DEPENDENCY_ERROR
    else:
        print("All detected parsers are available")
        return 0


def _collect_file_info_for_dry_run(items: List[CLIInputItem], format_arg: str) -> List[Dict[str, Any]]:
    """Collect file information for dry run display.

    Parameters
    ----------
    items : list of CLIInputItem
        Input items to analyze
    format_arg : str
        Format specification

    Returns
    -------
    list of dict
        List of file info dictionaries

    """
    file_info_list: List[Dict[str, Any]] = []

    for index, item in enumerate(items, start=1):
        if format_arg != "auto":
            detected_format = format_arg
            detection_method = "explicit (--format)"
        else:
            detected_format = registry.detect_format(item.raw_input)

            all_extensions: List[str] = []
            for fmt_name in registry.list_formats():
                fmt_info_list = registry.get_format_info(fmt_name)
                if fmt_info_list:
                    for fmt_info in fmt_info_list:
                        all_extensions.extend(fmt_info.extensions)

            suffix = item.suffix.lower() if item.suffix else ""
            detection_method = "extension" if suffix in all_extensions else "content analysis"

        converter_metadata_list = registry.get_format_info(detected_format)
        converter_metadata = converter_metadata_list[0] if converter_metadata_list else None

        converter_available = True
        dependency_issues: List[str] = []

        if converter_metadata:
            required_packages = converter_metadata.get_required_packages_for_content(
                content=None,
                input_data=item.display_name,
            )

            if required_packages:
                for pkg_name, _import_name, version_spec in required_packages:
                    if version_spec:
                        meets_req, installed_version = check_version_requirement(pkg_name, version_spec)
                        if not meets_req:
                            converter_available = False
                            if installed_version:
                                dependency_issues.append(f"{pkg_name} (version mismatch)")
                            else:
                                dependency_issues.append(f"{pkg_name} (missing)")
                    else:
                        if not check_package_installed(pkg_name):
                            converter_available = False
                            dependency_issues.append(f"{pkg_name} (missing)")

        file_info_list.append(
            {
                "item": item,
                "detected_format": detected_format,
                "detection_method": detection_method,
                "converter_available": converter_available,
                "dependency_issues": dependency_issues,
                "converter_metadata": converter_metadata,
                "index": index,
            }
        )

    return file_info_list


def _determine_output_destination(
    item: CLIInputItem,
    args: argparse.Namespace,
    file_info_list: List[Dict[str, Any]],
    base_input_dir: Optional[Path],
    index: int,
    generate_output_path_fn: Any,
) -> str:
    """Determine output destination for an item in dry run.

    Parameters
    ----------
    item : CLIInputItem
        Input item
    args : argparse.Namespace
        Command line arguments
    file_info_list : list of dict
        All file info
    base_input_dir : Path or None
        Base input directory
    index : int
        Item index
    generate_output_path_fn : callable
        Function to generate output paths

    Returns
    -------
    str
        Output destination string

    """
    if args.collate:
        return str(Path(args.out)) if args.out else "stdout (collated)"

    if len(file_info_list) == 1 and args.out and not args.output_dir:
        return str(Path(args.out))

    if args.output_dir:
        target_format = getattr(args, "output_format", "markdown")
        computed = generate_output_path_fn(
            item,
            Path(args.output_dir),
            args.preserve_structure,
            base_input_dir,
            target_format,
            index,
            dry_run=True,
        )
        return str(computed)

    return "stdout"


def _render_dry_run_rich(
    file_info_list: List[Dict[str, Any]],
    args: argparse.Namespace,
    base_input_dir: Optional[Path],
    generate_output_path_fn: Any,
) -> bool:
    """Render dry run output using rich formatting.

    Parameters
    ----------
    file_info_list : list of dict
        File information list
    args : argparse.Namespace
        Command line arguments
    base_input_dir : Path or None
        Base input directory
    generate_output_path_fn : callable
        Function to generate output paths

    Returns
    -------
    bool
        True if successfully rendered with rich, False otherwise

    """
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title="Dry Run - Planned Conversions")
        table.add_column("Input", style="cyan", no_wrap=False)
        table.add_column("Output", style="green", no_wrap=False)
        table.add_column("Format", style="yellow")
        table.add_column("Detection", style="magenta")
        table.add_column("Status", style="white")

        for info in file_info_list:
            item = info["item"]
            output_str = _determine_output_destination(
                item, args, file_info_list, base_input_dir, info["index"], generate_output_path_fn
            )

            if info["converter_available"]:
                status = "[green][OK] Ready[/green]"
            else:
                issues = ", ".join(info["dependency_issues"][:2])
                if len(info["dependency_issues"]) > 2:
                    issues += "..."
                status = f"[red][X] {issues}[/red]"

            table.add_row(
                item.display_name,
                output_str,
                info["detected_format"].upper(),
                info["detection_method"],
                status,
            )

        console.print(table)
        return True

    except ImportError:
        return False


def _render_dry_run_plain(
    file_info_list: List[Dict[str, Any]],
    args: argparse.Namespace,
    base_input_dir: Optional[Path],
    generate_output_path_fn: Any,
) -> None:
    """Render dry run output using plain text.

    Parameters
    ----------
    file_info_list : list of dict
        File information list
    args : argparse.Namespace
        Command line arguments
    base_input_dir : Path or None
        Base input directory
    generate_output_path_fn : callable
        Function to generate output paths

    """
    for info in file_info_list:
        item = info["item"]
        print(f"{item.display_name}")
        print(f"  Format: {info['detected_format'].upper()} ({info['detection_method']})")

        if info["converter_available"]:
            print("  Status: ready")
        else:
            issues_str = ", ".join(info["dependency_issues"]) or "dependency issues"
            print(f"  Status: missing requirements ({issues_str})")

        destination = _determine_output_destination(
            item, args, file_info_list, base_input_dir, info["index"], generate_output_path_fn
        )
        print(f"  Output: {destination}")
        print()


def process_dry_run(
    items: List[CLIInputItem],
    args: argparse.Namespace,
    format_arg: str,
    compute_base_input_dir_fn: Any,
    generate_output_path_fn: Any,
) -> int:
    """Show what would be processed without performing any conversions.

    Parameters
    ----------
    items : list of CLIInputItem
        Input items to process
    args : argparse.Namespace
        Command line arguments
    format_arg : str
        Format specification
    compute_base_input_dir_fn : callable
        Function to compute base input directory
    generate_output_path_fn : callable
        Function to generate output paths

    Returns
    -------
    int
        Exit code

    """
    base_input_dir = compute_base_input_dir_fn(items, args.preserve_structure)

    registry.auto_discover()

    print("DRY RUN MODE - Showing what would be processed")
    print(f"Found {len(items)} input(s) to convert")
    print()

    file_info_list = _collect_file_info_for_dry_run(items, format_arg)

    if args.rich:
        if not _render_dry_run_rich(file_info_list, args, base_input_dir, generate_output_path_fn):
            args.rich = False

    if not args.rich:
        _render_dry_run_plain(file_info_list, args, base_input_dir, generate_output_path_fn)

    print("Options that would be used:")
    if args.format != "auto":
        print(f"  Format: {args.format}")
    if args.recursive:
        print("  Recursive directory processing: enabled")
    parallel_provided = hasattr(args, "_provided_args") and "parallel" in args._provided_args
    if parallel_provided and args.parallel is None:
        worker_count = os.cpu_count() or "auto"
        print(f"  Parallel processing: {worker_count} workers (auto-detected)")
    elif isinstance(args.parallel, int) and args.parallel != 1:
        print(f"  Parallel processing: {args.parallel} workers")
    if args.preserve_structure:
        print("  Preserve directory structure: enabled")
    if args.collate:
        print("  Collate multiple inputs: enabled")
    if args.exclude:
        print(f"  Exclusion patterns: {', '.join(args.exclude)}")

    print()
    print("No inputs were converted (dry run mode).")
    return 0
