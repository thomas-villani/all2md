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
        List of format info dictionaries with separate parser/renderer availability

    """
    format_info_list: list[dict[str, Any]] = []
    for format_name in formats:
        metadata_list = registry.get_format_info(format_name)
        if not metadata_list or len(metadata_list) == 0:
            continue

        # Use the highest priority (first) converter
        metadata = metadata_list[0]

        # Check parser dependency status
        parser_available = True
        parser_dep_status: list[tuple[str, str | None, str, str | None]] = []

        for install_name, _import_name, version_spec in metadata.parser_required_packages:
            if version_spec:
                meets_req, installed_version = check_version_requirement(install_name, version_spec)
                if not meets_req:
                    parser_available = False
                    if installed_version:
                        parser_dep_status.append((install_name, version_spec, "mismatch", installed_version))
                    else:
                        parser_dep_status.append((install_name, version_spec, "missing", None))
                else:
                    parser_dep_status.append((install_name, version_spec, "ok", installed_version))
            else:
                installed_version = get_package_version(install_name)
                if installed_version:
                    parser_dep_status.append((install_name, version_spec, "ok", installed_version))
                else:
                    parser_available = False
                    parser_dep_status.append((install_name, version_spec, "missing", None))

        # Check renderer dependency status
        renderer_available = True
        renderer_dep_status: list[tuple[str, str | None, str, str | None]] = []

        for install_name, _import_name, version_spec in metadata.renderer_required_packages:
            if version_spec:
                meets_req, installed_version = check_version_requirement(install_name, version_spec)
                if not meets_req:
                    renderer_available = False
                    if installed_version:
                        renderer_dep_status.append((install_name, version_spec, "mismatch", installed_version))
                    else:
                        renderer_dep_status.append((install_name, version_spec, "missing", None))
                else:
                    renderer_dep_status.append((install_name, version_spec, "ok", installed_version))
            else:
                installed_version = get_package_version(install_name)
                if installed_version:
                    renderer_dep_status.append((install_name, version_spec, "ok", installed_version))
                else:
                    renderer_available = False
                    renderer_dep_status.append((install_name, version_spec, "missing", None))

        # Overall availability
        all_available = parser_available and renderer_available

        # Skip if filtering for available only
        if available_only and not all_available:
            continue

        format_info_list.append(
            {
                "name": format_name,
                "metadata": metadata,
                "all_available": all_available,
                "parser_available": parser_available,
                "renderer_available": renderer_available,
                "parser_dep_status": parser_dep_status,
                "renderer_dep_status": renderer_dep_status,
                # Keep combined for backward compatibility
                "dep_status": parser_dep_status + renderer_dep_status,
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
    has_parser = fmt_metadata.parser_class is not None
    has_renderer = fmt_metadata.renderer_class is not None

    parser_status = "[green][OK][/green]" if info["parser_available"] else "[red][X][/red]"
    renderer_status = "[green][OK][/green]" if info["renderer_available"] else "[red][X][/red]"

    parser_info = parser_status if has_parser else "[dim](not implemented)[/dim]"
    renderer_info = renderer_status if has_renderer else "[dim](not implemented)[/dim]"

    content = [
        f"[bold]Format:[/bold] {info['name'].upper()}",
        f"[bold]Description:[/bold] {fmt_metadata.description or 'N/A'}",
        f"[bold]Extensions:[/bold] {', '.join(fmt_metadata.extensions) or 'N/A'}",
        f"[bold]MIME Types:[/bold] {', '.join(fmt_metadata.mime_types) or 'N/A'}",
        f"[bold]Parser:[/bold] {fmt_metadata.get_parser_display_name()} {parser_info}",
        f"[bold]Renderer:[/bold] {fmt_metadata.get_renderer_display_name()} {renderer_info}",
        f"[bold]Priority:[/bold] {fmt_metadata.priority}",
    ]

    console.print(Panel("\n".join(content), title=f"{info['name'].upper()} Format Details"))

    # Parser Dependencies
    if info["parser_dep_status"]:
        parser_table = Table(title="Parser Dependencies")
        parser_table.add_column("Package", style="cyan")
        parser_table.add_column("Required", style="yellow")
        parser_table.add_column("Status", style="magenta")
        parser_table.add_column("Installed", style="green")

        for pkg_name, version_spec, status, installed_version in info["parser_dep_status"]:
            status_icon = {
                "ok": "[green][OK] Available[/green]",
                "missing": "[red][X] Missing[/red]",
                "mismatch": "[yellow][!] Version Mismatch[/yellow]",
            }[status]

            parser_table.add_row(pkg_name, version_spec or "any", status_icon, installed_version or "N/A")

        console.print(parser_table)

        if not info["parser_available"]:
            # Build install command for parser deps only
            parser_packages = []
            for pkg_name, _import_name, version_spec in fmt_metadata.parser_required_packages:
                if version_spec:
                    parser_packages.append(f'"{pkg_name}{version_spec}"')
                else:
                    parser_packages.append(pkg_name)
            install_cmd = f"pip install {' '.join(parser_packages)}"
            console.print(f"\n[yellow]Install parser dependencies:[/yellow] {install_cmd}")
    elif has_parser:
        console.print("[green]Parser: No dependencies required[/green]")

    # Renderer Dependencies
    if info["renderer_dep_status"]:
        renderer_table = Table(title="Renderer Dependencies")
        renderer_table.add_column("Package", style="cyan")
        renderer_table.add_column("Required", style="yellow")
        renderer_table.add_column("Status", style="magenta")
        renderer_table.add_column("Installed", style="green")

        for pkg_name, version_spec, status, installed_version in info["renderer_dep_status"]:
            status_icon = {
                "ok": "[green][OK] Available[/green]",
                "missing": "[red][X] Missing[/red]",
                "mismatch": "[yellow][!] Version Mismatch[/yellow]",
            }[status]

            renderer_table.add_row(pkg_name, version_spec or "any", status_icon, installed_version or "N/A")

        console.print(renderer_table)

        if not info["renderer_available"]:
            # Build install command for renderer deps only
            renderer_packages = []
            for pkg_name, _import_name, version_spec in fmt_metadata.renderer_required_packages:
                if version_spec:
                    renderer_packages.append(f'"{pkg_name}{version_spec}"')
                else:
                    renderer_packages.append(pkg_name)
            install_cmd = f"pip install {' '.join(renderer_packages)}"
            console.print(f"\n[yellow]Install renderer dependencies:[/yellow] {install_cmd}")
    elif has_renderer:
        console.print("[green]Renderer: No dependencies required[/green]")

    if not has_parser and not has_renderer:
        console.print("[yellow]No parser or renderer implemented for this format[/yellow]")


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
    table.add_column("Parser", style="blue")
    table.add_column("Renderer", style="green")
    table.add_column("Dependencies", style="white")

    for info in format_info_list:
        metadata = info["metadata"]

        # Extensions
        ext_str = ", ".join(metadata.extensions[:4])
        if len(metadata.extensions) > 4:
            ext_str += f" +{len(metadata.extensions) - 4}"

        # Parser status
        has_parser = metadata.parser_class is not None
        if not has_parser:
            parser_status = "[dim]N/A[/dim]"
        elif info["parser_available"]:
            parser_status = "[green][OK][/green]"
        else:
            parser_status = "[red][X][/red]"

        # Renderer status
        has_renderer = metadata.renderer_class is not None
        if not has_renderer:
            renderer_status = "[dim]N/A[/dim]"
        elif info["renderer_available"]:
            renderer_status = "[green][OK][/green]"
        else:
            renderer_status = "[red][X][/red]"

        # Dependencies summary
        parser_deps = info["parser_dep_status"]
        renderer_deps = info["renderer_dep_status"]

        if parser_deps or renderer_deps:
            parser_ok = sum(1 for _, _, s, _ in parser_deps if s == "ok")
            parser_total = len(parser_deps)
            renderer_ok = sum(1 for _, _, s, _ in renderer_deps if s == "ok")
            renderer_total = len(renderer_deps)

            parts = []
            if parser_deps:
                parts.append(f"P:{parser_ok}/{parser_total}")
            if renderer_deps:
                parts.append(f"R:{renderer_ok}/{renderer_total}")
            dep_str = " ".join(parts) if parts else "none"
        else:
            dep_str = "none"

        table.add_row(info["name"].upper(), ext_str, parser_status, renderer_status, dep_str)

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

    has_parser = metadata_obj.parser_class is not None
    has_renderer = metadata_obj.renderer_class is not None

    parser_status = "[OK]" if info["parser_available"] else "[X]"
    renderer_status = "[OK]" if info["renderer_available"] else "[X]"

    parser_info = f"{parser_status}" if has_parser else "(not implemented)"
    renderer_info = f"{renderer_status}" if has_renderer else "(not implemented)"

    print(f"\n{info['name'].upper()} Format")
    print("=" * 80)
    print(f"Description: {metadata_obj.description or 'N/A'}")
    print(f"Extensions: {', '.join(metadata_obj.extensions) or 'N/A'}")
    print(f"MIME Types: {', '.join(metadata_obj.mime_types) or 'N/A'}")
    print(f"Parser: {metadata_obj.get_parser_display_name()} {parser_info}")
    print(f"Renderer: {metadata_obj.get_renderer_display_name()} {renderer_info}")
    print(f"Priority: {metadata_obj.priority}")

    # Parser Dependencies
    if info["parser_dep_status"]:
        print("\nParser Dependencies:")
        for pkg_name, version_spec, status, installed_version in info["parser_dep_status"]:
            status_str = {"ok": "[OK]", "missing": "[MISSING]", "mismatch": "[VERSION MISMATCH]"}[status]
            version_str = f" {version_spec}" if version_spec else ""
            installed_str = f" (installed: {installed_version})" if installed_version else ""
            print(f"  {status_str} {pkg_name}{version_str}{installed_str}")

        if not info["parser_available"]:
            parser_packages = []
            for pkg_name, _import_name, version_spec in metadata_obj.parser_required_packages:
                if version_spec:
                    parser_packages.append(f'"{pkg_name}{version_spec}"')
                else:
                    parser_packages.append(pkg_name)
            install_cmd = f"pip install {' '.join(parser_packages)}"
            print(f"\nInstall parser dependencies: {install_cmd}")
    elif has_parser:
        print("\nParser: No dependencies required")

    # Renderer Dependencies
    if info["renderer_dep_status"]:
        print("\nRenderer Dependencies:")
        for pkg_name, version_spec, status, installed_version in info["renderer_dep_status"]:
            status_str = {"ok": "[OK]", "missing": "[MISSING]", "mismatch": "[VERSION MISMATCH]"}[status]
            version_str = f" {version_spec}" if version_spec else ""
            installed_str = f" (installed: {installed_version})" if installed_version else ""
            print(f"  {status_str} {pkg_name}{version_str}{installed_str}")

        if not info["renderer_available"]:
            renderer_packages = []
            for pkg_name, _import_name, version_spec in metadata_obj.renderer_required_packages:
                if version_spec:
                    renderer_packages.append(f'"{pkg_name}{version_spec}"')
                else:
                    renderer_packages.append(pkg_name)
            install_cmd = f"pip install {' '.join(renderer_packages)}"
            print(f"\nInstall renderer dependencies: {install_cmd}")
    elif has_renderer:
        print("\nRenderer: No dependencies required")

    if not has_parser and not has_renderer:
        print("\nNo parser or renderer implemented for this format")


def _render_plain_summary_formats(format_info_list: list[dict[str, Any]]) -> None:
    """Render summary of all formats as plain text.

    Parameters
    ----------
    format_info_list : list[dict]
        List of format information dictionaries

    """
    print("\nAll2MD Supported Formats")
    print("=" * 80)
    print(f"{'Format':<12} {'Parser':<8} {'Renderer':<10} {'Extensions'}")
    print("-" * 80)

    for info in format_info_list:
        format_meta = info["metadata"]
        assert format_meta is not None

        ext_str = ", ".join(format_meta.extensions[:4])
        if len(format_meta.extensions) > 4:
            ext_str += f" +{len(format_meta.extensions) - 4}"

        # Parser status
        has_parser = format_meta.parser_class is not None
        if not has_parser:
            parser_status = "N/A"
        elif info["parser_available"]:
            parser_status = "[OK]"
        else:
            parser_status = "[X]"

        # Renderer status
        has_renderer = format_meta.renderer_class is not None
        if not has_renderer:
            renderer_status = "N/A"
        elif info["renderer_available"]:
            renderer_status = "[OK]"
        else:
            renderer_status = "[X]"

        print(f"{info['name'].upper():<12} {parser_status:<8} {renderer_status:<10} {ext_str}")

    print(f"\nTotal: {len(format_info_list)} formats")
    print("\nLegend: [OK] = Available, [X] = Dependencies missing, N/A = Not implemented")


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
