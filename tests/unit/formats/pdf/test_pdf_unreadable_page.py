#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_unreadable_page.py
"""A page whose text cannot be read is dropped, but never silently.

``_process_page_to_ast`` wrapped its ``page.get_text("dict", ...)`` call in
``except (AttributeError, KeyError, Exception): return []`` -- no log line, no degraded
event, no progress event. The catch-all began life as test support for mock pages, and a
later commit moved the in-place ``dehyphenate_blocks()`` call inside it as well, so a bug
in our own dehyphenation would have been laundered into "this page was blank" too.

Three things go wrong when a page can disappear without a trace:

* an empty page and an unreadable page are indistinguishable in the output;
* the conversion reports success either way;
* the document-level OCR safety net counts meaningful characters, so if every page trips
  this it sees an empty document -- and can put a perfectly good text PDF through OCR.

The tolerance itself is deliberate and stays: one broken page must not cost the other
400. What is asserted here is that it leaves evidence.
"""

from __future__ import annotations

import logging

import pytest

from all2md.options.pdf import PdfOptions
from all2md.parsers.pdf import PdfToAstConverter

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

pymupdf = pytest.importorskip("pymupdf")


class _UnreadablePage:
    """A page that cannot answer ``get_text()`` -- the shape a mock page has."""

    def get_text(self, *args, **kwargs):
        raise RuntimeError("mupdf: cannot open page")


def _sequencer(name: str, mime: str) -> tuple[str, int]:
    return name, 0


def _converter() -> PdfToAstConverter:
    # table_detection_mode="none" so nothing touches the page before get_text() does.
    converter = PdfToAstConverter(options=PdfOptions(table_detection_mode="none"))
    converter._degraded_events = []
    return converter


def _process(converter: PdfToAstConverter, page, page_num: int = 0):
    return converter._process_page_to_ast(page, page_num, "doc", _sequencer, total_pages=1)


class TestAnUnreadablePageIsToleratedButReported:
    def test_the_page_is_still_dropped_rather_than_raising(self):
        """The tolerance is the point: mock pages reach here, and one bad page of 400 is not fatal."""
        assert _process(_converter(), _UnreadablePage()) == []

    def test_it_is_logged_with_the_page_number(self, caplog):
        converter = _converter()

        with caplog.at_level(logging.WARNING, logger="all2md.parsers.pdf"):
            _process(converter, _UnreadablePage(), page_num=6)

        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert "page 7" in logged.lower(), "the 0-based index must be reported 1-based, as everywhere else"

    def test_the_cause_is_in_the_log(self, caplog):
        with caplog.at_level(logging.WARNING, logger="all2md.parsers.pdf"):
            _process(_converter(), _UnreadablePage())

        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert "cannot open page" in logged

    def test_a_degraded_event_is_recorded(self):
        converter = _converter()

        _process(converter, _UnreadablePage())

        kinds = [event.kind for event in converter._degraded_events]
        assert "page_text_extraction_failed" in kinds

    def test_losing_a_whole_page_is_scored_as_an_error(self):
        """Every other degradation here is a rejected table or a dropped image. A page is not."""
        converter = _converter()

        _process(converter, _UnreadablePage())

        event = next(e for e in converter._degraded_events if e.kind == "page_text_extraction_failed")
        assert event.severity == "error"
        assert "page 1" in (event.detail or ""), "the event has to say which page went missing"


class TestDehyphenationIsNoLongerSwallowed:
    """``dehyphenate_blocks()`` runs on blocks already read successfully.

    A failure in it is a bug in our code, not an unreadable page. Inside the ``except``
    it became an empty page; outside, it surfaces.
    """

    @staticmethod
    def _one_line_pdf_page():
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 100), "a line of ordinary prose", fontsize=11)
        return pymupdf.open(stream=doc.tobytes(), filetype="pdf")[0]

    def test_a_dehyphenation_failure_propagates(self, monkeypatch):
        def explode(blocks):
            raise ValueError("bug in dehyphenation")

        monkeypatch.setattr("all2md.parsers.pdf.dehyphenate_blocks", explode)
        converter = _converter()

        with pytest.raises(ValueError, match="bug in dehyphenation"):
            _process(converter, self._one_line_pdf_page())

    def test_it_is_not_reported_as_an_unreadable_page(self, monkeypatch):
        def explode(blocks):
            raise ValueError("bug in dehyphenation")

        monkeypatch.setattr("all2md.parsers.pdf.dehyphenate_blocks", explode)
        converter = _converter()

        with pytest.raises(ValueError):
            _process(converter, self._one_line_pdf_page())

        assert [e.kind for e in converter._degraded_events] == []

    def test_a_readable_page_still_gets_dehyphenated(self, monkeypatch):
        """Hoisting the call out of the ``try`` must not have skipped it."""
        import all2md.parsers.pdf as pdf_module

        calls: list[int] = []
        original = pdf_module.dehyphenate_blocks

        def counting(blocks):
            calls.append(len(blocks))
            return original(blocks)

        monkeypatch.setattr(pdf_module, "dehyphenate_blocks", counting)

        _process(_converter(), self._one_line_pdf_page())

        assert calls, "merge_hyphenated_words is on by default; the blocks must still be dehyphenated"
