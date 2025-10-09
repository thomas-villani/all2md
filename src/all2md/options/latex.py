#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/latex.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from all2md import BaseParserOptions, BaseRendererOptions


@dataclass(frozen=True)
class LatexOptions(BaseParserOptions):
    r"""Configuration options for LaTeX-to-AST parsing.

    This dataclass contains settings specific to parsing LaTeX documents
    into AST representation using pylatexenc library.

    Parameters
    ----------
    parse_preamble : bool, default True
        Whether to parse document preamble for metadata.
        When True, extracts \title, \author, \date, etc.
    parse_math : bool, default True
        Whether to parse math environments into MathBlock/MathInline nodes.
        When True, preserves LaTeX math notation in AST.
    parse_custom_commands : bool, default False
        Whether to attempt parsing custom LaTeX commands.
        SECURITY: Disabled by default to prevent unexpected behavior.
    strict_mode : bool, default False
        Whether to raise errors on invalid LaTeX syntax.
        When False, attempts to recover gracefully.
    encoding : str, default "utf-8"
        Text encoding to use when reading LaTeX files.
    preserve_comments : bool, default False
        Whether to preserve LaTeX comments in the AST.
        When True, comments are stored in node metadata.

    """

    parse_preamble: bool = field(
        default=True,
        metadata={
            "help": "Parse document preamble for metadata",
            "cli_name": "no-parse-preamble"
        }
    )
    parse_math: bool = field(
        default=True,
        metadata={
            "help": "Parse math environments into AST math nodes",
            "cli_name": "no-parse-math"
        }
    )
    parse_custom_commands: bool = field(
        default=False,
        metadata={
            "help": "Parse custom LaTeX commands (SECURITY: disabled by default)",
            "cli_name": "parse-custom-commands"
        }
    )
    strict_mode: bool = field(
        default=False,
        metadata={
            "help": "Raise errors on invalid LaTeX syntax"
        }
    )
    encoding: str = field(
        default="utf-8",
        metadata={
            "help": "Text encoding for reading LaTeX files",
            "type": str
        }
    )
    preserve_comments: bool = field(
        default=False,
        metadata={
            "help": "Preserve LaTeX comments in AST",
            "cli_name": "preserve-comments"
        }
    )


@dataclass(frozen=True)
class LatexRendererOptions(BaseRendererOptions):
    """Configuration options for AST-to-LaTeX rendering.

    This dataclass contains settings for rendering AST documents as
    LaTeX output suitable for compilation with pdflatex/xelatex.

    Parameters
    ----------
    document_class : str, default "article"
        LaTeX document class to use (article, report, book, etc.).
    include_preamble : bool, default True
        Whether to generate a complete document with preamble.
        When False, generates only document body (for inclusion).
    packages : list[str], default ["amsmath", "graphicx", "hyperref"]
        LaTeX packages to include in preamble.
    math_mode : {"inline", "display"}, default "display"
        Preferred math rendering mode for ambiguous cases.
    line_width : int, default 0
        Target line width for text wrapping (0 = no wrapping).
    escape_special : bool, default True
        Whether to escape special LaTeX characters ($, %, &, etc.).
        Only disable if input is already LaTeX-safe.
    use_unicode : bool, default True
        Whether to allow Unicode characters in output.
        When False, uses LaTeX escapes for special characters.

    """

    document_class: str = field(
        default="article",
        metadata={
            "help": "LaTeX document class (article, report, book, etc.)",
            "type": str
        }
    )
    include_preamble: bool = field(
        default=True,
        metadata={
            "help": "Generate complete document with preamble",
            "cli_name": "no-include-preamble"
        }
    )
    packages: list[str] = field(
        default_factory=lambda: ["amsmath", "graphicx", "hyperref"],
        metadata={
            "help": "LaTeX packages to include in preamble"
        }
    )
    math_mode: Literal["inline", "display"] = field(
        default="display",
        metadata={
            "help": "Preferred math rendering mode",
            "choices": ["inline", "display"]
        }
    )
    line_width: int = field(
        default=0,
        metadata={
            "help": "Target line width for wrapping (0 = no wrapping)",
            "type": int
        }
    )
    escape_special: bool = field(
        default=True,
        metadata={
            "help": "Escape special LaTeX characters",
            "cli_name": "no-escape-special"
        }
    )
    use_unicode: bool = field(
        default=True,
        metadata={
            "help": "Allow Unicode characters in output",
            "cli_name": "no-use-unicode"
        }
    )
