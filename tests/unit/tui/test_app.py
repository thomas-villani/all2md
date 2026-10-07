"""The viewer driven headlessly through Wijjit's harness.

Skipped where Wijjit is not installed (the ``tui`` extra; Python 3.11+).
"""

from __future__ import annotations

import pytest

pytest.importorskip("wijjit")

from wijjit.testing import WijjitHarness  # noqa: E402

from all2md import to_ast  # noqa: E402
from all2md.options.terminal import TerminalRendererOptions  # noqa: E402
from all2md.tui.app import Viewer, _key_name  # noqa: E402
from all2md.tui.keys import Action  # noqa: E402
from all2md.tui.layout import DocumentLayout  # noqa: E402

NL = chr(10)
SOURCE = (
    "# Title"
    + NL * 2
    + "Intro with [a jump](#second) and [web](https://example.com/page) and a note[^1]."
    + NL * 2
    + ("filler words " * 40 + NL * 2) * 3
    + "## First"
    + NL * 2
    + ("alpha " * 60 + NL * 2) * 3
    + "## Second"
    + NL * 2
    + "beta text"
    + NL * 2
    + "[^1]: The note."
    + NL
)


def viewer(source: str = SOURCE, **kwargs) -> Viewer:
    doc = to_ast(source.encode(), source_format="markdown")
    return Viewer(DocumentLayout(doc, TerminalRendererOptions(color_system="none")), "doc.md", **kwargs)


@pytest.fixture
def harness():
    opened = []

    def start(v: Viewer, size=(100, 24)) -> WijjitHarness:
        h = WijjitHarness(v.app, size=size).start()
        opened.append(h)
        h.settle()
        return h

    yield start
    for h in opened:
        h.close()


def status(h: WijjitHarness) -> str:
    return h.lines()[-1]


def top(v: Viewer) -> int:
    return v._viewport()[0]


def locate(h: WijjitHarness, text: str) -> tuple[int, int]:
    for y, line in enumerate(h.lines()):
        x = line.find(text)
        if x >= 0:
            return x, y
    raise AssertionError(f"{text!r} not on screen")


@pytest.mark.unit
class TestLayout:
    def test_opens_with_body_outline_and_status(self, harness):
        v = viewer()
        h = harness(v)
        h.assert_no_errors()
        screen = h.screen()
        assert "Outline" in screen and "doc.md" in screen
        assert "Intro with a jump and web" in screen
        assert "Title" in status(h) and "1-" in status(h)

    def test_outline_toggles(self, harness):
        v = viewer()
        h = harness(v)
        width = v.width
        h.press("o").settle()
        assert "Outline" not in h.screen()
        assert v.width > width
        h.press("o").settle()
        assert "Outline" in h.screen()

    def test_no_outline_when_asked_or_without_headings(self, harness):
        assert "Outline" not in harness(viewer(outline=False)).screen()
        assert "Outline" not in harness(viewer("just text" + NL)).screen()

    def test_help_lists_the_keys(self, harness):
        v = viewer()
        h = harness(v)
        h.press("?").settle()
        screen = h.screen()
        assert "Keys" in screen and "PgDn, Space" in screen and "Scroll down a page" in screen


@pytest.mark.unit
class TestScrolling:
    def test_page_and_line(self, harness):
        v = viewer()
        h = harness(v)
        h.press("pagedown").settle()
        page = top(v)
        assert page > 1
        h.press("up").settle()
        assert top(v) == page - 1

    def test_headings(self, harness):
        v = viewer()
        h = harness(v)
        h.press("]").settle()
        assert top(v) == v.layout.heading_line(1, v.width)
        assert "First" in status(h)
        h.press("[").settle()
        assert top(v) == 0

    def test_vim_preset(self, harness):
        v = viewer(preset="vim")
        h = harness(v)
        h.press("G").settle()
        bottom = top(v)
        assert bottom > 0
        h.press("g").settle()
        assert top(v) == 0
        h.press("j").settle()
        assert top(v) == 1

    def test_default_preset_ignores_vim_keys(self, harness):
        v = viewer()
        h = harness(v)
        h.press("G").settle()
        assert top(v) == 0

    def test_outline_selection_jumps(self, harness):
        v = viewer()
        h = harness(v)
        x, y = locate(h, "Second")
        h.click(x, y).settle()
        h.press("enter").settle()
        assert top(v) == min(v.layout.heading_line(2, v.width), v._body().scroll_manager.state.max_scroll)

    def test_resize_keeps_the_section(self, harness):
        v = viewer()
        h = harness(v)
        h.press("]").settle()
        assert "First" in status(h)
        h.resize(60, 24).settle()
        h.assert_no_errors()
        assert top(v) == v.layout.heading_line(1, v.width)
        assert "First" in status(h)


@pytest.mark.unit
class TestLinks:
    def test_click_on_a_fragment_link_jumps_and_back_returns(self, harness):
        v = viewer()
        h = harness(v)
        x, y = locate(h, "a jump")
        h.click(x + 1, y).settle()
        assert top(v) == min(v.layout.heading_line(2, v.width), v._body().scroll_manager.state.max_scroll)
        assert "a jump" in status(h)
        h.press("left").settle()
        assert top(v) == 0
        h.press("right").settle()
        assert top(v) > 0

    def test_footnote_reference_jumps_to_the_note(self, harness):
        v = viewer()
        h = harness(v)
        x, y = locate(h, "[1]")
        h.click(x + 1, y).settle()
        assert "[1] The note." in h.screen()

    def test_external_link_is_shown_not_opened(self, harness, monkeypatch):
        import webbrowser

        opened = []
        monkeypatch.setattr(webbrowser, "open", lambda *a, **k: opened.append(a))
        v = viewer()
        h = harness(v)
        x, y = locate(h, "web")
        h.click(x + 1, y).settle()
        assert "Not opened: https://example.com/page" in status(h)
        assert top(v) == 0 and opened == []

    def test_copy_the_shown_link(self, harness, monkeypatch):
        import pyperclip

        copied = []
        monkeypatch.setattr(pyperclip, "copy", copied.append)
        v = viewer()
        h = harness(v)
        h.press("y").settle()
        assert "No link to copy" in status(h)
        x, y = locate(h, "web")
        h.click(x + 1, y).settle()
        h.press("y").settle()
        assert copied == ["https://example.com/page"]
        assert "Copied" in status(h)

    def test_link_panel_lists_the_links_on_screen(self, harness):
        v = viewer()
        h = harness(v)
        h.press("l").settle()
        screen = h.screen()
        assert "Links on screen" in screen
        assert "a jump  -> #second" in screen
        assert "web  -> https://exampl" in screen  # the panel truncates; the status bar shows it all
        assert "[1]  -> footnote" in screen

    def test_choosing_from_the_link_panel(self, harness):
        v = viewer()
        h = harness(v)
        h.press("l").settle()
        x, y = locate(h, "a jump  ->")
        h.click(x, y).settle()
        h.press("enter").settle()
        assert top(v) > 0
        assert "a jump" in status(h)

    def test_click_off_a_link_does_nothing(self, harness):
        v = viewer()
        h = harness(v)
        x, y = locate(h, "filler")
        h.click(x, y).settle()
        assert top(v) == 0
        h.assert_no_errors()


@pytest.mark.unit
class TestQuit:
    def test_q_quits(self, harness):
        v = viewer()
        h = harness(v)
        h.press("q").settle()
        assert not h.running


@pytest.mark.unit
@pytest.mark.parametrize(
    ("key", "name"),
    [("pagedown", "PgDn"), ("ctrl+d", "Ctrl+D"), ("space", "Space"), ("left", "Left"), ("g", "g"), ("G", "G")],
)
def test_key_names(key, name):
    assert _key_name(key) == name


@pytest.mark.unit
def test_copy_link_is_bound_in_every_preset():
    from all2md.tui.keys import PRESETS

    for preset in PRESETS.values():
        assert Action.COPY_LINK in preset.values()
