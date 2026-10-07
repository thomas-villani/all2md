"""Tests for the viewer's document layout: widths, outline, sections, links, resizes."""

from __future__ import annotations

import pytest
from document_strategies import documents, documents_with_footnotes
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from all2md import to_ast
from all2md.ast.nodes import Document, Heading, Link, Paragraph, Text
from all2md.options.terminal import TerminalRendererOptions
from all2md.tui.layout import DocumentLayout, OutlineEntry, github_slug

NL = chr(10)


def markdown(source: str) -> DocumentLayout:
    doc = to_ast(source.encode(), source_format="markdown")
    return DocumentLayout(doc, TerminalRendererOptions(color_system="none"))


def lines(layout: DocumentLayout, width: int) -> list[str]:
    return layout.text(width).split(NL)


def flatten(entries: tuple[OutlineEntry, ...]) -> list[tuple[int, int, str]]:
    out = []
    for entry in entries:
        out.append((entry.index, entry.level, entry.text))
        out.extend(flatten(entry.children))
    return out


LONG = "# Title\n\nIntro " + "words " * 60 + "\n\n## First\n\n" + "alpha " * 80 + "\n\n## Second\n\n" + "beta " * 80


@pytest.mark.unit
class TestWidths:
    def test_text_is_laid_out_at_the_width_asked(self):
        layout = markdown(LONG)
        assert all(len(line) <= 30 for line in lines(layout, 30))
        assert any(len(line) > 30 for line in lines(layout, 90))

    def test_width_option_is_ignored(self):
        doc = to_ast(LONG.encode(), source_format="markdown")
        layout = DocumentLayout(doc, TerminalRendererOptions(width=200, color_system="none"))
        assert layout.at(40).width == 40

    def test_layouts_are_cached_and_bounded(self):
        layout = DocumentLayout(Document(children=[Paragraph(content=[Text(content="x")])]), cache_size=2)
        first = layout.at(40)
        assert layout.at(40) is first
        layout.at(50)
        layout.at(40)  # refreshed, so 50 is the oldest
        layout.at(60)
        assert set(layout._layouts) == {40, 60}
        assert layout.at(40) is first

    def test_evicted_width_is_laid_out_again(self):
        layout = DocumentLayout(Document(children=[Paragraph(content=[Text(content="x")])]), cache_size=1)
        first = layout.at(40)
        layout.at(50)
        assert layout.at(40) is not first
        assert layout.at(40).text == first.text

    @pytest.mark.parametrize("bad", [0, -5])
    def test_width_must_be_positive(self, bad):
        with pytest.raises(ValueError):
            DocumentLayout(Document()).at(bad)

    def test_cache_size_must_be_positive(self):
        with pytest.raises(ValueError):
            DocumentLayout(Document(), cache_size=0)


@pytest.mark.unit
class TestOutline:
    def test_headings_nest_under_the_nearest_shallower_one(self):
        layout = markdown("# A\n\n## B\n\n### C\n\n## D\n\n# E\n\n### F\n")
        a, e = layout.outline
        assert (a.text, [c.text for c in a.children]) == ("A", ["B", "D"])
        assert [c.text for c in a.children[0].children] == ["C"]
        assert (e.text, [c.text for c in e.children]) == ("E", ["F"])

    def test_document_starting_below_level_one(self):
        layout = markdown("### deep\n\n## shallower\n\n### under\n")
        assert [entry.text for entry in layout.outline] == ["deep", "shallower"]
        assert [c.text for c in layout.outline[1].children] == ["under"]

    def test_indexes_are_document_order(self):
        layout = markdown("# A\n\n## B\n\n### C\n\n## D\n")
        assert [index for index, _, _ in flatten(layout.outline)] == [0, 1, 2, 3]

    def test_no_headings(self):
        assert markdown("just text\n").outline == ()

    @settings(deadline=None, derandomize=True, max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(doc=st.one_of(documents(), documents_with_footnotes()))
    def test_outline_holds_every_heading_once_in_order(self, doc):
        layout = DocumentLayout(doc, TerminalRendererOptions(color_system="none"))
        flat = flatten(layout.outline)
        assert [index for index, _, _ in flat] == list(range(len(layout.headings)))
        assert [(level, text) for _, level, text in flat] == [(h.level, h.text) for h in layout.headings]


@pytest.mark.unit
class TestSections:
    def test_heading_line_follows_the_width(self):
        layout = markdown(LONG)
        for width in (30, 60, 100):
            shown = lines(layout, width)
            for index, heading in enumerate(layout.headings):
                line = layout.heading_line(index, width)
                assert line is not None and heading.text in shown[line]
        assert layout.heading_line(2, 30) > layout.heading_line(2, 100)

    def test_cropped_heading_has_no_line(self):
        doc = to_ast(("# A" + NL * 2 + "> " * 12 + "## Deep" + NL * 2 + "# B" + NL).encode(), source_format="markdown")
        layout = DocumentLayout(doc, TerminalRendererOptions(color_system="none", word_wrap=False))
        assert [layout.heading_line(i, 80) for i in range(3)] == [0, 2, 4]
        assert [layout.heading_line(i, 12) for i in range(3)] == [0, None, 4]
        assert layout.section_at(3, 12) == 0

    def test_outline_grows_when_a_wider_width_shows_more(self):
        doc = to_ast(("# A" + NL * 2 + "> " * 12 + "## Deep" + NL).encode(), source_format="markdown")
        layout = DocumentLayout(doc, TerminalRendererOptions(color_system="none", word_wrap=False))
        layout.at(12)
        assert flatten(layout.outline) == [(0, 1, "A")]
        layout.at(80)
        assert flatten(layout.outline) == [(0, 1, "A"), (1, 2, "Deep")]
        assert layout.heading_line(1, 12) is None
        assert layout.heading_line(1, 80) == 2

    def test_heading_line_out_of_range(self):
        assert markdown("# A\n").heading_line(5, 40) is None

    def test_section_at(self):
        layout = markdown(LONG)
        first = layout.heading_line(1, 40)
        second = layout.heading_line(2, 40)
        assert layout.section_at(first - 1, 40) == 0
        assert layout.section_at(first, 40) == 1
        assert layout.section_at(second - 1, 40) == 1
        assert layout.section_at(second + 3, 40) == 2

    def test_section_above_the_first_heading(self):
        layout = markdown("intro\n\n# A\n")
        assert layout.section_at(0, 40) is None

    def test_next_and_previous_heading(self):
        layout = markdown(LONG)
        title, first, second = (layout.heading_line(i, 40) for i in range(3))
        assert layout.next_heading(title, 40) == first
        assert layout.next_heading(first + 1, 40) == second
        assert layout.next_heading(second, 40) is None
        assert layout.previous_heading(second, 40) == first
        assert layout.previous_heading(first + 1, 40) == first
        assert layout.previous_heading(title, 40) is None


@pytest.mark.unit
class TestRelocate:
    def test_heading_stays_at_the_top(self):
        layout = markdown(LONG)
        for index in range(3):
            line = layout.heading_line(index, 30)
            assert layout.relocate(line, 30, 100) == layout.heading_line(index, 100)

    def test_line_keeps_its_section(self):
        layout = markdown(LONG)
        first = layout.heading_line(1, 30)
        second = layout.heading_line(2, 30)
        middle = (first + second) // 2
        moved = layout.relocate(middle, 30, 100)
        assert layout.section_at(moved, 100) == 1
        assert layout.heading_line(1, 100) < moved < layout.heading_line(2, 100)

    def test_out_of_range_lines_are_clamped(self):
        layout = markdown(LONG)
        assert 0 <= layout.relocate(10_000, 30, 100) < layout.at(100).line_count
        assert layout.relocate(-3, 30, 100) == 0

    def test_empty_document(self):
        assert DocumentLayout(Document()).relocate(5, 30, 60) == 0

    @settings(deadline=None, derandomize=True, max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        doc=documents(),
        widths=st.tuples(st.integers(20, 120), st.integers(20, 120)),
        fraction=st.floats(0, 1),
    )
    def test_relocated_line_exists_and_keeps_its_section(self, doc, widths, fraction):
        layout = DocumentLayout(doc, TerminalRendererOptions(color_system="none"))
        old, new = widths
        count = layout.at(old).line_count
        line = int(fraction * max(count - 1, 0))
        moved = layout.relocate(line, old, new)
        assert 0 <= moved < max(layout.at(new).line_count, 1)
        section = layout.section_at(line, old)
        if section is not None and layout.at(new).line_count:
            assert layout.section_at(moved, new) == section


@pytest.mark.unit
class TestFragments:
    @pytest.mark.parametrize(
        ("text", "slug"),
        [
            ("Hello World!", "hello-world"),
            ("API Reference (v2.0)", "api-reference-v20"),
            ("snake_case and-dash", "snake_case-and-dash"),
            ("Über straße", "über-straße"),
            ("  padded  ", "padded"),
            ("What's new?", "whats-new"),
        ],
    )
    def test_github_slug(self, text, slug):
        assert github_slug(text) == slug

    def test_github_anchors(self):
        layout = markdown("# Getting Started\n\n## API Reference (v2.0)\n\n## Über uns\n")
        assert layout.resolve_fragment("#getting-started") == 0
        assert layout.resolve_fragment("api-reference-v20") == 1
        assert layout.resolve_fragment("#über-uns") == 2
        assert layout.resolve_fragment("#%C3%BCber-uns") == 2

    def test_repeated_headings_are_numbered_from_one(self):
        layout = markdown("# Intro\n\n# Intro\n\n# Intro\n")
        assert [layout.resolve_fragment(f) for f in ("#intro", "#intro-1", "#intro-2")] == [0, 1, 2]

    def test_numbering_skips_anchors_in_use(self):
        layout = markdown("# Intro-1\n\n# Intro\n\n# Intro\n")
        assert [layout.resolve_fragment(f) for f in ("#intro-1", "#intro", "#intro-2")] == [0, 1, 2]

    def test_loose_match(self):
        layout = markdown("# Über uns\n")
        assert layout.resolve_fragment("#Uber-Uns") == 0
        assert layout.resolve_fragment("#ueber-uns") is None

    def test_explicit_id_wins(self):
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="custom")]),
                Heading(level=2, content=[Text(content="Shown title")], metadata={"id": "custom"}),
            ]
        )
        layout = DocumentLayout(doc)
        assert layout.resolve_fragment("#custom") == 1
        assert layout.resolve_fragment("#shown-title") == 1

    def test_asciidoc_ids(self):
        doc = to_ast(b"[[setup]]\n== Installing things\n\ntext\n", source_format="asciidoc")
        assert DocumentLayout(doc).resolve_fragment("#setup") == 0

    @pytest.mark.parametrize("fragment", ["", "#", "#nowhere", "#!!!"])
    def test_unknown(self, fragment):
        assert markdown("# A\n").resolve_fragment(fragment) is None


@pytest.mark.unit
class TestLinks:
    SOURCE = (
        "# Top\n\nSee [below](#later), [the web](https://example.com), "
        "[a file](other.md) and a note[^1].\n\n" + "filler " * 120 + "\n\n## Later\n\ntext\n\n[^1]: The note.\n"
    )

    def test_links_between(self):
        layout = markdown(self.SOURCE)
        found = layout.links_between(0, 5, 40)
        assert [p.target for p in found] == ["#later", "https://example.com", "other.md", "1"]
        assert layout.links_between(found[-1].line + 1, found[-1].line + 3, 40) == []

    def test_wrapped_link_listed_once(self):
        doc = Document(
            children=[
                Paragraph(
                    content=[Text(content="x"), Link(url="#a", content=[Text(content="a long label that wraps")])]
                )
            ]
        )
        layout = DocumentLayout(doc, TerminalRendererOptions(color_system="none"))
        assert len(layout.at(12).links) > 1
        (only,) = layout.links_between(0, 100, 12)
        assert only == layout.at(12).links[0]

    def test_link_partly_in_range_is_listed(self):
        doc = Document(
            children=[
                Paragraph(
                    content=[Text(content="x"), Link(url="#a", content=[Text(content="a long label that wraps")])]
                )
            ]
        )
        layout = DocumentLayout(doc, TerminalRendererOptions(color_system="none"))
        last = layout.at(12).links[-1]
        (found,) = layout.links_between(last.line, last.line + 1, 12)
        assert found == last

    def test_jump_targets(self):
        layout = markdown(self.SOURCE)
        for width in (40, 80):
            by_target = {p.target: p for p in layout.at(width).links}
            later = layout.jump_target(by_target["#later"], width)
            assert later == layout.heading_line(1, width)
            note = layout.jump_target(by_target["1"], width)
            assert lines(layout, width)[note].startswith("[1] The note.")
            assert layout.jump_target(by_target["https://example.com"], width) is None
            assert layout.jump_target(by_target["other.md"], width) is None

    def test_fragment_to_nowhere_does_not_jump(self):
        layout = markdown("[gone](#missing)\n")
        (position,) = layout.at(40).links
        assert layout.jump_target(position, 40) is None
