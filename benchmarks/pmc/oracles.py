"""Project JATS article ground truth into the shape the OmniDocBench oracle already scores.

The metric definitions are **not** duplicated here. `benchmarks.omnidocbench.oracles` owns
them, and every one carries a calibration story that took a corpus to settle -- what counts
as text, why block kinds are scored apart from reading order, why locating blocks beats
pairing them. Reusing `score_page` means the two lanes are directly comparable: the same
number means the same thing on a raster page and on a born-digital one.

What is new here is only the ground-truth side. JATS is publisher markup, not page
annotation, so this module answers two questions the raster lane never had to ask.

**What does the PDF actually render?** JATS holds material that never reaches the page
(processing metadata, structured bibliographic scalars) and omits material the page carries
(running heads, folios). Neither can be fixed, so `coverage` reports the ratio of projected
ground-truth words to PDF words per article, and a caller that does not look at it is
scoring against an unknown denominator.

**Structured citations do not round-trip.** Two thirds of this corpus's references are
``<element-citation>``: surname, year, source and page range as separate fields with no
rendered punctuation between them. Their text is projected in field order, which is close
to the rendered string but never equal to it. Reference-heavy articles therefore carry a
noise floor that is a property of JATS, not of the parser.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from benchmarks.omnidocbench.oracles import PageProjection, TableProjection, normalize_text

#: Elements whose subtree never reaches the rendered page. Skipped whole, so nothing inside
#: can leak into the text stream through a descendant rule.
SKIPPED = frozenset(
    {
        "processing-meta",
        "custom-meta-group",
        "journal-meta",
        "article-id",
        "article-categories",
        "history",
        "pub-date",
        "volume",
        "issue",
        "fpage",
        "lpage",
        "elocation-id",
        "object-id",
        "counts",
        "funding-group",
        "graphic",
        "media",
        "inline-graphic",
        "alt-text",
        "long-desc",
    }
)

#: Elements that become one ground-truth block, mapped to the block kind the shared oracle
#: scores. Encountering one ends the walk of that subtree: its whole text is the block.
BLOCKS: dict[str, str] = {
    "article-title": "title",
    "subtitle": "title",
    "trans-title": "title",
    "title": "title",
    "contrib-group": "text_block",
    "aff": "text_block",
    "author-notes": "text_block",
    "kwd-group": "text_block",
    "copyright-statement": "text_block",
    "license": "text_block",
    "p": "text_block",
    "disp-formula": "text_block",
    "disp-quote": "text_block",
    "def-item": "text_block",
    "speech": "text_block",
    "verse-group": "text_block",
    "statement": "text_block",
    "fn": "text_block",
    "supplementary-material": "text_block",
    "ref": "text_block",
    "fig": "text_block",
    "table-wrap": "table",
}

#: Containers walked through rather than emitted, listed so that an unrecognized element is
#: a visible gap rather than silent text loss. Anything not skipped, not a block, and not
#: here still recurses -- this set only documents the expected ones.
_CONTAINERS = frozenset(
    {
        "article",
        "front",
        "article-meta",
        "title-group",
        "abstract",
        "trans-abstract",
        "permissions",
        "body",
        "sec",
        "back",
        "ack",
        "app",
        "app-group",
        "glossary",
        "def-list",
        "ref-list",
        "fn-group",
        "notes",
        "boxed-text",
        "list",
        "list-item",
        "floats-group",
        "sub-article",
        "response",
    }
)


@dataclass(frozen=True, slots=True)
class JatsBlock:
    """One rendered block of an article, in document order.

    Attributes
    ----------
    kind : str
        Block kind in the shared oracle's vocabulary: ``title``, ``text_block``, ``table``.
    text : str
        Rendered text of the block. For a table this is its cell text, matching how the
        shared oracle puts table content into the text stream on both sides.
    caption : str
        Table or figure caption, emitted as its own block by `to_projection`. Empty
        elsewhere.
    table : TableProjection or None
        Structure and content of a ``<table-wrap>``'s table, when it has one.

    """

    kind: str
    text: str
    caption: str = ""
    table: TableProjection | None = None


def _tag(element: Any) -> str:
    return element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""


def _all_text(element: Any) -> str:
    """Return every rendered character under an element, joined by spaces.

    Joined, never concatenated: concatenation fuses ``<label>Table 2</label>`` onto the
    caption that follows it into a single bogus token, corrupting a token boundary at every
    element boundary. Tables have the most boundaries, so an earlier version of the
    alignment probe made them look unlocatable when they are not.
    """
    parts: list[str] = []

    def visit(node: Any) -> None:
        if _tag(node) in SKIPPED:
            return
        if node.text and node.text.strip():
            parts.append(node.text.strip())
        for child in node:
            visit(child)
            if child.tail and child.tail.strip():
                parts.append(child.tail.strip())

    visit(element)
    return " ".join(parts)


def _own_text(element: Any) -> str:
    """Return an element's text *excluding* nested elements that are blocks in their own right.

    JATS nests block material inside prose: a ``<table-wrap>`` or ``<disp-formula>`` sits
    inside the ``<p>`` that introduces it. Taking the paragraph's full text swallowed the
    table's caption and every cell into the paragraph, which fused three page objects into
    one string, deleted the table from the ground truth entirely, and -- because the fused
    block straddled the paragraph's page and the table's page -- placed it on the wrong one.
    """
    parts: list[str] = []

    def visit(node: Any, *, root: bool) -> None:
        tag = _tag(node)
        if tag in SKIPPED or (not root and tag in BLOCKS):
            return
        if node.text and node.text.strip():
            parts.append(node.text.strip())
        for child in node:
            visit(child, root=False)
            if child.tail and child.tail.strip():
                parts.append(child.tail.strip())

    visit(element, root=True)
    return " ".join(parts)


def _nested_blocks(element: Any) -> list[Any]:
    """Return block elements nested inside another block, in document order."""
    found: list[Any] = []

    def visit(node: Any) -> None:
        for child in node:
            tag = _tag(child)
            if tag in SKIPPED:
                continue
            if tag in BLOCKS:
                found.append(child)
            else:
                visit(child)

    visit(element)
    return found


def _positive_span(value: str | None) -> int:
    try:
        span = int(value) if value is not None else 1
    except ValueError:
        return 1
    return max(1, span)


def _jats_table(table: Any) -> TableProjection:
    """Project a JATS ``<table>`` with the same counting rules the HTML side uses.

    Deliberately mirrors `benchmarks.omnidocbench.oracles._TableHTMLParser` rather than
    inventing a second convention: a row count, the widest row by colspan, total occupied
    slots, and cell text in row-major order. A test pins the two against each other, because
    two table metrics that disagree would make the lanes incomparable in exactly the
    dimension this one exists to exercise.
    """
    rows = 0
    columns = 0
    cell_slots = 0
    cells: list[str] = []
    for row in table.iter():
        if _tag(row) != "tr":
            continue
        rows += 1
        row_columns = 0
        for cell in row:
            if _tag(cell) not in {"td", "th"}:
                continue
            colspan = _positive_span(cell.get("colspan"))
            row_columns += colspan
            cell_slots += colspan * _positive_span(cell.get("rowspan"))
            cells.append(_all_text(cell))
        columns = max(columns, row_columns)
    return TableProjection(rows=rows, columns=columns, cell_slots=cell_slots, text=" ".join(cells))


def _caption_of(element: Any) -> str:
    """Return a figure or table's label and caption as the page renders them together."""
    parts = [_all_text(child) for child in element if _tag(child) in {"label", "caption"} and _all_text(child)]
    return " ".join(parts)


def _table_wrap(element: Any) -> JatsBlock:
    table = next((child for child in element.iter() if _tag(child) == "table"), None)
    projection = _jats_table(table) if table is not None else None
    # Footnotes under the table are rendered beneath it, so they belong to the caption
    # stream rather than to the cell text, which is compared against Table nodes.
    foot = " ".join(_all_text(child) for child in element if _tag(child) == "table-wrap-foot")
    caption = " ".join(part for part in (_caption_of(element), foot) if part)
    if projection is None:
        # A table-wrap with no table renders as a graphic plus its caption: real page
        # content, but nothing a Table node could match. Scoring it as an empty table would
        # punish a parser for the absence of something that was never there.
        return JatsBlock(kind="text_block", text=caption, caption="")
    return JatsBlock(kind="table", text=projection.text, caption=caption, table=projection)


def walk(root: Any) -> Iterator[JatsBlock]:
    """Yield every rendered block of a parsed JATS article in document order.

    Parameters
    ----------
    root : xml.etree.ElementTree.Element
        Parsed JATS article element.

    Yields
    ------
    JatsBlock
        Blocks in the order the article declares them.

    """
    tag = _tag(root)
    if tag in SKIPPED:
        return
    kind = BLOCKS.get(tag)
    if kind == "table":
        yield _table_wrap(root)
        return
    if tag == "fig":
        caption = _caption_of(root)
        if caption:
            yield JatsBlock(kind="text_block", text=caption)
        return
    if kind is not None:
        # The element's own prose first, then whatever block material it contains. A page
        # renders a floated table after the sentence that introduces it, so this is also
        # the order the page shows them in.
        text = _own_text(root)
        if text:
            yield JatsBlock(kind=kind, text=text)
        for nested in _nested_blocks(root):
            yield from walk(nested)
        return
    for child in root:
        yield from walk(child)


def to_projection(blocks: tuple[JatsBlock, ...]) -> PageProjection:
    """Convert ground-truth blocks into the projection the shared oracle scores.

    A table contributes two entries to the text stream -- its caption and its cell text --
    matching the raster lane, where a caption is its own annotated detection and cell text
    is appended beside the table. Formulas are deliberately empty: this corpus records
    equations as MathML rather than LaTeX for 246 of 284 cases, and scoring MathML against
    an AST's LaTeX representation would measure a notation gap rather than the parser.

    Parameters
    ----------
    blocks : tuple[JatsBlock, ...]
        Ground-truth blocks in document order.

    Returns
    -------
    PageProjection
        Comparable facts for `benchmarks.omnidocbench.oracles.score_page`.

    """
    text_blocks: list[str] = []
    block_kinds: list[str] = []
    tables: list[TableProjection] = []
    for block in blocks:
        if block.caption:
            text_blocks.append(block.caption)
            block_kinds.append("text_block")
        if block.table is not None:
            tables.append(block.table)
            block_kinds.append("table")
            text_blocks.append(block.table.text)
        elif block.text:
            text_blocks.append(block.text)
            block_kinds.append(block.kind)
    return PageProjection(
        text_blocks=tuple(text_blocks),
        block_kinds=tuple(block_kinds),
        tables=tuple(tables),
        formulas=(),
    )


def project_jats(root: Any) -> tuple[tuple[JatsBlock, ...], PageProjection]:
    """Project a whole article, returning its blocks and their comparable projection.

    Parameters
    ----------
    root : xml.etree.ElementTree.Element
        Parsed JATS article element.

    Returns
    -------
    tuple[tuple[JatsBlock, ...], PageProjection]
        Blocks in document order, and the projection scored against an AST.

    """
    blocks = tuple(walk(root))
    return blocks, to_projection(blocks)


def coverage(projection: PageProjection, pdf_words: int) -> float:
    """Return projected ground-truth words as a share of the PDF's own word count.

    A ratio near 1 means the ground truth accounts for the page. Far below it, the article
    renders text JATS never recorded and every content score carries an unearned penalty;
    far above it, the projection is claiming text the page does not show. Reported rather
    than asserted, because both directions are properties of the source.

    Parameters
    ----------
    projection : PageProjection
        Projected ground truth.
    pdf_words : int
        Whitespace-separated word count of the PDF's own text layer.

    Returns
    -------
    float
        Ground-truth words over PDF words, or ``0.0`` when the PDF has no text.

    """
    if pdf_words <= 0:
        return 0.0
    return len(normalize_text(" ".join(projection.text_blocks)).split()) / pdf_words
