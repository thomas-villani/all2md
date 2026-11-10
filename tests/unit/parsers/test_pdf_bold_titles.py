#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_pdf_bold_titles.py
"""Section headings set in bold at the body size (#688).

Contracts set their section headings in bold at the size of the text, so the font-size
rules cannot admit them: 120 contracts from CUAD produced 11 headings between them. The
heading sits as close to its text as one line of a paragraph to the next, so the change of
weight is what ends it. A short all-bold paragraph is a heading; a bold paragraph that runs
on is not, and neither is a bold run that reads as prose.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from all2md import to_ast
from all2md.ast import Heading, Paragraph
from all2md.ast.utils import extract_text
from all2md.options.pdf import PdfOptions

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

PITCH = 13.0  # the leading of 11pt text: a title is set no further from its text than this


def _pdf(tmp_path: Path, lines: list[tuple[str, bool]], fontsize: float = 11.0) -> str:
    """A one-page PDF of ``(text, bold)`` lines, every line at one size and one pitch."""
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    regular, bold = pymupdf.Font("helv"), pymupdf.Font("hebo")
    writer = pymupdf.TextWriter(page.rect)
    y = 60.0
    for text, is_bold in lines:
        writer.append((72, y), text, font=bold if is_bold else regular, fontsize=fontsize)
        y += PITCH
    writer.write_text(page)
    path = tmp_path / "contract.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _blocks(path: str, **options: object) -> list[tuple[str, str]]:
    doc = to_ast(path, parser_options=PdfOptions(layout_analysis_mode="disabled", **options))
    return [(type(child).__name__, " ".join(extract_text(child).split())) for child in doc.children]


def _headings(path: str, **options: object) -> list[str]:
    return [text for kind, text in _blocks(path, **options) if kind == Heading.__name__]


BODY = [
    ("The Company shall indemnify and hold harmless the Purchaser from any and all", False),
    ("losses, claims and damages arising out of a breach of this Agreement.", False),
]


def _contract() -> list[tuple[str, bool]]:
    return [
        ("RECITALS", True),
        *BODY,
        ("ARTICLE 5 INDEMNIFICATION", True),
        *BODY,
        ("5.1 Survival of Representations", True),
        *BODY,
    ]


class TestABoldTitleAtBodySizeIsAHeading:
    def test_each_bold_title_is_a_heading(self, tmp_path: Path) -> None:
        assert _headings(_pdf(tmp_path, _contract())) == [
            "RECITALS",
            "ARTICLE 5 INDEMNIFICATION",
            "5.1 Survival of Representations",
        ]

    def test_the_text_under_a_title_stays_one_paragraph(self, tmp_path: Path) -> None:
        blocks = _blocks(_pdf(tmp_path, _contract()))
        assert blocks[0] == ("Heading", "RECITALS")
        assert blocks[1][0] == Paragraph.__name__
        assert blocks[1][1].startswith("The Company shall") and blocks[1][1].endswith("this Agreement.")

    def test_a_numbered_title_is_a_heading_not_a_list(self, tmp_path: Path) -> None:
        lines = [("1. DEFINITIONS", True), *BODY, ("2. TERM", True), *BODY]
        assert _headings(_pdf(tmp_path, lines)) == ["1. DEFINITIONS", "2. TERM"]

    def test_a_bold_title_ranks_under_a_title_set_large(self, tmp_path: Path) -> None:
        pymupdf = pytest.importorskip("pymupdf")
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        regular, bold = pymupdf.Font("helv"), pymupdf.Font("hebo")
        writer = pymupdf.TextWriter(page.rect)
        writer.append((72, 50), "Supply Agreement", font=bold, fontsize=20)
        y = 90.0
        for text, is_bold in _contract():
            writer.append((72, y), text, font=bold if is_bold else regular, fontsize=11)
            y += PITCH
        writer.write_text(page)
        path = tmp_path / "titled.pdf"
        doc.save(str(path))
        doc.close()
        parsed = to_ast(str(path), parser_options=PdfOptions(layout_analysis_mode="disabled"))
        levels = {" ".join(extract_text(h).split()): h.level for h in parsed.children if isinstance(h, Heading)}
        assert levels["Supply Agreement"] == 1
        assert levels["RECITALS"] == 2

    def test_font_weight_off_turns_it_off(self, tmp_path: Path) -> None:
        assert _headings(_pdf(tmp_path, _contract()), header_use_font_weight=False) == []


class TestBoldThatIsNotATitle:
    def test_a_bold_paragraph_is_not_a_heading(self, tmp_path: Path) -> None:
        """A disclaimer in bold capitals runs on for lines and stays a paragraph."""
        disclaimer = [
            ("THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR", True),
            ("IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,", True),
            ("FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT IN NO EVENT SHALL", True),
            ("THE AUTHORS BE LIABLE FOR ANY CLAIM.", True),
        ]
        assert _headings(_pdf(tmp_path, [*BODY, *disclaimer, *BODY])) == []

    def test_a_bold_sentence_is_not_a_heading(self, tmp_path: Path) -> None:
        lines = [*BODY, ("Time is of the essence of each and every provision hereof.", True), *BODY]
        assert _headings(_pdf(tmp_path, lines)) == []

    def test_a_bare_label_is_not_a_heading(self, tmp_path: Path) -> None:
        lines = [*BODY, ("a.", True), *BODY]
        assert _headings(_pdf(tmp_path, lines)) == []

    @pytest.mark.parametrize(
        "label",
        [
            "Table 1",
            "Figure 2.",
            "Page",
            "(continued)",
            "Country/",
            "Methods..........",
            "Page 12 GAO-07-375 Progress",
            "E E E E",
            "miR-21 miR-21",
            "- Thorough peer review",
        ],
    )
    def test_a_label_set_bold_is_not_a_heading(self, tmp_path: Path, label: str) -> None:
        """Caption and figure labels, contents pages, running heads, bullets, cut table headers."""
        lines = [*BODY, (label, True), *BODY]
        assert _headings(_pdf(tmp_path, lines)) == []

    def test_a_bold_phrase_inside_a_sentence_stays_in_it(self, tmp_path: Path) -> None:
        """A line that is all bold mid-sentence does not end the paragraph above it."""
        lines = [
            ("The parties agree that the following terms shall apply to the", False),
            ("Confidential Information Disclosed Hereunder", True),
            ("and to any copies made of it by either party.", False),
        ]
        blocks = _blocks(_pdf(tmp_path, lines))
        assert [kind for kind, _ in blocks] == ["Paragraph"]
