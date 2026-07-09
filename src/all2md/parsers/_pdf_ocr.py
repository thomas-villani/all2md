#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_ocr.py
"""PDF OCR utilities.

This private module contains functions for determining when OCR should be
applied to PDF pages and language detection for OCR optimization.

"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from all2md.constants import DEPS_PDF_LANGDETECT
from all2md.options.common import OCROptions
from all2md.options.pdf import PdfOptions
from all2md.utils.decorators import requires_dependencies

if TYPE_CHECKING:
    import fitz

__all__ = [
    "should_use_ocr",
    "get_tesseract_lang",
    "detect_page_language",
    "calculate_image_coverage",
    "dehyphenate_text",
]

logger = logging.getLogger(__name__)

# A word broken across a line by hyphenation: a letter, a hyphen character,
# optional trailing spaces/tabs, a newline, optional leading whitespace, then the
# continuation letter. Matches the hyphen-minus (U+002D), soft hyphen (U+00AD),
# and Unicode hyphen (U+2010) that OCR engines emit at a line break. ``[^\W\d_]``
# matches any letter, including accented and non-Latin ones (ü, ß, …), while
# excluding digits and underscore so numeric ranges ("10-\n20") are left alone.
_HYPHEN_LINEBREAK_RE = re.compile(r"([^\W\d_])[-­‐][ \t]*\r?\n[ \t]*([^\W\d_])", re.UNICODE)


def _merge_hyphenation(match: "re.Match[str]") -> str:
    r"""Join the two halves of a line-break-hyphenated word.

    When the continuation letter is uppercase the hyphen is *kept* (only the line
    break is removed), because an uppercase second half signals a genuine
    hyphenated compound — "Anglo-\\nSaxon" → "Anglo-Saxon", "Marie-\\nClaire" →
    "Marie-Claire" — rather than a word soft-wrapped mid-token. A lowercase
    continuation is treated as ordinary hyphenation and the hyphen is dropped:
    "be-\\nwusst" → "bewusst". The kept hyphen is normalized to a plain
    hyphen-minus so an invisible soft hyphen at the break still renders as a
    visible "-" in the compound.
    """
    lead, cont = match.group(1), match.group(2)
    if cont.isupper():
        return f"{lead}-{cont}"
    return f"{lead}{cont}"


def dehyphenate_text(text: str) -> str:
    r"""Merge words split across line breaks by hyphenation.

    OCR engines preserve the source layout, so a word hyphenated at the end of a
    line ("be-\\nwusst") comes back with the hyphen and newline intact. PyMuPDF's
    native extraction can strip these via ``TEXT_DEHYPHENATE``, but that flag does
    not touch OCR output, so this reproduces the same behaviour for OCR text: the
    trailing hyphen and the line break are removed and the two halves are joined
    ("bewusst"). The line break itself is consumed so downstream paragraph
    reconstruction does not re-insert a space between the halves.

    Only hyphens that sit at a line break between two letters are merged;
    hyphens followed by digits, punctuation, or whitespace (e.g. em-dash usage
    or a trailing "- " list marker) are left untouched. The merge is
    capitalization-aware: an uppercase continuation letter keeps the hyphen
    (dropping only the line break) so legitimately hyphenated compounds such as
    "Anglo-\\nSaxon" survive as "Anglo-Saxon" instead of collapsing to
    "AngloSaxon". Numeric continuations ("COVID-\\n19") are already excluded by
    the letter-only pattern.

    Parameters
    ----------
    text : str
        Text that may contain line-break hyphenation.

    Returns
    -------
    str
        Text with line-break hyphenation merged.

    """
    if not text:
        return text
    return _HYPHEN_LINEBREAK_RE.sub(_merge_hyphenation, text)


def calculate_image_coverage(page: "fitz.Page") -> float:
    """Calculate the ratio of image area to total page area.

    This function analyzes a PDF page to determine what fraction of the page
    is covered by images, which helps identify image-based or scanned pages.

    Parameters
    ----------
    page : fitz.Page
        PDF page to analyze

    Returns
    -------
    float
        Ratio of image area to page area (0.0 to 1.0)

    Notes
    -----
    This function accounts for overlapping images by combining their bounding
    boxes and calculating the total covered area.

    """
    page_area = page.rect.width * page.rect.height
    if page_area == 0:
        return 0.0

    # Get all images on the page
    image_list = page.get_images()
    if not image_list:
        return 0.0

    # Calculate total image area (accounting for potential overlaps)
    # We'll use a simple approach: sum individual image areas
    # For more accuracy, we could use union of bounding boxes
    total_image_area = 0.0

    for img in image_list:
        xref = img[0]
        img_rects = page.get_image_rects(xref)
        if img_rects:
            # Use first occurrence of image on page
            bbox = img_rects[0]
            img_area = (bbox.width) * (bbox.height)
            total_image_area += img_area

    # Calculate ratio
    coverage_ratio = min(1.0, total_image_area / page_area)
    return coverage_ratio


def should_use_ocr(page: "fitz.Page", extracted_text: str, options: PdfOptions) -> bool:
    """Determine whether OCR should be applied to a PDF page.

    Analyzes the page content based on the OCR mode and detection thresholds
    to decide if OCR processing is needed.

    Parameters
    ----------
    page : fitz.Page
        PDF page to analyze
    extracted_text : str
        Text extracted by PyMuPDF from the page
    options : PdfOptions
        PDF conversion options containing OCR settings

    Returns
    -------
    bool
        True if OCR should be applied, False otherwise

    Notes
    -----
    Detection logic depends on ocr.mode:
    - "off": Always returns False
    - "force": Always returns True
    - "auto": Uses text_threshold and image_area_threshold to detect scanned pages

    """
    ocr_opts: OCROptions = options.ocr

    # Check if OCR is enabled
    if not ocr_opts.enabled or ocr_opts.mode == "off":
        return False

    # Force mode always uses OCR
    if ocr_opts.mode == "force":
        return True

    # Auto mode: detect based on thresholds
    if ocr_opts.mode == "auto":
        # Check text threshold against *meaningful* characters only. Counting raw
        # length (including whitespace and invisible glyphs) lets near-empty
        # scanned pages slip past the threshold; alphanumeric characters are a
        # far better proxy for real extractable text.
        meaningful_chars = sum(1 for char in extracted_text if char.isalnum())
        if meaningful_chars < ocr_opts.text_threshold:
            logger.debug(
                f"Page has {meaningful_chars} meaningful chars (threshold: {ocr_opts.text_threshold}), triggering OCR"
            )
            return True

        # Check image coverage threshold
        image_coverage = calculate_image_coverage(page)
        if image_coverage >= ocr_opts.image_area_threshold:
            logger.debug(
                f"Page has {image_coverage:.1%} image coverage "
                f"(threshold: {ocr_opts.image_area_threshold:.1%}), triggering OCR"
            )
            return True

    return False


def get_tesseract_lang(detected_lang_code: str) -> str:
    """Map ISO 639-1 language codes (and some variants) to Tesseract language codes.

    Parameters
    ----------
    detected_lang_code : str
        ISO 639-1 language code (e.g., "en", "fr", "zh-cn")

    Returns
    -------
    str
        Tesseract language code (e.g., "eng", "fra", "chi_sim")

    """
    lang_map = {
        # English and variants
        "en": "eng",
        # European languages
        "fr": "fra",  # French
        "es": "spa",  # Spanish
        "de": "deu",  # German
        "it": "ita",  # Italian
        "pt": "por",  # Portuguese
        "ru": "rus",  # Russian
        "nl": "nld",  # Dutch
        "sv": "swe",  # Swedish
        "no": "nor",  # Norwegian
        "da": "dan",  # Danish
        "fi": "fin",  # Finnish
        "pl": "pol",  # Polish
        "cs": "ces",  # Czech
        "sk": "slk",  # Slovak
        "hu": "hun",  # Hungarian
        "ro": "ron",  # Romanian
        "bg": "bul",  # Bulgarian
        "el": "ell",  # Greek
        "tr": "tur",  # Turkish
        "uk": "ukr",  # Ukrainian
        "hr": "hrv",  # Croatian
        "sr": "srp",  # Serbian
        "sl": "slv",  # Slovenian
        "lv": "lav",  # Latvian
        "lt": "lit",  # Lithuanian
        "et": "est",  # Estonian
        # Asian languages
        "zh-cn": "chi_sim",  # Chinese Simplified
        "zh-tw": "chi_tra",  # Chinese Traditional
        "zh": "chi_sim",  # Default to Simplified
        "ja": "jpn",  # Japanese
        "ko": "kor",  # Korean
        "hi": "hin",  # Hindi
        "th": "tha",  # Thai
        "vi": "vie",  # Vietnamese
        "my": "mya",  # Burmese
        "km": "khm",  # Khmer
        "bn": "ben",  # Bengali
        # Middle Eastern languages
        "ar": "ara",  # Arabic
        "fa": "fas",  # Persian (Farsi)
        "he": "heb",  # Hebrew
        "ur": "urd",  # Urdu
        # Others
        "id": "ind",  # Indonesian
        "ms": "msa",  # Malay
        "ta": "tam",  # Tamil
        "te": "tel",  # Telugu
        "kn": "kan",  # Kannada
        "ml": "mal",  # Malayalam
        "gu": "guj",  # Gujarati
        "mr": "mar",  # Marathi
        "pa": "pan",  # Punjabi
        "si": "sin",  # Sinhala
    }

    # Normalize input to lowercase
    code = detected_lang_code.lower()

    # Handle cases like 'zh-cn', 'zh-tw'
    if code in lang_map:
        return lang_map[code]

    # Sometimes language codes come with region subtags, e.g. 'en-US', 'pt-BR'
    if "-" in code:
        base_code = code.split("-")[0]
        if base_code in lang_map:
            return lang_map[base_code]

    # Fallback to English if unknown
    return "eng"


@requires_dependencies("pdf", DEPS_PDF_LANGDETECT)
def detect_page_language(page: "fitz.Page", options: PdfOptions) -> str:
    """Attempt to auto-detect the language of a PDF page for OCR.

    This is an experimental feature that tries to determine the language
    of the page content to optimize OCR accuracy.

    Parameters
    ----------
    page : fitz.Page
        PDF page to analyze
    options : PdfOptions
        PDF conversion options containing OCR settings

    Returns
    -------
    str
        Tesseract language code (e.g., "eng", "fra", "deu")
        Falls back to options.ocr.languages if detection fails

    """
    from langdetect import detect
    from langdetect.detector import Detector

    page_text_sample = page.get_text()[:10000]  # Limit to 10KB
    detected_lang_code = detect(page_text_sample)

    if detected_lang_code == Detector.UNKNOWN_LANG:
        # Return the configured languages (handle both string and list formats)
        if isinstance(options.ocr.languages, list):
            return "+".join(options.ocr.languages)
        return options.ocr.languages

    return get_tesseract_lang(detected_lang_code)
