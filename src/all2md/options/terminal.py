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
ClickableLinks = Literal["none", "web", "all"]
TerminalMathMode = Literal["latex", "unicode"]

#: Help for the ``--math`` flag of ``all2md`` (``rcat``) and ``all2md read``.
MATH_MODE_HELP = (
    "How math is shown: 'latex' (default) prints its LaTeX source; 'unicode' writes it with Unicode symbols, "
    "superscripts and subscripts (\\alpha^2 + x_i as α² + xᵢ), with matrices and aligned equations on lines "
    "of their own. 'unicode' needs pylatexenc (pip install 'all2md[latex]') and falls back to LaTeX without it."
)

#: Help for the ``--clickable-links`` flag of ``all2md`` (``rcat``) and ``all2md read``.
CLICKABLE_LINKS_HELP = (
    "Which links a click in the terminal may open (OSC 8 hyperlinks): 'none' (default), 'web' (http and "
    "https only) or 'all'. 'all' includes file: links and the handlers installed applications register "
    "(ms-msdt:, vscode:, ...), so a click on a link in a document you did not write can start a program; "
    "use it only for documents you trust. External link targets are shown after their text either way."
)


@dataclass(frozen=True)
class TerminalRendererOptions(BaseRendererOptions):
    r"""Configuration options for AST to terminal (ANSI) rendering.

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
    clickable_links : {"none", "web", "all"}, default "none"
        Which links the terminal may open on a click (OSC 8 hyperlinks). A
        document is untrusted, and a click hands the target to whatever program
        the operating system registers for its scheme, so by default no link is
        clickable. ``web`` makes ``http`` and ``https`` links clickable. ``all``
        makes every scheme clickable, including ``file:`` and the handlers
        installed applications register (``ms-msdt:``, ``vscode:``, ...), which
        is unsafe for documents you did not write. Whatever the setting, an
        external link's target is shown after its text (shortened in the middle,
        never in the host) unless the text already is the target, so the text of
        ``[bank.example](https://evil.example)`` cannot pass for its target.
    math_mode : {"latex", "unicode"}, default "latex"
        How math is shown. ``latex`` prints the formula's LaTeX source, which
        loses nothing. ``unicode`` writes it with Unicode symbols, superscripts
        and subscripts (``\alpha^2 + x_i`` as ``α² + xᵢ``, ``\frac{a+b}{2}`` as
        ``(a+b)/2``), and lays the rows of display math (``aligned``,
        ``cases``, matrices) out on lines of their own. A character Unicode has
        no superscript or subscript for keeps its ``^`` or ``_``. Needs
        ``pylatexenc`` (the ``latex`` extra); without it, and for a formula
        that does not parse, the LaTeX is shown.
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
    clickable_links: ClickableLinks = field(
        default="none",
        metadata={
            "help": "Links a click in the terminal may open: none, web (http/https) or all schemes (unsafe)",
            "choices": ["none", "web", "all"],
            "importance": "advanced",
        },
    )
    math_mode: TerminalMathMode = field(
        default="latex",
        metadata={
            "help": "Show math as LaTeX source or as Unicode text (unicode needs pylatexenc)",
            "choices": ["latex", "unicode"],
            "importance": "core",
        },
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
