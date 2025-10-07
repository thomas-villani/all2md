"""Security utilities for all2md conversion modules.

This module provides security validation functions to prevent unauthorized
access to local files and malicious ZIP archive processing.

Functions
---------
- validate_local_file_access: Check if access to a local file path is allowed
- validate_zip_archive: Pre-validate ZIP archives for security threats
- sanitize_language_identifier: Sanitize code fence language identifiers
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the "Software"), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import logging
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Union
from urllib.parse import urlparse

from all2md.constants import (
    DEFAULT_MAX_COMPRESSION_RATIO,
    DEFAULT_MAX_UNCOMPRESSED_SIZE,
    DEFAULT_MAX_ZIP_ENTRIES,
    MAX_LANGUAGE_IDENTIFIER_LENGTH,
    SAFE_LANGUAGE_IDENTIFIER_PATTERN,
)
from all2md.exceptions import MalformedFileError, ZipFileSecurityError

logger = logging.getLogger(__name__)


def validate_local_file_access(
        file_url: str,
        allow_local_files: bool = False,
        local_file_allowlist: list[str] | None = None,
        local_file_denylist: list[str] | None = None,
        allow_cwd_files: bool = True
) -> bool:
    """Validate if access to a local file URL is allowed based on security settings.

    Parameters
    ----------
    file_url : str
        The file:// URL to validate
    allow_local_files : bool, default False
        Master switch for local file access. If False, no local files are allowed.
    local_file_allowlist : list[str] | None, default None
        List of directories allowed for local file access (when allow_local_files=True)
    local_file_denylist : list[str] | None, default None
        List of directories denied for local file access
    allow_cwd_files : bool, default True
        Allow local files from current working directory and subdirectories.
        Only applies when allow_local_files=True.

    Returns
    -------
    bool
        True if access is allowed, False otherwise

    Examples
    --------
    >>> validate_local_file_access("file:///etc/passwd", allow_local_files=False)
    False
    >>> validate_local_file_access("file://./image.png", allow_local_files=False)
    False
    >>> validate_local_file_access("file://./image.png", allow_local_files=True, allow_cwd_files=True)
    True

    """
    if not file_url.startswith("file://"):
        return True  # Not a local file URL, validation doesn't apply

    # Parse the file URL to get the path
    # Handle the special case where urlparse normalizes relative paths
    if file_url.startswith("file://./") or file_url.startswith("file://../"):
        # Extract the path directly from the URL to preserve relative context
        path = file_url[7:]  # Remove "file://" prefix
        file_path = Path.cwd() / path
    elif file_url.startswith("file://") and not file_url.startswith("file:///"):
        # file://filename (without leading slash) - treat as relative to CWD
        path = file_url[7:]  # Remove "file://" prefix
        file_path = Path.cwd() / path
    else:
        # Standard absolute file:///path handling
        parsed = urlparse(file_url)
        file_path = Path(parsed.path)

    file_path = file_path.resolve()
    cwd = Path.cwd().resolve()

    # Check denylist first (highest priority)
    if local_file_denylist:
        for denied_dir in local_file_denylist:
            denied_path = Path(denied_dir).resolve()
            try:
                file_path.relative_to(denied_path)
                return False  # File is in a denied directory
            except ValueError:
                continue  # File is not under this denied directory

    # Check master switch for local files first
    if not allow_local_files:
        return False

    # Check if CWD files are allowed and file is under CWD
    if allow_cwd_files:
        try:
            file_path.relative_to(cwd)
            return True  # File is under current working directory
        except ValueError:
            pass  # File is not under CWD

    # Check allowlist if provided
    if local_file_allowlist is not None:
        for allowed_dir in local_file_allowlist:
            allowed_path = Path(allowed_dir).resolve()
            try:
                file_path.relative_to(allowed_path)
                return True  # File is in an allowed directory
            except ValueError:
                continue  # File is not under this allowed directory
        return False  # Not in any allowed directory (or empty allowlist)

    # If allow_local_files=True and no allowlist, allow access
    return True


def validate_zip_archive(
        file_path: Union[str, Path],
        max_compression_ratio: float = DEFAULT_MAX_COMPRESSION_RATIO,
        max_uncompressed_size: int = DEFAULT_MAX_UNCOMPRESSED_SIZE,  # 1GB
        max_entries: int = DEFAULT_MAX_ZIP_ENTRIES
) -> None:
    """Validate a ZIP archive for security threats before processing.

    This function performs pre-validation checks on ZIP archives to detect
    potential security threats like zip bombs, path traversal attacks, and
    excessive resource consumption.

    Parameters
    ----------
    file_path : str or Path
        Path to the ZIP archive to validate
    max_compression_ratio : float, default 100.0
        Maximum allowed compression ratio (uncompressed/compressed)
    max_uncompressed_size : int, default 1073741824
        Maximum total uncompressed size in bytes (default: 1GB)
    max_entries : int, default 10000
        Maximum number of entries in the archive

    Raises
    ------
    ZipFileSecurityError
        If the archive fails security validation
    MalformedFileError
        If the archive cannot be read for some other reason

    Examples
    --------
    >>> validate_zip_archive("document.docx")
    # Passes if the file is a safe ZIP archive

    >>> validate_zip_archive("malicious.zip")  # doctest: +SKIP
    ZipFileSecurityError: ZIP archive has suspicious compression ratio: 1000:1

    """
    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            entries = zf.infolist()

            # Check number of entries
            if len(entries) > max_entries:
                raise ZipFileSecurityError(
                    f"ZIP archive contains too many entries: {len(entries)} > {max_entries}"
                )

            total_uncompressed = 0
            total_compressed = 0

            for entry in entries:
                # Check for path traversal attempts
                name = entry.filename
                # Normalize backslashes to handle Windows paths
                name_norm = name.replace('\\', '/')
                p = PurePosixPath(name_norm)
                if any(part == '..' for part in p.parts) or name_norm.startswith('/'):
                    raise ZipFileSecurityError(
                        f"ZIP archive contains suspicious path: {entry.filename}"
                    )

                # Accumulate sizes for compression ratio calculation
                total_uncompressed += entry.file_size
                total_compressed += entry.compress_size

                # Check total uncompressed size
                if total_uncompressed > max_uncompressed_size:
                    raise ZipFileSecurityError(
                        f"ZIP archive uncompressed size too large: "
                        f"{total_uncompressed / (1024 * 1024):.1f}MB > "
                        f"{max_uncompressed_size / (1024 * 1024):.1f}MB"
                    )

            # Check compression ratio
            if total_compressed > 0:
                compression_ratio = total_uncompressed / total_compressed
                if compression_ratio > max_compression_ratio:
                    raise ZipFileSecurityError(
                        f"ZIP archive has suspicious compression ratio: {compression_ratio:.1f}:1"
                    )

    except zipfile.BadZipFile as e:
        raise MalformedFileError(f"Invalid ZIP archive: {e}") from e
    except (OSError, IOError) as e:
        raise MalformedFileError(f"Could not read ZIP archive: {e}") from e


def sanitize_language_identifier(language: str) -> str:
    """Sanitize code fence language identifier to prevent markdown injection.

    Code fence language identifiers must only contain safe characters to prevent
    markdown injection via malicious language strings. This function validates
    and sanitizes language strings by checking against a safe pattern of
    alphanumeric characters, underscores, hyphens, and plus signs.

    Parameters
    ----------
    language : str
        Raw language identifier string to sanitize

    Returns
    -------
    str
        Sanitized language identifier, or empty string if invalid

    Examples
    --------
    >>> sanitize_language_identifier("python")
    'python'
    >>> sanitize_language_identifier("c++")
    'c++'
    >>> sanitize_language_identifier("python\\nmalicious")
    ''
    >>> sanitize_language_identifier("python javascript")
    ''
    >>> sanitize_language_identifier("x" * 100)
    ''

    Notes
    -----
    This function is used by both HTML and Markdown parsers to ensure
    consistent security validation of code block language identifiers.

    """
    if not language:
        return ""

    # Strip whitespace
    language = language.strip()

    # Check length limit
    if len(language) > MAX_LANGUAGE_IDENTIFIER_LENGTH:
        logger.warning(
            f"Language identifier exceeds maximum length ({MAX_LANGUAGE_IDENTIFIER_LENGTH}): {language[:50]}..."
        )
        return ""

    # Validate against safe pattern
    if not re.match(SAFE_LANGUAGE_IDENTIFIER_PATTERN, language):
        logger.warning(
            f"Blocked potentially dangerous language identifier containing invalid characters: {language[:50]}"
        )
        return ""

    return language
