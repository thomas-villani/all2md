#  Copyright (c) 2025 Tom Villani, Ph.D.

# ${DIR_PATH}/${FILE_NAME}
"""Format listing command for all2md CLI.

This module provides the list-formats command for displaying information
about available document parsers and renderers, including their file
extensions, MIME types, capabilities, and dependency status. Supports
both plain text and rich terminal output.
"""
import argparse
import sys
from typing import Any

from all2md.cli.builder import EXIT_VALIDATION_ERROR
from all2md.converter_registry import registry
from all2md.utils.packages import check_version_requirement, get_package_version


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
