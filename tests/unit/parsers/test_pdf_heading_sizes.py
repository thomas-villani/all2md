#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_pdf_heading_sizes.py
"""Which font sizes count as heading sizes, on documents with few sizes.

A Word document sets three to five sizes: a title, one or two heading sizes and the body.
The percentile filter ranked the document's *distinct* sizes and, below eight of them,
kept only the largest, so every section heading came out as a paragraph and only the
title survived (12 of 52 headings on the PDF to Word lane). It is now off by default, and
a size needs three lines rather than five, which a short document's sections reach.

What the percentile filter had been hiding is guarded directly: when two sizes set
near-equal amounts of text, body detection can pick the wrong one and the real body size
then clears every test above "body". A size that sets more than a quarter of the text is
body text, whatever admitted it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from all2md import to_ast
from all2md.ast import Heading
from all2md.options.pdf import PdfOptions
from all2md.parsers._pdf_headers import IdentifyHeaders

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "benchmarks" / "pdfword" / "corpus"


def _pdf(tmp_path: Path, lines: list[tuple[float, str, float]]) -> str:
    """A one-page PDF with each ``(y, text, fontsize)`` triple on its own line."""
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=800)
    writer = pymupdf.TextWriter(page.rect)
    font = pymupdf.Font("helv")
    for y, text, fontsize in lines:
        writer.append((30, y), text, font=font, fontsize=fontsize)
    writer.write_text(page)
    path = tmp_path / "page.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _header_sizes(path: str, **options: object) -> dict[int, int]:
    import pymupdf

    with pymupdf.open(path) as doc:
        return IdentifyHeaders(doc, options=PdfOptions(**options)).header_id


def _word_like(sections: int) -> list[tuple[float, str, float]]:
    """A 28pt title, ``sections`` 20pt headings, each over three 12pt body lines."""
    lines = [(50.0, "Annual Review", 28.0)]
    y = 100.0
    for number in range(sections):
        lines.append((y, f"Section {number}", 20.0))
        y += 28.0
        for row in range(3):
            lines.append((y, f"Body text of section {number}, line {row}, set plain.", 12.0))
            y += 16.0
        y += 12.0
    return lines


class TestAWordDocumentKeepsItsSectionHeadings:
    """With three distinct sizes, the 20pt section headings are heading sizes."""

    def test_three_section_headings_are_found(self, tmp_path: Path) -> None:
        sizes = _header_sizes(_pdf(tmp_path, _word_like(3)))
        assert 28 in sizes
        assert 20 in sizes
        assert sizes[28] < sizes[20]

    def test_two_lines_at_a_size_are_not_enough(self, tmp_path: Path) -> None:
        """The occurrence floor still drops a size seen on only two lines."""
        assert 20 not in _header_sizes(_pdf(tmp_path, _word_like(2)))

    def test_the_old_percentile_still_works_when_asked_for(self, tmp_path: Path) -> None:
        """The percentile filter is an option, now off by default rather than removed."""
        sizes = _header_sizes(_pdf(tmp_path, _word_like(3)), header_percentile_threshold=75)
        assert 20 not in sizes


class TestASizeThatSetsMuchOfTheTextIsBody:
    """Two near-tied text sizes: whichever is not picked as body is still not a heading."""

    def test_the_runner_up_text_size_is_not_a_heading_size(self, tmp_path: Path) -> None:
        lines = [(40.0, "A Paper Title", 21.0)]
        y = 70.0
        for row in range(14):
            lines.append((y, f"Reference {row}: an author, a journal and a page range.", 7.0))
            y += 10.0
        for row in range(12):
            lines.append((y, f"Prose line {row} of the article body at nine points.", 9.0))
            y += 12.0
        path = _pdf(tmp_path, lines)
        import pymupdf

        with pymupdf.open(path) as doc:
            detector = IdentifyHeaders(doc, options=PdfOptions(header_debug_output=True))
        info = detector.get_debug_info()
        assert info is not None
        assert info["body_text_size"] == 7
        assert 9 not in detector.header_id
        assert 21 in detector.header_id

    def test_bold_lines_at_a_text_size_are_still_headings(self, tmp_path: Path) -> None:
        """A text size keeps its bold lines as headings rather than being dropped outright.

        A journal sets its abstract and its section headings both at 10pt, the headings in
        bold: the size sets far more than a quarter of the text, but only its bold lines
        are headings, and those must survive.
        """
        pymupdf = pytest.importorskip("pymupdf")
        doc = pymupdf.open()
        page = doc.new_page(width=400, height=800)
        regular, bold = pymupdf.Font("helv"), pymupdf.Font("hebo")
        writer = pymupdf.TextWriter(page.rect)
        writer.append((30, 40), "A Paper Title", font=bold, fontsize=18)
        y = 70.0
        for row in range(20):
            writer.append((30, y), f"Body line {row} of the article at nine points, plain.", font=regular, fontsize=9)
            y += 11
        for name in ("Introduction", "Methods", "Results"):
            writer.append((30, y), name, font=bold, fontsize=10)
            y += 14
            for row in range(6):
                writer.append(
                    (30, y), f"Abstract-style text {row} set at ten points, plain.", font=regular, fontsize=10
                )
                y += 12
        writer.write_text(page)
        path = tmp_path / "page.pdf"
        doc.save(str(path))
        doc.close()

        with pymupdf.open(str(path)) as opened:
            detector = IdentifyHeaders(opened, options=PdfOptions())
        assert 10 in detector.header_id
        assert 10 in detector.bold_header_sizes

    def test_a_short_form_keeps_a_heading_size_with_a_large_share(self, tmp_path: Path) -> None:
        """Headings on a one-page form can set a tenth of its text and are still headings."""
        lines = [(40.0, "Registration Form", 28.0)]
        y = 90.0
        for number in range(4):
            lines.append((y, f"Section {number}: Details", 16.0))
            y += 22.0
            for row in range(4):
                lines.append((y, f"Field {row}: name, address and phone number", 10.0))
                y += 14.0
        assert 16 in _header_sizes(_pdf(tmp_path, lines))


@pytest.mark.skipif(not LANE.is_dir(), reason="the PDF to Word lane corpus is not checked out")
class TestOnWordsOwnPdfs:
    """The lane's untagged Word exports keep their section headings by default."""

    @pytest.mark.parametrize(
        ("case", "wanted"),
        [
            ("control/plain-prose", ["Construction", "Decline", "Restoration"]),
            ("report/memo-findings", ["Summary", "Findings", "Exceptions by Quarter", "Recommendations"]),
        ],
    )
    def test_section_headings(self, case: str, wanted: list[str]) -> None:
        pdf = LANE / f"{case}.untagged.pdf"
        doc = to_ast(str(pdf), parser_options=PdfOptions(layout_analysis_mode="disabled"))
        found = [
            "".join(getattr(c, "content", "") for c in h.content).strip()
            for h in doc.children
            if isinstance(h, Heading)
        ]
        for heading in wanted:
            assert heading in found


class TestAHeadingThatReadsAsProseIsAParagraph:
    """A line set at a heading size is still prose when its text says so."""

    @pytest.mark.parametrize(
        "text",
        [
            "599",  # a page number in a header bar
            "0.0012",  # a table figure
            "track is shown in Figure 2.2",  # the middle of a sentence
            "Increase opportunities for informal,",
            "This guidance is being distributed for comment purposes only.",
        ],
    )
    def test_prose_and_numbers_are_not_headings(self, text: str) -> None:
        from all2md.parsers.pdf import _reads_as_prose

        assert _reads_as_prose(text)

    @pytest.mark.parametrize(
        "text",
        [
            "Construction",
            "Introduction.",  # a short run-in label may end in a full stop
            "a. Preoperative education",  # a letter label opens lowercase
            "iv. Results",
            "mRNA expression",  # a name with a capital inside
            "Global Spread of Avian Flu: Issues for",  # a wrap is judged whole, not by line
            "2.1 Study design",
        ],
    )
    def test_headings_stay_headings(self, text: str) -> None:
        from all2md.parsers.pdf import _reads_as_prose

        assert not _reads_as_prose(text)

    def test_a_number_set_large_comes_out_as_a_paragraph(self, tmp_path: Path) -> None:
        lines = _word_like(3)
        lines += [(760.0, "599", 20.0)]
        doc = to_ast(_pdf(tmp_path, lines), parser_options=PdfOptions(layout_analysis_mode="disabled"))
        headings = [
            "".join(getattr(c, "content", "") for c in h.content).strip()
            for h in doc.children
            if isinstance(h, Heading)
        ]
        assert "Section 0" in headings
        assert "599" not in headings
