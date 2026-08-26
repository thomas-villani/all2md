#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/pdf.py
"""PDF to AST converter.

This module provides conversion from PDF documents to AST representation.
It replaces direct markdown string generation with structured AST building,
enabling multiple rendering strategies and improved testability.

"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Callable, Optional, Union

from all2md.options.pdf import PdfOptions
from all2md.utils.attachments import create_attachment_sequencer
from all2md.utils.parser_helpers import attachment_result_to_image_node

if TYPE_CHECKING:
    import pymupdf

    from all2md.parsers._ocr import OcrParagraph

from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from all2md.ast import (
    Code,
    CodeBlock,
    Comment,
    Document,
    Emphasis,
    Heading,
    Link,
    List,
    ListItem,
    Node,
    SourceLocation,
    Strong,
    TableCell,
    TableRow,
    Text,
)
from all2md.ast import (
    Figure as AstFigure,
)
from all2md.ast import (
    Paragraph as AstParagraph,
)
from all2md.ast import (
    Table as AstTable,
)
from all2md.ast import (
    extract_text as extract_node_text,
)
from all2md.ast.transforms import InlineFormattingConsolidator, extract_nodes
from all2md.constants import (
    DEPS_PDF,
    DEPS_PDF_LAYOUT,
    PDF_CAPTION_DEDUP_MIN_CHARS,
    PDF_CAPTION_REGION_SUPPRESS_MARGIN,
    PDF_MIN_PYMUPDF_VERSION,
    PDF_READING_ORDER_MIN_ROW_TOLERANCE,
    PDF_READING_ORDER_ROW_TOLERANCE_RATIO,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import DependencyError, MalformedFileError, PasswordProtectedError, ValidationError

# Import from private submodules
from all2md.parsers._pdf_columns import detect_columns, split_gutter_merged_blocks
from all2md.parsers._pdf_headers import IdentifyHeaders, compute_line_style
from all2md.parsers._pdf_images import detect_image_caption, extract_page_images
from all2md.parsers._pdf_layout import (
    PageLayoutPredictions,
    annotate_blocks_with_layout,
    annotate_lines_with_layout,
    is_layout_available,
    match_predictions_to_blocks,
    native_find_tables,
    predict_page_layout,
)
from all2md.parsers._pdf_numbering import parse_numbering_prefix
from all2md.parsers._pdf_ocr import (
    dehyphenate_blocks,
    dehyphenate_text,
)
from all2md.parsers._pdf_ocr import (
    should_use_ocr as _should_use_ocr,
)
from all2md.parsers._pdf_tables import (
    MAX_DOT_LEADER_CELL_RATIO,
    MAX_EXTRACT_LOSS_SHARE,
    MAX_ROW_EXTENT_OVERLAP_PT,
    MAX_SPLIT_WORD_RATIO,
    MAX_TABLE_COLS,
    MAX_TABLE_EMPTY_RATIO,
    MAX_TABLE_ROWS,
    MAX_TWO_COLUMN_REGION_DRAWINGS,
    MIN_COLUMN_CUT_ROWS,
    MIN_FILLED_FOR_UNIFORMITY_CHECK,
    MIN_REBUILD_CHAR_RATIO,
    MIN_TABLE_COLS,
    MIN_TABLE_ROWS,
    TABLE_REGION_STRATEGIES,
    adjacent_clipped_column,
    bbox_clipped_rows,
    boundaries_to_dissolve,
    contradicted_column_boundaries,
    detect_tables_by_ruling_lines,
    extract_loss_share,
    is_dot_leader_cell,
    looks_like_gridded_prose,
    looks_like_numbered_bibliography,
    merge_continuation_lines,
    page_has_table_signals,
    rebuild_cells_from_words,
    split_word_ratio,
    word_gutter_grid,
)
from all2md.parsers._pdf_text import (
    classify_line_rotation,
    clipped_textbox,
    collapse_whitespace_runs,
    extract_rotated_text,
    format_rotation_note,
    inline_has_text,
)
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.encoding import normalize_stream_to_bytes
from all2md.utils.inputs import validate_and_convert_input, validate_page_range
from all2md.utils.metadata import (
    PDF_FIELD_MAPPING,
    DocumentMetadata,
    extract_dict_metadata,
)

logger = logging.getLogger(__name__)

#: Fractions of the page height treated as the header and footer zones when
#: auto-detecting running furniture.
HEADER_ZONE_FRACTION = 0.2
FOOTER_ZONE_FRACTION = 0.8

#: Fewest pages that can show repetition. Two pages are enough: a block in the same
#: place on both has repeated. (Three used to be required, which silently disabled
#: ``auto_trim_headers_footers`` on every two-page document.)
MIN_PAGES_FOR_RUNNING_DETECTION = 2

#: How far, in points, a running header/footer may drift between pages and still count
#: as the same one. Real furniture is anchored to the page; body text that happens to
#: recur is anchored to the text flow and moves. The zone boundary is taken from the
#: innermost matching block, so a false positive trims everything outside it on every
#: page -- this tolerance is what keeps that aimed at furniture.
RUNNING_POSITION_TOLERANCE = 5.0

#: Runs of digits in a running header/footer, which differ from page to page precisely
#: because it is running furniture.
_RUNNING_DIGITS = re.compile(r"\d+")

#: How far apart, as a multiple of the line's own height, two heading lines may sit and
#: still be the same heading wrapped onto a second printed line. Set as a ratio rather
#: than in points so it means the same thing for a 24pt article title and a 9pt
#: subheading. Consecutive *distinct* headings are separated by the space above a new
#: section, which is what puts them beyond this.
HEADING_WRAP_GAP_RATIO = 1.6

#: How much of the two lines' shared measure the *first* line must fill for the second to
#: be its wrap. A line only wraps because it ran out of room, so a "continuation" that
#: extends past the line above it is a different heading -- a section title with its
#: subsection printed directly beneath was fusing into one heading this way, losing both
#: titles (#400). Measured on the PMC born-digital corpus (307 merges, labeled against
#: JATS): true wraps fill 0.852-1.0 (plausible unlabeled ones 0.822+), while fused pairs
#: separable by width sit at 0.222-0.835. 0.8 keeps every measured wrap and cuts the
#: fused band; pairs whose first line is the wider one (`Methods` + `Animals`) stay
#: geometrically inseparable and still merge.
HEADING_WRAP_MIN_FILL = 0.8


def _span_union_bbox(spans: list) -> tuple[float, float, float, float] | None:
    """Bounding box covering every span on a line, or None if none carry one.

    The line's own bbox is not in scope where headings are emitted, and a span union is
    the same rectangle for this purpose: spans partition the line.
    """
    boxes = [s["bbox"] for s in spans if s.get("bbox")]
    if not boxes:
        return None
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


#: Inline nodes that can wrap the text a line opens with. A span's font flags become
#: ``Strong``/``Emphasis`` and a hyperlink becomes ``Link``, so a marker printed in bold, in
#: italic, or inside a link arrives wrapped rather than as a bare ``Text``. ``Superscript``
#: is deliberately absent: a superscript digit opening a line is a footnote or citation
#: reference, and descending into one would read ``1. Smith et al.`` off a footnote.
_INLINE_WRAPPERS = (Strong, Emphasis, Link)

#: How much of a line's opening text the marker tests need. The longest marker they accept
#: is a run of digits, a ``.`` or ``)`` and a space, so this is generous; it exists to stop
#: the walk after a few nodes rather than to bound what counts as a marker.
_LEADING_TEXT_CHARS = 16

#: A bullet standing alone, with the space that follows it not yet read. The walk crosses a
#: node boundary only while what it holds matches this -- see :func:`_leading_inline_text`.
#: Numbers are deliberately not here, and that is the whole of what keeps a bibliography
#: from becoming an ordered list.
_BULLET_AWAITING_ITS_SPACE = re.compile("^[-–—*+•◦▪▫o]$")


def _leading_inline_text(content: list[Node], limit: int = _LEADING_TEXT_CHARS) -> str:
    """Return the text a paragraph or line *opens with*, descending into inline wrappers.

    Reading the first top-level ``Text`` node instead gets the question wrong in both
    directions. A bullet set in a symbol font is italic by its font flags, so it arrives as
    ``Emphasis(Text("-"))`` and the line has no top-level ``Text`` at all -- it reads as
    empty and never starts a list. A citation opening with a styled journal name has its
    first top-level ``Text`` in the *middle* of the line, so ``Nature 12. 45-67`` reported
    an ordered marker and became a list item.

    Reading the raw spans instead is no better, and is the reason this is not simply a text
    join over ``line["spans"]``: ``_process_text_spans_to_inline`` rewrites four bullet
    glyphs (``U+F0B7``, ``U+00B7``, ``U+2022``, ``U+25CF``) to ``-``, and three of the four
    are not markers in their printed form. The conversion is what makes a symbol-font bullet
    recognisable, so detection has to run after it.

    The walk crosses a node boundary **only while what it has read so far is a lone
    bullet**, waiting on the space that follows it. A bullet is its own span by typographic
    necessity -- it is set in a different font from the text -- and the letter ``o`` is only
    a bullet when a space follows, so without that one step the rule that keeps "office"
    from being a bullet could never fire and Word's second-level bullets could never be
    recognised at all.

    Numbers get no such step, and that restriction is the load-bearing part. A numbered
    marker arrives split exactly the same way -- ``Text("44.")`` then ``Text(" Konema,
    Nigeria ...")`` -- and nothing in the PDF distinguishes the 44th bibliography entry from
    the 44th item of a list. Reading across that boundary turned reference lists into
    ordered lists, whereupon the renderer renumbered them from 1 and destroyed every
    citation number in the document. A numbered marker must therefore be complete within one
    node, which is exactly what it was before.

    ``Code`` and anything else that is not an inline wrapper stops the walk: a line opening
    with inline code does not open with a list marker, and reporting the text past it would
    reintroduce the middle-of-the-line reading.
    """
    text = ""
    for node in content:
        if isinstance(node, Text):
            piece = node.content
        elif isinstance(node, _INLINE_WRAPPERS):
            piece = _leading_inline_text(node.content, limit)
        else:
            break
        if text and not _BULLET_AWAITING_ITS_SPACE.match(text.strip()):
            break
        text += piece
        if len(text.lstrip()) >= limit:
            break
    return text


def _opening_line_text(content: list[Node], limit: int = _LEADING_TEXT_CHARS) -> str:
    """Everything a line opens with, wrappers descended and node boundaries ignored.

    The liberal counterpart to :func:`_leading_inline_text`, and safe only where it is used.
    The item-split test runs *inside* a paragraph already known to be a list, so reading
    across node boundaries there can re-split a list that exists but can never create one --
    and it has to read across them, because a numbered item's marker is routinely a span of
    its own and every item after the first would otherwise run into its predecessor.

    The tests that *create* lists cannot use this, which is the whole distinction between
    the two readers: a bibliography entry is a numbered marker in its own span too, and
    creating a list from one renumbers the references from 1.
    """
    text = ""
    for node in content:
        if isinstance(node, Text):
            text += node.content
        elif isinstance(node, _INLINE_WRAPPERS):
            text += _opening_line_text(node.content, limit)
        else:
            break
        if len(text.lstrip()) >= limit:
            break
    return text


def _consume_leading_chars(content: list[Node], count: int) -> tuple[list[Node], int]:
    """Drop the first ``count`` characters of ``content``, descending into inline wrappers.

    Counts characters exactly as :func:`_leading_inline_text` reports them, so a marker
    *located* by that function is *removed* by this one even when it sits inside a wrapper
    or straddles two nodes -- ``Emphasis(Text("-"))`` followed by ``Text(" Body")`` keeps
    the bullet in the first node and the space after it in the second. A wrapper left with
    nothing inside it is dropped rather than emitted empty.

    Returns the new content and however much of ``count`` went unconsumed.
    """
    out: list[Node] = []
    remaining = count
    for node in content:
        if remaining <= 0:
            out.append(node)
        elif isinstance(node, Text):
            if len(node.content) <= remaining:
                remaining -= len(node.content)  # wholly marker; drop the node
            else:
                out.append(replace(node, content=node.content[remaining:]))
                remaining = 0
        elif isinstance(node, _INLINE_WRAPPERS):
            inner, remaining = _consume_leading_chars(node.content, remaining)
            if inner:
                out.append(replace(node, content=inner))
        else:
            # Opaque to the reader above, so it cannot have been part of the marker.
            out.append(node)
            remaining = 0
    return out, remaining


def _caption_comparison_key(text: str) -> str:
    """Reduce text to the glyphs both extraction routes agree on, for caption dedup.

    A bound caption and its body copy are the same printed glyphs read back through
    different routes -- ``clipped_textbox`` for the caption, span text (or a rescued
    region, which dehyphenates) for the copy. The routes disagree on what they
    insert or keep *between* glyphs: ligature expansion ("ﬁrst" vs "first"),
    spacing split mid-word ("enrich ment"), and wrap hyphens kept by one route and
    consumed by the other ("knock- down" vs "knockdown"). NFKC plus dropping
    whitespace and hyphens leaves what they agree on (#410).
    """
    return "".join(unicodedata.normalize("NFKC", text).replace("-", "").split())


def _running_text_key(text: str) -> str:
    """Key a header/footer candidate by what stays the same from page to page.

    ``Page 1 of 12`` and ``Page 2 of 12`` are the same running footer, but keying on
    raw text makes each of them unique, so neither ever reaches ``min_occurrences``
    and the footer is never detected. Collapsing digit runs is what lets the most
    common footer in existence -- one with a page number in it -- be recognized at all.
    """
    return _RUNNING_DIGITS.sub("#", text).strip()


def _collapse_text_whitespace_in_place(node: Node) -> None:
    """Collapse 2+ horizontal-whitespace runs in every Text descendant.

    Skips ``Code`` and ``CodeBlock`` content (whitespace-significant) and
    table cells (table layout uses its own spacing). Walks all other
    container nodes recursively, mutating Text.content in place.
    """
    if isinstance(node, (Code, CodeBlock)):
        return
    if isinstance(node, Text):
        node.content = collapse_whitespace_runs(node.content)
        return
    if isinstance(node, AstTable):
        # Tables are rendered with their own pipe-aligned spacing — leave
        # cell content alone so we don't collapse intentional padding.
        return
    children = getattr(node, "content", None)
    if isinstance(children, list):
        for child in children:
            _collapse_text_whitespace_in_place(child)
    block_children = getattr(node, "children", None)
    if isinstance(block_children, list):
        for child in block_children:
            _collapse_text_whitespace_in_place(child)


def _heading_text(heading: Heading) -> str:
    """Recursively extract plain text from a Heading's inline content."""
    parts: list[str] = []

    def _walk(nodes: list[Node]) -> None:
        for node in nodes:
            if isinstance(node, Text):
                parts.append(node.content)
            elif isinstance(node, Code):
                parts.append(node.content)
            elif isinstance(node, (Strong, Emphasis, Link)):
                _walk(node.content)

    _walk(heading.content)
    return "".join(parts).strip()


def _normalize_heading_for_dedup(text: str) -> str:
    """Normalize heading text for running-title comparison.

    Lowercases and collapses internal whitespace runs to single spaces so
    cosmetic differences (extra spaces from layout, capitalization changes
    between page templates) don't prevent matching.
    """
    return " ".join(text.lower().split())


def _demote_running_headings(doc: "Document", total_pages: int) -> int:
    """Convert headings that recur on >50% of pages into paragraphs.

    A real document section usually appears once. Headings that recur on
    page after page are almost always running titles, form-label headers,
    or per-page footers misclassified by the layout model. Convert them
    to paragraphs in place so downstream readers don't see fake section
    breaks.

    Returns
    -------
    int
        The number of heading nodes demoted (a structural-confidence signal).

    """
    if total_pages < 3:
        return 0

    # First pass: count distinct pages each normalized heading appears on.
    pages_per_heading: dict[str, set[int]] = {}
    for child in doc.children:
        if not isinstance(child, Heading):
            continue
        norm = _normalize_heading_for_dedup(_heading_text(child))
        if not norm:
            continue
        page = child.source_location.page if child.source_location else None
        pages_per_heading.setdefault(norm, set()).add(page if page is not None else 0)

    threshold = max(2, total_pages // 2 + 1)
    running_headings = {norm for norm, pages in pages_per_heading.items() if len(pages) >= threshold}
    if not running_headings:
        return 0

    # Second pass: rebuild children, demoting matched headings.
    demoted = 0
    new_children: list[Node] = []
    for child in doc.children:
        if isinstance(child, Heading):
            norm = _normalize_heading_for_dedup(_heading_text(child))
            if norm in running_headings:
                new_children.append(
                    AstParagraph(
                        content=child.content,
                        metadata=child.metadata.copy(),
                        source_location=child.source_location,
                    )
                )
                demoted += 1
                continue
        new_children.append(child)
    doc.children = new_children
    return demoted


def _strip_leading_whitespace_in_place(nodes: list[Node]) -> None:
    """Trim leading whitespace from the first Text-bearing leaf in ``nodes``.

    Walks through Strong/Emphasis/Link wrappers (since heading content is
    often a wrapped Text node like ``Strong([Text(' I.')])``). Leaves the
    rest of the content alone — only the very first Text leaf is touched,
    so a heading like ``" **I.** **Background**"`` becomes
    ``"**I.** **Background**"`` without disturbing internal spacing.
    """
    for node in nodes:
        if isinstance(node, Text):
            node.content = node.content.lstrip()
            if node.content:
                return
            # Empty after strip — keep walking to the next leaf.
            continue
        if isinstance(node, (Strong, Emphasis, Link)):
            if node.content:
                _strip_leading_whitespace_in_place(node.content)
                # Only stop walking if the wrapper now carries text.
                first_text = next(
                    (c for c in node.content if isinstance(c, Text) and c.content),
                    None,
                )
                if first_text is not None:
                    return
            continue
        if isinstance(node, Code):
            return  # Code preserves whitespace; don't trim.


def _trailing_whitespace_verdict(nodes: list[Node]) -> bool | None:
    """Report whether the last Text-bearing leaf in ``nodes`` ends with whitespace.

    Returns ``None`` — meaning "no text here, keep looking" — rather than ``False``
    when there is no Text leaf to judge. The distinction matters: a wrapper whose
    text does *not* end in whitespace is a definite answer about the join point, and
    collapsing it into "keep looking" makes the walk fall through to an earlier
    sibling and answer about the wrong position entirely.
    """
    for node in reversed(nodes):
        if isinstance(node, Text):
            return bool(node.content) and node.content[-1] in (" ", "\t")
        if isinstance(node, (Strong, Emphasis, Link)):
            verdict = _trailing_whitespace_verdict(node.content) if node.content else None
            if verdict is not None:
                return verdict
            # This wrapper really had no Text leaves — keep walking outward.
            continue
        if isinstance(node, Code):
            return False
    return None


def _trailing_text_is_whitespace(nodes: list[Node]) -> bool:
    """Return True if the last Text-bearing leaf in ``nodes`` ends with whitespace.

    Walks Strong/Emphasis/Link wrappers to find the actual Text content.
    Used to decide whether an inter-line separator space would create a
    redundant whitespace run.
    """
    return _trailing_whitespace_verdict(nodes) is True


def _block_outside_table_regions(block: dict, regions: list[Any]) -> dict | None:
    """Return ``block`` reduced to the lines no table region covers, or None if none remain.

    A detected table region is emitted in its own right -- as a table, or as a paragraph
    when the grid is rejected -- so the lines it covers must not be emitted a second time as
    body text. The lines it does *not* cover are a different matter: they are ordinary prose
    that happens to share a PyMuPDF block with the region, and no other node carries them.

    This exists because "the region covers most of this block" and "the region is this
    block" are not the same statement. A layout-predicted region over the lower half of a
    full-height reference column clears the 50% bar for the whole column, and discarding the
    block outright deleted the upper half -- nine reference entries on one page of the
    born-digital corpus, with nothing recording the loss.

    Parameters
    ----------
    block : dict
        PyMuPDF text block.
    regions : list
        Table region rectangles.

    Returns
    -------
    dict or None
        A copy of ``block`` holding only the uncovered lines, with its bbox tightened to
        them; ``None`` when every line is covered, which is the ordinary case of a block
        that really is the table.

    """
    import pymupdf

    lines = block.get("lines")
    if not lines:
        return None

    kept = []
    for line in lines:
        bbox = line.get("bbox")
        if bbox is None:
            kept.append(line)
            continue
        rect = pymupdf.Rect(bbox)
        area = abs(rect)
        # Judge a line by the same majority rule used for blocks, so a line straddling the
        # region boundary is assigned rather than duplicated or dropped by both sides.
        if area > 0 and any(abs(rect & region) > 0.5 * area for region in regions):
            continue
        kept.append(line)

    if not kept or len(kept) == len(lines):
        # Nothing survived, or nothing was covered -- in both cases the caller's existing
        # whole-block decision is already correct and a rebuilt copy would only differ by
        # its bbox.
        return None if not kept else dict(block)

    # Rescue prose, not whitespace. The lines bordering a table region are routinely blank
    # or a single space, and emitting those as a paragraph adds an empty block where the
    # whole block used to be dropped -- visible in output as a stray gap.
    if not any(span.get("text", "").strip() for line in kept for span in line.get("spans", [])):
        return None

    tightened = None
    for line in kept:
        if line.get("bbox") is None:
            continue
        rect = pymupdf.Rect(line["bbox"])
        tightened = rect if tightened is None else (tightened | rect)

    remainder = dict(block)
    remainder["lines"] = kept
    if tightened is not None:
        remainder["bbox"] = tuple(tightened)
    return remainder


@dataclass
class _BlockProcessingState:
    """State tracking for block-to-AST processing.

    This class encapsulates the mutable state used during block processing,
    reducing parameter passing and simplifying helper method signatures.

    """

    nodes: list[Node] = field(default_factory=list)
    in_code_block: bool = False
    code_block_lines: list[str] = field(default_factory=list)
    paragraph_content: list[Node] = field(default_factory=list)
    paragraph_bbox: tuple[float, float, float, float] | None = None
    paragraph_is_list: bool = False
    paragraph_list_type: str | None = None
    previous_y: float = 0.0
    pending_rotated_text: list[str] = field(default_factory=list)
    pending_rotated_key: str | None = None
    # A heading whose entire text is a numbering prefix (e.g. "I.", "1.1")
    # is buffered here rather than emitted immediately, so it can be merged
    # with the next heading line on the same block. Flushed as its own
    # heading on block end if no follow-up appears.
    pending_heading_prefix_content: list[Node] | None = None
    pending_heading_prefix_level: int = 0
    pending_heading_prefix_page: int = 0
    # Bottom edge of the line the most recent heading was emitted from, and the index it
    # occupies in `nodes`. Together these say "the previous node is a heading and it came
    # from the line directly above this one", which is how a heading that wrapped onto a
    # second printed line is recognised and joined instead of emitted twice.
    last_heading_slot: int = -1
    last_heading_bottom: float = 0.0
    last_heading_height: float = 0.0
    # Full bbox of that line, kept for the wrap-width test: a line only wraps
    # because it filled its measure, so a "continuation" wider than the line
    # above it is a different heading, not the rest of this one.
    last_heading_bbox: tuple[float, float, float, float] | None = None

    def reset_paragraph(self) -> None:
        """Reset paragraph accumulation state."""
        self.paragraph_content = []
        self.paragraph_bbox = None
        self.paragraph_is_list = False
        self.paragraph_list_type = None

    def reset_code_block(self) -> None:
        """Reset code block state."""
        self.in_code_block = False
        self.code_block_lines = []

    def reset_rotated(self) -> None:
        """Reset accumulated rotated-text run."""
        self.pending_rotated_text = []
        self.pending_rotated_key = None


def _check_pymupdf_version() -> None:
    """Check that PyMuPDF version meets minimum requirements.

    Raises
    ------
    DependencyError
        If PyMuPDF version is too old

    Notes
    -----
    This function assumes pymupdf is already imported. It should be called
    after dependency checking via the @requires_dependencies decorator.

    """
    import pymupdf

    min_version = tuple(map(int, PDF_MIN_PYMUPDF_VERSION.split(".")))
    if pymupdf.pymupdf_version_tuple < min_version:
        # str() per component: the tuple holds ints, and joining it directly
        # raised TypeError from inside the error path, so the one user this
        # branch exists for got a traceback instead of "upgrade pymupdf".
        installed = ".".join(str(part) for part in pymupdf.pymupdf_version_tuple)
        raise DependencyError(
            converter_name="pdf",
            missing_packages=[],
            version_mismatches=[("pymupdf", PDF_MIN_PYMUPDF_VERSION, installed)],
        )


def _silence_pymupdf_layout_advisory() -> None:
    """Stop PyMuPDF writing its layout-package advisory to stdout.

    PyMuPDF emits::

        Consider using the pymupdf_layout package for a greatly improved page layout analysis.

    with a bare ``print()`` -- not a warning, not a log record -- the first time
    ``find_tables()`` runs in a process where ``pymupdf.layout`` is not
    installed. all2md writes converted documents to stdout, so the advisory
    landed *inside the document*: ``all2md report.pdf > report.md`` made it line
    one of the markdown. It is not a rare configuration either, since
    ``pymupdf-layout`` is deliberately excluded from the ``all`` extra over its
    Polyform Noncommercial license, so the plain and ``[all]`` installs both hit
    it.

    Suppressing it costs the user nothing: all2md ships that package as the
    ``pdf_layout`` extra and already reports its absence through its own
    dependency machinery, which writes to stderr.
    """
    import pymupdf

    # Guarded: the entry point is PyMuPDF's own, but it is not load-bearing, and
    # a version without it should convert rather than crash.
    suppress = getattr(pymupdf, "no_recommend_layout", None)
    if suppress is not None:
        suppress()


# Note: Column detection, table detection, image extraction, header identification,
# OCR utilities, and text processing functions have been moved to private submodules:
# - _pdf_columns.py: detect_columns and helpers
# - _pdf_tables.py: detect_tables_by_ruling_lines and helpers
# - _pdf_images.py: extract_page_images, detect_image_caption
# - _pdf_headers.py: IdentifyHeaders class
# - _pdf_ocr.py: OCR decision logic and language detection
# - _pdf_text.py: handle_rotated_text, resolve_links


class PdfToAstConverter(BaseParser):
    """Convert PDF to AST representation.

    This converter parses PDF documents using PyMuPDF and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : PdfOptions or None, default = None
        Conversion options

    """

    def __init__(self, options: PdfOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the PDF parser with options and progress callback."""
        BaseParser._validate_options_type(options, PdfOptions, "pdf")
        options = options or PdfOptions()
        super().__init__(options, progress_callback)
        self.options: PdfOptions = options
        self._hdr_identifier: Optional[IdentifyHeaders] = None
        self._attachment_footnotes: dict[str, str] = {}  # label -> content for footnote definitions
        self._ocr_pages_applied: int = 0  # pages OCR was applied to in the current parse
        self._use_layout: bool = False
        # Most recent heading level emitted (any path). Used by
        # `_handle_header_line_with_layout` to pick a sibling-or-deeper level
        # when the layout model says section-header but the font heuristic
        # has nothing to anchor against.
        self._last_heading_level: int = 0

    @requires_dependencies("pdf", DEPS_PDF)
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse PDF document into AST.

        This method handles loading the PDF file and converting it to AST.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            PDF file to parse

        Returns
        -------
        Document
            AST document node

        """
        import pymupdf

        _check_pymupdf_version()
        _silence_pymupdf_layout_advisory()

        # Determine if layout analysis should be used
        if self.options.layout_analysis_mode == "enabled":
            if not is_layout_available():
                raise DependencyError(
                    converter_name="pdf",
                    missing_packages=[(pkg, ver) for pkg, _, ver in DEPS_PDF_LAYOUT],
                )
            self._use_layout = True
        elif self.options.layout_analysis_mode == "auto":
            self._use_layout = is_layout_available()
            if self._use_layout:
                logger.debug("Layout analysis available, enabling automatic block classification")
        else:
            self._use_layout = False

        # Validate and convert input
        doc_input, input_type = validate_and_convert_input(
            input_data, supported_types=["path-like", "file-like (BytesIO)", "pymupdf.Document objects"]
        )

        # Open document based on input type
        try:
            if input_type == "path":
                doc = pymupdf.open(filename=str(doc_input))
            elif input_type in ("file", "bytes"):
                # PyMuPDF expects bytes, not file-like objects
                stream_bytes = normalize_stream_to_bytes(doc_input)
                doc = pymupdf.open(stream=stream_bytes, filetype="pdf")
            elif input_type == "object":
                if isinstance(doc_input, pymupdf.Document) or (
                    hasattr(doc_input, "page_count") and hasattr(doc_input, "__getitem__")
                ):
                    doc = doc_input
                else:
                    raise ValidationError(
                        f"Expected pymupdf.Document object, got {type(doc_input).__name__}",
                        parameter_name="input_data",
                        parameter_value=doc_input,
                    )
            else:
                raise ValidationError(
                    f"Unsupported input type: {input_type}", parameter_name="input_data", parameter_value=doc_input
                )
        except Exception as e:
            raise MalformedFileError(
                f"Failed to open PDF document: {e!r}",
                file_path=str(input_data) if isinstance(input_data, (str, Path)) else None,
                original_error=e,
            ) from e

        # Handle password-protected PDFs using PyMuPDF's authentication API
        if doc.is_encrypted:
            filename = str(input_data) if isinstance(input_data, (str, Path)) else None
            if self.options.password:
                # Attempt authentication with provided password
                auth_result = doc.authenticate(self.options.password)
                if auth_result == 0:
                    # Authentication failed (return code 0)
                    raise PasswordProtectedError(
                        message=(
                            "Failed to authenticate PDF with provided password. Please check the password is correct."
                        ),
                        filename=filename,
                    )
                # auth_result > 0 indicates successful authentication
                # (1=no passwords, 2=user password, 4=owner password, 6=both equal)
            else:
                # Document is encrypted but no password provided
                raise PasswordProtectedError(
                    message=(
                        "PDF document is password-protected. Please provide a password using the 'password' option."
                    ),
                    filename=filename,
                )

        # Validate page range
        try:
            validated_pages = validate_page_range(self.options.pages, doc.page_count)
            pages_to_use: range | list[int] = validated_pages if validated_pages else range(doc.page_count)
        except Exception as e:
            raise ValidationError(
                f"Invalid page range: {str(e)}", parameter_name="pdf.pages", parameter_value=self.options.pages
            ) from e

        # Extract base filename for standardized attachment naming
        if input_type == "path" and isinstance(doc_input, (str, Path)):
            base_filename = Path(doc_input).stem
        else:
            # For non-file inputs, use a default name
            base_filename = "document"

        self._hdr_identifier = IdentifyHeaders(
            doc, pages=pages_to_use if isinstance(pages_to_use, list) else None, options=self.options
        )
        self._last_heading_level = 0

        # Auto-detect header/footer zones if requested
        if self.options.auto_trim_headers_footers:
            self._auto_detect_header_footer_zones(doc, pages_to_use)

        return self.convert_to_ast(doc, pages_to_use, base_filename)

    def _get_sample_pages(self, pages_to_use: range | list[int]) -> list[int] | None:
        """Get evenly distributed sample pages for header/footer detection.

        Two pages are enough. Repetition is the entire signal, and a block that appears
        at the same position on both pages of a two-page document has already repeated;
        ``min_occurrences`` still requires it on every sampled page. The previous floor
        of three made ``auto_trim_headers_footers`` a silent no-op on two-page documents.
        """
        total_pages = len(list(pages_to_use))
        if total_pages < MIN_PAGES_FOR_RUNNING_DETECTION:
            return None  # A single page cannot show repetition.

        sample_size = min(10, total_pages)
        if isinstance(pages_to_use, range):
            step = max(1, total_pages // sample_size)
            return [pages_to_use.start + i * step for i in range(sample_size)]
        step = max(1, len(pages_to_use) // sample_size)
        return [pages_to_use[i * step] for i in range(sample_size)]

    def _extract_block_text(self, block: dict) -> str | None:
        """Extract text from a block dictionary. Returns None if no valid text."""
        if block.get("type") != 0:
            return None
        if not block.get("bbox"):
            return None

        text_lines = []
        for line in block.get("lines", []):
            line_text = " ".join(span["text"] for span in line.get("spans", []))
            text_lines.append(line_text.strip())

        block_text = " ".join(text_lines).strip()
        return block_text if block_text else None

    def _collect_page_blocks(
        self, doc: "pymupdf.Document", sample_pages: list[int]
    ) -> dict[int, list[tuple[str, float, float]]]:
        """Collect text blocks with positions from sampled pages."""
        import pymupdf

        page_blocks: dict[int, list[tuple[str, float, float]]] = {}

        for page_num in sample_pages:
            page = doc[page_num]
            blocks = page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]
            page_blocks[page_num] = []

            for block in blocks:
                block_text = self._extract_block_text(block)
                if block_text:
                    bbox = block["bbox"]
                    page_blocks[page_num].append((block_text, bbox[1], bbox[3]))

        return page_blocks

    def _classify_header_footer_candidates(
        self, page_blocks: dict[int, list[tuple[str, float, float]]], page_height: float
    ) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
        """Classify blocks into header/footer candidates based on position.

        Candidates are keyed on their text with digit runs collapsed (see
        :func:`_running_text_key`), so ``Page 1 of 12`` and ``Page 2 of 12`` are
        recognized as the same running footer rather than as two unrelated blocks.
        """
        header_candidates: dict[str, list[float]] = {}
        footer_candidates: dict[str, list[float]] = {}

        header_zone_threshold = page_height * HEADER_ZONE_FRACTION
        footer_zone_threshold = page_height * FOOTER_ZONE_FRACTION

        for blocks in page_blocks.values():
            for text, y_top, y_bottom in blocks:
                key = _running_text_key(text)
                if y_bottom < header_zone_threshold:
                    header_candidates.setdefault(key, []).append(y_bottom)
                if y_top > footer_zone_threshold:
                    footer_candidates.setdefault(key, []).append(y_top)

        return header_candidates, footer_candidates

    def _find_repeating_zone_boundaries(
        self,
        header_candidates: dict[str, list[float]],
        footer_candidates: dict[str, list[float]],
        page_height: float,
        min_occurrences: int,
    ) -> tuple[float, float]:
        """Find boundaries of repeating header/footer zones.

        A candidate must repeat *and hold still*. The zone boundary is taken from the
        innermost matching block, so a single false positive does not just drop its own
        line -- it drops everything outside it, on every page. Requiring the block to
        occupy the same vertical position on each page (within
        :data:`RUNNING_POSITION_TOLERANCE`) is what keeps that blast radius aimed at
        real furniture: a running head is anchored to the page, whereas a heading that
        merely recurs sits wherever the text flow leaves it.
        """
        max_header_y = 0.0
        max_footer_y = page_height

        def anchored(y_values: list[float]) -> bool:
            return len(y_values) >= min_occurrences and max(y_values) - min(y_values) <= RUNNING_POSITION_TOLERANCE

        for y_values in header_candidates.values():
            if anchored(y_values):
                max_header_y = max(max_header_y, max(y_values))

        for y_values in footer_candidates.values():
            if anchored(y_values):
                max_footer_y = min(max_footer_y, min(y_values))

        return max_header_y, max_footer_y

    def _auto_detect_header_footer_zones(self, doc: "pymupdf.Document", pages_to_use: range | list[int]) -> None:
        """Automatically detect and set header/footer zones by analyzing repeating text patterns.

        This method analyzes text blocks across multiple pages to identify repeating
        headers and footers. It looks for text that appears in similar vertical positions
        across multiple pages and calculates appropriate header_height and footer_height
        values to exclude them from conversion.

        Parameters
        ----------
        doc : pymupdf.Document
            PDF document to analyze
        pages_to_use : range or list[int]
            Pages to process (used to determine sample range)

        """
        sample_pages = self._get_sample_pages(pages_to_use)
        if not sample_pages:
            return

        page_blocks = self._collect_page_blocks(doc, sample_pages)
        if not page_blocks:
            return

        page_height = doc[sample_pages[0]].rect.height
        header_candidates, footer_candidates = self._classify_header_footer_candidates(page_blocks, page_height)

        min_occurrences = max(2, len(sample_pages) // 2)
        max_header_y, max_footer_y = self._find_repeating_zone_boundaries(
            header_candidates, footer_candidates, page_height, min_occurrences
        )

        # Set header_height and footer_height if we found repeating patterns
        if max_header_y > 0:
            self.options = self.options.create_updated(header_height=int(max_header_y + 5), trim_headers_footers=True)

        if max_footer_y < page_height:
            footer_height_value = int(page_height - max_footer_y + 5)
            self.options = self.options.create_updated(footer_height=footer_height_value, trim_headers_footers=True)

    def extract_metadata(self, document: "pymupdf.Document") -> DocumentMetadata:
        """Extract metadata from PDF document.

        Extracts standard metadata fields from a PDF document including title,
        author, subject, keywords, creation date, modification date, and creator
        application information. Also preserves any custom metadata fields that
        are not part of the standard set.

        Parameters
        ----------
        document : pymupdf.Document
            PyMuPDF document object to extract metadata from

        Returns
        -------
        DocumentMetadata
            Extracted metadata including standard fields (title, author, dates, etc.)
            and any custom fields found in the PDF. Returns empty DocumentMetadata
            if no metadata is available.

        Notes
        -----
        - PDF date strings in format 'D:YYYYMMDDHHmmSS' are parsed into datetime objects
        - Empty or whitespace-only metadata values are ignored
        - Internal PDF fields (format, trapped, encryption) are excluded
        - Unknown metadata fields are stored in the custom dictionary

        """
        # PyMuPDF provides metadata as a dictionary
        pdf_meta = document.metadata if hasattr(document, "metadata") else {}

        if not pdf_meta:
            return DocumentMetadata()

        # Create custom handlers for PDF-specific field processing
        def handle_pdf_dates(meta_dict: dict[str, Any], field_names: list[str]) -> Any:
            """Handle PDF date fields with special parsing."""
            for field_name in field_names:
                if field_name in meta_dict:
                    date_val = meta_dict[field_name]
                    if date_val and str(date_val).strip():
                        return self._parse_pdf_date(str(date_val).strip())
            return None

        # Custom field mapping for PDF dates
        pdf_mapping = PDF_FIELD_MAPPING.copy()
        pdf_mapping.update(
            {
                "creation_date": ["creationDate", "CreationDate"],
                "modification_date": ["modDate", "ModDate"],
            }
        )

        # Custom handlers for special fields
        custom_handlers = {
            "creation_date": handle_pdf_dates,
            "modification_date": handle_pdf_dates,
        }

        # Use the utility function for standard extraction
        metadata = extract_dict_metadata(pdf_meta, pdf_mapping)

        # Apply custom handlers for date fields
        for field_name, handler in custom_handlers.items():
            if field_name in pdf_mapping:
                value = handler(pdf_meta, pdf_mapping[field_name])
                if value:
                    setattr(metadata, field_name, value)

        # Store any additional PDF-specific metadata in custom fields
        processed_keys = set()
        for field_names in pdf_mapping.values():
            if isinstance(field_names, list):
                processed_keys.update(field_names)
            else:
                processed_keys.add(field_names)  # type: ignore[unreachable]

        # Skip internal PDF fields
        internal_fields = {"format", "trapped", "encryption"}

        for key, value in pdf_meta.items():
            if key not in processed_keys and key not in internal_fields:
                if value and str(value).strip():
                    metadata.custom[key] = value

        return metadata

    def _parse_pdf_date(self, date_str: str) -> str:
        """Parse PDF date format into a readable string.

        Converts PDF date strings from the internal format 'D:YYYYMMDDHHmmSS'
        into datetime objects for standardized date handling.

        Parameters
        ----------
        date_str : str
            PDF date string in format 'D:YYYYMMDDHHmmSS' with optional timezone

        Returns
        -------
        str
            Parsed datetime object or original string if parsing fails

        Notes
        -----
        Handles both UTC (Z suffix) and timezone offset formats.
        Returns original string if format is unrecognized.

        """
        if not date_str or not date_str.startswith("D:"):
            return date_str

        try:
            # Remove D: prefix and parse
            clean_date = date_str[2:]
            if "Z" in clean_date:
                clean_date = clean_date.replace("Z", "+0000")
            # Basic parsing - format is YYYYMMDDHHmmSS
            if len(clean_date) >= 8:
                year = int(clean_date[0:4])
                month = int(clean_date[4:6])
                day = int(clean_date[6:8])

                # Validate date ranges before passing to datetime
                if not (1000 <= year <= 9999):
                    logger.debug(f"Invalid year in PDF date: {year}")
                    return date_str
                if not (1 <= month <= 12):
                    logger.debug(f"Invalid month in PDF date: {month}")
                    return date_str
                if not (1 <= day <= 31):
                    logger.debug(f"Invalid day in PDF date: {day}")
                    return date_str

                return datetime(year, month, day).isoformat()
        except (ValueError, IndexError):
            pass
        return date_str

    def convert_to_ast(self, doc: "pymupdf.Document", pages_to_use: range | list[int], base_filename: str) -> Document:
        """Convert PDF document to AST Document.

        Parameters
        ----------
        doc : pymupdf.Document
            PDF document to convert
        pages_to_use : range or list of int
            Pages to process
        base_filename : str
            Base filename for attachments

        Returns
        -------
        Document
            AST document node

        """
        # Reset footnote collection for this conversion
        self._attachment_footnotes = {}
        # Count pages OCR was applied to this conversion (drives the doc-level
        # OCR safety net below).
        self._ocr_pages_applied = 0
        # Reset per-conversion confidence collectors (degraded events accumulate
        # via _record_degraded; _tables_rejected feeds the quality-card signals).
        self._degraded_events: list[Any] = []
        self._quality_signals: dict[str, Any] = {}
        self._tables_rejected = 0

        total_pages = len(list(pages_to_use))

        # Emit started event
        self._emit_progress(
            "started",
            f"Converting PDF with {total_pages} page{'s' if total_pages != 1 else ''}",
            current=0,
            total=total_pages,
        )

        attachment_sequencer = create_attachment_sequencer()

        pages_list = list(pages_to_use)
        children = self._render_pages(doc, pages_list, base_filename, attachment_sequencer, total_pages)

        # Document-level OCR safety net: when nothing triggered OCR in auto mode
        # yet the rendered document is essentially empty, the per-page heuristic
        # likely missed a scanned/image-only PDF — retry once with OCR forced.
        children = self._maybe_retry_with_ocr(doc, pages_list, base_filename, total_pages, children)

        # Extract and attach metadata
        metadata = self.extract_metadata(doc)

        # Attach header detection debug info if enabled
        if self.options.header_debug_output and self._hdr_identifier:
            debug_info = self._hdr_identifier.get_debug_info()
            if debug_info:
                metadata.custom["pdf_header_debug"] = debug_info
                logger.debug("Attached PDF header detection debug info to document metadata")

        # Append footnote definitions if any were collected
        if self.options.attachments_footnotes_section:
            self._append_attachment_footnotes(
                children, self._attachment_footnotes, self.options.attachments_footnotes_section
            )

        # Emit finished event
        self._emit_progress(
            "finished",
            f"PDF conversion completed ({total_pages} page{'s' if total_pages != 1 else ''})",
            current=total_pages,
            total=total_pages,
        )

        # Build the document
        ast_doc = Document(children=children, metadata=metadata.to_dict())

        # Apply inline formatting consolidation if enabled
        if self.options.consolidate_inline_formatting:
            consolidator = InlineFormattingConsolidator()
            consolidated = consolidator.transform(ast_doc)
            if isinstance(consolidated, Document):
                ast_doc = consolidated

        # Collapse whitespace runs that the consolidator may have produced when
        # it merged adjacent Text nodes carrying span-boundary spaces. Runs at
        # span level were already collapsed in `_process_text_spans_to_inline`,
        # but text-merging during consolidation can re-introduce them.
        if self.options.collapse_excess_whitespace:
            _collapse_text_whitespace_in_place(ast_doc)

        # Demote headings that recur on more than half the document pages —
        # those are running titles or per-page form labels masquerading as
        # section headings, not real document structure.
        headings_demoted = 0
        if self.options.dedup_running_headings and total_pages >= 3:
            headings_demoted = _demote_running_headings(ast_doc, total_pages)

        self._record_pdf_quality_signals(ast_doc, total_pages, headings_demoted)

        return ast_doc

    def _record_pdf_quality_signals(self, ast_doc: Document, total_pages: int, headings_demoted: int) -> None:
        """Populate the confidence-report signals from the finished PDF conversion.

        Derives the reference-free quality metrics — meaningful-text density,
        OCR reliance, and detected/rejected table counts — that feed the
        conversion :class:`~all2md.confidence.ConfidenceReport` assembled in
        ``to_ast``. ``chars_per_page`` is the primary text-density signal (a
        near-empty scanned page yields a low value); ``ocr_page_fraction``
        captures how much of the document leaned on OCR.
        """
        meaningful_chars = self._count_meaningful_chars(ast_doc.children)
        pages = max(1, total_pages)
        tables_emitted = sum(1 for _ in extract_nodes(ast_doc, AstTable))
        tables_rejected = getattr(self, "_tables_rejected", 0)

        self._set_quality_signal("page_count", total_pages)
        self._set_quality_signal("meaningful_chars", meaningful_chars)
        self._set_quality_signal("chars_per_page", round(meaningful_chars / pages, 1))
        self._set_quality_signal("ocr_page_fraction", round(self._ocr_pages_applied / pages, 3))
        self._set_quality_signal("tables_detected", tables_emitted + tables_rejected)
        self._set_quality_signal("tables_emitted", tables_emitted)
        self._set_quality_signal("tables_rejected", tables_rejected)
        self._set_quality_signal("running_headings_demoted", headings_demoted)

    def _render_pages(
        self,
        doc: "pymupdf.Document",
        pages_list: list[int],
        base_filename: str,
        attachment_sequencer: Any,
        total_pages: int,
    ) -> list[Node]:
        """Process each page to AST nodes, inserting page separators between pages.

        Extracted from ``parse`` so the document-level OCR safety net can re-run
        the whole page loop with OCR forced.
        """
        children: list[Node] = []
        # Suppress pymupdf-layout's global find_tables() hook for the whole
        # page loop. We call predict_page_layout() explicitly inside
        # _process_page_to_ast and merge its predictions ourselves; the
        # implicit hook would additionally reroute find_tables()/Table.extract()
        # through the layout model, overdetecting tables and garbling cell text.
        # See native_find_tables() for the full rationale.
        with native_find_tables():
            for idx, pno in enumerate(pages_list):
                try:
                    page = doc[pno]
                    page_nodes = self._process_page_to_ast(page, pno, base_filename, attachment_sequencer, total_pages)
                    if page_nodes:
                        children.extend(page_nodes)

                    # Add page separator between pages (but not after the last page)
                    if idx < len(pages_list) - 1 and self.options.include_page_numbers:
                        # Add page separator as Comment node - renderers decide whether to display it
                        # Format using page_separator_template with placeholders
                        separator_text = self.options.page_separator_template.format(
                            page_num=pno + 1, total_pages=total_pages
                        )
                        children.append(Comment(content=separator_text, metadata={"comment_type": "page_separator"}))

                    # Emit page done event
                    self._emit_progress(
                        "item_done",
                        f"Page {pno + 1} of {total_pages} processed",
                        current=idx + 1,
                        total=total_pages,
                        item_type="page",
                        page=pno + 1,
                    )
                except Exception as e:
                    # Emit error event but continue processing
                    self._emit_progress(
                        "error",
                        f"Error processing page {pno + 1}: {str(e)}",
                        current=idx + 1,
                        total=total_pages,
                        error=str(e),
                        stage="page_processing",
                        page=pno + 1,
                    )
                    # Re-raise to maintain existing error handling
                    raise
        return children

    @staticmethod
    def _count_meaningful_chars(children: list[Node]) -> int:
        """Count alphanumeric characters across content nodes (ignoring separators)."""
        content_nodes = [n for n in children if not isinstance(n, Comment)]
        text = extract_node_text(content_nodes, joiner="")
        return sum(1 for char in text if char.isalnum())

    def _record_table_rejection(self, reason: str) -> None:
        """Note a detected "table" discarded as non-tabular (empty frame, TOC, ...).

        Bumps the rejection counter used for the ``tables_rejected`` confidence
        signal and records a degraded-content event carrying the reason, so the
        quality card reflects structure the converter chose to drop.
        """
        self._tables_rejected = getattr(self, "_tables_rejected", 0) + 1
        self._record_degraded("table_rejected", detail=reason, severity="warn")

    def _maybe_retry_with_ocr(
        self,
        doc: "pymupdf.Document",
        pages_list: list[int],
        base_filename: str,
        total_pages: int,
        children: list[Node],
    ) -> list[Node]:
        """Re-run page rendering with OCR forced if an auto-mode doc came out empty.

        Returns the original ``children`` unless a forced-OCR retry produced
        strictly more text. When OCR is unavailable/disabled, emits a one-line
        hint instead of retrying.
        """
        ocr_opts = self.options.ocr
        meaningful = self._count_meaningful_chars(children)
        if meaningful >= ocr_opts.doc_text_threshold:
            return children

        # Already near-empty. Can we recover with OCR?
        can_auto_ocr = ocr_opts.enabled and ocr_opts.mode == "auto" and self._ocr_pages_applied == 0
        if not can_auto_ocr:
            if not ocr_opts.enabled or ocr_opts.mode == "off":
                logger.warning(
                    "PDF produced almost no text (%d meaningful chars) and OCR is disabled. "
                    "Re-run with --pdf-ocr-enabled --pdf-ocr-mode force (and install OCR extras, "
                    "e.g. `pip install all2md[ocr]`) to extract scanned content.",
                    meaningful,
                )
            return children

        logger.info(
            "Document produced almost no text (%d meaningful chars) under auto OCR; retrying with OCR forced.",
            meaningful,
        )
        forced_options = self.options.create_updated(ocr=ocr_opts.create_updated(mode="force"))
        original_options = self.options
        self.options = forced_options
        try:
            retry_children = self._render_pages(
                doc, pages_list, base_filename, create_attachment_sequencer(), total_pages
            )
        except Exception as e:  # noqa: BLE001 - retry is best-effort; keep the original result
            logger.warning("Forced-OCR retry failed: %s. Keeping original extraction.", e)
            return children
        finally:
            self.options = original_options

        if self._count_meaningful_chars(retry_children) > meaningful:
            return retry_children
        return children

    @staticmethod
    def _ocr_page_to_text(page: "pymupdf.Page", options: PdfOptions) -> str:
        """Extract text from a PDF page using OCR (Optical Character Recognition).

        Renders the page to an image at the configured DPI and hands it to the
        OCR backend selected by ``options.ocr.engine`` ("tesseract" or
        "easyocr"). Rendering needs only PyMuPDF; the per-engine Python
        dependencies are checked inside the engine adapters.

        Parameters
        ----------
        page : pymupdf.Page
            PDF page to extract text from
        options : PdfOptions
            PDF conversion options containing OCR settings

        Returns
        -------
        str
            Text extracted via OCR (empty string on failure)

        Raises
        ------
        DependencyError
            If the selected engine's Python packages are not installed
        RuntimeError
            If the Tesseract binary is missing, or EasyOCR cannot initialize

        """
        import pymupdf

        from all2md.parsers._ocr import ocr_pixmap

        # Render page to image (pixmap) at the configured DPI. DPI is applied via
        # the zoom matrix (DPI/72 = zoom factor).
        zoom = options.ocr.dpi / 72.0

        # No explicit pixmap cleanup: the buffer is freed when the last reference to it
        # goes away, and that is this function returning. Rebinding the local to None
        # first — as this did — happens after the return value is computed and drops a
        # reference that is about to be dropped anyway.
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return ocr_pixmap(pix, page, options)

    @staticmethod
    def _ocr_page_to_layout(page: "pymupdf.Page", options: PdfOptions) -> "list[OcrParagraph] | None":
        """OCR a page and keep the engine's paragraph segmentation.

        Parameters
        ----------
        page : pymupdf.Page
            PDF page to extract text from
        options : PdfOptions
            PDF conversion options containing OCR settings

        Returns
        -------
        list of OcrParagraph or None
            Paragraphs in PDF coordinates, or ``None`` if the engine reports no layout.

        """
        import pymupdf

        from all2md.parsers._ocr import ocr_pixmap_layout

        zoom = options.ocr.dpi / 72.0
        try:
            mat = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            return ocr_pixmap_layout(pix, page, options)
        except Exception as exc:  # noqa: BLE001 - layout is an enhancement, never a reason to lose the page
            # Falling back to flat text costs segmentation, which is bad; letting this
            # propagate would cost the page's text entirely, which is worse.
            logger.debug(f"OCR layout recovery unavailable, falling back to flat text: {exc}")
            return None

    @staticmethod
    def _blocks_from_ocr_layout(paragraphs: "list[OcrParagraph]") -> list[dict]:
        """Shape OCR paragraphs like PyMuPDF text blocks so downstream stages see geometry.

        Font size is estimated from line height in points. It is not the true point size,
        but it is monotonic in it, which is what the size-relative heading and body-text
        heuristics actually consume.
        """
        blocks: list[dict] = []
        for paragraph in paragraphs:
            lines = []
            for line in paragraph.lines:
                height = max(line.bbox[3] - line.bbox[1], 1.0)
                lines.append(
                    {
                        "spans": [
                            {
                                "text": line.text,
                                "font": "OCR",
                                "size": round(height, 2),
                                "flags": 0,
                                "color": 0,
                                "bbox": line.bbox,
                            }
                        ],
                        "bbox": line.bbox,
                        "dir": (1, 0),  # Horizontal text direction
                    }
                )
            # Marked so the reading-order sort can leave these alone: the engine emitted
            # them in reading order already. See _build_sorted_column_items.
            blocks.append({"type": 0, "bbox": paragraph.bbox, "lines": lines, "_engine_segmented": True})
        return blocks

    def _detect_page_tables(
        self, page: "pymupdf.Page", page_num: int, total_pages: int
    ) -> tuple[list[dict], list[Any], list[Any]]:
        """Detect tables on a PDF page.

        Parameters
        ----------
        page : pymupdf.Page
            PDF page to analyze
        page_num : int
            Page number (0-based)
        total_pages : int
            Total number of pages

        Returns
        -------
        tuple
            (table_info, fallback_table_rects, fallback_table_lines)

        """
        import pymupdf

        mode = self.options.table_detection_mode.lower()

        class EmptyTables:
            tables: list[Any] = []

            def __getitem__(self, index: int) -> Any:
                return self.tables[index]

        fallback_table_rects: list[Any] = []
        fallback_table_lines: list[Any] = []
        tabs = None

        if mode == "none":
            tabs = EmptyTables()
        elif mode == "pymupdf":
            tabs = page.find_tables()
        elif mode == "ruling":
            fallback_table_rects, fallback_table_lines = detect_tables_by_ruling_lines(
                page, self.options.table_ruling_line_threshold
            )
            tabs = EmptyTables()
        else:
            # Default ("both"): gate ``find_tables()`` behind a cheap drawings
            # scan. On prose-only pages ``find_tables()`` does ~1s of wasted
            # work per page and either returns nothing useful or fires on
            # decorative frames that our guards then have to reject. Skip it
            # when there's no ruling-line evidence; the ruling-line fallback
            # would also find nothing on those pages.
            if page_has_table_signals(page):
                tabs = page.find_tables()
                if self.options.enable_table_fallback_detection and not tabs.tables:
                    fallback_table_rects, fallback_table_lines = detect_tables_by_ruling_lines(
                        page, self.options.table_ruling_line_threshold
                    )
            else:
                tabs = EmptyTables()

        # Build table info list
        table_info = []
        for i, t in enumerate(tabs.tables):
            try:
                bbox = pymupdf.Rect(t.bbox) | pymupdf.Rect(t.header.bbox)
            except ValueError:
                # PyMuPDF may detect a table structure with no cells,
                # causing t.bbox to fail with "min() iterable argument is empty".
                # Skip these empty tables.
                continue
            # A whole column of the table can be printed just outside the detected
            # bbox (#419). Admitting it must happen here, not at emission time: the
            # recorded bbox is what excludes the region's text from the ordinary
            # blocks, so a column admitted later would be emitted twice -- once in
            # the table and once as a paragraph beside it.
            clipped = adjacent_clipped_column(page, t)
            entry = {"bbox": bbox, "idx": i, "type": "pymupdf", "table_obj": t}
            if clipped is not None:
                extension_rect, side = clipped
                entry["bbox"] = bbox | extension_rect
                entry["clip_extension"] = (extension_rect, side)
            table_info.append(entry)
        for i, rect in enumerate(fallback_table_rects):
            table_info.append({"bbox": rect, "idx": i, "type": "fallback", "lines": fallback_table_lines[i]})

        # Emit progress event if tables found
        total_table_count = len(table_info)
        if total_table_count > 0:
            self._emit_progress(
                "detected",
                f"Found {total_table_count} table{'s' if total_table_count != 1 else ''} on page {page_num + 1}",
                current=page_num + 1,
                total=total_pages,
                detected_type="table",
                table_count=total_table_count,
                page=page_num + 1,
            )

        return table_info, fallback_table_rects, fallback_table_lines

    def _apply_ocr_if_needed(
        self, page: "pymupdf.Page", all_blocks: list[dict], extracted_text: str
    ) -> tuple[list[dict], bool]:
        """Apply OCR to page if needed based on options and content.

        Parameters
        ----------
        page : pymupdf.Page
            PDF page
        all_blocks : list of dict
            Extracted text blocks
        extracted_text : str
            Extracted plain text from blocks

        Returns
        -------
        tuple of (list of dict, bool)
            Updated blocks (may include OCR-generated blocks) and whether OCR was applied.

        """
        use_ocr = _should_use_ocr(page, extracted_text, self.options)

        if not use_ocr:
            return all_blocks, False

        try:
            # Prefer the engine's own paragraph segmentation. Flattening a page to one
            # string forces every later stage -- column detection, header/footer trimming,
            # table-region filtering, block segmentation -- to re-derive structure from
            # geometry that no longer exists, so an OCR'd page projected as a single
            # page-sized block no matter what was on it.
            paragraphs = self._ocr_page_to_layout(page, self.options)
            if paragraphs:
                ocr_blocks = self._blocks_from_ocr_layout(paragraphs)
                if self.options.merge_hyphenated_words:
                    # Now that OCR carries real spans, the normal walker applies.
                    dehyphenate_blocks(ocr_blocks)
                self._ocr_pages_applied += 1
                if self.options.ocr.preserve_existing_text and extracted_text.strip():
                    logger.debug(f"Supplementing existing text with {len(ocr_blocks)} OCR block(s)")
                    return [*all_blocks, *ocr_blocks], True
                logger.debug(f"Replacing PyMuPDF text with {len(ocr_blocks)} OCR block(s)")
                return ocr_blocks, True

            ocr_text = self._ocr_page_to_text(page, self.options)

            if not ocr_text.strip():
                logger.warning("OCR returned empty text, keeping original extraction")
                return all_blocks, False

            # This engine returns a flat string rather than the span structure
            # dehyphenate_blocks() walks, so line-break hyphenation ("be-\nwusst")
            # is merged here on the text instead. Same rules, same option.
            if self.options.merge_hyphenated_words:
                ocr_text = dehyphenate_text(ocr_text)

            # Handle preserve_existing_text option
            if self.options.ocr.preserve_existing_text and extracted_text.strip():
                logger.debug(
                    f"Supplementing existing text ({len(extracted_text)} chars) with OCR ({len(ocr_text)} chars)"
                )
                # Add OCR as additional block
                ocr_block = {
                    "type": 0,
                    "bbox": page.rect,
                    "lines": [
                        {
                            "spans": [
                                {
                                    "text": ocr_text,
                                    "font": "OCR",
                                    "size": 11,
                                    "flags": 0,
                                    "color": 0,
                                    "bbox": tuple(page.rect),
                                }
                            ],
                            "bbox": page.rect,
                            "dir": (1, 0),  # Horizontal text direction
                        }
                    ],
                }
                all_blocks.append(ocr_block)
                self._ocr_pages_applied += 1
                return all_blocks, True
            else:
                logger.debug(f"Replacing PyMuPDF text ({len(extracted_text)} chars) with OCR ({len(ocr_text)} chars)")
                # Replace with OCR block
                self._ocr_pages_applied += 1
                return [
                    {
                        "type": 0,
                        "bbox": page.rect,
                        "lines": [
                            {
                                "spans": [
                                    {
                                        "text": ocr_text,
                                        "font": "OCR",
                                        "size": 11,
                                        "flags": 0,
                                        "color": 0,
                                        "bbox": tuple(page.rect),
                                    }
                                ],
                                "bbox": page.rect,
                                "dir": (1, 0),  # Horizontal text direction
                            }
                        ],
                    }
                ], True

        except Exception as e:
            logger.warning(f"OCR processing failed: {e}. Falling back to standard text extraction.")
            return all_blocks, False

    def _assign_to_columns(self, items: list[dict], columns: list[list[dict]]) -> None:
        """Assign each item to a column based on x-coordinate.

        Used for tables and for figures: both are placed by the column their own
        bbox falls in, and both fall back to the first column when their centre
        lands in none of them.

        Parameters
        ----------
        items : list of dict
            Tables or figure plan items, each with a ``bbox`` rect
        columns : list of list of dict
            Column blocks

        """
        for table in items:
            table_center_x = (table["bbox"].x0 + table["bbox"].x1) / 2
            table["column"] = 0  # Default to first column

            for col_idx, column in enumerate(columns):
                if column:
                    col_x_values = [b["bbox"][0] for b in column if "bbox" in b]
                    if col_x_values:
                        col_min_x = min(col_x_values)
                        col_max_x = max(b["bbox"][2] for b in column if "bbox" in b)
                        if col_min_x <= table_center_x <= col_max_x:
                            table["column"] = col_idx
                            break

    def _calculate_average_line_height(self, columns: list[list[dict]]) -> float | None:
        """Calculate average line height across all columns.

        Parameters
        ----------
        columns : list of list of dict
            Text block columns

        Returns
        -------
        float or None
            Average line height, or None if no valid lines found

        """
        line_heights = []
        for column in columns:
            for block in column:
                for line in block.get("lines", []):
                    if "bbox" in line:
                        line_height = line["bbox"][3] - line["bbox"][1]
                        if line_height > 0:
                            line_heights.append(line_height)
        return sum(line_heights) / len(line_heights) if line_heights else None

    def _build_sorted_column_items(self, column: list[dict], col_tables: list[dict]) -> list[tuple[str, float, Any]]:
        """Build a sorted list of blocks and tables for a column.

        Parameters
        ----------
        column : list of dict
            Text blocks in the column
        col_tables : list of dict
            Tables assigned to this column

        Returns
        -------
        list of tuple
            Sorted list of (item_type, y_coord, item_data) tuples

        """
        items: list[tuple[str, float, Any]] = []
        for block in column:
            if "bbox" in block:
                items.append(("block", block["bbox"][1], block))
        for table in col_tables:
            items.append(("table", table["bbox"].y0, table))

        # Sorting by y assumes one column of blocks. When an OCR engine segmented the page
        # it has already emitted its blocks in reading order, including across columns that
        # our own column detection may have missed -- and on a two-column page that it read
        # as one, the y sort interleaves left and right into nonsense. Trust the engine's
        # order instead. Scoped to engine-segmented pages with no tables to interleave;
        # native blocks keep the existing behaviour exactly.
        if not self._keeps_engine_order(items, col_tables):
            items = self._sort_items_into_reading_order(items, column)
        return items

    @staticmethod
    def _keeps_engine_order(items: list[tuple[str, float, Any]], col_tables: list[dict]) -> bool:
        """Whether this column keeps the OCR engine's block order instead of sorting by y.

        Callers that read position out of the item stream need to know: when this is
        true, an item's ``y`` says nothing about where it sits in the stream.
        """
        return bool(items) and not col_tables and all(item[2].get("_engine_segmented") for item in items)

    def _sort_items_into_reading_order(
        self, items: list[tuple[str, float, Any]], column: list[dict]
    ) -> list[tuple[str, float, Any]]:
        """Order items top-to-bottom, and left-to-right among those starting level.

        Sorting on ``y`` alone makes the *first* item decided by whichever block's
        top edge is a hair higher, and on a two-column page that column detection
        read as one, that hair decides the order of the whole page. On page 16 of
        ``PMC7500012.1`` the two columns start at ``y=89.708`` and ``y=89.703`` --
        five thousandths of a point apart -- and the right column wins, so the
        references read 39-61 and then 19-38 (#290).

        The blocks are not exactly level, so a plain ``(y, x)`` key does not help:
        they have to be treated as level first. Items whose tops fall within
        ``row_tolerance`` of the row's first item form one row and are ordered by
        ``x``. The tolerance is a quarter of the page's average line height rather
        than a constant, because what counts as "level" scales with the type size
        -- the same reason an absolute ``column_gap_threshold`` misjudges this
        page. At a quarter of a line it cannot merge consecutive lines of running
        text; it only reaches blocks that begin at effectively the same height,
        where the ``y`` order was noise to begin with.

        Parameters
        ----------
        items : list of tuple
            ``(item_type, y_coord, item_data)`` tuples to order.
        column : list of dict
            The column's text blocks, used to size the tolerance.

        Returns
        -------
        list of tuple
            The same tuples in reading order.

        """
        ordered = sorted(items, key=lambda item: item[1])
        if len(ordered) < 2:
            return ordered

        average_line_height = self._calculate_blocks_average_line_height(column)
        row_tolerance = max(
            PDF_READING_ORDER_MIN_ROW_TOLERANCE,
            (average_line_height or 0.0) * PDF_READING_ORDER_ROW_TOLERANCE_RATIO,
        )

        result: list[tuple[str, float, Any]] = []
        start = 0
        while start < len(ordered):
            end = start + 1
            # Compared against the row's first item, not its predecessor, so a
            # column of near-level blocks cannot chain into one giant row.
            while end < len(ordered) and ordered[end][1] - ordered[start][1] <= row_tolerance:
                end += 1
            row = ordered[start:end]
            row.sort(key=lambda item: self._item_x0(item))
            result.extend(row)
            start = end
        return result

    @staticmethod
    def _item_x0(item: tuple[str, float, Any]) -> float:
        """Return the left edge of a block or table item."""
        kind, _, data = item
        if kind == "table":
            return float(data["bbox"].x0)
        bbox = data.get("bbox")
        return float(bbox[0]) if bbox else 0.0

    def _process_table_item(self, item_data: dict, page: "pymupdf.Page", page_num: int) -> Node | None:
        """Process a single table item and return its AST node.

        Parameters
        ----------
        item_data : dict
            Table information dictionary
        page : pymupdf.Page
            PDF page
        page_num : int
            Page number

        Returns
        -------
        Node or None
            Table AST node, or None if processing failed

        """
        if item_data["type"] == "pymupdf":
            return self._process_table_to_ast(
                item_data["table_obj"], page, page_num, clip_extension=item_data.get("clip_extension")
            )
        elif item_data["type"] == "fallback":
            h_lines, v_lines = item_data["lines"]
            return self._extract_table_from_ruling_rect(page, item_data["bbox"], h_lines, v_lines, page_num)
        elif item_data["type"] == "layout":
            # Layout-detected table: extract text from the predicted region
            return self._extract_table_from_layout_region(page, item_data["bbox"], page_num)
        return None

    def _get_page_links(self, page: "pymupdf.Page") -> list:
        """Extract URI links from a page.

        Parameters
        ----------
        page : pymupdf.Page
            PDF page

        Returns
        -------
        list
            List of URI link dictionaries

        """
        try:
            return [link for link in page.get_links() if link["kind"] == 2]
        except (AttributeError, Exception):
            return []

    def _process_columns_and_tables(
        self,
        columns: list[list[dict]],
        table_info: list[dict],
        page: "pymupdf.Page",
        page_num: int,
        figure_plan: list[dict],
    ) -> list[Node]:
        """Process columns with tables inserted at correct positions.

        Parameters
        ----------
        columns : list of list of dict
            Text block columns
        table_info : list of dict
            Table information
        page : pymupdf.Page
            PDF page
        page_num : int
            Page number
        figure_plan : list of dict
            The page's planned figure emissions from :meth:`_plan_page_figures`

        Returns
        -------
        list of Node
            Processed AST nodes

        """
        nodes: list[Node] = []
        average_line_height = self._calculate_average_line_height(columns)
        links = self._get_page_links(page)

        # A figure is printed at a place on the page, and the text around it reads as
        # though it is there: the paragraph above introduces it, the one below refers
        # back to it. Emitting every figure at the page tail moved all of that text
        # one step out of reading order (#429). Place each figure in the column its
        # own bbox falls in, at the y it is printed at, the way tables already are.
        if figure_plan and columns:
            self._assign_to_columns(figure_plan, columns)
        placed: set[int] = set()

        # Process each column
        for col_idx, column in enumerate(columns):
            col_tables = [t for t in table_info if t["column"] == col_idx]
            items = self._build_sorted_column_items(column, col_tables)
            # Placement reads position out of the item stream's y order. On a page an
            # OCR engine segmented, that stream is in the engine's order instead (#411),
            # where y says nothing about position -- those pages keep the tail emission.
            col_figures = (
                []
                if self._keeps_engine_order(items, col_tables)
                else sorted(
                    (item for item in figure_plan if item.get("column") == col_idx),
                    key=lambda item: (item["bbox"].y0, item["bbox"].x0),
                )
            )
            pending = 0

            for item_type, item_y, item_data in items:
                # Everything printed above this item's top belongs before it.
                while pending < len(col_figures) and col_figures[pending]["bbox"].y0 <= item_y:
                    nodes.extend(self._figure_nodes(col_figures[pending], page_num))
                    placed.add(id(col_figures[pending]))
                    pending += 1
                if item_type == "block":
                    block_nodes = self._process_single_block_to_ast(item_data, links, page_num, average_line_height)
                    nodes.extend(block_nodes)
                elif item_type == "table":
                    table_node = self._process_table_item(item_data, page, page_num)
                    if table_node:
                        nodes.append(table_node)
            for item in col_figures[pending:]:
                nodes.extend(self._figure_nodes(item, page_num))
                placed.add(id(item))

        # A caption's body copy can reach the node list around the block-level
        # suppression entirely: find_tables() can fire on a caption's aligned lines,
        # its bbox removes the block from ordinary text, and when the grid is then
        # rejected _region_text_as_paragraph re-emits the region verbatim -- so the
        # caption prints beside the figure *and* as this rescued paragraph (#410).
        # Catch every such path in one place: a paragraph whose entire text sits
        # inside a caption bound on this page is that caption's body copy, whatever
        # route it took here. Runs before the merges so a body copy cannot first
        # fuse with real prose and escape.
        bound_keys = [_caption_comparison_key(item["caption"]) for item in figure_plan if item["caption"]]
        if bound_keys:
            kept: list[Node] = []
            for candidate in nodes:
                if isinstance(candidate, AstParagraph):
                    text = extract_node_text(candidate)
                    if len(" ".join(text.split())) >= PDF_CAPTION_DEDUP_MIN_CHARS:
                        key = _caption_comparison_key(text)
                        if any(key in bound for bound in bound_keys):
                            continue
                kept.append(candidate)
            nodes = kept

        # Post-processing
        nodes = self._merge_rotated_paragraphs(nodes)
        nodes = self._merge_adjacent_paragraphs(nodes)
        nodes = self._convert_paragraphs_to_lists(nodes)

        # Figures the column pass could not place -- a page with no text columns at
        # all, so there was no stream to interleave them into -- keep the tail
        # emission they have always had.
        for item in figure_plan:
            if id(item) not in placed:
                nodes.extend(self._figure_nodes(item, page_num))

        return nodes

    def _figure_nodes(self, item: dict, page_num: int) -> list[Node]:
        """Render one figure plan item.

        A captioned group becomes a ``Figure`` container (caption on the container, so
        it renders once), an uncaptioned image stays the bare paragraph it always was,
        and a vector-drawn figure -- images empty -- is a caption-only container (#338).
        """
        source = SourceLocation(format="pdf", page=page_num + 1)
        panels: list[Node] = [node for info in item["images"] if (node := self._create_image_node(info, page_num))]
        if item["caption"] is None:
            return panels
        if panels or not item["images"]:
            return [AstFigure(children=panels, caption=item["caption"], source_location=source)]
        return []

    def _plan_page_figures(
        self,
        page: "pymupdf.Page",
        page_images: list[dict],
        layout: PageLayoutPredictions | None,
        table_info: list[dict],
    ) -> list[dict]:
        """Group the page's images into figures and mine picture regions for vector ones.

        Returns plan items ``{"images": [...], "caption": ...}`` in top-of-page order:

        - caption and images: a ``Figure`` whose images are panels. Images sharing a
          layout ``picture`` region or an identical detected caption fold into one
          figure -- a three-panel figure is one figure, not three (#338).
        - images and no caption: bare image paragraphs, exactly as before.
        - caption and no images: a vector-drawn figure. A ``picture`` region holding
          no extracted raster has no pixels to emit, and the caption is the only
          record the figure exists.

        The ``picture`` region also rescues captions the per-image search cannot
        reach: panels bind individually against their own bbox, and the bottom
        panel's neighbour is the top panel, not the caption -- the region's extent
        is what actually ends just above the caption.
        """
        import pymupdf

        caption_regions = layout.get_predictions_by_label("caption") if layout else None
        picture_rects = (
            [pymupdf.Rect(pred.bbox) for pred in layout.get_predictions_by_label("picture")] if layout else []
        )

        def union(members: list[dict]) -> Any:
            """Return the extent of a figure's panels, used to place it back on the page."""
            box = pymupdf.Rect(members[0]["bbox"])
            for member in members[1:]:
                box |= member["bbox"]
            return box

        def region_index(bbox: Any) -> int | None:
            center = pymupdf.Point((bbox.x0 + bbox.x1) / 2, (bbox.y0 + bbox.y1) / 2)
            for idx, rect in enumerate(picture_rects):
                if rect.contains(center):
                    return idx
            return None

        by_region: dict[int, list[dict]] = {}
        loose: list[dict] = []
        for info in page_images:
            idx = region_index(info["bbox"])
            if idx is None:
                loose.append(info)
            else:
                by_region.setdefault(idx, []).append(info)

        plan: list[tuple[float, dict]] = []
        used_captions: set[str] = set()

        for idx, members in sorted(by_region.items()):
            captions = {member["caption"] for member in members if member.get("caption")}
            if len(captions) > 1:
                # Two captioned figures under one region means the region is wrong,
                # not the captions; regroup those members by caption instead.
                loose.extend(members)
                continue
            caption = next(iter(captions), None)
            if caption is None:
                caption = detect_image_caption(page, picture_rects[idx], caption_regions)
            if caption is None:
                loose.extend(members)
                continue
            used_captions.add(caption)
            members = sorted(members, key=lambda member: (member["bbox"].y0, member["bbox"].x0))
            plan.append(
                (
                    min(member["bbox"].y0 for member in members),
                    {"images": members, "caption": caption, "bbox": union(members)},
                )
            )

        by_caption: dict[str, list[dict]] = {}
        for info in loose:
            if info.get("caption"):
                by_caption.setdefault(info["caption"], []).append(info)
            else:
                plan.append((info["bbox"].y0, {"images": [info], "caption": None, "bbox": union([info])}))
        for caption, members in by_caption.items():
            used_captions.add(caption)
            members = sorted(members, key=lambda member: (member["bbox"].y0, member["bbox"].x0))
            plan.append(
                (
                    min(member["bbox"].y0 for member in members),
                    {"images": members, "caption": caption, "bbox": union(members)},
                )
            )

        for idx, rect in enumerate(picture_rects):
            if idx in by_region:
                continue
            # A chart the model saw as a picture *and* the table detector claimed
            # stays a table -- the same 0.3 overlap convention the table supplement
            # uses above.
            if any(abs(rect & table["bbox"]) > 0.3 * max(abs(rect), abs(table["bbox"])) for table in table_info):
                continue
            caption = detect_image_caption(page, rect, caption_regions)
            if not caption or caption in used_captions:
                continue
            used_captions.add(caption)
            plan.append((rect.y0, {"images": [], "caption": caption, "bbox": pymupdf.Rect(rect)}))

        # One printed caption is one figure. The region loop emits one item per
        # ``picture`` region, so a multi-panel figure whose panels the layout model
        # drew as separate regions would become one Figure per panel, each
        # re-binding the same caption and printing it once per panel (#410).
        # Folding by verbatim caption here covers every path that can produce a
        # duplicate -- region items, loose items, and the caption-only rescue --
        # and cannot fuse distinct figures: two different figures on one page do
        # not share a verbatim caption.
        by_caption_final: dict[str, dict] = {}
        ordered: list[dict] = []
        for _y, item in sorted(plan, key=lambda entry: entry[0]):
            caption = item["caption"]
            if caption is None:
                ordered.append(item)
                continue
            existing = by_caption_final.get(caption)
            if existing is None:
                by_caption_final[caption] = item
                ordered.append(item)
            else:
                existing["images"].extend(item["images"])
                existing["bbox"] |= item["bbox"]
        for item in by_caption_final.values():
            item["images"].sort(key=lambda member: (member["bbox"].y0, member["bbox"].x0))
        return ordered

    def _process_page_to_ast(
        self,
        page: "pymupdf.Page",
        page_num: int,
        base_filename: str,
        attachment_sequencer: Callable[[str, str], tuple[str, int]],
        total_pages: int = 0,
    ) -> list[Node]:
        """Process a PDF page to AST nodes.

        Parameters
        ----------
        page : pymupdf.Page
            PDF page to process
        page_num : int
            Page number (0-based)
        base_filename : str
            Base filename for attachments
        attachment_sequencer : Callable
            Sequencer for generating unique attachment names
        total_pages : int, default=0
            Total number of pages being processed

        Returns
        -------
        list of Node
            List of AST nodes representing the page

        """
        import pymupdf

        # Detect tables on the page
        table_info, _, _ = self._detect_page_tables(page, page_num, total_pages)

        # Extract all text blocks from the page.
        #
        # A page whose text cannot be read at all is tolerated rather than fatal: one
        # broken page should not cost the other 400, and the test suite drives this
        # method with mock pages that cannot answer get_text() at all. But it is no
        # longer silent. A page that vanished without a trace was indistinguishable in
        # the output from a page that was genuinely blank, the conversion still reported
        # success, and if every page tripped it the document-level OCR safety net saw an
        # empty document and could re-run a perfectly good text PDF through OCR.
        try:
            all_blocks = page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT, sort=False)["blocks"]
        except Exception as e:
            logger.warning(
                "Text extraction failed on page %d (%s); the page is dropped from the output.", page_num + 1, e
            )
            self._record_degraded(
                "page_text_extraction_failed",
                detail=f"page {page_num + 1}: {type(e).__name__}: {e}",
                severity="error",
            )
            return []

        # Deliberately outside the try. dehyphenate_blocks() is defensive internally and
        # operates on blocks we have already read successfully, so an exception from it
        # is a bug in our own code, not an unreadable page -- and the catch above would
        # have turned it into the same silent empty page. (It was moved inside the try in
        # 0e2d5927, which predates this method's error handling meaning anything.)
        if self.options.merge_hyphenated_words:
            dehyphenate_blocks(all_blocks)

        # Run layout analysis if enabled (before any filtering so indices match).
        # Done before image extraction so that page-header / page-footer regions
        # can be used to filter out repeating decorative images.
        layout: PageLayoutPredictions | None = None
        if self._use_layout:
            try:
                raw_predictions = predict_page_layout(page, self.options.layout_feature_set)
                layout = match_predictions_to_blocks(raw_predictions, all_blocks, self.options.layout_iou_threshold)
                annotate_blocks_with_layout(all_blocks, layout)
                # Also label individual lines. A block-level label is only available when
                # the block happens to be one semantic unit; on a journal page it is a whole
                # column, and every heading inside it loses its label to the IoU test.
                annotate_lines_with_layout(all_blocks, raw_predictions)
            except Exception as e:
                logger.warning("Layout analysis failed for page %d: %s", page_num + 1, e)
                layout = None

        # Extract images if needed. Pass page-header/footer regions so we don't
        # emit placeholders for the recurring decorations / signature artifacts
        # those zones tend to contain.
        page_images: list[Any] = []
        if self.options.attachment_mode != "skip":
            excluded_regions = self._collect_image_exclusion_regions(layout)
            page_images, page_footnotes = extract_page_images(
                page,
                page_num,
                self.options,
                base_filename,
                attachment_sequencer,
                excluded_regions=excluded_regions,
                # The model's own caption regions beat guessing from a fixed band: 87%
                # of what they return is a real caption against 59% for the band.
                caption_regions=layout.get_predictions_by_label("caption") if layout else None,
            )
            self._attachment_footnotes.update(page_footnotes)

        # Extract plain text for OCR detection
        extracted_text = "".join(
            span.get("text", "")
            for block in all_blocks
            if block.get("type") == 0
            for line in block.get("lines", [])
            for span in line.get("spans", [])
        )

        # Apply OCR if needed
        all_blocks, ocr_applied = self._apply_ocr_if_needed(page, all_blocks, extracted_text)

        # Filter headers/footers when enabled - layout labels provide more accurate detection
        if self.options.trim_headers_footers or self.options.auto_trim_headers_footers:
            if layout and (layout.has_label("page-header") or layout.has_label("page-footer")):
                all_blocks = [b for b in all_blocks if b.get("_layout_label") not in ("page-header", "page-footer")]
            else:
                all_blocks = self._filter_headers_footers(all_blocks, page)

        # Supplement table detection with layout-predicted tables
        if layout:
            for pred in layout.get_predictions_by_label("table"):
                pred_rect = pymupdf.Rect(pred.x0, pred.y0, pred.x1, pred.y1)
                # Check both directions: layout region covered by existing table,
                # OR existing table covered by layout region
                already_covered = any(
                    abs(pred_rect & t["bbox"]) > 0.3 * max(abs(pred_rect), abs(t["bbox"])) for t in table_info
                )
                if not already_covered:
                    table_info.append(
                        {
                            "bbox": pred_rect,
                            "idx": len(table_info),
                            "type": "layout",
                            "lines": ([], []),
                        }
                    )
                    logger.debug("Layout analysis detected additional table at %s on page %d", pred_rect, page_num + 1)

        # Group the page's images into figures and mine rasterless picture regions
        # for vector-drawn ones (#338). Skipped when OCR replaced the page: the
        # figures would not be emitted, and dropping their caption blocks from
        # OCR-recovered text would lose the only copy of the caption.
        figure_plan: list[dict] = []
        if not ocr_applied and self.options.image_placement_markers:
            figure_plan = self._plan_page_figures(page, page_images, layout, table_info)

        # A caption bound to a figure renders beside that figure, so the body copy of
        # the same text must not also survive as a paragraph -- every caption would
        # appear twice. Matching is textual rather than geometric: the whole block,
        # whitespace-normalized, must sit inside a caption actually bound on this
        # page, so nothing that is not literally the caption can be dropped.
        bound_captions = [" ".join(item["caption"].split()) for item in figure_plan if item["caption"]]

        # The caption's printed region suppresses geometrically what the textual rule
        # cannot: ``clipped_textbox`` and the block spans read the same glyphs through
        # different heuristics (wrap hyphens kept vs dehyphenated, spacing split mid-word,
        # occasionally a dropped character), so the two strings can disagree while the
        # geometry stays exact (#410). A region qualifies only when its entire text sits
        # inside a caption actually bound on this page -- then every glyph a block inside
        # it holds is already emitted on the figure, and dropping the block loses nothing.
        bound_caption_rects: list[Any] = []
        if bound_captions and layout:
            region_bound_keys = [_caption_comparison_key(c) for c in bound_captions]
            for pred in layout.get_predictions_by_label("caption"):
                rect = pymupdf.Rect(pred.bbox)
                region_key = _caption_comparison_key(clipped_textbox(page, rect))
                if region_key and any(region_key in bound for bound in region_bound_keys):
                    bound_caption_rects.append(rect + PDF_CAPTION_REGION_SUPPRESS_MARGIN)

        # Filter out blocks inside table regions
        text_blocks = []
        for block in all_blocks:
            if bound_captions and self._is_bound_caption_block(block, bound_captions):
                continue
            if (
                bound_caption_rects
                and block.get("type") == 0
                and "bbox" in block
                and any(rect.contains(pymupdf.Rect(block["bbox"])) for rect in bound_caption_rects)
            ):
                continue
            if "bbox" not in block:
                text_blocks.append(block)
                continue

            block_rect = pymupdf.Rect(block["bbox"])
            is_in_table = any(abs(block_rect & table["bbox"]) > 0.5 * abs(block_rect) for table in table_info)
            if not is_in_table:
                text_blocks.append(block)
                continue

            # Mostly-a-table is not entirely-a-table. Keep whatever lies outside every
            # region, so a region covering part of a tall block does not take the rest of
            # that block with it -- only the region's own text is re-emitted downstream.
            remainder = _block_outside_table_regions(block, [table["bbox"] for table in table_info])
            if remainder is not None:
                text_blocks.append(remainder)

        # Apply column detection if enabled -- but not to OCR-derived blocks (#411).
        # The engine already ran its own layout analysis and numbers its blocks in
        # reading order; re-sorting them with born-digital column geometry loses to
        # that order across the OmniDocBench raster corpus. Bisecting the v1.12/v1.13
        # raster regression put 91% of the text_content bill (-21.05 of -23.01 summed
        # per-page delta) on 72 pages whose old single-block output scored 0.73/0.83
        # (text/order); on every locally reproducible one of them, skipping this pass
        # restored the pre-regression score exactly -- including a newspaper page,
        # the very layout the pass exists for -- while keeping the block_structure
        # gain the segmentation bought. An explicit ``force_multi`` request still
        # runs the pass: that mode is a user override, not a heuristic.
        run_column_pass = (
            self.options.detect_columns
            and self.options.column_detection_mode not in ("disabled", "force_single")
            and (self.options.column_detection_mode == "force_multi" or not ocr_applied)
        )
        if run_column_pass:
            force_multi = self.options.column_detection_mode == "force_multi"
            # PyMuPDF fuses both columns of a tight-gutter page into one block on some
            # pages; the fused block's interleaving is invisible to any block-level
            # split, so its lines are regrouped into per-band blocks first (#405).
            text_blocks = split_gutter_merged_blocks(text_blocks, page.rect.width)
            columns = detect_columns(
                text_blocks,
                self.options.column_gap_threshold,
                use_clustering=self.options.use_column_clustering,
                force_multi_column=force_multi,
            )
        else:
            columns = [text_blocks]

        # Assign tables to columns
        self._assign_to_columns(table_info, columns)

        # Process columns and tables (the figure plan is already empty when OCR
        # replaced page content or placement markers are off)
        nodes = self._process_columns_and_tables(columns, table_info, page, page_num, figure_plan=figure_plan)

        return nodes

    def _calculate_blocks_average_line_height(self, blocks: list[dict]) -> float | None:
        """Calculate average line height across multiple blocks."""
        line_heights = []
        for block in blocks:
            for line in block.get("lines", []):
                if "bbox" in line:
                    line_height = line["bbox"][3] - line["bbox"][1]
                    if line_height > 0:
                        line_heights.append(line_height)

        if line_heights:
            avg = sum(line_heights) / len(line_heights)
            logger.debug(f"Calculated average line height for page: {avg:.2f} points")
            return avg
        return None

    def _process_text_spans_to_inline(
        self, spans: list[dict], links: list[dict], page_num: int, average_line_height: float | None = None
    ) -> list[Node]:
        """Process text spans to inline AST nodes.

        Parameters
        ----------
        spans : list of dict
            Text spans from PyMuPDF
        links : list of dict
            Links on the page
        page_num : int
            Page number for source tracking
        average_line_height : float or None, optional
            Average line height for the page, used for link threshold auto-calibration

        Returns
        -------
        list of Node
            List of inline AST nodes

        """
        result: list[Node] = []
        # Tracks whether the most recently emitted Text-bearing span ended
        # with whitespace, so we can avoid creating multi-space runs at span
        # boundaries when collapse_excess_whitespace is enabled.
        prev_text_ends_ws = False

        for span in spans:
            span_text = span["text"]
            # Skip completely empty spans, but preserve single spaces
            if not span_text:
                continue

            # Check for list bullets before treating as monospace
            is_list_bullet = span_text in ["-", "o", "•", "◦", "▪"] and len(span_text) == 1

            # Decode font properties
            mono = span["flags"] & 8
            bold = span["flags"] & 16
            italic = span["flags"] & 2

            # Check for links with auto-calibrated threshold
            link_url = self._resolve_link_for_span(links, span, average_line_height)

            # Build the inline node
            if mono and not is_list_bullet:
                # Inline code — preserve whitespace as-is, don't update the
                # running whitespace state.
                inline_node: Node = Code(content=span_text)
            else:
                # Regular text with optional formatting.
                # Bullet glyphs become "-"; "<" and ">" are left as the page
                # prints them. Writing "&lt;" here put the entity into the AST
                # itself, so every consumer that reads nodes rather than a
                # rendered page -- the reverse converters, the benchmark's
                # normalization path -- saw "p &lt; 0.05" (#441). Escaping for
                # markdown's sake belongs to the markdown renderer, which knows
                # when a "<" would actually be read as a tag.
                span_text = (
                    span_text.replace(chr(0xF0B7), "-")
                    .replace(chr(0xB7), "-")
                    .replace(chr(8226), "-")
                    .replace(chr(9679), "-")
                )

                # Collapse layout-padded whitespace runs in non-mono spans.
                # PDF spans frequently encode visual spacing as long runs of
                # ascii spaces (e.g. "Policy Title:                  ") that
                # do not carry meaning in markdown.
                if self.options.collapse_excess_whitespace:
                    span_text = collapse_whitespace_runs(span_text)
                    if prev_text_ends_ws and span_text.startswith((" ", "\t")):
                        span_text = span_text.lstrip(" \t")
                    if not span_text:
                        # Span was nothing but redundant whitespace — drop it.
                        continue
                    prev_text_ends_ws = span_text[-1] in (" ", "\t")

                inline_node = Text(content=span_text)

                # Apply formatting layers — but skip bold/italic wrapping
                # for whitespace-only spans, since "**  **" or "* *" carries
                # no meaning and tends to confuse the inline-formatting
                # consolidator into emitting redundant marker pairs.
                if span_text.strip():
                    if bold:
                        inline_node = Strong(content=[inline_node])
                    if italic:
                        inline_node = Emphasis(content=[inline_node])

            # Wrap in link if URL present
            if link_url:
                inline_node = Link(url=link_url, content=[inline_node])

            result.append(inline_node)

        return result

    def _calculate_paragraph_break_threshold(self, block: dict) -> float:
        """Calculate adaptive paragraph break threshold based on line heights.

        Parameters
        ----------
        block : dict
            Text block from PyMuPDF

        Returns
        -------
        float
            Paragraph break threshold in points

        """
        line_heights_in_block = []
        for line in block["lines"]:
            if "bbox" in line and "dir" in line and line["dir"][1] == 0:  # Only horizontal lines
                line_height = line["bbox"][3] - line["bbox"][1]
                if line_height > 0:
                    line_heights_in_block.append(line_height)

        # Use median line height for robustness (less affected by outliers)
        if line_heights_in_block:
            sorted_heights = sorted(line_heights_in_block)
            median_height = sorted_heights[len(sorted_heights) // 2]
            # Paragraph break threshold: 50% of typical line height
            return median_height * 0.5
        else:
            # Fallback to fixed threshold if we can't calculate
            return 5.0

    def _build_paragraph_metadata(
        self,
        paragraph_bbox: tuple[float, float, float, float] | None,
        paragraph_is_list: bool,
        paragraph_list_type: str | None,
    ) -> dict:
        """Build metadata dict including bbox and list marker info.

        Parameters
        ----------
        paragraph_bbox : tuple or None
            Bounding box of paragraph
        paragraph_is_list : bool
            Whether paragraph is a list item
        paragraph_list_type : str or None
            Type of list marker

        Returns
        -------
        dict
            Metadata dictionary

        """
        metadata: dict[str, Any] = {"bbox": paragraph_bbox} if paragraph_bbox else {}
        if paragraph_is_list:
            metadata["is_list_item"] = True
            metadata["list_type"] = paragraph_list_type
            if paragraph_bbox:
                metadata["marker_x"] = paragraph_bbox[0]
        return metadata

    def _flush_paragraph(
        self,
        paragraph_content: list[Node],
        paragraph_bbox: tuple[float, float, float, float] | None,
        paragraph_is_list: bool,
        paragraph_list_type: str | None,
        page_num: int,
        nodes: list[Node],
    ) -> None:
        """Flush accumulated paragraph content to nodes list.

        Parameters
        ----------
        paragraph_content : list of Node
            Accumulated inline nodes for paragraph
        paragraph_bbox : tuple or None
            Bounding box of paragraph
        paragraph_is_list : bool
            Whether paragraph is a list item
        paragraph_list_type : str or None
            Type of list marker
        page_num : int
            Page number for source tracking
        nodes : list of Node
            Output nodes list to append to

        """
        if paragraph_content:
            metadata = self._build_paragraph_metadata(paragraph_bbox, paragraph_is_list, paragraph_list_type)
            source_loc = SourceLocation(format="pdf", page=page_num + 1, metadata=metadata)
            nodes.append(AstParagraph(content=paragraph_content, source_location=source_loc))

    def _flush_state_paragraph(self, state: _BlockProcessingState, page_num: int) -> None:
        """Flush paragraph from state to nodes and reset paragraph state.

        If the state has accumulated paragraph content, also drain any
        buffered numbering-prefix heading first so the prefix is emitted
        as its own heading rather than disappearing behind the paragraph.
        Empty-paragraph flushes leave the buffer alone — heading lines may
        still arrive on the same block and want to absorb the prefix.
        """
        if state.paragraph_content:
            self._flush_pending_heading_prefix(state)
        self._flush_paragraph(
            state.paragraph_content,
            state.paragraph_bbox,
            state.paragraph_is_list,
            state.paragraph_list_type,
            page_num,
            state.nodes,
        )
        state.reset_paragraph()

    def _emit_heading(
        self,
        state: _BlockProcessingState,
        level: int,
        line_text: str,
        inline_content: list[Node],
        page_num: int,
        line_bbox: tuple[float, float, float, float] | None = None,
    ) -> None:
        """Emit a heading or buffer a numbering-only prefix for merging.

        Lines whose entire text is a numbering prefix (``"I."``, ``"1.1"``,
        ``"(a)"``) are deferred — the next heading line on the same block
        will absorb them and emit a single ``"I. Background"``-style
        heading. PDFs often visually break Roman-numeral section markers
        onto their own line above the actual heading text, and emitting
        them as separate headings produced obviously-wrong output before.

        A heading too long for one printed line is set on two, and each line
        reaches here separately. When ``line_bbox`` shows this line sits
        directly under the heading just emitted, at the same level, the text
        is appended to that heading rather than starting a new one.
        """
        if line_bbox is not None and self._continues_wrapped_heading(state, level, line_text, line_bbox):
            heading = state.nodes[-1]
            assert isinstance(heading, Heading)  # guaranteed by _continues_wrapped_heading
            heading.content.extend([Text(content=" "), *inline_content])
            state.last_heading_bottom = line_bbox[3]
            state.last_heading_height = max(line_bbox[3] - line_bbox[1], state.last_heading_height)
            state.last_heading_bbox = line_bbox
            return

        if parse_numbering_prefix(line_text) is not None:
            # If we *already* have a buffered prefix and this is also one,
            # flush the older one first so neither gets lost (rare in real
            # documents but cheap to handle).
            if state.pending_heading_prefix_content is not None:
                self._flush_pending_heading_prefix(state)
            state.pending_heading_prefix_content = inline_content
            state.pending_heading_prefix_level = level
            state.pending_heading_prefix_page = page_num
            return

        if state.pending_heading_prefix_content is not None:
            # Merge: prepend pending prefix content with a single space,
            # using the prefix's level (which represented the section depth).
            merged = state.pending_heading_prefix_content + [Text(content=" ")] + inline_content
            merged_level = state.pending_heading_prefix_level
            page = state.pending_heading_prefix_page
            state.pending_heading_prefix_content = None
            state.pending_heading_prefix_level = 0
            _strip_leading_whitespace_in_place(merged)
            state.nodes.append(
                Heading(
                    level=merged_level,
                    content=merged,
                    source_location=SourceLocation(format="pdf", page=page + 1),
                )
            )
            self._last_heading_level = merged_level
            self._mark_heading_line(state, line_bbox)
            return

        _strip_leading_whitespace_in_place(inline_content)
        state.nodes.append(
            Heading(
                level=level,
                content=inline_content,
                source_location=SourceLocation(format="pdf", page=page_num + 1),
            )
        )
        self._last_heading_level = level
        self._mark_heading_line(state, line_bbox)

    @staticmethod
    def _mark_heading_line(state: _BlockProcessingState, line_bbox: tuple[float, float, float, float] | None) -> None:
        """Record where the heading just appended to ``state.nodes`` was printed."""
        if line_bbox is None:
            state.last_heading_slot = -1
            state.last_heading_bbox = None
            return
        state.last_heading_slot = len(state.nodes) - 1
        state.last_heading_bottom = line_bbox[3]
        state.last_heading_height = line_bbox[3] - line_bbox[1]
        state.last_heading_bbox = line_bbox

    @staticmethod
    def _continues_wrapped_heading(
        state: _BlockProcessingState,
        level: int,
        line_text: str,
        line_bbox: tuple[float, float, float, float],
    ) -> bool:
        """Report whether this line is the rest of the heading emitted immediately above it.

        Five things have to hold, and each rules out a way two heading lines can be
        adjacent without being one heading: the previous node is a heading and nothing
        came between them; it is at this line's level, since a subheading under a
        heading is two headings; the line sits within a line's height of it, which is
        what a wrap looks like and what the space above a new section does not; it
        does not open with its own numbering, which announces a new section however
        tightly it is set; and the line above it filled the measure the two lines
        share, because a line only wraps when it ran out of room -- a section title
        with its subsection printed directly beneath fused into one heading before
        this test, losing both titles (#400).
        """
        if not state.nodes or state.last_heading_slot != len(state.nodes) - 1:
            return False
        previous = state.nodes[-1]
        if not isinstance(previous, Heading) or previous.level != level:
            return False
        if parse_numbering_prefix(line_text.split(" ", 1)[0]) is not None:
            return False

        prev_bbox = state.last_heading_bbox
        if prev_bbox is not None:
            left = min(prev_bbox[0], line_bbox[0])
            right = max(prev_bbox[2], line_bbox[2])
            width = right - left
            if width > 0 and (prev_bbox[2] - left) / width < HEADING_WRAP_MIN_FILL:
                return False

        height = max(line_bbox[3] - line_bbox[1], state.last_heading_height)
        if height <= 0:
            return False
        gap = line_bbox[3] - state.last_heading_bottom
        # Strictly below: a line at or above the previous one is a different column or a
        # reading-order artefact, not a continuation.
        return 0 < gap <= height * HEADING_WRAP_GAP_RATIO

    def _flush_pending_heading_prefix(self, state: _BlockProcessingState) -> None:
        """Emit any buffered numbering-prefix heading as a standalone heading."""
        if state.pending_heading_prefix_content is None:
            return
        _strip_leading_whitespace_in_place(state.pending_heading_prefix_content)
        state.nodes.append(
            Heading(
                level=state.pending_heading_prefix_level,
                content=state.pending_heading_prefix_content,
                source_location=SourceLocation(format="pdf", page=state.pending_heading_prefix_page + 1),
            )
        )
        self._last_heading_level = state.pending_heading_prefix_level
        state.pending_heading_prefix_content = None
        state.pending_heading_prefix_level = 0

    def _finalize_code_block(self, state: _BlockProcessingState, page_num: int) -> None:
        """Finalize code block from state and reset code block state."""
        if state.code_block_lines:
            code_content = "\n".join(state.code_block_lines)
            state.nodes.append(
                CodeBlock(content=code_content, source_location=SourceLocation(format="pdf", page=page_num + 1))
            )
        state.reset_code_block()

    def _flush_rotated_text(self, state: _BlockProcessingState, page_num: int) -> None:
        """Emit accumulated rotated-text run as a single paragraph and reset.

        Same-direction rotated lines within one block are joined with spaces.
        The paragraph is tagged with the rotation key in source-location metadata
        so :meth:`_merge_rotated_paragraphs` can join runs that span multiple
        blocks (common when PyMuPDF puts each rotated label in its own block).
        """
        if not state.pending_rotated_text:
            return
        combined = " ".join(state.pending_rotated_text)
        source_loc = SourceLocation(
            format="pdf",
            page=page_num + 1,
            metadata={"rotated": state.pending_rotated_key or ""},
        )
        state.nodes.append(AstParagraph(content=[Text(content=combined)], source_location=source_loc))
        state.reset_rotated()

    def _accumulate_rotated_line(self, line: dict, state: _BlockProcessingState, page_num: int) -> None:
        """Append a rotated line to the in-progress run, flushing on direction change."""
        text = extract_rotated_text(line, None)
        if not text.strip():
            return
        key = classify_line_rotation(line)
        if state.pending_rotated_key is not None and state.pending_rotated_key != key:
            self._flush_rotated_text(state, page_num)
        if state.pending_rotated_key is None:
            self._flush_state_paragraph(state, page_num)
            state.pending_rotated_key = key
        state.pending_rotated_text.append(text)

    def _handle_rotated_line(self, line: dict, state: _BlockProcessingState, page_num: int) -> bool:
        """Handle rotated text line. Returns True if line was processed (should skip further processing)."""
        if line["dir"][1] == 0:  # Horizontal line
            self._flush_rotated_text(state, page_num)
            return False

        if self.options.handle_rotated_text:
            self._accumulate_rotated_line(line, state, page_num)
        return True  # Skip non-horizontal lines

    def _handle_monospace_line(
        self, line: dict, spans: list, text: str, block: dict, state: _BlockProcessingState, page_num: int
    ) -> bool:
        """Handle monospace line (code block). Returns True if line was processed as code."""
        all_mono = all(s["flags"] & 8 for s in spans)
        if not all_mono:
            return False

        # Flush accumulated paragraph before starting code block
        self._flush_state_paragraph(state, page_num)
        state.in_code_block = True

        # Compute approximate indentation
        span_size = spans[0]["size"]
        delta = int((spans[0]["bbox"][0] - block["bbox"][0]) / (span_size * 0.5)) if span_size > 0 else 0
        state.code_block_lines.append(" " * delta + text)
        return True

    def _handle_header_line(
        self,
        spans: list,
        links: list[dict],
        state: _BlockProcessingState,
        page_num: int,
        average_line_height: float | None,
    ) -> bool:
        """Handle header line. Returns True if line was processed as header."""
        header_level = 0
        if self._hdr_identifier:
            line_style = compute_line_style(spans)
            if line_style is not None:
                header_level = self._hdr_identifier.classify_line_style(
                    size=line_style.size,
                    text=line_style.text,
                    is_bold=line_style.is_bold,
                    is_allcaps=line_style.is_allcaps,
                )

        if header_level <= 0:
            return False

        inline_content = self._process_text_spans_to_inline(spans, links, page_num, average_line_height)
        if not inline_content or not inline_has_text(inline_content):
            # Whitespace-only line at header-sized font: drop it, don't promote
            # to a heading and don't fall through to paragraph treatment.
            return True

        self._flush_state_paragraph(state, page_num)
        line_text = "".join(s.get("text", "") for s in spans).strip()
        self._emit_heading(state, header_level, line_text, inline_content, page_num, _span_union_bbox(spans))
        return True

    def _handle_header_line_with_layout(
        self,
        spans: list,
        links: list[dict],
        state: _BlockProcessingState,
        page_num: int,
        average_line_height: float | None,
        layout_label: str,
    ) -> bool:
        """Handle header line using layout analysis classification.

        The layout model classifies the block as ``title`` or ``section-header``.
        For ``title``, always use heading level 1. For ``section-header``,
        prefer the font-size heuristic if available. When the heuristic
        disagrees with the layout model, only promote to heading if the text
        looks plausibly like a header (short text without trailing punctuation).

        Parameters
        ----------
        spans : list
            Text spans from the line.
        links : list[dict]
            Links on the page.
        state : _BlockProcessingState
            Current processing state.
        page_num : int
            Page number for source tracking.
        average_line_height : float or None
            Average line height for the page.
        layout_label : str
            Layout label (``"title"`` or ``"section-header"``).

        Returns
        -------
        bool
            True if the line was emitted as a heading.

        """
        # The layout model labels whole blocks as section-header / title, which
        # means every line in the block (including blank/whitespace lines) hits
        # this path. Reject whitespace-only lines up front so we don't emit
        # empty `## ` headings; return True so the caller doesn't fall through
        # to paragraph treatment.
        line_style = compute_line_style(spans)
        if line_style is None:
            return True

        # Ask the font heuristic at line level — used to corroborate or
        # override the layout label.
        font_level = 0
        if self._hdr_identifier:
            font_level = self._hdr_identifier.classify_line_style(
                size=line_style.size,
                text=line_style.text,
                is_bold=line_style.is_bold,
                is_allcaps=line_style.is_allcaps,
            )

        if layout_label == "title":
            # Layout's "title" is often noisy: it fires for the first
            # heading-styled line on each page even when the document has
            # only one heading style and the line is really a section
            # heading. Defer to the font heuristic when it has an opinion.
            level = font_level if font_level > 0 else 1
        else:
            # section-header: trust the font heuristic when it speaks; cap
            # at h2 so a doc with a single heading size doesn't promote
            # every section-header to h1 against the structural signal.
            if font_level > 0:
                level = max(font_level, 2)
            else:
                # Font heuristic has nothing to say. Trust the layout label
                # only if the text plausibly looks like a header.
                text = line_style.text
                if text.endswith((".", ",", ";", ":", "!", "?")):
                    return False  # Trailing punctuation: usually a sentence, not a heading
                if len(text) > self.options.header_max_line_length:
                    return False  # Too long for a header
                # Pick a level from context rather than the old hard-coded 2:
                # sibling of the most recent emitted heading; fall back to h2
                # when nothing has been emitted yet.
                level = self._last_heading_level if self._last_heading_level > 0 else 2

        inline_content = self._process_text_spans_to_inline(spans, links, page_num, average_line_height)
        if not inline_content or not inline_has_text(inline_content):
            return True

        self._flush_state_paragraph(state, page_num)
        self._emit_heading(state, level, line_style.text, inline_content, page_num, _span_union_bbox(spans))
        return True

    def _accumulate_paragraph_line(
        self,
        line: dict,
        spans: list,
        links: list[dict],
        vertical_gap: float,
        paragraph_break_threshold: float,
        state: _BlockProcessingState,
        page_num: int,
        average_line_height: float | None,
    ) -> None:
        """Accumulate regular text line into paragraph state."""
        # Converted before the split test below rather than after it, because the conversion
        # is what turns a symbol-font bullet into a recognisable marker -- see
        # _leading_inline_text. The flush still has to happen before the empty-content
        # return, so that a line which converts to nothing keeps ending a paragraph on gap.
        inline_content = self._process_text_spans_to_inline(spans, links, page_num, average_line_height)

        # A list item runs on across the vertical gaps that separate paragraphs -- the space
        # between two bullets is the same space that ends a paragraph -- so the gap rule is
        # suspended once a list has started. Without a second rule to end an item, though,
        # every bullet in a list ran into its predecessor and the whole list arrived as a
        # single item: one born-digital article emitted 1 list item for its 16 bullets.
        # A line carrying its own marker is the next item, whatever the spacing says.
        #
        # This asks with the liberal reader, unlike the paragraph-start test below. It is
        # gated on the paragraph already being a list, so it can only ever re-split one;
        # narrowing it to the conservative reader ran a whole ordered list back into a
        # single item, because "2." is a span of its own and stops that reader dead.
        opens_with_marker = self._is_valid_list_marker(_opening_line_text(inline_content))[0]
        starts_new_item = state.paragraph_is_list and opens_with_marker
        breaks_paragraph = vertical_gap > paragraph_break_threshold and not state.paragraph_is_list
        if state.paragraph_content and (starts_new_item or breaks_paragraph):
            self._flush_state_paragraph(state, page_num)

        if not inline_content:
            return

        if state.paragraph_content:
            # Add an inter-line separator unless the previous line already
            # ended with whitespace (collapse_excess_whitespace would
            # otherwise leave us with a 2-space run at the line boundary).
            if not (self.options.collapse_excess_whitespace and _trailing_text_is_whitespace(state.paragraph_content)):
                state.paragraph_content.append(Text(content=" "))
        else:
            # Starting new paragraph
            state.paragraph_bbox = line["bbox"]
            state.paragraph_is_list, state.paragraph_list_type = self._is_valid_list_marker(
                _leading_inline_text(inline_content)
            )

        state.paragraph_content.extend(inline_content)

        # Expand bbox to include this line
        if state.paragraph_bbox:
            line_bbox = line["bbox"]
            state.paragraph_bbox = (
                min(state.paragraph_bbox[0], line_bbox[0]),
                min(state.paragraph_bbox[1], line_bbox[1]),
                max(state.paragraph_bbox[2], line_bbox[2]),
                max(state.paragraph_bbox[3], line_bbox[3]),
            )

    def _process_single_block_to_ast(
        self, block: dict, links: list[dict], page_num: int, average_line_height: float | None = None
    ) -> list[Node]:
        """Process a single text block to AST nodes.

        Parameters
        ----------
        block : dict
            Single text block from PyMuPDF
        links : list of dict
            Links on the page
        page_num : int
            Page number for source tracking
        average_line_height : float or None, optional
            Average line height for the page, used for link threshold auto-calibration

        Returns
        -------
        list of Node
            List of AST nodes (paragraphs, headings, code blocks)

        """
        if "lines" not in block:
            return []

        layout_label = block.get("_layout_label")
        state = _BlockProcessingState()
        paragraph_break_threshold = self._calculate_paragraph_break_threshold(block)

        # Layout hint: if model says list-item, pre-set list state
        if layout_label == "list-item":
            state.paragraph_is_list = True
            state.paragraph_list_type = "unordered"

        for line in block["lines"]:
            # Handle rotated text (skip further processing if rotated)
            if self._handle_rotated_line(line, state, page_num):
                continue

            spans = list(line.get("spans", []))
            if not spans:
                continue

            this_y = line["bbox"][3]
            vertical_gap = abs(this_y - state.previous_y) if state.previous_y > 0 else 0
            text = "".join([s["text"] for s in spans])
            state.previous_y = this_y

            # Handle monospace text (code blocks)
            if self._handle_monospace_line(line, spans, text, block, state, page_num):
                continue

            # Finalize code block if we were in one
            if state.in_code_block:
                self._finalize_code_block(state, page_num)

            # Handle headers - layout label overrides font-size heuristics. A line carries
            # its own label when the model drew a box around it, which is the only way a
            # heading inside a full-column block is ever labelled; fall back to the block's
            # label, which is all that exists when the block is one semantic unit.
            line_label = line.get("_layout_label") or layout_label
            if line_label in ("title", "section-header"):
                if self._handle_header_line_with_layout(spans, links, state, page_num, average_line_height, line_label):
                    continue
            elif self._handle_header_line(spans, links, state, page_num, average_line_height):
                continue

            # Regular paragraph text
            self._accumulate_paragraph_line(
                line, spans, links, vertical_gap, paragraph_break_threshold, state, page_num, average_line_height
            )

        # Finalize remaining content
        self._flush_rotated_text(state, page_num)
        self._flush_state_paragraph(state, page_num)
        if state.in_code_block:
            self._finalize_code_block(state, page_num)
        # Flush any unmerged numbering prefix at block end so it surfaces
        # as a standalone heading rather than vanishing.
        self._flush_pending_heading_prefix(state)

        return state.nodes

    def _resolve_link_for_span(
        self, links: list[dict], span: dict, average_line_height: float | None = None
    ) -> str | None:
        """Resolve link URL for a text span with auto-calibrated overlap threshold.

        Parameters
        ----------
        links : list of dict
            Links on the page
        span : dict
            Text span
        average_line_height : float or None, optional
            Average line height for the page, used for auto-calibration of threshold
            for spans with unusual heights (e.g., large fonts)

        Returns
        -------
        str or None
            Link URL if span is part of a link

        Notes
        -----
        Uses the link_overlap_threshold option from self.options to determine
        the minimum overlap required for link detection. When average_line_height
        is provided, automatically adjusts the threshold for spans that are
        significantly taller than average (common in documents with font scaling).

        """
        if not links or not span.get("text"):
            return None

        import pymupdf

        bbox = pymupdf.Rect(span["bbox"])

        # Calculate span height
        span_height = bbox.height

        # Use threshold from options
        threshold_percent = self.options.link_overlap_threshold

        # Auto-calibrate threshold for tall spans if average line height is available
        if average_line_height and average_line_height > 0 and span_height > average_line_height * 1.5:
            # Span is significantly taller than average (>1.5x), likely due to font scaling
            # Relax the threshold to compensate for the increased bbox area
            # Scale down threshold proportionally to the height ratio
            height_ratio = span_height / average_line_height
            adjusted_threshold = threshold_percent / (height_ratio**0.5)  # Square root dampening
            adjusted_threshold = max(adjusted_threshold, 30.0)  # Don't go below 30%
            threshold_percent = adjusted_threshold
            logger.debug(
                f"Auto-calibrated link threshold for tall span: "
                f"{self.options.link_overlap_threshold:.1f}% -> {threshold_percent:.1f}% "
                f"(span height: {span_height:.1f}, avg: {average_line_height:.1f})"
            )

        # Find all links that overlap with this span
        for link in links:
            hot = link["from"]  # The hot area of the link
            overlap = hot & bbox
            bbox_area = (threshold_percent / 100.0) * abs(bbox)
            if abs(overlap) >= bbox_area:
                return link.get("uri")

        return None

    @classmethod
    def _extract_cell_text(cls, cell_text: Any) -> str:
        """Normalize a table cell value to a stripped string.

        Parameters
        ----------
        cell_text : Any
            Cell text value which may be None, string, or other type

        Returns
        -------
        str
            Stripped cell text, empty string if None

        """
        if cell_text is None:
            return ""
        return str(cell_text).strip()

    @staticmethod
    def _char_mass(table_data: "Sequence[Sequence[str | None]]") -> int:
        """Non-whitespace character count of a grid -- the mass a rebuild must preserve."""
        return sum(len("".join(str(cell).split())) for row in table_data for cell in row if cell is not None)

    @staticmethod
    def _table_row_extents(table: Any, n_rows: int) -> list[tuple[float, float]] | None:
        """Vertical extents of a find_tables() grid's rows, for continuation merging.

        Parameters
        ----------
        table : PyMuPDF Table
            Table object from ``find_tables()``.
        n_rows : int
            Number of rows in the extracted grid; the extents are only meaningful
            when they describe exactly those rows.

        Returns
        -------
        list of (float, float) or None
            ``(top, bottom)`` per row, or ``None`` when the table's row geometry
            is missing, does not match the extracted grid, or is not line-like --
            the caller then skips the merge rather than merging on wrong geometry.

        """
        try:
            rows = list(table.rows)
            if len(rows) != n_rows:
                return None
            extents = [(float(row.bbox[1]), float(row.bbox[3])) for row in rows]
        except Exception:
            return None
        # The merge reads inter-line gaps, which only mean anything when the rows
        # are stacked printed lines. On tables with row spans, find_tables() hands
        # back overlapping row bboxes -- one row's box containing whole later rows,
        # gaps of -17pt -- and every gap statistic computed over them is garbage
        # (measured: a rowspan table's 5 true rows fused to 4, another's 42 to 31).
        # Printed lines never overlap by more than font-box slop, so anything past
        # 1pt of overlap means this is not line geometry, and extract()'s own row
        # structure -- which already understands the spans -- is left alone.
        if any(
            extents[index][0] < extents[index - 1][1] - MAX_ROW_EXTENT_OVERLAP_PT for index in range(1, len(extents))
        ):
            return None
        return extents

    def _process_table_to_ast(
        self,
        table: Any,
        page: "pymupdf.Page",
        page_num: int,
        clip_extension: "tuple[pymupdf.Rect, str] | None" = None,
    ) -> Node | None:
        """Process a PyMuPDF table to AST Table node.

        Directly accesses table cell data from PyMuPDF table object instead of
        converting to markdown and re-parsing, which is more efficient and robust.

        Parameters
        ----------
        table : PyMuPDF Table
            Table object from find_tables()
        page : pymupdf.Page
            Page containing the table. Used to recover the region's text when the
            detection is rejected as a degenerate grid.
        page_num : int
            Page number for source tracking
        clip_extension : tuple of (pymupdf.Rect, str), optional
            A clipped column admitted at detection time (see
            ``adjacent_clipped_column``): the rectangle holding its words and the
            side of the table it sits on. Its words join the grid as one more cell
            per row.

        Returns
        -------
        Node or None
            A table when the detection is a real grid; a paragraph carrying the
            region's text when it is a degenerate (1xN / Nx1) grid; ``None`` when
            the region has no usable content.

        """
        import pymupdf

        try:
            # Try to extract cells directly from PyMuPDF table object
            # PyMuPDF tables have a `extract()` method that returns cell data
            table_data = table.extract()

            if not table_data or len(table_data) == 0:
                logger.debug("Table has no data")
                return None

            # ``Table.extract()`` assembles cell text from the characters its cell
            # rects clip, so a glyph straddling a boundary is cut mid-character --
            # on the PMC dev corpus it produced cells reading "Contro" and
            # "perce ntage" inside grids whose geometry the rulings corroborate.
            # The split-word guard that already protects the text-alignment
            # strategy detects exactly this damage, so run it on every grid; but
            # where the text strategy's failure means the *columns* are invented
            # (reject), a line-corroborated grid's failure means only the text
            # assembly is wrong -- so repair it from the page's own word boxes,
            # which cannot be cut by construction.
            repaired = False
            fragments = split_word_ratio(page, table_data)
            lost = extract_loss_share(page, table_data, table.bbox)
            # A third failure mode is invisible to both guards above (#419): a column
            # boundary drawn *through* cell content splits "Vitamin B12," into
            # "Vitamin B" | "12," -- no word is lost, and the fragment tokenizer is
            # digit-blind by design. The page's word boxes are the evidence again: a
            # boundary the grid draws on a row while the page prints a word across it
            # is contradicted. Spanning header cells omit the edge on their row and
            # are left untouched -- see MIN_COLUMN_CUT_ROWS for the measured gap.
            cut_boundaries = contradicted_column_boundaries(page, table, table_data)
            # The bbox's own outer edge can cut words the same way ("0.454 \u00b1 0.024"
            # extracted as "4 \u00b1 0"): extract_loss_share cannot see those words -- their
            # centers lie outside the bbox -- so rows carrying them are their own
            # trigger, and the rebuild's outer-cell rule heals them in place.
            clipped_rows = bbox_clipped_rows(page, table) if not cut_boundaries else 0
            if (
                fragments > MAX_SPLIT_WORD_RATIO
                or lost > MAX_EXTRACT_LOSS_SHARE
                or cut_boundaries
                or clipped_rows >= MIN_COLUMN_CUT_ROWS
            ):
                # Rebuilding fixes the *text* either way -- a cut word lands whole in
                # the cell holding its center. Whether the boundary itself should go
                # depends on which shape cut it: dissolve the ones whose uncut rows
                # read straight across them (one printed column split in two), and
                # keep the real boundaries wide values merely overhang. See
                # boundaries_to_dissolve for the gutter-width arbiter.
                dissolve = boundaries_to_dissolve(page, table, cut_boundaries) if cut_boundaries else []
                rebuilt = rebuild_cells_from_words(page, table, dissolve_boundaries=dissolve or None)
                # The rebuild must come back at least as heavy as what it replaces:
                # on rotated pages the cell rects and word boxes do not share a
                # coordinate frame, and a rebuild that misses the words would gut
                # the table it was meant to repair.
                if rebuilt is not None and self._char_mass(rebuilt) >= MIN_REBUILD_CHAR_RATIO * self._char_mass(
                    table_data
                ):
                    logger.debug(
                        f"Rebuilt table cell text from word boxes on page {page_num + 1}: "
                        f"{fragments:.0%} of extracted tokens were fragments, "
                        f"{lost:.0%} of the region's words were missing from the grid, "
                        f"{len(cut_boundaries)} column boundaries contradicted by word boxes"
                    )
                    table_data = rebuilt
                    repaired = True

            # A clipped column admitted at detection time joins the grid here: its
            # words, grouped by the grid's own row bands, become one more cell per
            # row on the side the bbox cut it from. The bbox recorded in table_info
            # already covers the region, so the text appears nowhere else.
            if clip_extension is not None:
                extension_rect, side = clip_extension
                extension_words = [
                    word for word in page.get_text("words") if pymupdf.Rect(word[:4]).intersects(extension_rect)
                ]
                extension_cells: list[str] = []
                for row in getattr(table, "rows", []) or []:
                    row_cells = [cell[:4] for cell in (getattr(row, "cells", None) or []) if cell is not None]
                    if not row_cells:
                        extension_cells.append("")
                        continue
                    top = min(cell[1] for cell in row_cells)
                    bottom = max(cell[3] for cell in row_cells)
                    lines: dict[tuple[int, int], list[str]] = {}
                    for word in extension_words:
                        center_y = (word[1] + word[3]) / 2
                        if top <= center_y <= bottom:
                            lines.setdefault((word[5], word[6]), []).append(str(word[4]))
                    extension_cells.append("\n".join(" ".join(parts) for _key, parts in sorted(lines.items())))
                if len(extension_cells) == len(table_data) and any(cell.strip() for cell in extension_cells):
                    table_data = [
                        [*row, cell] if side == "right" else [cell, *row]
                        for row, cell in zip(table_data, extension_cells, strict=True)
                    ]
                    repaired = True

            # Reject pathological detections (PyMuPDF's find_tables() can fire on
            # decorative frames / TOC dot-leader regions / non-tabular content,
            # the same way our ruling-line fallback can). Same caps as ruling.
            n_rows = len(table_data)
            n_cols = max((len(r) for r in table_data), default=0)
            n_cells = sum(len(r) for r in table_data)
            if n_cells == 0:
                return None
            # A grid needs two dimensions to be a table. One column is prose wrapped in
            # pipes; one row is a single line of text chopped at its word boundaries --
            # find_tables() emits both, and on an academic paper it turned the sentence
            # "What is the capital of this country?" into an eight-column table. Neither
            # shape can carry tabular meaning, and rendering them as tables is strictly
            # worse than leaving the text alone.
            #
            # Return the region's text as a paragraph rather than None: the text inside a
            # table bbox has already been excluded from the ordinary text blocks, so
            # returning None here would delete it, not demote it.
            if n_rows < MIN_TABLE_ROWS or n_cols < MIN_TABLE_COLS:
                logger.debug(
                    f"Rejecting pymupdf table on page {page_num + 1}: "
                    f"{n_rows}x{n_cols} is not a grid (needs at least "
                    f"{MIN_TABLE_ROWS}x{MIN_TABLE_COLS})"
                )
                self._record_table_rejection("degenerate_grid")
                return self._region_text_as_paragraph(page, pymupdf.Rect(table.bbox), page_num)
            if n_cols > MAX_TABLE_COLS or n_rows > MAX_TABLE_ROWS:
                logger.debug(
                    f"Rejecting pymupdf table on page {page_num + 1}: {n_rows}x{n_cols} grid exceeds size caps"
                )
                self._record_table_rejection("oversized_grid")
                return self._region_text_as_paragraph(page, pymupdf.Rect(table.bbox), page_num)
            n_empty = sum(1 for r in table_data for c in r if c is None or not str(c).strip())
            if n_empty / n_cells > MAX_TABLE_EMPTY_RATIO:
                logger.debug(
                    f"Rejecting pymupdf table on page {page_num + 1}: "
                    f"{n_empty}/{n_cells} ({n_empty / n_cells:.0%}) cells empty"
                )
                self._record_table_rejection("mostly_empty")
                return self._region_text_as_paragraph(page, pymupdf.Rect(table.bbox), page_num)
            unique_texts = {str(c).strip() for r in table_data for c in r if c is not None and str(c).strip()}
            n_filled = n_cells - n_empty
            if len(unique_texts) == 1 and n_filled >= MIN_FILLED_FOR_UNIFORMITY_CHECK:
                logger.debug(
                    f"Rejecting pymupdf table on page {page_num + 1}: "
                    f"all {n_filled} non-empty cells have identical content"
                )
                self._record_table_rejection("uniform_cells")
                return self._region_text_as_paragraph(page, pymupdf.Rect(table.bbox), page_num)
            n_dot_leader = sum(1 for r in table_data for c in r if c is not None and is_dot_leader_cell(str(c)))
            if n_filled and n_dot_leader / n_filled > MAX_DOT_LEADER_CELL_RATIO:
                logger.debug(
                    f"Rejecting pymupdf table on page {page_num + 1}: "
                    f"{n_dot_leader}/{n_filled} ({n_dot_leader / n_filled:.0%}) cells are "
                    f"dot-leader noise (looks like TOC region)"
                )
                self._record_table_rejection("dot_leader_toc")
                return self._region_text_as_paragraph(page, pymupdf.Rect(table.bbox), page_num)
            # A passage of prose the detector fenced is not a table (#451). Demoted to a
            # paragraph it reads as it is printed; left as a grid it reads as a cell, and
            # where the region spans two columns they interleave line by line inside it.
            if looks_like_gridded_prose(table_data):
                logger.debug(f"Rejecting pymupdf table on page {page_num + 1}: one cell holds the region's prose")
                self._record_table_rejection("gridded_prose")
                return self._region_text_as_paragraph(page, pymupdf.Rect(table.bbox), page_num)

            # A find_tables() grid can shred wrapped cells the same way the
            # word-gutter grid did before #416: where the rulings only mark
            # columns, PyMuPDF snaps its rows to printed lines, and a cell
            # wrapping to a second line splits mid-sentence. The row bboxes
            # carry the same inter-line geometry the gutter path merges on, so
            # the same guarded merge runs here. Dense grids with real row
            # rulings have uniform gaps and filled anchors, and pass through
            # untouched.
            line_rows = [[self._extract_cell_text(c) for c in row] for row in table_data]
            row_extents = self._table_row_extents(table, len(line_rows))
            merged = (
                merge_continuation_lines(line_rows, row_extents, continuation_within_start_columns=True)
                if row_extents is not None
                else line_rows
            )
            if len(merged) < MIN_TABLE_ROWS:
                # The merge collapsed the grid below two rows: whatever this
                # region is, it is one logical row of text, not a table.
                logger.debug(
                    f"Rejecting pymupdf table on page {page_num + 1}: "
                    f"{len(line_rows)} printed lines merge into {len(merged)} logical rows"
                )
                self._record_table_rejection("degenerate_grid")
                return self._region_text_as_paragraph(page, pymupdf.Rect(table.bbox), page_num)

            # Untouched tables keep the exact text extract() gave them. Repaired
            # or merged ones get the word-gutter path's cell treatment: newline
            # joins feed hyphenation repair, then whitespace collapses.
            changed = repaired or len(merged) != len(line_rows)

            def make_cell(cell_text: str) -> TableCell:
                if changed:
                    if self.options.merge_hyphenated_words:
                        cell_text = dehyphenate_text(cell_text)
                    cell_text = " ".join(cell_text.split())
                return TableCell(content=[Text(content=cell_text)])

            header_row = TableRow(cells=[make_cell(cell_text) for cell_text in merged[0]], is_header=True)
            data_rows = [TableRow(cells=[make_cell(cell_text) for cell_text in row]) for row in merged[1:]]

            return AstTable(
                header=header_row, rows=data_rows, source_location=SourceLocation(format="pdf", page=page_num + 1)
            )

        except (AttributeError, Exception) as e:
            # Fallback to markdown conversion if direct extraction fails
            logger.debug(f"Direct table extraction failed ({e}), falling back to markdown parsing")
            return self._process_table_to_ast_fallback(table, page_num)

    def _process_table_to_ast_fallback(self, table: Any, page_num: int) -> AstTable | None:
        """Fallback method using markdown conversion when direct extraction fails.

        Parameters
        ----------
        table : PyMuPDF Table
            Table object from find_tables()
        page_num : int
            Page number for source tracking

        Returns
        -------
        AstTable or None
            Table node if table has content

        """
        try:
            # Get table as markdown
            table_md = table.to_markdown(clean=False)
            if not table_md:
                return None

            # Parse the markdown table to extract structure
            lines = table_md.strip().split("\n")
            if len(lines) < 2:  # Need at least header and separator
                return None

            # Parse header row (first line)
            header_line = lines[0]
            header_cells_text = self._parse_markdown_table_row(header_line)

            # Skip separator line (second line)
            # Parse data rows (remaining lines)
            data_rows_text = []
            for line in lines[2:]:
                if line.strip():
                    row_cells = self._parse_markdown_table_row(line)
                    if row_cells:
                        data_rows_text.append(row_cells)

            # Build AST table
            header_cells = [TableCell(content=[Text(content=cell)]) for cell in header_cells_text]
            header_row = TableRow(cells=header_cells, is_header=True)

            data_rows = []
            for row_cells in data_rows_text:
                cells = [TableCell(content=[Text(content=cell)]) for cell in row_cells]
                data_rows.append(TableRow(cells=cells))

            return AstTable(
                header=header_row, rows=data_rows, source_location=SourceLocation(format="pdf", page=page_num + 1)
            )

        except Exception as e:
            logger.debug(f"Fallback table processing failed: {e}")
            return None

    def _extract_table_from_ruling_rect(
        self,
        page: "pymupdf.Page",
        table_rect: "pymupdf.Rect",
        h_lines: list[tuple],
        v_lines: list[tuple],
        page_num: int,
    ) -> Node | None:
        """Extract table content from a bounding box using ruling lines.

        Implements basic grid-based cell segmentation using detected horizontal
        and vertical lines to extract text from each cell.

        Parameters
        ----------
        page : pymupdf.Page
            PDF page containing the table
        table_rect : pymupdf.Rect
            Bounding box of the table
        h_lines : list of tuple
            Horizontal ruling lines as (x0, y0, x1, y1) tuples
        v_lines : list of tuple
            Vertical ruling lines as (x0, y0, x1, y1) tuples
        page_num : int
            Page number for source tracking

        Returns
        -------
        Node or None
            A table when the ruling lines really bound one; a paragraph carrying the
            region's text when the detection is rejected or extraction is switched
            off; ``None`` only when the region holds no text at all.

        Notes
        -----
        This method uses grid-based cell segmentation. It may not work well
        for tables without clear ruling lines or with merged cells.

        Every path out of here that is *not* a table returns the region's text as a
        paragraph rather than ``None``. The region's text was removed from the ordinary
        text blocks before this ran (see :meth:`_region_text_as_paragraph`), so this
        method is the only remaining copy of it: ``None`` deletes it, it does not demote
        it. The caller, :meth:`_process_table_item`, appends whatever comes back and
        adds nothing of its own, so there is no risk of emitting the text twice.

        """
        if self.options.table_fallback_extraction_mode == "none":
            # "Detect only, don't extract". The region was still detected, so its text is
            # already out of the text blocks -- hand it back as prose. Not recorded as a
            # rejection: nothing was rejected, the caller configured extraction off.
            return self._region_text_as_paragraph(page, table_rect, page_num)

        # Sort lines for grid creation
        h_lines_sorted = sorted(h_lines, key=lambda line: line[1])  # Sort by y-coordinate
        v_lines_sorted = sorted(v_lines, key=lambda line: line[0])  # Sort by x-coordinate

        # Extract y-coordinates for rows (between consecutive h_lines)
        row_y_coords = [(h_lines_sorted[i][1], h_lines_sorted[i + 1][1]) for i in range(len(h_lines_sorted) - 1)]

        # Extract x-coordinates for columns (between consecutive v_lines)
        col_x_coords = [(v_lines_sorted[i][0], v_lines_sorted[i + 1][0]) for i in range(len(v_lines_sorted) - 1)]

        n_rows = len(row_y_coords)
        n_cols = len(col_x_coords)
        n_cells = n_rows * n_cols

        # The same degenerate-grid cap the find_tables() path applies, on the grid the
        # ruling lines actually bound: n lines on an axis bound n-1 cells, so the old
        # ">= 2 lines on each axis" test admitted a 1x1 "table" -- a framed text box that
        # cleared the sparsity guard came out as a single cell of prose wrapped in pipes.
        # Fewer than two lines on an axis bounds no cells at all and lands here too.
        if n_rows < MIN_TABLE_ROWS or n_cols < MIN_TABLE_COLS:
            logger.debug(
                f"Rejecting ruling-line table on page {page_num + 1}: "
                f"{n_rows}x{n_cols} is not a grid (needs at least "
                f"{MIN_TABLE_ROWS}x{MIN_TABLE_COLS})"
            )
            self._record_table_rejection("degenerate_grid")
            return self._region_text_as_paragraph(page, table_rect, page_num)

        # Create grid cells from line intersections
        rows: list[TableRow] = []

        import pymupdf

        n_empty = 0
        n_dot_leader = 0
        unique_texts: set[str] = set()

        for row_idx, (y0, y1) in enumerate(row_y_coords):
            cells: list[TableCell] = []

            for _col_idx, (x0, x1) in enumerate(col_x_coords):
                cell_rect = pymupdf.Rect(x0, y0, x1, y1)
                cell_text = clipped_textbox(page, cell_rect).strip()

                if cell_text:
                    unique_texts.add(cell_text)
                    if is_dot_leader_cell(cell_text):
                        n_dot_leader += 1
                else:
                    n_empty += 1

                cells.append(TableCell(content=[Text(content=cell_text)]))

            # First row is typically the header
            is_header = row_idx == 0
            rows.append(TableRow(cells=cells, is_header=is_header))

        if not rows:
            return self._region_text_as_paragraph(page, table_rect, page_num)

        # Sparsity guard: real tables are not mostly empty. A "table" past
        # MAX_TABLE_EMPTY_RATIO is almost always a misfire on a bordered region.
        if n_cells > 0 and n_empty / n_cells > MAX_TABLE_EMPTY_RATIO:
            logger.debug(
                f"Rejecting ruling-line table on page {page_num + 1}: "
                f"{n_empty}/{n_cells} ({n_empty / n_cells:.0%}) cells empty"
            )
            self._record_table_rejection("mostly_empty")
            return self._region_text_as_paragraph(page, table_rect, page_num)

        # Uniformity guard: a "table" where every non-empty cell has the same
        # content is the prompt-callout pattern (decorative box with a
        # repeated title fragment scattered across cells).
        n_filled = n_cells - n_empty
        if len(unique_texts) == 1 and n_filled >= MIN_FILLED_FOR_UNIFORMITY_CHECK:
            logger.debug(
                f"Rejecting ruling-line table on page {page_num + 1}: "
                f"all {n_filled} non-empty cells have identical content"
            )
            self._record_table_rejection("uniform_cells")
            return self._region_text_as_paragraph(page, table_rect, page_num)

        if n_filled and n_dot_leader / n_filled > MAX_DOT_LEADER_CELL_RATIO:
            logger.debug(
                f"Rejecting ruling-line table on page {page_num + 1}: "
                f"{n_dot_leader}/{n_filled} ({n_dot_leader / n_filled:.0%}) cells are "
                f"dot-leader noise (looks like TOC region)"
            )
            self._record_table_rejection("dot_leader_toc")
            return self._region_text_as_paragraph(page, table_rect, page_num)

        # Separate header and data rows
        header_row = rows[0] if rows else TableRow(cells=[])
        data_rows = rows[1:] if len(rows) > 1 else []

        return AstTable(
            header=header_row, rows=data_rows, source_location=SourceLocation(format="pdf", page=page_num + 1)
        )

    def _extract_table_from_layout_region(
        self, page: "pymupdf.Page", table_rect: "pymupdf.Rect", page_num: int
    ) -> Node | None:
        """Extract the content of a region the layout model predicted to be a table.

        Uses ``page.find_tables()`` scoped to the predicted region, trying ruling lines
        first and then text alignment. When no structured table can be recovered there,
        the region's text is returned as a **paragraph**.

        It used to be returned as a single-column table -- one row per line of text --
        and that was wrong twice over. A one-column table is not a table: it is prose
        wrapped in pipes, so the output was *worse* than plain text, not better. And
        because these tables are the only copy of the region's text (it is excluded
        from the ordinary text blocks to avoid duplication), the mangling could not
        simply be dropped either: suppressing them on a real arXiv paper removed 144
        junk table rows and 530 words of body text along with them.

        The layout model over-fires on academic PDFs -- on one paper it predicted six
        "table" regions and none of them held a table -- so this path is common, and
        every one of those six became a fake table. No converter option changed that;
        the same six appeared under every ``table_detection_mode``, because they never
        came from the table detector at all.

        Parameters
        ----------
        page : pymupdf.Page
            PDF page containing the region.
        table_rect : pymupdf.Rect
            Bounding box predicted by the layout model.
        page_num : int
            Page number for source tracking.

        Returns
        -------
        Node or None
            A table when the region really holds one, otherwise a paragraph carrying
            its text. ``None`` only when the region is empty.

        """
        # Try PyMuPDF's find_tables within the predicted region, line-based detection
        # first and text alignment second (see TABLE_REGION_STRATEGIES: the default
        # strategy needs ruling lines on both axes, which borderless journal tables do
        # not have). Only a real table is accepted here: a rejected detection may hand
        # back a paragraph covering just the grid's bbox, which can be narrower than the
        # region the layout model predicted. Falling through instead keeps the whole
        # region's text.
        found_grid = False
        for strategy in TABLE_REGION_STRATEGIES:
            try:
                tabs = page.find_tables(clip=table_rect, strategy=strategy)
            except Exception:
                # PyMuPDF table detection is best-effort; try the next strategy.
                continue
            if not tabs.tables:
                continue
            # Set before the guards below, not after them. This flag answers "was anything
            # tabular found here at all", which is true of a grid that was found and then
            # rejected -- and the rejection paths below `continue`, so setting it after them
            # meant it was only ever true for grids that survived. See the double-count note
            # at the foot of this method.
            found_grid = True
            # Text alignment has no ruling lines corroborating it, so it is held to one
            # extra test the line strategies are not: its columns must not cut through
            # words. See MAX_SPLIT_WORD_RATIO -- without this, a mis-predicted region
            # renders a page of prose as a multi-column table of half-words.
            if strategy == "text":
                try:
                    fragments = split_word_ratio(page, tabs.tables[0].extract())
                except Exception:
                    fragments = 0.0
                if fragments > MAX_SPLIT_WORD_RATIO:
                    logger.debug(
                        f"Rejecting text-aligned grid on page {page_num + 1}: "
                        f"{fragments:.0%} of its word tokens are fragments, so its columns "
                        f"cut through words rather than falling between them"
                    )
                    self._record_table_rejection("text_grid_splits_words")
                    continue
            table = self._process_table_to_ast(tabs.tables[0], page, page_num)
            if isinstance(table, AstTable):
                return table

        # Third pass: build the grid from the page's own word boxes (#386). The two
        # find_tables() strategies above delegate both geometry and cell text to
        # PyMuPDF, and on borderless journal tables its text mode invents column
        # boundaries through words and reassembles cells with lost spaces -- so the
        # split-word guard kills the grid, correctly, and the table is lost. Word
        # boxes cannot be cut by construction (boundaries sit at gutter midpoints and
        # every word lands whole in the column holding its center), so this pass needs
        # no word-integrity guard; the gutters themselves are the evidence, and the
        # shape guards below still apply. Runs last so every grid the established
        # strategies already accept keeps its exact path.
        gutter_found, table = self._extract_table_from_word_gutters(page, table_rect, page_num)
        if isinstance(table, AstTable):
            return table
        found_grid = found_grid or gutter_found

        # No table here -- the layout model was wrong. Keep the text, drop the pipes.
        paragraph = self._region_text_as_paragraph(page, table_rect, page_num)
        if paragraph is not None and not found_grid:
            # Only when nothing tabular was found at all. If a grid *was* found and then
            # rejected, that guard has already recorded its own, more specific reason --
            # adding this vaguer one on top counts the same region twice and takes a
            # second bite out of the confidence score.
            self._record_table_rejection("layout_region_not_tabular")
        return paragraph

    def _extract_table_from_word_gutters(
        self, page: "pymupdf.Page", table_rect: "pymupdf.Rect", page_num: int
    ) -> tuple[bool, AstTable | None]:
        """Recover a borderless table from word-box gutters inside a layout region.

        Parameters
        ----------
        page : pymupdf.Page
            PDF page containing the region.
        table_rect : pymupdf.Rect
            Bounding box predicted by the layout model.
        page_num : int
            Page number for source tracking.

        Returns
        -------
        tuple of (bool, AstTable or None)
            Whether anything tabular was found (a grid that a guard then rejected
            still counts, so the caller does not also record the vaguer
            ``layout_region_not_tabular`` on top of the guard's reason), and the
            table when one survives the guards.

        """
        import pymupdf

        try:
            words = [word for word in page.get_text("words") if pymupdf.Rect(word[:4]).intersects(table_rect)]
        except Exception:
            return False, None
        grid = word_gutter_grid(words)
        if grid is None:
            return False, None

        n_rows = len(grid)
        n_cols = max((len(row) for row in grid), default=0)
        if n_rows < MIN_TABLE_ROWS or n_cols < MIN_TABLE_COLS:
            self._record_table_rejection("degenerate_grid")
            return True, None
        if n_rows > MAX_TABLE_ROWS or n_cols > MAX_TABLE_COLS:
            self._record_table_rejection("oversized_grid")
            return True, None

        n_cells = n_rows * n_cols
        n_empty = 0
        n_dot_leader = 0
        unique_texts: set[str] = set()
        for row in grid:
            for cell_text in row:
                if cell_text:
                    unique_texts.add(cell_text)
                    if is_dot_leader_cell(cell_text):
                        n_dot_leader += 1
                else:
                    n_empty += 1

        if n_empty / n_cells > MAX_TABLE_EMPTY_RATIO:
            logger.debug(
                f"Rejecting word-gutter table on page {page_num + 1}: "
                f"{n_empty}/{n_cells} ({n_empty / n_cells:.0%}) cells empty"
            )
            self._record_table_rejection("mostly_empty")
            return True, None
        n_filled = n_cells - n_empty
        if len(unique_texts) == 1 and n_filled >= MIN_FILLED_FOR_UNIFORMITY_CHECK:
            self._record_table_rejection("uniform_cells")
            return True, None
        if n_filled and n_dot_leader / n_filled > MAX_DOT_LEADER_CELL_RATIO:
            self._record_table_rejection("dot_leader_toc")
            return True, None
        # A numbered reference list is the worst grid to emit: row-major cell order
        # interleaves the page's two columns, scrambling every citation -- measured on
        # the PMC corpus, one gridded bibliography cost 15 of an article's 21 citation
        # titles their recall. Demoted to prose it reads exactly as it did before.
        if looks_like_numbered_bibliography(grid):
            self._record_table_rejection("numbered_bibliography")
            return True, None
        # The same fenced-prose guard the find_tables() path applies (#451). This is the
        # path the journal keywords-box-beside-abstract shape arrives on: the whitespace
        # between the two is a real gutter, so the grid is sound and only its content
        # says it is not a table.
        if looks_like_gridded_prose(grid):
            self._record_table_rejection("gridded_prose")
            return True, None
        # A two-column grid rides on a single gutter -- the weakest geometry the sweep
        # accepts, and the one shape it shares with a chart, whose axis ticks and
        # legend labels grid perfectly across the plot area. What separates them is
        # under the text: a chart's words float over its plot's vector paths, while a
        # borderless table has at most its own ruling lines -- measured on the PMC
        # corpus (#389), 541 intersecting paths against 0-4. get_drawings() is costly,
        # so this runs last and only at the two-column tier; wider grids carry two
        # aligned boundaries, which stray chart labels do not produce.
        if n_cols == 2 and self._region_drawing_count(page, table_rect) > MAX_TWO_COLUMN_REGION_DRAWINGS:
            self._record_table_rejection("two_column_chart_region")
            return True, None

        def cell_node(cell_text: str) -> TableCell:
            # Merged continuation lines join with a newline so hyphenation repair can
            # run across the wrap, the same as the paragraph path does.
            if self.options.merge_hyphenated_words:
                cell_text = dehyphenate_text(cell_text)
            return TableCell(content=[Text(content=" ".join(cell_text.split()))])

        rows = [
            TableRow(cells=[cell_node(cell_text) for cell_text in row], is_header=index == 0)
            for index, row in enumerate(grid)
        ]
        return True, AstTable(
            header=rows[0],
            rows=rows[1:],
            source_location=SourceLocation(format="pdf", page=page_num + 1),
        )

    @staticmethod
    def _region_drawing_count(page: "pymupdf.Page", region: "pymupdf.Rect") -> int:
        """Count the vector drawing paths intersecting *region*.

        Returns ``0`` on any error, so an unreadable page falls back to the other
        guards rather than dropping a table nothing has shown to be bad -- the same
        fail-open posture as :func:`split_word_ratio`.

        Parameters
        ----------
        page : pymupdf.Page
            Page holding the region.
        region : pymupdf.Rect
            Region whose drawing density is being measured.

        Returns
        -------
        int
            Number of drawing paths whose bounding box intersects the region.

        """
        import pymupdf

        try:
            return sum(1 for drawing in page.get_drawings() if pymupdf.Rect(drawing["rect"]).intersects(region))
        except Exception:
            return 0

    def _region_text_as_paragraph(
        self, page: "pymupdf.Page", region: "pymupdf.Rect", page_num: int
    ) -> AstParagraph | None:
        """Return a region's text as a paragraph, for regions rejected as tables.

        Text inside a detected table's bbox is removed from the ordinary text blocks so
        it is not emitted twice, and that removal happens *before* the table is validated.
        So a rejection path that simply returns ``None`` does not fall back to prose --
        it deletes the region's text outright. Rejecting degenerate grids this way cost
        256 words of real body text across the corpus.

        Returns
        -------
        AstParagraph or None
            The region's text as a paragraph, or ``None`` if the region holds no text.

        """
        text = clipped_textbox(page, region)
        if not text or not text.strip():
            return None

        # clipped_textbox is raw extraction: it returns the glyphs with their printed line
        # breaks, and this is the only path into the AST that does not pass through
        # dehyphenate_blocks(). Without this a word broken across a line survives as two
        # fragments and the whole word is absent from the output -- "Coroman-" + "del" meant
        # "Coromandel" appeared nowhere at all. The line break is consumed with the hyphen,
        # so the join below does not put a space back between the halves.
        if self.options.merge_hyphenated_words:
            text = dehyphenate_text(text)

        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        if not lines:
            return None

        return AstParagraph(
            content=[Text(content=" ".join(lines))],
            source_location=SourceLocation(format="pdf", page=page_num + 1),
        )

    def _parse_markdown_table_row(self, row_line: str) -> list[str]:
        """Parse a markdown table row into cell contents.

        Parameters
        ----------
        row_line : str
            Markdown table row (e.g., "| cell1 | cell2 |")

        Returns
        -------
        list of str
            Cell contents

        """
        # Remove leading/trailing pipes and split, respecting escaped pipes (\|)
        row_line = row_line.strip()
        if row_line.startswith("|"):
            row_line = row_line[1:]
        if row_line.endswith("|"):
            row_line = row_line[:-1]

        # The AST holds unescaped text: restore the placeholder as a bare "|" and let the
        # renderer re-escape it. Keeping the backslash here would escape it a second time.
        escaped_pipe_placeholder = "\x00PIPE\x00"
        row_line_escaped = row_line.replace(r"\|", escaped_pipe_placeholder)
        cells = [cell.replace(escaped_pipe_placeholder, "|").strip() for cell in row_line_escaped.split("|")]
        return cells

    def _collect_image_exclusion_regions(self, layout: "PageLayoutPredictions | None") -> list[Any]:
        """Return regions where images should be skipped during extraction.

        Currently only the layout model's ``page-header`` and ``page-footer``
        predictions are used. Returns an empty list when layout analysis is
        unavailable or the option is disabled, leaving image extraction
        unchanged.
        """
        if layout is None or not self.options.filter_header_footer_images:
            return []
        import pymupdf

        regions: list[Any] = []
        for label in ("page-header", "page-footer"):
            for pred in layout.get_predictions_by_label(label):
                regions.append(pymupdf.Rect(pred.x0, pred.y0, pred.x1, pred.y1))
        return regions

    @staticmethod
    def _is_bound_caption_block(block: dict, bound_captions: list[str]) -> bool:
        """Return True if this text block is the body copy of a bound figure caption.

        The caption's text is real page text, so after binding it to an ``Image`` it
        would otherwise also be emitted as an ordinary paragraph, and every caption
        would appear twice in the output. A block is the body copy only when its
        entire whitespace-normalized text sits inside a bound caption -- a block
        holding the caption *plus* other prose keeps its place, because dropping it
        would take that prose with it.

        Parameters
        ----------
        block : dict
            PyMuPDF text block
        bound_captions : list of str
            Whitespace-normalized captions bound to this page's images

        Returns
        -------
        bool
            True when the block should be suppressed as a duplicate

        """
        if block.get("type") != 0:
            return False
        text = " ".join(span.get("text", "") for line in block.get("lines", []) for span in line.get("spans", []))
        # The floor keeps a short cross-reference ("Figure 1.") standing alone in the
        # body from being mistaken for the caption fragment it is contained in.
        if len(" ".join(text.split())) < PDF_CAPTION_DEDUP_MIN_CHARS:
            return False
        # See _caption_comparison_key: the two extraction routes disagree on
        # ligatures, inserted spaces, and wrap hyphens; comparing what they agree
        # on is what lets the body copy be recognized at all (#410).
        key = _caption_comparison_key(text)
        return any(key in _caption_comparison_key(caption) for caption in bound_captions)

    def _create_image_node(self, img_info: dict, page_num: int) -> AstParagraph | None:
        """Create an image node from image info.

        Parameters
        ----------
        img_info : dict
            Image information dict with 'result' (process_attachment result) and 'caption' keys
        page_num : int
            Page number for source tracking

        Returns
        -------
        AstParagraph or None
            Paragraph containing the image node

        """
        try:
            # Get the process_attachment result
            result = img_info.get("result", {})

            # Convert result to Image node using helper
            img_node = attachment_result_to_image_node(result, fallback_alt_text="Image")

            if img_node:
                # The detected caption is visible page content set beside the figure,
                # not a substitute for it -- and a captioned image is always emitted
                # inside a Figure container now, so the caption rides on
                # ``Figure.caption`` rather than here (#338). Setting it on the
                # image too would render the caption twice.
                # Add source location
                img_node.source_location = SourceLocation(format="pdf", page=page_num + 1)

                # Wrap in paragraph
                return AstParagraph(content=[img_node], source_location=SourceLocation(format="pdf", page=page_num + 1))

            return None

        except Exception as e:
            logger.debug(f"Failed to create image node: {e}")
            return None

    def _filter_headers_footers(self, blocks: list[dict], page: "pymupdf.Page") -> list[dict]:
        """Filter out text blocks in header/footer zones.

        Parameters
        ----------
        blocks : list of dict
            Text blocks from PyMuPDF
        page : pymupdf.Page
            PDF page

        Returns
        -------
        list of dict
            Filtered blocks excluding headers and footers

        """
        if not self.options.trim_headers_footers:
            return blocks

        page_height = page.rect.height
        header_zone = self.options.header_height
        footer_zone = self.options.footer_height

        filtered_blocks = []
        for block in blocks:
            bbox = block.get("bbox")
            if not bbox:
                filtered_blocks.append(block)
                continue

            # A block must lie ENTIRELY inside the zone to be furniture. Testing only the
            # near edge -- does the block *start* above header_height -- deletes any body
            # paragraph that happens to begin near the top margin, and takes the rest of
            # the page with it: on an FCC filing whose body opened 4pt below the running
            # head, the whole opening paragraph of every page was dropped. Real furniture
            # is always fully contained, because the zone is derived from its own far edge.
            if header_zone > 0 and bbox[3] <= header_zone:
                continue  # Skip this block

            if footer_zone > 0 and bbox[1] >= (page_height - footer_zone):
                continue  # Skip this block

            filtered_blocks.append(block)

        return filtered_blocks

    def _is_list_item_paragraph(self, paragraph: AstParagraph) -> bool:
        """Check if paragraph starts with a list marker.

        Parameters
        ----------
        paragraph : AstParagraph
            Paragraph to check

        Returns
        -------
        bool
            True if paragraph starts with list marker

        """
        if not paragraph.content:
            return False

        # The liberal reader, because this only ever *protects* a paragraph from being
        # merged into its neighbour -- it creates nothing. Answering it conservatively let
        # consecutive numbered items merge back into a single paragraph, which is how a
        # whole ordered list came out on one line.
        is_list, _ = self._is_valid_list_marker(_opening_line_text(paragraph.content))
        return is_list

    def _determine_list_level_from_x(self, x_coord: float, x_levels: dict[int, float]) -> int:
        """Determine the nesting level of a list item based on its x-coordinate.

        Parameters
        ----------
        x_coord : float
            The x-coordinate of the list item
        x_levels : dict
            Level number -> the x-coordinate anchoring it. Mutated in place as new
            indents are seen; the caller clears it whenever a non-list node ends the run.

        Returns
        -------
        int
            The nesting level: an ordering key, not a count. A larger ``x`` always
            yields a larger level, but the numbers are neither 0-based nor contiguous.
            See the notes.

        Notes
        -----
        X-coordinates within 5 points of an established indent are that indent's level.

        Levels used to be handed out in *arrival* order (``len(x_levels)``), so the first
        item seen was level 0 whatever its indent, and each new indent after it was one
        level deeper whether it lay to the right or to the left. A nested list that
        continues at the top of a column or page begins on a sub-bullet -- routine in
        two-column typesetting -- so the sub-bullet took level 0 and the genuine
        top-level bullet after it took level 1. The caller reads a larger level as
        "deeper", so it nested the parent underneath its own child.

        An indent shallower than everything seen so far consequently has to be able to
        become a shallower *level* after the fact, and one arriving between two known
        indents has to be able to land between their levels. Renumbering would strand
        the level numbers the caller has already recorded on its list stack, so instead
        the numbers are only ever compared, never counted: a shallower indent takes
        ``min(...) - LEVEL_STRIDE``, a deeper one ``max(...) + LEVEL_STRIDE``, and one in
        between takes the midpoint of its two neighbours' levels. The stride is what
        leaves room for that midpoint; ten successive insertions into the same gap
        exhaust it, at which point the indent joins the nearer of the two rather than
        colliding with one of them.

        Known limitation, deliberately out of scope: this is blind to columns. The first
        item of a right-hand column sits at a larger ``x`` than anything in the left one,
        so it still reads as deeper. Fixing that needs to know which column each item
        came from, which this helper is not given.

        """
        LEVEL_THRESHOLD = 5.0
        LEVEL_STRIDE = 1024

        if not x_levels:
            x_levels[0] = x_coord
            return 0

        # Compare against the *nearest* indent rather than the first one within
        # tolerance: with several levels established, "first match wins" is arrival order
        # again, by way of the dict's insertion order.
        nearest_level = min(x_levels, key=lambda level: abs(x_coord - x_levels[level]))
        if abs(x_coord - x_levels[nearest_level]) < LEVEL_THRESHOLD:
            return nearest_level

        if x_coord > max(x_levels.values()):
            new_level = max(x_levels) + LEVEL_STRIDE
        elif x_coord < min(x_levels.values()):
            new_level = min(x_levels) - LEVEL_STRIDE
        else:
            # Between two established indents. Level order tracks indent order, so the
            # neighbouring levels can be picked out by number.
            below = max(level for level, level_x in x_levels.items() if level_x < x_coord)
            above = min(level for level, level_x in x_levels.items() if level_x > x_coord)
            new_level = (below + above) // 2
            if new_level in (below, above):
                return nearest_level

        x_levels[new_level] = x_coord
        return new_level

    def _apply_list_indentation(
        self, paragraph: AstParagraph, current_bbox: tuple[float, float, float, float], first_list_item_x: float
    ) -> None:
        """Store bbox information for later use in nested list detection.

        Parameters
        ----------
        paragraph : AstParagraph
            Paragraph to process
        current_bbox : tuple
            Current bounding box
        first_list_item_x : float
            X-coordinate of first list item (unused, kept for API compatibility)

        Notes
        -----
        This method no longer adds manual spacing. List nesting is now handled
        structurally in _convert_paragraphs_to_lists using x-coordinate data.

        """
        # No-op: nesting is now handled structurally, not via spacing
        pass

    def _should_merge_with_accumulated(
        self,
        current_bbox: tuple[float, float, float, float] | None,
        last_bbox_bottom: float | None,
        accumulated_content: list[Node],
        is_list_item: bool,
        last_was_list_item: bool,
        merge_threshold: float,
        current_metadata: dict | None = None,
        last_metadata: dict | None = None,
    ) -> bool:
        """Determine if current paragraph should merge with accumulated content.

        Parameters
        ----------
        current_bbox : tuple or None
            Current paragraph bounding box
        last_bbox_bottom : float or None
            Bottom y-coordinate of last paragraph
        accumulated_content : list of Node
            Accumulated content so far
        is_list_item : bool
            Whether current paragraph is a list item
        last_was_list_item : bool
            Whether last paragraph was a list item
        merge_threshold : float
            Threshold for vertical gap merging
        current_metadata : dict or None, optional
            Metadata from current paragraph's source location
        last_metadata : dict or None, optional
            Metadata from last paragraph's source location

        Returns
        -------
        bool
            True if should merge

        """
        # Check metadata for list markers first (more reliable than text-based detection)
        current_is_list = (current_metadata and current_metadata.get("is_list_item", False)) or is_list_item
        last_is_list = (last_metadata and last_metadata.get("is_list_item", False)) or last_was_list_item

        # A list item never merges into what came before it: two items are two items,
        # and an item opening under a paragraph starts its own block.
        if current_is_list:
            return False

        # If bbox information is missing, don't merge to be safe -- and a continuation
        # of a list item is admitted on its geometry alone, so without geometry it stays
        # where the unconditional rule used to put it.
        if not current_bbox or last_bbox_bottom is None:
            return not accumulated_content and not last_is_list

        # Must have accumulated content and valid bbox info
        if not accumulated_content:
            return not last_is_list

        # Calculate vertical gap
        current_bbox_top = current_bbox[1]
        vertical_gap = current_bbox_top - last_bbox_bottom

        # A list item's own wrapped lines are not new paragraphs (#442). The rule here
        # used to refuse any merge touching a list item, which strands every line a long
        # item wraps onto -- and a numbered bibliography is a list of long items, so a
        # reference's title and journal arrive as separate blocks from its authors.
        #
        # Measured over 8,183 merge decisions on twelve dev-corpus articles, 151 of the
        # 325 blocks that end mid-sentence are stranded this way, and 98% of them sit
        # 0.5-3.8pt below the item -- the same geometry as the wraps this method already
        # merges (median 1.98pt, 95th percentile 3.67pt). They are indistinguishable from
        # an ordinary wrap except for the list item above them.
        #
        # What is NOT admitted is a negative gap. For ordinary prose a continuation above
        # its predecessor is the foot of one column meeting the head of the next, and
        # joining them is usually right; under a list item it is 8 cases of a page or
        # column break -- one of them 287pt -- where "just below" means nothing.
        if last_is_list:
            return 0.0 <= vertical_gap < merge_threshold

        # Only merge if gap is small
        return vertical_gap < merge_threshold

    def _merge_rotated_paragraphs(self, nodes: list[Node]) -> list[Node]:
        """Merge consecutive paragraphs that came from same-direction rotated runs.

        Each rotated paragraph is tagged with its rotation key in
        ``source_location.metadata['rotated']`` by :meth:`_flush_rotated_text`.
        This pass joins adjacent paragraphs with the same key (which can be
        produced by separate PyMuPDF blocks within a column) and appends the
        rotation marker once per merged run when ``annotate_rotated_text`` is on.
        """
        if not nodes:
            return nodes

        merged: list[Node] = []
        pending_text: list[str] = []
        pending_key: str | None = None
        pending_loc: SourceLocation | None = None

        def flush() -> None:
            nonlocal pending_text, pending_key, pending_loc
            if pending_text:
                combined = " ".join(pending_text)
                if self.options.annotate_rotated_text and pending_key:
                    combined += format_rotation_note(pending_key)
                merged.append(AstParagraph(content=[Text(content=combined)], source_location=pending_loc))
            pending_text = []
            pending_key = None
            pending_loc = None

        for node in nodes:
            rot_key: str | None = None
            if isinstance(node, AstParagraph) and node.source_location and node.source_location.metadata:
                rot_key = node.source_location.metadata.get("rotated") or None

            if rot_key and isinstance(node, AstParagraph):
                text = "".join(c.content for c in node.content if isinstance(c, Text))
                if pending_key is not None and pending_key != rot_key:
                    flush()
                if pending_key is None:
                    pending_key = rot_key
                    pending_loc = node.source_location
                pending_text.append(text)
            else:
                flush()
                merged.append(node)
        flush()
        return merged

    def _merge_adjacent_paragraphs(self, nodes: list[Node]) -> list[Node]:
        """Merge consecutive paragraph nodes that should be combined.

        In multi-column layouts, PyMuPDF often creates separate blocks for each
        line of text. This results in many small paragraph nodes that should be
        merged into cohesive paragraphs. This method combines consecutive
        Paragraph nodes that have small vertical gaps (< 10 points), indicating
        they're part of the same logical paragraph.

        Parameters
        ----------
        nodes : list of Node
            List of AST nodes (paragraphs, headings, tables, etc.)

        Returns
        -------
        list of Node
            List of nodes with consecutive paragraphs merged

        Notes
        -----
        Only Paragraph nodes with small vertical gaps are merged. Paragraphs
        with larger gaps (>= 10 points) are kept separate. Headings, code blocks,
        tables, and other block-level elements act as natural paragraph boundaries.

        This method requires bbox information to be stored in SourceLocation.metadata['bbox'].
        If bbox information is not available, paragraphs without bbox are not merged.

        """
        if not nodes:
            return nodes

        MERGE_THRESHOLD = 5.0

        merged: list[Node] = []
        accumulated_content: list[Node] = []
        last_source_location: SourceLocation | None = None
        last_bbox_bottom: float | None = None
        last_was_list_item: bool = False
        last_metadata: dict | None = None
        first_list_item_x: float | None = None

        for node in nodes:
            if isinstance(node, AstParagraph):
                current_bbox = None
                current_metadata = None
                if node.source_location and node.source_location.metadata:
                    current_bbox = node.source_location.metadata.get("bbox")
                    current_metadata = node.source_location.metadata

                is_list_item = self._is_list_item_paragraph(node)

                # Handle list item indentation
                if is_list_item and current_bbox:
                    if first_list_item_x is None:
                        first_list_item_x = current_bbox[0]
                    self._apply_list_indentation(node, current_bbox, first_list_item_x)

                # Determine if we should merge
                should_merge = self._should_merge_with_accumulated(
                    current_bbox,
                    last_bbox_bottom,
                    accumulated_content,
                    is_list_item,
                    last_was_list_item,
                    MERGE_THRESHOLD,
                    current_metadata,
                    last_metadata,
                )

                if should_merge:
                    # Merge: accumulate content. A word hyphenated across the seam --
                    # the last line of one PyMuPDF block continuing in the next, which
                    # dehyphenate_blocks cannot see because it works within a block --
                    # is joined here under the same rules, instead of surviving as
                    # "transcrip- tion" (#405).
                    if accumulated_content and node.content:
                        if not self._join_hyphenated_seam(accumulated_content, node.content):
                            accumulated_content.append(Text(content=" "))
                    accumulated_content.extend(node.content)
                    if last_source_location is None:
                        last_source_location = node.source_location
                    if current_bbox:
                        last_bbox_bottom = current_bbox[3]
                    last_was_list_item = is_list_item
                    last_metadata = current_metadata
                else:
                    # Don't merge: flush accumulated content
                    if accumulated_content:
                        merged.append(AstParagraph(content=accumulated_content, source_location=last_source_location))
                    accumulated_content = list(node.content)
                    last_source_location = node.source_location
                    last_bbox_bottom = current_bbox[3] if current_bbox else None
                    last_was_list_item = is_list_item
                    last_metadata = current_metadata
                    if not is_list_item:
                        first_list_item_x = None
            else:
                # Non-paragraph node: flush and reset
                if accumulated_content:
                    merged.append(AstParagraph(content=accumulated_content, source_location=last_source_location))
                    accumulated_content = []
                    last_source_location = None
                    last_bbox_bottom = None
                    last_was_list_item = False
                    last_metadata = None
                    first_list_item_x = None
                merged.append(node)

        # Flush remaining content
        if accumulated_content:
            merged.append(AstParagraph(content=accumulated_content, source_location=last_source_location))

        return merged

    def _join_hyphenated_seam(self, accumulated_content: list[Node], incoming: list[Node]) -> bool:
        """Join a word hyphenated across two merged paragraphs, if one is split there.

        Returns True when the seam was a hyphenated line break -- the caller must then
        *not* insert the joining space. The hyphen and capitalization rules are
        :func:`dehyphenate_blocks`'s exactly: an uppercase continuation keeps the
        hyphen ("Anglo-" + "Saxon"), a lowercase one drops it ("transcrip-" + "tion").

        Parameters
        ----------
        accumulated_content : list of Node
            Content accumulated so far; its last `Text` node may end with a hyphen.
        incoming : list of Node
            The next paragraph's content; its first `Text` node may continue the word.

        Returns
        -------
        bool
            True if the hyphen seam was joined.

        """
        from all2md.parsers._pdf_ocr import _CONTINUATION_RE, _LINE_END_HYPHEN_RE

        if not self.options.merge_hyphenated_words:
            return False
        last = accumulated_content[-1]
        first = incoming[0]
        if not isinstance(last, Text) or not isinstance(first, Text):
            return False
        hyphen = _LINE_END_HYPHEN_RE.search(last.content)
        continuation = _CONTINUATION_RE.match(first.content.lstrip())
        if not hyphen or not continuation:
            return False
        joiner = "-" if continuation.group(1)[0].isupper() else ""
        accumulated_content[-1] = Text(content=_LINE_END_HYPHEN_RE.sub(rf"\1{joiner}", last.content))
        if first.content != first.content.lstrip():
            incoming[0] = Text(content=first.content.lstrip())
        return True

    @staticmethod
    def _is_valid_list_marker(text: str) -> tuple[bool, str | None]:
        """Check if text starts with a valid list marker.

        Parameters
        ----------
        text : str
            Text to check for list markers

        Returns
        -------
        tuple[bool, str | None]
            (is_list_item, list_type) where list_type is "ordered", "unordered", or None

        Notes
        -----
        This function is more conservative about detecting list markers to avoid false positives:
        - Letter "o" must be followed by a space to be treated as a marker (avoids "office", "online", etc.)
        - Numbered markers must be followed by space (avoids dates like "2024")

        """
        if not text:
            return False, None

        stripped = text.lstrip()
        if not stripped:
            return False, None

        first_char = stripped[0]

        # Check for bullet markers - but be careful with "o"
        # Include EN DASH (–, U+2013) and EM DASH (—, U+2014) which are commonly used in PDFs
        if first_char in ("-", "\u2013", "\u2014", "*", "+", "•", "◦", "▪", "▫"):
            return True, "unordered"

        # Special handling for lowercase "o" - only treat as marker if followed by space
        if first_char == "o":
            # Must have at least 2 characters and second must be space
            if len(stripped) >= 2 and stripped[1] == " ":
                return True, "unordered"
            else:
                return False, None

        # Check for numbered list markers (1. or 1) followed by space)
        # More robust: require space after marker to avoid matching dates/numbers
        match = re.match(r"^\s*(\d+)[\.\)]\s", text)
        if match:
            return True, "ordered"

        return False, None

    def _detect_list_marker(self, para: AstParagraph) -> tuple[bool, str | None]:
        """Detect if a paragraph is a list item and return its type.

        Parameters
        ----------
        para : AstParagraph
            The paragraph to check

        Returns
        -------
        tuple[bool, str | None]
            A tuple of (is_list_item, list_type) where list_type is
            "ordered", "unordered", or None

        """
        return self._is_valid_list_marker(_leading_inline_text(para.content))

    def _extract_list_item_x_coord(self, node: AstParagraph) -> float | None:
        """Extract x-coordinate from a paragraph's bbox metadata.

        Parameters
        ----------
        node : AstParagraph
            The paragraph node

        Returns
        -------
        float | None
            The x-coordinate if available, None otherwise

        """
        if node.source_location and node.source_location.metadata:
            bbox = node.source_location.metadata.get("bbox")
            if bbox and len(bbox) >= 1:
                return bbox[0]
        return None

    def _strip_list_marker(self, para: AstParagraph) -> list[Node]:
        """Remove list marker from paragraph content and return cleaned content.

        Parameters
        ----------
        para : AstParagraph
            The paragraph containing a list marker

        Returns
        -------
        list[Node]
            Content nodes with the list marker removed

        """
        full_text = _leading_inline_text(para.content)

        # Use the robust marker detection to validate this is actually a list item
        is_list, list_type = self._is_valid_list_marker(full_text)
        if not is_list:
            # Not a valid list marker, return content as-is
            return list(para.content)

        # Determine marker and strip it
        stripped = full_text.lstrip()
        marker_end = 0

        if list_type == "unordered":
            # Bullet marker - find where it ends (marker + space)
            marker_char = stripped[0]
            marker_end = full_text.index(marker_char) + 1
            # Skip following space if present
            if marker_end < len(full_text) and full_text[marker_end] == " ":
                marker_end += 1
        elif list_type == "ordered":
            # Numbered marker - use regex to find end
            match = re.match(r"^(\s*)(\d+[\.\)])\s", full_text)
            if match:
                marker_end = match.end()

        if marker_end <= 0:
            return list(para.content)

        # The marker may sit inside a wrapper and may straddle two nodes, so it is removed
        # by character count rather than by rewriting whichever node happens to be first.
        new_content, _ = _consume_leading_chars(para.content, marker_end)
        return new_content

    def _finalize_pending_lists(self, list_stack: list[tuple[str, int, list[ListItem]]], result: list[Node]) -> None:
        """Finalize all lists in the stack, nesting them properly.

        Parameters
        ----------
        list_stack : list[tuple[str, int, list[ListItem]]]
            Stack of (list_type, level, items) tuples
        result : list[Node]
            Result list to append finalized top-level list to

        """
        while len(list_stack) > 1:
            # Pop deeper list
            deeper_type, deeper_level, deeper_items = list_stack.pop()
            nested_list = List(ordered=(deeper_type == "ordered"), items=deeper_items, tight=True)

            # Add to parent's last item
            parent_items = list_stack[-1][2]
            if parent_items:
                parent_items[-1].children.append(nested_list)

        # Add the top-level list to results
        if list_stack:
            list_type, level, items = list_stack.pop()
            result.append(List(ordered=(list_type == "ordered"), items=items, tight=True))

    def _handle_empty_stack(
        self, list_stack: list[tuple[str, int, list[ListItem]]], list_type: str, level: int, item_node: ListItem
    ) -> None:
        """Handle adding a list item when stack is empty.

        Parameters
        ----------
        list_stack : list[tuple[str, int, list[ListItem]]]
            Stack of list tuples (will be empty when called)
        list_type : str
            Type of list ("ordered" or "unordered")
        level : int
            Nesting level
        item_node : ListItem
            The list item to add

        """
        list_stack.append((list_type, level, [item_node]))

    def _handle_deeper_nesting(
        self, list_stack: list[tuple[str, int, list[ListItem]]], list_type: str, level: int, item_node: ListItem
    ) -> None:
        """Handle adding a list item at a deeper nesting level.

        Parameters
        ----------
        list_stack : list[tuple[str, int, list[ListItem]]]
            Stack of list tuples
        list_type : str
            Type of list ("ordered" or "unordered")
        level : int
            Nesting level (greater than current stack top level)
        item_node : ListItem
            The list item to add

        """
        list_stack.append((list_type, level, [item_node]))

    def _handle_shallower_level(
        self,
        list_stack: list[tuple[str, int, list[ListItem]]],
        list_type: str,
        level: int,
        item_node: ListItem,
        result: list[Node],
    ) -> None:
        """Handle adding a list item at a shallower nesting level.

        Parameters
        ----------
        list_stack : list[tuple[str, int, list[ListItem]]]
            Stack of list tuples
        list_type : str
            Type of list ("ordered" or "unordered")
        level : int
            Nesting level (less than current stack top level)
        item_node : ListItem
            The list item to add
        result : list[Node]
            Result list for finalized lists

        """
        # Going back to shallower level - finalize deeper lists
        while list_stack and list_stack[-1][1] > level:
            popped_type, popped_level, popped_items = list_stack.pop()
            nested_list = List(ordered=(popped_type == "ordered"), items=popped_items, tight=True)

            # Add nested list to parent's last item
            if list_stack:
                parent_items = list_stack[-1][2]
                if parent_items:
                    parent_items[-1].children.append(nested_list)
            else:
                # Nothing shallower left to nest under. Reachable since
                # _determine_list_level_from_x learned to place a later, shallower indent
                # *below* the level the stack was opened at: the sub-bullet-first case,
                # where the run's own first item is a nested one. Its items have no parent
                # in this document -- the parent came before them, or not at all -- so the
                # list stands on its own. Dropping it here would delete them.
                result.append(nested_list)

        # Check if we're at the same level and type
        if list_stack and list_stack[-1][1] == level:
            if list_stack[-1][0] == list_type:
                # Same level and type - add item
                list_stack[-1][2].append(item_node)
            else:
                # Different type at same level - finalize old, start new
                old_type, old_level, old_items = list_stack.pop()
                result.append(List(ordered=(old_type == "ordered"), items=old_items, tight=True))
                list_stack.append((list_type, level, [item_node]))
        else:
            # Start new list at this level
            list_stack.append((list_type, level, [item_node]))

    def _handle_same_level(
        self,
        list_stack: list[tuple[str, int, list[ListItem]]],
        list_type: str,
        item_node: ListItem,
        result: list[Node],
        current_type: str,
        current_level: int,
    ) -> None:
        """Handle adding a list item at the same nesting level.

        Parameters
        ----------
        list_stack : list[tuple[str, int, list[ListItem]]]
            Stack of list tuples
        list_type : str
            Type of list ("ordered" or "unordered")
        item_node : ListItem
            The list item to add
        result : list[Node]
            Result list for finalized lists
        current_type : str
            Current list type from stack top
        current_level : int
            Current nesting level from stack top

        """
        if current_type == list_type:
            # Same type - add to current list
            list_stack[-1][2].append(item_node)
        else:
            # Different type at same level - finalize old, start new
            old_type, old_level, old_items = list_stack.pop()
            result.append(List(ordered=(old_type == "ordered"), items=old_items, tight=True))
            list_stack.append((list_type, current_level, [item_node]))

    def _convert_paragraphs_to_lists(self, nodes: list[Node]) -> list[Node]:
        """Convert paragraphs with list markers into List/ListItem structures with proper nesting.

        Parameters
        ----------
        nodes : list of Node
            AST nodes that may contain list marker paragraphs

        Returns
        -------
        list of Node
            Nodes with list paragraphs converted to nested List structures

        Notes
        -----
        Uses x-coordinate information from bbox metadata to determine nesting levels.
        Implements a stack-based algorithm to build properly nested list structures.

        """
        result: list[Node] = []
        list_stack: list[tuple[str, int, list[ListItem]]] = []
        x_levels: dict[int, float] = {}

        for node in nodes:
            if isinstance(node, AstParagraph):
                # Check if this is a list item
                is_list_item, list_type = self._detect_list_marker(node)

                if is_list_item and list_type:
                    # Extract x-coordinate and determine nesting level
                    x_coord = self._extract_list_item_x_coord(node)
                    level = 0
                    if x_coord is not None:
                        level = self._determine_list_level_from_x(x_coord, x_levels)

                    # Create list item with cleaned content
                    cleaned_content = self._strip_list_marker(node)
                    item_node = ListItem(children=[AstParagraph(content=cleaned_content)])

                    # Handle list stack based on level
                    if not list_stack:
                        self._handle_empty_stack(list_stack, list_type, level, item_node)
                    else:
                        current_type, current_level, current_items = list_stack[-1]

                        if level > current_level:
                            self._handle_deeper_nesting(list_stack, list_type, level, item_node)
                        elif level < current_level:
                            self._handle_shallower_level(list_stack, list_type, level, item_node, result)
                        else:
                            self._handle_same_level(
                                list_stack, list_type, item_node, result, current_type, current_level
                            )
                else:
                    # Not a list item - finalize any pending lists
                    self._finalize_pending_lists(list_stack, result)
                    x_levels.clear()
                    result.append(node)
            else:
                # Non-paragraph - finalize any pending lists
                self._finalize_pending_lists(list_stack, result)
                x_levels.clear()
                result.append(node)

        # Finalize any remaining lists
        self._finalize_pending_lists(list_stack, result)

        return result


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="pdf",
    extensions=[".pdf"],
    mime_types=["application/pdf"],
    magic_bytes=[
        (b"%PDF", 0),
    ],
    parser_class=PdfToAstConverter,
    renderer_class="all2md.renderers.pdf.PdfRenderer",
    renders_as_string=False,
    parser_required_packages=DEPS_PDF,
    renderer_required_packages=[("reportlab", "reportlab", ">=4.0.0")],
    optional_packages=[
        ("pytesseract", "pytesseract"),
        ("easyocr", "easyocr"),
        ("Pillow", "PIL"),
    ],
    import_error_message=("PDF conversion requires 'PyMuPDF'. Install with: pip install pymupdf"),
    parser_options_class=PdfOptions,
    renderer_options_class="all2md.options.pdf.PdfRendererOptions",
    description="Convert PDF documents to/from AST with table detection and optional OCR support",
    priority=10,
)
