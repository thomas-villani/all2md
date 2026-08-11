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
    degraded_kinds : tuple[str, ...]
        Degraded-conversion event kinds the parser recorded.

    """

    document: Document
    pages: tuple[Document, ...]
    ocr_page_fraction: float
    degraded_kinds: tuple[str, ...]


def pdf_options(**overrides: Any) -> PdfOptions:
    """Build this lane's fixed parser policy.

    OCR is left **enabled in auto mode** rather than switched off. Disabling it would make
    "no page needed OCR" true by construction; leaving it on means the reported OCR fraction
    is a measurement that can fail, and a corpus that is not born-digital would say so.

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
    events = confidence.get("degraded_events") if isinstance(confidence, Mapping) else None
    kinds = (
        tuple(sorted(str(event["kind"]) for event in events if isinstance(event, Mapping) and "kind" in event))
        if isinstance(events, list)
        else ()
    )
    return ConvertedArticle(
        document=document,
        pages=split_pages(document, expected_pages),
        ocr_page_fraction=fraction,
        degraded_kinds=kinds,
    )
