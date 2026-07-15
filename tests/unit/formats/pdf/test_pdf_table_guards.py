#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_table_guards.py
"""Guards that reject non-tabular detections must never cost a word of text.

``find_tables()`` fires on things that are not tables. A one-column "table" is prose
wrapped in pipes; a one-row "table" is a line of text chopped at its word boundaries.
Rejecting those is easy. Rejecting them *without deleting their text* is the part that
bit us, and is what these tests pin down.

The trap is an ordering one, and it is invisible from the guard's own code: text blocks
that fall inside a detected table's bbox are removed from the ordinary text stream
**before** the table is validated, so they will not be emitted twice. A rejection path
that simply returns ``None`` therefore does not demote the region to prose -- it deletes
it. Across the PDF corpus, rejecting degenerate grids that way silently cost 256 words
of real body text while every table-shaped assertion still passed.
"""

from __future__ import annotations

import pytest

from all2md.ast import Paragraph as AstParagraph
from all2md.ast import Table as AstTable
from all2md.ast.nodes import Text, get_node_children
from all2md.parsers.pdf import PdfToAstConverter

pytestmark = [pytest.mark.unit, pytest.mark.pdf, pytest.mark.table]


class _FakeTable:
    """The shape of a PyMuPDF table: an ``extract()`` grid and a ``bbox``."""

    def __init__(self, grid: list[list[str | None]], bbox: tuple[float, float, float, float]) -> None:
        self._grid = grid
        self.bbox = bbox

    def extract(self) -> list[list[str | None]]:
        return self._grid


class _FakePage:
    """A page that can only do what the rejection path needs: hand back a region's text."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.asked_for: list[tuple] = []

    def get_textbox(self, rect) -> str:
        self.asked_for.append(tuple(rect))
        return self._text


def _text_of(node) -> str:
    parts: list[str] = []

    def walk(current) -> None:
        if isinstance(current, Text):
            parts.append(current.content)
            return
        for child in get_node_children(current):
            walk(child)

    walk(node)
    return " ".join(parts)


@pytest.fixture
def converter() -> PdfToAstConverter:
    conv = PdfToAstConverter()
    conv._tables_rejected = 0
    return conv


# A real grid: two dimensions, so it can carry tabular meaning.
REAL_GRID = [["Model", "Score"], ["baseline", "0.62"], ["ours", "0.81"]]

# The shapes find_tables() invents. Both are text, not tables.
SINGLE_COLUMN = [["Retrieval augments the decoder."], ["Each layer attends to the graph."]]
SINGLE_ROW = [["What", "is", "the", "capital", "of", "this", "country", "?"]]


@pytest.mark.parametrize(
    ("grid", "region_text"),
    [
        pytest.param(SINGLE_COLUMN, "Retrieval augments the decoder.\nEach layer attends to the graph.", id="1xN"),
        pytest.param(SINGLE_ROW, "What is the capital of this country?", id="Nx1"),
    ],
)
def test_degenerate_grid_becomes_a_paragraph_not_a_table(converter, grid, region_text):
    """A grid with only one dimension is demoted to prose rather than rendered as a table."""
    page = _FakePage(region_text)
    node = converter._process_table_to_ast(_FakeTable(grid, (0, 0, 100, 50)), page, page_num=0)

    assert not isinstance(node, AstTable), "a 1xN / Nx1 detection is text, not a table"
    assert isinstance(node, AstParagraph)


@pytest.mark.parametrize(
    ("grid", "region_text"),
    [
        pytest.param(SINGLE_COLUMN, "Retrieval augments the decoder.\nEach layer attends to the graph.", id="1xN"),
        pytest.param(SINGLE_ROW, "What is the capital of this country?", id="Nx1"),
    ],
)
def test_rejecting_a_degenerate_grid_keeps_every_word(converter, grid, region_text):
    """The whole point: rejection must demote the region's text, never delete it.

    Returning ``None`` here would drop the text on the floor -- it has already been
    excluded from the ordinary text blocks by the time this runs.
    """
    page = _FakePage(region_text)
    node = converter._process_table_to_ast(_FakeTable(grid, (0, 0, 100, 50)), page, page_num=0)

    assert node is not None, "returning None deletes the region's text: it is not emitted anywhere else"
    recovered = _text_of(node).split()
    for word in region_text.split():
        assert word in recovered, f"rejecting the junk table lost the word {word!r}"


def test_degenerate_rejection_reads_the_tables_own_region(converter):
    """The paragraph is built from the rejected table's bbox, not some other region."""
    page = _FakePage("some text")
    converter._process_table_to_ast(_FakeTable(SINGLE_ROW, (10, 20, 110, 70)), page, page_num=0)

    assert page.asked_for == [(10, 20, 110, 70)]


def test_degenerate_rejection_is_recorded(converter):
    """The demotion is counted, so the quality card can report it."""
    page = _FakePage("What is the capital of this country?")
    converter._process_table_to_ast(_FakeTable(SINGLE_ROW, (0, 0, 100, 50)), page, page_num=0)

    assert converter._tables_rejected == 1


def test_a_real_grid_is_still_a_table(converter):
    """The guard must not touch tables that have two dimensions. It is the whole corpus's worth of them."""
    page = _FakePage("Model Score baseline 0.62 ours 0.81")
    node = converter._process_table_to_ast(_FakeTable(REAL_GRID, (0, 0, 100, 50)), page, page_num=0)

    assert isinstance(node, AstTable)
    assert converter._tables_rejected == 0
    assert [c.content[0].content for c in node.header.cells] == ["Model", "Score"]
    assert len(node.rows) == 2


def test_empty_region_yields_nothing(converter):
    """A degenerate grid over a region with no text has nothing to preserve."""
    page = _FakePage("   \n  ")
    node = converter._process_table_to_ast(_FakeTable(SINGLE_ROW, (0, 0, 100, 50)), page, page_num=0)

    assert node is None


# Grids that each trip a *different* rejection branch. #77 demoted only the
# degenerate-grid branch to prose; these four still returned None, silently
# deleting a sparse-but-real table (a financial statement or form crosses the
# 70%-empty bar), a TOC region, or an oversized grid. Each grid is built to fire
# exactly one branch given the _pdf_tables thresholds (MIN 2x2, MAX 25 cols /
# 200 rows, empty > 0.70, uniform >= 5 filled, dot-leader > 0.30).
OVERSIZED_GRID = [[f"h{i}" for i in range(26)], [f"v{i}" for i in range(26)]]
MOSTLY_EMPTY_GRID = [["a", "b", ""], ["", "", ""], ["", "", ""]]
UNIFORM_GRID = [["X", "X"], ["X", "X"], ["X", "X"]]
DOT_LEADER_GRID = [["Introduction", ".........."], ["Methods", ".........."]]


@pytest.mark.parametrize(
    ("grid", "rejection"),
    [
        pytest.param(OVERSIZED_GRID, "oversized_grid", id="oversized"),
        pytest.param(MOSTLY_EMPTY_GRID, "mostly_empty", id="mostly-empty"),
        pytest.param(UNIFORM_GRID, "uniform_cells", id="uniform"),
        pytest.param(DOT_LEADER_GRID, "dot_leader_toc", id="dot-leader-toc"),
    ],
)
def test_every_rejection_branch_demotes_to_prose(converter, grid, rejection):
    """Every table-rejection branch must preserve the region's text, never delete it.

    The text inside a rejected table's bbox is already gone from the ordinary text
    blocks, so a ``return None`` drops it on the floor. Only the degenerate-grid
    branch was fixed for that; the rest are pinned here.
    """
    region_text = "alpha beta gamma delta"
    page = _FakePage(region_text)
    node = converter._process_table_to_ast(_FakeTable(grid, (0, 0, 100, 50)), page, page_num=0)

    assert not isinstance(node, AstTable), f"a {rejection} detection is not a real table"
    assert isinstance(node, AstParagraph), f"{rejection} must demote to prose, not delete (returned {node!r})"
    recovered = _text_of(node).split()
    for word in region_text.split():
        assert word in recovered, f"rejecting the {rejection} region lost the word {word!r}"
    assert converter._tables_rejected == 1, f"{rejection} demotion must be recorded for the quality card"
