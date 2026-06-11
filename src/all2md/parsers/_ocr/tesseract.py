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
    import fitz

    from all2md.options.pdf import PdfOptions

logger = logging.getLogger(__name__)


@requires_dependencies("pdf", DEPS_PDF_OCR)
def ocr_pixmap(pix: "fitz.Pixmap", page: "fitz.Page", options: "PdfOptions") -> str:
    """Extract text from a rendered page pixmap using Tesseract.

    Parameters
    ----------
    pix : fitz.Pixmap
        Page rendered to an RGB pixmap.
    page : fitz.Page
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
