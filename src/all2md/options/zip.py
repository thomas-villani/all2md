#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/options/zip.py
"""Configuration options for ZIP archive parsing.

This module defines options for parsing ZIP files with resource extraction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from all2md.options.base import BaseParserOptions


@dataclass(frozen=True)
class ZipOptions(BaseParserOptions):
    r"""Configuration options for ZIP archive to Markdown conversion.

    This dataclass contains settings specific to ZIP/archive processing,
    including file filtering, directory structure handling, and attachment extraction.

    Parameters
    ----------
    include_patterns : list[str] or None, default None
        Glob patterns for files to include (e.g., ['*.pdf', '*.docx']).
        If None, all parseable files are included.
    exclude_patterns : list[str] or None, default None
        Glob patterns for files to exclude (e.g., ['__MACOSX/*', '.DS_Store']).
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
    skip_empty_files : bool, default True
        Whether to skip files with no content or that fail to parse.
    include_resource_manifest : bool, default True
        Whether to include a manifest table of extracted resources at the end of the document.

    """

    include_patterns: Optional[list[str]] = field(
        default=None,
        metadata={
            "help": "Glob patterns for files to include",
            "cli_name": "include",
            "importance": "core"
        }
    )

    exclude_patterns: Optional[list[str]] = field(
        default=None,
        metadata={
            "help": "Glob patterns for files to exclude",
            "cli_name": "exclude",
            "importance": "core"
        }
    )

    max_depth: Optional[int] = field(
        default=None,
        metadata={
            "help": "Maximum directory depth to traverse",
            "importance": "advanced"
        }
    )

    create_section_headings: bool = field(
        default=True,
        metadata={
            "help": "Create section headings for each file",
            "cli_name": "no-section-headings",
            "importance": "core"
        }
    )

    preserve_directory_structure: bool = field(
        default=True,
        metadata={
            "help": "Include directory path in section headings",
            "cli_name": "no-preserve-directory",
            "importance": "core"
        }
    )

    flatten_structure: bool = field(
        default=False,
        metadata={
            "help": "Flatten directory structure in output",
            "cli_name": "flatten",
            "importance": "advanced"
        }
    )

    extract_resource_files: bool = field(
        default=True,
        metadata={
            "help": "Extract non-parseable files to attachment directory",
            "cli_name": "no-extract-resources",
            "importance": "core"
        }
    )

    skip_empty_files: bool = field(
        default=True,
        metadata={
            "help": "Skip files with no content or parse failures",
            "cli_name": "no-skip-empty",
            "importance": "advanced"
        }
    )

    include_resource_manifest: bool = field(
        default=True,
        metadata={
            "help": "Include manifest table of extracted resources",
            "cli_name": "no-resource-manifest",
            "importance": "advanced"
        }
    )
