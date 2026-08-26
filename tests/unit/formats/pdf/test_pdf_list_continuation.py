#  Copyright (c) 2025 Tom Villani, Ph.D.
"""A list item's wrapped lines are not new paragraphs (#442).

``_should_merge_with_accumulated`` used to refuse any merge touching a list item.
That is right for two *items* -- two items are two items -- but it also strands
every line a long item wraps onto. A numbered bibliography is a list of long
items, so a reference's title and journal arrived as separate blocks from its
authors, and the hyphenation repair that runs at a merged seam never got to run.

Measured over 8,183 merge decisions on twelve dev-corpus articles: 151 of the 325
blocks that end mid-sentence are stranded this way, and 98% of them sit 0.5-3.8pt
below the item -- the same geometry as the wraps this method already merges
(median 1.98pt, 95th percentile 3.67pt).

A negative gap is the one shape refused. Under ordinary prose a block starting
*above* its predecessor is the foot of one column meeting the head of the next;
under a list item, across the sample, it was 8 page or column breaks -- one of
them 287pt -- where "just below" means nothing.
"""

import pytest

from all2md.ast.nodes import Paragraph, SourceLocation, Text
from all2md.parsers.pdf import PdfToAstConverter

pytestmark = [pytest.mark.unit, pytest.mark.pdf]


def _para(text: str, top: float, bottom: float, *, is_list_item: bool = False) -> Paragraph:
    """A paragraph as the PDF parser produces one, at a given vertical position."""
    metadata: dict = {"bbox": [50.0, top, 280.0, bottom]}
    if is_list_item:
        metadata["is_list_item"] = True
    return Paragraph(
        content=[Text(content=text)],
        source_location=SourceLocation(format="pdf", page=1, metadata=metadata),
    )


def _merge(nodes: list[Paragraph]) -> list[str]:
    merged = PdfToAstConverter()._merge_adjacent_paragraphs(nodes)
    return ["".join(t.content for t in node.content if isinstance(t, Text)) for node in merged]


class TestAListItemKeepsItsWrappedLines:
    def test_a_continuation_just_below_joins_its_item(self) -> None:
        """The regression: 2.74pt below is a wrap, not a new paragraph."""
        nodes = [
            _para("1. Smith AB, Jones CD, Karlin K. D. & Hoffman B. M.", 100.0, 110.0, is_list_item=True),
            _para("Opportunities and challenges for a sustainable", 112.74, 122.74),
        ]

        assert _merge(nodes) == [
            "1. Smith AB, Jones CD, Karlin K. D. & Hoffman B. M. Opportunities and challenges for a sustainable"
        ]

    def test_a_second_continuation_joins_too(self) -> None:
        """A reference wraps onto three lines as readily as two."""
        nodes = [
            _para("42. Andreassen KH, Dahl C and Andersen JT", 100.0, 110.0, is_list_item=True),
            _para("Mineral extraction from seawater with", 112.7, 122.7),
            _para("selective separation. J Chem 2019;4:1-9.", 125.4, 135.4),
        ]

        assert len(_merge(nodes)) == 1

    def test_a_hyphen_is_repaired_across_the_seam(self) -> None:
        """The seam repair only runs where a merge happens, so it never ran here.

        This is the sub-case #442 folded in: a word broken at a block boundary is
        out of ``dehyphenate_blocks``'s reach by construction, because that works
        within a block.
        """
        nodes = [
            _para("7. Effects of electro-chemical transcrip-", 100.0, 110.0, is_list_item=True),
            _para("tion factor binding", 112.7, 122.7),
        ]

        assert "transcription factor" in _merge(nodes)[0]


class TestWhatStillWillNotMerge:
    def test_a_new_list_item_stays_its_own_block(self) -> None:
        """Two items are two items, however tightly they are set."""
        nodes = [
            _para("1. The first reference of the list", 100.0, 110.0, is_list_item=True),
            _para("2. The second reference of the list", 112.7, 122.7, is_list_item=True),
        ]

        assert len(_merge(nodes)) == 2

    def test_a_list_item_under_prose_stays_its_own_block(self) -> None:
        """A list opening under a paragraph starts a block even at a tight gap."""
        nodes = [
            _para("The study considered three factors.", 100.0, 110.0),
            _para("1. The first of the three factors", 112.7, 122.7, is_list_item=True),
        ]

        assert len(_merge(nodes)) == 2

    def test_a_block_above_the_item_does_not_join_it(self) -> None:
        """A negative gap is a column or page break, not a wrap.

        Across the sample every one of these was exactly that -- the largest 287pt
        -- so under a list item "just below" is required, not merely "close".
        """
        nodes = [
            _para("9. The last reference at the foot of a column", 700.0, 710.0, is_list_item=True),
            _para("Introduction text at the head of the next", 90.0, 100.0),
        ]

        assert len(_merge(nodes)) == 2

    def test_a_paragraph_a_clear_gap_below_stays_separate(self) -> None:
        """The wrap test is still a gap test: 20pt below the item is a new block."""
        nodes = [
            _para("3. A reference that ends here.", 100.0, 110.0, is_list_item=True),
            _para("A following paragraph of body prose", 130.0, 140.0),
        ]

        assert len(_merge(nodes)) == 2

    def test_a_continuation_without_geometry_stays_separate(self) -> None:
        """Admission rests on the geometry, so no geometry means no admission."""
        nodes = [
            _para("5. A reference with a bbox", 100.0, 110.0, is_list_item=True),
            Paragraph(content=[Text(content="a continuation with none")], source_location=None),
        ]

        assert len(_merge(nodes)) == 2
