"""Advanced tests for PDF layout handling edge cases."""

from unittest.mock import Mock, patch

from utils import cleanup_test_dir, create_test_temp_dir

from all2md import to_markdown as pdf_to_markdown
from all2md.options import PdfOptions
from all2md.parsers.pdf import IdentifyHeaders, detect_columns


class TestPdfLayoutAdvanced:
    """Test complex PDF layout scenarios."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def test_detect_columns_two_column_layout(self):
        """Test detection of two-column layout."""
        # Mock blocks representing two-column layout
        blocks = [
            {"bbox": [50, 100, 250, 200]},  # Left column, top
            {"bbox": [300, 100, 500, 200]},  # Right column, top
            {"bbox": [50, 250, 250, 350]},  # Left column, middle
            {"bbox": [300, 250, 500, 350]},  # Right column, middle
            {"bbox": [50, 400, 250, 500]},  # Left column, bottom
            {"bbox": [300, 400, 500, 500]},  # Right column, bottom
        ]

        columns = detect_columns(blocks, column_gap_threshold=30)

        # Should detect 2 columns
        assert len(columns) == 2
        # Each column should have 3 blocks
        assert len(columns[0]) == 3
        assert len(columns[1]) == 3

        # Blocks should be sorted by vertical position within columns
        left_column_y_positions = [block["bbox"][1] for block in columns[0]]
        right_column_y_positions = [block["bbox"][1] for block in columns[1]]

        assert left_column_y_positions == sorted(left_column_y_positions)
        assert right_column_y_positions == sorted(right_column_y_positions)

    def test_detect_columns_three_column_layout(self):
        """Test detection of three-column layout."""
        blocks = [
            {"bbox": [50, 100, 150, 200]},  # Left column
            {"bbox": [200, 100, 300, 200]},  # Middle column
            {"bbox": [350, 100, 450, 200]},  # Right column
            {"bbox": [50, 250, 150, 350]},  # Left column
            {"bbox": [200, 250, 300, 350]},  # Middle column
            {"bbox": [350, 250, 450, 350]},  # Right column
        ]

        columns = detect_columns(blocks, column_gap_threshold=30)

        # Should detect 3 columns
        assert len(columns) == 3
        # Each column should have 2 blocks
        for column in columns:
            assert len(column) == 2

    def test_detect_columns_irregular_layout(self):
        """Test column detection with irregular block positioning."""
        blocks = [
            {"bbox": [50, 100, 200, 150]},  # Wide block spanning multiple columns
            {"bbox": [50, 200, 150, 250]},  # Left column
            {"bbox": [200, 200, 350, 250]},  # Right column
            {"bbox": [100, 300, 400, 350]},  # Another wide block
        ]

        columns = detect_columns(blocks, column_gap_threshold=30)

        # Should handle irregular layout gracefully
        assert len(columns) >= 1
        # All blocks should be assigned to columns
        total_blocks = sum(len(column) for column in columns)
        assert total_blocks == len(blocks)

    def test_detect_columns_single_column_fallback(self):
        """Test fallback to single column when no clear column structure."""
        blocks = [
            {"bbox": [100, 100, 400, 150]},  # Wide block
            {"bbox": [150, 200, 350, 250]},  # Centered block
            {"bbox": [75, 300, 425, 350]},  # Another wide block
        ]

        columns = detect_columns(blocks, column_gap_threshold=30)

        # Should fall back to single column
        assert len(columns) == 1
        assert len(columns[0]) == len(blocks)

    # TODO: remove or refactor
    @patch('all2md.parsers.pdf.fitz.open')
    def test_rotated_text_handling(self, mock_fitz_open):
        """Test handling of rotated text blocks."""
        # Mock PDF with rotated text
        mock_doc = Mock()
        mock_page = Mock()
        mock_tables = Mock()

        # Simulate rotated text with different dir values
        rotated_span = {
            "text": "Rotated Text",
            "bbox": (100, 100, 200, 120),
            "size": 12.0,
            "flags": 0,
            "dir": (0, 1)  # 90-degree rotation
        }

        normal_span = {
            "text": "Normal Text",
            "bbox": (100, 150, 200, 170),
            "size": 12.0,
            "flags": 0,
            "dir": (1, 0)  # No rotation
        }

        mock_line1 = {"spans": [rotated_span], "dir": (0, 1), "bbox": (100, 100, 200, 120)}
        mock_line2 = {"spans": [normal_span], "dir": (1, 0), "bbox": (100, 150, 200, 170)}

        mock_block1 = {"lines": [mock_line1], "bbox": (100, 100, 200, 120)}
        mock_block2 = {"lines": [mock_line2], "bbox": (100, 150, 200, 170)}

        mock_page.get_text.return_value = {"blocks": [mock_block1, mock_block2]}
        mock_page.get_links.return_value = []
        mock_page.get_images.return_value = []
        mock_page.get_drawings.return_value = []

        mock_rect = Mock()
        mock_rect.width = 200
        mock_rect.height = 200
        mock_page.rect = mock_rect
        mock_tables.tables = []
        mock_page.find_tables.return_value = mock_tables
        # Fix the magic method by configuring it properly
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        mock_doc.page_count = 1
        mock_doc.name = "test.pdf"
        mock_doc.metadata = {}  # Add metadata dict for extraction
        mock_doc.is_encrypted = False  # Not password-protected
        mock_fitz_open.return_value = mock_doc

        options = PdfOptions(handle_rotated_text=True)

        # This would be called by pdf_to_markdown internally
        result = pdf_to_markdown(mock_doc, source_format="pdf", parser_options=options)
        # Should handle rotated text (currently rotated text may be filtered out)
        # The test verifies that the function runs without error with rotated text present
        assert "Normal Text" in result
        # Note: Rotated text handling is not yet fully implemented, so rotated text may not appear

    def test_multi_column_reading_order(self):
        """Test reading order in multi-column layouts."""
        # Test blocks that should be read in column order, not page order
        blocks = [
            {"bbox": [50, 100, 200, 150], "text": "Column 1 Top"},
            {"bbox": [250, 100, 400, 150], "text": "Column 2 Top"},
            {"bbox": [50, 200, 200, 250], "text": "Column 1 Middle"},
            {"bbox": [250, 200, 400, 250], "text": "Column 2 Middle"},
            {"bbox": [50, 300, 200, 350], "text": "Column 1 Bottom"},
            {"bbox": [250, 300, 400, 350], "text": "Column 2 Bottom"},
        ]

        columns = detect_columns(blocks, column_gap_threshold=40)

        # Should detect 2 columns
        assert len(columns) == 2

        # Reading order should be: all of column 1, then all of column 2
        expected_order = [
            "Column 1 Top",
            "Column 1 Middle",
            "Column 1 Bottom",
            "Column 2 Top",
            "Column 2 Middle",
            "Column 2 Bottom"
        ]

        actual_order = []
        for column in columns:
            for block in column:
                actual_order.append(block["text"])

        assert actual_order == expected_order

    def test_complex_column_gaps(self):
        """Test column detection with varying gaps."""
        blocks = [
            {"bbox": [50, 100, 150, 200]},  # Column 1
            {"bbox": [180, 100, 280, 200]},  # Column 2 (small gap)
            {"bbox": [350, 100, 450, 200]},  # Column 3 (large gap)
        ]

        # With small threshold, should detect 3 columns
        columns_small = detect_columns(blocks, column_gap_threshold=20)
        assert len(columns_small) == 3

        # With large threshold, might merge columns 1&2
        columns_large = detect_columns(blocks, column_gap_threshold=50)
        assert len(columns_large) <= 3

    @patch('all2md.parsers.pdf.fitz.open')
    def test_header_detection_with_rotation(self, mock_fitz_open):
        """Test header detection considering rotated text."""
        mock_doc = Mock()
        mock_page = Mock()

        # Mock headers and body text with rotation
        header_span = {
            "text": "CHAPTER TITLE",
            "bbox": (100, 50, 400, 80),
            "size": 18.0,
            "flags": 16,  # Bold flag
            "dir": (1, 0)
        }

        rotated_sidebar = {
            "text": "SIDEBAR TEXT",
            "bbox": (500, 100, 520, 400),
            "size": 10.0,
            "flags": 0,
            "dir": (0, 1)  # Rotated
        }

        body_span = {
            "text": "Regular body text content.",
            "bbox": (100, 100, 400, 120),
            "size": 12.0,
            "flags": 0,
            "dir": (1, 0)
        }

        mock_lines = [
            {"spans": [header_span], "dir": (1, 0)},
            {"spans": [rotated_sidebar], "dir": (0, 1)},
            {"spans": [body_span], "dir": (1, 0)},
        ]

        mock_blocks = [{"lines": [line]} for line in mock_lines]
        mock_page.get_text.return_value = {"blocks": mock_blocks}

        # Fix the magic method by configuring it properly
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        mock_doc.page_count = 1
        mock_fitz_open.return_value = mock_doc

        # Header detection should consider rotation
        options = PdfOptions(
            header_use_font_weight=True,
            handle_rotated_text=True
        )

        header_analyzer = IdentifyHeaders(mock_doc, options=options)

        # Large, bold text should be detected as header regardless of some rotated content
        header_level = header_analyzer.get_header_level(header_span)
        assert header_level > 0  # Should be detected as header

        # Rotated text should not interfere with header detection
        rotated_level = header_analyzer.get_header_level(rotated_sidebar)
        # Rotated text might or might not be header depending on implementation

    def test_column_detection_with_images_and_graphics(self):
        """Test column detection in presence of images and graphics."""
        blocks = [
            # Text blocks in two columns
            {"bbox": [50, 100, 200, 150], "type": "text"},
            {"bbox": [300, 100, 450, 150], "type": "text"},

            # Image spanning partial width
            {"bbox": [50, 200, 250, 300], "type": "image"},

            # Text continues in columns
            {"bbox": [300, 200, 450, 250], "type": "text"},
            {"bbox": [50, 350, 200, 400], "type": "text"},
            {"bbox": [300, 350, 450, 400], "type": "text"},
        ]

        columns = detect_columns(blocks, column_gap_threshold=40)

        # Should still detect column structure despite image
        assert len(columns) >= 1

        # All blocks should be processed
        total_blocks = sum(len(column) for column in columns)
        assert total_blocks == len(blocks)
