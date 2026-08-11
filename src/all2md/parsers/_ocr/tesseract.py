#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_ocr/tesseract.py
"""Tesseract OCR engine adapter.

Thin wrapper over ``pytesseract``. Requires the Tesseract system binary to be
installed and on PATH in addition to the ``pytesseract`` and ``Pillow`` Python
packages (``pip install all2md[ocr]``).

"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from all2md.constants import DEPS_PDF_OCR
from all2md.parsers._pdf_ocr import detect_page_language
from all2md.utils.decorators import requires_dependencies

if TYPE_CHECKING:
    from collections.abc import Iterable

    import pymupdf

    from all2md.options.pdf import PdfOptions
    from all2md.parsers._ocr import OcrParagraph

logger = logging.getLogger(__name__)


@requires_dependencies("pdf", DEPS_PDF_OCR)
def ocr_pixmap(pix: "pymupdf.Pixmap", page: "pymupdf.Page", options: "PdfOptions") -> str:
    """Extract text from a rendered page pixmap using Tesseract.

    Parameters
    ----------
    pix : pymupdf.Pixmap
        Page rendered to an RGB pixmap.
    page : pymupdf.Page
        Source page (used for language auto-detection).
    options : PdfOptions
        PDF conversion options containing OCR settings.

    Returns
    -------
    str
        Extracted text (empty string on a non-fatal failure).

    Raises
    ------
    RuntimeError
        If the Tesseract binary is not installed or not on PATH.

    """
    import pytesseract
    from PIL import Image

    ocr_opts = options.ocr

    # Determine the Tesseract language code(s) to use.
    if ocr_opts.auto_detect_language:
        lang = detect_page_language(page, options)
    elif isinstance(ocr_opts.languages, list):
        lang = "+".join(ocr_opts.languages)
    else:
        lang = ocr_opts.languages

    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    config = ocr_opts.tesseract_config if ocr_opts.tesseract_config else ""

    try:
        ocr_text = pytesseract.image_to_string(img, lang=lang, config=config)
    except pytesseract.TesseractNotFoundError as e:
        raise RuntimeError(
            "Tesseract OCR is not installed or not in PATH. "
            "Please install Tesseract: "
            "https://github.com/tesseract-ocr/tesseract/wiki"
        ) from e
    except Exception as e:  # noqa: BLE001 - keep extraction resilient per-page
        logger.warning(f"OCR failed for page: {e}")
        return ""

    logger.debug(f"OCR extracted {len(ocr_text)} characters using language '{lang}' at {ocr_opts.dpi} DPI")
    return ocr_text


def _resolve_language(page: "pymupdf.Page", options: "PdfOptions") -> str:
    ocr_opts = options.ocr
    if ocr_opts.auto_detect_language:
        return detect_page_language(page, options)
    if isinstance(ocr_opts.languages, list):
        return "+".join(ocr_opts.languages)
    return str(ocr_opts.languages)


@requires_dependencies("pdf", DEPS_PDF_OCR)
def ocr_pixmap_layout(
    pix: "pymupdf.Pixmap",
    page: "pymupdf.Page",
    options: "PdfOptions",
) -> "list[OcrParagraph] | None":
    """Extract text from a pixmap while keeping Tesseract's own segmentation.

    ``image_to_string`` discards the block, paragraph and line numbers Tesseract already
    assigns, and everything downstream of OCR segments on geometry. ``image_to_data``
    reports them alongside per-word boxes, so the page can be handed on as the paragraphs
    the engine actually found instead of one page-sized blob.

    Parameters
    ----------
    pix : pymupdf.Pixmap
        Page rendered to an RGB pixmap.
    page : pymupdf.Page
        Source page, supplying the coordinate space and language auto-detection.
    options : PdfOptions
        PDF conversion options containing OCR settings.

    Returns
    -------
    list of OcrParagraph or None
        Paragraphs in PDF points, or ``None`` if Tesseract reported no usable words.

    Raises
    ------
    RuntimeError
        If the Tesseract binary is not installed or not on PATH.

    """
    import pytesseract
    from PIL import Image

    from all2md.parsers._ocr import OcrLine, OcrParagraph

    ocr_opts = options.ocr
    lang = _resolve_language(page, options)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    config = ocr_opts.tesseract_config if ocr_opts.tesseract_config else ""

    try:
        data = pytesseract.image_to_data(img, lang=lang, config=config, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError as e:
        raise RuntimeError(
            "Tesseract OCR is not installed or not in PATH. "
            "Please install Tesseract: "
            "https://github.com/tesseract-ocr/tesseract/wiki"
        ) from e
    except Exception as e:  # noqa: BLE001 - keep extraction resilient per-page
        logger.warning(f"OCR layout extraction failed for page: {e}")
        return None

    # Map pixel space back to PDF points from the rendered size rather than from the DPI
    # setting, so a pixmap clamped or rounded by PyMuPDF still lands in the right place.
    if not pix.width or not pix.height:
        return None
    scale_x = page.rect.width / pix.width
    scale_y = page.rect.height / pix.height

    # (block_num, par_num) is Tesseract's paragraph; line_num splits it into lines.
    words: dict[tuple[int, int], dict[int, list[tuple[str, tuple[float, float, float, float]]]]] = {}
    for index, raw_text in enumerate(data.get("text", [])):
        text = (raw_text or "").strip()
        if not text:
            continue
        try:
            confidence = float(data["conf"][index])
        except (KeyError, IndexError, TypeError, ValueError):
            confidence = -1.0
        # Tesseract marks non-text rows with -1; they carry boxes but no readable content.
        if confidence < 0:
            continue
        left = page.rect.x0 + data["left"][index] * scale_x
        top = page.rect.y0 + data["top"][index] * scale_y
        box = (
            left,
            top,
            left + data["width"][index] * scale_x,
            top + data["height"][index] * scale_y,
        )
        paragraph_key = (data["block_num"][index], data["par_num"][index])
        words.setdefault(paragraph_key, {}).setdefault(data["line_num"][index], []).append((text, box))

    if not words:
        return None

    paragraphs: list[OcrParagraph] = []
    for paragraph_key in sorted(words):
        lines: list[OcrLine] = []
        for line_number in sorted(words[paragraph_key]):
            entries = words[paragraph_key][line_number]
            lines.append(
                OcrLine(
                    text=" ".join(text for text, _ in entries),
                    bbox=_union(box for _, box in entries),
                )
            )
        if lines:
            paragraphs.append(OcrParagraph(lines=tuple(lines), bbox=_union(line.bbox for line in lines)))

    logger.debug(
        f"OCR recovered {len(paragraphs)} paragraph(s) and "
        f"{sum(len(p.lines) for p in paragraphs)} line(s) using language '{lang}' at {ocr_opts.dpi} DPI"
    )
    return paragraphs


def _union(boxes: "Iterable[tuple[float, float, float, float]]") -> tuple[float, float, float, float]:
    collected = list(boxes)
    return (
        min(box[0] for box in collected),
        min(box[1] for box in collected),
        max(box[2] for box in collected),
        max(box[3] for box in collected),
    )
