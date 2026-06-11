"""Unit tests for the Windows context-menu integration and the all2mdw launcher."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

from all2md.cli import viewer_launch
from all2md.cli.commands import context_menu

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# Pure helpers (cross-platform)                                               #
# --------------------------------------------------------------------------- #


def test_parse_extensions_default() -> None:
    assert context_menu._parse_extensions(None) == context_menu._DEFAULT_EXTENSIONS
    assert context_menu._parse_extensions("") == context_menu._DEFAULT_EXTENSIONS


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("md,pdf,docx", ("md", "pdf", "docx")),
        (".MD, .PDF", ("md", "pdf")),
        ("md pdf\tdocx", ("md", "pdf", "docx")),
        ("  md ,, pdf ", ("md", "pdf")),
    ],
)
def test_parse_extensions_custom(raw: str, expected: tuple[str, ...]) -> None:
    assert context_menu._parse_extensions(raw) == expected


def test_build_applies_to() -> None:
    assert context_menu._build_applies_to(("md", "pdf"), include_text=False) == (
        "System.FileExtension:=.md OR System.FileExtension:=.pdf"
    )
    with_text = context_menu._build_applies_to(("md",), include_text=True)
    assert with_text.startswith("System.Kind:=text OR ")
    assert with_text.endswith("System.FileExtension:=.md")


def test_build_entry_command_view_prefers_windowed() -> None:
    launchers = {"all2mdw": r"C:\bin\all2mdw.exe", "all2md": r"C:\bin\all2md.exe"}
    built = context_menu._build_entry_command(context_menu._ENTRIES["view"], launchers)
    assert built == (r'"C:\bin\all2mdw.exe" "%1"', True)


def test_build_entry_command_view_console_fallback() -> None:
    launchers = {"all2md": r"C:\bin\all2md.exe"}
    built = context_menu._build_entry_command(context_menu._ENTRIES["view"], launchers)
    assert built == (r'"C:\bin\all2md.exe" view "%1"', False)


def test_build_entry_command_edit_and_serve_use_console() -> None:
    launchers = {"all2mdw": r"C:\bin\all2mdw.exe", "all2md": r"C:\bin\all2md.exe"}
    edit = context_menu._build_entry_command(context_menu._ENTRIES["edit"], launchers)
    assert edit == (r'"C:\bin\all2md.exe" edit "%1"', False)
    serve = context_menu._build_entry_command(context_menu._ENTRIES["serve"], launchers)
    assert serve == (r'"C:\bin\all2md.exe" serve "%V"', False)


def test_build_entry_command_edit_requires_console() -> None:
    # Only the windowed launcher is present → edit/serve cannot be built.
    launchers = {"all2mdw": r"C:\bin\all2mdw.exe"}
    assert context_menu._build_entry_command(context_menu._ENTRIES["edit"], launchers) is None


def test_select_entries_default() -> None:
    ns = argparse.Namespace(edit=False, serve=False, all=False)
    assert context_menu._select_entries(ns) == ["view"]


def test_select_entries_flags() -> None:
    ns = argparse.Namespace(edit=True, serve=True, all=False)
    assert context_menu._select_entries(ns) == ["view", "edit", "serve"]


def test_select_entries_all() -> None:
    ns = argparse.Namespace(edit=False, serve=False, all=True)
    assert context_menu._select_entries(ns) == ["view", "edit", "serve"]


def test_which_launcher_uses_which(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(context_menu.shutil, "which", lambda name: rf"C:\bin\{name}.exe" if name == "all2mdw" else None)
    assert context_menu._which_launcher("all2mdw") == r"C:\bin\all2mdw.exe"


def test_which_launcher_none_when_absent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(context_menu.shutil, "which", lambda name: None)
    # Point the interpreter dir at an empty tmp dir and clear install-location envs.
    monkeypatch.setattr(context_menu.sys, "executable", str(tmp_path / "python.exe"))
    monkeypatch.delenv("UV_TOOL_BIN_DIR", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    assert context_menu._which_launcher("all2mdw") is None


def test_non_windows_returns_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(context_menu.sys, "platform", "linux")
    rc = context_menu.handle_context_menu_command(["status"])
    assert rc != 0
    assert "only available on Windows" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# viewer_launch (console-less viewer)                                          #
# --------------------------------------------------------------------------- #


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    path = tmp_path / "sample.md"
    path.write_text("# Title\n\nThis is **bold** and a [link](https://example.com).\n", encoding="utf-8")
    return path


def test_render_html_contains_formatting(sample_md: Path) -> None:
    html = viewer_launch._render_html(sample_md)
    assert "<h1" in html
    assert "<strong>" in html
    assert "<a " in html


def test_main_opens_browser(monkeypatch: pytest.MonkeyPatch, sample_md: Path) -> None:
    opened: dict[str, str] = {}
    monkeypatch.setattr(viewer_launch.webbrowser, "open", lambda url: opened.setdefault("url", url) or True)
    rc = viewer_launch.main([str(sample_md)])
    assert rc == 0
    assert opened["url"].startswith("file:")
    assert opened["url"].endswith(".html")


def test_main_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    errors: list[str] = []
    monkeypatch.setattr(viewer_launch, "_error_dialog", lambda msg: errors.append(msg))
    rc = viewer_launch.main([str(tmp_path / "nope.md")])
    assert rc == 1
    assert errors and "not found" in errors[0].lower()


def test_main_no_args(monkeypatch: pytest.MonkeyPatch) -> None:
    errors: list[str] = []
    monkeypatch.setattr(viewer_launch, "_error_dialog", lambda msg: errors.append(msg))
    rc = viewer_launch.main([])
    assert rc == 2
    assert errors


def test_cleanup_stale_previews(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(viewer_launch.tempfile, "gettempdir", lambda: str(tmp_path))
    stale = tmp_path / f"{viewer_launch._TEMP_PREFIX}old.html"
    fresh = tmp_path / f"{viewer_launch._TEMP_PREFIX}new.html"
    stale.write_text("x", encoding="utf-8")
    fresh.write_text("x", encoding="utf-8")
    import os

    now = 1_000_000.0
    os.utime(stale, (now - viewer_launch._STALE_SECONDS - 10, now - viewer_launch._STALE_SECONDS - 10))
    os.utime(fresh, (now - 10, now - 10))
    viewer_launch._cleanup_stale_previews(now)
    assert not stale.exists()
    assert fresh.exists()


# --------------------------------------------------------------------------- #
# Registry round-trip (Windows only)                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(sys.platform != "win32", reason="registry integration is Windows-only")
def test_registry_round_trip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import winreg

    view_entry = context_menu._ENTRIES["view"]
    serve_entry = context_menu._ENTRIES["serve"]

    # Never clobber a real, pre-existing user entry.
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, view_entry.menu_key):
            pytest.skip("context-menu entry already installed; skipping to avoid clobbering it")
    except FileNotFoundError:
        pass

    fake_w = tmp_path / "all2mdw.exe"
    fake_w.write_bytes(b"")
    fake_c = tmp_path / "all2md.exe"
    fake_c.write_bytes(b"")
    monkeypatch.setattr(context_menu, "_resolve_launchers", lambda: {"all2mdw": str(fake_w), "all2md": str(fake_c)})
    # Keep the copied icon out of the real LOCALAPPDATA.
    monkeypatch.setattr(context_menu, "_icon_target", lambda: tmp_path / "icon.ico")

    try:
        assert context_menu._install(["view", "serve"], ("md", "pdf"), include_text=False) == 0
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, view_entry.command_key) as cmd:
            command = winreg.QueryValueEx(cmd, "")[0]
        assert command == f'"{fake_w}" "%1"'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, view_entry.menu_key) as menu:
            applies_to = winreg.QueryValueEx(menu, "AppliesTo")[0]
        assert "System.FileExtension:=.md" in applies_to
        # The serve entry is a directory entry with a folder command and no AppliesTo.
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, serve_entry.command_key) as cmd:
            serve_command = winreg.QueryValueEx(cmd, "")[0]
        assert serve_command == f'"{fake_c}" serve "%V"'
    finally:
        context_menu._uninstall()

    for entry in (view_entry, serve_entry):
        with pytest.raises(FileNotFoundError):
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, entry.menu_key)
