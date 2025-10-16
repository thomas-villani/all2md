#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/ipynb.py
"""Configuration options for Jupyter Notebook parsing.

This module defines options for parsing .ipynb files with cell handling.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import DEFAULT_TRUNCATE_OUTPUT_LINES, DEFAULT_TRUNCATE_OUTPUT_MESSAGE
from all2md.options.base import BaseParserOptions


@dataclass(frozen=True)
class IpynbOptions(BaseParserOptions):
    """Configuration options for IPYNB-to-Markdown conversion.

    This dataclass contains settings specific to Jupyter Notebook processing,
    including output handling and image conversion preferences.

    Parameters
    ----------
    include_inputs : bool, default True
        Whether to include cell input (source code) in output.
    include_outputs : bool, default True
        Whether to include cell outputs in the markdown.
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
            "importance": "core"
        }
    )
    include_outputs: bool = field(
        default=True,
        metadata={
            "help": "Include cell outputs in the markdown",
            "cli_name": "no-include-outputs",
            "importance": "core"
        }
    )
    show_execution_count: bool = field(
        default=False,
        metadata={
            "help": "Show execution counts for code cells",
            "importance": "advanced"
        }
    )
    output_types: tuple[str, ...] | None = field(
        default=("stream", "execute_result", "display_data"),
        metadata={
            "help": "Types of outputs to include (stream, execute_result, display_data, error)",
            "action": "append",
            "importance": "core"
        }
    )
    image_format: str = field(
        default="png",
        metadata={
            "help": "Preferred image format for notebook outputs (png, jpeg)",
            "importance": "advanced"
        }
    )
    image_quality: int = field(
        default=85,
        metadata={
            "help": "JPEG quality setting (1-100) for image conversion",
            "importance": "advanced"
        }
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
            raise ValueError(
                f"image_quality must be in range [1, 100], got {self.image_quality}"
            )
