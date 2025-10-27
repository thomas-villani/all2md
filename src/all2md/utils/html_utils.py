"""HTML-related utility helpers."""

from __future__ import annotations

from html import escape as _html_escape
from typing import TYPE_CHECKING, Literal

from all2md.utils.html_sanitizer import sanitize_html_content

if TYPE_CHECKING:
    pass

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
    """Render math content as HTML wrapper with notation metadata.

    Parameters
    ----------
    content : str
        Math content to render
    notation : MathNotation
        Format of the math content ("latex", "mathml", or "html")
    inline : bool
        If True, render as inline math (span), otherwise block math (div)
    escape_enabled : bool, default True
        If True, escape HTML special characters in content to prevent XSS.
        When notation="html", this should generally be True unless you are
        certain the content comes from a trusted source.

    Returns
    -------
    str
        HTML string with math content wrapped in appropriate tags

    Warning
    -------
    When using notation="html" with escape_enabled=False, you must ensure
    that the content comes from a trusted source to prevent XSS attacks.

    """
    tag = "span" if inline else "div"
    classes = "math math-inline" if inline else "math math-block"
    data_attr = f' data-notation="{notation}"'

    if notation == "latex":
        escaped = escape_html(content, enabled=escape_enabled)
        inner = f"${escaped}$" if inline else f"$$\n{escaped}\n$$"
    elif notation == "mathml":
        # MathML content must be sanitized to prevent XSS when escape_enabled=True
        if escape_enabled:
            # Sanitize MathML to remove dangerous elements/attributes
            inner = sanitize_html_content(content, mode="sanitize")
            # If content doesn't look like MathML after sanitization, wrap it
            stripped = inner.strip()
            if not stripped.startswith("<"):
                inner = f"<math>{escape_html(stripped, enabled=True)}</math>"
        else:
            # When escaping is disabled, preserve content as-is (trusted source)
            stripped = content.strip()
            inner = stripped if stripped.startswith("<") else f"<math>{content}</math>"
    else:  # notation == "html"
        # Apply escaping to HTML notation to prevent XSS
        inner = escape_html(content, enabled=escape_enabled)

    if inline:
        return f'<{tag} class="{classes}"{data_attr}>{inner}</{tag}>'

    return f'<{tag} class="{classes}"{data_attr}>\n{inner}\n</{tag}>'


__all__ = ["escape_html", "render_math_html", "MathNotation"]
