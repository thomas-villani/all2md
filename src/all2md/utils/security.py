#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Security utilities for all2md conversion modules.

This module provides security validation functions to prevent unauthorized
access to local files and malicious ZIP archive processing.

Functions
---------
- resolve_file_url_to_path: Resolve file:// URL to canonical filesystem path
- validate_local_file_access: Check if access to a local file path is allowed
- validate_zip_archive: Pre-validate ZIP archives for security threats
- sanitize_language_identifier: Sanitize code fence language identifiers
"""

import logging
import re
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from all2md.constants import (
    DANGEROUS_NULL_LIKE_CHARS,
    DEFAULT_MAX_COMPRESSION_RATIO,
    DEFAULT_MAX_UNCOMPRESSED_SIZE,
    DEFAULT_MAX_ZIP_ENTRIES,
    MAX_LANGUAGE_IDENTIFIER_LENGTH,
    SAFE_LANGUAGE_IDENTIFIER_PATTERN,
)
from all2md.exceptions import MalformedFileError, ZipFileSecurityError

logger = logging.getLogger(__name__)


def sanitize_null_bytes(content: str) -> str:
    r"""Remove null bytes and zero-width characters that can bypass XSS filters.

    This function removes various null-like and zero-width Unicode characters
    that attackers may use to bypass XSS sanitization filters. These characters
    can be used to hide malicious payloads or break parser assumptions.

    Removed characters:
    - \\x00 (NULL byte)
    - \\ufeff (BOM/Zero Width No-Break Space)
    - \\u200b (Zero Width Space)
    - \\u200c (Zero Width Non-Joiner)
    - \\u200d (Zero Width Joiner)
    - \\u2060 (Word Joiner)

    Parameters
    ----------
    content : str
        Content to sanitize

    Returns
    -------
    str
        Sanitized content with dangerous characters removed

    Examples
    --------
    >>> sanitize_null_bytes("Hello\\x00World")
    'HelloWorld'
    >>> sanitize_null_bytes("Test\\u200bZero\\u200cWidth")
    'TestZeroWidth'
    >>> sanitize_null_bytes("Normal text")
    'Normal text'

    Notes
    -----
    This function is used by HTML and other parsers to prevent XSS attacks
    that rely on null bytes or zero-width characters to bypass security filters.

    See Also
    --------
    HtmlToAstConverter.convert_to_ast : Uses this function to sanitize HTML input

    """
    if not content:
        return content

    # Remove all dangerous null-like and zero-width characters
    for char in DANGEROUS_NULL_LIKE_CHARS:
        if char in content:
            content = content.replace(char, "")

    return content


def resolve_file_url_to_path(file_url: str) -> Path:
    """Resolve a file:// URL to a canonical filesystem path.

    This function provides consistent path resolution for file:// URLs across
    the codebase. It handles various file URL formats including relative paths,
    Windows paths, and UNC paths. All paths are resolved to absolute canonical
    form to prevent path traversal attacks.

    Supported file:// URL formats:
    - Unix/Linux absolute: file:///path/to/file
    - Windows drive letters: file:///C:/path/to/file
    - Windows UNC paths: file://server/share/file
    - Relative paths: file://./file or file://../file
    - Relative to CWD: file://filename

    Parameters
    ----------
    file_url : str
        The file:// URL to resolve

    Returns
    -------
    Path
        Resolved absolute path object

    Raises
    ------
    ValueError
        If file_url is not a file:// URL

    Examples
    --------
    >>> resolve_file_url_to_path("file:///etc/passwd")
    Path('/etc/passwd')
    >>> resolve_file_url_to_path("file://./image.png")  # doctest: +SKIP
    Path('/current/working/directory/image.png')
    >>> resolve_file_url_to_path("file:///C:/Users/file.txt")  # Windows
    Path('C:/Users/file.txt')

    Notes
    -----
    This function is used by both validate_local_file_access() and HTML parser
    to ensure consistent path resolution and prevent TOCTOU vulnerabilities.

    Always call validate_local_file_access() before using the resolved path
    to access files, to ensure security policies are enforced.

    """
    if not file_url.startswith("file://"):
        raise ValueError(f"Not a file:// URL: {file_url}")

    # Handle various file:// URL formats
    # The logic here must match the security validation expectations

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
        if len(path_part) >= 2 and path_part[1] == ":":
            # Windows absolute path: file://C:\path or file://C:/path
            # Normalize backslashes to forward slashes for Path
            normalized_path = path_part.replace("\\", "/")
            file_path = Path(normalized_path)
        # Check if it looks like a UNC path (has at least one slash/backslash after server name)
        elif "/" in path_part or "\\" in path_part:
            # Likely UNC path: file://server/share/file -> \\server\share\file
            file_path = Path("\\\\" + path_part.replace("/", "\\"))  # No f-str for python3.10
        else:
            # Likely relative path: file://filename
            file_path = Path.cwd() / path_part
    else:
        # Standard absolute file:///path handling
        parsed = urlparse(file_url)
        path_str = parsed.path

        # Handle Windows drive letters: file:///C:/path
        # urlparse may give us "/C:/path", we need "C:/path"
        if len(path_str) >= 3 and path_str[0] == "/" and path_str[2] == ":":
            # Remove leading slash for Windows drive letter
            path_str = path_str[1:]

        file_path = Path(path_str)

    # Resolve to canonical absolute path (follows symlinks, normalizes case on Windows)
    file_path = file_path.resolve()
    return file_path


def validate_local_file_access(
    file_url: str,
    allow_local_files: bool = False,
    local_file_allowlist: list[str] | None = None,
    local_file_denylist: list[str] | None = None,
    allow_cwd_files: bool = True,
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

    # Resolve the file URL to a canonical path
    # This uses centralized path resolution to prevent TOCTOU vulnerabilities
    file_path = resolve_file_url_to_path(file_url)
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
    file_path: str | Path,
    max_compression_ratio: float = DEFAULT_MAX_COMPRESSION_RATIO,
    max_uncompressed_size: int = DEFAULT_MAX_UNCOMPRESSED_SIZE,  # 1GB
    max_entries: int = DEFAULT_MAX_ZIP_ENTRIES,
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
        with zipfile.ZipFile(file_path, "r") as zf:
            entries = zf.infolist()

            # Check number of entries
            if len(entries) > max_entries:
                raise ZipFileSecurityError(f"ZIP archive contains too many entries: {len(entries)} > {max_entries}")

            total_uncompressed = 0
            total_compressed = 0

            for entry in entries:
                # Check for path traversal attempts
                name = entry.filename
                # Normalize backslashes to handle Windows paths
                name_norm = name.replace("\\", "/")

                # Check for Windows absolute paths (drive letters)
                if ":" in name_norm and len(name_norm) >= 2 and name_norm[1] == ":":
                    raise ZipFileSecurityError(f"ZIP archive contains Windows absolute path: {entry.filename}")

                p = PurePosixPath(name_norm)
                if any(part == ".." for part in p.parts) or name_norm.startswith("/"):
                    raise ZipFileSecurityError(f"ZIP archive contains suspicious path: {entry.filename}")

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
    except OSError as e:
        raise MalformedFileError(f"Could not read ZIP archive: {e}") from e


def validate_tar_archive(
    file_path: str | Path,
    max_compression_ratio: float = DEFAULT_MAX_COMPRESSION_RATIO,
    max_uncompressed_size: int = DEFAULT_MAX_UNCOMPRESSED_SIZE,
    max_entries: int = DEFAULT_MAX_ZIP_ENTRIES,
) -> None:
    """Validate a TAR archive for security threats before processing.

    This function performs pre-validation checks on TAR archives to detect
    potential security threats like tar bombs, path traversal attacks, and
    excessive resource consumption.

    Parameters
    ----------
    file_path : str or Path
        Path to the TAR archive to validate
    max_compression_ratio : float, default 100.0
        Maximum allowed compression ratio (uncompressed/compressed)
    max_uncompressed_size : int, default 1073741824
        Maximum total uncompressed size in bytes (default: 1GB)
    max_entries : int, default 10000
        Maximum number of entries in the archive

    Raises
    ------
    ArchiveSecurityError
        If the archive fails security validation
    MalformedFileError
        If the archive cannot be read for some other reason

    """
    import tarfile

    from all2md.exceptions import ArchiveSecurityError

    try:
        with tarfile.open(file_path, "r:*") as tf:
            members = tf.getmembers()

            # Check number of entries
            if len(members) > max_entries:
                raise ArchiveSecurityError(f"TAR archive contains too many entries: {len(members)} > {max_entries}")

            total_uncompressed = 0
            total_compressed = 0

            for member in members:
                # Check for path traversal attempts
                name = member.name
                # Normalize backslashes to handle Windows paths
                name_norm = name.replace("\\", "/")

                # Check for Windows absolute paths (drive letters)
                if ":" in name_norm and len(name_norm) >= 2 and name_norm[1] == ":":
                    raise ArchiveSecurityError(f"TAR archive contains Windows absolute path: {member.name}")

                p = PurePosixPath(name_norm)
                if any(part == ".." for part in p.parts) or name_norm.startswith("/"):
                    raise ArchiveSecurityError(f"TAR archive contains suspicious path: {member.name}")

                # Accumulate sizes for compression ratio calculation
                total_uncompressed += member.size
                # TAR files don't track compressed size per member, estimate from file size
                # For compressed TAR (gzip/bzip2/xz), we'll compare total file size

            # Check total uncompressed size
            if total_uncompressed > max_uncompressed_size:
                raise ArchiveSecurityError(
                    f"TAR archive uncompressed size too large: "
                    f"{total_uncompressed / (1024 * 1024):.1f}MB > "
                    f"{max_uncompressed_size / (1024 * 1024):.1f}MB"
                )

            # Check compression ratio (for compressed TAR files)
            import os

            if os.path.exists(file_path):
                total_compressed = os.path.getsize(file_path)
                if total_compressed > 0:
                    compression_ratio = total_uncompressed / total_compressed
                    if compression_ratio > max_compression_ratio:
                        raise ArchiveSecurityError(
                            f"TAR archive has suspicious compression ratio: {compression_ratio:.1f}:1"
                        )

    except tarfile.TarError as e:
        raise MalformedFileError(f"Invalid TAR archive: {e}") from e
    except OSError as e:
        raise MalformedFileError(f"Could not read TAR archive: {e}") from e


def validate_7z_archive(
    file_path: str | Path,
    max_compression_ratio: float = DEFAULT_MAX_COMPRESSION_RATIO,
    max_uncompressed_size: int = DEFAULT_MAX_UNCOMPRESSED_SIZE,
    max_entries: int = DEFAULT_MAX_ZIP_ENTRIES,
) -> None:
    """Validate a 7Z archive for security threats before processing.

    This function performs pre-validation checks on 7Z archives to detect
    potential security threats like archive bombs, path traversal attacks, and
    excessive resource consumption.

    Parameters
    ----------
    file_path : str or Path
        Path to the 7Z archive to validate
    max_compression_ratio : float, default 100.0
        Maximum allowed compression ratio (uncompressed/compressed)
    max_uncompressed_size : int, default 1073741824
        Maximum total uncompressed size in bytes (default: 1GB)
    max_entries : int, default 10000
        Maximum number of entries in the archive

    Raises
    ------
    ArchiveSecurityError
        If the archive fails security validation
    MalformedFileError
        If the archive cannot be read for some other reason

    """
    try:
        import py7zr
    except ImportError:
        # If py7zr is not installed, skip validation
        # The parser will handle the import error
        logger.debug("py7zr not installed, skipping 7Z validation")
        return

    from all2md.exceptions import ArchiveSecurityError

    try:
        with py7zr.SevenZipFile(file_path, mode="r") as sz:
            all_files = sz.list()

            # Check number of entries
            if len(all_files) > max_entries:
                raise ArchiveSecurityError(f"7Z archive contains too many entries: {len(all_files)} > {max_entries}")

            total_uncompressed = 0
            total_compressed = 0

            for file_info in all_files:
                # Check for path traversal attempts
                name = file_info.filename
                # Normalize backslashes to handle Windows paths
                name_norm = name.replace("\\", "/")

                # Check for Windows absolute paths (drive letters)
                if ":" in name_norm and len(name_norm) >= 2 and name_norm[1] == ":":
                    raise ArchiveSecurityError(f"7Z archive contains Windows absolute path: {file_info.filename}")

                p = PurePosixPath(name_norm)
                if any(part == ".." for part in p.parts) or name_norm.startswith("/"):
                    raise ArchiveSecurityError(f"7Z archive contains suspicious path: {file_info.filename}")

                # Accumulate sizes
                total_uncompressed += file_info.uncompressed
                total_compressed += file_info.compressed if file_info.compressed else 0

            # Check total uncompressed size
            if total_uncompressed > max_uncompressed_size:
                raise ArchiveSecurityError(
                    f"7Z archive uncompressed size too large: "
                    f"{total_uncompressed / (1024 * 1024):.1f}MB > "
                    f"{max_uncompressed_size / (1024 * 1024):.1f}MB"
                )

            # Check compression ratio
            if total_compressed > 0:
                compression_ratio = total_uncompressed / total_compressed
                if compression_ratio > max_compression_ratio:
                    raise ArchiveSecurityError(
                        f"7Z archive has suspicious compression ratio: {compression_ratio:.1f}:1"
                    )

    except py7zr.Bad7zFile as e:
        raise MalformedFileError(f"Invalid 7Z archive: {e}") from e
    except OSError as e:
        raise MalformedFileError(f"Could not read 7Z archive: {e}") from e


def validate_rar_archive(
    file_path: str | Path,
    max_compression_ratio: float = DEFAULT_MAX_COMPRESSION_RATIO,
    max_uncompressed_size: int = DEFAULT_MAX_UNCOMPRESSED_SIZE,
    max_entries: int = DEFAULT_MAX_ZIP_ENTRIES,
) -> None:
    """Validate a RAR archive for security threats before processing.

    This function performs pre-validation checks on RAR archives to detect
    potential security threats like archive bombs, path traversal attacks, and
    excessive resource consumption.

    Parameters
    ----------
    file_path : str or Path
        Path to the RAR archive to validate
    max_compression_ratio : float, default 100.0
        Maximum allowed compression ratio (uncompressed/compressed)
    max_uncompressed_size : int, default 1073741824
        Maximum total uncompressed size in bytes (default: 1GB)
    max_entries : int, default 10000
        Maximum number of entries in the archive

    Raises
    ------
    ArchiveSecurityError
        If the archive fails security validation
    MalformedFileError
        If the archive cannot be read for some other reason

    """
    try:
        import rarfile
    except ImportError:
        # If rarfile is not installed, skip validation
        # The parser will handle the import error
        logger.debug("rarfile not installed, skipping RAR validation")
        return

    from all2md.exceptions import ArchiveSecurityError

    try:
        with rarfile.RarFile(file_path) as rf:
            members = rf.infolist()

            # Check number of entries
            if len(members) > max_entries:
                raise ArchiveSecurityError(f"RAR archive contains too many entries: {len(members)} > {max_entries}")

            total_uncompressed = 0
            total_compressed = 0

            for member in members:
                # Check for path traversal attempts
                name = member.filename
                # Normalize backslashes to handle Windows paths
                name_norm = name.replace("\\", "/")

                # Check for Windows absolute paths (drive letters)
                if ":" in name_norm and len(name_norm) >= 2 and name_norm[1] == ":":
                    raise ArchiveSecurityError(f"RAR archive contains Windows absolute path: {member.filename}")

                p = PurePosixPath(name_norm)
                if any(part == ".." for part in p.parts) or name_norm.startswith("/"):
                    raise ArchiveSecurityError(f"RAR archive contains suspicious path: {member.filename}")

                # Accumulate sizes
                total_uncompressed += member.file_size
                total_compressed += member.compress_size

            # Check total uncompressed size
            if total_uncompressed > max_uncompressed_size:
                raise ArchiveSecurityError(
                    f"RAR archive uncompressed size too large: "
                    f"{total_uncompressed / (1024 * 1024):.1f}MB > "
                    f"{max_uncompressed_size / (1024 * 1024):.1f}MB"
                )

            # Check compression ratio
            if total_compressed > 0:
                compression_ratio = total_uncompressed / total_compressed
                if compression_ratio > max_compression_ratio:
                    raise ArchiveSecurityError(
                        f"RAR archive has suspicious compression ratio: {compression_ratio:.1f}:1"
                    )

    except rarfile.BadRarFile as e:
        raise MalformedFileError(f"Invalid RAR archive: {e}") from e
    except OSError as e:
        raise MalformedFileError(f"Could not read RAR archive: {e}") from e


def validate_safe_extraction_path(output_dir: str | Path, zip_entry_name: str) -> Path:
    """Validate and return a safe extraction path for a ZIP/archive entry to prevent path traversal.

    This function prevents Zip Slip attacks by ensuring that extracted files
    cannot escape the intended output directory through absolute paths or
    parent directory traversal (..). Works for ZIP and other archive formats.

    Parameters
    ----------
    output_dir : str or Path
        The base directory where files should be extracted
    zip_entry_name : str
        The filename from the archive entry (ZipInfo.filename or archive member name)

    Returns
    -------
    Path
        A safe, validated absolute path for extraction

    Raises
    ------
    ArchiveSecurityError
        If the path contains dangerous patterns or would escape output_dir

    Examples
    --------
    >>> validate_safe_extraction_path("/tmp/out", "subdir/file.txt")
    Path('/tmp/out/subdir/file.txt')

    >>> validate_safe_extraction_path("/tmp/out", "../etc/passwd")  # doctest: +SKIP
    ArchiveSecurityError: Unsafe path in archive entry: ../etc/passwd

    >>> validate_safe_extraction_path("/tmp/out", "/etc/passwd")  # doctest: +SKIP
    ArchiveSecurityError: Unsafe path in archive entry: /etc/passwd

    Notes
    -----
    This function is critical for preventing Zip Slip vulnerabilities (CVE-2018-1000117
    and related). Always use this when extracting archive entries to the filesystem.

    See Also
    --------
    validate_zip_archive : Pre-validate ZIP archives for security threats
    validate_tar_archive : Pre-validate TAR archives for security threats

    """
    import os

    from all2md.exceptions import ArchiveSecurityError

    # Normalize to POSIX path (archives typically use forward slashes)
    # Replace backslashes with forward slashes to handle malformed entries
    normalized_name = zip_entry_name.replace("\\", "/")

    # Check for Windows absolute paths (drive letters like C:, D:, etc.)
    # These are not caught by PurePosixPath.is_absolute()
    if ":" in normalized_name:
        # Check if it looks like a drive letter (single letter followed by colon)
        if len(normalized_name) >= 2 and normalized_name[1] == ":":
            raise ArchiveSecurityError(f"Unsafe Windows absolute path in archive entry: {zip_entry_name}")

    # Use PurePosixPath to parse the normalized path
    try:
        rel_path = PurePosixPath(normalized_name)
    except Exception as e:
        raise ArchiveSecurityError(f"Invalid path in archive entry: {zip_entry_name}") from e

    # Reject absolute paths (starting with /)
    if rel_path.is_absolute():
        raise ArchiveSecurityError(f"Unsafe absolute path in archive entry: {zip_entry_name}")

    # Reject paths containing parent directory traversal or current directory
    # Check each component for dangerous patterns
    for part in rel_path.parts:
        if part in (".", ".."):
            raise ArchiveSecurityError(f"Unsafe path component in archive entry: {zip_entry_name} (contains '{part}')")

    # Convert output_dir to Path and resolve it
    output_dir_path = Path(output_dir).resolve()

    # Convert the relative path to a native path under output_dir
    # Use joinpath with unpacked parts to build the path correctly
    target_path = output_dir_path.joinpath(*rel_path.parts)

    # Resolve the target path to get the absolute canonical path
    # This handles any remaining symbolic links or path anomalies
    try:
        target_resolved = target_path.resolve()
    except Exception as e:
        raise ArchiveSecurityError(f"Cannot resolve path for archive entry: {zip_entry_name}") from e

    # Ensure the resolved target is within the output directory
    # Use string comparison with os.sep to ensure proper prefix matching
    output_dir_str = str(output_dir_path)
    target_str = str(target_resolved)

    # Check if target is inside output_dir
    # We need to be careful about paths like:
    # - /tmp/output vs /tmp/output-sibling
    # So we ensure the prefix is followed by a separator or is exactly the same
    if not (target_str.startswith(output_dir_str + os.sep) or target_str == output_dir_str):
        raise ArchiveSecurityError(f"Path escapes output directory: {zip_entry_name} -> {target_str}")

    return target_resolved


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


def validate_safe_output_directory(
    output_dir: str | Path,
    allowed_base_dirs: list[str | Path] | None = None,
    block_sensitive_paths: bool = True,
) -> Path:
    """Validate that an output directory is safe for file operations.

    This function prevents path traversal attacks by detecting and blocking
    relative paths that escape the current working directory (e.g., `../../etc/`).
    Absolute paths are allowed but can be validated against an allowlist.

    Security Model
    --------------
    By default, this function:
    - BLOCKS: Relative paths that traverse outside CWD (e.g., `../../../etc/`)
    - BLOCKS: Paths to sensitive system directories (optional, via block_sensitive_paths)
    - ALLOWS: Relative paths within CWD (e.g., `./attachments`, `subdir/files`)
    - ALLOWS: Absolute paths (explicit intent, but check sensitive paths)

    Parameters
    ----------
    output_dir : str or Path
        The output directory to validate
    allowed_base_dirs : list[str | Path] | None, default None
        Optional allowlist of base directories. If provided, output_dir must be
        within one of these directories. When None, uses the default security
        model described above.
    block_sensitive_paths : bool, default True
        Block paths to common sensitive system directories like /etc, /sys, /proc.
        Only applies when allowed_base_dirs is None.

    Returns
    -------
    Path
        The validated, resolved absolute path

    Raises
    ------
    SecurityError
        If the path contains path traversal patterns or targets sensitive locations

    Examples
    --------
    >>> validate_safe_output_directory("./attachments")  # doctest: +SKIP
    Path('/current/working/directory/attachments')

    >>> validate_safe_output_directory("../../../etc/")  # doctest: +SKIP
    SecurityError: Path traversal detected

    >>> validate_safe_output_directory("/tmp/safe-output")  # doctest: +SKIP
    Path('/tmp/safe-output')

    >>> validate_safe_output_directory("/tmp/out", allowed_base_dirs=["/tmp"])  # doctest: +SKIP
    Path('/tmp/out')

    Notes
    -----
    This function focuses on preventing PATH TRAVERSAL attacks (the actual
    vulnerability identified in the security review) rather than restricting
    all paths outside CWD, which would break legitimate use cases.

    """
    from all2md.exceptions import SecurityError

    if not output_dir or (isinstance(output_dir, str) and not output_dir.strip()):
        raise SecurityError("Output directory cannot be empty")

    # Store original for error messages
    original_dir = str(output_dir)

    # Check for path traversal patterns in the original string
    # This is the primary security check - detect attempts to escape via ../
    if isinstance(output_dir, str):
        # Normalize path separators
        normalized = output_dir.replace("\\", "/")

        # Check for parent directory traversal patterns
        if "/../" in normalized or normalized.startswith("../") or normalized.endswith("/.."):
            # Additional check: does it actually escape CWD?
            # Some patterns like "subdir/../otherdir" are safe (stay in CWD)
            try:
                test_path = Path(output_dir).resolve()
                cwd = Path.cwd().resolve()
                try:
                    test_path.relative_to(cwd)
                    # It's within CWD despite having .., allow it
                except ValueError:
                    # It escapes CWD - this is the attack vector
                    raise SecurityError(
                        f"Path traversal detected in output directory: '{original_dir}'. "
                        f"Relative paths that escape the current working directory are not allowed. "
                        f"Attempted to access: {test_path}, CWD: {cwd}"
                    ) from None
            except Exception as e:
                # If we can't resolve it, be safe and block it
                raise SecurityError(f"Suspicious path traversal pattern detected: '{original_dir}'") from e

    # Convert to Path and resolve to absolute canonical form
    try:
        output_path = Path(output_dir).resolve()
    except Exception as e:
        raise SecurityError(f"Invalid output directory path: {output_dir}") from e

    # Check if allowed_base_dirs is provided (explicit allowlist)
    if allowed_base_dirs is not None:
        if not allowed_base_dirs:
            raise SecurityError(
                "allowed_base_dirs cannot be an empty list. "
                "Pass None to use default security checks, or provide allowed directories."
            )

        # Validate against allowed base directories
        for base_dir in allowed_base_dirs:
            try:
                base_path = Path(base_dir).resolve()
                # Check if output_path is within or equal to base_path
                try:
                    output_path.relative_to(base_path)
                    # Success - output_path is within this base directory
                    return output_path
                except ValueError:
                    # Not within this base directory, try next one
                    continue
            except Exception as e:
                logger.warning(f"Invalid base directory in allowlist: {base_dir}: {e}")
                continue

        # If we get here, output_path is not within any allowed base directory
        raise SecurityError(
            f"Output directory '{original_dir}' is not within any allowed base directory. "
            f"Allowed base directories: {[str(d) for d in allowed_base_dirs]}"
        )

    # No explicit allowlist - apply default security checks
    # Block paths to sensitive system directories
    if block_sensitive_paths:
        sensitive_prefixes = [
            "/etc",
            "/sys",
            "/proc",
            "/dev",
            "/boot",
            "/root",
            "C:\\Windows",
            "C:\\System32",
            "C:\\Program Files",
        ]

        output_str = str(output_path).replace("\\", "/")
        for prefix in sensitive_prefixes:
            prefix_normalized = prefix.replace("\\", "/")
            if output_str.startswith(prefix_normalized):
                raise SecurityError(
                    f"Output directory targets sensitive system location: '{original_dir}' -> {output_path}. "
                    f"Writing to {prefix} is not allowed for security reasons."
                )

    return output_path


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

    For more information on ReDoS attacks, see the OWASP documentation on
    Regular Expression Denial of Service attacks.

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


def is_relative_url(url: str) -> bool:
    """Check if a URL is a relative URL.

    Relative URLs do not have a scheme and typically start with #, /, ./, ../, or ?.

    Parameters
    ----------
    url : str
        URL to check

    Returns
    -------
    bool
        True if URL is relative, False otherwise

    Examples
    --------
    >>> is_relative_url("#section")
    True
    >>> is_relative_url("/path/to/file")
    True
    >>> is_relative_url("./file.html")
    True
    >>> is_relative_url("../parent/file.html")
    True
    >>> is_relative_url("?query=param")
    True
    >>> is_relative_url("https://example.com")
    False
    >>> is_relative_url("javascript:alert(1)")
    False

    """
    if not url or not url.strip():
        return True  # Empty URLs are considered relative

    url_stripped = url.strip()

    # Check for common relative URL patterns
    return url_stripped.startswith(("#", "/", "./", "../", "?"))


def is_url_scheme_dangerous(url: str) -> bool:
    """Check if a URL uses a dangerous scheme.

    Dangerous schemes include javascript:, vbscript:, data:text/html, and others
    that can be used for XSS attacks or malicious code execution.

    Parameters
    ----------
    url : str
        URL to check

    Returns
    -------
    bool
        True if URL uses a dangerous scheme, False otherwise

    Examples
    --------
    >>> is_url_scheme_dangerous("https://example.com")
    False
    >>> is_url_scheme_dangerous("javascript:alert('xss')")
    True
    >>> is_url_scheme_dangerous("data:text/html,<script>alert('xss')</script>")
    True
    >>> is_url_scheme_dangerous("/relative/path")
    False
    >>> is_url_scheme_dangerous("vbscript:msgbox('xss')")
    True

    """
    from all2md.constants import DANGEROUS_SCHEMES

    if not url or not url.strip():
        return False

    url_lower = url.lower().strip()

    # Relative URLs are not dangerous
    if is_relative_url(url_lower):
        return False

    # Check for dangerous schemes (exact prefix match)
    for dangerous_scheme in DANGEROUS_SCHEMES:
        if url_lower.startswith(dangerous_scheme.lower()):
            return True

    # Try parsing to check the scheme component
    try:
        parsed = urlparse(url_lower)
        # Extract base scheme name without the colon
        scheme = parsed.scheme

        # Check if scheme matches dangerous scheme patterns
        if scheme in ("javascript", "vbscript", "about"):
            return True

        # Check for data: URLs with dangerous content types
        if scheme == "data":
            # data: URLs can be safe (like data:image/png) or dangerous (like data:text/html)
            # Check if it's a dangerous data URL type
            if any(
                danger in url_lower
                for danger in (
                    "data:text/html",
                    "data:text/javascript",
                    "data:application/javascript",
                    "data:application/x-javascript",
                )
            ):
                return True

    except ValueError:
        # If URL parsing fails, consider it potentially dangerous
        return True

    return False


def validate_url_scheme_safe(url: str, context: str = "URL") -> None:
    """Validate that a URL does not use a dangerous scheme.

    This function raises a ValueError if the URL uses a dangerous scheme,
    making it suitable for strict validation contexts.

    Parameters
    ----------
    url : str
        URL to validate
    context : str, default "URL"
        Context description for error messages (e.g., "Link", "Image")

    Raises
    ------
    ValueError
        If URL uses a dangerous scheme

    Examples
    --------
    >>> validate_url_scheme_safe("https://example.com")
    # No exception raised

    >>> validate_url_scheme_safe("javascript:alert(1)")  # doctest: +SKIP
    ValueError: URL uses dangerous scheme

    >>> validate_url_scheme_safe("/relative/path")
    # No exception raised

    """
    if is_url_scheme_dangerous(url):
        # Extract the scheme for error message
        url_lower = url.lower()
        scheme = url_lower.split(":", 1)[0] if ":" in url_lower else "unknown"
        raise ValueError(f"{context} URL uses dangerous scheme '{scheme}': {url[:50]}")
