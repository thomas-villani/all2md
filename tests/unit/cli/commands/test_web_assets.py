"""Unit tests for the shared view/serve web-asset helpers."""

from pathlib import Path

import pytest

from all2md.cli.commands.web_assets import (
    ThemeError,
    builtin_theme_names,
    inject_web_assets,
    resolve_theme,
)


@pytest.mark.unit
class TestResolveTheme:
    def test_default_theme_is_minimal(self):
        assert resolve_theme(None, dark=False, config={}).name == "minimal.html"

    def test_dark_default_theme(self):
        assert resolve_theme(None, dark=True, config={}).name == "dark.html"

    def test_builtin_name(self):
        path = resolve_theme("newspaper", dark=False, config={})
        assert path.name == "newspaper.html"
        assert path.is_file()

    def test_builtin_names_exclude_editor(self):
        names = builtin_theme_names()
        assert "minimal" in names
        assert "editor" not in names

    def test_explicit_html_path(self, tmp_path: Path):
        theme = tmp_path / "custom.html"
        theme.write_text("<html><head></head><body>{CONTENT}</body></html>")
        assert resolve_theme(str(theme), dark=False, config={}) == theme

    def test_css_path_is_wrapped_in_shell(self, tmp_path: Path):
        css = tmp_path / "look.css"
        css.write_text("body { background: #abcdef; }")
        result = resolve_theme(str(css), dark=False, config={})
        text = result.read_text(encoding="utf-8")
        assert result.suffix == ".html"
        assert "#abcdef" in text
        assert "{CONTENT}" in text
        assert "{TITLE}" in text

    def test_named_registry_from_config(self, tmp_path: Path):
        theme = tmp_path / "corp.html"
        theme.write_text("<html><head></head><body>{CONTENT}</body></html>")
        path = resolve_theme("corp", dark=False, config={"themes": {"corp": str(theme)}})
        assert path == theme

    def test_registry_missing_file_errors(self, tmp_path: Path):
        with pytest.raises(ThemeError, match="missing file"):
            resolve_theme("corp", dark=False, config={"themes": {"corp": str(tmp_path / "gone.html")}})

    def test_unknown_theme_lists_available(self):
        with pytest.raises(ThemeError) as exc:
            resolve_theme("does-not-exist", dark=False, config={})
        assert "Available built-in themes" in str(exc.value)


@pytest.mark.unit
class TestInjectWebAssets:
    HTML = "<html><head><title>t</title></head><body>x</body></html>"

    def test_injects_both_before_head_close(self):
        out = inject_web_assets(self.HTML)
        assert "mermaid@11" in out
        assert "highlight.min.js" in out
        assert out.index("mermaid@11") < out.index("</head>")
        assert out.index("highlight.min.js") < out.index("</head>")

    def test_dark_switches_highlight_stylesheet(self):
        assert "github-dark.min.css" in inject_web_assets(self.HTML, dark=True)
        assert "github.min.css" in inject_web_assets(self.HTML, dark=False)

    def test_disabling_both_is_a_noop(self):
        assert inject_web_assets(self.HTML, mermaid=False, highlight=False) == self.HTML

    def test_only_mermaid(self):
        out = inject_web_assets(self.HTML, mermaid=True, highlight=False)
        assert "mermaid@11" in out
        assert "highlight.min.js" not in out

    def test_appends_when_no_head_close(self):
        out = inject_web_assets("<body>x</body>", highlight=False)
        assert "mermaid@11" in out
