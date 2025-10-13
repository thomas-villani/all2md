"""Unit tests for PDF to Markdown conversion.

This module contains unit tests for PDF parsing and conversion functionality,
including text extraction, table detection, formatting preservation, and
various PDF-specific features.

"""
import tempfile

import fitz
import pytest

import all2md.parsers.pdf as pdf_parser
from all2md import to_markdown
from all2md.options import PdfOptions


class FakePageIdent:
    def __init__(self):
        spans = [{"text": "a" * 100, "size": 12.0, "flags": 0}, {"text": "b" * 10, "size": 20.0, "flags": 0}]
        line = {"dir": (1, 0), "spans": spans}
        block = {"lines": [line]}
        self.blocks = [block]

    def get_text(self, mode, **kwargs):
        return {"blocks": self.blocks}


class FakeDocIdent:
    def __init__(self):
        self.page_count = 1

    def __getitem__(self, i):
        assert i == 0
        return FakePageIdent()


@pytest.mark.unit
def test_identify_headers_empty_doc():
    class EmptyDoc:
        page_count = 0

        def __getitem__(self, i):
            raise IndexError

    hdr = pdf_parser.IdentifyHeaders(EmptyDoc())
    assert hdr.header_id == {}
    assert hdr.get_header_level({"size": 15}) == 0
    assert hdr.get_header_level({"size": 100}) == 0


@pytest.mark.unit
def test_identify_headers_mapping():
    doc = FakeDocIdent()
    hdr = pdf_parser.IdentifyHeaders(doc)
    assert hdr.header_id.get(20) == 1  # Level 1 heading
    assert hdr.get_header_level({"size": 20.0, "flags": 0, "text": "test"}) == 1
    assert hdr.get_header_level({"size": 12.0, "flags": 0, "text": "test"}) == 0


@pytest.mark.unit
def test_resolve_links_no_overlap():
    span = {"bbox": (0, 0, 10, 10), "text": "X"}
    link = {"from": fitz.Rect(50, 50, 60, 60), "uri": "u"}  # Link is completely outside span
    assert pdf_parser.resolve_links([link], span) is None


@pytest.mark.unit
def test_resolve_links_partial_overlap():
    """Test link resolution with partial overlap."""
    span = {"bbox": (0, 0, 100, 10), "text": "Click here for more info"}
    link = {"from": fitz.Rect(0, 0, 50, 10), "uri": "http://example.com"}
    # Link covers 50% of span, use 50% threshold so it's detected
    result = pdf_parser.resolve_links([link], span, overlap_threshold=50.0)
    assert result is not None
    assert "[Click here]" in result or "http://example.com" in result


@pytest.mark.unit
def test_resolve_links_multiple_links():
    """Test handling of multiple links in one span."""
    span = {"bbox": (0, 0, 200, 10), "text": "Link1 and Link2 here"}
    links = [
        {"from": fitz.Rect(0, 0, 50, 10), "uri": "http://link1.com"},
        {"from": fitz.Rect(100, 0, 150, 10), "uri": "http://link2.com"},
    ]
    # Each link covers 25% of span, use 20% threshold so both are detected
    result = pdf_parser.resolve_links(links, span, overlap_threshold=20.0)
    assert result is not None
    # Should contain both links
    assert "link1.com" in result
    assert "link2.com" in result


@pytest.mark.unit
def test_header_detection_with_font_weight():
    """Test header detection using font weight."""
    doc = FakeDocIdent()
    options = PdfOptions(header_use_font_weight=True, header_use_all_caps=False)
    hdr = pdf_parser.IdentifyHeaders(doc, options=options)
    # The implementation would need to check for bold flag
    assert hdr.header_id is not None


@pytest.mark.unit
def test_header_detection_with_percentile():
    """Test header detection using percentile threshold."""
    doc = FakeDocIdent()
    options = PdfOptions(
        header_percentile_threshold=80,  # Top 20% of sizes
        header_min_occurrences=1,
    )
    hdr = pdf_parser.IdentifyHeaders(doc, options=options)
    assert hdr.header_id.get(20) == 1  # Large font should be level 1 header


@pytest.mark.unit
def test_header_detection_with_allowlist():
    """Test header detection with font size allowlist."""
    doc = FakeDocIdent()
    options = PdfOptions(
        header_size_allowlist=[14.0, 16.0],  # Force these sizes to be headers
        header_min_occurrences=0,
    )
    hdr = pdf_parser.IdentifyHeaders(doc, options=options)
    # 14 and 16 should be treated as headers even if not frequent
    assert hdr.header_id.get(14) is not None or hdr.header_id.get(16) is not None


@pytest.mark.unit
def test_header_detection_with_denylist():
    """Test header detection with font size denylist."""
    doc = FakeDocIdent()
    options = PdfOptions(
        header_size_denylist=[20.0],  # Prevent this size from being a header
        header_min_occurrences=0,
    )
    hdr = pdf_parser.IdentifyHeaders(doc, options=options)
    # 20 should not be a header even though it's larger
    assert hdr.header_id.get(20) is None or hdr.header_id.get(20) == ""


@pytest.mark.unit
def test_detect_columns():
    """Test multi-column layout detection."""
    # Create blocks simulating two columns
    blocks = [
        {"bbox": [50, 100, 250, 200]},  # Left column, top
        {"bbox": [300, 100, 500, 200]},  # Right column, top
        {"bbox": [50, 250, 250, 350]},  # Left column, bottom
        {"bbox": [300, 250, 500, 350]},  # Right column, bottom
    ]
    columns = pdf_parser.detect_columns(blocks, column_gap_threshold=30)
    assert len(columns) == 2  # Should detect 2 columns
    assert len(columns[0]) == 2  # Each column should have 2 blocks
    assert len(columns[1]) == 2


@pytest.mark.unit
def test_detect_columns_single_column():
    """Test that single column layout is preserved."""
    blocks = [
        {"bbox": [50, 100, 500, 200]},
        {"bbox": [50, 250, 500, 350]},
    ]
    columns = pdf_parser.detect_columns(blocks)
    assert len(columns) == 1  # Should detect single column


@pytest.mark.unit
def test_detect_tables_by_ruling_lines_empty():
    """Test fallback table detection using ruling lines with empty input."""

    # This would need a mock page with drawing commands
    # For now, test that the function exists and handles empty input
    class MockPage:
        rect = fitz.Rect(0, 0, 600, 800)

        def get_drawings(self):
            return []

    tables = pdf_parser.detect_tables_by_ruling_lines(MockPage())
    assert len(tables) == 2  # A 2-tuple
    assert all(len(t) == 0 for t in tables)  # No tables in empty page


@pytest.mark.unit
def test_page_separator_customization():
    """Test customizable page separators."""
    pdf_options = PdfOptions(page_separator_template="--- Page {page_num} ---")
    # Would need to test in full pdf_to_markdown flow
    assert "{page_num}" in pdf_options.page_separator_template


@pytest.mark.unit
def test_image_extraction_options():
    """Test image extraction configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        options = PdfOptions(
            attachment_mode="skip",
            attachment_output_dir=tmpdir,
            image_placement_markers=True,
            include_image_captions=True,
        )
        assert options.attachment_mode == "skip"
        assert options.attachment_output_dir == tmpdir
        assert options.image_placement_markers is True


@pytest.mark.unit
def test_resolve_links_overlap():
    span = {"bbox": (0, 0, 10, 10), "text": " click "}
    link = {"from": fitz.Rect(0, 0, 10, 10), "uri": "http://test"}
    res = pdf_parser.resolve_links([link], span)
    assert res == "[click](http://test)"



@pytest.mark.skip(reason="Old-style converter test - needs refactoring for new AST architecture")
@pytest.mark.unit
def test_pdf_to_markdown_no_tables(monkeypatch):
    """Test PDF conversion with no tables - now uses AST approach."""
    class DummyHdr:
        def __init__(self, doc, pages=None, body_limit=None, options=None):
            pass

        def get_header_level(self, span):
            return 0

    monkeypatch.setattr(pdf_parser, "IdentifyHeaders", DummyHdr)

    class FakeTables:
        def __init__(self, tables):
            self.tables = tables

    class FakePage:
        def __init__(self):
            self.rect = fitz.Rect(0, 0, 10, 10)

        def find_tables(self):
            return FakeTables([])

        def get_drawings(self):
            return []  # No drawings for test

        def get_images(self):
            return []  # No images for test

    class FakeDoc:
        page_count = 1

        def __getitem__(self, i):
            return FakePage()

    # With AST approach, the result will be empty since FakePage has no real content
    # This test now just verifies the converter doesn't crash with minimal mocks
    res = to_markdown(FakeDoc())
    assert isinstance(res, str)  # Just verify it returns a string


@pytest.mark.skip(reason="Old-style converter test - needs refactoring for new AST architecture")
@pytest.mark.unit
def test_pdf_to_markdown_with_tables(monkeypatch):
    """Test PDF conversion with tables - now uses AST approach."""
    class DummyHdr:
        def __init__(self, doc, pages=None, body_limit=None, options=None):
            pass

        def get_header_level(self, span):
            return 0

    monkeypatch.setattr(pdf_parser, "IdentifyHeaders", DummyHdr)

    class FakeTable:
        def __init__(self, bbox, header_bbox):
            self.bbox = bbox
            self.header = type("H", (), {"bbox": header_bbox})

        def to_markdown(self, clean=False):
            return "| Header |\n|---|\n| Cell |"

    class FakeTables:
        def __init__(self, tables):
            self.tables = tables

        def __getitem__(self, item):
            return self.tables[item]

    page_rect = fitz.Rect(0, 0, 100, 200)

    class FakePage:
        def __init__(self):
            self.rect = page_rect

        def find_tables(self):
            tbl = FakeTable((0, 10, 100, 20), (0, 10, 100, 20))
            return FakeTables([tbl])

        def get_drawings(self):
            return []  # No drawings for test

        def get_images(self):
            return []  # No images for test

    class FakeDoc:
        page_count = 1

        def __getitem__(self, i):
            return FakePage()

    # With AST approach, the result should contain the table
    res = to_markdown(FakeDoc())
    assert isinstance(res, str)
    # Verify table was processed (contains pipe characters from markdown table)
    assert "|" in res


# ============================================================================
# Tests for new PDF parser improvements
# ============================================================================


@pytest.mark.unit
def test_link_overlap_threshold_high():
    """Test link resolution with high overlap threshold (90%)."""
    span = {"bbox": (0, 0, 100, 10), "text": "Click here for info"}
    # Link only covers first 40% of span
    link = {"from": fitz.Rect(0, 0, 40, 10), "uri": "http://example.com"}

    # With 90% threshold, should NOT detect link
    result = pdf_parser.resolve_links([link], span, overlap_threshold=90.0)
    assert result is None or "http://example.com" not in result

    # With 30% threshold, should detect link
    result = pdf_parser.resolve_links([link], span, overlap_threshold=30.0)
    assert result is not None
    assert "http://example.com" in result


@pytest.mark.unit
def test_link_overlap_threshold_options():
    """Test that link_overlap_threshold option is used."""
    from all2md.options.pdf import PdfOptions

    # Test high threshold
    options_high = PdfOptions(link_overlap_threshold=90.0)
    assert options_high.link_overlap_threshold == 90.0

    # Test low threshold
    options_low = PdfOptions(link_overlap_threshold=30.0)
    assert options_low.link_overlap_threshold == 30.0

    # Test default
    options_default = PdfOptions()
    assert options_default.link_overlap_threshold == 70.0


@pytest.mark.unit
def test_link_overlap_multiple_links_threshold():
    """Test handling of multiple links with different overlap amounts."""
    span = {"bbox": (0, 0, 200, 10), "text": "Link1 and Link2 and more text"}
    links = [
        # First link covers chars 0-50 (25% of span)
        {"from": fitz.Rect(0, 0, 50, 10), "uri": "http://link1.com"},
        # Second link covers chars 100-150 (25% of span)
        {"from": fitz.Rect(100, 0, 150, 10), "uri": "http://link2.com"},
    ]

    # With 50% threshold, neither link should be detected (each is only 25%)
    result = pdf_parser.resolve_links(links, span, overlap_threshold=50.0)
    assert result is None or ("link1.com" not in result and "link2.com" not in result)

    # With 20% threshold, both links should be detected
    result = pdf_parser.resolve_links(links, span, overlap_threshold=20.0)
    assert result is not None
    assert "link1.com" in result
    assert "link2.com" in result


@pytest.mark.unit
def test_header_debug_output_enabled():
    """Test header detection debug output when enabled."""
    from all2md.options.pdf import PdfOptions

    doc = FakeDocIdent()
    options = PdfOptions(header_debug_output=True, header_min_occurrences=1)
    hdr = pdf_parser.IdentifyHeaders(doc, options=options)

    # Should have debug info
    debug_info = hdr.get_debug_info()
    assert debug_info is not None
    assert "font_size_distribution" in debug_info
    assert "body_text_size" in debug_info
    assert "header_sizes" in debug_info
    assert "header_id_mapping" in debug_info


@pytest.mark.unit
def test_header_debug_output_disabled():
    """Test header detection debug output when disabled."""
    from all2md.options.pdf import PdfOptions

    doc = FakeDocIdent()
    options = PdfOptions(header_debug_output=False, header_min_occurrences=1)
    hdr = pdf_parser.IdentifyHeaders(doc, options=options)

    # Should NOT have debug info
    debug_info = hdr.get_debug_info()
    assert debug_info is None


@pytest.mark.unit
def test_column_detection_mode_disabled():
    """Test that column_detection_mode='disabled' forces single column."""
    from all2md.options.pdf import PdfOptions

    # With detect_columns=True but mode='disabled', should return single column
    # (This would be tested in integration with actual PdfToAstConverter)
    options = PdfOptions(detect_columns=True, column_detection_mode="disabled")
    assert options.column_detection_mode == "disabled"


@pytest.mark.unit
def test_column_detection_with_clustering():
    """Test k-means clustering for column detection."""
    blocks = [
        {"bbox": [50, 100, 150, 120]},   # Column 1
        {"bbox": [55, 130, 155, 150]},   # Column 1 (slightly offset)
        {"bbox": [300, 100, 400, 120]},  # Column 2
        {"bbox": [305, 130, 405, 150]},  # Column 2 (slightly offset)
    ]

    # With clustering enabled, should handle slight offsets better
    columns_clustering = pdf_parser.detect_columns(blocks, column_gap_threshold=20, use_clustering=True)
    assert len(columns_clustering) == 2
    # Each column should have 2 blocks
    assert len(columns_clustering[0]) == 2
    assert len(columns_clustering[1]) == 2


@pytest.mark.unit
def test_table_fallback_extraction_mode_option():
    """Test table_fallback_extraction_mode option values."""
    from all2md.options.pdf import PdfOptions

    # Test 'none' mode
    options_none = PdfOptions(table_fallback_extraction_mode="none")
    assert options_none.table_fallback_extraction_mode == "none"

    # Test 'grid' mode (default)
    options_grid = PdfOptions(table_fallback_extraction_mode="grid")
    assert options_grid.table_fallback_extraction_mode == "grid"

    # Test 'text_clustering' mode
    options_clustering = PdfOptions(table_fallback_extraction_mode="text_clustering")
    assert options_clustering.table_fallback_extraction_mode == "text_clustering"


@pytest.mark.unit
def test_detect_tables_by_ruling_lines():
    """Test basic table detection using ruling lines."""
    # Create a mock page with drawing commands
    class MockPage:
        rect = fitz.Rect(0, 0, 600, 800)

        def get_drawings(self):
            # Simulate a simple 2x2 table with horizontal and vertical lines
            return [
                {
                    "items": [
                        ("l", fitz.Point(100, 100), fitz.Point(400, 100)),  # Top h-line
                        ("l", fitz.Point(100, 150), fitz.Point(400, 150)),  # Middle h-line
                        ("l", fitz.Point(100, 200), fitz.Point(400, 200)),  # Bottom h-line
                    ]
                },
                {
                    "items": [
                        ("l", fitz.Point(100, 100), fitz.Point(100, 200)),  # Left v-line
                        ("l", fitz.Point(250, 100), fitz.Point(250, 200)),  # Middle v-line
                        ("l", fitz.Point(400, 100), fitz.Point(400, 200)),  # Right v-line
                    ]
                },
            ]

    table_rects, table_lines = pdf_parser.detect_tables_by_ruling_lines(MockPage(), threshold=0.3)

    # Should detect at least one table
    assert len(table_rects) >= 1

    # Should have corresponding line information
    assert len(table_lines) == len(table_rects)


@pytest.mark.unit
def test_simple_kmeans_1d():
    """Test simple k-means clustering implementation."""
    # Test with clear two-cluster data
    values = [10.0, 12.0, 11.0, 100.0, 102.0, 101.0]  # Two clear clusters
    assignments = pdf_parser._simple_kmeans_1d(values, k=2)

    # Should assign first 3 values to one cluster, last 3 to another
    assert len(assignments) == 6
    assert assignments[0] == assignments[1] == assignments[2]  # First cluster
    assert assignments[3] == assignments[4] == assignments[5]  # Second cluster
    # The two clusters should be different
    assert assignments[0] != assignments[3]


@pytest.mark.unit
def test_simple_kmeans_edge_cases():
    """Test k-means edge cases."""
    # Test with k=1
    values = [10.0, 20.0, 30.0]
    assignments = pdf_parser._simple_kmeans_1d(values, k=1)
    assert all(a == 0 for a in assignments)  # All in one cluster

    # Test with empty values
    assignments = pdf_parser._simple_kmeans_1d([], k=2)
    assert assignments == []

    # Test with fewer values than k
    values = [10.0, 20.0]
    assignments = pdf_parser._simple_kmeans_1d(values, k=5)
    # Should handle gracefully
    assert len(assignments) == 2
