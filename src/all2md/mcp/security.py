"""Security utilities for MCP server path validation.

This module provides MCP-specific path validation and allowlist enforcement
for secure file access in the MCP server.

Functions
---------
- validate_read_path: Validate a path is in the read allowlist
- validate_write_path: Validate a path is in the write allowlist
- prepare_allowlist_dirs: Convert allowlist strings to resolved Paths

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import logging
from pathlib import Path

from all2md.exceptions import All2MdError

logger = logging.getLogger(__name__)


class MCPSecurityError(All2MdError):
    """Raised when MCP security validation fails."""

    def __init__(self, message: str, path: str | None = None) -> None:
        """Initialize MCP security error.

        Parameters
        ----------
        message : str
            Error message
        path : str | None
            Path that failed validation

        """
        super().__init__(message)
        self.path = path


def validate_read_path(
    path: str | Path,
    read_allowlist_dirs: list[str] | None
) -> Path:
    """Validate a path is allowed for reading.

    Parameters
    ----------
    path : str | Path
        Path to validate
    read_allowlist_dirs : list[str] | None
        List of allowed read directory paths (strings), or None to allow all

    Returns
    -------
    Path
        Validated, resolved path

    Raises
    ------
    MCPSecurityError
        If path is not in read allowlist or validation fails

    """
    path_obj = Path(path)

    # Resolve and verify path exists
    try:
        resolved_path = path_obj.resolve(strict=True)
    except (OSError, RuntimeError) as e:
        raise MCPSecurityError(
            f"Read access denied: path does not exist or cannot be resolved: {path}",
            path=str(path)
        ) from e

    # Ensure it's a file
    if not resolved_path.is_file():
        raise MCPSecurityError(
            f"Read access denied: path is not a file: {path}",
            path=str(path)
        )

    # Check if path is in allowlist (if allowlist is provided)
    if read_allowlist_dirs is not None:
        in_allowlist = False
        for allowed_dir_str in read_allowlist_dirs:
            try:
                allowed_dir = Path(allowed_dir_str).resolve(strict=True)
                resolved_path.relative_to(allowed_dir)
                in_allowlist = True
                break
            except ValueError:
                continue
            except (OSError, RuntimeError):
                logger.warning(f"Invalid allowlist directory: {allowed_dir_str}")
                continue

        if not in_allowlist:
            raise MCPSecurityError(
                f"Read access denied: path not in allowlist: {path}",
                path=str(path)
            )

    logger.debug(f"Read path validated: {resolved_path}")
    return resolved_path


def validate_write_path(
    path: str | Path,
    write_allowlist_dirs: list[str] | None
) -> Path:
    """Validate a path is allowed for writing.

    Parameters
    ----------
    path : str | Path
        Path to validate
    write_allowlist_dirs : list[str] | None
        List of allowed write directory paths (strings), or None to allow all

    Returns
    -------
    Path
        Validated, resolved path

    Raises
    ------
    MCPSecurityError
        If path is not in write allowlist or validation fails

    """
    if write_allowlist_dirs is None:
        # No restrictions
        path_obj = Path(path)
        try:
            return path_obj.absolute()
        except (OSError, RuntimeError) as e:
            raise MCPSecurityError(
                f"Invalid write path: {path}",
                path=str(path)
            ) from e

    # For write paths, parent directory must exist and be in allowlist
    path_obj = Path(path)

    # Check for path traversal
    if '..' in path_obj.parts:
        raise MCPSecurityError(
            f"Path contains parent directory references (..): {path}",
            path=str(path)
        )

    # Get absolute path
    abs_path = path_obj.absolute()
    parent = abs_path.parent

    # Verify parent exists and is in allowlist
    if not parent.exists():
        raise MCPSecurityError(
            f"Write access denied: parent directory does not exist: {parent}",
            path=str(path)
        )

    # Resolve parent (following symlinks)
    try:
        resolved_parent = parent.resolve(strict=True)
    except (OSError, RuntimeError) as e:
        raise MCPSecurityError(
            f"Write access denied: cannot resolve parent directory: {parent}",
            path=str(path)
        ) from e

    # Check if resolved parent is within any allowed directory
    in_allowlist = False
    for allowed_dir_str in write_allowlist_dirs:
        try:
            allowed_dir = Path(allowed_dir_str).resolve(strict=True)
            resolved_parent.relative_to(allowed_dir)
            in_allowlist = True
            break
        except ValueError:
            continue
        except (OSError, RuntimeError):
            logger.warning(f"Invalid allowlist directory: {allowed_dir_str}")
            continue

    if not in_allowlist:
        raise MCPSecurityError(
            f"Write access denied: path not in allowlist: {path}",
            path=str(path)
        )

    # Return full resolved path
    resolved_path = resolved_parent / abs_path.name
    logger.debug(f"Write path validated: {resolved_path}")
    return resolved_path


def prepare_allowlist_dirs(
    paths: list[str] | None
) -> list[str] | None:
    """Validate allowlist directory paths.

    Ensures all paths exist and are directories.

    Parameters
    ----------
    paths : list[str] | None
        List of directory paths, or None for no restrictions

    Returns
    -------
    list[str] | None
        Validated list of directory paths (as strings), or None

    Raises
    ------
    MCPSecurityError
        If any path is invalid or doesn't exist

    """
    if paths is None:
        return None

    validated_paths = []
    for path_str in paths:
        try:
            path = Path(path_str).resolve(strict=True)
            if not path.is_dir():
                raise MCPSecurityError(
                    f"Allowlist path is not a directory: {path_str}",
                    path=path_str
                )
            # Store as string for compatibility with validate_local_file_access
            validated_paths.append(str(path))
            logger.debug(f"Added to allowlist: {path}")
        except (OSError, RuntimeError) as e:
            raise MCPSecurityError(
                f"Invalid allowlist path: {path_str} ({e})",
                path=path_str
            ) from e

    return validated_paths
