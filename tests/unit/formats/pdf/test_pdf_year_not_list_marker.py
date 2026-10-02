#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_year_not_list_marker.py
"""A year at the start of a line is not an ordered-list marker.

A reference whose year wraps onto a line of its own ("... Wageningen Press;" then
"2001.") was read as an ordered list starting at 2001, holding one empty item
(PMC2500011.1 in the PMC development corpus). A list number has at most three digits.
"""

from __future__ import annotations

import pytest

from all2md.ast.nodes import List, SourceLocation, Text
from all2md.ast.nodes import Paragraph as AstParagraph
from all2md.options.pdf import PdfOptions
from all2md.parsers.pdf import PdfToAstConverter

pytestmark = [pytest.mark.unit, pytest.mark.pdf]


def _para(text: str) -> AstParagraph:
    return AstParagraph(
        content=[Text(content=text)],
        source_location=SourceLocation(format="pdf", page=1, metadata={"bbox": [54.0, 100.0, 295.0, 112.0]}),
    )


@pytest.mark.parametrize("text", ["2001. ", "2001. Wageningen Press.", "1999) see above", "12345. x"])
def test_four_or_more_digits_are_not_a_marker(text):
    assert PdfToAstConverter._is_valid_list_marker(text) == (False, None)


@pytest.mark.parametrize("text", ["1. First", "42) Answer", "999. Last reference"])
def test_up_to_three_digits_are_a_marker(text):
    assert PdfToAstConverter._is_valid_list_marker(text) == (True, "ordered")


def test_a_wrapped_reference_year_stays_prose():
    converter = PdfToAstConverter(options=PdfOptions())
    nodes = [_para("2. Brand A: Herd Health. Wageningen: Wageningen Press;"), _para("2001. ")]

    grouped = converter._convert_paragraphs_to_lists(nodes)

    assert not any(isinstance(node, List) and (node.start or 1) >= 1000 for node in grouped)
    assert "2001." in "".join(
        t.content for node in grouped for t in getattr(node, "content", []) if isinstance(t, Text)
    )
