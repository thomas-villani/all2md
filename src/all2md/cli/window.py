#  Copyright (c) 2025 Tom Villani, Ph.D.

"""Optional standalone-window support for the ``view`` and ``edit`` commands.

When the optional ``pywebview`` dependency is installed, ``--window`` opens the
local preview/editor in a native OS webview (Edge WebView2 on Windows, WebKit on
macOS, GTK/Qt on Linux) with no address bar or browser chrome, instead of a
regular browser tab. The dependency is import-guarded so the package — and its
test suite — work fine without it; callers use :func:`is_available` to fall back
to ``webbrowser`` when it is missing.

Install with::

    pip install all2md[window]
"""

from __future__ import annotations

from typing import Callable, Optional

INSTALL_HINT = "Standalone-window mode requires 'pywebview'. Install it with: pip install all2md[window]"


def is_available() -> bool:
    """Return ``True`` if pywebview can be imported."""
    try:
        import webview  # noqa: F401
    except ImportError:
        return False
    return True


def open_window(url: str, title: str, *, on_start: Optional[Callable[[], None]] = None) -> None:
    """Open ``url`` in a native window and block until the user closes it.

    Parameters
    ----------
    url : str
        The address to load (an ``http://`` server URL or a ``file://`` URI).
    title : str
        The window title.
    on_start : callable, optional
        Invoked once the GUI event loop is running, on a background thread. Use
        it to start a server thread or otherwise react to the window being ready.

    Raises
    ------
    RuntimeError
        If pywebview is not installed (message points at the install extra).

    """
    try:
        import webview
    except ImportError as exc:  # pragma: no cover - exercised via is_available fallback
        raise RuntimeError(INSTALL_HINT) from exc

    webview.create_window(title, url=url)
    # webview.start() must own the main thread; it returns when the last window
    # is closed. `func` (if given) runs on a worker thread after startup.
    webview.start(func=on_start)
