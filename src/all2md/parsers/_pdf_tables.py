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
    import pymupdf

__all__ = [
    "MAX_DOT_LEADER_CELL_RATIO",
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
    "MIN_WORD_GUTTER_COLS",
    "TABLE_REGION_STRATEGIES",
    "TABLE_SIGNAL_RULING_THRESHOLD",
    "detect_tables_by_ruling_lines",
    "group_words_into_lines",
    "is_dot_leader_cell",
    "looks_like_numbered_bibliography",
    "page_has_table_signals",
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
# layout has -- a reference list, a chart legend beside its axis, a title page -- so a
# single band is not evidence of a table, it is evidence of columns. Measured on the
# PMC corpus: 8 of the 13 genuinely non-tabular regions this pass would otherwise emit
# were two-column (bibliographies split at the page's own column gutter), against 1 of
# the 34 real tables it recovers.
MIN_WORD_GUTTER_COLS = 3
# Share of a region's multi-character words that may stand taller than wide before the
# region reads as rotated and the gutter pass declines it.
MAX_ROTATED_WORD_SHARE = 0.5


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
    # Rotated regions are not this detector's to grid. A landscape table read in page
    # coordinates groups perpendicular text into fake lines, and the grid that falls out
    # scrambles the reading order rather than merely mis-shaping it -- measured, a 28x4
    # truth table came back 8x12 with its containment destroyed, where the rotation-aware
    # prose path reads it fine. A multi-character word taller than it is wide is almost
    # surely rotated; single characters are excluded because an upright "I" is too.
    sized = [word for word in words if len(str(word[4])) >= 3]
    if sized:
        rotated = sum(1 for word in sized if (word[3] - word[1]) > (word[2] - word[0]))
        if rotated > MAX_ROTATED_WORD_SHARE * len(sized):
            return None

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
    for line in lines:
        cells: list[list[str]] = [[] for _ in range(len(boundaries) + 1)]
        for word in line:
            center = (word[0] + word[2]) / 2
            column = sum(1 for boundary in boundaries if boundary < center)
            cells[column].append(str(word[4]))
        line_rows.append([" ".join(parts) for parts in cells])
    return _merge_continuation_lines(line_rows)


def _merge_continuation_lines(line_rows: list[list[str]]) -> list[list[str]]:
    """Fold wrapped cell lines into their logical row.

    One printed line is not one table row: a cell holding more than a line of text wraps,
    and emitting each printed line as a row splits every wrapped cell -- including through
    hyphenated words, which the whole-word guarantee is supposed to make impossible. The
    anchor is the leftmost column filled on at least 60% of lines: a line with the anchor
    cell empty is a continuation of the row above it, because a new logical row announces
    itself in the column that names rows. Leftmost-qualifying rather than most-filled on
    purpose -- a heavily wrapped description column is *more* filled than the key column
    beside it, and choosing it would read every real row as a continuation of the first.
    Fully-dense numeric tables have every anchor cell filled, so nothing merges and the
    per-line rows stand.

    Cell fragments join with a newline rather than a space so the caller can run its
    hyphenation repair across the join, exactly as the paragraph path does.
    """
    column_count = max(len(row) for row in line_rows)
    fill = [sum(1 for row in line_rows if column < len(row) and row[column]) for column in range(column_count)]
    anchor = next(
        (column for column in range(column_count) if fill[column] >= 0.6 * len(line_rows)),
        max(range(column_count), key=lambda column: (fill[column], -column)),
    )

    merged: list[list[str]] = []
    for row in line_rows:
        is_continuation = merged and not (anchor < len(row) and row[anchor])
        if not is_continuation:
            merged.append(list(row))
            continue
        target = merged[-1]
        for column, fragment in enumerate(row):
            if not fragment:
                continue
            target[column] = f"{target[column]}\n{fragment}" if target[column] else fragment
    return merged


# The integer forms a bibliography numbers its entries with: ``42.``, ``42``, ``[42]``.
_BIB_INTEGER = re.compile(r"^\[?(\d{1,3})[.\]]?$")
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
