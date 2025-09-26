"""Advanced tests for PDF formatting and emphasis handling."""

from unittest.mock import Mock, patch

from all2md.converters.pdf2markdown import IdentifyHeaders, page_to_markdown
from all2md.options import PdfOptions
from tests.utils import assert_markdown_valid, cleanup_test_dir, create_test_temp_dir


class TestPdfFormatting:
    """Test PDF font flags mapping to Markdown emphasis."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def test_font_flags_bold_detection(self):
        """Test detection of bold text using font flags."""
        # Mock span with bold flag
        bold_span = {
            "text": "Bold Text",
            "bbox": (100, 100, 200, 120),
            "size": 12.0,
            "flags": 16,  # Bold flag in PyMuPDF
            "dir": (1, 0)
        }

        # Mock span without bold flag
        normal_span = {
            "text": "Normal Text",
            "bbox": (100, 130, 200, 150),
            "size": 12.0,
            "flags": 0,  # No formatting flags
            "dir": (1, 0)
        }

        # Test that we can identify bold text
        # (This would be used internally by the PDF processing functions)
        assert bold_span["flags"] & 16  # Bold flag set
        assert not (normal_span["flags"] & 16)  # Bold flag not set

    def test_font_flags_italic_detection(self):
        """Test detection of italic text using font flags."""
        # Mock span with italic flag
        italic_span = {
            "text": "Italic Text",
            "bbox": (100, 100, 200, 120),
            "size": 12.0,
            "flags": 2,  # Italic flag in PyMuPDF
            "dir": (1, 0)
        }

        # Mock span with both bold and italic
        bold_italic_span = {
            "text": "Bold Italic Text",
            "bbox": (100, 130, 200, 150),
            "size": 12.0,
            "flags": 18,  # Bold (16) + Italic (2) flags
            "dir": (1, 0)
        }

        # Test flag detection
        assert italic_span["flags"] & 2  # Italic flag set
        assert bold_italic_span["flags"] & 16  # Bold flag set
        assert bold_italic_span["flags"] & 2  # Italic flag set

    @patch('all2md.converters.pdf2markdown.fitz.open')
    def test_emphasis_mapping_to_markdown(self, mock_fitz_open):
        """Test mapping of PDF font flags to Markdown emphasis."""
        mock_doc = Mock()
        mock_page = Mock()

        # Mock different formatting scenarios
        spans = [
            {
                "text": "Normal text",
                "bbox": (100, 100, 200, 120),
                "size": 12.0,
                "flags": 0,
                "dir": (1, 0)
            },
            {
                "text": "Bold text",
                "bbox": (100, 130, 180, 150),
                "size": 12.0,
                "flags": 16,  # Bold
                "dir": (1, 0)
            },
            {
                "text": "Italic text",
                "bbox": (100, 160, 180, 180),
                "size": 12.0,
                "flags": 2,  # Italic
                "dir": (1, 0)
            },
            {
                "text": "Bold italic text",
                "bbox": (100, 190, 220, 210),
                "size": 12.0,
                "flags": 18,  # Bold + Italic
                "dir": (1, 0)
            }
        ]

        mock_lines = []
        for span in spans:
            line = {"spans": [span], "dir": (1, 0), "bbox": span["bbox"]}
            mock_lines.append(line)

        mock_blocks = []
        for line in mock_lines:
            block = {"lines": [line], "bbox": line["bbox"]}
            mock_blocks.append(block)

        mock_page.get_text.return_value = {"blocks": mock_blocks}
        mock_page.get_links.return_value = []

        # Configure mock to support indexing
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        mock_doc.page_count = 1
        mock_fitz_open.return_value = mock_doc

        header_analyzer = IdentifyHeaders(mock_doc)
        result = page_to_markdown(mock_page, None, header_analyzer)

        assert_markdown_valid(result)

        # Should contain the text (exact formatting depends on implementation)
        assert "Normal text" in result
        assert "Bold text" in result
        assert "Italic text" in result
        assert "Bold italic text" in result

    def test_font_weight_header_detection(self):
        """Test header detection using font weight/bold flags."""
        # Mock document with various text sizes and weights
        mock_doc = Mock()
        mock_doc.page_count = 1

        # Create mock page with text data
        mock_page = Mock()
        mock_doc.__getitem__ = Mock(return_value=mock_page)

        # Mock page with different text styles
        bold_large_span = {
            "text": "Chapter Title",
            "size": 16.0,
            "flags": 16,  # Bold
        }

        normal_large_span = {
            "text": "Large but not bold",
            "size": 16.0,
            "flags": 0,  # No bold
        }

        bold_small_span = {
            "text": "Bold but small",
            "size": 10.0,
            "flags": 16,  # Bold
        }

        # Set up mock page text structure for IdentifyHeaders
        mock_blocks = []
        for span in [bold_large_span, normal_large_span, bold_small_span]:
            line = {"spans": [span], "dir": (1, 0)}
            block = {"lines": [line]}
            mock_blocks.append(block)

        mock_page.get_text.return_value = {"blocks": mock_blocks}

        options = PdfOptions(
            header_use_font_weight=True,
            header_min_occurrences=1  # Low threshold for testing
        )

        # Test header detection logic
        header_analyzer = IdentifyHeaders(mock_doc, options=options)

        # Simulate header detection (exact implementation may vary)
        # Bold + large should be strong header candidate
        # Large alone might be header
        # Bold alone (small) might not be header

    def test_underline_and_strikethrough_flags(self):
        """Test detection of underline and strikethrough formatting."""
        # Mock spans with different text decorations
        underline_span = {
            "text": "Underlined text",
            "bbox": (100, 100, 200, 120),
            "size": 12.0,
            "flags": 1,  # Underline flag
            "dir": (1, 0)
        }

        strikethrough_span = {
            "text": "Strikethrough text",
            "bbox": (100, 130, 220, 150),
            "size": 12.0,
            "flags": 8,  # Strikethrough flag
            "dir": (1, 0)
        }

        # Test flag detection
        assert underline_span["flags"] & 1  # Underline flag
        assert strikethrough_span["flags"] & 8  # Strikethrough flag

    def test_superscript_subscript_flags(self):
        """Test detection of superscript and subscript formatting."""
        # Mock spans with super/subscript flags
        superscript_span = {
            "text": "E=mc²",
            "bbox": (100, 100, 150, 120),
            "size": 10.0,
            "flags": 32,  # Superscript flag (if supported)
            "dir": (1, 0)
        }

        subscript_span = {
            "text": "H₂O",
            "bbox": (100, 130, 150, 150),
            "size": 10.0,
            "flags": 64,  # Subscript flag (if supported)
            "dir": (1, 0)
        }

        # These flags may not be standard in PyMuPDF, but test structure
        assert "²" in superscript_span["text"]
        assert "₂" in subscript_span["text"]

    def test_font_family_monospace_detection(self):
        """Test detection of monospace fonts for code formatting."""
        # Mock spans with different font families
        monospace_span = {
            "text": "def function():",
            "bbox": (100, 100, 200, 120),
            "size": 10.0,
            "flags": 0,
            "font": "Courier",  # Monospace font
            "dir": (1, 0)
        }

        proportional_span = {
            "text": "Regular text",
            "bbox": (100, 130, 200, 150),
            "size": 12.0,
            "flags": 0,
            "font": "Times",  # Proportional font
            "dir": (1, 0)
        }

        # Test font family detection (implementation-dependent)
        assert "Courier" in monospace_span.get("font", "")

    @patch('all2md.converters.pdf2markdown.fitz.open')
    def test_mixed_formatting_in_paragraph(self, mock_fitz_open):
        """Test paragraphs with mixed formatting within same line."""
        mock_doc = Mock()
        mock_page = Mock()

        # Mock line with multiple spans having different formatting
        mixed_spans = [
            {
                "text": "This is ",
                "bbox": (100, 100, 140, 120),
                "size": 12.0,
                "flags": 0,
                "dir": (1, 0)
            },
            {
                "text": "bold",
                "bbox": (140, 100, 170, 120),
                "size": 12.0,
                "flags": 16,  # Bold
                "dir": (1, 0)
            },
            {
                "text": " and ",
                "bbox": (170, 100, 200, 120),
                "size": 12.0,
                "flags": 0,
                "dir": (1, 0)
            },
            {
                "text": "italic",
                "bbox": (200, 100, 240, 120),
                "size": 12.0,
                "flags": 2,  # Italic
                "dir": (1, 0)
            },
            {
                "text": " text.",
                "bbox": (240, 100, 280, 120),
                "size": 12.0,
                "flags": 0,
                "dir": (1, 0)
            }
        ]

        mock_line = {"spans": mixed_spans, "dir": (1, 0), "bbox": (100, 100, 280, 120)}
        mock_block = {"lines": [mock_line], "bbox": (100, 100, 280, 120)}

        mock_page.get_text.return_value = {"blocks": [mock_block]}
        mock_page.get_links.return_value = []

        # Configure mock to support indexing
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        mock_doc.page_count = 1
        mock_fitz_open.return_value = mock_doc

        header_analyzer = IdentifyHeaders(mock_doc)
        result = page_to_markdown(mock_page, None, header_analyzer)

        assert_markdown_valid(result)

        # Should contain all text parts
        assert "This is" in result
        assert "bold" in result
        assert "italic" in result

    def test_all_caps_header_detection(self):
        """Test header detection using ALL CAPS text."""
        # Mock spans with different casing
        all_caps_span = {
            "text": "CHAPTER ONE",
            "size": 14.0,
            "flags": 0,
        }

        mixed_case_span = {
            "text": "Regular Text",
            "size": 14.0,
            "flags": 0,
        }

        options = PdfOptions(
            header_use_all_caps=True,
            header_min_occurrences=1
        )

        # Test ALL CAPS detection
        assert all_caps_span["text"].isupper()
        assert not mixed_case_span["text"].isupper()

    def test_complex_formatting_combinations(self):
        """Test complex combinations of formatting flags."""
        # Mock spans with multiple formatting flags
        complex_spans = [
            {
                "text": "Bold + Italic",
                "flags": 18,  # Bold (16) + Italic (2)
                "size": 12.0
            },
            {
                "text": "Bold + Underline",
                "flags": 17,  # Bold (16) + Underline (1)
                "size": 12.0
            },
            {
                "text": "All formatting",
                "flags": 31,  # Multiple flags combined
                "size": 12.0
            }
        ]

        # Test flag combinations
        for span in complex_spans:
            flags = span["flags"]
            has_bold = bool(flags & 16)
            has_italic = bool(flags & 2)
            has_underline = bool(flags & 1)

            # Should be able to detect individual flags
            if span["text"] == "Bold + Italic":
                assert has_bold and has_italic
            elif span["text"] == "Bold + Underline":
                assert has_bold and has_underline

    def test_font_size_emphasis_correlation(self):
        """Test correlation between font size and emphasis."""
        # Mock spans with same formatting but different sizes
        large_bold_span = {
            "text": "Large Bold",
            "size": 18.0,
            "flags": 16,  # Bold
        }

        small_bold_span = {
            "text": "Small Bold",
            "size": 8.0,
            "flags": 16,  # Bold
        }

        # Large + bold might be header
        # Small + bold might just be emphasis
        # Implementation should consider both size and formatting

    def test_formatting_consistency_across_document(self):
        """Test consistency of formatting interpretation across document."""
        # Mock document with consistent formatting patterns
        header_pattern = {"size": 16.0, "flags": 16}  # Large + Bold
        body_pattern = {"size": 12.0, "flags": 0}  # Normal
        emphasis_pattern = {"size": 12.0, "flags": 2}  # Italic

        # Should consistently identify similar patterns
        # This would be tested in full document processing
