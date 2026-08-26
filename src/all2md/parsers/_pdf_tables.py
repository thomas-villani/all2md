#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_tables.py
"""PDF table detection algorithms.

This private module contains algorithms for detecting tables in PDF documents
using ruling lines (horizontal and vertical lines that form table borders).

"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pymupdf

__all__ = [
    "MAX_DOT_LEADER_CELL_RATIO",
    "MAX_EXTRACT_LOSS_SHARE",
    "MIN_REBUILD_CHAR_RATIO",
    "MAX_GUTTER_INTRUSION_SHARE",
    "MAX_TABLE_COLS",
    "MIN_TABLE_COLS",
    "MIN_TABLE_ROWS",
    "MAX_TABLE_EMPTY_RATIO",
    "MAX_TABLE_ROWS",
    "MAX_SPLIT_WORD_RATIO",
    "MIN_FILLED_FOR_UNIFORMITY_CHECK",
    "MIN_GUTTER_LINES",
    "MIN_GUTTER_WIDTH_PT",
    "MAX_ROTATED_WORD_SHARE",
    "MAX_ROW_EXTENT_OVERLAP_PT",
    "MAX_TWO_COLUMN_REGION_DRAWINGS",
    "MIN_WORD_GUTTER_COLS",
    "TABLE_REGION_STRATEGIES",
    "TABLE_SIGNAL_RULING_THRESHOLD",
    "detect_tables_by_ruling_lines",
    "extract_loss_share",
    "group_words_into_lines",
    "is_dot_leader_cell",
    "looks_like_gridded_prose",
    "looks_like_numbered_bibliography",
    "merge_continuation_lines",
    "page_has_table_signals",
    "MIN_COLUMN_CUT_ROWS",
    "adjacent_clipped_column",
    "bbox_clipped_rows",
    "boundaries_to_dissolve",
    "contradicted_column_boundaries",
    "rebuild_cells_from_words",
    "split_word_ratio",
    "word_gutter_grid",
]

# Hard caps and guards applied to detected tables. Real prose tables rarely
# exceed these bounds; "tables" outside them are almost always misfires on
# non-tabular content (decorative frames, callout boxes, TOC dot-leader
# regions, layout grids). The same caps apply to both PyMuPDF's
# find_tables() output and our ruling-line detector since both can fire
# on the same false-positive shapes.
MAX_TABLE_COLS = 25
MAX_TABLE_ROWS = 200
# A grid needs two dimensions to mean anything. A one-column "table" is prose wrapped
# in pipes; a one-row "table" is a single line of text chopped at its word boundaries.
# find_tables() emits both on academic PDFs -- on one paper it rendered the sentence
# "What is the capital of this country?" as an eight-column table -- and both are
# strictly worse than leaving the text as text.
MIN_TABLE_COLS = 2
MIN_TABLE_ROWS = 2
MAX_TABLE_EMPTY_RATIO = 0.70
MIN_FILLED_FOR_UNIFORMITY_CHECK = 5
# When more than this fraction of non-empty cells are dot-leader cells
# (only dots, or a value with trailing dot-leader bleeding from the next
# visual row), the table is treated as a TOC region and rejected.
MAX_DOT_LEADER_CELL_RATIO = 0.30

# ``find_tables()`` strategies tried inside a region the layout model predicted to be a
# table, in order. PyMuPDF's default wants ruling lines on both axes, and journal tables
# are typically booktabs-style: horizontal rules only, or none at all. On the PMC
# born-digital corpus the line strategies recovered 0 of 31 such regions and ``"text"``,
# which infers columns from glyph alignment, recovered a >=2x2 grid in all 31.
#
# ``"lines"`` (looser than ``"lines_strict"``: it also accepts thin filled rectangles as
# rules) is deliberately absent -- it found nothing the strict pass had not, on every one
# of those 31 regions, and each strategy costs a full detection pass.
#
# Text alignment is trusted *only* inside a layout-predicted region. Run page-wide it
# reads any vertically aligned prose as a grid; the predicted region is the prior that
# makes it safe, and the guards in ``_process_table_to_ast`` still filter what it returns.
TABLE_REGION_STRATEGIES = ("lines_strict", "text")

# Maximum share of a text-aligned grid's word tokens that may be fragments -- pieces that are
# not a whole word anywhere on the page. A real table's columns sit in the whitespace gutters
# between cells, so its cells hold whole words. A column boundary invented over prose cuts
# through them: on a mis-predicted abstract region it produced "condu"/"cted",
# "micronutr"/"ients", "coronaviru", and rendered a page of prose as a seven-column table.
#
# Measured on the PMC born-digital corpus, this is the only signal found that separates the
# two. Grid shape (rows, columns, fill ratio, words per cell), reading-order preservation, and
# region corroboration (ruling lines, a "Table N" caption) were each measured and each failed:
# every one of them had near-identical distributions for real tables and for gridded prose.
#
# Clean regions measured 0.000-0.022 and damaged ones 0.128-0.333, so the threshold sits in an
# empty gap rather than on a slope. The residue in clean regions is ligature and encoding
# noise, not splitting.
MAX_SPLIT_WORD_RATIO = 0.05

# Ruling-line length threshold (as a fraction of page width/height) used by
# the cheap pre-flight gate that decides whether to call ``page.find_tables()``.
# Smaller than the fallback threshold (0.5) on purpose: the gate just needs to
# answer "are there any ruling-line drawings on this page", so we accept much
# shorter lines as evidence of possible tabular structure.
TABLE_SIGNAL_RULING_THRESHOLD = 0.15

# A pure dot-leader cell is all dots/whitespace. A mixed cell is dot-leader
# noise only when the trailing line has multiple dots (a section name plus
# its dot-leader run). A single trailing dot is more likely a benign font-
# baseline artifact (e.g. ``$10.99`` extracted as ``$1099\n.``) and is left
# alone.
_DOT_ONLY = re.compile(r"^[.…\s]+$")
_DOT_LEADER_TAIL = re.compile(r"\n\s*[.…](?:\s*[.…]){2,}\s*$")

# Letters only. Digits are never "split words" -- a column boundary falling inside a number
# yields two numbers, both plausible, and counting those would flag real numeric tables.
_WORD_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)

# Word-gutter grid recovery (the third region strategy; see #386). The first two
# strategies delegate the grid to find_tables(), whose text mode both invents column
# boundaries through words and reassembles cell text with lost spaces -- on the PMC
# born-digital corpus that combination cost 56 of the 63 missing tables, every one
# killed by the split-word guard telling the truth about a damaged grid. Building the
# grid from the page's own word boxes makes both damage classes impossible: a column
# boundary can only fall in a gutter no word crosses, and cell text is the words
# themselves.
#
# A gutter must be corroborated by enough printed lines to mean anything: with fewer
# than MIN_GUTTER_LINES lines, the space between any two words "spans" the region.
MIN_GUTTER_LINES = 3
# Share of a region's lines that may intrude into an x-band before it stops counting
# as a gutter. Nonzero because spanning headers and footnote lines legitimately cross
# column boundaries -- measured on the PMC corpus, requiring 90% clearance recovered
# the truth column count almost exactly (35 of 37 guard-killed tables, counts matching
# JATS: 4->4, 5->5, 9->9) while one intruding line per ten still blocks prose.
MAX_GUTTER_INTRUSION_SHARE = 0.1
# Narrower bands than this are ordinary word spacing, not column separation.
MIN_GUTTER_WIDTH_PT = 4.0
# A gutter grid needs at least this many columns. One gutter is what ANY two-column
# layout has -- a reference list, a chart legend beside its axis -- so a single band is
# the weakest geometry this pass accepts, and two-column admission leans on the
# downstream guards rather than the sweep. Measured on the PMC corpus (#389), the
# whole two-column population is 12 regions: 4 real tables, 7 numbered reference
# lists (6 already condemned by looks_like_numbered_bibliography, the 7th once its
# ``42)`` spelling counted), and 1 chart whose axis ticks and legend gridded --
# the shape MAX_TWO_COLUMN_REGION_DRAWINGS exists for. Refusing the single gutter
# outright, as this pass first shipped, cost the 4 real tables to save nothing the
# guards were not already saving. Three-plus columns need no such corroboration:
# two aligned internal boundaries do not happen to prose.
MIN_WORD_GUTTER_COLS = 2
# A two-column grid whose region holds more vector drawing paths than this is a chart,
# not a table: plot lines sit under a chart's tick labels and legend, while a
# borderless table has at most its own ruling lines. Measured on the PMC corpus, the
# one chart region in the two-column population held 541 intersecting paths; the four
# real two-column tables held 0-4.
MAX_TWO_COLUMN_REGION_DRAWINGS = 25
# Share of a region's multi-character words that may stand taller than wide before the
# region reads as rotated and the gutter pass switches to the transposed frame.
MAX_ROTATED_WORD_SHARE = 0.5
# How much taller than wide a word's box must be to count as *unambiguously* rotated.
# Declining a region is safe on weak evidence -- the prose path picks it up -- but
# transposing it is a positive claim, and near-square boxes cut both ways: measured on
# the PMC corpus, genuinely rotated table regions hold words at median aspect 2.5-2.7,
# while a mixed-orientation region that must NOT be transposed sits at median 1.05.
MIN_ROTATED_WORD_ASPECT = 1.2

# Row grouping from inter-line gaps. A wrapped cell's continuation line sits one
# leading below its row; the next logical row sits leading plus row padding below.
# When those two populations are separable, the gap between them names the rows --
# measured on the PMC corpus: wraps at 1.0-1.3pt against rows at 2.0-6.1pt across
# four publishers. The jump must clear both bars before it is believed: an absolute
# floor as a share of line height (0.10 x ~8pt line = 0.8pt, so the 4.0-vs-4.4pt
# near-tie one publisher prints does NOT qualify) and a ratio (1.8x, so uniform
# leading with jitter does not manufacture rows).
ROW_GAP_JUMP_MIN_HEIGHT_SHARE = 0.10
ROW_GAP_JUMP_MIN_RATIO = 1.8
# A grouping whose rows are mostly half-empty has mistaken wrapping for rows: a real row
# fills its columns, while a line left standing by a threshold set too low fills one. So
# the first gap jump is no longer taken on faith -- jumps are tried in order and the first
# whose grouping clears this bar wins. Measured on PMC7750019.1, the worst table on the
# held-out corpus: a single -7.95pt gap sat below a cluster of 52 at -3.21pt, the first
# jump peeled that outlier off, and the threshold landed beneath every real gap -- 97
# printed lines became 89 rows, 77 of them half-empty, nothing merged at all. Distinct gap
# values are the candidates, so without this a gap occurring once weighs exactly as much
# as one occurring fifty times.
#
# This bar is a *share*, and deliberately only that. Nothing here folds a half-empty group
# into its neighbour, because a half-empty row is not always a wrap: a section-heading row
# inside a table -- "Gender", then indented "Male"/"Female" beneath it -- fills exactly one
# column and is a real row. #438 shipped such a fold and it silently relabelled data: on
# PMC4500011.1 "Gender" fused onto the Age row's numbers and "Height (cm)" onto Female's,
# so every value sat under the wrong label. Folding is not separable from that by geometry
# -- those headings abut their neighbours as tightly as any wrapped fragment, so no gap
# tolerance divides them -- and measured against JATS ground truth on both corpora the fold
# lost: 7 table pages worse against 1 better on the born-digital corpus, and on the held-out
# corpus it was designed against, 5 worse against 3 better. It looked like a win only under
# a half-empty-row count, which *rewards* folding a real heading away. Judge groupings by
# ground truth, and treat a proxy that cannot see its own worst outcome as no evidence.
ROW_GROUP_MAX_SPARSE_SHARE = 0.5
# A cell is "mostly numeric" when digits dominate its alphanumerics. Two adjacent
# lines that each hold two or more such cells are two data rows, not a wrapped cell:
# no publisher wraps a numeric row. Any grouping that would fuse such a pair is
# structurally wrong, so the grouping that proposed it is abandoned wholesale --
# measured, the failure this prevents is a table whose only detectable gap jump is
# its header seam, where believing the jump fuses every data row into one.
ROW_NUMERIC_CELL_DIGIT_SHARE = 0.5
ROW_FUSE_MIN_NUMERIC_CELLS = 2
# The continuation-merge anchor may be a sparse column: a row-label column in a
# heavily wrapped table is filled only on row starts (measured: 23% of printed lines
# on a table whose every row wraps to 3-6 lines). Columns below this floor are noise;
# columns between the floor and the trusted 60% bar are believed only when the merge
# they imply survives the numeric-fusion guard above.
ROW_ANCHOR_MIN_FILL = 0.2
ROW_ANCHOR_TRUSTED_FILL = 0.6
# A column may hold at most this many separate filled runs inside one merged row.
# A cell fills contiguous lines, so two runs is a hole (tolerated: one stray gap in a
# ragged prose cell), while three or more is a stack of distinct cells -- the group is
# fusing rows and the grouping that proposed it is wrong. Measured: a TF-gene table
# whose only gap jump was its header seam fused 64 lines into one row past the numeric
# guard (its cells are prose), while its row-label column showed 15 separate runs.
ROW_GROUP_MAX_COLUMN_RUNS = 2

# Row bboxes may overlap by at most this much before the merge distrusts them as
# line geometry. Printed lines never overlap beyond font-box slop; find_tables()
# rows on a rowspan table overlap by whole rows (measured: -17pt on a
# two-axis-header table whose spans stretched one row's bbox over three).
MAX_ROW_EXTENT_OVERLAP_PT = 1.0

# Maximum share of the page's own words (centered inside a grid's bbox) that may be
# missing from the extracted cell text before the grid's text assembly is distrusted
# and rebuilt from word boxes. The complement of MAX_SPLIT_WORD_RATIO: that guard asks
# "does the grid hold tokens the page does not?", this one asks "does the page hold
# words the grid lost?" -- and unlike the fragment test it counts numbers, because
# ``Table.extract()``'s clipping eats numeric cells ("0.75", "(-0.04-0.28)") that the
# letters-only fragment tokenizer is blind to by design. Measured on the PMC dev
# corpus with the per-cell containment rule: intact grids 0.000-0.029 (subscript and
# ligature noise), grids with clipped cell text 0.055-0.441, so the threshold sits in
# the gap between them.
MAX_EXTRACT_LOSS_SHARE = 0.04

# A rebuilt grid must carry at least this share of the extracted grid's non-whitespace
# characters to replace it. The rebuild exists to *recover* clipped text; when it comes
# back lighter than the extract, it lost text instead -- measured on rotated (landscape)
# pages, where find_tables() cell rects and the page's word boxes do not share a
# coordinate frame, so nearly every cell came back empty (27/121 filled), the gutted
# grid died at the mostly-empty guard, and three intact tables were destroyed outright.
MIN_REBUILD_CHAR_RATIO = 0.9

# A grid column boundary is *contradicted* when the page prints a word straddling it on a
# row whose cells really do abut there -- the grid claims two cells where the page wrote
# one word ("Vitamin B12," cut into "Vitamin B" | "12,"). Both existing text guards are
# blind to this by design: the fragment tokenizer drops digits, so "B12," reduces to "b"
# and passes, and nothing is *lost* -- every character lands in one cell or the other.
# The word boxes are the evidence, exactly as in the gutter path and the rebuild above.
#
# A word crossing an x-position where that row's cell *spans* is no contradiction: a
# two-tier header ("Intraobserver variability" over three columns) legitimately crosses
# the boundaries beneath it, and find_tables() records the span by omitting the edge on
# that row. Counting only edge-bearing rows separates the two cases cleanly -- measured
# on the PMC dev corpus, spanning headers show 0 contradicted rows while mis-split
# columns show 2, 3, and 15+ -- and the threshold sits in that gap. A single
# contradicted row is left alone: observed only on degenerate one-row detections, where
# demotion to a paragraph already handles it.
MIN_COLUMN_CUT_ROWS = 2

# A word must extend at least this far beyond both sides of a boundary before it counts
# as cut, so glyph-box slop against a real boundary is not read as a contradiction.
COLUMN_CUT_MARGIN_PT = 1.0

# Two x-positions within this distance are the same column edge (find_tables() emits
# cell rects whose shared edges agree to well under a point).
COLUMN_EDGE_TOLERANCE_PT = 0.5

# find_tables() can also draw its bbox short of a whole column: on the PMC dev corpus
# a four-column table was detected as three, with the fourth ("3rd trimester ...")
# printed just outside the bbox. The evidence that a band of outside words is the
# table's own clipped column and not a neighbour: it sits a column gutter away, not a
# page-layout gutter (measured 3.0-4.7pt against 13.7+ for prose neighbours and
# captions); its words line up with essentially every grid row (measured full
# coverage against <=0.73 for prose and <=0.45 for captions); and nothing continues
# beyond it (measured 0-1 further words against 62+ where a prose column runs on, and
# 100+ where a second table sits alongside -- both of which must not be swallowed).
# Each threshold sits inside its measured gap.
MAX_ADJACENT_COLUMN_GAP_PT = 8.0
MIN_ADJACENT_COLUMN_ROW_COVERAGE = 0.8
MAX_ADJACENT_COLUMN_FAR_WORDS = 2
ADJACENT_COLUMN_SEARCH_PT = 40.0
ADJACENT_COLUMN_FAR_SEARCH_PT = 150.0

# A contradicted boundary names the damage, not the repair. Two shapes produce cut
# words, and they need opposite treatment. A *spurious* boundary splits one printed
# column in two ("Vitamin A, | μg"): away from the rows whose words it cut, the text
# still runs straight across it -- the space between the words on either side is an
# ordinary inter-word space. A *real* boundary with a wide value overhanging it
# ("<0.001" protruding into the neighbour) lives where every column boundary lives:
# in a gutter, with clear air on both sides on every row it does not cut. So the
# arbiter is the same physical quantity the word-gutter path is built on -- the
# median horizontal gap across the boundary on uncut rows, against
# MIN_GUTTER_WIDTH_PT. Dissolve when the gap is a space; keep when it is a gutter,
# because the word-box rebuild already lands an overhanging value whole in the cell
# holding its center, and dissolving there would fuse two true columns.


def split_word_ratio(page: "pymupdf.Page", table_data: list[list[str | None]]) -> float:
    """Share of a grid's word tokens that are not whole words of the page.

    A grid whose columns fall in the whitespace gutters between cells holds whole words. One
    whose column boundaries were invented over running prose cuts through them, leaving
    fragments (``"condu"``, ``"cted"``) that appear nowhere on the page as words. That is the
    difference between adding structure to a table and shredding a paragraph into one.

    The page's own word segmentation is the reference, taken **unclipped**: clipping to the
    region truncates any word straddling its boundary, which manufactures the very fragments
    this is meant to detect.

    Parameters
    ----------
    page : PyMuPDF Page
        Page the grid was extracted from.
    table_data : list of list of (str or None)
        Extracted cell text, as returned by ``Table.extract()``.

    Returns
    -------
    float
        Fragment share in ``0.0..1.0``. ``0.0`` when the grid holds no word tokens, and on
        error, so an unreadable page falls back to the other guards rather than dropping a
        table nothing has shown to be bad.

    """
    tokens: list[str] = []
    for row in table_data:
        for cell in row:
            if cell is not None:
                tokens.extend(token.lower() for token in _WORD_TOKEN.findall(str(cell)))
    if not tokens:
        return 0.0

    try:
        vocabulary: set[str] = set()
        for word in page.get_text("words"):
            vocabulary.update(token.lower() for token in _WORD_TOKEN.findall(word[4]))
    except Exception:
        return 0.0
    if not vocabulary:
        return 0.0

    return sum(1 for token in tokens if token not in vocabulary) / len(tokens)


def extract_loss_share(
    page: "pymupdf.Page", table_data: list[list[str | None]], bbox: tuple[float, float, float, float]
) -> float:
    """Share of the page's words inside *bbox* that the extracted grid does not contain.

    ``split_word_ratio`` catches invented column boundaries by finding tokens in the grid
    that are whole words nowhere on the page. This is its complement for the opposite
    damage: ``Table.extract()`` clipping cell text, which *removes* words from the grid --
    most of them numeric, which the fragment tokenizer deliberately ignores. A word counts
    as lost when its exact text is not among the grid's whitespace-split tokens.

    Parameters
    ----------
    page : pymupdf.Page
        Page the grid was extracted from.
    table_data : list of list of (str or None)
        Extracted cell text, as returned by ``Table.extract()``.
    bbox : tuple of float
        The table's bounding box; only words centered inside it are judged.

    Returns
    -------
    float
        Lost-word share in ``0.0..1.0``; ``0.0`` when the region holds no words, and on
        error -- the same fail-open posture as :func:`split_word_ratio`.

    """
    # A page word is judged against whitespace-stripped cell text, cell by cell: a
    # cell wrapping "(-0.04-0.28)" across two printed lines still *contains* the word,
    # while a cell truncated to "(-0.04-0." does not. Token equality was measured
    # first and misfires on exactly the wrapped-cell shape (0.10-0.44 "loss" on
    # undamaged landscape grids); per-cell containment keeps the truncation signal
    # without it. Cells are tested individually so two adjacent cells cannot
    # accidentally concatenate into a word neither of them holds.
    cell_texts = [
        "".join(str(cell).lower().split()) for row in table_data for cell in row if cell is not None and str(cell)
    ]
    try:
        words = page.get_text("words")
    except Exception:
        return 0.0
    x0, y0, x1, y1 = bbox
    lost = 0
    total = 0
    for word in words:
        center_x = (word[0] + word[2]) / 2
        center_y = (word[1] + word[3]) / 2
        if not (x0 <= center_x < x1 and y0 <= center_y < y1):
            continue
        total += 1
        needle = "".join(str(word[4]).lower().split())
        if needle and not any(needle in cell for cell in cell_texts):
            lost += 1
    return lost / total if total else 0.0


def _dissolve_cell_edges(
    cells: "list[tuple[float, float, float, float] | None]", boundaries: list[float]
) -> "list[tuple[float, float, float, float] | None]":
    """Union a row's adjacent cell rects wherever they abut at a dissolved boundary."""
    out: list[tuple[float, float, float, float] | None] = []
    for cell in cells:
        rect = None if cell is None else tuple(cell[:4])
        previous = out[-1] if out else None
        if (
            rect is not None
            and previous is not None
            and any(
                abs(previous[2] - boundary) <= COLUMN_EDGE_TOLERANCE_PT
                and abs(rect[0] - boundary) <= COLUMN_EDGE_TOLERANCE_PT
                for boundary in boundaries
            )
        ):
            out[-1] = (previous[0], min(previous[1], rect[1]), rect[2], max(previous[3], rect[3]))
        else:
            out.append(rect)  # type: ignore[arg-type]
    return out


def contradicted_column_boundaries(
    page: "pymupdf.Page", table: object, table_data: "list[list[str | None]] | None" = None
) -> list[tuple[float, tuple[int, ...]]]:
    """Interior column boundaries the page's own words contradict.

    For every interior x-edge of a ``find_tables()`` grid, count the rows where the
    grid draws the edge -- both neighbouring cells abut at it -- while the page prints
    a word straddling it. Rows whose cell spans across the position (merged headers)
    do not count, and neither do words that merely graze the edge; see
    ``MIN_COLUMN_CUT_ROWS`` for the measured gap the threshold sits in.

    Parameters
    ----------
    page : pymupdf.Page
        Page the table was found on.
    table : PyMuPDF Table
        Table object from ``find_tables()`` whose ``rows[].cells`` rects define the
        grid.
    table_data : list of list of str or None, optional
        The grid ``table.extract()`` returned. When given, a crossing word that one of
        the two adjacent cells already holds **whole** does not count: the damage this
        detector exists to find is ``extract()`` cutting a word across the boundary,
        and a wide value merely overhanging its correct column ("<0.001" protruding
        into the neighbour on two rows of an otherwise-aligned grid, measured on the
        PMC dev corpus) arrives intact in its own cell.

    Returns
    -------
    list of tuple of (float, tuple of int)
        The contradicted boundary x-positions, ascending, each with the indices of
        the rows whose words it cuts -- ``boundaries_to_dissolve`` reads the fill
        pattern *away* from those rows. Empty when the grid's columns fall between
        the page's words, or when the table exposes no usable cell geometry.

    """
    import pymupdf

    try:
        rows = list(table.rows)  # type: ignore[attr-defined]
        bbox = pymupdf.Rect(table.bbox)  # type: ignore[attr-defined]
        words = [word for word in page.get_text("words") if pymupdf.Rect(word[:4]).intersects(bbox)]
    except Exception:
        return []
    if not rows or not words:
        return []

    row_cells: list[list[tuple[float, float, float, float]]] = []
    row_tokens: list[list[tuple[tuple[float, float, float, float], set[str]]]] = []
    edges: set[float] = set()
    for row_index, row in enumerate(rows):
        raw_cells = list(getattr(row, "cells", None) or [])
        cells = [cell[:4] for cell in raw_cells if cell is not None]
        row_cells.append(cells)
        extracted_row = table_data[row_index] if table_data is not None and row_index < len(table_data) else []
        cell_tokens: list[tuple[tuple[float, float, float, float], set[str]]] = []
        for cell_index, cell in enumerate(raw_cells):
            if cell is None:
                continue
            text = extracted_row[cell_index] if cell_index < len(extracted_row) else None
            cell_tokens.append((cell[:4], set(str(text).split()) if text else set()))
        row_tokens.append(cell_tokens)
        xs = sorted({cell[0] for cell in cells} | {cell[2] for cell in cells})
        edges.update(xs[1:-1])

    def same_edge(a: float, b: float) -> bool:
        return abs(a - b) <= COLUMN_EDGE_TOLERANCE_PT

    contradicted: list[tuple[float, tuple[int, ...]]] = []
    for boundary in sorted(edges):
        if any(same_edge(boundary, seen) for seen, _rows in contradicted):
            continue
        cut_rows: list[int] = []
        for row_index, (cells, cell_tokens) in enumerate(zip(row_cells, row_tokens, strict=True)):
            if not cells:
                continue
            # The row bears this edge only if a cell ends (or the next begins) there;
            # a spanning cell omits it, and its words may cross freely.
            bears = any(same_edge(cell[2], boundary) for cell in cells[:-1]) or any(
                same_edge(cell[0], boundary) for cell in cells[1:]
            )
            if not bears:
                continue
            # Tokens the two cells meeting at this boundary hold: a crossing word
            # either delivered whole was not cut by it.
            adjacent: set[str] = set()
            for rect, tokens in cell_tokens:
                if same_edge(rect[2], boundary) or same_edge(rect[0], boundary):
                    adjacent |= tokens
            top = min(cell[1] for cell in cells)
            bottom = max(cell[3] for cell in cells)
            for word in words:
                if not (word[0] + COLUMN_CUT_MARGIN_PT < boundary < word[2] - COLUMN_CUT_MARGIN_PT):
                    continue
                center_y = (word[1] + word[3]) / 2
                if top <= center_y < bottom and str(word[4]) not in adjacent:
                    cut_rows.append(row_index)
                    break
        if len(cut_rows) >= MIN_COLUMN_CUT_ROWS:
            contradicted.append((boundary, tuple(cut_rows)))
    return contradicted


def adjacent_clipped_column(page: "pymupdf.Page", table: object) -> "tuple[pymupdf.Rect, str] | None":
    """Find a whole column of the table printed just outside its bbox.

    Scans the bbox's vertical band on each side for words the bbox excluded, and
    admits them as the table's own clipped column only on three measured signals
    together: they sit a column gutter away (not a page-layout gutter), they align
    with essentially every grid row, and nothing continues beyond them. See the
    constants above for the measured gaps; prose neighbours, captions, and
    side-by-side tables each fail at least one.

    Parameters
    ----------
    page : pymupdf.Page
        Page the table was found on.
    table : PyMuPDF Table
        Table object from ``find_tables()`` whose ``rows[].cells`` rects define the
        grid.

    Returns
    -------
    tuple of (pymupdf.Rect, str) or None
        The rectangle holding the clipped column's words and which side of the
        table it sits on (``"left"`` or ``"right"``), or ``None`` when no side
        qualifies.

    """
    import pymupdf

    try:
        rows = list(table.rows)  # type: ignore[attr-defined]
        bbox = pymupdf.Rect(table.bbox)  # type: ignore[attr-defined]
        words = page.get_text("words")
    except Exception:
        return None
    row_bands = []
    for row in rows:
        cells = [cell[:4] for cell in (getattr(row, "cells", None) or []) if cell is not None]
        if cells:
            row_bands.append((min(cell[1] for cell in cells), max(cell[3] for cell in cells)))
    if not row_bands:
        return None

    for side in ("right", "left"):
        near = []
        n_far = 0
        for word in words:
            center_y = (word[1] + word[3]) / 2
            if not (bbox.y0 - 2 <= center_y <= bbox.y1 + 2):
                continue
            rect = pymupdf.Rect(word[:4])
            if rect.intersects(bbox):
                continue
            if side == "right" and word[0] >= bbox.x1:
                gap = word[0] - bbox.x1
            elif side == "left" and word[2] <= bbox.x0:
                gap = bbox.x0 - word[2]
            else:
                continue
            if gap <= ADJACENT_COLUMN_SEARCH_PT:
                near.append((word, gap))
            elif gap <= ADJACENT_COLUMN_FAR_SEARCH_PT:
                n_far += 1
        if not near:
            continue
        if min(gap for _word, gap in near) > MAX_ADJACENT_COLUMN_GAP_PT:
            continue
        if n_far > MAX_ADJACENT_COLUMN_FAR_WORDS:
            continue
        covered = set()
        for word, _gap in near:
            center_y = (word[1] + word[3]) / 2
            for index, (top, bottom) in enumerate(row_bands):
                if top <= center_y <= bottom:
                    covered.add(index)
                    break
        if len(covered) / len(row_bands) < MIN_ADJACENT_COLUMN_ROW_COVERAGE:
            continue
        rect = pymupdf.Rect(
            min(word[0] for word, _gap in near),
            min(word[1] for word, _gap in near),
            max(word[2] for word, _gap in near),
            max(word[3] for word, _gap in near),
        )
        return rect, side
    return None


def bbox_clipped_rows(page: "pymupdf.Page", table: object) -> int:
    """Count the rows whose words the table's own outer edge cuts through.

    ``find_tables()`` sometimes draws its bbox through the middle of the last
    column's values ("0.454 \u00b1 0.024" clipped to "4 \u00b1 0"): the word begins inside
    the row's outer cell but extends past the table edge. ``extract_loss_share``
    cannot see it -- the word's center lies outside the bbox, so it is not counted
    against the grid -- and no interior boundary is contradicted. The rebuild's
    outer-cell rule heals exactly these words, so rows carrying them are the
    trigger for it.

    Parameters
    ----------
    page : pymupdf.Page
        Page the table was found on.
    table : PyMuPDF Table
        Table object from ``find_tables()`` whose ``rows[].cells`` rects define the
        grid.

    Returns
    -------
    int
        Rows where a word begins inside the row's outermost cell and extends more
        than ``COLUMN_CUT_MARGIN_PT`` beyond it.

    """
    try:
        rows = list(table.rows)  # type: ignore[attr-defined]
        words = page.get_text("words")
    except Exception:
        return 0
    clipped = 0
    for row in rows:
        cells = [cell[:4] for cell in (getattr(row, "cells", None) or []) if cell is not None]
        if not cells:
            continue
        first = cells[0]
        last = cells[-1]
        top = min(cell[1] for cell in cells)
        bottom = max(cell[3] for cell in cells)
        for word in words:
            center_y = (word[1] + word[3]) / 2
            if not top <= center_y < bottom:
                continue
            cut_right = word[0] < last[2] and word[0] >= last[0] and word[2] > last[2] + COLUMN_CUT_MARGIN_PT
            cut_left = word[2] > first[0] and word[2] <= first[2] and word[0] < first[0] - COLUMN_CUT_MARGIN_PT
            if cut_right or cut_left:
                clipped += 1
                break
    return clipped


def boundaries_to_dissolve(
    page: "pymupdf.Page", table: object, boundaries: list[tuple[float, tuple[int, ...]]]
) -> list[float]:
    """Select the contradicted boundaries that split one column rather than two.

    For each boundary, measure the horizontal gap between the nearest word ending
    left of it and the nearest word starting right of it, within the pair's own cell
    rects, on every row the boundary did not cut. A spurious boundary runs through a
    line of text, so those gaps are ordinary inter-word spaces; a real boundary sits
    in a column gutter. The median gap decides, against the same
    ``MIN_GUTTER_WIDTH_PT`` the word-gutter path trusts. A boundary with no
    measurable uncut row -- every row it bears either has its words cut or is blank
    on one side -- runs through printed content wherever it is tested, which is the
    spurious shape.

    Parameters
    ----------
    page : pymupdf.Page
        Page the table was found on.
    table : PyMuPDF Table
        Table object whose ``rows[].cells`` rects define the grid.
    boundaries : list of tuple of (float, tuple of int)
        Contradicted boundaries from ``contradicted_column_boundaries``: each an
        x-position with the indices of the rows whose words it cuts.

    Returns
    -------
    list of float
        The boundary x-positions whose crossings are spaces, not gutters --
        dissolving them merges the two halves of one printed column back together.

    """
    import pymupdf

    try:
        rows = list(table.rows)  # type: ignore[attr-defined]
        bbox = pymupdf.Rect(table.bbox)  # type: ignore[attr-defined]
        words = [word for word in page.get_text("words") if pymupdf.Rect(word[:4]).intersects(bbox)]
    except Exception:
        return []
    dissolve: list[float] = []
    for boundary, cut_row_indices in boundaries:
        cut = set(cut_row_indices)
        gaps: list[float] = []
        for row_index, row in enumerate(rows):
            if row_index in cut:
                continue
            cells = list(getattr(row, "cells", None) or [])
            left = right = None
            for cell in cells:
                if cell is None:
                    continue
                if abs(cell[2] - boundary) <= COLUMN_EDGE_TOLERANCE_PT:
                    left = cell
                elif abs(cell[0] - boundary) <= COLUMN_EDGE_TOLERANCE_PT:
                    right = cell
            if left is None or right is None:
                continue
            top = min(left[1], right[1])
            bottom = max(left[3], right[3])
            nearest_end: float | None = None
            nearest_start: float | None = None
            for word in words:
                center_y = (word[1] + word[3]) / 2
                if not top <= center_y < bottom:
                    continue
                if word[2] <= boundary + COLUMN_CUT_MARGIN_PT and word[0] >= left[0] - COLUMN_EDGE_TOLERANCE_PT:
                    nearest_end = word[2] if nearest_end is None else max(nearest_end, word[2])
                elif word[0] >= boundary - COLUMN_CUT_MARGIN_PT and word[2] <= right[2] + COLUMN_EDGE_TOLERANCE_PT:
                    nearest_start = word[0] if nearest_start is None else min(nearest_start, word[0])
            if nearest_end is not None and nearest_start is not None:
                gaps.append(nearest_start - nearest_end)
        if not gaps:
            dissolve.append(boundary)
            continue
        gaps.sort()
        median = gaps[len(gaps) // 2]
        if median < MIN_GUTTER_WIDTH_PT:
            dissolve.append(boundary)
    return dissolve


def rebuild_cells_from_words(
    page: "pymupdf.Page", table: object, dissolve_boundaries: list[float] | None = None
) -> list[list[str]] | None:
    """Rebuild a ``find_tables()`` grid's cell text from the page's own word boxes.

    ``Table.extract()`` assembles cell text from the characters its cell rects clip,
    so a glyph straddling a cell boundary is cut mid-character: the PMC dev corpus
    holds tables whose extracted cells read ``"Contro"`` / ``"perce ntage"`` while the
    page itself spells every word whole. The grid geometry is right -- the rulings
    corroborate it -- only the text assembly is wrong.

    Word boxes cannot be cut by construction: each of the page's words lands whole in
    the cell holding its center, exactly the guarantee the word-gutter path is built
    on. Within a cell, words keep the page's reading order, joined by spaces within a
    printed line and newlines across lines so the caller's hyphenation repair can run
    across wraps.

    Parameters
    ----------
    page : pymupdf.Page
        Page the table was found on.
    table : PyMuPDF Table
        Table object from ``find_tables()`` whose ``rows[].cells`` rects define the
        grid.
    dissolve_boundaries : list of float, optional
        Contradicted column boundaries (from ``contradicted_column_boundaries``) to
        dissolve while rebuilding: each row's cells abutting at one of these
        x-positions are unioned into a single cell before words are assigned, so a
        word the boundary cut lands whole in the reunited cell. Rows whose cells
        span across the position are unaffected.

    Returns
    -------
    list of list of str or None
        The rebuilt grid, or ``None`` when the table exposes no usable cell
        geometry -- the caller keeps the extracted text it already has.

    """
    try:
        rows = list(table.rows)  # type: ignore[attr-defined]
        words = page.get_text("words")
    except Exception:
        return None
    if not rows:
        return None

    rebuilt: list[list[str]] = []
    for row in rows:
        cells = getattr(row, "cells", None)
        if not cells:
            return None
        if dissolve_boundaries:
            cells = _dissolve_cell_edges(cells, dissolve_boundaries)
        filled = [index for index, cell in enumerate(cells) if cell is not None]
        first_filled = filled[0] if filled else -1
        last_filled = filled[-1] if filled else -1
        row_texts: list[str] = []
        for cell_index, cell in enumerate(cells):
            if cell is None:
                row_texts.append("")
                continue
            x0, y0, x1, y1 = cell[:4]
            lines: dict[tuple[int, int], list[str]] = {}
            for word in words:
                center_x = (word[0] + word[2]) / 2
                center_y = (word[1] + word[3]) / 2
                if not y0 <= center_y < y1:
                    continue
                # Half-open on the far edges so a word centered exactly on a shared
                # boundary lands in exactly one of the two cells meeting there.
                inside = x0 <= center_x < x1
                # A word that *begins* inside the row's outer cell belongs to it even
                # when its center leaks past the table edge: find_tables() draws its
                # bbox through the middle of such words ("0.454" clipped to "4" by
                # extract()), and the center rule alone would drop them into no cell
                # at all. Interior boundaries are untouched -- there the neighbouring
                # cell owns the center by the same rule.
                leaked = (cell_index == last_filled and center_x >= x1 and word[0] < x1) or (
                    cell_index == first_filled and center_x < x0 and word[2] > x0
                )
                if inside or leaked:
                    lines.setdefault((word[5], word[6]), []).append(str(word[4]))
            row_texts.append("\n".join(" ".join(parts) for _key, parts in sorted(lines.items())))
        rebuilt.append(row_texts)
    return rebuilt


def is_dot_leader_cell(text: str) -> bool:
    """Detect cells that are dot-leader noise rather than real content.

    Two shapes count: cells that are entirely dot characters (TOC dot-
    leaders that PyMuPDF allocated to their own column), and cells whose
    final line is a run of three-or-more dots (a section name with its
    dot-leader trailing into the bbox).

    Parameters
    ----------
    text : str
        Cell text to test.

    Returns
    -------
    bool
        True if the cell is dot-leader noise.

    """
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if _DOT_ONLY.match(stripped):
        return True
    return bool(_DOT_LEADER_TAIL.search(stripped))


def _extract_ruling_lines(
    drawings: list,
    min_hline_len: float,
    min_vline_len: float,
) -> tuple[list[tuple], list[tuple]]:
    """Extract horizontal and vertical ruling lines from drawing commands.

    Parameters
    ----------
    drawings : list
        Drawing commands from page.get_drawings()
    min_hline_len : float
        Minimum length for horizontal lines
    min_vline_len : float
        Minimum length for vertical lines

    Returns
    -------
    tuple[list[tuple], list[tuple]]
        Tuple of (h_lines, v_lines) where each line is (x0, y0, x1, y1)

    """
    h_lines: list[tuple] = []
    v_lines: list[tuple] = []

    for item in drawings:
        if "items" not in item:
            continue

        for drawing in item["items"]:
            if drawing[0] != "l":  # Not a line command
                continue

            p1, p2 = drawing[1], drawing[2]

            # Check if horizontal line (nearly horizontal)
            if abs(p1.y - p2.y) < 2:
                line_len = abs(p2.x - p1.x)
                if line_len >= min_hline_len:
                    h_lines.append((min(p1.x, p2.x), p1.y, max(p1.x, p2.x), p2.y))

            # Check if vertical line (nearly vertical)
            elif abs(p1.x - p2.x) < 2:
                line_len = abs(p2.y - p1.y)
                if line_len >= min_vline_len:
                    v_lines.append((p1.x, min(p1.y, p2.y), p2.x, max(p1.y, p2.y)))

    return h_lines, v_lines


def page_has_table_signals(
    page: "pymupdf.Page",
    threshold: float = TABLE_SIGNAL_RULING_THRESHOLD,
) -> bool:
    """Return True if the page has drawings that could indicate a table.

    Used to gate the expensive ``page.find_tables()`` call. Three signals
    count as evidence of tabular structure: two or more ruling lines, a
    single page-proportional closed rectangle (a framed region), or three
    or more smaller closed rectangles (a cell grid). Returns ``False`` for
    pages that contain only text, no drawings, or one-to-two decorative
    drawings — those are the bulk of typical prose documents and
    ``find_tables()`` produces no real output on them, only wasted CPU.

    On error (PyMuPDF failing to enumerate drawings), returns ``True`` so the
    caller falls back to the existing always-run behavior rather than silently
    losing real tables.

    Parameters
    ----------
    page : PyMuPDF Page
        Page to inspect.
    threshold : float
        Minimum ruling-line length as a fraction of the page width (horizontal)
        or height (vertical). Smaller than the ``detect_tables_by_ruling_lines``
        threshold because the gate only needs evidence that *something*
        table-shaped exists, not a fully-formed grid.

    Returns
    -------
    bool
        ``True`` if ``find_tables()`` should run, ``False`` to skip it.

    """
    try:
        drawings = page.get_drawings()
    except Exception:
        return True
    if not drawings:
        return False

    page_rect = page.rect
    min_hline_len = page_rect.width * threshold
    min_vline_len = page_rect.height * threshold * 0.3

    h_lines, v_lines = _extract_ruling_lines(drawings, min_hline_len, min_vline_len)
    if len(h_lines) + len(v_lines) >= 2:
        return True

    rect_count = 0
    for item in drawings:
        for cmd in item.get("items", []):
            if cmd[0] != "re":
                continue
            rect = cmd[1]
            if rect.width >= min_hline_len and rect.height >= min_vline_len:
                return True
            rect_count += 1
            if rect_count >= 3:
                return True

    return False


def _check_table_overlap(table_rect: "pymupdf.Rect", existing_rects: list["pymupdf.Rect"]) -> bool:
    """Check if a table rect overlaps significantly with existing tables.

    Returns
    -------
    bool
        True if there's significant overlap with any existing table

    """
    for existing in existing_rects:
        if abs(existing & table_rect) > abs(table_rect) * 0.5:
            return True
    return False


def _find_table_regions(
    h_lines: list[tuple],
    v_lines: list[tuple],
) -> list["pymupdf.Rect"]:
    """Find table regions from horizontal and vertical lines.

    Parameters
    ----------
    h_lines : list[tuple]
        Horizontal lines sorted by y-coordinate
    v_lines : list[tuple]
        Vertical lines

    Returns
    -------
    list[pymupdf.Rect]
        List of detected table bounding boxes

    """
    import pymupdf

    table_rects: list["pymupdf.Rect"] = []

    if len(h_lines) < 2 or len(v_lines) < 2:
        return table_rects

    # Look for regions with multiple h_lines and v_lines
    for i in range(len(h_lines) - 1):
        for j in range(i + 1, min(i + 10, len(h_lines))):
            y1 = h_lines[i][1]
            y2 = h_lines[j][1]

            # Find v_lines that span between these h_lines
            spanning_vlines = [v for v in v_lines if v[1] <= y1 + 5 and v[3] >= y2 - 5]

            if len(spanning_vlines) < 2:
                continue

            # Found a potential table - calculate bounds
            x_min = min(min(h_lines[i][0], h_lines[j][0]), min(v[0] for v in spanning_vlines))
            x_max = max(max(h_lines[i][2], h_lines[j][2]), max(v[2] for v in spanning_vlines))

            table_rect = pymupdf.Rect(x_min, y1, x_max, y2)

            if not table_rect.is_empty and not _check_table_overlap(table_rect, table_rects):
                table_rects.append(table_rect)

    return table_rects


def _collect_lines_for_tables(
    table_rects: list["pymupdf.Rect"],
    h_lines: list[tuple],
    v_lines: list[tuple],
) -> list[tuple[list[tuple], list[tuple]]]:
    """Collect lines that belong to each table region.

    Returns
    -------
    list[tuple[list[tuple], list[tuple]]]
        List of (table_h_lines, table_v_lines) for each table

    """
    table_lines = []
    for table_rect in table_rects:
        table_h_lines = [line for line in h_lines if table_rect.y0 <= line[1] <= table_rect.y1]
        table_v_lines = [line for line in v_lines if table_rect.x0 <= line[0] <= table_rect.x1]
        table_lines.append((table_h_lines, table_v_lines))
    return table_lines


def detect_tables_by_ruling_lines(
    page: "pymupdf.Page", threshold: float = 0.5
) -> tuple[list["pymupdf.Rect"], list[tuple[list[tuple], list[tuple]]]]:
    """Fallback table detection using ruling lines and text alignment.

    Uses page drawing commands to detect horizontal and vertical lines
    that form table structures, useful when PyMuPDF's table detection fails.

    Parameters
    ----------
    page : PyMuPDF Page
        PDF page to analyze for tables
    threshold : float, default 0.5
        Minimum line length ratio relative to page size for ruling lines

    Returns
    -------
    tuple[list[PyMuPDF Rect], list[tuple[list, list]]]
        Tuple containing:
            - List of bounding boxes for detected tables
            - List of (h_lines, v_lines) tuples for each table, where each line
              is a tuple of (x0, y0, x1, y1) coordinates

    """
    # Calculate minimum line lengths based on page dimensions
    page_rect = page.rect
    min_hline_len = page_rect.width * threshold
    min_vline_len = page_rect.height * threshold * 0.3

    # Extract ruling lines from drawings
    h_lines, v_lines = _extract_ruling_lines(page.get_drawings(), min_hline_len, min_vline_len)

    # Sort horizontal lines by y-coordinate for region detection
    h_lines.sort(key=lambda line: line[1])

    # Find table regions
    table_rects = _find_table_regions(h_lines, v_lines)

    # Collect lines for each table
    table_lines = _collect_lines_for_tables(table_rects, h_lines, v_lines)

    # Drop rects whose internal line count would produce an absurdly large
    # grid - those are essentially always bordered non-tabular content.
    filtered_rects: list["pymupdf.Rect"] = []
    filtered_lines: list[tuple[list[tuple], list[tuple]]] = []
    for rect, (th, tv) in zip(table_rects, table_lines, strict=True):
        # cols = len(v_lines) - 1, rows = len(h_lines) - 1
        if len(tv) - 1 > MAX_TABLE_COLS or len(th) - 1 > MAX_TABLE_ROWS:
            continue
        filtered_rects.append(rect)
        filtered_lines.append((th, tv))

    return filtered_rects, filtered_lines


def group_words_into_lines(words: list[tuple]) -> list[list[tuple]]:
    """Group word boxes into printed lines by vertical overlap.

    Two words share a line when their boxes overlap vertically by more than half the
    shorter box's height. Superscripts and subscripts overlap their base line well past
    that bar; consecutive printed lines do not.

    Parameters
    ----------
    words : list of tuple
        Word entries as returned by ``page.get_text("words")``:
        ``(x0, y0, x1, y1, text, ...)``.

    Returns
    -------
    list of list of tuple
        Lines in reading order, each line's words sorted by ``x0``.

    """
    lines: list[dict] = []
    for word in sorted(words, key=lambda entry: (entry[3], entry[0])):
        x0, y0, x1, y1 = word[:4]
        for line in lines:
            overlap = min(y1, line["y1"]) - max(y0, line["y0"])
            if overlap > 0.5 * min(y1 - y0, line["y1"] - line["y0"]):
                line["words"].append(word)
                line["y0"] = min(y0, line["y0"])
                line["y1"] = max(y1, line["y1"])
                break
        else:
            lines.append({"y0": y0, "y1": y1, "words": [word]})
    lines.sort(key=lambda line: line["y0"])
    return [sorted(line["words"], key=lambda entry: entry[0]) for line in lines]


def word_gutter_grid(words: list[tuple]) -> list[list[str]] | None:
    """Recover a table grid from word boxes alone: columns from gutters, one row per line.

    A gutter is a vertical band of x that at most :data:`MAX_GUTTER_INTRUSION_SHARE` of
    the region's printed lines intrude into, at least :data:`MIN_GUTTER_WIDTH_PT` wide.
    Column boundaries sit at gutter midpoints, so a word box can never be cut: every word
    lands whole in the column holding its center, and cell text is those words joined in
    x order. Running prose has no such bands -- justified text aligns its outer edges but
    scatters its inner gaps -- so a region yielding fewer than two columns is not a table
    to this detector.

    Parameters
    ----------
    words : list of tuple
        Word entries as returned by ``page.get_text("words")`` clipped to the region.

    Returns
    -------
    list of list of str or None
        Cell text per row, or ``None`` when no gutter-corroborated grid exists here.

    """
    # A rotated region must not be gridded in page coordinates. A landscape table read
    # this way groups perpendicular text into fake lines, and the grid that falls out
    # scrambles the reading order rather than merely mis-shaping it -- measured, a 28x4
    # truth table came back 8x12 with its containment destroyed. Unambiguously rotated
    # regions go to the transposed pass, which runs this same sweep in the table's own
    # frame; a region whose tall boxes are only marginally tall is *declined* instead,
    # exactly as before -- transposing upright text manufactures perfect "gutters" out
    # of its line spacing, so the dispatch needs stronger evidence than the decline.
    # Multi-character words only: an upright "I" is taller than wide too.
    sized = [word for word in words if len(str(word[4])) >= 3]
    if sized:
        tall = sum(1 for word in sized if (word[3] - word[1]) > (word[2] - word[0]))
        if tall > MAX_ROTATED_WORD_SHARE * len(sized):
            strongly_rotated = sum(
                1 for word in sized if (word[3] - word[1]) > MIN_ROTATED_WORD_ASPECT * (word[2] - word[0])
            )
            if strongly_rotated > MAX_ROTATED_WORD_SHARE * len(sized):
                return _transposed_gutter_grid(words)
            return None

    return _gutter_grid_core(words)


def _stream_order_mirrors(words: list[tuple]) -> tuple[bool, bool]:
    """Decide whether either transposed axis runs against reading order.

    Transposing a box swaps its axes, but a swap is a reflection, not a rotation: one
    axis of the transposed frame always runs backwards for one of the two rotation
    directions, and which one depends on whether the text was rotated clockwise or
    counter-clockwise -- which the boxes alone cannot say. PyMuPDF can: each word tuple
    carries its ``(block, line, word)`` position in the document stream, and the stream
    holds the text in the order it reads. Words later in their line sitting at smaller
    ``x`` means the reading axis is mirrored; later lines sitting at smaller ``y`` means
    the stacking axis is. Majority vote over every adjacent pair, so one out-of-band
    word (a superscript, a stray footnote marker) cannot flip an axis.

    Parameters
    ----------
    words : list of tuple
        Word entries **already transposed**, retaining their trailing
        ``(block, line, word)`` stream coordinates.

    Returns
    -------
    tuple of (bool, bool)
        Whether to mirror the reading (x) axis and the stacking (y) axis. Tuples
        without stream coordinates, or streams with no adjacent pairs to compare,
        vote for no mirror -- the unmirrored frame is then as good as any.

    """
    by_line: dict[tuple, list[tuple]] = {}
    for word in words:
        if len(word) < 8:
            return False, False
        by_line.setdefault((word[5], word[6]), []).append(word)

    read_pairs = read_reversed = 0
    for group in by_line.values():
        group.sort(key=lambda word: word[7])
        for left, right in zip(group, group[1:], strict=False):
            read_pairs += 1
            if right[0] + right[2] < left[0] + left[2]:
                read_reversed += 1

    ordered_lines = sorted(by_line.items(), key=lambda item: item[0])
    centers = [sum((word[1] + word[3]) / 2 for word in group) / len(group) for _, group in ordered_lines]
    stack_pairs = stack_reversed = 0
    for above, below in zip(centers, centers[1:], strict=False):
        stack_pairs += 1
        if below < above:
            stack_reversed += 1

    return (2 * read_reversed > read_pairs, 2 * stack_reversed > stack_pairs)


def _transposed_gutter_grid(words: list[tuple]) -> list[list[str]] | None:
    """Run the gutter sweep in a rotated region's own frame.

    Swapping each box's axes turns the region's vertical printed lines into horizontal
    ones, so the ordinary sweep applies unchanged -- gutters, guards and all. The swap
    leaves one axis running backwards depending on the rotation's direction, so both
    axes are checked against PyMuPDF's stream order and mirrored where they disagree;
    without that, one rotation direction would come back with its columns (or rows) in
    reverse and every cell in the wrong place, which is worse than the prose fallback
    this pass replaces.
    """
    transposed = [(word[1], word[0], word[3], word[2], word[4], *word[5:]) for word in words]
    mirror_x, mirror_y = _stream_order_mirrors(transposed)
    if mirror_x:
        transposed = [(-w[2], w[1], -w[0], w[3], w[4], *w[5:]) for w in transposed]
    if mirror_y:
        transposed = [(w[0], -w[3], w[2], -w[1], w[4], *w[5:]) for w in transposed]
    return _gutter_grid_core(transposed)


def _gutter_grid_core(words: list[tuple]) -> list[list[str]] | None:
    """Run the gutter sweep proper, over words whose frame is already reading-oriented."""
    lines = group_words_into_lines(words)
    if len(lines) < MIN_GUTTER_LINES:
        return None

    # Sweep the x axis: between consecutive interval endpoints the set of intruding
    # lines is constant, so intrusion counts only change at word-box edges.
    intervals = []  # (x0, x1, line_index) -- per line, the union is what matters
    for index, line in enumerate(lines):
        for word in line:
            intervals.append((word[0], word[2], index))
    edges = sorted({x for x0, x1, _ in intervals for x in (x0, x1)})
    if len(edges) < 2:
        return None

    max_intruding = MAX_GUTTER_INTRUSION_SHARE * len(lines)
    gutters: list[tuple[float, float]] = []  # merged maximal clear bands
    band_start: float | None = None
    for left, right in zip(edges, edges[1:], strict=False):
        mid = (left + right) / 2
        intruding = len({index for x0, x1, index in intervals if x0 < mid < x1})
        if intruding <= max_intruding:
            if band_start is None:
                band_start = left
        else:
            if band_start is not None and left - band_start >= MIN_GUTTER_WIDTH_PT:
                gutters.append((band_start, left))
            band_start = None
    # A trailing clear band ends at the region's edge: that is the right margin, not a
    # column separator, and the leading band is the left margin for the same reason --
    # margins separate the table from the page, not cell from cell. Bands starting at
    # edges[0] are excluded by construction only when a word starts there, so drop any
    # band touching the outer edges explicitly.
    boundaries = [(start + end) / 2 for start, end in gutters if start > edges[0] and end < edges[-1]]
    if len(boundaries) < MIN_WORD_GUTTER_COLS - 1:
        return None

    line_rows: list[list[str]] = []
    line_extents: list[tuple[float, float]] = []
    for line in lines:
        cells: list[list[str]] = [[] for _ in range(len(boundaries) + 1)]
        for word in line:
            center = (word[0] + word[2]) / 2
            column = sum(1 for boundary in boundaries if boundary < center)
            cells[column].append(str(word[4]))
        line_rows.append([" ".join(parts) for parts in cells])
        line_extents.append((min(word[1] for word in line), max(word[3] for word in line)))
    return merge_continuation_lines(line_rows, line_extents)


def _mostly_numeric_cell(cell: str) -> bool:
    """Whether digits dominate a cell's alphanumeric characters."""
    alnum = [character for character in cell if character.isalnum()]
    if not alnum:
        return False
    digits = sum(1 for character in alnum if character.isdigit())
    return digits / len(alnum) > ROW_NUMERIC_CELL_DIGIT_SHARE


def _numeric_cell_count(row: list[str]) -> int:
    return sum(1 for cell in row if cell and _mostly_numeric_cell(cell))


def _groups_stack_column_cells(line_rows: list[list[str]], groups: list[list[int]]) -> bool:
    """Whether any group holds a column with three-plus separate filled runs.

    A cell fills contiguous lines, so a column inside one logical row is a single run
    (two tolerated -- a ragged prose cell can leave one hole). Three or more runs is a
    stack of distinct cells: the group is fusing rows, however plausible its gap
    structure looked, and the grouping that proposed it cannot be trusted.
    """
    for group in groups:
        columns = max(len(line_rows[index]) for index in group)
        for column in range(columns):
            runs = 0
            previous_filled = False
            for index in group:
                row = line_rows[index]
                filled = column < len(row) and bool(row[column])
                if filled and not previous_filled:
                    runs += 1
                previous_filled = filled
            if runs > ROW_GROUP_MAX_COLUMN_RUNS:
                return True
    return False


def _groups_fuse_numeric_rows(line_rows: list[list[str]], groups: list[list[int]]) -> bool:
    """Whether any group would fuse two adjacent lines that are each a numeric data row.

    No publisher wraps a numeric row, so a grouping that joins two of them has mistaken
    row separation for cell wrapping and cannot be trusted anywhere on the grid.
    """
    for group in groups:
        for first, second in zip(group, group[1:], strict=False):
            if (
                _numeric_cell_count(line_rows[first]) >= ROW_FUSE_MIN_NUMERIC_CELLS
                and _numeric_cell_count(line_rows[second]) >= ROW_FUSE_MIN_NUMERIC_CELLS
            ):
                return True
    return False


def _gap_row_groups(line_rows: list[list[str]], line_extents: list[tuple[float, float]]) -> list[list[int]] | None:
    """Group printed lines into logical rows by the jump in their inter-line gaps.

    A wrapped continuation sits one leading below its row; the next row sits leading
    plus row padding below. When the sorted gaps show a first jump clearing both the
    height-share floor and the ratio bar, gaps above the jump are row boundaries.
    Uniform leading has no such jump and returns ``None`` -- the per-line rows stand,
    exactly as before. Vertically centered multi-line cells interlace their baselines
    across columns, so gaps go *negative* inside a row; a negative baseline satisfies
    the ratio vacuously and the height-share floor still applies.
    """
    if len(line_extents) != len(line_rows) or len(line_rows) < 3:
        return None
    gaps = [line_extents[index][0] - line_extents[index - 1][1] for index in range(1, len(line_extents))]
    heights = sorted(y1 - y0 for y0, y1 in line_extents)
    median_height = heights[len(heights) // 2]
    unique_gaps = sorted({round(gap, 2) for gap in gaps})
    if len(unique_gaps) < 2:
        return None

    for lower, upper in zip(unique_gaps, unique_gaps[1:], strict=False):
        if upper - lower < ROW_GAP_JUMP_MIN_HEIGHT_SHARE * median_height:
            continue
        if lower > 0 and upper / lower < ROW_GAP_JUMP_MIN_RATIO:
            continue
        threshold = (lower + upper) / 2

        groups: list[list[int]] = []
        current = [0]
        for index, gap in enumerate(gaps, start=1):
            if gap > threshold:
                groups.append(current)
                current = [index]
            else:
                current.append(index)
        groups.append(current)
        if len(groups) < 2 or _groups_fuse_numeric_rows(line_rows, groups):
            return None
        if _groups_stack_column_cells(line_rows, groups):
            return None

        if _sparse_row_share(line_rows, groups) > ROW_GROUP_MAX_SPARSE_SHARE:
            # This jump cut below the row population instead of between it and the
            # wraps. Try the next one up before handing the table to the fill rules.
            continue
        return groups
    return None


def _sparse_row_share(line_rows: list[list[str]], groups: list[list[int]]) -> float:
    """Share of grouped rows that fill at most half their columns.

    The fingerprint of a threshold set below the row population: every wrapped line is
    left standing as a row of its own, so the grid fills with half-empty rows holding one
    cell's continuation each. all2md prints them on 33.2% of the articles where it loses a
    table, against docling's 12.0% (#438).
    """
    if not groups:
        return 0.0
    width = max((len(line_rows[index]) for group in groups for index in group), default=0)
    if width == 0:
        return 0.0
    sparse = sum(1 for group in groups if 0 < len(_filled_columns(line_rows, group)) * 2 <= width)
    return sparse / len(groups)


def _filled_columns(line_rows: list[list[str]], group: list[int]) -> set[int]:
    return {column for index in group for column, cell in enumerate(line_rows[index]) if cell}


def _rows_from_groups(line_rows: list[list[str]], groups: list[list[int]]) -> list[list[str]]:
    """Assemble merged rows from line groups, joining cell fragments with newlines."""
    merged: list[list[str]] = []
    for group in groups:
        row = list(line_rows[group[0]])
        for index in group[1:]:
            for column, fragment in enumerate(line_rows[index]):
                if not fragment:
                    continue
                row[column] = f"{row[column]}\n{fragment}" if row[column] else fragment
        merged.append(row)
    return merged


def merge_continuation_lines(
    line_rows: list[list[str]],
    line_extents: list[tuple[float, float]] | None = None,
    *,
    continuation_within_start_columns: bool = False,
) -> list[list[str]]:
    """Fold wrapped cell lines into their logical row.

    One printed line is not one table row: a cell holding more than a line of text wraps,
    and emitting each printed line as a row splits every wrapped cell -- including through
    hyphenated words, which the whole-word guarantee is supposed to make impossible.
    Three signals decide, each measured on the PMC corpus and each guarded:

    1. **Gap grouping** (`_gap_row_groups`): when inter-line gaps separate into a wrap
       population and a row population, the rows are geometric fact and the fill-based
       rules below never run. Abandoned whole when it would fuse adjacent numeric rows
       (the header-seam trap).
    2. **Single-column wraps**: a line filling exactly one column of a 3+-column grid,
       sitting closer to the previous line than this table's median gap, is a wrapped
       fragment -- the shape the anchor rule cannot see, because the wrap lives *in*
       the anchor column while every other column is empty.
    3. **The anchor rule**: the leftmost column filled on at least 60% of lines names
       the rows; a line with that cell empty continues the row above. A sparser anchor
       (down to the 20% floor) is believed only when the merge it implies survives the
       numeric-fusion guard -- a row-label column in a heavily wrapped table is filled
       only on row starts, but a sparse *data* column must not be mistaken for one.

    Fully-dense numeric tables have uniform gaps, no single-column lines, and every
    anchor cell filled, so nothing merges and the per-line rows stand.

    ``continuation_within_start_columns`` extends the sparse-anchor path's
    no-new-columns test to *every* anchor continuation: a line only folds into the row
    above when its filled columns are a subset of the columns that row already fills.
    The find_tables() path asks for this because its row bboxes tile the grid -- every
    gap is exactly zero -- so the geometric rules above are inert and the anchor rule
    carries the whole merge unaided. Measured on the PMC dev corpus: a two-tier header
    whose second row ("# | Acc | # | Acc") has an empty label cell fused into the tier
    above, interleaving both rows' grams (0.87 -> 0.79); its filled columns were
    exactly the ones the first tier left empty. Word-gutter callers keep the default:
    their middle-aligned continuation shape legitimately fills fresh columns, and
    their real inter-line gaps give the guards above their say first.

    Cell fragments join with a newline rather than a space so the caller can run its
    hyphenation repair across the join, exactly as the paragraph path does.
    """
    column_count = max(len(row) for row in line_rows)

    if line_extents is not None:
        groups = _gap_row_groups(line_rows, line_extents)
        if groups is not None:
            return _rows_from_groups(line_rows, groups)

    gaps: list[float] | None = None
    median_gap = 0.0
    if line_extents is not None and len(line_extents) == len(line_rows) and len(line_rows) > 1:
        gaps = [line_extents[index][0] - line_extents[index - 1][1] for index in range(1, len(line_extents))]
        median_gap = sorted(gaps)[len(gaps) // 2]

    fill = [sum(1 for row in line_rows if column < len(row) and row[column]) for column in range(column_count)]
    trusted_anchor = next(
        (column for column in range(column_count) if fill[column] >= ROW_ANCHOR_TRUSTED_FILL * len(line_rows)),
        max(range(column_count), key=lambda column: (fill[column], -column)),
    )
    anchor = trusted_anchor
    sparse_anchor = next(
        (column for column in range(column_count) if fill[column] >= ROW_ANCHOR_MIN_FILL * len(line_rows)),
        trusted_anchor,
    )
    if sparse_anchor < trusted_anchor:
        # A sparser, further-left candidate implies a bolder merge. Simulate it: the
        # groups it builds must not fuse adjacent numeric rows, or it is a data column.
        candidate_groups: list[list[int]] = []
        for index, row in enumerate(line_rows):
            if candidate_groups and not (sparse_anchor < len(row) and row[sparse_anchor]):
                candidate_groups[-1].append(index)
            else:
                candidate_groups.append([index])

        # And the merge must look like wrapping, not like new rows under a group label:
        # a wrapped continuation only *continues* columns its row start already filled,
        # while a grouped-label table's inner rows introduce fresh content in columns
        # the label line left empty (measured: an exercise-program table whose sparse
        # first column held section names fused 13 real rows into 4 without this).
        def _introduces_new_columns(group: list[int]) -> bool:
            start_columns = {column for column, cell in enumerate(line_rows[group[0]]) if cell}
            return any(
                column not in start_columns
                for index in group[1:]
                for column, cell in enumerate(line_rows[index])
                if cell
            )

        if (
            not _groups_fuse_numeric_rows(line_rows, candidate_groups)
            and not _groups_stack_column_cells(line_rows, candidate_groups)
            and not any(_introduces_new_columns(group) for group in candidate_groups)
        ):
            anchor = sparse_anchor

    merged: list[list[str]] = []
    for index, row in enumerate(line_rows):
        filled_columns = [column for column, cell in enumerate(row) if cell]
        single_column_wrap = (
            gaps is not None
            and merged
            and column_count >= 3
            and len(filled_columns) == 1
            and gaps[index - 1] < median_gap
        )
        anchor_continuation = merged and not (anchor < len(row) and row[anchor])
        if anchor_continuation and continuation_within_start_columns:
            row_columns = {column for column, cell in enumerate(merged[-1]) if cell}
            anchor_continuation = all(column in row_columns for column in filled_columns)
        if not (single_column_wrap or anchor_continuation):
            merged.append(list(row))
            continue
        target = merged[-1]
        for column, fragment in enumerate(row):
            if not fragment:
                continue
            target[column] = f"{target[column]}\n{fragment}" if target[column] else fragment
    return merged


# The integer forms a bibliography numbers its entries with: ``42.``, ``42``, ``[42]``,
# ``42)`` -- the paren form measured on the PMC corpus as the one spelling the guard
# missed.
_BIB_INTEGER = re.compile(r"^\[?(\d{1,3})[.)\]]?$")
# A run of consecutive integers needs this many members before it reads as numbering
# rather than coincidence.
MIN_BIB_SEQUENTIAL_CELLS = 5
# Bibliographies are sentences chopped into cells; tables are values placed in them.
# Measured on the PMC corpus over the grids the sequential-integer test flags: the four
# reference-page grids had a 90th-percentile filled-cell length of 10-15 words, the three
# real tables with a sequential "No." column 1-8. The bar sits in the gap.
MIN_BIB_CELL_WORDS_P90 = 9


def looks_like_numbered_bibliography(grid: list[list[str]]) -> bool:
    """Decide whether this grid is a numbered reference list rather than a table.

    A bibliography that reaches a grid detector is the worst false positive available:
    row-major cell order interleaves the page's columns, so every citation is scrambled
    rather than merely re-wrapped. Two signals must agree before a grid is condemned:
    a column that counts (five-plus consecutive integers -- ``42.``, ``43.``, ``44.``),
    and prose-length cells beside it. Either alone describes plenty of real tables; a
    numbered column of sentences is how a reference list is typeset.
    """
    word_counts = sorted(len(cell.split()) for row in grid for cell in row if cell.strip())
    if not word_counts:
        return False
    if word_counts[int(0.9 * len(word_counts))] < MIN_BIB_CELL_WORDS_P90:
        return False

    column_count = max(len(row) for row in grid)
    for column in range(column_count):
        values: list[int | None] = []
        for row in grid:
            if column < len(row) and row[column].strip():
                match = _BIB_INTEGER.match(row[column].strip())
                values.append(int(match.group(1)) if match else None)
        integers = [value for value in values if value is not None]
        if len(integers) < MIN_BIB_SEQUENTIAL_CELLS or len(integers) < 0.8 * len(values):
            continue
        consecutive = sum(1 for a, b in zip(integers, integers[1:], strict=False) if b == a + 1)
        if consecutive >= 0.8 * (len(integers) - 1):
            return True
    return False


# A sentence ends where a terminator meets whitespace or the cell does. A decimal point
# inside a number ("0.54") is followed by a digit, so a row of measurements reads as no
# sentences however long it runs -- which is what keeps a shredded data row a table.
_SENTENCE_END = re.compile(r"[.!?](?:\s|$)")
# Running prose reads as prose whatever it is fenced inside: 60 words is several printed
# lines, well past any label or value a table cell carries.
MIN_PROSE_CELL_WORDS = 60
# Enough terminators that the cell is a passage rather than one long caption.
MIN_PROSE_CELL_SENTENCES = 3
# And the passage must BE the grid, not sit in it.
MIN_PROSE_CELL_SHARE = 0.60
# ...where "the grid" is cells of prose. A real data table whose values are one word each
# can be dominated by a caption absorbed into it and is still a table.
MIN_PROSE_GRID_MEDIAN_WORDS = 5


def looks_like_gridded_prose(grid: "Sequence[Sequence[str | None]]") -> bool:
    """Decide whether this grid is a passage of prose the detector fenced.

    A journal first page prints its keywords beside its abstract, a peer-review page
    prints a reviewer's comments beside an author's response, and a magazine prints a
    figure between two columns of body text. Each of those separates text by whitespace
    a grid detector reads as a column boundary, so the abstract arrives as a table cell
    -- which reads wrong for a human and, where the region spans two columns, interleaves
    them line by line inside the cell.

    Three signals must agree before a grid is condemned, because no two of them separate
    the corpus. Censused over the 411 tables emitted across the 66-article dev corpus and
    the 110-article held-out corpus, the twelve grids holding a 60-word cell of three or
    more sentences are:

    ==========  ======  ======  ======  =======================================
    dominance   median  cells   verdict what it is
    ==========  ======  ======  ======  =======================================
    93% - 71%   7 - 503 2 - 6   reject  keywords/abstract boxes, a peer review
    70%         1       26      KEEP    a 6x5 data grid with a caption absorbed
    69%         49      3       reject  an abstract beside its affiliations
    51%         53      6       KEEP    three parallel case descriptions
    ==========  ======  ======  ======  =======================================

    Dominance orders the two middle rows *backwards* -- the real table dominates more
    than the defect below it -- so the median cell length is what separates them, and
    dominance is what separates the pair from the real table at the bottom. Either alone
    condemns a real table. Together they take all ten defects and none of the 401 other
    grids, and the verdict does not move anywhere in the ranges 40-80 words, 2-4
    sentences, 55-65% share or 3-7 median words: 81 of 81 combinations tried agree.

    Ground truth cannot referee this on its own: three of the real tables here are
    ``<table-wrap>`` elements deposited as *graphics*, so JATS carries their captions and
    none of their cells. A rule scored only against the text of the ground truth would
    read them as absent and reject them.
    """
    lengths: list[int] = []
    longest = ""
    for row in grid:
        for cell in row:
            text = (cell or "").strip()
            if not text:
                continue
            lengths.append(len(text.split()))
            if lengths[-1] > len(longest.split()):
                longest = text
    total = sum(lengths)
    n_words = len(longest.split())
    if not total or n_words < MIN_PROSE_CELL_WORDS or n_words < MIN_PROSE_CELL_SHARE * total:
        return False
    if sorted(lengths)[len(lengths) // 2] < MIN_PROSE_GRID_MEDIAN_WORDS:
        return False
    return len(_SENTENCE_END.findall(longest)) >= MIN_PROSE_CELL_SENTENCES
