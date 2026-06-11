#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Console-less ``view`` launcher for the Windows context-menu integration.

Registered as the ``all2mdw`` GUI entry point (built with the ``pythonw``
launcher, so no console window appears). It renders a document to a temporary
HTML file, opens it in the default browser, and exits immediately — unlike
``all2md view``, which is interactive and waits at the terminal before cleaning
up its temp file. This is the command wired into the right-click
"View with all2md" shell entry; see ``all2md context-menu``.

Because there is no console, failures are surfaced via a native message box
rather than printed to a (nonexistent) stderr.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import webbrowser
from pathlib import Path

# Temp preview files are tagged so we can reap stale ones from earlier launches.
_TEMP_PREFIX = "all2md-view-"
_STALE_SECONDS = 3600


def _error_dialog(message: str) -> None:
    """Surface an error to the user without a console (best-effort).

    On Windows we pop a native message box; everywhere else (and if the box
    fails) we fall back to stderr.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, message, "all2md", 0x10)  # MB_ICONERROR
            return
        except Exception:  # noqa: BLE001 - fall through to stderr
            pass
    print(message, file=sys.stderr)


def _cleanup_stale_previews(now: float) -> None:
    """Best-effort removal of leftover preview files from earlier launches.

    The fire-and-forget design can't delete its own temp file on exit (the
    browser may still be loading it), so each launch sweeps previews older than
    an hour to keep the temp directory tidy.
    """
    temp_dir = Path(tempfile.gettempdir())
    try:
        candidates = list(temp_dir.glob(f"{_TEMP_PREFIX}*.html"))
    except OSError:
        return
    for path in candidates:
        try:
            if now - path.stat().st_mtime > _STALE_SECONDS:
                path.unlink()
        except OSError:
            pass  # In use or already gone — ignore.


def _render_html(input_path: Path) -> str:
    """Convert the document to standalone HTML using the minimal view theme."""
    from all2md import HtmlRendererOptions, from_ast, to_ast

    theme_path = Path(__file__).parent / "commands" / "themes" / "minimal.html"

    doc = to_ast(str(input_path))
    doc.metadata["title"] = f"{input_path.name} - all2md Web Preview"
    options = HtmlRendererOptions(
        template_mode="replace",
        template_file=str(theme_path),
        include_toc=False,
        external_links_new_tab=True,
    )
    result = from_ast(doc, "html", renderer_options=options)
    if not isinstance(result, str):
        raise RuntimeError("Expected string result from HTML rendering")
    return result


def main(argv: list[str] | None = None) -> int:
    """Render the given file to HTML, open it in the browser, and exit.

    Parameters
    ----------
    argv : list[str], optional
        Arguments after the program name (defaults to ``sys.argv[1:]``). The
        first element is the path of the document to view.

    Returns
    -------
    int
        Process exit code (0 on success).

    """
    args = sys.argv[1:] if argv is None else argv
    if not args:
        _error_dialog("Usage: all2mdw <file>\n\nOpens a document in your browser via all2md.")
        return 2

    input_path = Path(args[0])
    if not input_path.exists():
        _error_dialog(f"File not found:\n{input_path}")
        return 1

    try:
        html = _render_html(input_path)
    except Exception as exc:  # noqa: BLE001 - surface any conversion failure to the user
        _error_dialog(f"Could not convert:\n{input_path}\n\n{exc}")
        return 1

    _cleanup_stale_previews(time.time())

    fd, temp_name = tempfile.mkstemp(suffix=".html", prefix=_TEMP_PREFIX)
    try:
        os.write(fd, html.encode("utf-8"))
    finally:
        os.close(fd)

    webbrowser.open(Path(temp_name).resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
