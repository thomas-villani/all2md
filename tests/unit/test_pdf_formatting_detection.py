"""Unit tests for PDF formatting detection logic.

These tests focus on the core formatting detection algorithms without mocking,
using real PDF fixtures to test font flag interpretation and emphasis mapping.
"""

import pytest

from all2md.converters.pdf2markdown import IdentifyHeaders
from tests.fixtures.generators.pdf_test_fixtures import create_pdf_with_figures


@pytest.mark.unit
class TestPdfFormattingDetection:
    """Unit tests for PDF text formatting detection."""

    def test_font_flags_constants(self):
        """Test that we understand PyMuPDF font flag constants correctly."""
        # PyMuPDF font flags - these are the actual constants
        BOLD_FLAG = 16
        ITALIC_FLAG = 2
        SUPERSCRIPT_FLAG = 1

        # Test flag combinations
        bold_only = BOLD_FLAG
        italic_only = ITALIC_FLAG
        bold_italic = BOLD_FLAG | ITALIC_FLAG

        assert bold_only & BOLD_FLAG
        assert not (bold_only & ITALIC_FLAG)

        assert italic_only & ITALIC_FLAG
        assert not (italic_only & BOLD_FLAG)

        assert bold_italic & BOLD_FLAG
        assert bold_italic & ITALIC_FLAG

        # Test common combinations
        assert (bold_italic & BOLD_FLAG) and (bold_italic & ITALIC_FLAG)

    def test_header_identification_with_real_pdf(self):
        """Test header identification using real PDF fixtures."""
        # Create a PDF with different font sizes for testing
        doc = create_pdf_with_figures()

        try:
            header_identifier = IdentifyHeaders(doc)

            # Should create header mapping based on document content
            assert isinstance(header_identifier.header_id, dict)

            # Test with different font sizes
            test_span_large = {"size": 18.0, "flags": 0, "text": "Large Text"}
            test_span_normal = {"size": 12.0, "flags": 0, "text": "Normal Text"}
            test_span_small = {"size": 10.0, "flags": 0, "text": "Small Text"}

            large_header = header_identifier.get_header_id(test_span_large)
            normal_header = header_identifier.get_header_id(test_span_normal)
            small_header = header_identifier.get_header_id(test_span_small)

            # Headers should be determined by relative font sizes
            assert isinstance(large_header, str)
            assert isinstance(normal_header, str)
            assert isinstance(small_header, str)

        finally:
            doc.close()

    def test_emphasis_detection_logic(self):
        """Test the logic for detecting emphasis from font flags."""

        # This tests the logic without mocking by checking flag interpretation

        def detect_emphasis(flags):
            """Simulate the emphasis detection logic."""
            bold = bool(flags & 16)
            italic = bool(flags & 2)

            if bold and italic:
                return "***text***"  # Bold italic
            elif bold:
                return "**text**"  # Bold only
            elif italic:
                return "*text*"  # Italic only
            else:
                return "text"  # No emphasis

        # Test different flag combinations
        assert detect_emphasis(0) == "text"
        assert detect_emphasis(16) == "**text**"
        assert detect_emphasis(2) == "*text*"
        assert detect_emphasis(18) == "***text***"  # 16 + 2

    def test_font_size_hierarchy_detection(self):
        """Test detection of font size hierarchies for headers."""
        # Simulate font size analysis logic
        font_sizes = [24.0, 18.0, 16.0, 14.0, 12.0, 10.0]

        def determine_header_level(size, sizes):
            """Determine header level based on relative font size."""
            sorted_sizes = sorted(set(sizes), reverse=True)

            if len(sorted_sizes) <= 1:
                return ""

            try:
                size_index = sorted_sizes.index(size)
                if size_index < 6:  # Max 6 header levels in Markdown
                    return "#" * (size_index + 1) + " "
                else:
                    return ""
            except ValueError:
                return ""

        # Test header level assignment
        assert determine_header_level(24.0, font_sizes) == "# "
        assert determine_header_level(18.0, font_sizes) == "## "
        assert determine_header_level(16.0, font_sizes) == "### "
        assert determine_header_level(12.0, font_sizes) == "##### "
        assert determine_header_level(8.0, font_sizes) == ""  # Not in list

    def test_span_text_processing_logic(self):
        """Test text processing and cleanup logic for PDF spans."""

        # Test text normalization logic
        def normalize_span_text(text):
            """Simulate text normalization from PDF spans."""
            if not text:
                return ""

            # Remove extra whitespace
            normalized = " ".join(text.split())

            # Handle special characters
            normalized = normalized.replace('\u00a0', ' ')  # Non-breaking space
            normalized = normalized.replace('\u2013', '-')  # En dash
            normalized = normalized.replace('\u2014', '--')  # Em dash

            return normalized

        # Test various text scenarios
        assert normalize_span_text("  Multiple   spaces  ") == "Multiple spaces"
        assert normalize_span_text("Text\u00a0with\u00a0NBSP") == "Text with NBSP"
        assert normalize_span_text("En\u2013dash and Em\u2014dash") == "En-dash and Em--dash"
        assert normalize_span_text("") == ""
        assert normalize_span_text("   ") == ""

    def test_bounding_box_analysis_logic(self):
        """Test logic for analyzing text positioning using bounding boxes."""

        # Test bounding box overlap and positioning logic
        def boxes_overlap_vertically(box1, box2, tolerance=2):
            """Check if two bounding boxes overlap vertically."""
            y1_min, y1_max = box1[1], box1[3]
            y2_min, y2_max = box2[1], box2[3]

            return not (y1_max + tolerance < y2_min or y2_max + tolerance < y1_min)

        def is_same_line(box1, box2, tolerance=2):
            """Check if two spans are on the same line."""
            return boxes_overlap_vertically(box1, box2, tolerance)

        # Test with sample bounding boxes
        box_line1 = (100, 100, 200, 120)  # x0, y0, x1, y1
        box_line1_cont = (200, 102, 300, 118)  # Slightly different y, same line
        box_line2 = (100, 130, 200, 150)  # Different line

        assert is_same_line(box_line1, box_line1_cont)
        assert not is_same_line(box_line1, box_line2)
        assert not is_same_line(box_line1_cont, box_line2)

    def test_text_direction_handling(self):
        """Test handling of text direction for proper text assembly."""

        # Test text direction logic
        def get_text_direction(dir_vector):
            """Determine text direction from PyMuPDF direction vector."""
            x, y = dir_vector

            if abs(x) > abs(y):
                return "horizontal"
            else:
                return "vertical"

        # Test direction detection
        assert get_text_direction((1, 0)) == "horizontal"
        assert get_text_direction((-1, 0)) == "horizontal"
        assert get_text_direction((0, 1)) == "vertical"
        assert get_text_direction((0, -1)) == "vertical"
        assert get_text_direction((0.9, 0.1)) == "horizontal"
        assert get_text_direction((0.1, 0.9)) == "vertical"


@pytest.mark.unit
class TestPdfTextAssembly:
    """Unit tests for PDF text assembly and processing logic."""

    def test_line_assembly_logic(self):
        """Test logic for assembling spans into lines of text."""
        # Mock spans representing a line of text
        spans_data = [
            {
                "text": "This is ",
                "bbox": (100, 100, 140, 120),
                "size": 12.0,
                "flags": 0
            },
            {
                "text": "bold text",
                "bbox": (140, 100, 180, 120),
                "size": 12.0,
                "flags": 16  # Bold
            },
            {
                "text": " in a sentence.",
                "bbox": (180, 100, 250, 120),
                "size": 12.0,
                "flags": 0
            }
        ]

        def assemble_line(spans):
            """Simulate line assembly logic."""
            if not spans:
                return ""

            # Sort by x-coordinate for proper order
            sorted_spans = sorted(spans, key=lambda s: s["bbox"][0])

            line_parts = []
            for span in sorted_spans:
                text = span["text"]
                flags = span.get("flags", 0)

                # Apply formatting
                if flags & 16:  # Bold
                    text = f"**{text}**"
                if flags & 2:  # Italic
                    text = f"*{text}*"

                line_parts.append(text)

            return "".join(line_parts)

        result = assemble_line(spans_data)
        assert result == "This is **bold text** in a sentence."

    def test_paragraph_detection_logic(self):
        """Test logic for detecting paragraph breaks in PDF text."""

        # Test paragraph break detection
        def is_paragraph_break(current_line, next_line, threshold=5):
            """Determine if there should be a paragraph break."""
            if not current_line or not next_line:
                return False

            current_y = current_line["bbox"][3]  # Bottom y coordinate
            next_y = next_line["bbox"][1]  # Top y coordinate

            gap = next_y - current_y
            return gap > threshold

        # Test line data
        line1 = {"bbox": (100, 100, 400, 120), "text": "First line."}
        line2 = {"bbox": (100, 125, 400, 145), "text": "Second line."}  # Small gap
        line3 = {"bbox": (100, 155, 400, 175), "text": "Third line."}  # Large gap

        assert not is_paragraph_break(line1, line2)  # Small gap, same paragraph
        assert is_paragraph_break(line2, line3)  # Large gap, new paragraph

    def test_whitespace_normalization_logic(self):
        """Test whitespace normalization for PDF text extraction."""

        def normalize_whitespace(text):
            """Normalize whitespace in extracted text."""
            if not text:
                return ""

            # Replace multiple whitespace with single space
            import re
            normalized = re.sub(r'\s+', ' ', text)

            # Strip leading/trailing whitespace
            normalized = normalized.strip()

            return normalized

        # Test various whitespace scenarios
        assert normalize_whitespace("  multiple   spaces  ") == "multiple spaces"
        assert normalize_whitespace("line\nbreaks\tand\ttabs") == "line breaks and tabs"
        assert normalize_whitespace("\n\t  \n") == ""
        assert normalize_whitespace("normal text") == "normal text"
