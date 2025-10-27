"""Dependency management utilities for all2md.

This module provides utilities for checking and reporting on
optional dependencies for various converter modules.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Tuple

from all2md.cli.output import should_use_rich_output
from all2md.converter_registry import check_package_installed, registry
from all2md.utils.packages import check_version_requirement, get_package_version


def get_all_dependencies() -> Dict[str, List[Tuple[str, str, str]]]:
    """Get all dependencies for all parsers from the registry.

    Returns
    -------
    dict
        Mapping of format names to required packages as (install_name, import_name, version_spec) tuples

    """
    # Ensure auto-discovery has been performed before listing formats
    registry.auto_discover()

    dependencies = {}
    for format_name in registry.list_formats():
        metadata_list = registry.get_format_info(format_name)
        if metadata_list and len(metadata_list) > 0:
            # Use the highest priority (first) converter's dependencies
            metadata = metadata_list[0]
            if metadata.required_packages:
                dependencies[format_name] = metadata.required_packages
            else:
                dependencies[format_name] = []  # No dependencies required
        else:
            dependencies[format_name] = []  # No dependencies required

    return dependencies


def check_all_dependencies() -> Dict[str, Dict[str, bool]]:
    """Check installation status of all dependencies.

    Returns
    -------
    dict
        Nested dict of format -> package -> is_installed

    """
    all_deps = get_all_dependencies()
    status = {}

    for format_name, packages in all_deps.items():
        format_status = {}
        for package_name, _import_name, version_spec in packages:
            if version_spec:
                meets, _ = check_version_requirement(package_name, version_spec)
                format_status[package_name] = meets
            else:
                format_status[package_name] = check_package_installed(_import_name)
        status[format_name] = format_status

    return status


def is_valid_format(format_name: str) -> bool:
    """Check if a format name is valid.

    Parameters
    ----------
    format_name : str
        Format name to validate

    Returns
    -------
    bool
        True if format is valid, False otherwise

    """
    registry.auto_discover()
    return format_name in registry.list_formats()


def get_missing_dependencies(format_name: str) -> List[Tuple[str, str]]:
    """Get list of missing dependencies for a specific format.

    Parameters
    ----------
    format_name : str
        Format to check dependencies for

    Returns
    -------
    list
        List of (package_name, version_spec) tuples for missing packages

    """
    # Get metadata for the specific format
    metadata_list = registry.get_format_info(format_name)
    if not metadata_list or len(metadata_list) == 0:
        return []

    # Use the highest priority (first) converter
    metadata = metadata_list[0]
    if not metadata.required_packages:
        return []

    missing = []
    for package_name, _import_name, version_spec in metadata.required_packages:
        if version_spec:
            meets, _ = check_version_requirement(package_name, version_spec)
            if not meets:
                missing.append((package_name, version_spec))
        elif not check_package_installed(_import_name):
            missing.append((package_name, version_spec))

    return missing


def get_missing_dependencies_for_file(format_name: str, input_file: Optional[str] = None) -> List[Tuple[str, str]]:
    """Get list of missing dependencies for a specific format and file.

    This function uses context-aware dependency checking to accurately determine
    which packages are needed for a specific file. This is especially useful for
    formats like spreadsheets where different file types (XLSX vs ODS) require
    different dependencies.

    Parameters
    ----------
    format_name : str
        Format to check dependencies for
    input_file : str, optional
        Path to the input file for context-aware checking

    Returns
    -------
    list
        List of (package_name, version_spec) tuples for missing packages

    """
    # Get metadata for the specific format
    metadata_list = registry.get_format_info(format_name)
    if not metadata_list or len(metadata_list) == 0:
        return []

    # Use the highest priority (first) converter
    metadata = metadata_list[0]

    # Use context-aware dependency checking if file is provided
    if input_file:
        required_packages = metadata.get_required_packages_for_content(content=None, input_data=input_file)
    else:
        required_packages = metadata.required_packages

    if not required_packages:
        return []

    missing = []
    for package_name, _import_name, version_spec in required_packages:
        if version_spec:
            meets, _ = check_version_requirement(package_name, version_spec)
            if not meets:
                missing.append((package_name, version_spec))
        elif not check_package_installed(_import_name):
            missing.append((package_name, version_spec))

    return missing


def generate_install_command(packages: List[Tuple[str, str]]) -> str:
    """Generate pip install command for packages.

    Parameters
    ----------
    packages : list
        List of (package_name, version_spec) tuples

    Returns
    -------
    str
        Pip install command

    """
    if not packages:
        return ""

    package_strs = []
    for package_name, version_spec in packages:
        if version_spec:
            package_strs.append(f'"{package_name}{version_spec}"')
        else:
            package_strs.append(package_name)

    return f"pip install {' '.join(package_strs)}"


def print_dependency_report() -> str:
    """Generate a human-readable dependency report.

    Returns
    -------
    str
        Formatted dependency report

    """
    status = check_all_dependencies()
    lines = ["All2MD Dependency Status", "=" * 40]

    for format_name, packages in sorted(status.items()):
        if not packages:
            lines.append(f"\n{format_name.upper()}: [OK] No dependencies required")
            continue

        all_installed = all(packages.values())
        status_icon = "[OK]" if all_installed else "[MISSING]"
        lines.append(f"\n{format_name.upper()}: {status_icon}")

        for package_name, is_installed in sorted(packages.items()):
            icon = "[OK]" if is_installed else "[MISSING]"
            lines.append(f"  {icon} {package_name}")

        if not all_installed:
            missing = get_missing_dependencies(format_name)
            if missing:
                cmd = generate_install_command(missing)
                lines.append(f"  Install with: {cmd}")

    return "\n".join(lines)


def suggest_minimal_install() -> str:
    """Suggest minimal pip install for common formats.

    Returns
    -------
    str
        Pip install command for common formats

    """
    # Common formats that most users need
    common_formats = ["pdf", "docx", "html"]
    common_packages = set()

    for format_name in common_formats:
        metadata_list = registry.get_format_info(format_name)
        if metadata_list and len(metadata_list) > 0:
            # Use the highest priority (first) converter
            metadata = metadata_list[0]
            if metadata.required_packages:
                for install_name, _import_name, version_spec in metadata.required_packages:
                    common_packages.add((install_name, version_spec))

    return generate_install_command(sorted(common_packages))


def suggest_full_install() -> str:
    """Suggest pip install for all supported formats.

    Returns
    -------
    str
        Pip install command for all formats

    """
    all_deps = get_all_dependencies()
    all_packages = set()

    for packages in all_deps.values():
        for install_name, _import_name, version_spec in packages:
            all_packages.add((install_name, version_spec))

    return generate_install_command(sorted(all_packages))


def format_json_all_formats() -> Dict[str, Any]:
    """Generate JSON output for all format dependencies.

    Returns
    -------
    dict
        JSON-serializable dict with dependency information for all formats

    """
    all_deps = get_all_dependencies()

    formats_data = {}
    total_formats = 0
    formats_ok = 0
    formats_missing = 0

    for format_name, packages in sorted(all_deps.items()):
        total_formats += 1
        format_packages = []
        format_status = "ok"

        for package_name, import_name, version_spec in packages:
            installed_version = get_package_version(package_name)

            if version_spec:
                meets, installed_version = check_version_requirement(package_name, version_spec)
                pkg_status = "ok" if meets else "missing"
            else:
                is_installed = check_package_installed(import_name)
                pkg_status = "ok" if is_installed else "missing"

            if pkg_status == "missing":
                format_status = "missing"

            format_packages.append(
                {
                    "name": package_name,
                    "import_name": import_name,
                    "version_spec": version_spec if version_spec else None,
                    "installed_version": installed_version,
                    "status": pkg_status,
                }
            )

        if format_status == "ok":
            formats_ok += 1
        else:
            formats_missing += 1

        formats_data[format_name] = {"status": format_status, "packages": format_packages}

    overall_status = "ok" if formats_missing == 0 else "missing"

    return {
        "status": overall_status,
        "formats": formats_data,
        "summary": {"total_formats": total_formats, "formats_ok": formats_ok, "formats_missing": formats_missing},
    }


def format_json_specific_format(format_name: str) -> Dict[str, Any]:
    """Generate JSON output for a specific format's dependencies.

    Parameters
    ----------
    format_name : str
        Format to check dependencies for

    Returns
    -------
    dict
        JSON-serializable dict with dependency information for the format

    """
    metadata_list = registry.get_format_info(format_name)
    if not metadata_list or len(metadata_list) == 0:
        return {"status": "ok", "format": format_name, "packages": [], "missing_packages": [], "install_command": ""}

    metadata = metadata_list[0]
    if not metadata.required_packages:
        return {"status": "ok", "format": format_name, "packages": [], "missing_packages": [], "install_command": ""}

    packages_data = []
    missing_packages = []

    for package_name, import_name, version_spec in metadata.required_packages:
        installed_version = get_package_version(package_name)

        if version_spec:
            meets, installed_version = check_version_requirement(package_name, version_spec)
            pkg_status = "ok" if meets else "missing"
            if not meets:
                version_str = f"{package_name}{version_spec}"
                missing_packages.append(version_str)
        else:
            is_installed = check_package_installed(import_name)
            pkg_status = "ok" if is_installed else "missing"
            if not is_installed:
                missing_packages.append(package_name)

        packages_data.append(
            {
                "name": package_name,
                "import_name": import_name,
                "version_spec": version_spec if version_spec else None,
                "installed_version": installed_version,
                "status": pkg_status,
            }
        )

    overall_status = "ok" if len(missing_packages) == 0 else "missing"
    install_command = ""

    if missing_packages:
        missing_tuples = get_missing_dependencies(format_name)
        install_command = generate_install_command(missing_tuples)

    return {
        "status": overall_status,
        "format": format_name,
        "packages": packages_data,
        "missing_packages": missing_packages,
        "install_command": install_command,
    }


def print_dependency_report_rich() -> None:
    """Generate a rich formatted dependency report using tables.

    Notes
    -----
    This function displays dependencies in a formatted table with color coding.

    """
    from rich.console import Console
    from rich.table import Table

    console = Console()
    status = check_all_dependencies()

    # Create main table
    table = Table(title="All2MD Dependency Status")
    table.add_column("Format", style="cyan", no_wrap=True)
    table.add_column("Package", style="yellow")
    table.add_column("Status", style="white")
    table.add_column("Install Command", style="magenta")

    for format_name, packages in sorted(status.items()):
        if not packages:
            table.add_row(format_name.upper(), "-", "[green]OK[/green] (No dependencies)", "-")
        else:
            all_installed = all(packages.values())
            for idx, (package_name, is_installed) in enumerate(sorted(packages.items())):
                format_col = format_name.upper() if idx == 0 else ""
                status_text = "[green]OK[/green]" if is_installed else "[red]MISSING[/red]"

                # Get install command for missing packages
                install_cmd = ""
                if not all_installed and idx == 0:
                    missing = get_missing_dependencies(format_name)
                    if missing:
                        install_cmd = generate_install_command(missing)

                table.add_row(format_col, package_name, status_text, install_cmd if idx == 0 else "")

    console.print(table)


def print_dependency_report_rich_specific(format_name: str) -> None:
    """Generate a rich formatted dependency report for a specific format.

    Parameters
    ----------
    format_name : str
        Format to check dependencies for

    """
    from rich.console import Console
    from rich.table import Table

    console = Console()
    metadata_list = registry.get_format_info(format_name)

    if not metadata_list or len(metadata_list) == 0:
        console.print(f"[green]All dependencies for {format_name} are installed.[/green]")
        return

    metadata = metadata_list[0]
    if not metadata.required_packages:
        console.print(f"[green]All dependencies for {format_name} are installed.[/green]")
        return

    # Create table
    table = Table(title=f"Dependencies for {format_name.upper()}")
    table.add_column("Package", style="cyan")
    table.add_column("Version Requirement", style="yellow")
    table.add_column("Installed Version", style="magenta")
    table.add_column("Status", style="white")

    missing = get_missing_dependencies(format_name)
    has_missing = len(missing) > 0

    for package_name, import_name, version_spec in metadata.required_packages:
        installed_version = get_package_version(package_name)

        if version_spec:
            meets, installed_version = check_version_requirement(package_name, version_spec)
            status_text = "[green]OK[/green]" if meets else "[red]MISSING[/red]"
        else:
            is_installed = check_package_installed(import_name)
            status_text = "[green]OK[/green]" if is_installed else "[red]MISSING[/red]"

        table.add_row(
            package_name,
            version_spec if version_spec else "-",
            installed_version if installed_version else "-",
            status_text,
        )

    console.print(table)

    # Show install command if there are missing dependencies
    if has_missing:
        cmd = generate_install_command(missing)
        console.print(f"\n[yellow]Install with:[/yellow] {cmd}")


def main(argv: Optional[List[str]] = None) -> int:
    """Execute dependency management CLI.

    Parameters
    ----------
    argv : List[str], optional
        Command line arguments

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure)

    """
    parser = argparse.ArgumentParser(prog="all2md-deps", description="Check and manage all2md dependencies")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # check command
    check_parser = subparsers.add_parser("check", help="Check dependency status")
    check_parser.add_argument("--format", help="Check dependencies for specific format only")

    # Create mutually exclusive group for output modes
    output_group = check_parser.add_mutually_exclusive_group()
    output_group.add_argument("--json", action="store_true", help="Output results as JSON")
    output_group.add_argument("--rich", action="store_true", help="Use rich table formatting")

    args = parser.parse_args(argv)

    if args.command == "check":
        if args.format:
            # Validate format exists
            if not is_valid_format(args.format):
                if args.json:
                    # Output error as JSON
                    error_result = {
                        "status": "error",
                        "error": f"Unknown format: {args.format}",
                        "available_formats": sorted(registry.list_formats()),
                    }
                    print(json.dumps(error_result, indent=2))
                else:
                    # Human-readable error
                    print(f"Error: Unknown format '{args.format}'", file=sys.stderr)
                    print(f"\nAvailable formats: {', '.join(sorted(registry.list_formats()))}", file=sys.stderr)
                return 1

            # Check specific format
            if args.json:
                # Output JSON for specific format
                result = format_json_specific_format(args.format)
                print(json.dumps(result, indent=2))
                return 1 if result["status"] == "missing" else 0
            elif should_use_rich_output(args):
                # Rich formatted output
                print_dependency_report_rich_specific(args.format)
                missing = get_missing_dependencies(args.format)
                return 1 if missing else 0
            else:
                # Human-readable output
                missing = get_missing_dependencies(args.format)
                if missing:
                    print(f"Missing dependencies for {args.format}:")
                    for package, version in missing:
                        version_str = version if version else ""
                        print(f"  - {package}{version_str}")
                    cmd = generate_install_command(missing)
                    print(f"\nInstall with: {cmd}")
                    return 1
                else:
                    print(f"All dependencies for {args.format} are installed.")
                    return 0
        else:
            # Check all dependencies
            if args.json:
                # Output JSON for all formats
                result = format_json_all_formats()
                print(json.dumps(result, indent=2))
                return 1 if result["status"] == "missing" else 0
            elif should_use_rich_output(args):
                # Rich formatted output
                print_dependency_report_rich()
                status = check_all_dependencies()
                # Return 1 if any format has missing dependencies
                for format_status in status.values():
                    if format_status and not all(format_status.values()):
                        return 1
                return 0
            else:
                # Human-readable output
                print(print_dependency_report())
                status = check_all_dependencies()
                # Return 1 if any format has missing dependencies
                for format_status in status.values():
                    if format_status and not all(format_status.values()):
                        return 1
                return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    exit(main())
