#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/options/zip.py
"""Configuration options for ZIP archive parsing.

This module defines options for parsing ZIP files with resource extraction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.options.base import BaseParserOptions
from all2md.options.common import AttachmentOptionsMixin


@dataclass(frozen=True)
class ZipOptions(BaseParserOptions, AttachmentOptionsMixin):
    r"""Configuration options for ZIP archive to Markdown conversion.

    This dataclass contains settings specific to ZIP/archive processing,
    including file filtering, directory structure handling, and attachment extraction.
    Inherits attachment handling from AttachmentOptionsMixin for extracting embedded
    resources.

    Parameters
    ----------
    include_patterns : list[str] or None, default None
        Glob patterns for files to include (e.g., ``['*.pdf', '*.docx']``).
        If None, all parseable files are included.
    exclude_patterns : list[str] or None, default None
        Glob patterns for files to exclude (e.g., ``['__MACOSX/*', '.DS_Store']``).
    max_depth : int or None, default None
        Maximum directory depth to traverse. None means unlimited.
    create_section_headings : bool, default True
        Whether to create section headings for each extracted file.
    preserve_directory_structure : bool, default True
        Whether to include directory path in section headings.
    flatten_structure : bool, default False
        Whether to flatten directory structure (ignore paths in output).
    extract_resource_files : bool, default True
        Whether to extract non-parseable files (images, CSS, etc.) to attachment directory.
    resource_file_extensions : list[str] or None, default None
        List of file extensions to treat as resources (e.g., ``['.png', '.css', '.js']``).
        If None, uses default list from ``RESOURCE_FILE_EXTENSIONS`` in constants.
        If empty list ``[]``, no files are treated as resources (all are parsed).
        Extensions should include the leading dot and are case-insensitive.
    skip_empty_files : bool, default True
        Whether to skip files with no content or that fail to parse.
    include_resource_manifest : bool, default True
        Whether to include a manifest table of extracted resources at the end of the document.
    enable_parallel_processing : bool, default False
        Whether to enable parallel processing for large archives (opt-in).
        When enabled and file count exceeds parallel_threshold, files are processed
        in parallel using a process pool for improved performance.
    max_workers : int or None, default None
        Maximum number of worker processes for parallel processing.
        If None, defaults to the number of CPU cores available.
    parallel_threshold : int, default 10
        Minimum number of files required to enable parallel processing.
        Archives with fewer files are always processed sequentially.

    """

    include_patterns: list[str] | None = field(
        default=None,
        metadata={"help": "Glob patterns for files to include", "cli_name": "include", "importance": "core"},
    )

    exclude_patterns: list[str] | None = field(
        default=None,
        metadata={"help": "Glob patterns for files to exclude", "cli_name": "exclude", "importance": "core"},
    )

    max_depth: int | None = field(
        default=None, metadata={"help": "Maximum directory depth to traverse", "importance": "advanced"}
    )

    create_section_headings: bool = field(
        default=True,
        metadata={
            "help": "Create section headings for each file",
            "cli_name": "no-section-headings",
            "importance": "core",
        },
    )

    preserve_directory_structure: bool = field(
        default=True,
        metadata={
            "help": "Include directory path in section headings (False = flatten structure)",
            "cli_name": "no-preserve-directory",
            "importance": "advanced",
        },
    )

    extract_resource_files: bool = field(
        default=True,
        metadata={
            "help": "Extract non-parseable files to attachment directory",
            "cli_name": "no-extract-resources",
            "importance": "core",
        },
    )

    resource_file_extensions: list[str] | None = field(
        default=None,
        metadata={
            "help": "File extensions to treat as resources (None=use defaults, []=parse all)",
            "cli_name": "resource-extensions",
            "importance": "advanced",
        },
    )

    skip_empty_files: bool = field(
        default=True,
        metadata={
            "help": "Skip files with no content or parse failures",
            "cli_name": "no-skip-empty",
            "importance": "advanced",
        },
    )

    include_resource_manifest: bool = field(
        default=True,
        metadata={
            "help": "Include manifest table of extracted resources",
            "cli_name": "no-resource-manifest",
            "importance": "advanced",
        },
    )

    enable_parallel_processing: bool = field(
        default=False,
        metadata={
            "help": "Enable parallel processing for large archives (opt-in)",
            "cli_name": "parallel",
            "importance": "advanced",
        },
    )

    max_workers: int | None = field(
        default=None,
        metadata={
            "help": "Maximum worker processes for parallel processing (None=auto-detect CPU cores)",
            "cli_name": "max-workers",
            "importance": "advanced",
        },
    )

    parallel_threshold: int = field(
        default=10,
        metadata={
            "help": "Minimum number of files to enable parallel processing",
            "cli_name": "parallel-threshold",
            "importance": "advanced",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
