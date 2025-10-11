#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Security utilities for all2md conversion modules.

This module provides security validation functions to prevent unauthorized
access to local files and malicious ZIP archive processing.

Functions
---------
- validate_local_file_access: Check if access to a local file path is allowed
- validate_zip_archive: Pre-validate ZIP archives for security threats
- sanitize_language_identifier: Sanitize code fence language identifiers
"""

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

    Supports various file URL formats including:
    - Unix/Linux: file:///path/to/file
    - Windows drive letters: file:///C:/path/to/file
    - Windows UNC paths: file://server/share/file
    - Relative paths: file://./file or file://../file

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
    >>> validate_local_file_access("file:///C:/Users/file.txt", allow_local_files=True)  # Windows
    True

    """
    if not file_url.startswith("file://"):
        return True  # Not a local file URL, validation doesn't apply

    # Parse the file URL to get the path
    # Handle various file:// URL formats

    # Check for relative paths first
    if file_url.startswith("file://./") or file_url.startswith("file://../"):
        # Extract the path directly from the URL to preserve relative context
        path = file_url[7:]  # Remove "file://" prefix
        file_path = Path.cwd() / path
    # Check for Windows UNC paths: file://server/share/path
    elif file_url.startswith("file://") and not file_url.startswith("file:///"):
        # This could be either:
        # 1. file://server/share (UNC path on Windows)
        # 2. file://filename (relative path)
        # 3. file://C:\... (Windows absolute path with backslashes - malformed but handle it)
        path_part = file_url[7:]  # Remove "file://" prefix

        # Check if it's a Windows absolute path (starts with drive letter)
        # Pattern: C:\ or C:/ or just C:
        if len(path_part) >= 2 and path_part[1] == ':':
            # Windows absolute path: file://C:\path or file://C:/path
            # Normalize backslashes to forward slashes for Path
            normalized_path = path_part.replace('\\', '/')
            file_path = Path(normalized_path)
        # Check if it looks like a UNC path (has at least one slash/backslash after server name)
        elif '/' in path_part or '\\' in path_part:
            # Likely UNC path: file://server/share/file -> \\server\share\file
            file_path = Path(f"\\\\{path_part.replace('/', chr(92))}")
        else:
            # Likely relative path: file://filename
            file_path = Path.cwd() / path_part
    else:
        # Standard absolute file:///path handling
        parsed = urlparse(file_url)
        path_str = parsed.path

        # Handle Windows drive letters: file:///C:/path
        # urlparse may give us "/C:/path", we need "C:/path"
        if len(path_str) >= 3 and path_str[0] == '/' and path_str[2] == ':':
            # Remove leading slash for Windows drive letter
            path_str = path_str[1:]

        file_path = Path(path_str)

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
    r"""Sanitize code fence language identifier to prevent markdown injection.

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


def validate_user_regex_pattern(pattern: str) -> None:
    """Validate user-supplied regex pattern to prevent ReDoS attacks.

    This function checks user-supplied regex patterns for dangerous constructs
    that could lead to catastrophic backtracking (Regular Expression Denial of
    Service - ReDoS attacks). Patterns with nested quantifiers or other
    backtracking-prone structures are rejected.

    Parameters
    ----------
    pattern : str
        The regex pattern to validate

    Raises
    ------
    SecurityError
        If the pattern is too long or contains dangerous constructs

    Examples
    --------
    >>> validate_user_regex_pattern(r"^/docs/")
    # Returns None (safe pattern)

    >>> validate_user_regex_pattern(r"(a+)+")  # doctest: +SKIP
    SecurityError: Regex pattern contains dangerous nested quantifiers

    >>> validate_user_regex_pattern("x" * 1000)  # doctest: +SKIP
    SecurityError: Regex pattern exceeds maximum length

    Notes
    -----
    This function is conservative and may reject some complex but safe patterns.
    This is intentional to ensure security. Common safe patterns include:
    - Simple anchors: ^, $
    - Character classes: [a-z], [0-9]
    - Single-level quantifiers: a+, b*, c{2,5}
    - Alternations without quantifiers: (cat|dog)
    - Simple groups: (abc)+

    Dangerous patterns that are rejected include:
    - Nested quantifiers: (a+)+, (b*)*
    - Quantified groups with inner quantifiers: (a+){2,}
    - Lookaheads/lookbehinds with quantifiers: (?=.*)+, (?!test)*
    - Lookaheads/lookbehinds containing quantifiers: (?=.*a)
    - Overlapping alternations: (a|ab)*, (foo|foobar)+
    - Multiple nested groups: ((a+)
    - Greedy wildcards with quantifiers: .*+, .+*

    For more information on ReDoS attacks, see:
    https://owasp.org/www-community/attacks/Regular_expression_Denial_of_Service_-_ReDoS

    """
    from all2md.constants import DANGEROUS_REGEX_PATTERNS, MAX_REGEX_PATTERN_LENGTH
    from all2md.exceptions import SecurityError

    # Check pattern length
    if len(pattern) > MAX_REGEX_PATTERN_LENGTH:
        raise SecurityError(
            f"Regex pattern exceeds maximum length of {MAX_REGEX_PATTERN_LENGTH} characters. "
            f"This limit prevents potential ReDoS (Regular Expression Denial of Service) attacks."
        )

    # Check for dangerous patterns that can cause catastrophic backtracking
    for dangerous_pattern in DANGEROUS_REGEX_PATTERNS:
        if re.search(dangerous_pattern, pattern):
            raise SecurityError(
                f"Regex pattern contains dangerous nested quantifiers or similar constructs "
                f"that could lead to catastrophic backtracking (ReDoS). "
                f"Pattern: {pattern[:100]}{'...' if len(pattern) > 100 else ''}\n"
                f"Detected dangerous construct matching: {dangerous_pattern}\n"
                f"Avoid patterns like: (a+)+, (b*)*, (c+){{2,}}, etc."
            )

    # Try to compile the pattern to check if it's valid regex
    try:
        re.compile(pattern)
    except re.error as e:
        raise SecurityError(f"Invalid regex pattern: {e}") from e
