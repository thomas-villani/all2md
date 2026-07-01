#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Shared browser-viewing helpers for the ``view`` and ``serve`` commands.

Both commands render documents with ``HtmlRendererOptions(template_mode="replace")``,
so the page ``<head>`` comes entirely from a theme file and the renderer never injects
scripts. This module centralises two concerns that both commands need:

* :func:`resolve_theme` -- turn a ``--theme`` argument (built-in name, custom ``.html``
  template, plain ``.css`` file, or a name registered in the config ``[themes]`` table)
  into a concrete template file path.
* :func:`inject_web_assets` -- splice the client-side mermaid.js and highlight.js CDN
  includes into a rendered HTML page so diagrams draw and code blocks are highlighted.
"""

from __future__ import annotations

import atexit
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

# Directory holding the packaged built-in theme templates.
_THEMES_DIR = Path(__file__).parent / "themes"

# ``editor.html`` backs the ``edit`` command, not a ``--theme`` choice, so it is not a
# user-selectable theme name.
_NON_THEME_STEMS = frozenset({"editor"})

# CDN endpoints (pinned to major versions). mermaid was requested explicitly; highlight.js
# uses the official browser build published via jsDelivr's GitHub mirror.
_MERMAID_ESM = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"
_HLJS_BASE = "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build"

# Minimal HTML shell used to wrap a plain ``.css`` theme into a valid replace-mode
# template. ``{TITLE}``/``{CONTENT}`` mirror the placeholders the built-in themes expose.
_CSS_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta content="width=device-width, initial-scale=1.0" name="viewport">
    <title>{{TITLE}}</title>
    <style>
{css}
    </style>
</head>
<body>
{{CONTENT}}
</body>
</html>
"""


class ThemeError(Exception):
    """Raised when a ``--theme`` argument cannot be resolved to a template."""


def builtin_theme_names() -> list[str]:
    """Return the sorted names of the packaged built-in themes."""
    return sorted(p.stem for p in _THEMES_DIR.glob("*.html") if p.stem not in _NON_THEME_STEMS)


def _write_temp_template(text: str) -> Path:
    """Write ``text`` to a temp ``.html`` file, scheduling it for cleanup at exit."""
    fd, name = tempfile.mkstemp(suffix=".html", prefix="all2md-theme-")
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)
    path = Path(name)
    atexit.register(lambda: path.unlink(missing_ok=True))
    return path


def _template_from_file(path: Path) -> Path:
    """Turn a concrete theme file into a replace-mode template path.

    ``.html`` files are used as-is; ``.css`` files are wrapped in :data:`_CSS_SHELL`.
    """
    suffix = path.suffix.lower()
    if suffix == ".html":
        return path
    if suffix == ".css":
        css = path.read_text(encoding="utf-8")
        return _write_temp_template(_CSS_SHELL.format(css=css))
    raise ThemeError(f"Unsupported theme file type: {path} (expected .html or .css)")


def resolve_theme(
    theme_arg: str | None,
    *,
    dark: bool,
    config: Mapping[str, Any] | None = None,
) -> Path:
    """Resolve a ``--theme`` argument to a replace-mode template file path.

    Resolution order for a given ``theme_arg``:

    1. an existing ``.html`` file path -> used directly;
    2. an existing ``.css`` file path -> wrapped in a minimal HTML shell;
    3. a name registered in the config ``[themes]`` table -> its ``.html``/``.css`` file;
    4. a built-in theme name -> ``themes/{name}.html``.

    When ``theme_arg`` is ``None`` the ``dark`` built-in is used if ``dark`` is set,
    otherwise ``minimal``.

    Raises
    ------
    ThemeError
        If the theme cannot be resolved (message lists the available names).

    """
    registered: Mapping[str, Any] = {}
    if config:
        maybe = config.get("themes")
        if isinstance(maybe, Mapping):
            registered = maybe

    if not theme_arg:
        name = "dark" if dark else "minimal"
        return _THEMES_DIR / f"{name}.html"

    # 1 & 2: a direct path to an existing theme file.
    candidate = Path(theme_arg)
    if candidate.is_file() and candidate.suffix.lower() in (".html", ".css"):
        return _template_from_file(candidate)

    # 3: a name registered in the config [themes] table.
    if theme_arg in registered:
        mapped = Path(str(registered[theme_arg])).expanduser()
        if not mapped.is_file():
            raise ThemeError(f"Configured theme {theme_arg!r} points to a missing file: {mapped}")
        return _template_from_file(mapped)

    # 4: a packaged built-in theme name.
    builtin = _THEMES_DIR / f"{theme_arg}.html"
    if builtin.is_file():
        return builtin

    available = builtin_theme_names()
    msg = f"Theme not found: {theme_arg}\nAvailable built-in themes: {', '.join(available)}"
    if registered:
        msg += f"\nConfigured themes: {', '.join(sorted(registered))}"
    raise ThemeError(msg)


def _highlight_block(dark: bool) -> str:
    """Return the highlight.js ``<link>``/``<script>`` include block."""
    style = "github-dark" if dark else "github"
    return (
        f'<link rel="stylesheet" href="{_HLJS_BASE}/styles/{style}.min.css">\n'
        f'<script src="{_HLJS_BASE}/highlight.min.js"></script>\n'
        "<script>window.addEventListener('DOMContentLoaded',function(){"
        "if(window.hljs){window.hljs.highlightAll();}});</script>\n"
    )


def _mermaid_block(dark: bool) -> str:
    """Return the mermaid.js ESM ``<script>`` include block."""
    theme = "dark" if dark else "default"
    return (
        '<script type="module">'
        f"import mermaid from '{_MERMAID_ESM}';"
        f"mermaid.initialize({{startOnLoad:true,theme:'{theme}'}});"
        "</script>\n"
    )


def inject_web_assets(
    html: str,
    *,
    mermaid: bool = True,
    highlight: bool = True,
    dark: bool = False,
) -> str:
    """Splice mermaid.js / highlight.js CDN includes into a rendered HTML page.

    The assets are inserted immediately before ``</head>`` (appended if there is no
    ``</head>``). highlight.js only targets ``<pre><code>`` elements, so it leaves the
    ``<pre class="mermaid">`` diagram blocks untouched. If the CDN is unreachable the
    page degrades gracefully: diagrams stay as readable text and code stays unhighlighted.
    """
    block = ""
    if highlight:
        block += _highlight_block(dark)
    if mermaid:
        block += _mermaid_block(dark)
    if not block:
        return html

    marker = "</head>"
    idx = html.lower().find(marker)
    if idx == -1:
        return html + "\n" + block
    return html[:idx] + block + html[idx:]
