#  Copyright (c) 2025 Tom Villani, Ph.D.

r"""Windows shell context-menu integration for all2md ("View with all2md").

Registers a per-user right-click entry under ``HKEY_CURRENT_USER`` that invokes
the console-less ``all2mdw`` launcher to open a document in the browser. No
administrator rights are required — only the per-user ``HKCU\Software\Classes``
hive is touched, and uninstalling removes exactly what was added.

The bundled icon is copied to a stable per-user location (``%LOCALAPPDATA%``) so
the registry reference survives uv/pip reinstalls and upgrades that relocate the
installed package.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from importlib.resources import (  # nosemgrep: python.lang.compatibility.python37.python37-compatibility-importlib2
    as_file,
    files,
)
from pathlib import Path

from all2md.cli.builder import EXIT_ERROR, EXIT_SUCCESS

# Per-user registry layout (no admin needed). The leading ``*`` means "all
# files"; ``AppliesTo`` then narrows visibility to the configured extensions.
_MENU_KEY = r"Software\Classes\*\shell\all2mdView"
_COMMAND_KEY = _MENU_KEY + r"\command"
_MENU_TEXT = "View with all2md"

# Default file types the entry appears on — formats all2md renders well in the
# browser preview. Override with ``--extensions``.
_DEFAULT_EXTENSIONS = (
    "md",
    "markdown",
    "rst",
    "txt",
    "docx",
    "pdf",
    "pptx",
    "rtf",
    "odt",
    "odp",
    "html",
    "htm",
    "eml",
    "csv",
    "json",
    "ipynb",
)


def _icon_target() -> Path | None:
    """Stable per-user path the registry icon reference points at."""
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    return Path(local) / "all2md" / "icon.ico"


def _copy_bundled_icon(dest: Path) -> Path | None:
    """Copy the packaged ``assets/icon.ico`` to ``dest``; return it or None.

    Returns None (rather than raising) when the asset isn't present or can't be
    copied, so the menu still installs — just without a custom icon.
    """
    try:
        resource = files("all2md") / "assets" / "icon.ico"
        with as_file(resource) as icon_path:
            if not icon_path.is_file():
                return None
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(icon_path, dest)
        return dest
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return None


def _find_launcher() -> tuple[str, bool] | None:
    """Locate the best available launcher executable.

    Prefers the console-less ``all2mdw`` GUI launcher; falls back to ``all2md``
    (which flashes a console and uses the interactive ``view`` prompt).

    Returns
    -------
    tuple[str, bool] or None
        ``(path, windowed)`` where ``windowed`` is True for ``all2mdw``, or
        None if no launcher could be found.

    """
    search_dirs = [Path(sys.executable).parent]
    if os.environ.get("UV_TOOL_BIN_DIR"):
        search_dirs.append(Path(os.environ["UV_TOOL_BIN_DIR"]))
    if os.environ.get("USERPROFILE"):
        search_dirs.append(Path(os.environ["USERPROFILE"]) / ".local" / "bin")

    for name, windowed in (("all2mdw", True), ("all2md", False)):
        found = shutil.which(name)
        if found:
            return found, windowed
        for directory in search_dirs:
            candidate = directory / f"{name}.exe"
            if candidate.is_file():
                return str(candidate), windowed
    return None


def _parse_extensions(raw: str | None) -> tuple[str, ...]:
    """Normalize a comma/space separated extension list (or the default)."""
    if not raw:
        return _DEFAULT_EXTENSIONS
    parts = re.split(r"[,\s]+", raw.strip())
    return tuple(part.lstrip(".").lower() for part in parts if part)


def _build_applies_to(extensions: tuple[str, ...], include_text: bool) -> str:
    """Build the ``AppliesTo`` query that scopes the menu to certain files."""
    clauses = [f"System.FileExtension:=.{ext}" for ext in extensions]
    if include_text:
        clauses.insert(0, "System.Kind:=text")
    return " OR ".join(clauses)


def _build_command(launcher: str, windowed: bool) -> str:
    """Build the shell command string (``%1`` is the clicked file)."""
    if windowed:
        return f'"{launcher}" "%1"'
    return f'"{launcher}" view "%1"'


def _install(extensions: tuple[str, ...], include_text: bool) -> int:
    """Register the context-menu entry. Returns an exit code."""
    import winreg

    launcher = _find_launcher()
    if launcher is None:
        print(
            "Error: could not find the all2md launcher on PATH.\n"
            "Make sure all2md is installed (e.g. `uv tool install all2md`) and its "
            "scripts directory is on PATH.",
            file=sys.stderr,
        )
        return EXIT_ERROR
    launcher_path, windowed = launcher

    icon_value: str | None = None
    target = _icon_target()
    if target is not None:
        copied = _copy_bundled_icon(target)
        icon_value = str(copied) if copied else None
    if icon_value is None:
        # No bundled icon available — fall back to the launcher's own icon.
        icon_value = launcher_path

    applies_to = _build_applies_to(extensions, include_text)
    command = _build_command(launcher_path, windowed)

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _MENU_KEY) as menu:
        winreg.SetValueEx(menu, "MUIVerb", 0, winreg.REG_SZ, _MENU_TEXT)
        winreg.SetValueEx(menu, "Icon", 0, winreg.REG_SZ, icon_value)
        winreg.SetValueEx(menu, "AppliesTo", 0, winreg.REG_SZ, applies_to)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _COMMAND_KEY) as cmd:
        winreg.SetValueEx(cmd, "", 0, winreg.REG_SZ, command)

    print(f'Installed context-menu entry: "{_MENU_TEXT}"')
    print(f"  Launcher: {launcher_path}")
    print(f"  Icon:     {icon_value}")
    print(f"  Shows on: {', '.join('.' + e for e in extensions)}" + (" + all text files" if include_text else ""))
    if not windowed:
        print(
            "\nNote: the console-less 'all2mdw' launcher was not found, so the entry uses "
            "'all2md view', which opens a console window and waits for Enter. Reinstall all2md "
            "to get 'all2mdw' for a clean, windowless launch.",
            file=sys.stderr,
        )
    print("\nIf the entry doesn't appear right away, restart Explorer (or sign out and back in).")
    return EXIT_SUCCESS


def _uninstall() -> int:
    """Remove the context-menu entry and the copied icon. Returns an exit code."""
    import winreg

    removed = False
    for key in (_COMMAND_KEY, _MENU_KEY):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
            removed = True
        except FileNotFoundError:
            pass

    target = _icon_target()
    if target is not None and target.exists():
        try:
            target.unlink()
        except OSError:
            pass

    if removed:
        print(f'Removed context-menu entry: "{_MENU_TEXT}"')
    else:
        print(f'Context-menu entry not found: "{_MENU_TEXT}"')
    return EXIT_SUCCESS


def _status() -> int:
    """Report whether the entry is installed and what it points at."""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _MENU_KEY) as menu:
            applies_to = winreg.QueryValueEx(menu, "AppliesTo")[0]
            icon = winreg.QueryValueEx(menu, "Icon")[0]
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _COMMAND_KEY) as cmd:
            command = winreg.QueryValueEx(cmd, "")[0]
    except FileNotFoundError:
        print(f'Not installed: "{_MENU_TEXT}"')
        print("Run: all2md context-menu install")
        return EXIT_SUCCESS

    print(f'Installed: "{_MENU_TEXT}"')
    print(f"  Command:   {command}")
    print(f"  Icon:      {icon}")
    print(f"  AppliesTo: {applies_to}")
    return EXIT_SUCCESS


def handle_context_menu_command(args: list[str] | None = None) -> int:
    """Handle the ``context-menu`` command (Windows shell integration).

    Parameters
    ----------
    args : list[str], optional
        Command line arguments after ``context-menu``.

    Returns
    -------
    int
        Exit code.

    """
    parser = argparse.ArgumentParser(
        prog="all2md context-menu",
        description='Manage the Windows right-click "View with all2md" entry (per-user, no admin).',
    )
    parser.add_argument(
        "action",
        choices=("install", "uninstall", "status"),
        help="install / uninstall the menu entry, or show its current status",
    )
    parser.add_argument(
        "--extensions",
        metavar="LIST",
        help="Comma/space separated file extensions the entry shows on "
        "(overrides the built-in default set, e.g. --extensions 'md,pdf,docx').",
    )
    parser.add_argument(
        "--all-text",
        action="store_true",
        help="Also show the entry on all text files (adds System.Kind:=text).",
    )

    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_ERROR

    if sys.platform != "win32":
        print("The 'context-menu' command is only available on Windows.", file=sys.stderr)
        return EXIT_ERROR

    if parsed.action == "install":
        return _install(_parse_extensions(parsed.extensions), parsed.all_text)
    if parsed.action == "uninstall":
        return _uninstall()
    return _status()
