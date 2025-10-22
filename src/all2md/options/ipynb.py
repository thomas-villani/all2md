#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/ipynb.py
"""Configuration options for Jupyter Notebook parsing.

This module defines options for parsing .ipynb files with cell handling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from all2md.constants import DEFAULT_TRUNCATE_OUTPUT_LINES, DEFAULT_TRUNCATE_OUTPUT_MESSAGE
from all2md.options.common import AttachmentOptionsMixin
from all2md.options.base import BaseParserOptions, BaseRendererOptions
from all2md.options.markdown import MarkdownOptions


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
    image_format : str, default "png"
        Preferred image format for notebook outputs. Options: "png", "jpeg".
    image_quality : int, default 85
        JPEG quality setting (1-100) when converting images to JPEG format.
    truncate_long_outputs : int or None, default DEFAULT_TRUNCATE_OUTPUT_LINES
        Maximum number of lines for text outputs before truncating.
        If None, outputs are not truncated.
    truncate_output_message : str or None, default DEFAULT_TRUNCATE_OUTPUT_MESSAGE
        The message to place to indicate truncated output.

    """

    include_inputs: bool = field(
        default=True,
        metadata={
            "help": "Include cell input (source code) in output",
            "cli_name": "no-include-inputs",
            "importance": "core",
        },
    )
    include_outputs: bool = field(
        default=True,
        metadata={
            "help": "Include cell outputs in the markdown",
            "cli_name": "no-include-outputs",
            "importance": "core",
        },
    )
    skip_empty_cells: bool = field(
        default=True,
        metadata={
            "help": "Skip cells with no content (preserves round-trip fidelity when False)",
            "cli_name": "no-skip-empty-cells",
            "importance": "advanced",
        },
    )
    show_execution_count: bool = field(
        default=False, metadata={"help": "Show execution counts for code cells", "importance": "advanced"}
    )
    output_types: tuple[str, ...] | None = field(
        default=("stream", "execute_result", "display_data"),
        metadata={
            "help": "Types of outputs to include (stream, execute_result, display_data, error)",
            "action": "append",
            "importance": "core",
        },
    )
    image_format: str = field(
        default="png",
        metadata={"help": "Preferred image format for notebook outputs (png, jpeg)", "importance": "advanced"},
    )
    image_quality: int = field(
        default=85, metadata={"help": "JPEG quality setting (1-100) for image conversion", "importance": "advanced"}
    )
    truncate_long_outputs: int | None = DEFAULT_TRUNCATE_OUTPUT_LINES
    truncate_output_message: str | None = DEFAULT_TRUNCATE_OUTPUT_MESSAGE

    def __post_init__(self) -> None:
        """Validate numeric ranges for IPYNB options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        # Validate image quality (1-100)
        if not 1 <= self.image_quality <= 100:
            raise ValueError(f"image_quality must be in range [1, 100], got {self.image_quality}")


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
    markdown_options : MarkdownOptions or None, default None
        Optional Markdown renderer configuration used when consolidating AST
        nodes into markdown notebook cells. When None, a default renderer is
        constructed per cell.

    """

    nbformat: int | Literal["auto"] = field(
        default=4,
        metadata={
            "help": "Major notebook format version (auto = preserve from source)",
            "importance": "advanced",
            "choices": ["auto", 4, 5],
        },
    )
    nbformat_minor: int | Literal["auto"] = field(
        default="auto",
        metadata={
            "help": "Minor notebook format revision (auto = preserve from source)",
            "importance": "advanced",
        },
    )
    default_language: str = field(
        default="python",
        metadata={
            "help": "Fallback programming language for language_info",
            "importance": "core",
        },
    )
    default_kernel_name: str = field(
        default="python3",
        metadata={
            "help": "Fallback kernelspec name when inference fails",
            "importance": "core",
        },
    )
    default_kernel_display_name: str = field(
        default="Python 3",
        metadata={
            "help": "Fallback kernelspec display name when inference fails",
            "importance": "core",
        },
    )
    infer_language_from_document: bool = field(
        default=True,
        metadata={
            "help": "Infer language from Document metadata before using defaults",
            "importance": "advanced",
        },
    )
    infer_kernel_from_document: bool = field(
        default=True,
        metadata={
            "help": "Infer kernelspec information from Document metadata when present",
            "importance": "advanced",
        },
    )
    include_trusted_metadata: bool = field(
        default=False,
        metadata={
            "help": "Preserve cell.metadata.trusted values in output notebook",
            "importance": "advanced",
        },
    )
    include_ui_metadata: bool = field(
        default=False,
        metadata={
            "help": "Preserve UI metadata like collapsed/scrolled/widget state",
            "importance": "advanced",
        },
    )
    preserve_unknown_metadata: bool = field(
        default=True,
        metadata={
            "help": "Retain unrecognized metadata keys instead of dropping them",
            "importance": "advanced",
        },
    )
    inline_attachments: bool = field(
        default=True,
        metadata={
            "help": "Embed attachments directly inside notebook cells",
            "importance": "core",
        },
    )
    markdown_options: MarkdownOptions | None = field(
        default=None,
        metadata={
            "help": "Override markdown renderer configuration for markdown cells",
            "importance": "advanced",
        },
    )
