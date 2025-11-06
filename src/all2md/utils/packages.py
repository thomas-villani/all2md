"""Utility functions to checking installed packages."""

#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/utils/packages.py
from __future__ import annotations

from typing import Optional, Tuple


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
        return None


def check_version_requirement(package_name: str, version_spec: str) -> Tuple[bool, Optional[str]]:
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
