#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_layout_region_tables.py
"""Recovering borderless tables from layout-predicted regions, without shredding prose.

PyMuPDF's default ``find_tables()`` strategy wants ruling lines on both axes. Journal tables
are typically booktabs-style -- horizontal rules only, or none -- so the default finds nothing
in them. Measured on the PMC born-digital corpus, it recovered **0 of 31** regions the layout
model predicted to be tables, and every one of those became a ``layout_region_not_tabular``
event. The diagnosis that matters: those events were a *detection* failure, not guards
rejecting grids they had found.

``strategy="text"``, which infers columns from glyph alignment, recovered a >=2x2 grid in all
31. But it has no ruling lines corroborating it, and the layout model over-fires: on a
mis-predicted region it turned a page of abstract prose into a seven-column table whose
columns cut through words ("study was condu | cted to explore", "micronutr | ients in the").
That is far worse output than the paragraph it replaced, and no table-shaped metric catches
it -- the table scores went *up* while whole-article recall fell from 92.6% to 83.8%.

Grid shape (rows, columns, fill ratio, words per cell), reading-order preservation, and region
corroboration (ruling lines, a "Table N" caption) were each measured as candidate guards and
each failed, with near-identical distributions for real tables and gridded prose. What
separates them is whether the columns cut through words, which is what these tests pin.
"""

from __future__ import annotations

import pytest

from all2md.ast import Paragraph as AstParagraph
from all2md.ast import Table as AstTable
from all2md.parsers._pdf_tables import MAX_SPLIT_WORD_RATIO, TABLE_REGION_STRATEGIES, split_word_ratio
from all2md.parsers.pdf import PdfToAstConverter

pytestmark = [pytest.mark.unit, pytest.mark.pdf, pytest.mark.table]


class _FakeTable:
    def __init__(self, grid: list[list[str | None]], bbox: tuple[float, float, float, float]) -> None:
        self._grid = grid
        self.bbox = bbox

    def extract(self) -> list[list[str | None]]:
        return self._grid


class _FakeTables:
    def __init__(self, tables: list[_FakeTable]) -> None:
        self.tables = tables


class _FakePage:
    """A page whose ``find_tables`` answers per strategy, as PyMuPDF's does."""

    def __init__(self, text: str, by_strategy: dict[str, list[_FakeTable]] | None = None) -> None:
        self._text = text
        self._by_strategy = by_strategy or {}
        self.strategies_tried: list[str] = []

    def get_textbox(self, rect) -> str:
        return self._text

    def get_text(self, kind: str, **kwargs):
        assert kind == "words", "the split-word guard reads word segmentation"
        assert "clip" not in kwargs, "clipping truncates boundary words and fabricates fragments"
        return [(0.0, 0.0, 1.0, 1.0, word, 0, 0, 0) for word in self._text.split()]

    def find_tables(self, clip=None, strategy: str = "lines_strict"):
        self.strategies_tried.append(strategy)
        return _FakeTables(self._by_strategy.get(strategy, []))


@pytest.fixture
def converter() -> PdfToAstConverter:
    conv = PdfToAstConverter()
    conv._tables_rejected = 0
    return conv


def _rejection_reasons(converter: PdfToAstConverter) -> list[str]:
    """The ``detail`` of every ``table_rejected`` event, in the order recorded.

    Asserting on the counter alone cannot see a region rejected twice under two different
    reasons, which is precisely the defect these tests pin.
    """
    events = converter.__dict__.get("_degraded_events", [])
    return [event.detail for event in events if event.kind == "table_rejected"]


def _rect(*values: float):
    import pymupdf

    return pymupdf.Rect(*values)


# A booktabs table: real columns, whole words in every cell.
BORDERLESS_TABLE = [["Variables", "AUC", "Sensitivity"], ["25(OH)D3", "0.901", "0.88"], ["Mg", "0.774", "0.71"]]
BORDERLESS_TEXT = "Variables AUC Sensitivity 25(OH)D3 0.901 0.88 Mg 0.774 0.71"

# The abstract that the layout model mis-predicted, gridded by text alignment. Its column
# boundary falls inside words, which is the thing that distinguishes it.
SHREDDED_PROSE = [
    ["Keywords:", "Objectives: The present", "study was condu", "cted to explore"],
    ["COVID-19", "prediction and prevent", "ion of coronaviru", "s disease"],
]
PROSE_TEXT = "Keywords: Objectives: The present study was conducted to explore prediction and prevention of coronavirus disease COVID-19"


class TestSplitWordRatio:
    def test_a_faithful_grid_holds_whole_words(self):
        page = _FakePage(BORDERLESS_TEXT)
        assert split_word_ratio(page, BORDERLESS_TABLE) == 0.0

    def test_columns_cutting_through_words_leave_fragments(self):
        """Fragments like condu/cted are words nowhere on the page; that is the signal."""
        page = _FakePage(PROSE_TEXT)
        assert split_word_ratio(page, SHREDDED_PROSE) > MAX_SPLIT_WORD_RATIO

    def test_digits_are_never_counted_as_split_words(self):
        """A boundary inside a number yields two plausible numbers, so numeric tables must not trip."""
        page = _FakePage("Total 1234 5678")
        assert split_word_ratio(page, [["Total", "12", "34"], ["", "56", "78"]]) == 0.0

    def test_an_unreadable_page_does_not_reject_the_table(self):
        """On error the guard must abstain, not drop a table nothing has shown to be bad."""

        class _Broken(_FakePage):
            def get_text(self, kind: str, **kwargs):
                raise RuntimeError("no text layer")

        assert split_word_ratio(_Broken(BORDERLESS_TEXT), BORDERLESS_TABLE) == 0.0

    def test_a_grid_of_pure_punctuation_has_no_opinion(self):
        assert split_word_ratio(_FakePage("a b c"), [["-", "-"], ["", "."]]) == 0.0


class TestLayoutRegionExtraction:
    def test_text_alignment_recovers_a_table_the_line_strategies_miss(self, converter):
        """The headline fix: a borderless journal table stops being emitted as prose."""
        page = _FakePage(BORDERLESS_TEXT, {"text": [_FakeTable(BORDERLESS_TABLE, (0, 0, 100, 50))]})
        node = converter._extract_table_from_layout_region(page, _rect(0, 0, 100, 50), page_num=0)

        assert isinstance(node, AstTable), "a booktabs table has no ruling lines but is still a table"
        assert page.strategies_tried == ["lines_strict", "text"], "lines are tried first, text only as fallback"

    def test_a_grid_whose_columns_split_words_is_refused(self, converter):
        """Gridding prose is worse than leaving it alone, however tabular the result looks."""
        page = _FakePage(PROSE_TEXT, {"text": [_FakeTable(SHREDDED_PROSE, (0, 0, 100, 50))]})
        node = converter._extract_table_from_layout_region(page, _rect(0, 0, 100, 50), page_num=0)

        assert not isinstance(node, AstTable)
        assert isinstance(node, AstParagraph), "the region's text must survive as prose"

    def test_refusing_a_shredded_grid_keeps_every_word(self, converter):
        """Region text is already excluded from the ordinary blocks, so a refusal must demote, not delete."""
        page = _FakePage(PROSE_TEXT, {"text": [_FakeTable(SHREDDED_PROSE, (0, 0, 100, 50))]})
        node = converter._extract_table_from_layout_region(page, _rect(0, 0, 100, 50), page_num=0)

        assert isinstance(node, AstParagraph), f"the shredded grid was emitted as {type(node).__name__}"
        rendered = " ".join(text.content for text in node.content)
        for word in ("conducted", "coronavirus", "Objectives:"):
            assert word in rendered, f"refusing the shredded grid lost {word!r}"

    def test_the_split_word_guard_applies_only_to_text_alignment(self, converter):
        """Ruling lines are corroboration the text strategy lacks; a line-detected grid is not second-guessed.

        Its fragments come from hyphenation and ligatures, not from invented columns.
        """
        page = _FakePage(PROSE_TEXT, {"lines_strict": [_FakeTable(SHREDDED_PROSE, (0, 0, 100, 50))]})
        node = converter._extract_table_from_layout_region(page, _rect(0, 0, 100, 50), page_num=0)

        assert isinstance(node, AstTable)
        assert page.strategies_tried == ["lines_strict"], "a line-detected table stops the search"

    def test_a_region_with_no_grid_at_all_is_still_reported(self, converter):
        """The genuine detection failure keeps its own event, which is how the corpus was diagnosed."""
        page = _FakePage("just some prose here")
        node = converter._extract_table_from_layout_region(page, _rect(0, 0, 100, 50), page_num=0)

        assert isinstance(node, AstParagraph)
        assert converter._tables_rejected == 1
        assert page.strategies_tried == list(TABLE_REGION_STRATEGIES), "every strategy is tried before giving up"

    def test_a_guard_rejection_is_not_counted_twice(self, converter):
        """A grid found and then rejected has already recorded its specific reason.

        Adding ``layout_region_not_tabular`` on top counts the same region twice and takes a
        second bite out of the confidence score.
        """
        degenerate = [["one column"], ["still one column"]]
        page = _FakePage("one column still one column", {"lines_strict": [_FakeTable(degenerate, (0, 0, 100, 50))]})
        converter._extract_table_from_layout_region(page, _rect(0, 0, 100, 50), page_num=0)

        assert converter._tables_rejected == 1, "the degenerate-grid guard already recorded this region"
        assert _rejection_reasons(converter) == ["degenerate_grid"]

    def test_the_split_word_guard_rejection_is_not_counted_twice(self, converter):
        """The sibling arm of the test above, and the one where the double count really happened.

        The test above reaches the bottom of the method with ``found_grid`` already set,
        because ``lines_strict`` returned a grid that ``_process_table_to_ast`` then rejected.
        The split-word guard ``continue``s *before* that assignment, so the flag stayed false
        and every guarded rejection also recorded the vaguer ``layout_region_not_tabular`` --
        the exact case the note at the foot of the method forbids.

        The signature on the born-digital corpus is unmistakable: the two reasons appeared in
        exact 1:1 correspondence in every affected article (1/1, 4/4, 6/6, 12/12), which is
        one region counted twice rather than two regions rejected.
        """
        page = _FakePage(PROSE_TEXT, {"text": [_FakeTable(SHREDDED_PROSE, (0, 0, 100, 50))]})
        node = converter._extract_table_from_layout_region(page, _rect(0, 0, 100, 50), page_num=0)

        assert isinstance(node, AstParagraph), "the region's text must still survive as prose"
        assert _rejection_reasons(converter) == [
            "text_grid_splits_words"
        ], "the specific guard reports; the vaguer layout_region_not_tabular must not pile on"
        assert converter._tables_rejected == 1, "one region, one rejection, one hit to confidence"
