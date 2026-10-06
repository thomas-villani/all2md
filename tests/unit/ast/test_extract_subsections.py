"""Extracting a section takes in its subsections.

``get_all_sections`` ends each section at the next heading of any level, so
``--extract Introduction`` used to stop at Introduction's own first subheading
and return the heading alone.
"""

from __future__ import annotations

import pytest

from all2md.ast.extraction import build_extracted_document
from all2md.ast.nodes import Document, Heading, Paragraph, Text, ThematicBreak
from all2md.ast.sections import extract_sections, get_all_sections, subsection_ranges
from all2md.ast.utils import extract_text
from all2md.cli import main

NL = chr(10)

SOURCE = NL.join(
    [
        "# Title",
        "",
        "## Introduction",
        "",
        "### Subheading",
        "",
        "Some text in the subheading",
        "",
        "## Next Section",
        "",
        "After.",
        "",
    ]
)


def _heading(level: int, text: str) -> Heading:
    return Heading(level=level, content=[Text(content=text)])


def _para(text: str) -> Paragraph:
    return Paragraph(content=[Text(content=text)])


@pytest.fixture
def doc() -> Document:
    return Document(
        children=[
            _heading(1, "Title"),
            _heading(2, "Introduction"),
            _heading(3, "Subheading"),
            _para("Some text in the subheading"),
            _heading(4, "Deeper"),
            _para("Deep text"),
            _heading(2, "Next Section"),
            _para("After."),
        ]
    )


def _texts(document: Document) -> list[str]:
    return [extract_text(node) for node in document.children]


@pytest.mark.unit
class TestSubsectionRanges:
    def test_a_section_runs_to_the_next_heading_at_its_level_or_above(self, doc):
        sections = get_all_sections(doc)
        assert subsection_ranges(sections, [1]) == [(1, 4)]
        assert subsection_ranges(sections, [0]) == [(0, 5)]
        assert subsection_ranges(sections, [4]) == [(4, 5)]

    def test_a_selection_inside_another_is_dropped(self, doc):
        sections = get_all_sections(doc)
        assert subsection_ranges(sections, [2, 1, 3]) == [(1, 4)]

    def test_selection_order_is_kept(self, doc):
        sections = get_all_sections(doc)
        assert subsection_ranges(sections, [4, 1]) == [(4, 5), (1, 4)]

    def test_repeats_are_dropped(self, doc):
        sections = get_all_sections(doc)
        assert subsection_ranges(sections, [1, 1]) == [(1, 4)]


@pytest.mark.unit
class TestExtractSections:
    def test_by_name(self, doc):
        assert _texts(extract_sections(doc, "Introduction")) == [
            "Introduction",
            "Subheading",
            "Some text in the subheading",
            "Deeper",
            "Deep text",
        ]

    def test_a_leaf_section_is_unchanged(self, doc):
        assert _texts(extract_sections(doc, "Next Section")) == ["Next Section", "After."]

    def test_not_combined(self, doc):
        assert _texts(extract_sections(doc, "Introduction", combine=False))[-1] == "Deep text"

    def test_a_range_over_a_section_and_its_subsection_has_no_repeats(self, doc):
        extracted = extract_sections(doc, "#:2-3")
        texts = _texts(extracted)
        assert texts.count("Subheading") == 1
        assert not any(isinstance(node, ThematicBreak) for node in extracted.children)

    def test_typed_selector(self, doc):
        assert _texts(build_extracted_document(doc, ["Introduction"]))[-1] == "Deep text"


@pytest.mark.unit
class TestCli:
    def _run(self, tmp_path, capsys, *flags: str) -> list[str]:
        path = tmp_path / "doc.md"
        path.write_text(SOURCE, encoding="utf-8")
        assert main([str(path), *flags]) == 0
        return [line for line in capsys.readouterr().out.splitlines() if line.strip()]

    def test_extract(self, tmp_path, capsys):
        assert self._run(tmp_path, capsys, "--extract", "Introduction") == [
            "## Introduction",
            "### Subheading",
            "Some text in the subheading",
        ]

    def test_extract_with_line_numbers(self, tmp_path, capsys):
        lines = self._run(tmp_path, capsys, "--extract", "Introduction", "--line-numbers")
        numbered = [line.strip() for line in lines if line.split(":", 1)[1].strip()]
        assert numbered == ["3: ## Introduction", "5: ### Subheading", "7: Some text in the subheading"]
