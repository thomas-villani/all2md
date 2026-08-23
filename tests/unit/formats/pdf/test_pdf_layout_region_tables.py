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

    def get_textpage(self, flags=None):
        """Real pages hand one to ``get_textbox`` so clipped-away glyphs stay out.

        This fake has no clipping paths, so the token it returns is never read.
        """
        return None

    def get_textbox(self, rect, textpage=None) -> str:
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


class _PositionedPage(_FakePage):
    """A page whose words carry real geometry, for the word-gutter pass."""

    def __init__(
        self,
        words: list[tuple],
        by_strategy: dict[str, list[_FakeTable]] | None = None,
        drawings: list[dict] | None = None,
    ) -> None:
        super().__init__(" ".join(word[4] for word in words), by_strategy)
        self._words = words
        self._drawings = drawings or []

    def get_text(self, kind: str, **kwargs):
        assert kind == "words"
        return list(self._words)

    def get_drawings(self):
        return list(self._drawings)


def _word(x0: float, y: float, text: str, width: float = 8.0) -> tuple:
    return (x0, y, x0 + width * max(1, len(text)) / 2, y + 10.0, text, 0, 0, 0)


def _booktabs_words() -> list[tuple]:
    """Three lines, three columns, 40pt gutters -- a borderless journal table's geometry."""
    columns = (10.0, 100.0, 180.0)
    rows = (
        ("Variables", "AUC", "Sensitivity"),
        ("Magnesium", "0.774", "0.71"),
        ("Vitamin", "0.901", "0.88"),
    )
    return [_word(columns[i], 10.0 + 20.0 * r, text) for r, row in enumerate(rows) for i, text in enumerate(row)]


def _prose_words() -> list[tuple]:
    """Justified prose: word gaps land at different x on every line, so no shared band is clear."""
    words = []
    for line_index in range(6):
        x = 10.0
        for word_index in range(12):
            text = f"w{line_index}{word_index}"
            entry = _word(x, 10.0 + 15.0 * line_index, text, width=6.0)
            words.append(entry)
            x = entry[2] + 2.0 + (line_index * 7 + word_index * 3) % 3
    return words


class TestWordGutterGrid:
    """The pure geometry: columns from gutters, whole words by construction."""

    def test_a_borderless_table_yields_its_grid(self):
        from all2md.parsers._pdf_tables import word_gutter_grid

        grid = word_gutter_grid(_booktabs_words())

        assert grid == [
            ["Variables", "AUC", "Sensitivity"],
            ["Magnesium", "0.774", "0.71"],
            ["Vitamin", "0.901", "0.88"],
        ]

    def test_prose_has_no_gutters(self):
        """Justified text aligns its outer edges but scatters its inner gaps."""
        from all2md.parsers._pdf_tables import word_gutter_grid

        assert word_gutter_grid(_prose_words()) is None

    def test_too_few_lines_cannot_corroborate_a_gutter(self):
        """With two lines, the space between any two words 'spans' the region."""
        from all2md.parsers._pdf_tables import word_gutter_grid

        two_lines = [entry for entry in _booktabs_words() if entry[1] < 45.0]
        assert word_gutter_grid(two_lines) is None

    def test_a_spanning_header_does_not_destroy_the_gutter(self):
        """One line in ten may cross a boundary: titles and footnotes span; columns survive.

        The spanning word itself lands whole in the column holding its center -- cut
        words are impossible here, which is the entire point of the pass.
        """
        from all2md.parsers._pdf_tables import word_gutter_grid

        columns = (10.0, 100.0, 180.0)
        words = [_word(10.0, 0.0, "SpanningTitleAcrossEverything", width=15.0)]
        for line in range(9):
            for column in columns:
                words.append(_word(column, 20.0 + 20.0 * line, f"c{line}", width=6.0))

        grid = word_gutter_grid(words)

        assert grid is not None
        assert len(grid) == 10
        assert all(len(row) == 3 for row in grid)
        assert (
            grid[0].count("SpanningTitleAcrossEverything") == 1
        ), "the spanning word stays whole in exactly one cell -- the column holding its center"

    def test_multiword_cells_join_in_reading_order(self):
        """Real multi-word cells put their word gaps at different x per line, unlike a gutter."""
        from all2md.parsers._pdf_tables import word_gutter_grid

        words = []
        for line in range(3):
            y = 10.0 + 20.0 * line
            first = _word(10.0, y, "left")
            words.extend(
                [
                    first,
                    _word(first[2] + 2.0 + 3.0 * line, y, "part"),
                    _word(120.0, y, "mid"),
                    _word(200.0, y, "right"),
                ]
            )

        grid = word_gutter_grid(words)

        assert grid == [["left part", "mid", "right"]] * 3

    def test_a_single_gutter_yields_a_two_column_grid(self):
        """One clear band is weak evidence, but the geometry no longer refuses it.

        Two-column admission moved from the sweep to the guards: measured on the PMC
        corpus (#389), the two-column population was 4 real tables against 8 junk
        regions, and every junk region is caught downstream -- 7 numbered reference
        lists by the bibliography guard, 1 chart by the drawing-density gate. Refusing
        the geometry outright cost the 4 real tables to save nothing the guards were
        not already saving.
        """
        from all2md.parsers._pdf_tables import word_gutter_grid

        rows = (("Male", "226"), ("Mean", "41"), ("Median", "38"), ("Deaths", "7"), ("Cured", "219"), ("Open", "0"))
        words = []
        for line, (label, value) in enumerate(rows):
            y = 10.0 + 15.0 * line
            words.extend([_word(10.0, y, label), _word(200.0, y, value)])

        grid = word_gutter_grid(words)

        assert grid == [list(row) for row in rows]


class TestWordGutterRegionExtraction:
    """The third pass in _extract_table_from_layout_region, behind the find_tables strategies."""

    def test_a_table_both_strategies_miss_is_recovered_from_word_boxes(self, converter):
        """The #386 headline: 56 of 63 missing corpus tables died after this point."""
        page = _PositionedPage(_booktabs_words())
        node = converter._extract_table_from_layout_region(page, _rect(0, 0, 300, 100), page_num=0)

        assert isinstance(node, AstTable)
        assert [cell.content[0].content for cell in node.header.cells] == ["Variables", "AUC", "Sensitivity"]
        assert len(node.rows) == 2
        assert converter._tables_rejected == 0, "recovering a table is not a rejection"

    def test_word_gutters_run_only_after_the_established_strategies(self, converter):
        """Additive by design: every grid the strategies already accept keeps its exact path."""
        page = _PositionedPage(_booktabs_words(), {"lines_strict": [_FakeTable(BORDERLESS_TABLE, (0, 0, 100, 50))]})
        node = converter._extract_table_from_layout_region(page, _rect(0, 0, 300, 100), page_num=0)

        assert isinstance(node, AstTable)
        assert [cell.content[0].content for cell in node.header.cells] == BORDERLESS_TABLE[0]

    def test_prose_still_falls_through_to_a_paragraph(self, converter):
        page = _PositionedPage(_prose_words())
        node = converter._extract_table_from_layout_region(page, _rect(0, 0, 300, 100), page_num=0)

        assert isinstance(node, AstParagraph)
        assert _rejection_reasons(converter) == ["layout_region_not_tabular"]

    def test_a_gutter_grid_killed_by_a_guard_is_counted_once(self, converter):
        """Same accounting rule as the other strategies: the specific reason, recorded once."""
        words = []
        for line in range(3):
            y = 10.0 + 20.0 * line
            words.extend([_word(10.0, y, "na"), _word(120.0, y, "na"), _word(200.0, y, "na")])
        page = _PositionedPage(words)
        node = converter._extract_table_from_layout_region(page, _rect(0, 0, 300, 100), page_num=0)

        assert isinstance(node, AstParagraph)
        assert _rejection_reasons(converter) == ["uniform_cells"]
        assert converter._tables_rejected == 1


class TestContinuationLineMerging:
    """A wrapped cell folds into its logical row instead of splitting into fake rows."""

    def test_a_line_with_an_empty_anchor_cell_merges_up(self):
        from all2md.parsers._pdf_tables import word_gutter_grid

        columns = (10.0, 100.0, 180.0)
        words = []
        for line in range(4):
            y = 10.0 + 20.0 * line
            words.extend(_word(column, y, f"r{line}") for column in columns)
        # a wrap line under row 1: only the middle column continues
        words.append(_word(100.0, 35.0, "wrapped"))

        grid = word_gutter_grid(words)

        assert grid is not None
        assert len(grid) == 4, "the wrap line is a continuation, not a row"
        assert grid[1][1] == "r1\nwrapped", "fragments join with a newline for hyphenation repair"

    def test_a_dense_numeric_table_keeps_its_per_line_rows(self):
        from all2md.parsers._pdf_tables import word_gutter_grid

        grid = word_gutter_grid(_booktabs_words())

        assert grid is not None and len(grid) == 3

    def test_gap_jump_names_the_rows_when_wrap_and_row_leading_separate(self):
        """Wraps sit one leading below their row; the next row sits leading plus padding.

        Measured on the PMC corpus: wraps at 1.0-1.3pt against rows at 2.0-6.1pt. The
        continuation lines here keep their anchor cell FILLED (the label wraps too), so
        the anchor rule alone cannot merge them -- the geometry must.
        """
        from all2md.parsers._pdf_tables import word_gutter_grid

        columns = (10.0, 100.0, 180.0)
        words = []
        y = 10.0
        for row in range(3):
            for column, text in zip(columns, (f"Label{row}", f"description{row}", f"outcome{row}"), strict=True):
                words.append(_word(column, y, text))
            wrap_y = y + 10.0 + 1.0  # one tight leading below: the wrapped fragment
            words.append(_word(10.0, wrap_y, f"wrapped{row}"))
            words.append(_word(100.0, wrap_y, f"more{row}"))
            y = wrap_y + 10.0 + 6.0  # leading plus row padding: the next logical row
        grid = word_gutter_grid(words)

        assert grid is not None
        assert len(grid) == 3, "six printed lines are three logical rows"
        assert grid[0][0] == "Label0\nwrapped0"
        assert grid[0][1] == "description0\nmore0"

    def test_a_parallel_prose_panel_table_collapses_to_its_two_rows(self):
        """Three narrative columns under one header: 8 printed lines, 2 logical rows."""
        from all2md.parsers._pdf_tables import word_gutter_grid

        columns = (10.0, 150.0, 290.0)
        words = [
            _word(column, 10.0, head) for column, head in zip(columns, ("Hospital", "Clinic", "Home"), strict=True)
        ]
        y = 10.0 + 10.0 + 6.0  # header seam: leading plus padding
        for line in range(7):
            for column in columns:
                words.append(_word(column, y, f"story{line}"))
            y += 10.0 + 1.0  # uniform tight leading throughout the body
        grid = word_gutter_grid(words)

        assert grid is not None
        assert len(grid) == 2, "uniform body leading under one header seam is two rows"
        assert grid[1][0].split("\n") == [f"story{line}" for line in range(7)]

    def test_the_header_seam_jump_does_not_fuse_numeric_data_rows(self):
        """The header seam is a qualifying jump; believing it would fuse the data rows.

        Two adjacent mostly-numeric lines abort the grouping, and per-line rows stand.
        """
        from all2md.parsers._pdf_tables import word_gutter_grid

        columns = (10.0, 100.0, 180.0, 260.0)
        words = [_word(column, 10.0, head) for column, head in zip(columns, ("Q", "Range", "Mean", "SD"), strict=True)]
        y = 10.0 + 10.0 + 14.0  # a big header seam, the only qualifying jump
        for row in range(4):
            for column, text in zip(columns, (f"item{row}", "0-9", "6.67", "1.3"), strict=True):
                words.append(_word(column, y, text))
            y += 10.0 + 4.0  # row gaps too uniform to qualify on their own
        grid = word_gutter_grid(words)

        assert grid is not None
        assert len(grid) == 5, "numeric rows must not fuse under the header-seam jump"

    def test_a_single_column_wrap_below_median_gap_merges_up(self):
        """The fill shape the anchor rule cannot see.

        The wrap lives IN the anchor column while every other column is empty ('Length
        of incubation period in' / 'days'), sitting tighter than the median gap.
        """
        from all2md.parsers._pdf_tables import word_gutter_grid

        columns = (10.0, 150.0, 230.0)
        words = []
        y = 10.0
        for row in range(4):
            for column, text in zip(columns, (f"question{row}", "6.67", "1.3"), strict=True):
                words.append(_word(column, y, text))
            if row == 1:
                y += 10.0 + 4.0  # the wrap sits tighter than this table's rows...
                words.append(_word(10.0, y, "days"))
            y += 10.0 + 4.4  # ...which are separated too uniformly for a gap jump
        grid = word_gutter_grid(words)

        assert grid is not None
        assert len(grid) == 4
        assert grid[1][0] == "question1\ndays"

    def test_a_sparse_row_label_column_anchors_a_heavily_wrapped_table(self):
        """Uniform leading end to end, so the rows are named by fill, not geometry.

        The label column is filled only on row starts. The 20%-floor anchor merges each
        row's wraps; the numeric-fusion guard keeps this from firing on data columns.
        """
        from all2md.parsers._pdf_tables import word_gutter_grid

        columns = (10.0, 80.0, 200.0)
        words = []
        y = 10.0
        for row in range(3):
            for line in range(4):
                if line == 0:
                    words.append(_word(10.0, y, f"GENE{row}"))
                words.append(_word(columns[1], y, f"describes{row}{line}"))
                words.append(_word(columns[2], y, f"relevance{row}{line}"))
                y += 10.0 + 2.6  # the same leading between wraps and between rows
        grid = word_gutter_grid(words)

        assert grid is not None
        assert len(grid) == 3, "rows are named by the sparse label column, not the leading"
        assert grid[0][0] == "GENE0"
        assert grid[0][1].split("\n") == [f"describes0{line}" for line in range(4)]

    def test_a_sparse_numeric_column_is_not_mistaken_for_a_row_label(self):
        """A sparse first column must not anchor a merge that fuses numeric rows.

        Grouped-label tables have exactly this shape, and their data rows are real rows.
        """
        from all2md.parsers._pdf_tables import word_gutter_grid

        columns = (10.0, 100.0, 180.0)
        words = []
        y = 10.0
        for group in range(2):
            for line in range(4):
                if line == 0:
                    words.append(_word(10.0, y, f"Group{group}"))
                words.append(_word(columns[1], y, "0.774"))
                words.append(_word(columns[2], y, "226"))
                y += 10.0 + 2.0
        grid = word_gutter_grid(words)

        assert grid is not None
        assert len(grid) == 8, "adjacent numeric rows stay separate rows"


class TestNumberedBibliography:
    def test_a_numbered_reference_grid_is_condemned(self):
        from all2md.parsers._pdf_tables import looks_like_numbered_bibliography

        citation = "Smith AB Jones CD Telehealth for global emergencies implications for disease study"
        grid = [[f"{n}.", citation] for n in range(41, 50)]

        assert looks_like_numbered_bibliography(grid)

    def test_a_paren_numbered_reference_grid_is_condemned(self):
        """``42)`` numbers its entries as surely as ``42.`` does.

        Measured: the one reference list the guard missed on the PMC corpus
        numbered its entries with exactly this paren form.
        """
        from all2md.parsers._pdf_tables import looks_like_numbered_bibliography

        citation = "Ng F Pushing back the retirement age by department of statistics labour force report"
        grid = [[f"{n})", citation] for n in range(2, 11)]

        assert looks_like_numbered_bibliography(grid)

    def test_a_real_table_with_a_sequential_number_column_is_not(self):
        """Sequential numbering alone describes plenty of real tables; the cells decide."""
        from all2md.parsers._pdf_tables import looks_like_numbered_bibliography

        grid = [[f"{n}", "TP53", "0.901", "significant"] for n in range(1, 12)]

        assert not looks_like_numbered_bibliography(grid)

    def test_prose_cells_without_numbering_are_not(self):
        from all2md.parsers._pdf_tables import looks_like_numbered_bibliography

        long_cell = "a description column can hold a full sentence of explanatory text per row easily"
        grid = [["ACE2", long_cell, "yes"] for _ in range(8)]

        assert not looks_like_numbered_bibliography(grid)

    def test_the_region_extractor_demotes_a_bibliography_to_prose(self, converter):
        """The worst false positive is a gridded bibliography.

        Row-major cells interleave the page's columns and scramble every citation --
        measured, one gridded bibliography cost an article 15 of its 21 citation titles.

        Geometry: two page columns, each a numbered citation whose intra-citation word
        gaps are narrow and jittered per line (real justified text), so the only shared
        gutters are the number-text gaps and the page column separator.
        """
        words = []
        for line in range(9):
            y = 10.0 + 15.0 * line
            for half, number in ((10.0, 41 + line), (300.0, 50 + line)):
                words.append(_word(half, y, f"{number}.", width=8.0))
                x = half + 30.0
                for index in range(10):
                    entry = _word(x, y, f"w{line}{index}", width=8.0)
                    words.append(entry)
                    x = entry[2] + 2.0 + (line * 5 + index * 3) % 2
        page = _PositionedPage(words)

        node = converter._extract_table_from_layout_region(page, _rect(0, 0, 600, 200), page_num=0)

        assert not isinstance(node, AstTable)
        assert _rejection_reasons(converter) == ["numbered_bibliography"]


def _two_column_words() -> list[tuple]:
    """A label/value table: six lines, one 100pt gutter, varied cell text."""
    rows = (
        ("Male", "226"),
        ("Mean", "41"),
        ("Median", "38"),
        ("Deaths", "7"),
        ("Cured", "219"),
        ("Open", "0"),
    )
    words = []
    for line, (label, value) in enumerate(rows):
        y = 10.0 + 15.0 * line
        words.extend([_word(10.0, y, label), _word(200.0, y, value)])
    return words


def _dense_drawings(count: int = 100) -> list[dict]:
    """Vector paths inside the region, the way a chart's plot lines sit under its labels."""
    return [{"rect": (20.0 + i, 20.0, 22.0 + i, 80.0), "items": []} for i in range(count)]


class TestTwoColumnAdmission:
    """One gutter admits a grid only when the region cannot be a chart or a reference list.

    Measured on the PMC corpus (#389): the two-column population is 4 real tables,
    7 numbered reference lists, and 1 chart whose axis ticks and legend gridded.
    The reference lists fall to the bibliography guard; the chart is the shape this
    drawing-density gate exists for -- its region held 541 vector paths where the
    real two-column tables held 0-4 (their own ruling lines).
    """

    def test_a_two_column_table_is_recovered(self, converter):
        page = _PositionedPage(_two_column_words())
        node = converter._extract_table_from_layout_region(page, _rect(0, 0, 300, 120), page_num=0)

        assert isinstance(node, AstTable)
        assert [cell.content[0].content for cell in node.header.cells] == ["Male", "226"]
        assert len(node.rows) == 5
        assert converter._tables_rejected == 0

    def test_a_two_column_grid_over_dense_drawings_is_demoted(self, converter):
        page = _PositionedPage(_two_column_words(), drawings=_dense_drawings())
        node = converter._extract_table_from_layout_region(page, _rect(0, 0, 300, 120), page_num=0)

        assert not isinstance(node, AstTable)
        assert _rejection_reasons(converter) == ["two_column_chart_region"]

    def test_dense_drawings_do_not_touch_wider_grids(self, converter):
        """The gate is scoped to the single-gutter tier.

        Two aligned internal boundaries do not happen to a chart's stray labels,
        so no established multi-column path changes behavior.
        """
        page = _PositionedPage(_booktabs_words(), drawings=_dense_drawings())
        node = converter._extract_table_from_layout_region(page, _rect(0, 0, 300, 100), page_num=0)

        assert isinstance(node, AstTable)

    def test_a_two_column_paren_numbered_reference_list_is_demoted(self, converter):
        """The junk shape the old column threshold existed for, on its worst spelling."""
        words = []
        for line in range(9):
            y = 10.0 + 15.0 * line
            words.append(_word(10.0, y, f"{2 + line})", width=8.0))
            x = 60.0
            for index in range(10):
                entry = _word(x, y, f"w{line}{index}", width=8.0)
                words.append(entry)
                x = entry[2] + 2.0 + (line * 5 + index * 3) % 2
        page = _PositionedPage(words)

        node = converter._extract_table_from_layout_region(page, _rect(0, 0, 400, 200), page_num=0)

        assert not isinstance(node, AstTable)
        assert _rejection_reasons(converter) == ["numbered_bibliography"]


def _rotated_words(clockwise: bool) -> list[tuple]:
    """The booktabs table's words, laid out as a landscape table on a portrait page.

    Rotating the 3x3 upright table maps each printed line to a vertical run of tall
    boxes. Clockwise text reads top-to-bottom and stacks its lines right-to-left;
    counter-clockwise reads bottom-to-top and stacks left-to-right. Stream coordinates
    ``(block, line, word)`` follow reading order in both, exactly as PyMuPDF's do.
    """
    rows = (
        ("Variables", "AUC", "Sensitivity"),
        ("Magnesium", "0.774", "0.71"),
        ("Vitamin", "0.901", "0.88"),
    )
    words = []
    for line_index, row in enumerate(rows):
        # Lines stack along x: later lines further left when clockwise.
        x = (100.0 - 20.0 * line_index) if clockwise else (10.0 + 20.0 * line_index)
        position = 10.0
        for word_index, text in enumerate(row):
            height = 4.0 * len(text)
            if clockwise:
                box = (x, position, x + 10.0, position + height)
            else:
                box = (x, 300.0 - position - height, x + 10.0, 300.0 - position)
            words.append((*box, text, 0, line_index, word_index))
            position += height + 24.0
        # Words within a line advance +y when clockwise, -y when counter-clockwise.
    return words


class TestRotatedRegions:
    def test_a_clockwise_rotated_table_is_recovered_in_its_own_frame(self):
        """The transposed sweep grids a landscape table the page frame would scramble.

        Measured before the transposed pass existed: a rotated 28x4 truth table came
        back 8x12 with its containment destroyed. Now the same sweep runs against the
        transposed boxes, so the grid comes out in the table's own reading order.
        """
        from all2md.parsers._pdf_tables import word_gutter_grid

        grid = word_gutter_grid(_rotated_words(clockwise=True))
        assert grid is not None
        assert grid[0] == ["Variables", "AUC", "Sensitivity"]
        assert grid[1][0] == "Magnesium"
        assert grid[2][2] == "0.88"

    def test_both_rotation_directions_yield_the_same_grid(self):
        """Transposing is a reflection, so one direction needs a mirrored axis.

        Which axis depends on clockwise versus counter-clockwise -- undecidable from
        the boxes alone, decided here by the words' stream order. Getting it wrong
        does not merely mis-shape the grid: it reverses the rows or the columns, and
        every cell lands in the wrong place.
        """
        from all2md.parsers._pdf_tables import word_gutter_grid

        clockwise = word_gutter_grid(_rotated_words(clockwise=True))
        counter = word_gutter_grid(_rotated_words(clockwise=False))
        assert clockwise is not None
        assert clockwise == counter

    def test_marginally_tall_boxes_are_declined_not_transposed(self):
        """Near-square boxes are weak evidence, and weak evidence declines.

        Transposing on weak evidence is worse than declining: upright text's line
        spacing becomes perfect fake "gutters" in the transposed frame. Measured on
        the PMC corpus: real rotated table words sit at median aspect 2.5-2.7, a
        mixed-orientation region that must not be transposed at 1.05. This region
        stays with the prose path, exactly as before the transposed pass existed.
        """
        from all2md.parsers._pdf_tables import word_gutter_grid

        words = []
        for column in range(4):
            x = 10.0 + 30.0 * column
            for row in range(8):
                y = 10.0 + 40.0 * row
                # taller than wide, but only just: ambiguous orientation
                words.append((x, y, x + 30.0, y + 34.0, f"word{column}{row}", 0, 0, 0))

        assert word_gutter_grid(words) is None
