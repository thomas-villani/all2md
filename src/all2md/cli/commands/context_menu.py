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
from dataclasses import dataclass
from importlib.resources import (  # nosemgrep: python.lang.compatibility.python37.python37-compatibility-importlib2
    as_file,
    files,
)
from pathlib import Path

from all2md.cli.builder import EXIT_ERROR, EXIT_SUCCESS


@dataclass(frozen=True)
class _MenuEntry:
    r"""A single right-click entry installed under the per-user class hive.

    ``scope`` is ``"file"`` (registered under ``*\shell`` and narrowed by an
    ``AppliesTo`` query) or ``"directory"`` (registered under
    ``Directory\shell`` for folders, with no extension filter).
    """

    id: str
    menu_key: str
    text: str
    scope: str  # "file" or "directory"
    arg: str  # "%1" for files, "%V" for directories

    @property
    def command_key(self) -> str:
        return self.menu_key + r"\command"


# All entries this command knows how to install. ``view``/``edit`` apply to
# files (``*\shell``); ``serve`` applies to folders (``Directory\shell``).
_ENTRIES: dict[str, _MenuEntry] = {
    "view": _MenuEntry("view", r"Software\Classes\*\shell\all2mdView", "View with all2md", "file", "%1"),
    "edit": _MenuEntry("edit", r"Software\Classes\*\shell\all2mdEdit", "Edit with all2md", "file", "%1"),
    "serve": _MenuEntry(
        "serve", r"Software\Classes\Directory\shell\all2mdServe", "Serve with all2md", "directory", "%V"
    ),
}

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


def _which_launcher(name: str) -> str | None:
    """Locate a specific launcher executable on PATH or known script dirs."""
    found = shutil.which(name)
    if found:
        return found

    search_dirs = [Path(sys.executable).parent]
    if os.environ.get("UV_TOOL_BIN_DIR"):
        search_dirs.append(Path(os.environ["UV_TOOL_BIN_DIR"]))
    if os.environ.get("USERPROFILE"):
        search_dirs.append(Path(os.environ["USERPROFILE"]) / ".local" / "bin")

    for directory in search_dirs:
        candidate = directory / f"{name}.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def _resolve_launchers() -> dict[str, str]:
    """Return a map of available launcher names to their resolved paths.

    Looks for the console-less ``all2mdw`` GUI launcher (preferred for ``view``)
    and the ``all2md`` console launcher (required for ``edit``/``serve``, which
    host a live local server).
    """
    launchers: dict[str, str] = {}
    for name in ("all2mdw", "all2md"):
        path = _which_launcher(name)
        if path:
            launchers[name] = path
    return launchers


def _build_entry_command(entry: _MenuEntry, launchers: dict[str, str]) -> tuple[str, bool] | None:
    """Build the shell command for an entry.

    Returns ``(command, windowed)`` or None if no suitable launcher exists.
    ``view`` prefers the windowless ``all2mdw``; ``edit``/``serve`` require the
    ``all2md`` console launcher invoked with the matching subcommand.
    """
    all2mdw = launchers.get("all2mdw")
    all2md = launchers.get("all2md")

    if entry.id == "view":
        if all2mdw:
            return f'"{all2mdw}" "{entry.arg}"', True
        if all2md:
            return f'"{all2md}" view "{entry.arg}"', False
        return None

    # edit / serve: explicit subcommand on the console launcher.
    if all2md:
        return f'"{all2md}" {entry.id} "{entry.arg}"', False
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


def _resolve_icon(fallback: str) -> str:
    """Copy the bundled icon to a stable path; fall back to a launcher path."""
    target = _icon_target()
    if target is not None:
        copied = _copy_bundled_icon(target)
        if copied:
            return str(copied)
    return fallback


def _install(selected_ids: list[str], extensions: tuple[str, ...], include_text: bool) -> int:
    """Register the selected context-menu entries. Returns an exit code."""
    import winreg

    launchers = _resolve_launchers()
    if not launchers:
        print(
            "Error: could not find the all2md launcher on PATH.\n"
            "Make sure all2md is installed (e.g. `uv tool install all2md`) and its "
            "scripts directory is on PATH.",
            file=sys.stderr,
        )
        return EXIT_ERROR

    icon_value = _resolve_icon(next(iter(launchers.values())))
    applies_to = _build_applies_to(extensions, include_text)

    installed: list[tuple[_MenuEntry, str]] = []
    used_console_view = False
    for entry_id in selected_ids:
        entry = _ENTRIES[entry_id]
        built = _build_entry_command(entry, launchers)
        if built is None:
            print(
                f"Skipping '{entry.text}': the '{entry.id}' entry needs the 'all2md' console "
                "launcher, which was not found on PATH.",
                file=sys.stderr,
            )
            continue
        command, windowed = built
        if entry.id == "view" and not windowed:
            used_console_view = True

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, entry.menu_key) as menu:
            winreg.SetValueEx(menu, "MUIVerb", 0, winreg.REG_SZ, entry.text)
            winreg.SetValueEx(menu, "Icon", 0, winreg.REG_SZ, icon_value)
            # ``AppliesTo`` only applies to the file-scoped entries; directory
            # entries (serve) appear on every folder.
            if entry.scope == "file":
                winreg.SetValueEx(menu, "AppliesTo", 0, winreg.REG_SZ, applies_to)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, entry.command_key) as cmd:
            winreg.SetValueEx(cmd, "", 0, winreg.REG_SZ, command)
        installed.append((entry, command))

    if not installed:
        print("No context-menu entries were installed.", file=sys.stderr)
        return EXIT_ERROR

    print("Installed context-menu entries:")
    for entry, command in installed:
        scope_note = (
            "folders"
            if entry.scope == "directory"
            else (", ".join("." + e for e in extensions) + (" + all text files" if include_text else ""))
        )
        print(f'  "{entry.text}"  →  {command}')
        print(f"      Shows on: {scope_note}")
    print(f"  Icon: {icon_value}")
    if used_console_view:
        print(
            "\nNote: the console-less 'all2mdw' launcher was not found, so the View entry uses "
            "'all2md view', which opens a console window and waits for Enter. Reinstall all2md "
            "to get 'all2mdw' for a clean, windowless launch.",
            file=sys.stderr,
        )
    print("\nIf the entries don't appear right away, restart Explorer (or sign out and back in).")
    return EXIT_SUCCESS


def _uninstall() -> int:
    """Remove ALL known context-menu entries and the copied icon."""
    import winreg

    removed: list[str] = []
    for entry in _ENTRIES.values():
        entry_removed = False
        for key in (entry.command_key, entry.menu_key):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
                entry_removed = True
            except FileNotFoundError:
                # Subkey already absent — that's the desired end state.
                pass
        if entry_removed:
            removed.append(entry.text)

    target = _icon_target()
    if target is not None and target.exists():
        try:
            target.unlink()
        except OSError:
            # Best-effort cleanup; a leftover icon in %LOCALAPPDATA% is harmless.
            pass

    if removed:
        print("Removed context-menu entries:")
        for text in removed:
            print(f'  "{text}"')
    else:
        print("No all2md context-menu entries were installed.")
    return EXIT_SUCCESS


def _status() -> int:
    """Report which entries are installed and what they point at."""
    import winreg

    any_installed = False
    for entry in _ENTRIES.values():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, entry.menu_key) as menu:
                icon = winreg.QueryValueEx(menu, "Icon")[0]
                try:
                    applies_to = winreg.QueryValueEx(menu, "AppliesTo")[0]
                except FileNotFoundError:
                    applies_to = "(folders)"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, entry.command_key) as cmd:
                command = winreg.QueryValueEx(cmd, "")[0]
        except FileNotFoundError:
            print(f'Not installed: "{entry.text}"')
            continue

        any_installed = True
        print(f'Installed: "{entry.text}"')
        print(f"  Command:   {command}")
        print(f"  Icon:      {icon}")
        print(f"  AppliesTo: {applies_to}")

    if not any_installed:
        print("\nRun: all2md context-menu install [--edit] [--serve] [--all]")
    return EXIT_SUCCESS


def _select_entries(parsed: argparse.Namespace) -> list[str]:
    """Resolve which entry ids to install from the install flags.

    ``view`` is always installed (backward compatible). ``--edit``/``--serve``
    add those entries; ``--all`` installs every entry.
    """
    if parsed.all:
        return list(_ENTRIES.keys())
    selected = ["view"]
    if parsed.edit:
        selected.append("edit")
    if parsed.serve:
        selected.append("serve")
    return selected


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
        description="Manage the Windows right-click all2md entries (per-user, no admin). "
        "Installs a View entry by default; add Edit (files) and Serve (folders) with flags.",
    )
    parser.add_argument(
        "action",
        choices=("install", "uninstall", "status"),
        help="install / uninstall the menu entries, or show their current status",
    )
    parser.add_argument(
        "--edit",
        action="store_true",
        help="Also install an 'Edit with all2md' entry on files (in addition to View).",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Also install a 'Serve with all2md' entry on folders.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Install all entries (View + Edit + Serve).",
    )
    parser.add_argument(
        "--extensions",
        metavar="LIST",
        help="Comma/space separated file extensions the file entries show on "
        "(overrides the built-in default set, e.g. --extensions 'md,pdf,docx').",
    )
    parser.add_argument(
        "--all-text",
        action="store_true",
        help="Also show the file entries on all text files (adds System.Kind:=text).",
    )

    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_ERROR

    if sys.platform != "win32":
        print("The 'context-menu' command is only available on Windows.", file=sys.stderr)
        return EXIT_ERROR

    if parsed.action == "install":
        return _install(_select_entries(parsed), _parse_extensions(parsed.extensions), parsed.all_text)
    if parsed.action == "uninstall":
        return _uninstall()
    return _status()
