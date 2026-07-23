"""Unit tests for PDF OCR functionality.

Tests the OCR detection logic, configuration options, and integration
with the PDF parser. Uses mocking to avoid dependency on Tesseract.
"""

from unittest.mock import Mock, patch

import pytest

from all2md.options.common import OCROptions
from all2md.options.pdf import PdfOptions
from all2md.parsers._pdf_ocr import (
    calculate_image_coverage,
    dehyphenate_text,
)
from all2md.parsers._pdf_ocr import (
    detect_page_language as _detect_page_language,
)
from all2md.parsers.pdf import (
    PdfToAstConverter,
    _should_use_ocr,
)


class TestOCROptions:
    """Test OCROptions dataclass validation and configuration."""

    def test_default_ocr_options(self) -> None:
        """Test that default OCR options are correctly initialized."""
        opts = OCROptions()
        assert opts.enabled is False
        assert opts.mode == "auto"
        assert opts.languages == "eng"
        assert opts.auto_detect_language is False
        assert opts.dpi == 300
        assert opts.text_threshold == 50
        assert opts.doc_text_threshold == 16
        assert opts.image_area_threshold == 0.5
        assert opts.preserve_existing_text is False
        assert opts.tesseract_config == ""

    def test_ocr_options_validation_dpi(self) -> None:
        """Test DPI range validation."""
        # Valid DPI values
        OCROptions(dpi=150)
        OCROptions(dpi=300)
        OCROptions(dpi=600)

        # Invalid DPI values
        with pytest.raises(ValueError, match="dpi must be in range"):
            OCROptions(dpi=50)
        with pytest.raises(ValueError, match="dpi must be in range"):
            OCROptions(dpi=2000)

    def test_ocr_options_validation_thresholds(self) -> None:
        """Test threshold validation."""
        # Valid thresholds
        OCROptions(text_threshold=0)
        OCROptions(text_threshold=100)
        OCROptions(image_area_threshold=0.0)
        OCROptions(image_area_threshold=1.0)

        # Invalid thresholds
        with pytest.raises(ValueError, match="text_threshold must be non-negative"):
            OCROptions(text_threshold=-1)
        with pytest.raises(ValueError, match="image_area_threshold must be in range"):
            OCROptions(image_area_threshold=-0.1)
        with pytest.raises(ValueError, match="image_area_threshold must be in range"):
            OCROptions(image_area_threshold=1.5)

    def test_ocr_options_languages_list(self) -> None:
        """Test language list validation."""
        # Valid language lists
        OCROptions(languages=["eng"])
        OCROptions(languages=["eng", "fra", "deu"])

        # Invalid language lists
        with pytest.raises(ValueError, match="languages list cannot be empty"):
            OCROptions(languages=[])
        with pytest.raises(ValueError, match="Invalid language code"):
            OCROptions(languages=["eng", ""])
        with pytest.raises(ValueError, match="Invalid language code"):
            OCROptions(languages=["eng", "   "])


class TestImageCoverage:
    """Test image coverage calculation."""

    def test_calculate_image_coverage_no_images(self) -> None:
        """Test coverage calculation for page with no images."""
        mock_page = Mock()
        mock_page.rect.width = 612
        mock_page.rect.height = 792
        mock_page.get_images.return_value = []

        coverage = calculate_image_coverage(mock_page)
        assert coverage == 0.0

    def test_calculate_image_coverage_with_images(self) -> None:
        """Test coverage calculation for page with images."""
        mock_page = Mock()
        mock_page.rect.width = 612
        mock_page.rect.height = 792

        # Mock image list (one image)
        mock_page.get_images.return_value = [(1, 0, 0, 0, 0, 0, 0)]

        # Mock image rectangle (half page)
        mock_rect = Mock()
        mock_rect.width = 612
        mock_rect.height = 396
        mock_page.get_image_rects.return_value = [mock_rect]

        coverage = calculate_image_coverage(mock_page)
        # Image area: 612 * 396 = 242352
        # Page area: 612 * 792 = 484704
        # Coverage: 242352 / 484704 ≈ 0.5
        assert 0.49 < coverage < 0.51

    def test_calculate_image_coverage_zero_page_area(self) -> None:
        """Test coverage calculation for page with zero area."""
        mock_page = Mock()
        mock_page.rect.width = 0
        mock_page.rect.height = 0
        mock_page.get_images.return_value = []

        coverage = calculate_image_coverage(mock_page)
        assert coverage == 0.0


class TestShouldUseOCR:
    """Test OCR triggering logic."""

    def test_should_use_ocr_disabled(self) -> None:
        """Test that OCR is not used when disabled."""
        mock_page = Mock()
        options = PdfOptions(ocr=OCROptions(enabled=False))

        result = _should_use_ocr(mock_page, "Sample text", options)
        assert result is False

    def test_should_use_ocr_mode_off(self) -> None:
        """Test that OCR is not used when mode is 'off'."""
        mock_page = Mock()
        options = PdfOptions(ocr=OCROptions(enabled=True, mode="off"))

        result = _should_use_ocr(mock_page, "Sample text", options)
        assert result is False

    def test_should_use_ocr_mode_force(self) -> None:
        """Test that OCR is always used when mode is 'force'."""
        mock_page = Mock()
        mock_page.rect.width = 612
        mock_page.rect.height = 792
        mock_page.get_images.return_value = []

        options = PdfOptions(ocr=OCROptions(enabled=True, mode="force"))

        # Should use OCR even with plenty of text
        result = _should_use_ocr(mock_page, "A" * 1000, options)
        assert result is True

    def test_should_use_ocr_auto_low_text(self) -> None:
        """Test OCR triggering in auto mode with low text."""
        mock_page = Mock()
        mock_page.rect.width = 612
        mock_page.rect.height = 792
        mock_page.get_images.return_value = []

        options = PdfOptions(ocr=OCROptions(enabled=True, mode="auto", text_threshold=50))

        # Text below threshold should trigger OCR
        result = _should_use_ocr(mock_page, "Short", options)
        assert result is True

        # Text above threshold should not trigger OCR
        result = _should_use_ocr(mock_page, "A" * 100, options)
        assert result is False

    def test_should_use_ocr_auto_whitespace_only_text(self) -> None:
        """Whitespace/invisible text triggers OCR even when raw length is high."""
        mock_page = Mock()
        mock_page.rect.width = 612
        mock_page.rect.height = 792
        mock_page.get_images.return_value = []

        options = PdfOptions(ocr=OCROptions(enabled=True, mode="auto", text_threshold=10))

        # 90 chars of whitespace/punctuation but zero meaningful characters.
        result = _should_use_ocr(mock_page, "   \n\t . . . \n   " * 6, options)
        assert result is True

    def test_should_use_ocr_auto_counts_alnum_not_length(self) -> None:
        """Punctuation padding must not mask a near-empty page (meaningful-char count)."""
        mock_page = Mock()
        mock_page.rect.width = 612
        mock_page.rect.height = 792
        mock_page.get_images.return_value = []

        options = PdfOptions(ocr=OCROptions(enabled=True, mode="auto", text_threshold=10))

        # 5 meaningful chars padded with punctuation -> below threshold -> OCR.
        assert _should_use_ocr(mock_page, "abcde" + "-" * 100, options) is True
        # 20 meaningful chars -> above threshold -> no OCR.
        assert _should_use_ocr(mock_page, "a" * 20 + "  ...", options) is False

    @patch("all2md.parsers._pdf_ocr.calculate_image_coverage")
    def test_should_use_ocr_auto_high_image_coverage(self, mock_coverage: Mock) -> None:
        """Test OCR triggering in auto mode with high image coverage."""
        mock_page = Mock()
        mock_coverage.return_value = 0.8  # 80% image coverage

        options = PdfOptions(ocr=OCROptions(enabled=True, mode="auto", text_threshold=50, image_area_threshold=0.5))

        # High image coverage should trigger OCR even with some text
        result = _should_use_ocr(mock_page, "A" * 100, options)
        assert result is True


class TestDetectPageLanguage:
    """Test language detection functionality."""

    @patch("langdetect.detect")
    def test_detect_page_language_single(self, mock_detect: Mock) -> None:
        """Test language detection with single language."""
        mock_page = Mock()
        mock_page.get_text.return_value = "Sample text for language detection"
        # Mock langdetect to return UNKNOWN_LANG to trigger fallback
        from langdetect.detector import Detector

        mock_detect.return_value = Detector.UNKNOWN_LANG

        options = PdfOptions(ocr=OCROptions(languages="fra"))

        lang = _detect_page_language(mock_page, options)
        assert lang == "fra"

    @patch("langdetect.detect")
    def test_detect_page_language_list(self, mock_detect: Mock) -> None:
        """Test language detection with language list."""
        mock_page = Mock()
        mock_page.get_text.return_value = "Sample text for language detection"
        # Mock langdetect to return UNKNOWN_LANG to trigger fallback
        from langdetect.detector import Detector

        mock_detect.return_value = Detector.UNKNOWN_LANG

        options = PdfOptions(ocr=OCROptions(languages=["eng", "fra", "deu"]))

        lang = _detect_page_language(mock_page, options)
        assert lang == "eng+fra+deu"


class TestOCRPageToText:
    """Test OCR text extraction method."""

    @patch("fitz.Matrix")
    @patch("pytesseract.image_to_string")
    @patch("PIL.Image")
    def test_ocr_page_to_text_success(self, mock_image: Mock, mock_pytesseract: Mock, mock_matrix_class: Mock) -> None:
        """Test successful OCR extraction."""
        # Mock page and pixmap
        mock_page = Mock()
        mock_pix = Mock()
        mock_pix.width = 612
        mock_pix.height = 792
        mock_pix.samples = b"mock image data"
        mock_page.get_pixmap.return_value = mock_pix

        # Mock PIL Image
        mock_img = Mock()
        mock_image.frombytes.return_value = mock_img

        # Mock pytesseract
        mock_pytesseract.return_value = "Extracted text from OCR"

        # Mock fitz.Matrix
        mock_matrix = Mock()
        mock_matrix_class.return_value = mock_matrix

        options = PdfOptions(ocr=OCROptions(enabled=True, languages="eng", dpi=300))

        result = PdfToAstConverter._ocr_page_to_text(mock_page, options)

        assert result == "Extracted text from OCR"
        mock_pytesseract.assert_called_once()
        mock_matrix_class.assert_called_once_with(300 / 72.0, 300 / 72.0)

    @patch("fitz.Matrix")
    @patch("pytesseract.image_to_string")
    @patch("pytesseract.TesseractNotFoundError", new=Exception)
    @patch("PIL.Image")
    def test_ocr_page_to_text_tesseract_not_found(
        self, mock_image: Mock, mock_pytesseract: Mock, mock_matrix_class: Mock
    ) -> None:
        """Test OCR when Tesseract is not installed."""
        # Mock page and pixmap
        mock_page = Mock()
        mock_pix = Mock()
        mock_pix.width = 612
        mock_pix.height = 792
        mock_pix.samples = b"mock image data"
        mock_page.get_pixmap.return_value = mock_pix

        # Mock PIL Image
        mock_img = Mock()
        mock_image.frombytes.return_value = mock_img

        # Mock pytesseract raising TesseractNotFoundError
        mock_pytesseract.side_effect = Exception("Tesseract not found")

        # Mock fitz.Matrix
        mock_matrix = Mock()
        mock_matrix_class.return_value = mock_matrix

        options = PdfOptions(ocr=OCROptions(enabled=True, languages="eng"))

        with pytest.raises(RuntimeError, match="Tesseract OCR is not installed"):
            PdfToAstConverter._ocr_page_to_text(mock_page, options)

    @patch("fitz.Matrix")
    @patch("pytesseract.image_to_string")
    @patch("PIL.Image")
    def test_ocr_page_to_text_with_config(
        self, mock_image: Mock, mock_pytesseract: Mock, mock_matrix_class: Mock
    ) -> None:
        """Test OCR with custom Tesseract config."""
        # Mock page and pixmap
        mock_page = Mock()
        mock_pix = Mock()
        mock_pix.width = 612
        mock_pix.height = 792
        mock_pix.samples = b"mock image data"
        mock_page.get_pixmap.return_value = mock_pix

        # Mock PIL Image
        mock_img = Mock()
        mock_image.frombytes.return_value = mock_img

        # Mock pytesseract
        mock_pytesseract.return_value = "OCR text"

        # Mock fitz.Matrix
        mock_matrix = Mock()
        mock_matrix_class.return_value = mock_matrix

        options = PdfOptions(ocr=OCROptions(enabled=True, languages="eng", tesseract_config="--psm 6"))

        result = PdfToAstConverter._ocr_page_to_text(mock_page, options)

        assert result == "OCR text"
        # Verify custom config was passed
        call_args = mock_pytesseract.call_args
        assert call_args[1]["config"] == "--psm 6"


class TestDehyphenateText:
    """Test line-break dehyphenation of OCR text (issue #51)."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            # The exact cases reported in issue #51 (German prose from test.pdf).
            ("wieder einmal be-\nwusst, wie", "wieder einmal bewusst, wie"),
            ("Stadtar-\nchiv von", "Stadtarchiv von"),
            ("Krieg ver-\nloren gegangen", "Krieg verloren gegangen"),
            ("heute erhal-\nten, wie", "heute erhalten, wie"),
            ("in Mag-\ndeburg befindliche", "in Magdeburg befindliche"),
            ("des Politi-\nkers, Naturwissenschaftlers", "des Politikers, Naturwissenschaftlers"),
            # ß and other letters are covered by the letter class.
            ("nur erschlie-\nßen lassen", "nur erschließen lassen"),
            # Single-letter fragments still merge.
            ("x-\ny axis", "xy axis"),
            # Windows line endings.
            ("be-\r\nwusst", "bewusst"),
            # Soft hyphen (U+00AD) and Unicode hyphen (U+2010) at the break.
            ("be­\nwusst", "bewusst"),
            ("be‐\nwusst", "bewusst"),
            # Trailing/leading whitespace around the break is tolerated.
            ("be- \n  wusst", "bewusst"),
        ],
    )
    def test_merges_line_break_hyphenation(self, text: str, expected: str) -> None:
        assert dehyphenate_text(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            # Numeric ranges must not be joined into a single number.
            "10-\n20",
            "end-\n42 next",
            "Kapitel-\n3",
            # A hyphen not attached to a letter (list marker, dangling dash).
            "a list-\n- item",
            "trailing hyphen -\nword",
            # A spaced hyphen (en/em-dash usage) on one line is left alone.
            "range 10 - 20",
            # Hyphen followed by punctuation, not a letter.
            "foo-\n.bar",
            # No hyphen at all.
            "just\nregular text",
        ],
    )
    def test_leaves_non_hyphenation_untouched(self, text: str) -> None:
        assert dehyphenate_text(text) == text

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            # An uppercase continuation signals a genuine hyphenated compound:
            # keep the hyphen, drop only the line break.
            ("Anglo-\nSaxon heritage", "Anglo-Saxon heritage"),
            ("Marie-\nClaire arrived", "Marie-Claire arrived"),
            ("Sino-\nAmerican relations", "Sino-American relations"),
            # Preserves the whichever hyphen character was used at the break.
            ("Nord­\nSüd", "Nord-Süd"),
            ("Judeo‐\nChristian", "Judeo-Christian"),
            # Windows line endings and surrounding whitespace still collapse to
            # a bare hyphen join.
            ("Anglo-\r\nSaxon", "Anglo-Saxon"),
            ("Anglo- \n  Saxon", "Anglo-Saxon"),
        ],
    )
    def test_uppercase_continuation_keeps_hyphen(self, text: str, expected: str) -> None:
        assert dehyphenate_text(text) == expected

    def test_empty_string(self) -> None:
        assert dehyphenate_text("") == ""


class TestApplyOCRDehyphenation:
    """OCR text is dehyphenated only when merge_hyphenated_words is enabled."""

    def _run(self, *, merge: bool) -> str:
        """Run _apply_ocr_if_needed with a forced, hyphenated OCR result."""
        options = PdfOptions(
            ocr=OCROptions(enabled=True, mode="force"),
            merge_hyphenated_words=merge,
        )
        converter = PdfToAstConverter(options=options)

        mock_page = Mock()
        mock_page.rect = "PAGE_RECT"

        with patch.object(PdfToAstConverter, "_ocr_page_to_text", return_value="be-\nwusst sein"):
            blocks, applied = converter._apply_ocr_if_needed(mock_page, [], extracted_text="")

        assert applied is True
        return blocks[0]["lines"][0]["spans"][0]["text"]

    def test_dehyphenates_when_merge_enabled(self) -> None:
        assert self._run(merge=True) == "bewusst sein"

    def test_preserves_hyphenation_when_merge_disabled(self) -> None:
        assert self._run(merge=False) == "be-\nwusst sein"


class TestOCRSpanBbox:
    """OCR-synthesized spans must carry a bbox (regression for KeyError('bbox')).

    Real PyMuPDF spans always expose a ``bbox``; downstream code such as
    ``_resolve_link_for_span`` reads ``span["bbox"]`` directly. When a page
    that also has link annotations was OCR'd, the bbox-less OCR span raised
    ``KeyError('bbox')`` and aborted the whole conversion.
    """

    def _ocr_blocks(self, *, preserve: bool, extracted: str) -> list[dict]:
        import fitz

        options = PdfOptions(
            ocr=OCROptions(enabled=True, mode="force", preserve_existing_text=preserve),
        )
        converter = PdfToAstConverter(options=options)

        mock_page = Mock()
        mock_page.rect = fitz.Rect(0, 0, 612, 792)

        with patch.object(PdfToAstConverter, "_ocr_page_to_text", return_value="scanned text"):
            blocks, applied = converter._apply_ocr_if_needed(mock_page, [], extracted_text=extracted)

        assert applied is True
        return blocks

    def test_replace_path_span_has_bbox(self) -> None:
        blocks = self._ocr_blocks(preserve=False, extracted="")
        span = blocks[0]["lines"][0]["spans"][0]
        assert span["bbox"] == (0.0, 0.0, 612.0, 792.0)

    def test_preserve_path_span_has_bbox(self) -> None:
        # preserve_existing_text appends the OCR block after existing ones.
        blocks = self._ocr_blocks(preserve=True, extracted="existing page text")
        span = blocks[-1]["lines"][0]["spans"][0]
        assert span["bbox"] == (0.0, 0.0, 612.0, 792.0)

    def test_resolve_link_for_span_handles_ocr_span(self) -> None:
        """The OCR span no longer crashes link resolution (issue: KeyError('bbox'))."""
        import fitz

        converter = PdfToAstConverter(options=PdfOptions(ocr=OCROptions(enabled=True, mode="force")))
        span = self._ocr_blocks(preserve=False, extracted="")[0]["lines"][0]["spans"][0]

        # A small hyperlink hotspot on the page (as returned by page.get_links()).
        links = [{"from": fitz.Rect(100, 100, 200, 120), "uri": "https://example.com/"}]

        # Must not raise, and a page-sized span must not spuriously match a tiny link.
        assert converter._resolve_link_for_span(links, span, average_line_height=12.0) is None


class TestPdfOptionsWithOCR:
    """Test PdfOptions integration with OCR."""

    def test_pdf_options_default_ocr(self) -> None:
        """Test that PdfOptions has default OCR settings."""
        options = PdfOptions()
        assert isinstance(options.ocr, OCROptions)
        assert options.ocr.enabled is False

    def test_pdf_options_custom_ocr(self) -> None:
        """Test PdfOptions with custom OCR settings."""
        ocr_opts = OCROptions(enabled=True, mode="force", languages="fra", dpi=600)
        options = PdfOptions(ocr=ocr_opts)

        assert options.ocr.enabled is True
        assert options.ocr.mode == "force"
        assert options.ocr.languages == "fra"
        assert options.ocr.dpi == 600
