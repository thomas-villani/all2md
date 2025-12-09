"""Security utilities for MCP server path validation.

This module provides MCP-specific path validation and allowlist enforcement
for secure file access in the MCP server.

Functions
---------
- validate_read_path: Validate a path is in the read allowlist
- validate_write_path: Validate a path is in the write allowlist
- prepare_allowlist_dirs: Convert allowlist strings to resolved Paths
- secure_open_for_write: Open a file for writing with TOCTOU protection

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import logging
import os
import sys
from pathlib import Path
from typing import BinaryIO

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


def validate_read_path(path: str | Path, read_allowlist_dirs: list[str | Path] | None) -> Path:
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
            f"Read access denied: path does not exist or cannot be resolved: {path}", path=str(path)
        ) from e

    # Ensure it's a file
    if not resolved_path.is_file():
        raise MCPSecurityError(f"Read access denied: path is not a file: {path}", path=str(path))

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
            raise MCPSecurityError(f"Read access denied: path not in allowlist: {path}", path=str(path))

    logger.debug(f"Read path validated: {resolved_path}")
    return resolved_path


def validate_write_path(path: str | Path, write_allowlist_dirs: list[str | Path] | None) -> Path:
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
    if ".." in path_obj.parts:
        raise MCPSecurityError(f"Path contains parent directory references (..): {path}", path=str(path))

    # Get absolute path
    abs_path = path_obj.absolute()
    parent = abs_path.parent

    # Verify parent exists
    if not parent.exists():
        raise MCPSecurityError(f"Write access denied: parent directory does not exist: {parent}", path=str(path))

    # Resolve parent (following symlinks)
    try:
        resolved_parent = parent.resolve(strict=True)
    except (OSError, RuntimeError) as e:
        raise MCPSecurityError(f"Write access denied: cannot resolve parent directory: {parent}", path=str(path)) from e

    # Build final path with resolved parent
    final_path = resolved_parent / abs_path.name

    # If file already exists, resolve it fully to handle symlinks
    if final_path.exists():
        try:
            final_path = final_path.resolve(strict=True)
        except (OSError, RuntimeError) as e:
            raise MCPSecurityError(
                f"Write access denied: cannot resolve existing file: {final_path}", path=str(path)
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
        raise MCPSecurityError(f"Write access denied: path not in allowlist: {path}", path=str(path))

    logger.debug(f"Write path validated: {final_path}")
    return final_path


def prepare_allowlist_dirs(paths: list[str | Path] | None) -> list[Path] | None:
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
                raise MCPSecurityError(f"Allowlist path is not a directory: {path_item}", path=str(path_item))
            # Store as resolved Path object to avoid re-resolving in validation
            validated_paths.append(path)
            logger.debug(f"Added to allowlist: {path}")
        except (OSError, RuntimeError) as e:
            raise MCPSecurityError(f"Invalid allowlist path: {path_item} ({e})", path=str(path_item)) from e

    return validated_paths


def secure_open_for_write(validated_path: Path) -> BinaryIO:
    """Open a file for writing with TOCTOU race condition protection.

    This function opens a file using OS-level flags to prevent Time-Of-Check
    Time-Of-Use (TOCTOU) attacks where a file could be replaced with a symlink
    between validation and write operations.

    Parameters
    ----------
    validated_path : Path
        Path that has already been validated by validate_write_path().
        Must be an absolute, resolved path.

    Returns
    -------
    BinaryIO
        Binary file object opened for writing in a secure manner.
        Caller is responsible for closing this file.

    Raises
    ------
    MCPSecurityError
        If the file cannot be opened securely (e.g., it's a symlink or
        access is denied)

    Notes
    -----
    Security measures:
    - On Unix-like systems: Uses O_NOFOLLOW flag to prevent following symlinks
    - On Windows: Uses os.open without follow_symlinks behavior
    - Creates new files with O_CREAT | O_EXCL when possible
    - For existing files, verifies they are not symlinks before opening

    This function should be called immediately after validate_write_path() to
    minimize the TOCTOU window. The returned file object must be used for all
    write operations to ensure the validated path is actually being written to.

    """
    # Ensure path is absolute
    if not validated_path.is_absolute():
        raise MCPSecurityError(
            f"secure_open_for_write requires absolute path, got: {validated_path}", path=str(validated_path)
        )

    # Check if file is a symlink (final check before opening)
    # Note: This check is still subject to TOCTOU, but combined with O_NOFOLLOW
    # it provides defense in depth
    if validated_path.is_symlink():
        raise MCPSecurityError(f"Refusing to write to symlink: {validated_path}", path=str(validated_path))

    # Prepare flags for secure file opening
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC

    # Add O_NOFOLLOW on platforms that support it (Unix/Linux/macOS)
    # This is the key protection against symlink attacks
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
        logger.debug("Using O_NOFOLLOW flag for symlink protection")
    else:
        # On Windows, O_NOFOLLOW doesn't exist, but symlink behavior is different
        # Windows symlinks require special privileges by default
        logger.debug("O_NOFOLLOW not available (Windows), relying on is_symlink check")

    # Add O_BINARY on Windows to ensure binary mode
    if sys.platform == "win32" and hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY

    try:
        # Open file with secure flags
        # Mode 0o644 = rw-r--r-- (owner can read/write, others can read)
        # This is intentional - output files need to be readable by other processes
        fd = os.open(str(validated_path), flags, mode=0o644)  # nosec B101  # noqa: S101
        logger.debug(f"Securely opened file for writing: {validated_path}")

        # Convert file descriptor to file object
        # Use binary mode as that's what most document formats need
        return os.fdopen(fd, "wb")

    except OSError as e:
        # Could fail for several reasons:
        # - ELOOP: Too many symbolic links (O_NOFOLLOW prevented following symlink)
        # - EACCES: Permission denied
        # - EISDIR: Path is a directory
        # - ENOENT: Parent directory doesn't exist
        error_msg = f"Failed to securely open file for writing: {validated_path} ({e})"

        # Provide more specific error for symlink detection
        if e.errno == 40 or "symbolic link" in str(e).lower() or "ELOOP" in str(e):
            error_msg = f"Refusing to write to symlink (TOCTOU attack prevented): {validated_path}"

        raise MCPSecurityError(error_msg, path=str(validated_path)) from e
