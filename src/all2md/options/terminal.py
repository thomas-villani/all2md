#  Copyright (c) 2025 Tom Villani, Ph.D.
# all2md/options/terminal.py
"""Configuration options for rendering a document to the terminal.

The terminal renderer walks the AST and builds `rich` renderables directly, so
footnotes, math, task lists, definition lists and admonitions reach the screen
as what they are rather than as Markdown source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from all2md.options.base import BaseRendererOptions

TerminalColorSystem = Literal["auto", "standard", "256", "truecolor", "windows", "none"]
TerminalJustify = Literal["left", "center", "right", "full"]
TerminalCommentMode = Literal["visible", "ignore"]


@dataclass(frozen=True)
class TerminalRendererOptions(BaseRendererOptions):
    """Configuration options for AST to terminal (ANSI) rendering.

    Parameters
    ----------
    width : int or None, default None
        Width to lay the document out at, in columns. ``None`` uses the
        terminal's width (80 when there is no terminal).
    code_theme : str, default "monokai"
        Pygments theme for code blocks.
    inline_code_theme : str or None, default None
        Pygments theme for inline code. ``None`` styles inline code with the
        ``markdown.code`` style instead of highlighting it.
    hyperlinks : bool, default True
        Make links clickable (OSC 8). When off, a link's URL follows its text in
        parentheses unless the two are the same.
    justify : {"left", "center", "right", "full"} or None, default None
        Justification for paragraphs. ``None`` is left.
    word_wrap : bool, default True
        Wrap long lines. When off, lines are cropped at the width.
    color_system : {"auto", "standard", "256", "truecolor", "windows", "none"}, default "auto"
        Color depth of the output. ``auto`` detects it from the environment;
        ``none`` writes plain text, with no escape codes.
    comment_mode : {"visible", "ignore"}, default "visible"
        Show comments (dimmed, with their author) or leave them out.
    styles : dict or None, default None
        Style overrides, ``{name: style}``, as in the ``[rich]`` config table.
        Bare element names such as ``h1`` mean ``markdown.h1``.

    Examples
    --------
    Lay a document out at 72 columns without color:
        >>> options = TerminalRendererOptions(width=72, color_system="none")

    """

    width: int | None = field(
        default=None,
        metadata={"help": "Width in columns (default: the terminal's width, else 80)", "type": int},
    )
    code_theme: str = field(
        default="monokai",
        metadata={"help": "Pygments theme for code blocks", "importance": "core"},
    )
    inline_code_theme: str | None = field(
        default=None,
        metadata={
            "help": "Pygments theme for inline code (default: the markdown.code style)",
            "importance": "advanced",
        },
    )
    hyperlinks: bool = field(
        default=True,
        metadata={"help": "Clickable links (OSC 8)", "cli_name": "no-hyperlinks", "importance": "advanced"},
    )
    justify: TerminalJustify | None = field(
        default=None,
        metadata={"help": "Paragraph justification", "choices": ["left", "center", "right", "full"]},
    )
    word_wrap: bool = field(
        default=True,
        metadata={"help": "Word wrapping", "cli_name": "no-word-wrap", "importance": "advanced"},
    )
    color_system: TerminalColorSystem = field(
        default="auto",
        metadata={
            "help": "Color depth of the output",
            "choices": ["auto", "standard", "256", "truecolor", "windows", "none"],
            "importance": "core",
        },
    )
    comment_mode: TerminalCommentMode = field(
        default="visible",
        metadata={"help": "Show comments or leave them out", "choices": ["visible", "ignore"]},
    )
    styles: dict[str, str] | None = field(
        default=None,
        metadata={"help": "Style overrides as in the [rich] config table", "exclude_from_cli": True},
    )

    def __post_init__(self) -> None:
        """Validate options."""
        super().__post_init__()
        if self.width is not None and self.width < 1:
            raise ValueError(f"width must be at least 1, got {self.width}")
