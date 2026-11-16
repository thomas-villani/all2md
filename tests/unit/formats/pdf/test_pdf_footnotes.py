"""PDF footnotes: the area below Word's separator rule becomes footnotes, its labels references.

The wide tier (``benchmarks/pdfword/wide.py``) found every footnote in Word's PDFs leaking into
the body: the note text at the foot of the page, and the reference number glued to the word
before it ("Rules1"). Word sets the notes below a short rule at the left margin, smaller than
the body, each opened by a small raised label.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from all2md import to_ast, to_markdown
from all2md.ast import FootnoteDefinition, FootnoteReference, extract_text
from all2md.ast.transforms import extract_nodes
from all2md.options.pdf import PdfOptions
from all2md.parsers._pdf_footnotes import find_separator, is_reference_span, take_footnote_area

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

PAGE_HEIGHT = 792.0


def _span(x0: float, x1: float, top: float, text: str, size: float) -> dict:
    return {"text": text, "size": size, "flags": 0, "font": "Times", "bbox": (x0, top, x1, top + size * 1.15)}


def _line(top: float, *spans: dict) -> dict:
    return {
        "bbox": (spans[0]["bbox"][0], top, spans[-1]["bbox"][2], top + max(s["size"] for s in spans) * 1.15),
        "dir": (1.0, 0.0),
        "spans": list(spans),
    }


def _block(*lines: dict) -> dict:
    return {
        "type": 0,
        "bbox": (
            min(line["bbox"][0] for line in lines),
            min(line["bbox"][1] for line in lines),
            max(line["bbox"][2] for line in lines),
            max(line["bbox"][3] for line in lines),
        ),
        "lines": list(lines),
    }


def _rule(x0: float, y: float, width: float) -> dict:
    return {"rect": SimpleNamespace(x0=x0, y0=y, x1=x0 + width, y1=y + 0.5)}


BODY = _block(
    _line(100.0, _span(72, 540, 100.0, "The station failed to maintain operational equipment, contrary to", 12.0)),
    _line(114.0, _span(72, 300, 114.0, "Sections 11.35 of the Rules.", 12.0), _span(300, 304, 112.0, "1", 7.0)),
)


def _note(top: float, label: str, text: str) -> dict:
    return _block(_line(top, _span(72, 76, top, label, 6.5), _span(76, 400, top, " " + text, 10.0)))


class TestTheArea:
    def test_notes_below_the_rule_are_taken_out_of_the_body(self):
        notes = [_note(700.0, "1", "47 C.F.R. 11.35 and 73.1745."), _note(712.0, "2", "See 47 C.F.R. 11.35(a).")]
        body, area = take_footnote_area([_rule(72, 690, 144)], [BODY, *notes], PAGE_HEIGHT)
        assert body == [BODY]
        assert area is not None
        assert [note.label for note in area.notes] == ["1", "2"]
        assert "".join(span["text"] for span in area.notes[0].lines[0]) == "47 C.F.R. 11.35 and 73.1745."

    def test_a_full_width_rule_is_not_a_separator(self):
        assert find_separator([_rule(72, 690, 468)], [BODY, _note(700.0, "1", "x")], PAGE_HEIGHT) is None

    def test_a_rule_high_on_the_page_is_not_a_separator(self):
        assert find_separator([_rule(72, 150, 144)], [BODY, _note(160.0, "1", "x")], PAGE_HEIGHT) is None

    def test_text_under_a_rule_without_labels_stays_in_the_body(self):
        # A signature line: a short rule low on the page with a name under it.
        name = _block(_line(700.0, _span(72, 200, 700.0, "John Smith, Chair", 12.0)))
        body, area = take_footnote_area([_rule(72, 690, 144)], [BODY, name], PAGE_HEIGHT)
        assert area is None
        assert body == [BODY, name]

    def test_a_page_number_below_the_notes_stays_in_the_body(self):
        number = _block(_line(714.0, _span(303, 309, 714.0, "3", 10.0)))
        note = _note(700.0, "1", "47 C.F.R. 11.35.")
        body, area = take_footnote_area([_rule(72, 690, 144)], [BODY, note, number], PAGE_HEIGHT)
        assert area is not None
        assert body == [BODY, number]

    def test_unlabelled_text_continues_a_note_only_when_one_is_open(self):
        rest = _block(_line(700.0, _span(72, 400, 700.0, "the rest of a long note.", 10.0)))
        assert take_footnote_area([_rule(72, 690, 144)], [BODY, rest], PAGE_HEIGHT)[1] is None
        area = take_footnote_area([_rule(72, 690, 144)], [BODY, rest], PAGE_HEIGHT, note_open=True)[1]
        assert area is not None
        assert area.continued


def test_a_reference_is_small_or_raised():
    line = BODY["lines"][1]["spans"]
    assert is_reference_span(line[1], line)
    assert not is_reference_span(line[0], line)


def _word_pdf(path: Path) -> Path:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 100), "The station failed to maintain its equipment, contrary to the Rules.", fontsize=12)
    page.insert_text((450, 95), "1", fontsize=7)
    page.insert_text((72, 120), "It also failed to keep its logs, which the inspector asked to see.", fontsize=12)
    page.insert_text((460, 115), "2", fontsize=7)
    # Enough body for a real page: a near-empty document is retried through OCR.
    for row in range(20):
        page.insert_text(
            (72, 150 + row * 20), "The licensee shall keep its station logs and records in order.", fontsize=12
        )
    page.draw_line((72, 700), (216, 700), width=0.5)
    for top, label, text in ((715, "1", "47 C.F.R. 11.35 and 73.1745."), (730, "2", "See 47 C.F.R. 73.1840.")):
        page.insert_text((72, top - 3), label, fontsize=6.5)
        page.insert_text((76, top), text, fontsize=10)
    document.save(path)
    return path


def test_a_word_pdf_gets_real_footnotes(tmp_path: Path) -> None:
    source = _word_pdf(tmp_path / "notes.pdf")
    doc = to_ast(str(source), parser_options=PdfOptions(layout_analysis_mode="disabled"))
    definitions = list(extract_nodes(doc, FootnoteDefinition))
    assert [d.identifier for d in definitions] == ["1", "2"]
    assert extract_text(definitions[0]).strip() == "47 C.F.R. 11.35 and 73.1745."
    assert [r.identifier for r in extract_nodes(doc, FootnoteReference)] == ["1", "2"]
    markdown = to_markdown(str(source), parser_options=PdfOptions(layout_analysis_mode="disabled"))
    assert "Rules.[^1]" in markdown
    assert "[^2]: See 47 C.F.R. 73.1840." in markdown


def test_detection_can_be_turned_off(tmp_path: Path) -> None:
    source = _word_pdf(tmp_path / "notes.pdf")
    options = PdfOptions(layout_analysis_mode="disabled", detect_footnotes=False)
    assert not list(extract_nodes(to_ast(str(source), parser_options=options), FootnoteDefinition))
