#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/latex.py
"""Configuration options for LaTeX parsing and rendering.

This module defines options for LaTeX document conversion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_LATEX_COMMENT_MODE,
    DEFAULT_LATEX_DOCUMENT_CLASS,
    DEFAULT_LATEX_ENCODING,
    DEFAULT_LATEX_ESCAPE_SPECIAL,
    DEFAULT_LATEX_INCLUDE_PREAMBLE,
    DEFAULT_LATEX_LINE_WIDTH,
    DEFAULT_LATEX_MATH_RENDER_MODE,
    DEFAULT_LATEX_PACKAGES,
    DEFAULT_LATEX_PARSE_CUSTOM_COMMANDS,
    DEFAULT_LATEX_PARSE_MATH,
    DEFAULT_LATEX_PARSE_PREAMBLE,
    DEFAULT_LATEX_PRESERVE_COMMENTS,
    DEFAULT_LATEX_STRICT_MODE,
    DEFAULT_LATEX_USE_UNICODE,
    LatexCommentMode,
    LatexMathRenderMode,
)
from all2md.options.base import BaseParserOptions, BaseRendererOptions


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
        default=DEFAULT_LATEX_PARSE_PREAMBLE,
        metadata={
            "help": "Parse document preamble for metadata",
            "cli_name": "no-parse-preamble",
            "importance": "core",
        },
    )
    parse_math: bool = field(
        default=DEFAULT_LATEX_PARSE_MATH,
        metadata={
            "help": "Parse math environments into AST math nodes",
            "cli_name": "no-parse-math",
            "importance": "core",
        },
    )
    parse_custom_commands: bool = field(
        default=DEFAULT_LATEX_PARSE_CUSTOM_COMMANDS,
        metadata={
            "help": "Attempt to parse unknown/custom LaTeX commands by extracting their arguments. "
            "When False (default), unknown commands are processed safely with minimal interpretation. "
            "When True, parser attempts to extract content from custom command arguments. "
            "(SECURITY: disabled by default to prevent unexpected behavior)",
            "cli_name": "parse-custom-commands",
            "importance": "security",
        },
    )
    strict_mode: bool = field(
        default=DEFAULT_LATEX_STRICT_MODE,
        metadata={"help": "Raise errors on invalid LaTeX syntax", "importance": "advanced"},
    )

    encoding: str = field(
        default=DEFAULT_LATEX_ENCODING,
        metadata={"help": "Text encoding for reading LaTeX files", "type": str, "importance": "advanced"},
    )
    preserve_comments: bool = field(
        default=DEFAULT_LATEX_PRESERVE_COMMENTS,
        metadata={"help": "Preserve LaTeX comments in AST", "cli_name": "preserve-comments", "importance": "advanced"},
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()


@dataclass(frozen=True)
class LatexRendererOptions(BaseRendererOptions):
    r"""Configuration options for AST-to-LaTeX rendering.

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
    comment_mode : {"percent", "todonotes", "marginnote", "ignore"}, default "percent"
        How to render Comment and CommentInline AST nodes:
        - "percent": Render as LaTeX comments (% Comment text)
        - "todonotes": Use \\todo{} command from todonotes package (colored margin notes)
        - "marginnote": Use \\marginpar{} for margin notes (simple side notes)
        - "ignore": Skip comment nodes entirely
        This controls presentation of comments from source documents.

    """

    document_class: str = field(
        default=DEFAULT_LATEX_DOCUMENT_CLASS,
        metadata={"help": "LaTeX document class (article, report, book, etc.)", "type": str, "importance": "core"},
    )
    include_preamble: bool = field(
        default=DEFAULT_LATEX_INCLUDE_PREAMBLE,
        metadata={
            "help": "Generate complete document with preamble",
            "cli_name": "no-include-preamble",
            "importance": "core",
        },
    )
    packages: list[str] = field(
        default_factory=lambda: DEFAULT_LATEX_PACKAGES.copy(),
        metadata={"help": "LaTeX packages to include in preamble", "importance": "advanced"},
    )
    math_mode: LatexMathRenderMode = field(
        default=DEFAULT_LATEX_MATH_RENDER_MODE,
        metadata={"help": "Preferred math rendering mode", "choices": ["inline", "display"], "importance": "core"},
    )
    line_width: int = field(
        default=DEFAULT_LATEX_LINE_WIDTH,
        metadata={"help": "Target line width for wrapping (0 = no wrapping)", "type": int, "importance": "advanced"},
    )
    escape_special: bool = field(
        default=DEFAULT_LATEX_ESCAPE_SPECIAL,
        metadata={"help": "Escape special LaTeX characters", "cli_name": "no-escape-special", "importance": "security"},
    )
    use_unicode: bool = field(
        default=DEFAULT_LATEX_USE_UNICODE,
        metadata={"help": "Allow Unicode characters in output", "cli_name": "no-use-unicode", "importance": "advanced"},
    )
    comment_mode: LatexCommentMode = field(
        default=DEFAULT_LATEX_COMMENT_MODE,
        metadata={
            "help": "How to render Comment and CommentInline nodes: "
            "percent (%% comments), todonotes (\\todo{}), marginnote (\\marginpar{}), "
            "ignore (skip comment nodes entirely). Controls presentation of source document comments.",
            "choices": ["percent", "todonotes", "marginnote", "ignore"],
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges and ensure immutability for LaTeX renderer options.

        Raises
        ------
        ValueError
            If any field value is outside its valid range.

        """
        # Call parent validation
        super().__post_init__()

        # Defensive copy of mutable collections to ensure immutability
        if self.packages is not None:
            object.__setattr__(self, "packages", list(self.packages))

        # Validate non-negative line width
        if self.line_width < 0:
            raise ValueError(f"line_width must be non-negative, got {self.line_width}")
