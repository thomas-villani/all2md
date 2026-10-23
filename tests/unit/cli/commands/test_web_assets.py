"""Unit tests for the shared view/serve web-asset helpers."""

from pathlib import Path

import pytest

from all2md.cli.commands.web_assets import (
    ThemeError,
    builtin_theme_names,
    inject_web_assets,
    inline_local_images,
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

    def test_math_is_typeset_only_when_the_page_has_latex(self):
        math = '<html><head></head><body><span class="math math-inline" data-notation="latex">$x$</span></body></html>'
        out = inject_web_assets(math, mermaid=False, highlight=False)
        assert "katex.min.js" in out
        assert out.index("katex.min.js") < out.index("</head>")
        assert "katex" not in inject_web_assets(self.HTML, mermaid=False, highlight=False)
        assert "katex" not in inject_web_assets(math, mermaid=False, highlight=False, math=False)


PNG = bytes.fromhex("89504e470d0a1a0a")


def _image_doc(*urls: str):
    from all2md.ast import Document, Image, Paragraph

    return Document(children=[Paragraph(content=[Image(url=url, alt_text="a") for url in urls])])


def _urls(doc) -> list[str]:
    return [image.url for image in doc.children[0].content]


@pytest.mark.unit
class TestInlineLocalImages:
    def test_relative_paths_resolve_against_the_source_folder(self, tmp_path: Path):
        (tmp_path / "img").mkdir()
        (tmp_path / "img" / "a b.png").write_bytes(PNG)
        doc = _image_doc("img/a b.png", "img/a%20b.png")
        assert inline_local_images(doc, tmp_path) == 2
        assert _urls(doc) == ["data:image/png;base64,iVBORw0KGgo="] * 2

    def test_absolute_paths_and_file_urls(self, tmp_path: Path):
        image = tmp_path / "a.png"
        image.write_bytes(PNG)
        doc = _image_doc(str(image), image.as_uri())
        assert inline_local_images(doc, Path("elsewhere")) == 2

    def test_remote_inline_missing_and_non_images_are_left_alone(self, tmp_path: Path):
        (tmp_path / "notes.txt").write_text("x")
        urls = ["https://example.com/a.png", "data:image/png;base64,AAAA", "missing.png", "notes.txt", "#anchor", ""]
        doc = _image_doc(*urls)
        assert inline_local_images(doc, tmp_path) == 0
        assert _urls(doc) == urls
