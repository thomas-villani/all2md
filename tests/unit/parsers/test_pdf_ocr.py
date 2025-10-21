"""Unit tests for PDF OCR functionality.

Tests the OCR detection logic, configuration options, and integration
with the PDF parser. Uses mocking to avoid dependency on Tesseract.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from all2md.options.pdf import OCROptions, PdfOptions
from all2md.parsers.pdf import (
    _calculate_image_coverage,
    _should_use_ocr,
    _detect_page_language,
    PdfToAstConverter,
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

        coverage = _calculate_image_coverage(mock_page)
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

        coverage = _calculate_image_coverage(mock_page)
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

        coverage = _calculate_image_coverage(mock_page)
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

        options = PdfOptions(
            ocr=OCROptions(enabled=True, mode="auto", text_threshold=50)
        )

        # Text below threshold should trigger OCR
        result = _should_use_ocr(mock_page, "Short", options)
        assert result is True

        # Text above threshold should not trigger OCR
        result = _should_use_ocr(mock_page, "A" * 100, options)
        assert result is False

    @patch('all2md.parsers.pdf._calculate_image_coverage')
    def test_should_use_ocr_auto_high_image_coverage(self, mock_coverage: Mock) -> None:
        """Test OCR triggering in auto mode with high image coverage."""
        mock_page = Mock()
        mock_coverage.return_value = 0.8  # 80% image coverage

        options = PdfOptions(
            ocr=OCROptions(
                enabled=True,
                mode="auto",
                text_threshold=50,
                image_area_threshold=0.5
            )
        )

        # High image coverage should trigger OCR even with some text
        result = _should_use_ocr(mock_page, "A" * 100, options)
        assert result is True


class TestDetectPageLanguage:
    """Test language detection functionality."""

    def test_detect_page_language_single(self) -> None:
        """Test language detection with single language."""
        mock_page = Mock()
        options = PdfOptions(ocr=OCROptions(languages="fra"))

        lang = _detect_page_language(mock_page, options)
        assert lang == "fra"

    def test_detect_page_language_list(self) -> None:
        """Test language detection with language list."""
        mock_page = Mock()
        options = PdfOptions(ocr=OCROptions(languages=["eng", "fra", "deu"]))

        lang = _detect_page_language(mock_page, options)
        assert lang == "eng+fra+deu"


class TestOCRPageToText:
    """Test OCR text extraction method."""

    @patch('all2md.parsers.pdf.fitz')
    @patch('all2md.parsers.pdf.pytesseract')
    @patch('all2md.parsers.pdf.Image')
    def test_ocr_page_to_text_success(
        self,
        mock_image: Mock,
        mock_pytesseract: Mock,
        mock_fitz: Mock
    ) -> None:
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
        mock_pytesseract.image_to_string.return_value = "Extracted text from OCR"

        # Mock fitz.Matrix
        mock_matrix = Mock()
        mock_fitz.Matrix.return_value = mock_matrix

        options = PdfOptions(ocr=OCROptions(enabled=True, languages="eng", dpi=300))

        result = PdfToAstConverter._ocr_page_to_text(mock_page, options)

        assert result == "Extracted text from OCR"
        mock_pytesseract.image_to_string.assert_called_once()
        mock_fitz.Matrix.assert_called_once_with(300/72.0, 300/72.0)

    @patch('all2md.parsers.pdf.fitz')
    @patch('all2md.parsers.pdf.pytesseract')
    @patch('all2md.parsers.pdf.Image')
    def test_ocr_page_to_text_tesseract_not_found(
        self,
        mock_image: Mock,
        mock_pytesseract: Mock,
        mock_fitz: Mock
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
        mock_pytesseract.TesseractNotFoundError = Exception
        mock_pytesseract.image_to_string.side_effect = mock_pytesseract.TesseractNotFoundError(
            "Tesseract not found"
        )

        # Mock fitz.Matrix
        mock_matrix = Mock()
        mock_fitz.Matrix.return_value = mock_matrix

        options = PdfOptions(ocr=OCROptions(enabled=True, languages="eng"))

        with pytest.raises(RuntimeError, match="Tesseract OCR is not installed"):
            PdfToAstConverter._ocr_page_to_text(mock_page, options)

    @patch('all2md.parsers.pdf.fitz')
    @patch('all2md.parsers.pdf.pytesseract')
    @patch('all2md.parsers.pdf.Image')
    def test_ocr_page_to_text_with_config(
        self,
        mock_image: Mock,
        mock_pytesseract: Mock,
        mock_fitz: Mock
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
        mock_pytesseract.image_to_string.return_value = "OCR text"

        # Mock fitz.Matrix
        mock_matrix = Mock()
        mock_fitz.Matrix.return_value = mock_matrix

        options = PdfOptions(
            ocr=OCROptions(
                enabled=True,
                languages="eng",
                tesseract_config="--psm 6"
            )
        )

        result = PdfToAstConverter._ocr_page_to_text(mock_page, options)

        assert result == "OCR text"
        # Verify custom config was passed
        call_args = mock_pytesseract.image_to_string.call_args
        assert call_args[1]['config'] == "--psm 6"


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
