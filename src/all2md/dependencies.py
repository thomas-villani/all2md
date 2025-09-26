"""Dependency management utilities for all2md.

This module provides utilities for checking, installing, and managing
optional dependencies for various converter modules.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from typing import Dict, List, Optional, Tuple


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
    try:
        # Handle package names with hyphens (e.g., python-docx)
        import_name = package_name.replace("-", "_")
        importlib.import_module(import_name)
        return True
    except ImportError:
        # Try the original name as well
        try:
            importlib.import_module(package_name)
            return True
        except ImportError:
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
    try:
        import pkg_resources
        return pkg_resources.get_distribution(package_name).version
    except Exception:
        try:
            # Fallback to importlib.metadata for Python 3.8+
            from importlib import metadata
            return metadata.version(package_name)
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
    """Get all dependencies for all converters.

    Returns
    -------
    dict
        Mapping of format names to required packages
    """
    dependencies = {
        "pdf": [("pymupdf", ">=1.24.0")],
        "docx": [("python-docx", "")],
        "pptx": [("python-pptx", "")],
        "html": [("beautifulsoup4", "")],
        "mhtml": [("beautifulsoup4", "")],
        "epub": [("ebooklib", ""), ("beautifulsoup4", "")],
        "odf": [("odfpy", "")],
        "rtf": [("pyth", "")],
        "eml": [],  # Uses standard library
        "ipynb": [],  # Uses standard library json
        "xlsx": [("pandas", ""), ("openpyxl", "")],
        "csv": [("pandas", "")],  # Optional, falls back to basic parsing
        "tsv": [("pandas", "")],  # Optional, falls back to basic parsing
    }
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
    all_deps = get_all_dependencies()
    if format_name not in all_deps:
        return []

    missing = []
    for package_name, version_spec in all_deps[format_name]:
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
            lines.append(f"\n{format_name.upper()}: ✓ No dependencies required")
            continue

        all_installed = all(packages.values())
        status_icon = "✓" if all_installed else "✗"
        lines.append(f"\n{format_name.upper()}: {status_icon}")

        for package_name, is_installed in sorted(packages.items()):
            icon = "✓" if is_installed else "✗"
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
    common_packages = [
        ("pymupdf", ">=1.24.0"),
        ("python-docx", ""),
        ("beautifulsoup4", ""),
    ]

    return generate_install_command(common_packages)


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
