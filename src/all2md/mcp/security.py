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
        read_allowlist_dirs: list[str | Path] | None
) -> Path:
    """Validate a path is allowed for reading.

    Parameters
    ----------
    path : str | Path
        Path to validate
    read_allowlist_dirs : list[str | Path] | None
        List of allowed read directory paths (strings or resolved Path objects), or None to allow all

    Returns
    -------
    Path
        Validated, resolved path

    Raises
    ------
    MCPSecurityError
        If path is not in read allowlist or validation fails

    Notes
    -----
    The allowlist comparison uses resolved canonical paths, which are case-normalized
    on Windows. This prevents bypass via case variations on case-insensitive filesystems.

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
        for allowed_dir_item in read_allowlist_dirs:
            try:
                # Convert to Path if needed (should already be Path if from prepare_allowlist_dirs)
                allowed_dir = Path(allowed_dir_item) if isinstance(allowed_dir_item, str) else allowed_dir_item
                # Resolve if not already resolved (e.g., if passing string directly)
                if isinstance(allowed_dir_item, str):
                    allowed_dir = allowed_dir.resolve(strict=True)
                resolved_path.relative_to(allowed_dir)
                in_allowlist = True
                break
            except ValueError:
                # Path is not relative to this allowlist directory
                continue
            except (OSError, RuntimeError):
                # Error resolving allowlist path (should not happen if from prepare_allowlist_dirs)
                logger.warning(f"Invalid allowlist directory: {allowed_dir_item}")
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
        write_allowlist_dirs: list[str | Path] | None
) -> Path:
    """Validate a path is allowed for writing.

    Uses security checks consistent with validate_local_file_access to ensure
    proper path validation and symlink resolution in all cases.

    Parameters
    ----------
    path : str | Path
        Path to validate
    write_allowlist_dirs : list[str | Path] | None
        List of allowed write directory paths (strings or resolved Path objects), or None to allow all

    Returns
    -------
    Path
        Validated, resolved path

    Raises
    ------
    MCPSecurityError
        If path is not in write allowlist or validation fails

    Notes
    -----
    The allowlist comparison uses resolved canonical paths, which are case-normalized
    on Windows. This prevents bypass via case variations on case-insensitive filesystems.

    """
    path_obj = Path(path)

    # Check for path traversal (always, regardless of allowlist)
    if '..' in path_obj.parts:
        raise MCPSecurityError(
            f"Path contains parent directory references (..): {path}",
            path=str(path)
        )

    # Get absolute path
    abs_path = path_obj.absolute()
    parent = abs_path.parent

    # Verify parent exists
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

    # Build final path with resolved parent
    final_path = resolved_parent / abs_path.name

    # If file already exists, resolve it fully to handle symlinks
    if final_path.exists():
        try:
            final_path = final_path.resolve(strict=True)
        except (OSError, RuntimeError) as e:
            raise MCPSecurityError(
                f"Write access denied: cannot resolve existing file: {final_path}",
                path=str(path)
            ) from e

    # If no allowlist, allow write after security checks
    if write_allowlist_dirs is None:
        logger.debug(f"Write path validated (no allowlist): {final_path}")
        return final_path

    # Check if final path is within any allowed directory
    # Use the parent of the final resolved path for checking
    check_path = final_path.parent

    in_allowlist = False
    for allowed_dir_item in write_allowlist_dirs:
        try:
            # Convert to Path if needed (should already be Path if from prepare_allowlist_dirs)
            allowed_dir = Path(allowed_dir_item) if isinstance(allowed_dir_item, str) else allowed_dir_item
            # Resolve if not already resolved (e.g., if passing string directly)
            if isinstance(allowed_dir_item, str):
                allowed_dir = allowed_dir.resolve(strict=True)
            check_path.relative_to(allowed_dir)
            in_allowlist = True
            break
        except ValueError:
            # Path is not relative to this allowlist directory
            continue
        except (OSError, RuntimeError):
            # Error resolving allowlist path (should not happen if from prepare_allowlist_dirs)
            logger.warning(f"Invalid allowlist directory: {allowed_dir_item}")
            continue

    if not in_allowlist:
        raise MCPSecurityError(
            f"Write access denied: path not in allowlist: {path}",
            path=str(path)
        )

    logger.debug(f"Write path validated: {final_path}")
    return final_path


def prepare_allowlist_dirs(
        paths: list[str | Path] | None
) -> list[Path] | None:
    """Validate allowlist directory paths.

    Ensures all paths exist and are directories. Resolves paths to canonical
    form, which normalizes case on Windows and follows symlinks.

    Parameters
    ----------
    paths : list[str | Path] | None
        List of directory paths (as strings or Path objects), or None for no restrictions

    Returns
    -------
    list[Path] | None
        Validated list of resolved Path objects, or None

    Raises
    ------
    MCPSecurityError
        If any path is invalid or doesn't exist

    Notes
    -----
    Paths are resolved to canonical form using Path.resolve(strict=True),
    which normalizes case on Windows filesystems. This ensures that case
    variations cannot bypass security checks on case-insensitive systems.

    """
    if paths is None:
        return None

    validated_paths = []
    for path_item in paths:
        try:
            # Convert to Path if string, or use as-is if already Path
            path = Path(path_item).resolve(strict=True)
            if not path.is_dir():
                raise MCPSecurityError(
                    f"Allowlist path is not a directory: {path_item}",
                    path=str(path_item)
                )
            # Store as resolved Path object to avoid re-resolving in validation
            validated_paths.append(path)
            logger.debug(f"Added to allowlist: {path}")
        except (OSError, RuntimeError) as e:
            raise MCPSecurityError(
                f"Invalid allowlist path: {path_item} ({e})",
                path=str(path_item)
            ) from e

    return validated_paths
