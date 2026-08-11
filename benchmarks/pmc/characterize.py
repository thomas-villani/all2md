"""Step 2 of the born-digital lane: measure what the built corpus actually contains.

Deliberately independent of the selection filter and of all2md.  The filter guarantees
*at least one* vector page per article, so reading that fact back out and calling it
characterization would be a measurement that cannot fail; these numbers come from
PyMuPDF directly, per page, over the whole corpus.

The per-page trait counts reuse the OmniDocBench lane's own ``_input_traits``, so the two
corpora are measured with one calibrated instrument and their numbers are comparable.
Two signals are added here because the build proved the trait booleans are not enough:

``drawings_per_page``
    A boolean "has vector drawings" cannot tell a page-sized background rectangle from a
    figure.  The count can.

``min_font_count``
    The signature of an OCR text dump re-typeset into a PDF, which is geometrically
    indistinguishable from a born-digital file: one embedded font, usually monospace.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from pathlib import Path

from benchmarks.pmc.corpus import CorpusSnapshot


@dataclass(frozen=True, slots=True)
class ArticleTraits:
    """Per-article measurement, kept so an outlier can be named rather than averaged away.

    Attributes
    ----------
    article_id : str
        Versioned article identifier.
    pages : int
        Page count.
    text_layer, vector_drawings, one_full_page_image : int
        Pages carrying each trait.
    median_drawings : float
        Median vector drawings per page.
    font_count : int
        Distinct embedded fonts across the document.

    """

    article_id: str
    pages: int
    text_layer: int
    vector_drawings: int
    one_full_page_image: int
    median_drawings: float
    font_count: int


@dataclass(frozen=True, slots=True)
class CorpusCharacterization:
    """Aggregate description of a built corpus.

    Attributes
    ----------
    articles : tuple[ArticleTraits, ...]
        Per-article measurements.
    pages : int
        Total pages measured.
    text_layer_pages, vector_drawing_pages, scan_shape_pages : int
        Pages carrying each trait across the whole corpus.
    pages_by_drawing_count : dict[str, int]
        Pages with zero, exactly one, and two or more vector drawings.
    median_drawings_per_page : float
        Median across every page in the corpus.
    unreadable : tuple[str, ...]
        Articles PyMuPDF could not open.

    """

    articles: tuple[ArticleTraits, ...]
    pages: int
    text_layer_pages: int
    vector_drawing_pages: int
    scan_shape_pages: int
    pages_by_drawing_count: dict[str, int]
    median_drawings_per_page: float
    unreadable: tuple[str, ...]

    @property
    def min_font_count(self) -> int:
        """Fewest embedded fonts in any article; 1 is the re-typeset-OCR signature."""
        return min((entry.font_count for entry in self.articles), default=0)

    def share(self, pages: int) -> float:
        """Return ``pages`` as a share of the corpus, or ``0.0`` for an empty corpus.

        Parameters
        ----------
        pages : int
            Page count to express as a share.

        Returns
        -------
        float
            Fraction in ``[0, 1]``.

        """
        return pages / self.pages if self.pages else 0.0


def characterize(snapshot: CorpusSnapshot) -> CorpusCharacterization:
    """Measure the input traits of every page of a materialized corpus.

    Parameters
    ----------
    snapshot : CorpusSnapshot
        Corpus to measure, as returned by `benchmarks.pmc.corpus.load_corpus`.

    Returns
    -------
    CorpusCharacterization
        Aggregate and per-article measurements.

    """
    import fitz

    from benchmarks.omnidocbench.benchmark import _input_traits

    entries: list[ArticleTraits] = []
    unreadable: list[str] = []
    drawings: list[int] = []

    for article in snapshot.articles:
        traits = _input_traits(article.pdf_path)
        measured = _measure_pdf(fitz, article.pdf_path)
        if traits is None or measured is None:
            unreadable.append(article.article_id)
            continue
        counts, font_count = measured
        drawings.extend(counts)
        entries.append(
            ArticleTraits(
                article_id=article.article_id,
                pages=traits.pages,
                text_layer=traits.text_layer,
                vector_drawings=traits.vector_drawings,
                one_full_page_image=traits.one_full_page_image,
                median_drawings=statistics.median(counts) if counts else 0.0,
                font_count=font_count,
            )
        )

    return CorpusCharacterization(
        articles=tuple(entries),
        pages=sum(entry.pages for entry in entries),
        text_layer_pages=sum(entry.text_layer for entry in entries),
        vector_drawing_pages=sum(entry.vector_drawings for entry in entries),
        scan_shape_pages=sum(entry.one_full_page_image for entry in entries),
        pages_by_drawing_count={
            "zero": sum(count == 0 for count in drawings),
            "one": sum(count == 1 for count in drawings),
            "two_or_more": sum(count >= 2 for count in drawings),
        },
        median_drawings_per_page=statistics.median(drawings) if drawings else 0.0,
        unreadable=tuple(unreadable),
    )


def _measure_pdf(fitz: object, pdf_path: Path) -> tuple[list[int], int] | None:
    """Return per-page drawing counts and the distinct embedded font count."""
    try:
        with fitz.open(pdf_path) as document:  # type: ignore[attr-defined]
            counts = [len(page.get_drawings()) for page in document]
            fonts = {font[3] for page in document for font in page.get_fonts(full=True)}
    except Exception:  # noqa: BLE001 - characterization is evidence, never a reason to fail
        return None
    return counts, len(fonts)
