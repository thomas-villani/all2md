#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_ruling_table_guards.py
"""The ruling-line fallback detector must never delete a region's text either.

``test_pdf_table_guards.py`` pins this down for the ``find_tables()`` path. The
ruling-line fallback -- the detector that reads a page's stroked lines directly -- has
exactly the same ordering trap and had none of the same protection: text under any rect
in ``table_info`` is removed from the ordinary text blocks *before* extraction runs, so
every ``return None`` in ``_extract_table_from_ruling_rect`` dropped a whole framed
region on the floor.

The synthetic page below (a stroked frame with one internal rule and a sentence in the
bottom-left cell) produced **no output at all** under
``table_detection_mode="ruling"``: the grid was 75% empty, the sparsity guard rejected
it, and the sentence went with it. The conversion still reported success.
"""

from __future__ import annotations

import io

import pytest

from all2md.ast import Paragraph as AstParagraph
from all2md.ast import Table as AstTable
from all2md.ast.utils import extract_text
from all2md.options.pdf import PdfOptions
from all2md.parsers.pdf import PdfToAstConverter

pytestmark = [pytest.mark.unit, pytest.mark.pdf, pytest.mark.table]

pymupdf = pytest.importorskip("pymupdf")


class _RuledRegion:
    """A framed region with a text grid, addressable the way the ruling path asks for it.

    ``_extract_table_from_ruling_rect`` reads one cell rectangle at a time and then, when
    it rejects the grid, asks for the whole region -- so the region's text here is the
    union of its cells', exactly as a real page's would be.
    """

    def __init__(self, cells: list[list[str]], xs: list[float], ys: list[float]) -> None:
        self.cells = cells
        self.xs = xs
        self.ys = ys

    @property
    def h_lines(self) -> list[tuple]:
        return [(self.xs[0], y, self.xs[-1], y) for y in self.ys]

    @property
    def v_lines(self) -> list[tuple]:
        return [(x, self.ys[0], x, self.ys[-1]) for x in self.xs]

    @property
    def rect(self):
        return pymupdf.Rect(self.xs[0], self.ys[0], self.xs[-1], self.ys[-1])

    def get_textbox(self, rect) -> str:
        for row, (y0, y1) in enumerate(zip(self.ys, self.ys[1:], strict=False)):
            for col, (x0, x1) in enumerate(zip(self.xs, self.xs[1:], strict=False)):
                if (rect.x0, rect.y0, rect.x1, rect.y1) == (x0, y0, x1, y1):
                    return self.cells[row][col]
        # Anything else is the whole-region query the rejection paths make.
        return "\n".join(" ".join(cell for cell in row if cell) for row in self.cells)


def _grid(cells: list[list[str]]) -> _RuledRegion:
    """A region whose ruling lines bound exactly ``cells``."""
    n_rows = len(cells)
    n_cols = len(cells[0])
    return _RuledRegion(
        cells,
        xs=[72.0 + 80.0 * i for i in range(n_cols + 1)],
        ys=[100.0 + 40.0 * i for i in range(n_rows + 1)],
    )


def _extract(converter: PdfToAstConverter, region: _RuledRegion):
    return converter._extract_table_from_ruling_rect(region, region.rect, region.h_lines, region.v_lines, page_num=0)


@pytest.fixture
def converter() -> PdfToAstConverter:
    conv = PdfToAstConverter()
    conv._tables_rejected = 0
    return conv


# Each grid fires exactly one rejection branch under the default thresholds
# (empty > 0.70, uniform >= 5 filled, dot-leader > 0.30).
MOSTLY_EMPTY = [["alpha beta", ""], ["", ""]]
UNIFORM = [["X", "X", "X"], ["X", "X", "X"], ["X", "X", "X"]]
DOT_LEADER = [["Introduction", ".........."], ["Methods", ".........."]]

REAL_GRID = [["Model", "Score"], ["baseline", "0.62"]]


@pytest.mark.parametrize(
    ("cells", "rejection"),
    [
        pytest.param(MOSTLY_EMPTY, "mostly_empty", id="mostly-empty"),
        pytest.param(UNIFORM, "uniform_cells", id="uniform"),
        pytest.param(DOT_LEADER, "dot_leader_toc", id="dot-leader-toc"),
    ],
)
def test_every_ruling_rejection_branch_demotes_to_prose(converter, cells, rejection):
    """A rejected ruling-line region comes back as prose, not as nothing.

    Its text has already been excluded from the page's text blocks by the time this
    runs, so ``None`` here is a deletion.
    """
    region = _grid(cells)
    node = _extract(converter, region)

    assert not isinstance(node, AstTable), f"a {rejection} region is not a real table"
    assert isinstance(node, AstParagraph), f"{rejection} must demote to prose, not delete (returned {node!r})"

    recovered = extract_text(node).split()
    for word in " ".join(" ".join(row) for row in cells).split():
        assert word in recovered, f"rejecting the {rejection} region lost the word {word!r}"
    assert converter._tables_rejected == 1, f"{rejection} demotion must be recorded for the quality card"


def test_a_real_ruled_grid_is_still_a_table(converter):
    """The guards must not touch a genuine ruled table."""
    node = _extract(converter, _grid(REAL_GRID))

    assert isinstance(node, AstTable)
    assert converter._tables_rejected == 0
    assert [c.content[0].content for c in node.header.cells] == ["Model", "Score"]
    assert len(node.rows) == 1


def test_too_few_ruling_lines_keeps_the_text():
    """Fewer than 2x2 lines cannot form cells -- but the region still holds prose."""
    converter = PdfToAstConverter()
    region = _grid([["alpha beta", "gamma"]])
    single_h_line = region.h_lines[:1]

    node = converter._extract_table_from_ruling_rect(region, region.rect, single_h_line, region.v_lines, page_num=0)

    assert isinstance(node, AstParagraph)
    assert "alpha" in extract_text(node)


def test_extraction_mode_none_still_returns_the_text():
    """``"none"`` means "don't build a table here", not "throw the region away".

    The region was still *detected*, so its text is already out of the text blocks.
    """
    converter = PdfToAstConverter(options=PdfOptions(table_fallback_extraction_mode="none"))
    region = _grid(REAL_GRID)

    node = _extract(converter, region)

    assert isinstance(node, AstParagraph)
    assert "baseline" in extract_text(node)


def test_extraction_mode_none_is_not_counted_as_a_rejection():
    """Nothing was rejected: the caller configured extraction off. Don't dock the score."""
    converter = PdfToAstConverter(options=PdfOptions(table_fallback_extraction_mode="none"))
    converter._tables_rejected = 0

    _extract(converter, _grid(REAL_GRID))

    assert converter._tables_rejected == 0


def test_an_empty_region_still_yields_nothing(converter):
    """Only genuinely empty regions may return ``None`` -- there is nothing to preserve."""
    node = _extract(converter, _grid([["", ""], ["", ""]]))

    assert node is None


# --- the caps are shared, not re-derived -------------------------------------------
#
# ``_pdf_tables`` says the caps "apply to both PyMuPDF's find_tables() output and our
# ruling-line detector since both can fire on the same false-positive shapes". The
# ruling path did not honour that: it required only two lines on each axis, which bound
# a *single cell*, and it re-hardcoded the empty ratio and the uniformity floor as bare
# literals next to the constants that name them.
#
# These are parity tests rather than ideal-outcome tests. The requirement is that the
# two detectors agree about what a table is; asserting an ideal for either one would
# encode a spec neither meets.


class _FakeTable:
    """The shape of a PyMuPDF table: an ``extract()`` grid and a ``bbox``."""

    def __init__(self, grid: list[list[str]], bbox: tuple[float, float, float, float]) -> None:
        self._grid = grid
        self.bbox = bbox

    def extract(self) -> list[list[str]]:
        return self._grid


SHARED_CAP_GRIDS = [
    pytest.param([["A framed callout, not a table."]], id="1x1-framed-box"),
    pytest.param([["What", "is", "the", "capital"]], id="1xN-single-row"),
    pytest.param([["one"], ["two"], ["three"]], id="Nx1-single-column"),
    pytest.param(REAL_GRID, id="2x2-real-grid"),
    # Sparsity, either side of MAX_TABLE_EMPTY_RATIO: 7/10 empty is not *past* 0.70.
    pytest.param([["a", "b", "c", "", ""], ["", "", "", "", ""]], id="empty-at-the-line"),
    pytest.param([["a", "b", "", "", ""], ["", "", "", "", ""]], id="empty-past-the-line"),
    # Uniformity, either side of MIN_FILLED_FOR_UNIFORMITY_CHECK.
    pytest.param([["X", "X"], ["X", "X"]], id="uniform-under-the-floor"),
    pytest.param([["X", "X", "X"], ["X", "X", "X"]], id="uniform-over-the-floor"),
]


@pytest.mark.parametrize("cells", SHARED_CAP_GRIDS)
def test_both_detectors_agree_on_what_counts_as_a_table(cells):
    """The same grid must be accepted, or rejected, by both detectors alike."""
    region = _grid(cells)
    by_ruling = _extract(PdfToAstConverter(), region)
    by_find_tables = PdfToAstConverter()._process_table_to_ast(
        _FakeTable(cells, tuple(region.rect)), region, page_num=0
    )

    assert isinstance(by_ruling, AstTable) == isinstance(by_find_tables, AstTable), (
        f"the ruling-line detector and find_tables() disagree about {cells!r}: " f"{by_ruling!r} vs {by_find_tables!r}"
    )


def test_a_framed_text_box_is_prose_not_a_one_cell_table(converter):
    """Two lines on each axis bound one cell. One cell is a frame, not a grid."""
    region = _grid([["A framed callout, not a table."]])

    node = _extract(converter, region)

    assert not isinstance(node, AstTable), "a 1x1 region is a framed box, not a table"
    assert isinstance(node, AstParagraph)
    assert "framed callout" in extract_text(node)
    assert converter._tables_rejected == 1


# --- end to end -------------------------------------------------------------------
#
# The unit tests above call the method directly. This one drives the whole converter
# over a real PDF, because the bug is not visible from the method's own code: it lives
# in the ordering between the text-block exclusion and the table validation.

FRAMED_TEXT = ("Prohibited items include glass", "containers and open flames.")


def _framed_pdf_bytes() -> bytes:
    """A page with a stroked frame, one internal rule, and a sentence in one cell.

    The lines have to be stroked ``"l"`` commands of page-proportional length to reach
    the ruling-line detector at all -- ``"re"`` rectangles are not read as ruling lines.
    The resulting 2x2 grid is 75% empty, which trips the sparsity guard.
    """
    xs = [72.0, 250.0, 420.0]
    ys = [100.0, 160.0, 300.0]

    doc = pymupdf.open()
    page = doc.new_page()
    for y in ys:
        page.draw_line((xs[0], y), (xs[-1], y))
    for x in xs:
        page.draw_line((x, ys[0]), (x, ys[-1]))
    for offset, line in enumerate(FRAMED_TEXT):
        page.insert_text((80, 200 + offset * 14), line, fontsize=11)
    return doc.tobytes()


def test_a_rejected_framed_region_reaches_the_output_as_prose():
    """The whole page's text used to vanish, and the conversion still reported success."""
    from all2md import to_markdown

    output = to_markdown(
        io.BytesIO(_framed_pdf_bytes()),
        source_format="pdf",
        parser_options=PdfOptions(table_detection_mode="ruling"),
    )

    assert "Prohibited items include glass containers and open flames." in output


def test_the_rejected_region_is_not_emitted_twice():
    """Nested ruling regions overlap; the text must still appear once, not once per region."""
    from all2md import to_markdown

    output = to_markdown(
        io.BytesIO(_framed_pdf_bytes()),
        source_format="pdf",
        parser_options=PdfOptions(table_detection_mode="ruling"),
    )

    assert output.count("Prohibited items") == 1


def test_the_rejected_region_is_not_rendered_as_a_table():
    from all2md import to_markdown

    output = to_markdown(
        io.BytesIO(_framed_pdf_bytes()),
        source_format="pdf",
        parser_options=PdfOptions(table_detection_mode="ruling"),
    )

    assert "|" not in output
