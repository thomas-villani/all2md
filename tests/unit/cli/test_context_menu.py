"""Unit tests for the Windows context-menu integration and the all2mdw launcher."""

from __future__ import annotations

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


def test_build_command() -> None:
    assert context_menu._build_command(r"C:\bin\all2mdw.exe", windowed=True) == r'"C:\bin\all2mdw.exe" "%1"'
    assert context_menu._build_command(r"C:\bin\all2md.exe", windowed=False) == r'"C:\bin\all2md.exe" view "%1"'


def test_find_launcher_prefers_windowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_which(name: str) -> str | None:
        return rf"C:\bin\{name}.exe" if name == "all2mdw" else None

    monkeypatch.setattr(context_menu.shutil, "which", fake_which)
    result = context_menu._find_launcher()
    assert result == (r"C:\bin\all2mdw.exe", True)


def test_find_launcher_falls_back_to_console(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_which(name: str) -> str | None:
        return rf"C:\bin\{name}.exe" if name == "all2md" else None

    monkeypatch.setattr(context_menu.shutil, "which", fake_which)
    # Neutralize the directory scan so only `which` can resolve a launcher
    # (otherwise the real all2mdw.exe in this dev env would be found first).
    monkeypatch.setattr(context_menu.sys, "executable", str(tmp_path / "python.exe"))
    monkeypatch.delenv("UV_TOOL_BIN_DIR", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    result = context_menu._find_launcher()
    assert result == (r"C:\bin\all2md.exe", False)


def test_find_launcher_none_when_absent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(context_menu.shutil, "which", lambda name: None)
    # Point the interpreter dir at an empty tmp dir and clear install-location envs.
    monkeypatch.setattr(context_menu.sys, "executable", str(tmp_path / "python.exe"))
    monkeypatch.delenv("UV_TOOL_BIN_DIR", raising=False)
    monkeypatch.delenv("USERPROFILE", raising=False)
    assert context_menu._find_launcher() is None


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

    # Never clobber a real, pre-existing user entry.
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, context_menu._MENU_KEY):
            pytest.skip("context-menu entry already installed; skipping to avoid clobbering it")
    except FileNotFoundError:
        pass

    fake_launcher = tmp_path / "all2mdw.exe"
    fake_launcher.write_bytes(b"")
    monkeypatch.setattr(context_menu, "_find_launcher", lambda: (str(fake_launcher), True))
    # Keep the copied icon out of the real LOCALAPPDATA.
    monkeypatch.setattr(context_menu, "_icon_target", lambda: tmp_path / "icon.ico")

    try:
        assert context_menu._install(("md", "pdf"), include_text=False) == 0
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, context_menu._COMMAND_KEY) as cmd:
            command = winreg.QueryValueEx(cmd, "")[0]
        assert command == f'"{fake_launcher}" "%1"'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, context_menu._MENU_KEY) as menu:
            applies_to = winreg.QueryValueEx(menu, "AppliesTo")[0]
        assert "System.FileExtension:=.md" in applies_to
    finally:
        context_menu._uninstall()

    with pytest.raises(FileNotFoundError):
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, context_menu._MENU_KEY)
