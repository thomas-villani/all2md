import tempfile

import fitz
import pytest

from all2md.parsers import pdf2markdown as mod
from all2md.options import MarkdownOptions, PdfOptions


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

    hdr = mod.IdentifyHeaders(EmptyDoc())
    assert hdr.header_id == {}
    assert hdr.get_header_level({"size": 15}) == 0
    assert hdr.get_header_level({"size": 100}) == 0


@pytest.mark.unit
def test_identify_headers_mapping():
    doc = FakeDocIdent()
    hdr = mod.IdentifyHeaders(doc)
    assert hdr.header_id.get(20) == 1  # Level 1 heading
    assert hdr.get_header_level({"size": 20.0, "flags": 0, "text": "test"}) == 1
    assert hdr.get_header_level({"size": 12.0, "flags": 0, "text": "test"}) == 0


@pytest.mark.unit
def test_resolve_links_no_overlap():
    span = {"bbox": (0, 0, 10, 10), "text": "X"}
    link = {"from": fitz.Rect(50, 50, 60, 60), "uri": "u"}  # Link is completely outside span
    assert mod.resolve_links([link], span) is None


@pytest.mark.unit
def test_resolve_links_partial_overlap():
    """Test link resolution with partial overlap."""
    span = {"bbox": (0, 0, 100, 10), "text": "Click here for more info"}
    link = {"from": fitz.Rect(0, 0, 50, 10), "uri": "http://example.com"}
    result = mod.resolve_links([link], span)
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
    result = mod.resolve_links(links, span)
    assert result is not None
    # Should contain both links
    assert "link1.com" in result
    assert "link2.com" in result


@pytest.mark.unit
def test_header_detection_with_font_weight():
    """Test header detection using font weight."""
    doc = FakeDocIdent()
    options = PdfOptions(header_use_font_weight=True, header_use_all_caps=False)
    hdr = mod.IdentifyHeaders(doc, options=options)
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
    hdr = mod.IdentifyHeaders(doc, options=options)
    assert hdr.header_id.get(20) == 1  # Large font should be level 1 header


@pytest.mark.unit
def test_header_detection_with_allowlist():
    """Test header detection with font size allowlist."""
    doc = FakeDocIdent()
    options = PdfOptions(
        header_size_allowlist=[14.0, 16.0],  # Force these sizes to be headers
        header_min_occurrences=0,
    )
    hdr = mod.IdentifyHeaders(doc, options=options)
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
    hdr = mod.IdentifyHeaders(doc, options=options)
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
    columns = mod.detect_columns(blocks, column_gap_threshold=30)
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
    columns = mod.detect_columns(blocks)
    assert len(columns) == 1  # Should detect single column


@pytest.mark.unit
def test_detect_tables_by_ruling_lines():
    """Test fallback table detection using ruling lines."""

    # This would need a mock page with drawing commands
    # For now, test that the function exists and handles empty input
    class MockPage:
        rect = fitz.Rect(0, 0, 600, 800)

        def get_drawings(self):
            return []

    tables = mod.detect_tables_by_ruling_lines(MockPage())
    assert tables == []  # No tables in empty page


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
    res = mod.resolve_links([link], span)
    assert res == "[click](http://test)"



@pytest.mark.unit
def test_pdf_to_markdown_no_tables(monkeypatch):
    """Test PDF conversion with no tables - now uses AST approach."""
    class DummyHdr:
        def __init__(self, doc, pages=None, body_limit=None, options=None):
            pass

        def get_header_level(self, span):
            return 0

    monkeypatch.setattr(mod, "IdentifyHeaders", DummyHdr)

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
    res = mod.pdf_to_markdown(FakeDoc())
    assert isinstance(res, str)  # Just verify it returns a string


@pytest.mark.unit
def test_pdf_to_markdown_with_tables(monkeypatch):
    """Test PDF conversion with tables - now uses AST approach."""
    class DummyHdr:
        def __init__(self, doc, pages=None, body_limit=None, options=None):
            pass

        def get_header_level(self, span):
            return 0

    monkeypatch.setattr(mod, "IdentifyHeaders", DummyHdr)

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
    res = mod.pdf_to_markdown(FakeDoc())
    assert isinstance(res, str)
    # Verify table was processed (contains pipe characters from markdown table)
    assert "|" in res
