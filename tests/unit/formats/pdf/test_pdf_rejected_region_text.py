#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_rejected_region_text.py
"""Text rescued from a rejected table region is prose, and has to be treated as prose.

When a detected table's grid turns out to be degenerate, the region is emitted as a
paragraph instead. Its text is recovered with ``clipped_textbox()``, which is raw
extraction: the glyphs come back with their printed line breaks intact. Every other route
into the AST passes through ``dehyphenate_blocks()`` first, and this one did not, so a word
broken across a line stayed broken -- "Coroman-" and "del" never became "Coromandel", and
the word appeared nowhere in the output at all.

That matters more than a rejected grid sounds like it should: the layout model over-predicts
tables, and each over-prediction routes a whole region's prose through here. On the page
this was found on, the predicted region covered the entire page body.
"""

from __future__ import annotations

import pytest

from all2md.ast.utils import extract_text
from all2md.options.pdf import PdfOptions
from all2md.parsers.pdf import PdfToAstConverter

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

pymupdf = pytest.importorskip("pymupdf")


TOP = 100


def _pdf_bytes(*lines: str) -> bytes:
    """A one-page PDF holding ``lines``, one under the other."""
    doc = pymupdf.open()
    page = doc.new_page()
    for offset, line in enumerate(lines):
        page.insert_text((72, TOP + offset * 14), line, fontsize=11)
    return doc.tobytes()


def _page_with_lines(*lines: str):
    """The same page, re-opened from bytes, plus a rect covering every line on it."""
    page = pymupdf.open(stream=_pdf_bytes(*lines), filetype="pdf")[0]
    region = pymupdf.Rect(60, TOP - 14, 400, TOP + len(lines) * 14 + 4)
    return page, region


def _region_text(page, region, **option_overrides) -> str:
    converter = PdfToAstConverter(options=PdfOptions(**option_overrides))
    paragraph = converter._region_text_as_paragraph(page, region, 0)
    return extract_text(paragraph, joiner="") if paragraph is not None else ""


class TestAWordBrokenAcrossALineComesBackWhole:
    def test_the_two_halves_are_joined(self):
        page, region = _page_with_lines("forests on the Coroman-", "del coast, south India.")

        assert "Coromandel" in _region_text(page, region)

    def test_the_broken_form_is_gone(self):
        # The failure was not just a missing join: searching the output for the word found
        # nothing, because neither fragment is the word.
        page, region = _page_with_lines("forests on the Coroman-", "del coast, south India.")

        text = _region_text(page, region)

        assert "Coroman-" not in text
        assert "Coroman del" not in text  # the line break must go with the hyphen

    def test_the_rest_of_the_region_is_unharmed(self):
        page, region = _page_with_lines("forests on the Coroman-", "del coast, south India.")

        assert "south India." in _region_text(page, region)


class TestTheJoinFollowsTheSameRulesAsEverywhereElse:
    def test_a_capitalised_continuation_keeps_its_hyphen(self):
        # "Anglo-Saxon" is a real compound that happens to break at its hyphen.
        page, region = _page_with_lines("the history of Anglo-", "Saxon settlement")

        assert "Anglo-Saxon" in _region_text(page, region)

    @pytest.mark.parametrize(
        ("first", "second"),
        [
            pytest.param("forests on the Coroman-", "del coast, south India.", id="merged"),
            pytest.param("the history of Anglo-", "Saxon settlement", id="compound-keeps-hyphen"),
            pytest.param("during the COVID-", "19 pandemic", id="digit-continuation-left-alone"),
            pytest.param("Plant biodiversity and", "conservation of forests", id="no-hyphen"),
        ],
    )
    def test_the_region_reads_the_same_as_ordinary_prose(self, first, second):
        """The actual requirement: same text either way, not some ideal text.

        Asserting an ideal outcome got this wrong once -- ``COVID-`` + ``19`` was expected
        to come back as ``COVID-19`` and comes back as ``COVID- 19``, because a digit
        continuation is deliberately not merged and the line join then puts a space in.
        Ordinary prose does exactly the same thing, so that is a quirk of the line join
        shared by both paths, not something this fallback does wrong.
        """
        from io import BytesIO

        from all2md import to_markdown

        page, region = _page_with_lines(first, second)
        as_prose = to_markdown(BytesIO(_pdf_bytes(first, second)), source_format="pdf").strip()

        assert _region_text(page, region) == as_prose

    def test_the_option_is_respected(self):
        # merge_hyphenated_words is off, so the region keeps what the page printed.
        page, region = _page_with_lines("forests on the Coroman-", "del coast, south India.")

        assert "Coroman-" in _region_text(page, region, merge_hyphenated_words=False)


class TestTheRestOfTheFallbackIsUnchanged:
    def test_separate_lines_are_still_joined_by_a_space(self):
        page, region = _page_with_lines("Plant biodiversity and", "conservation of forests")

        assert "biodiversity and conservation" in _region_text(page, region)

    def test_a_region_with_no_text_still_yields_nothing(self):
        page, region = _page_with_lines("text well below the region")
        empty = pymupdf.Rect(0, 0, 20, 20)

        converter = PdfToAstConverter(options=PdfOptions())

        assert converter._region_text_as_paragraph(page, empty, 0) is None
