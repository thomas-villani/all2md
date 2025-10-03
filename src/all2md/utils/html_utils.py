"""HTML-related utility helpers."""

from __future__ import annotations

from html import escape as _html_escape
from typing import Literal


MathNotation = Literal["latex", "mathml", "html"]


def escape_html(text: str, *, enabled: bool = True) -> str:
    """Escape HTML special characters when enabled."""
    if not enabled:
        return text
    return _html_escape(text)


def render_math_html(
    content: str,
    notation: MathNotation,
    *,
    inline: bool,
    escape_enabled: bool = True,
) -> str:
    """Render math content as HTML wrapper with notation metadata."""
    tag = "span" if inline else "div"
    classes = "math math-inline" if inline else "math math-block"
    data_attr = f' data-notation="{notation}"'

    if notation == "latex":
        escaped = escape_html(content, enabled=escape_enabled)
        inner = f"${escaped}$" if inline else f"$$\n{escaped}\n$$"
    elif notation == "mathml":
        stripped = content.strip()
        inner = stripped if stripped.startswith("<") else f"<math>{content}</math>"
    else:
        inner = content

    if inline:
        return f'<{tag} class="{classes}"{data_attr}>{inner}</{tag}>'

    return f'<{tag} class="{classes}"{data_attr}>\n{inner}\n</{tag}>'


__all__ = ["escape_html", "render_math_html", "MathNotation"]
