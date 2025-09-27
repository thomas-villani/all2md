"""Dependency management utilities for all2md.

This module provides utilities for checking, installing, and managing
optional dependencies for various converter modules.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

from all2md.converter_registry import registry


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
    # Mapping from package names to their actual import names
    # Many packages have different install names vs import names
    package_import_map = {
        'python-docx': 'docx',
        'beautifulsoup4': 'bs4',
        'python-pptx': 'pptx',
        'odfpy': 'odf',
        'pillow': 'PIL',
        'pyyaml': 'yaml',
        # Add more mappings as needed
    }

    # Determine the correct import name
    import_names_to_try = []

    # First try the mapped name if it exists
    if package_name.lower() in package_import_map:
        import_names_to_try.append(package_import_map[package_name.lower()])

    # Then try replacing hyphens with underscores
    if '-' in package_name:
        import_names_to_try.append(package_name.replace("-", "_"))

    # Finally try the original package name
    import_names_to_try.append(package_name)

    # Try each possible import name
    for import_name in import_names_to_try:
        try:
            importlib.import_module(import_name)
            return True
        except ImportError:
            continue

    return False


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


def get_all_dependencies() -> Dict[str, List[Tuple[str, str]]]:
    """Get all dependencies for all converters from the registry.

    Returns
    -------
    dict
        Mapping of format names to required packages
    """
    dependencies = {}
    for format_name in registry.list_formats():
        metadata = registry.get_format_info(format_name)
        if metadata and metadata.required_packages:
            dependencies[format_name] = metadata.required_packages
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
        for package_name, version_spec in packages:
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
    metadata = registry.get_format_info(format_name)
    if not metadata or not metadata.required_packages:
        return []

    missing = []
    for package_name, version_spec in metadata.required_packages:
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


def install_dependencies(
        packages: List[Tuple[str, str]],
        upgrade: bool = False
) -> Tuple[bool, str]:
    """Attempt to install missing dependencies.

    Parameters
    ----------
    packages : list
        List of (package_name, version_spec) tuples
    upgrade : bool
        Whether to upgrade existing packages

    Returns
    -------
    tuple
        (success, output_message)
    """
    if not packages:
        return True, "No packages to install"

    cmd = [sys.executable, "-m", "pip", "install"]
    if upgrade:
        cmd.append("--upgrade")

    for package_name, version_spec in packages:
        if version_spec:
            cmd.append(f"{package_name}{version_spec}")
        else:
            cmd.append(package_name)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, f"Installation failed: {e.stderr}"
    except Exception as e:
        return False, f"Installation failed: {str(e)}"


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
        metadata = registry.get_format_info(format_name)
        if metadata and metadata.required_packages:
            for package in metadata.required_packages:
                common_packages.add(package)

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
        for package in packages:
            all_packages.add(package)

    return generate_install_command(sorted(all_packages))


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for dependency management CLI.

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

    # install command
    install_parser = subparsers.add_parser('install', help='Install missing dependencies')
    install_parser.add_argument(
        'format',
        nargs='?',
        help='Install dependencies for specific format (or all if not specified)'
    )
    install_parser.add_argument(
        '--upgrade',
        action='store_true',
        help='Upgrade existing packages'
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

    elif args.command == 'install':
        if args.format:
            # Install for specific format
            missing = get_missing_dependencies(args.format)
            if not missing:
                print(f"All dependencies for {args.format} are already installed.")
                return 0

            print(f"Installing dependencies for {args.format}...")
            success, message = install_dependencies(missing, args.upgrade)
            print(message)
            return 0 if success else 1
        else:
            # Install all missing dependencies
            all_deps = get_all_dependencies()
            all_missing = set()

            for format_name in all_deps:
                missing = get_missing_dependencies(format_name)
                for package_tuple in missing:
                    all_missing.add(package_tuple)

            if not all_missing:
                print("All dependencies are already installed.")
                return 0

            all_missing_list = sorted(all_missing)
            print(f"Installing {len(all_missing_list)} missing packages...")
            success, message = install_dependencies(all_missing_list, args.upgrade)
            print(message)
            return 0 if success else 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    exit(main())
