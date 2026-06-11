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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import fitz

    from all2md.options.pdf import PdfOptions

__all__ = ["ocr_pixmap"]


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
