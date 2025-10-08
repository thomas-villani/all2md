"""Dependency management utilities for all2md.

This module provides utilities for checking and reporting on
optional dependencies for various converter modules.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from all2md.converter_registry import _check_package_installed, registry


def check_package_installed(package_name: str) -> bool:
    """Check if a package is installed and importable.

    Parameters
    ----------
    package_name : str
        Name of the package to check

    Returns
    -------
    bool
        True if package is installed and importable

    """
    return _check_package_installed(package_name)


def get_package_version(package_name: str) -> Optional[str]:
    """Get the installed version of a package.

    Parameters
    ----------
    package_name : str
        Name of the package

    Returns
    -------
    str or None
        Version string if package installed, None otherwise

    """
    # For version checking, we need to use the pip package name, not import name
    # Most tools use the actual package name for version info

    # Prefer importlib.metadata (modern approach, Python 3.8+)
    try:
        from importlib import metadata
        return metadata.version(package_name)
    except Exception:
        # Fallback to pkg_resources for older environments
        # Note: pkg_resources is deprecated but kept for compatibility
        try:
            import pkg_resources
            return pkg_resources.get_distribution(package_name).version
        except Exception:
            return None


def check_version_requirement(
        package_name: str,
        version_spec: str
) -> Tuple[bool, Optional[str]]:
    """Check if installed package meets version requirement.

    Parameters
    ----------
    package_name : str
        Name of the package
    version_spec : str
        Version specification (e.g., ">=1.24.0")

    Returns
    -------
    tuple
        (meets_requirement, installed_version)

    """
    installed_version = get_package_version(package_name)
    if not installed_version:
        return False, None

    try:
        from packaging import version
        from packaging.specifiers import SpecifierSet

        spec = SpecifierSet(version_spec)
        meets = version.parse(installed_version) in spec
        return meets, installed_version
    except ImportError:
        # If packaging not available, just check if installed
        return True, installed_version


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
                format_status[package_name] = check_package_installed(package_name)
        status[format_name] = format_status

    return status


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
        elif not check_package_installed(package_name):
            missing.append((package_name, version_spec))

    return missing


def get_missing_dependencies_for_file(
    format_name: str,
    input_file: Optional[str] = None
) -> List[Tuple[str, str]]:
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
        required_packages = metadata.get_required_packages_for_content(
            content=None,
            input_data=input_file
        )
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
        elif not check_package_installed(package_name):
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
    import argparse

    parser = argparse.ArgumentParser(
        prog="all2md-deps",
        description="Check and manage all2md dependencies"
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # check command
    check_parser = subparsers.add_parser('check', help='Check dependency status')
    check_parser.add_argument(
        '--format',
        help='Check dependencies for specific format only'
    )

    args = parser.parse_args(argv)

    if args.command == 'check':
        if args.format:
            # Check specific format
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
