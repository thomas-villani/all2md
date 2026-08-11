#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_ocr/__init__.py
"""OCR engine strategy.

Dispatches a rendered PDF page pixmap to the OCR backend selected by
``options.ocr.engine``. Each backend lives in its own adapter module and
declares its own optional dependencies, so importing this package never pulls
in pytesseract, EasyOCR, or PyTorch until an engine is actually used.

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import fitz

    from all2md.options.pdf import PdfOptions

__all__ = ["OcrLine", "OcrParagraph", "ocr_pixmap", "ocr_pixmap_layout"]


@dataclass(frozen=True, slots=True)
class OcrLine:
    """One recognized line of text and where it sits, in PDF points."""

    text: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class OcrParagraph:
    """A group of lines the engine considers one paragraph, in PDF points.

    Carrying the engine's own grouping is the whole point: a page handed back as one
    string has to be re-segmented by downstream geometry that no longer has any geometry
    to work with, which is how an OCR'd page came to project as a single block.
    """

    lines: tuple[OcrLine, ...]
    bbox: tuple[float, float, float, float]


def ocr_pixmap_layout(
    pix: "fitz.Pixmap",
    page: "fitz.Page",
    options: "PdfOptions",
) -> list[OcrParagraph] | None:
    """Run OCR and keep the engine's paragraph and line segmentation.

    Parameters
    ----------
    pix : fitz.Pixmap
        The page rendered to a pixmap at the configured OCR DPI.
    page : fitz.Page
        The source page, supplying the coordinate space results are mapped back into.
    options : PdfOptions
        PDF conversion options; ``options.ocr.engine`` selects the backend.

    Returns
    -------
    list of OcrParagraph or None
        Paragraphs in PDF coordinates, or ``None`` when the selected engine cannot
        report layout, in which case the caller falls back to flat text.

    """
    if options.ocr.engine == "easyocr":
        # EasyOCR reports per-detection boxes but no paragraph grouping, so it has no
        # segmentation to preserve. Returning None keeps it on the flat-text path
        # rather than inventing paragraph boundaries that the engine never asserted.
        return None
    from all2md.parsers._ocr.tesseract import ocr_pixmap_layout as _run

    return _run(pix, page, options)


def ocr_pixmap(pix: "fitz.Pixmap", page: "fitz.Page", options: "PdfOptions") -> str:
    """Run OCR on a rendered page pixmap using the configured engine.

    Parameters
    ----------
    pix : fitz.Pixmap
        The page rendered to a pixmap at the configured OCR DPI.
    page : fitz.Page
        The source page (used for language auto-detection).
    options : PdfOptions
        PDF conversion options; ``options.ocr.engine`` selects the backend.

    Returns
    -------
    str
        Text extracted via OCR (empty string on a non-fatal engine failure).

    """
    if options.ocr.engine == "easyocr":
        from all2md.parsers._ocr.easyocr import ocr_pixmap as _run
    else:
        from all2md.parsers._ocr.tesseract import ocr_pixmap as _run
    return _run(pix, page, options)
