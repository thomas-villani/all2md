"""Convert an article PDF once, and recover its page boundaries from that one conversion.

Both instruments in this lane need the same conversion, and the per-page one needs to know
which emitted nodes belong to which page. The alternative -- splitting the PDF and calling
the parser once per page -- was rejected: it hides every cross-page defect this lane exists
to find, because a parser that mangles a paragraph continuing across a page break would
never be shown the break.

Page attribution comes from the parser's own page-separator nodes, which is close to free
of judgement: the separator is emitted per PyMuPDF page, so the boundaries are the file's,
not a decision the parser could shade in its favour. What the parser *can* do is drop a
page, and the separators carry their page numbers precisely so that shows up as a mismatch
instead of silently shifting every later page's ground truth by one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from all2md.ast.nodes import Document
    from all2md.options.pdf import PdfOptions

#: Separator template carrying the number of the page that just ended. The parser's default
#: is a bare rule, which would leave page identity to be inferred from position -- and
#: inference is exactly what fails when a page is dropped.
PAGE_SEPARATOR_TEMPLATE = "--- all2md page {page_num} of {total_pages} ---"
_SEPARATOR = re.compile(r"^--- all2md page (\d+) of (\d+) ---$")


class PageBoundaryError(RuntimeError):
    """Emitted page separators do not describe the PDF's pages."""


@dataclass(frozen=True, slots=True)
class DegradedFact:
    """One degraded-conversion event, with the two fields the lane used to discard.

    The parser records nine distinct reasons for rejecting a table region alone, and
    coalesces repeats of ``(parser, kind, detail, severity)`` while summing their counts.
    Reading back only ``kind`` therefore threw away both halves of what the event says:
    *which* guard fired, and *how many* regions it fired on. A run could report
    ``table_rejected: 101`` with no way to tell one over-firing article from a corpus-wide
    detection failure -- and no way to tell an improvement from a regression, since some of
    those reasons are the parser correctly refusing to grid a page of prose.

    Attributes
    ----------
    kind : str
        Machine-readable event category, e.g. ``"table_rejected"``.
    reason : str or None
        The event's ``detail``, naming the specific guard that fired.
    occurrences : int
        How many times it fired, from the coalesced event's ``count``.

    """

    kind: str
    reason: str | None
    occurrences: int


@dataclass(frozen=True, slots=True)
class EmittedFigure:
    """One figure the parser emitted, and whatever caption it carries.

    A figure is a `Figure` container or a bare `Image` node outside one -- the same
    definition the ``figure:`` extraction selector uses. A container counts once, not
    once per panel image inside it, because the ground truth side counts JATS
    ``<fig>`` elements and a three-panel figure is one ``<fig>``.

    Attributes
    ----------
    alt_text : str
        The node's alt text; for a `Figure`, its panel images' alt texts joined. The
        PDF parser once wrote a detected caption here, which conflates an
        accessibility description with visible page content; recorded so the
        instrument can see a caption that was found but misfiled.
    caption : str
        The node's caption, once it has one. Empty until then.

    """

    alt_text: str
    caption: str


@dataclass(frozen=True, slots=True)
class ConvertedArticle:
    """One article's AST, whole and split by page.

    Attributes
    ----------
    document : Document
        The article's AST exactly as the parser produced it.
    pages : tuple[Document, ...]
        One synthetic `Document` per PDF page, holding that page's nodes in emitted order.
    ocr_page_fraction : float
        Share of pages the parser OCR'd. Expected to be zero on a born-digital corpus, and
        reported rather than assumed so a non-zero is visible.
    degraded : tuple[DegradedFact, ...]
        Degraded-conversion events the parser recorded, with their reason and occurrence
        count intact.
    figures : tuple[EmittedFigure, ...]
        Every `Image` node the parser emitted, in document order.

    """

    document: Document
    pages: tuple[Document, ...]
    ocr_page_fraction: float
    degraded: tuple[DegradedFact, ...]
    figures: tuple[EmittedFigure, ...] = ()


def pdf_options(**overrides: Any) -> PdfOptions:
    """Build this lane's fixed parser policy.

    OCR is left **enabled in auto mode** rather than switched off. Disabling it would make
    "no page needed OCR" true by construction; leaving it on means the reported OCR fraction
    is a measurement that can fail, and a corpus that is not born-digital would say so.

    **Image extraction is enabled for the same reason.** The default ``alt_text`` mode
    returns early before extraction runs, so a lane that inherited the default would report
    "no figures" by construction and could never see a figure defect at all. ``base64`` is
    chosen over ``save`` because it needs no temporary directory to create and clean up on
    a CI runner.

    This costs the text instruments nothing, which is why it can be turned on without
    disturbing the published figures: the shared oracle's ``_node_text`` returns ``""`` for
    an `Image` -- the node has no ``content`` and no children -- so extracted images add
    empty entries to the block stream and contribute not one word to recall or precision.
    They do add ``text_block`` kinds, which moves ``block_structure_similarity``; that
    dimension is already declared ungateable here for unrelated reasons.

    Parameters
    ----------
    **overrides
        Field overrides, for tests that need a narrower policy.

    Returns
    -------
    PdfOptions
        Parser options.

    """
    from all2md.options.common import OCROptions
    from all2md.options.pdf import PdfOptions

    settings: dict[str, Any] = {
        "layout_analysis_mode": "enabled",
        "include_page_numbers": True,
        "page_separator_template": PAGE_SEPARATOR_TEMPLATE,
        "ocr": OCROptions(enabled=True, mode="auto", engine="tesseract", languages="eng", dpi=200),
        "attachment_mode": "base64",
    }
    settings.update(overrides)
    return PdfOptions(**settings)


def _is_separator(node: Any) -> str | None:
    from all2md.ast.nodes import Comment

    if not isinstance(node, Comment):
        return None
    metadata = node.metadata if isinstance(node.metadata, dict) else {}
    if metadata.get("comment_type") != "page_separator":
        return None
    return node.content if isinstance(node.content, str) else ""


def split_pages(document: Any, expected_pages: int) -> tuple[Document, ...]:
    """Split a converted article into one `Document` per PDF page.

    Parameters
    ----------
    document : Document
        Converted article.
    expected_pages : int
        Page count read from the PDF itself.

    Returns
    -------
    tuple[Document, ...]
        One document per page, in page order.

    Raises
    ------
    PageBoundaryError
        If the separators do not describe exactly ``expected_pages`` consecutive pages.
        Silently accepting a mismatch would shift every later page's ground truth.

    """
    from all2md.ast.nodes import Document

    groups: list[list[Any]] = [[]]
    numbers: list[int] = []
    for node in document.children:
        content = _is_separator(node)
        if content is None:
            groups[-1].append(node)
            continue
        match = _SEPARATOR.match(content.strip())
        if match is None:
            raise PageBoundaryError(f"unparsable page separator: {content!r}")
        numbers.append(int(match.group(1)))
        groups.append([])

    if len(groups) != expected_pages:
        raise PageBoundaryError(
            f"parser emitted {len(groups)} page group(s) for a {expected_pages}-page PDF; "
            f"separators name pages {numbers}"
        )
    if numbers != list(range(1, expected_pages)):
        raise PageBoundaryError(f"page separators are not consecutive from 1: {numbers}")
    return tuple(Document(children=nodes) for nodes in groups)


def convert_article(pdf_path: Path, expected_pages: int, *, options: PdfOptions | None = None) -> ConvertedArticle:
    """Convert one article PDF and recover its page boundaries.

    Parameters
    ----------
    pdf_path : pathlib.Path
        Article PDF.
    expected_pages : int
        Page count read from the PDF itself, used to validate the separators.
    options : PdfOptions or None
        Parser policy; defaults to `pdf_options`.

    Returns
    -------
    ConvertedArticle
        Whole and per-page ASTs with conversion evidence.

    """
    from typing import Mapping

    from all2md import to_ast

    document = to_ast(pdf_path, source_format="pdf", parser_options=options or pdf_options())
    metadata = document.metadata if isinstance(document.metadata, Mapping) else {}
    confidence = metadata.get("confidence")
    signals = confidence.get("signals") if isinstance(confidence, Mapping) else None
    raw_fraction = signals.get("ocr_page_fraction") if isinstance(signals, Mapping) else None
    fraction = 0.0
    if isinstance(raw_fraction, (int, float)) and not isinstance(raw_fraction, bool):
        fraction = float(raw_fraction)
    raw_events = confidence.get("degraded_events") if isinstance(confidence, Mapping) else None
    events: list[DegradedFact] = []
    if isinstance(raw_events, list):
        for event in raw_events:
            if not isinstance(event, Mapping) or "kind" not in event:
                continue
            raw_count = event.get("count", 1)
            count = raw_count if isinstance(raw_count, int) and not isinstance(raw_count, bool) else 1
            detail = event.get("detail")
            events.append(
                DegradedFact(
                    kind=str(event["kind"]),
                    reason=None if detail is None else str(detail),
                    occurrences=max(count, 1),
                )
            )
    return ConvertedArticle(
        document=document,
        pages=split_pages(document, expected_pages),
        ocr_page_fraction=fraction,
        degraded=tuple(sorted(events, key=lambda fact: (fact.kind, fact.reason or ""))),
        figures=collect_figures(document),
    )


def collect_figures(document: Any) -> tuple[EmittedFigure, ...]:
    """Return every emitted figure -- `Figure` containers and bare `Image` nodes.

    Delegates the walk to :func:`all2md.ast.extraction.collect_figures`, which
    appends a `Figure` without descending into it (its child images are panels,
    not figures of their own) and reaches bare images through inline content via
    ``get_node_children`` -- a raw ``.children`` walk misses whole node types on
    this AST, finding 170 of 5,233 nodes on a real article.

    A container's entry takes its caption from ``Figure.caption`` and folds its
    panel images' alt texts into ``alt_text``, so the misfiled control still sees
    a caption that landed in alt text even after the parser wraps the image.

    Parameters
    ----------
    document : Document
        Converted article.

    Returns
    -------
    tuple[EmittedFigure, ...]
        Emitted figures in document order.

    """
    from all2md.ast.extraction import collect_figures as collect_figure_nodes
    from all2md.ast.nodes import Figure, Image
    from all2md.ast.transforms import NodeCollector

    emitted = []
    for node in collect_figure_nodes(document):
        if isinstance(node, Figure):
            panels = NodeCollector(lambda candidate: isinstance(candidate, Image))
            for child in node.children:
                child.accept(panels)
            alt_text = " ".join(
                panel.alt_text
                for panel in panels.collected
                if isinstance(panel, Image) and isinstance(panel.alt_text, str) and panel.alt_text
            )
            caption = node.caption if isinstance(node.caption, str) else ""
            emitted.append(EmittedFigure(alt_text=alt_text, caption=caption))
        else:
            emitted.append(
                EmittedFigure(
                    alt_text=node.alt_text if isinstance(node.alt_text, str) else "",
                    caption=caption if isinstance(caption := getattr(node, "caption", ""), str) else "",
                )
            )
    return tuple(emitted)
