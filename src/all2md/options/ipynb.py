#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/ipynb.py
"""Configuration options for Jupyter Notebook parsing.

This module defines options for parsing .ipynb files with cell handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from all2md.constants import (
    DEFAULT_IPYNB_DEFAULT_KERNEL_DISPLAY_NAME,
    DEFAULT_IPYNB_DEFAULT_KERNEL_NAME,
    DEFAULT_IPYNB_DEFAULT_LANGUAGE,
    DEFAULT_IPYNB_INCLUDE_INPUTS,
    DEFAULT_IPYNB_INCLUDE_OUTPUTS,
    DEFAULT_IPYNB_INCLUDE_TRUSTED_METADATA,
    DEFAULT_IPYNB_INCLUDE_UI_METADATA,
    DEFAULT_IPYNB_INFER_KERNEL_FROM_DOCUMENT,
    DEFAULT_IPYNB_INFER_LANGUAGE_FROM_DOCUMENT,
    DEFAULT_IPYNB_INLINE_ATTACHMENTS,
    DEFAULT_IPYNB_NBFORMAT,
    DEFAULT_IPYNB_NBFORMAT_MINOR,
    DEFAULT_IPYNB_OUTPUT_TYPES,
    DEFAULT_IPYNB_PRESERVE_UNKNOWN_METADATA,
    DEFAULT_IPYNB_SHOW_EXECUTION_COUNT,
    DEFAULT_IPYNB_SKIP_EMPTY_CELLS,
    DEFAULT_TRUNCATE_OUTPUT_LINES,
    DEFAULT_TRUNCATE_OUTPUT_MESSAGE,
)
from all2md.options.base import BaseParserOptions, BaseRendererOptions
from all2md.options.common import AttachmentOptionsMixin
from all2md.options.markdown import MarkdownRendererOptions


@dataclass(frozen=True)
class IpynbOptions(BaseParserOptions, AttachmentOptionsMixin):
    """Configuration options for IPYNB-to-Markdown conversion.

    This dataclass contains settings specific to Jupyter Notebook processing,
    including output handling and image conversion preferences. Inherits
    attachment handling from AttachmentOptionsMixin for notebook output images.

    Parameters
    ----------
    include_inputs : bool, default True
        Whether to include cell input (source code) in output.
    include_outputs : bool, default True
        Whether to include cell outputs in the markdown.
    skip_empty_cells : bool, default True
        Whether to skip cells with no content. When False, empty cells are preserved
        as empty blocks to maintain round-trip fidelity. When True, empty cells are
        omitted for cleaner output.
    show_execution_count : bool, default False
        Whether to show execution counts for code cells.
    output_types : list[str] or None, default ["stream", "execute_result", "display_data"]
        Types of outputs to include. Valid types: "stream", "execute_result", "display_data", "error".
        If None, includes all output types.
    truncate_long_outputs : int or None, default DEFAULT_TRUNCATE_OUTPUT_LINES
        Maximum number of lines for text outputs before truncating.
        If None, outputs are not truncated.
    truncate_output_message : str or None, default DEFAULT_TRUNCATE_OUTPUT_MESSAGE
        The message to place to indicate truncated output.
    strip_html_from_markdown : bool, default True
        Whether to strip HTML elements (HTMLInline and HTMLBlock nodes) from
        markdown cells for security. When True, HTML in markdown cells is removed
        to prevent XSS attacks. When False, HTML is preserved as-is (use only
        with trusted notebooks).

    """

    include_inputs: bool = field(
        default=DEFAULT_IPYNB_INCLUDE_INPUTS,
        metadata={
            "help": "Include cell input (source code) in output",
            "cli_name": "no-include-inputs",
            "importance": "core",
        },
    )
    include_outputs: bool = field(
        default=DEFAULT_IPYNB_INCLUDE_OUTPUTS,
        metadata={
            "help": "Include cell outputs in the markdown",
            "cli_name": "no-include-outputs",
            "importance": "core",
        },
    )
    skip_empty_cells: bool = field(
        default=DEFAULT_IPYNB_SKIP_EMPTY_CELLS,
        metadata={
            "help": "Skip cells with no content (preserves round-trip fidelity when False)",
            "cli_name": "no-skip-empty-cells",
            "importance": "advanced",
        },
    )
    show_execution_count: bool = field(
        default=DEFAULT_IPYNB_SHOW_EXECUTION_COUNT,
        metadata={"help": "Show execution counts for code cells", "importance": "advanced"},
    )

    output_types: tuple[str, ...] | None = field(
        default=DEFAULT_IPYNB_OUTPUT_TYPES,
        metadata={
            "help": "Types of outputs to include (stream, execute_result, display_data, error)",
            "action": "append",
            "importance": "core",
        },
    )

    truncate_long_outputs: int | None = field(
        default=DEFAULT_TRUNCATE_OUTPUT_LINES,
        metadata={"help": "Maximum number of lines for text outputs before truncating", "importance": "advanced"},
    )
    truncate_output_message: str | None = field(
        default=DEFAULT_TRUNCATE_OUTPUT_MESSAGE,
        metadata={"help": "Message to indicate truncated output", "importance": "advanced"},
    )
    strip_html_from_markdown: bool = field(
        default=True,
        metadata={
            "help": "Strip HTML elements from markdown cells for security (prevents XSS)",
            "cli_name": "no-strip-html-from-markdown",
            "importance": "security",
        },
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges for IPYNB options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        # Call parent validation
        super().__post_init__()


@dataclass(frozen=True)
class IpynbRendererOptions(BaseRendererOptions):
    """Configuration options for rendering AST documents to Jupyter notebooks.

    These options control notebook metadata inference, attachment handling, and
    preservation of notebook-specific metadata to support near round-tripping
    between AST and .ipynb formats.

    Parameters
    ----------
    nbformat : int or "auto", default 4
        Major notebook format version to emit. When "auto", use the version
        discovered in the source document metadata and fall back to 4.
    nbformat_minor : int or "auto", default "auto"
        Minor notebook format revision. "auto" preserves the original value
        from document metadata when available.
    default_language : str, default "python"
        Fallback programming language when the document does not provide one.
    default_kernel_name : str, default "python3"
        Fallback kernel name for kernelspec metadata when inference fails.
    default_kernel_display_name : str, default "Python 3"
        Fallback kernel display name when inference fails.
    infer_language_from_document : bool, default True
        When True, prefer `Document.metadata["language"]` (and related fields)
        before `default_language`.
    infer_kernel_from_document : bool, default True
        When True, attempt to build kernelspec metadata from document metadata
        (e.g., `custom["kernel"]`) before falling back to defaults.
    include_trusted_metadata : bool, default False
        When False, strip `trusted` flags from cell metadata for safer output.
    include_ui_metadata : bool, default False
        When False, drop UI hints such as `collapsed`, `scrolled`, and widget
        metadata to avoid propagating viewer state.
    preserve_unknown_metadata : bool, default True
        When True, retain metadata keys that are not explicitly filtered out.
    inline_attachments : bool, default True
        Whether to emit attachments inline (base64-encoded) in the notebook
        instead of delegating to external download locations.
    markdown_options : MarkdownRendererOptions or None, default None
        Optional Markdown renderer configuration used when consolidating AST
        nodes into markdown notebook cells. When None, a default renderer is
        constructed per cell.

    """

    nbformat: int | Literal["auto"] = field(
        default=DEFAULT_IPYNB_NBFORMAT,
        metadata={
            "help": "Major notebook format version (auto = preserve from source)",
            "importance": "advanced",
            "choices": ["auto", 4, 5],
        },
    )
    nbformat_minor: int | Literal["auto"] = field(
        default=DEFAULT_IPYNB_NBFORMAT_MINOR,
        metadata={
            "help": "Minor notebook format revision (auto = preserve from source)",
            "importance": "advanced",
        },
    )
    default_language: str = field(
        default=DEFAULT_IPYNB_DEFAULT_LANGUAGE,
        metadata={
            "help": "Fallback programming language for language_info",
            "importance": "core",
        },
    )
    default_kernel_name: str = field(
        default=DEFAULT_IPYNB_DEFAULT_KERNEL_NAME,
        metadata={
            "help": "Fallback kernelspec name when inference fails",
            "importance": "core",
        },
    )
    default_kernel_display_name: str = field(
        default=DEFAULT_IPYNB_DEFAULT_KERNEL_DISPLAY_NAME,
        metadata={
            "help": "Fallback kernelspec display name when inference fails",
            "importance": "core",
        },
    )
    infer_language_from_document: bool = field(
        default=DEFAULT_IPYNB_INFER_LANGUAGE_FROM_DOCUMENT,
        metadata={
            "help": "Infer language from Document metadata before using defaults",
            "importance": "advanced",
        },
    )
    infer_kernel_from_document: bool = field(
        default=DEFAULT_IPYNB_INFER_KERNEL_FROM_DOCUMENT,
        metadata={
            "help": "Infer kernelspec information from Document metadata when present",
            "importance": "advanced",
        },
    )
    include_trusted_metadata: bool = field(
        default=DEFAULT_IPYNB_INCLUDE_TRUSTED_METADATA,
        metadata={
            "help": "Preserve cell.metadata.trusted values in output notebook",
            "importance": "advanced",
        },
    )
    include_ui_metadata: bool = field(
        default=DEFAULT_IPYNB_INCLUDE_UI_METADATA,
        metadata={
            "help": "Preserve UI metadata like collapsed/scrolled/widget state",
            "importance": "advanced",
        },
    )
    preserve_unknown_metadata: bool = field(
        default=DEFAULT_IPYNB_PRESERVE_UNKNOWN_METADATA,
        metadata={
            "help": "Retain unrecognized metadata keys instead of dropping them",
            "importance": "advanced",
        },
    )
    inline_attachments: bool = field(
        default=DEFAULT_IPYNB_INLINE_ATTACHMENTS,
        metadata={
            "help": "Embed attachments directly inside notebook cells",
            "importance": "core",
        },
    )
    markdown_options: MarkdownRendererOptions | None = field(
        default=None,
        metadata={
            "help": "Override markdown renderer configuration for markdown cells",
            "importance": "advanced",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
