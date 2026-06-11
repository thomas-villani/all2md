#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_ocr/easyocr.py
"""EasyOCR engine adapter (binary-free OCR).

Uses the ``easyocr`` package, which requires no system binary but pulls in
PyTorch transitively and downloads recognition models on first use
(``pip install all2md[ocr-easyocr]``).

EasyOCR returns one result per detected text box rather than reading-order
text, so this adapter reconstructs line order by grouping boxes by vertical
position and sorting left-to-right within each line.

"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from all2md.constants import DEPS_PDF_OCR_EASYOCR
from all2md.parsers._pdf_ocr import detect_page_language
from all2md.utils.decorators import requires_dependencies

if TYPE_CHECKING:
    import fitz

    from all2md.options.pdf import PdfOptions

logger = logging.getLogger(__name__)

# Cache of EasyOCR Reader instances. Constructing a Reader loads recognition
# models from disk (slow), so reuse one per (languages, gpu) key across pages
# and documents.
_READER_CACHE: dict[tuple[tuple[str, ...], bool], Any] = {}

# Map language codes to EasyOCR's codes. Accepts both ISO 639-1 (e.g. "en") and
# Tesseract codes (e.g. "eng") so a config written for Tesseract keeps working
# when the engine is switched. EasyOCR supports a subset of Tesseract's
# languages; unmapped codes fall back to English with a warning.
_EASYOCR_LANG_MAP: dict[str, str] = {
    "en": "en",
    "eng": "en",
    "fr": "fr",
    "fra": "fr",
    "es": "es",
    "spa": "es",
    "de": "de",
    "deu": "de",
    "it": "it",
    "ita": "it",
    "pt": "pt",
    "por": "pt",
    "ru": "ru",
    "rus": "ru",
    "nl": "nl",
    "nld": "nl",
    "sv": "sv",
    "swe": "sv",
    "da": "da",
    "dan": "da",
    "no": "no",
    "nor": "no",
    "fi": "fi",
    "fin": "fi",
    "pl": "pl",
    "pol": "pl",
    "cs": "cs",
    "ces": "cs",
    "sk": "sk",
    "slk": "sk",
    "hu": "hu",
    "hun": "hu",
    "ro": "ro",
    "ron": "ro",
    "bg": "bg",
    "bul": "bg",
    "tr": "tr",
    "tur": "tr",
    "uk": "uk",
    "ukr": "uk",
    "hr": "hr",
    "hrv": "hr",
    "sl": "sl",
    "slv": "sl",
    "lv": "lv",
    "lav": "lv",
    "lt": "lt",
    "lit": "lt",
    "et": "et",
    "est": "et",
    "zh": "ch_sim",
    "zh-cn": "ch_sim",
    "chi_sim": "ch_sim",
    "zh-tw": "ch_tra",
    "chi_tra": "ch_tra",
    "ja": "ja",
    "jpn": "ja",
    "ko": "ko",
    "kor": "ko",
    "hi": "hi",
    "hin": "hi",
    "th": "th",
    "tha": "th",
    "vi": "vi",
    "vie": "vi",
    "ar": "ar",
    "ara": "ar",
    "fa": "fa",
    "fas": "fa",
    "ur": "ur",
    "urd": "ur",
    "id": "id",
    "ind": "id",
    "ms": "ms",
    "msa": "ms",
    "ta": "ta",
    "tam": "ta",
    "te": "te",
    "tel": "te",
    "kn": "kn",
    "kan": "kn",
    "mr": "mr",
    "mar": "mr",
}


def _resolve_languages(page: "fitz.Page", options: "PdfOptions") -> list[str]:
    """Resolve the configured OCR languages to EasyOCR language codes."""
    ocr_opts = options.ocr

    if ocr_opts.auto_detect_language:
        # ``detect_page_language`` returns a Tesseract code (possibly "+"-joined).
        raw_tokens: list[str] = [detect_page_language(page, options)]
    elif isinstance(ocr_opts.languages, list):
        raw_tokens = list(ocr_opts.languages)
    else:
        raw_tokens = [ocr_opts.languages]

    # Flatten any "+"-joined specs (e.g. "eng+fra") into individual tokens.
    tokens: list[str] = []
    for tok in raw_tokens:
        tokens.extend(part for part in str(tok).replace("+", " ").split() if part)

    mapped: list[str] = []
    for code in tokens:
        easy = _EASYOCR_LANG_MAP.get(code.strip().lower())
        if easy is None:
            logger.warning("EasyOCR: unsupported language code %r; falling back to 'en'", code)
            easy = "en"
        if easy not in mapped:
            mapped.append(easy)

    return mapped or ["en"]


def _get_reader(languages: list[str], gpu: bool) -> Any:
    """Return a cached EasyOCR ``Reader`` for the given languages and device."""
    import easyocr

    key = (tuple(languages), gpu)
    reader = _READER_CACHE.get(key)
    if reader is None:
        logger.debug("Initializing EasyOCR reader for languages=%s gpu=%s", languages, gpu)
        reader = easyocr.Reader(languages, gpu=gpu)
        _READER_CACHE[key] = reader
    return reader


def _results_to_text(results: list[Any]) -> str:
    """Reconstruct reading-order text from EasyOCR's per-box results.

    EasyOCR returns ``(bbox, text, confidence)`` tuples in detection order.
    Group boxes into lines by vertical proximity (using the median box height as
    the tolerance so it adapts to render DPI), then order each line left to right.
    """
    items: list[tuple[float, float, float, str]] = []  # (top, left, height, text)
    for entry in results:
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        bbox, text = entry[0], entry[1]
        if not text:
            continue
        try:
            ys = [float(pt[1]) for pt in bbox]
            xs = [float(pt[0]) for pt in bbox]
            top, left, height = min(ys), min(xs), max(ys) - min(ys)
        except (TypeError, IndexError, ValueError):
            top, left, height = 0.0, 0.0, 0.0
        items.append((top, left, height, text))

    if not items:
        return ""

    heights = sorted(h for _t, _l, h, _x in items if h > 0)
    median_height = heights[len(heights) // 2] if heights else 0.0
    line_tol = median_height * 0.6 if median_height else 10.0

    items.sort(key=lambda it: (it[0], it[1]))
    lines: list[list[tuple[float, float, float, str]]] = []
    line_top: float | None = None
    for item in items:
        if line_top is None or abs(item[0] - line_top) > line_tol:
            lines.append([])
            line_top = item[0]
        lines[-1].append(item)

    out_lines: list[str] = []
    for line in lines:
        line.sort(key=lambda it: it[1])
        out_lines.append(" ".join(text for _t, _l, _h, text in line))
    return "\n".join(out_lines)


@requires_dependencies("pdf", DEPS_PDF_OCR_EASYOCR)
def ocr_pixmap(pix: "fitz.Pixmap", page: "fitz.Page", options: "PdfOptions") -> str:
    """Extract text from a rendered page pixmap using EasyOCR.

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
        Extracted text in reading order (empty string on a non-fatal failure).

    Raises
    ------
    RuntimeError
        If EasyOCR cannot initialize for the requested languages (e.g. an
        unsupported script combination or a failed model download).

    """
    import numpy as np
    from PIL import Image

    languages = _resolve_languages(page, options)
    try:
        reader = _get_reader(languages, options.ocr.gpu)
    except Exception as e:  # noqa: BLE001 - surface init failures with guidance
        raise RuntimeError(
            f"EasyOCR failed to initialize for languages {languages}: {e}. "
            "Note that EasyOCR cannot combine certain scripts (e.g. Chinese, "
            "Japanese, and Korean) in one reader, and downloads models on first use."
        ) from e

    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    array = np.asarray(img)

    try:
        results = reader.readtext(array, detail=1, paragraph=False)
    except Exception as e:  # noqa: BLE001 - keep extraction resilient per-page
        logger.warning("EasyOCR failed for page: %s", e)
        return ""

    text = _results_to_text(results)
    logger.debug("EasyOCR extracted %d characters using languages %s", len(text), languages)
    return text
