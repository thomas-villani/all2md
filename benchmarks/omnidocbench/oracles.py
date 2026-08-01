"""Independent OmniDocBench annotation and all2md AST projections."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from html.parser import HTMLParser
from typing import Any, Callable, Iterable, Literal, Mapping, TypeVar

from all2md.ast.nodes import (
    Code,
    CodeBlock,
    Document,
    Heading,
    MathBlock,
    MathInline,
    Node,
    Paragraph,
    Table,
    Text,
    get_node_children,
)

# Every text-bearing category the dataset annotates. Scoring a filtered subset of the page
# inverts the metric: a parser that drops captions, headers, footers, page numbers,
# references, or footnotes would match a shorter ground truth and score higher for losing
# content. 63 pinned pages score 0.0 for perfect fidelity under a filtered projection.
TEXT_CATEGORIES = frozenset(
    {
        "code_txt",
        "equation_caption",
        "figure_caption",
        "figure_footnote",
        "footer",
        "header",
        "page_footnote",
        "page_number",
        "reference",
        "table_caption",
        "table_footnote",
        "text_block",
        "title",
    }
)
SUPPORTED_CATEGORIES = TEXT_CATEGORIES | frozenset({"table", "equation_isolated", "equation_inline"})
_WHITESPACE = re.compile(r"\s+")
# Deleting whitespace only next to ideographic text: CJK OCR inserts spurious inter-glyph
# spaces, but deleting Latin spaces makes total word-boundary loss score a perfect 1.0. The
# fullwidth block is included because NFKC folds those glyphs to ASCII, which would otherwise
# leave the spurious spaces beside fullwidth punctuation in place. Of the 743 pinned pages whose
# text contains such a glyph, padding it with spaces cost score on 588 before this widening and
# on none after it.
_IDEOGRAPHIC = "\u2e80-\u9fff\uac00-\ud7af\uf900-\ufaff\uff01-\uff60\uffe0-\uffe6"
_CJK_ADJACENT_WHITESPACE = re.compile(rf"(?<=[{_IDEOGRAPHIC}])\s+|\s+(?=[{_IDEOGRAPHIC}])")
# Content similarity at which an emitted block counts as *the* ground-truth block it matched,
# and so is allowed to vote on reading order. See `_reading_order_similarity`.
_IDENTIFIED_MATCH = 0.5
_ProjectionT = TypeVar("_ProjectionT")


@dataclass(frozen=True, slots=True)
class TableProjection:
    """Comparable table structure and content."""

    rows: int
    columns: int
    cell_slots: int
    text: str


@dataclass(frozen=True, slots=True)
class FormulaProjection:
    """Comparable formula content with its AST-level semantic kind."""

    kind: Literal["inline", "block"]
    content: str


@dataclass(frozen=True, slots=True)
class PageProjection:
    """Comparable document facts for one page."""

    text_blocks: tuple[str, ...]
    block_kinds: tuple[str, ...]
    tables: tuple[TableProjection, ...]
    formulas: tuple[FormulaProjection, ...]


@dataclass(frozen=True, slots=True)
class GroundTruthPage:
    """Validated supported facts projected directly from one annotation record."""

    page_id: str
    projection: PageProjection
    unscored_categories: Mapping[str, int]
    explicitly_ignored: int


class _TableHTMLParser(HTMLParser):
    """Extract table dimensions and cell text without accepting active markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows = 0
        self.columns = 0
        self.cell_slots = 0
        self._row_columns = 0
        self._in_row = False
        self._in_cell = False
        self._cell_text: list[str] = []
        self.text_cells: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "tr":
            self._in_row = True
            self._row_columns = 0
            self.rows += 1
        elif tag in {"td", "th"} and self._in_row:
            colspan = _positive_span(attributes.get("colspan"))
            rowspan = _positive_span(attributes.get("rowspan"))
            self._row_columns += colspan
            self.cell_slots += colspan * rowspan
            self._in_cell = True
            self._cell_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._in_cell:
            self.text_cells.append("".join(self._cell_text))
            self._cell_text = []
            self._in_cell = False
        elif tag == "tr" and self._in_row:
            self.columns = max(self.columns, self._row_columns)
            self._row_columns = 0
            self._in_row = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_text.append(data)


def _positive_span(value: str | None) -> int:
    try:
        span = int(value) if value is not None else 1
    except ValueError:
        return 1
    return max(1, span)


def normalize_text(value: str) -> str:
    """Normalize text for content comparison while ignoring layout whitespace."""
    # Run the substitution on both sides of NFKC: before it, fullwidth punctuation is still in
    # the ideographic class; after it, halfwidth forms have composed into it.
    collapsed = _CJK_ADJACENT_WHITESPACE.sub("", value)
    normalized = unicodedata.normalize("NFKC", collapsed).casefold()
    normalized = _CJK_ADJACENT_WHITESPACE.sub("", normalized)
    return _WHITESPACE.sub(" ", normalized).strip()


def normalize_formula(value: str) -> str:
    """Remove outer display delimiters without changing LaTeX semantics."""
    normalized = value.strip()
    for prefix, suffix in (("$$", "$$"), ("\\[", "\\]"), ("$", "$")):
        if normalized.startswith(prefix) and normalized.endswith(suffix):
            return normalized[len(prefix) : -len(suffix)].strip()
    return normalized


def _node_text(node: Node) -> str:
    if isinstance(node, (Text, Code)):
        return node.content
    children = get_node_children(node)
    if children:
        return " ".join(part for child in children if (part := _node_text(child)))
    content = getattr(node, "content", None)
    return content if isinstance(content, str) else ""


def _semantic_blocks(node: Node) -> Iterable[Node]:
    if isinstance(node, (Heading, Paragraph, CodeBlock, Table, MathBlock)):
        yield node
        return
    for child in get_node_children(node):
        yield from _semantic_blocks(child)


def _all_nodes(node: Node) -> Iterable[Node]:
    yield node
    for child in get_node_children(node):
        yield from _all_nodes(child)


def _ast_table(table: Table) -> TableProjection:
    rows = ([table.header] if table.header is not None else []) + list(table.rows)
    columns = max(
        (sum(max(1, cell.colspan) for cell in row.cells) for row in rows),
        default=0,
    )
    cell_slots = sum(max(1, cell.colspan) * max(1, cell.rowspan) for row in rows for cell in row.cells)
    text = " ".join(_node_text(cell) for row in rows for cell in row.cells)
    return TableProjection(len(rows), columns, cell_slots, text)


def project_ast(document: Document) -> PageProjection:
    """Project one all2md AST without routing through a renderer or second parser."""
    text_blocks: list[str] = []
    block_kinds: list[str] = []
    tables: list[TableProjection] = []
    formulas: list[FormulaProjection] = []

    for block in _semantic_blocks(document):
        if isinstance(block, Heading):
            block_kinds.append("title")
            text_blocks.append(_node_text(block))
        elif isinstance(block, (Paragraph, CodeBlock)):
            block_kinds.append("text_block")
            text_blocks.append(_node_text(block))
        elif isinstance(block, Table):
            block_kinds.append("table")
            tables.append(_ast_table(block))
            # Cell text belongs in the text stream on both sides. Otherwise a parser that fails
            # to build a Table node and emits the cells as a paragraph is punished harder than
            # one that deletes the table outright, on 317 of the 981 pinned pages.
            text_blocks.append(tables[-1].text)
        elif isinstance(block, MathBlock):
            block_kinds.append("equation_isolated")
            content, _ = block.get_preferred_representation("latex")
            formulas.append(FormulaProjection("block", content))

        if not isinstance(block, MathBlock):
            formulas.extend(
                FormulaProjection("inline", node.get_preferred_representation("latex")[0])
                for node in _all_nodes(block)
                if isinstance(node, MathInline)
            )

    return PageProjection(
        text_blocks=tuple(text_blocks),
        block_kinds=tuple(block_kinds),
        tables=tuple(tables),
        formulas=tuple(formulas),
    )


def _html_table(value: str) -> TableProjection:
    parser = _TableHTMLParser()
    parser.feed(value)
    parser.close()
    return TableProjection(
        rows=parser.rows,
        columns=parser.columns,
        cell_slots=parser.cell_slots,
        text=" ".join(parser.text_cells),
    )


def _annotation_page_id(record: Mapping[str, Any]) -> str:
    page_info = record.get("page_info")
    image_path = page_info.get("image_path") if isinstance(page_info, Mapping) else None
    if not isinstance(image_path, str) or not image_path:
        raise ValueError("annotation record has no page_info.image_path")
    filename = image_path.replace("\\", "/").rsplit("/", 1)[-1]
    return filename.rsplit(".", 1)[0]


def _annotation_inline_formulas(
    detection: Mapping[str, Any],
    *,
    page_id: str,
) -> tuple[list[FormulaProjection], int]:
    spans = detection.get("line_with_spans")
    if spans is None:
        return [], 0
    if not isinstance(spans, list):
        raise ValueError(f"annotation page {page_id!r} line_with_spans must be an array")

    formulas: list[FormulaProjection] = []
    ignored = 0
    for span in spans:
        if not isinstance(span, Mapping):
            raise ValueError(f"annotation page {page_id!r} contains a non-object line span")
        if span.get("ignore") is True:
            ignored += 1
            continue
        if span.get("category_type") != "equation_inline":
            continue
        latex = span.get("latex")
        if not isinstance(latex, str):
            raise ValueError(f"annotation page {page_id!r} inline formula has no LaTeX ground truth")
        formulas.append(FormulaProjection("inline", latex))
    return formulas, ignored


def _reading_rank(detection: Mapping[str, Any], record: Mapping[str, Any]) -> tuple[int, float]:
    """Rank one detection in reading order, placing unordered running content by geometry.

    Every ``header``, ``footer``, ``page_number``, and ``page_footnote`` detection in the pinned
    dataset carries ``order: null``. Sorting those last put running content after the body, which
    made dropping a header score higher than emitting it in its true position. A category-only
    rank is not enough: about one page number in seven sits at the top of the page.
    """
    order = detection.get("order")
    if isinstance(order, int) and not isinstance(order, bool):
        return (1, float(order))
    page_info = record.get("page_info")
    raw_height = page_info.get("height") if isinstance(page_info, Mapping) else None
    height = float(raw_height) if isinstance(raw_height, (int, float)) and raw_height else 1.0
    poly = detection.get("poly")
    vertical = [float(value) for value in poly[1::2]] if isinstance(poly, list) and poly else [0.0]
    centre = (min(vertical) + max(vertical)) / 2 / height
    return (0 if centre < 0.5 else 2, centre)


def project_annotation(record: Mapping[str, Any]) -> GroundTruthPage:
    """Project supported facts directly from one OmniDocBench annotation record."""
    page_id = _annotation_page_id(record)
    detections = record.get("layout_dets")
    if not isinstance(detections, list):
        raise ValueError(f"annotation page {page_id!r} has no layout_dets array")

    ordered: list[tuple[tuple[int, float], int, Mapping[str, Any]]] = []
    unscored: Counter[str] = Counter()
    explicitly_ignored = 0
    for position, raw in enumerate(detections):
        if not isinstance(raw, Mapping):
            raise ValueError(f"annotation page {page_id!r} contains a non-object layout item")
        if raw.get("ignore") is True:
            explicitly_ignored += 1
            continue
        category = raw.get("category_type")
        if not isinstance(category, str):
            raise ValueError(f"annotation page {page_id!r} has a layout item without category_type")
        if category not in SUPPORTED_CATEGORIES:
            unscored[category] += 1
        ordered.append((_reading_rank(raw, record), position, raw))

    text_blocks: list[str] = []
    block_kinds: list[str] = []
    tables: list[TableProjection] = []
    formulas: list[FormulaProjection] = []
    for _, _, detection in sorted(ordered):
        category = detection["category_type"]
        if category in TEXT_CATEGORIES:
            text = detection.get("text")
            if not isinstance(text, str):
                raise ValueError(f"annotation page {page_id!r} {category} has no text")
            text_blocks.append(text)
            block_kinds.append("title" if category == "title" else "text_block")
        elif category == "table":
            html = detection.get("html")
            if not isinstance(html, str) or not html:
                raise ValueError(f"annotation page {page_id!r} table has no HTML ground truth")
            tables.append(_html_table(html))
            block_kinds.append("table")
            text_blocks.append(tables[-1].text)
        elif category == "equation_isolated":
            latex = detection.get("latex")
            if not isinstance(latex, str):
                raise ValueError(f"annotation page {page_id!r} formula has no LaTeX ground truth")
            formulas.append(FormulaProjection("block", latex))
            block_kinds.append("equation_isolated")
        elif category == "equation_inline":
            latex = detection.get("latex")
            if not isinstance(latex, str):
                raise ValueError(f"annotation page {page_id!r} inline formula has no LaTeX ground truth")
            formulas.append(FormulaProjection("inline", latex))

        # A CodeBlock holds a plain string, so an inline equation inside code cannot be
        # represented in any AST; harvesting it would create ground truth nothing can match.
        if category == "code_txt":
            continue
        inline_formulas, ignored_spans = _annotation_inline_formulas(detection, page_id=page_id)
        formulas.extend(inline_formulas)
        explicitly_ignored += ignored_spans

    return GroundTruthPage(
        page_id=page_id,
        projection=PageProjection(
            text_blocks=tuple(text_blocks),
            block_kinds=tuple(block_kinds),
            tables=tuple(tables),
            formulas=tuple(formulas),
        ),
        unscored_categories=dict(sorted(unscored.items())),
        explicitly_ignored=explicitly_ignored,
    )


def _edit_distance(left: str, right: str) -> int:
    """Return exact Levenshtein distance with a bit-parallel Unicode pattern."""
    if len(left) > len(right):
        left, right = right, left
    if not left:
        return len(right)

    character_masks: dict[str, int] = {}
    for index, character in enumerate(left):
        character_masks[character] = character_masks.get(character, 0) | (1 << index)

    positive = ~0
    negative = 0
    score = len(left)
    highest = 1 << (len(left) - 1)
    for character in right:
        matching = character_masks.get(character, 0)
        vertical = matching | negative
        horizontal = (((matching & positive) + positive) ^ positive) | matching
        positive_horizontal = negative | ~(horizontal | positive)
        negative_horizontal = positive & horizontal
        if positive_horizontal & highest:
            score += 1
        elif negative_horizontal & highest:
            score -= 1
        positive_horizontal = (positive_horizontal << 1) | 1
        negative_horizontal <<= 1
        positive = negative_horizontal | ~(vertical | positive_horizontal)
        negative = positive_horizontal & vertical
    return score


def _string_similarity(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return 1.0 - _edit_distance(left, right) / max(len(left), len(right))


def content_similarity(expected: str, actual: str) -> float:
    """Return normalized character-sequence similarity in ``[0, 1]``."""
    return _string_similarity(normalize_text(expected), normalize_text(actual))


def _sequence_similarity(expected: tuple[str, ...], actual: tuple[str, ...]) -> float:
    if not expected and not actual:
        return 1.0
    if not expected or not actual:
        return 0.0
    previous = list(range(len(actual) + 1))
    for expected_item in expected:
        current = [previous[0] + 1]
        for index, actual_item in enumerate(actual, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[index] + 1,
                    previous[index - 1] + (expected_item != actual_item),
                )
            )
        previous = current
    distance = previous[-1]
    return 1.0 - distance / max(len(expected), len(actual))


def _count_similarity(expected: int, actual: int) -> float:
    if expected == actual == 0:
        return 1.0
    return 1.0 - abs(expected - actual) / max(expected, actual)


def _table_shape_similarity(expected: TableProjection, actual: TableProjection) -> float:
    return (
        _count_similarity(expected.rows, actual.rows)
        + _count_similarity(expected.columns, actual.columns)
        + _count_similarity(expected.cell_slots, actual.cell_slots)
    ) / 3


def _aligned_average(
    expected: tuple[_ProjectionT, ...],
    actual: tuple[_ProjectionT, ...],
    scorer: Callable[[_ProjectionT, _ProjectionT], float],
) -> float:
    denominator = max(len(expected), len(actual))
    if denominator == 0:
        return 1.0

    previous = [0.0] * (len(actual) + 1)
    for expected_item in expected:
        current = [0.0]
        for index, actual_item in enumerate(actual, 1):
            current.append(
                max(
                    previous[index],
                    current[-1],
                    previous[index - 1] + scorer(expected_item, actual_item),
                )
            )
        previous = current
    return previous[-1] / denominator


def _formula_similarity(expected: FormulaProjection, actual: FormulaProjection) -> float:
    if expected.kind != actual.kind:
        return 0.0
    return _string_similarity(
        normalize_formula(expected.content),
        normalize_formula(actual.content),
    )


def _align_pairs(
    expected: tuple[_ProjectionT, ...],
    actual: tuple[_ProjectionT, ...],
    weight: Callable[[_ProjectionT, _ProjectionT], float],
) -> list[tuple[int, int]]:
    """Return the order-preserving pairing that maximizes total match weight."""
    best = [[0.0] * (len(actual) + 1) for _ in range(len(expected) + 1)]
    for expected_index, expected_item in enumerate(expected, 1):
        for actual_index, actual_item in enumerate(actual, 1):
            best[expected_index][actual_index] = max(
                best[expected_index - 1][actual_index],
                best[expected_index][actual_index - 1],
                best[expected_index - 1][actual_index - 1] + weight(expected_item, actual_item),
            )

    pairs: list[tuple[int, int]] = []
    expected_index, actual_index = len(expected), len(actual)
    while expected_index and actual_index:
        current = best[expected_index][actual_index]
        if current == best[expected_index - 1][actual_index]:
            expected_index -= 1
        elif current == best[expected_index][actual_index - 1]:
            actual_index -= 1
        else:
            pairs.append((expected_index - 1, actual_index - 1))
            expected_index -= 1
            actual_index -= 1
    pairs.reverse()
    return pairs


def _table_similarities(
    expected: tuple[TableProjection, ...],
    actual: tuple[TableProjection, ...],
) -> tuple[float, float]:
    """Score table structure and content through one shared table alignment."""
    denominator = max(len(expected), len(actual))
    if denominator == 0:
        return 1.0, 1.0

    def composite(left: TableProjection, right: TableProjection) -> float:
        return (_table_shape_similarity(left, right) + content_similarity(left.text, right.text)) / 2

    structure = 0.0
    content = 0.0
    for expected_index, actual_index in _align_pairs(expected, actual, composite):
        expected_table = expected[expected_index]
        actual_table = actual[actual_index]
        structure += _table_shape_similarity(expected_table, actual_table)
        content += content_similarity(expected_table.text, actual_table.text)
    return structure / denominator, content / denominator


def _locate(haystack: str, needle: str) -> tuple[int, float]:
    """Return where ``needle`` best matches inside ``haystack`` and how much of it aligned.

    The fraction counts every aligned character, not just the longest unbroken run. Sporadic
    OCR damage fragments a block into many short runs without moving it, and scoring only the
    longest run made a substitution as ordinary as ``o`` to ``0`` look like a block that had
    gone missing. The alignment is monotonic, so the fragments cannot come from scattered
    coincidences all over the page.

    Position is taken from the longest run, offset by where that run sits inside the needle, so
    it is where the block *starts* rather than where its most recognizable part does.
    """
    matcher = SequenceMatcher(None, haystack, needle, autojunk=False)
    runs = [run for run in matcher.get_matching_blocks() if run.size]
    if not runs:
        return -1, 0.0
    anchor = max(runs, key=lambda run: run.size)
    return anchor.a - anchor.b, sum(run.size for run in runs) / len(needle)


def _reading_order_similarity(expected: PageProjection, actual: PageProjection) -> float:
    """Score how much of the page can be located, and whether it came out in order.

    Each ground-truth block is located inside the *concatenated* emitted text, and the order of
    those positions is compared with the order the annotation gives them. Position rather than
    block index is deliberate. Pairing emitted blocks against ground-truth blocks one-to-one
    measured segmentation as much as ordering, because a converter may split or merge blocks
    without moving a single word: text reproduced exactly but emitted as one block scored
    **0.0**, and splitting every block in two scored 0.44. On the pinned corpus that left 894 of
    981 pages at exactly zero, 128 of which scored 0.9 or better on text content -- a
    reading-order metric that reads zero for a page whose text is 90% right is measuring
    something other than reading order. Locating the blocks is blind to how the output was
    chunked and sensitive only to what moved.

    A block has to be found before it votes: below ``_IDENTIFIED_MATCH`` of its characters
    aligned it is not evidence of anything, and the score is scaled by the fraction that are
    found. That is what stops absent content from buying order credit -- ten blank paragraphs
    locate nothing and score 0, where an earlier version gave them a perfect 1.0.

    Block *kinds* are deliberately not part of this. They were, as a coverage factor, and that
    put segmentation back into the product through the other door: perfect text in perfect order
    emitted as one block instead of four scored 0.25, because four kinds became one. Structure
    is a real question and a separate one, scored on its own as ``block_structure_similarity``.
    """
    if not expected.text_blocks or not actual.text_blocks:
        return 0.0

    haystack = normalize_text(" ".join(actual.text_blocks))
    if not haystack:
        return 0.0

    positions: list[int] = []
    candidates = 0
    for block in expected.text_blocks:
        needle = normalize_text(block)
        if not needle:
            continue
        candidates += 1
        position, aligned = _locate(haystack, needle)
        if aligned >= _IDENTIFIED_MATCH:
            positions.append(position)

    if candidates == 0:
        return 0.0
    located = len(positions) / candidates
    if len(positions) < 2:
        return located
    pairs = len(positions) * (len(positions) - 1) // 2
    inversions = sum(
        1
        for left in range(len(positions))
        for right in range(left + 1, len(positions))
        if positions[left] > positions[right]
    )
    return located * (1.0 - inversions / pairs)


def score_page(expected: PageProjection, actual: PageProjection) -> dict[str, float]:
    """Score one AST projection directly against external annotation facts."""
    scores = {
        "text_content_similarity": content_similarity(
            " ".join(expected.text_blocks),
            " ".join(actual.text_blocks),
        ),
        "reading_order_similarity": _reading_order_similarity(expected, actual),
        # The sequence of block categories, on its own rather than folded into the order
        # score. It answers "did the page come apart into the right pieces", which is a
        # different question from "did the pieces come out in the right order" -- and eleven
        # text categories collapse to `text_block`, so it cannot answer the second one: fully
        # reversed output scores exactly 1.0 here on 153 of the 981 pinned pages, and any
        # permutation is free on the 113 pages with a single repeated kind.
        "block_structure_similarity": _sequence_similarity(expected.block_kinds, actual.block_kinds),
    }
    if expected.tables or actual.tables:
        structure, content = _table_similarities(expected.tables, actual.tables)
        scores["table_structure_similarity"] = structure
        scores["table_content_similarity"] = content
    if expected.formulas or actual.formulas:
        scores["formula_presence_accuracy"] = float(bool(expected.formulas) == bool(actual.formulas))
        scores["formula_content_similarity"] = _aligned_average(
            expected.formulas,
            actual.formulas,
            _formula_similarity,
        )
    return scores
