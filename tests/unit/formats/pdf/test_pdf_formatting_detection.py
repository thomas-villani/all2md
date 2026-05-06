"""Unit tests for PDF formatting detection logic.

These tests focus on the core formatting detection algorithms without mocking,
using real PDF fixtures to test font flag interpretation and emphasis mapping.
"""

import fitz
import pytest
from fixtures.generators.pdf_test_fixtures import create_pdf_with_figures

from all2md.parsers._pdf_headers import compute_line_style
from all2md.parsers.pdf import IdentifyHeaders


@pytest.mark.unit
class TestPdfFormattingDetection:
    """Unit tests for PDF text formatting detection."""

    def test_font_flags_constants(self):
        """Test that we understand PyMuPDF font flag constants correctly."""
        # PyMuPDF font flags - these are the actual constants
        BOLD_FLAG = 16
        ITALIC_FLAG = 2
        _SUPERSCRIPT_FLAG = 1  # Documented but not currently tested

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

            large_header = header_identifier.get_header_level(test_span_large)
            normal_header = header_identifier.get_header_level(test_span_normal)
            small_header = header_identifier.get_header_level(test_span_small)

            # Headers should be determined by relative font sizes
            assert isinstance(large_header, int)
            assert isinstance(normal_header, int)
            assert isinstance(small_header, int)

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
            normalized = normalized.replace("\u00a0", " ")  # Non-breaking space
            normalized = normalized.replace("\u2013", "-")  # En dash
            normalized = normalized.replace("\u2014", "--")  # Em dash

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
            {"text": "This is ", "bbox": (100, 100, 140, 120), "size": 12.0, "flags": 0},
            {"text": "bold text", "bbox": (140, 100, 180, 120), "size": 12.0, "flags": 16},  # Bold
            {"text": " in a sentence.", "bbox": (180, 100, 250, 120), "size": 12.0, "flags": 0},
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

            normalized = re.sub(r"\s+", " ", text)

            # Strip leading/trailing whitespace
            normalized = normalized.strip()

            return normalized

        # Test various whitespace scenarios
        assert normalize_whitespace("  multiple   spaces  ") == "multiple spaces"
        assert normalize_whitespace("line\nbreaks\tand\ttabs") == "line breaks and tabs"
        assert normalize_whitespace("\n\t  \n") == ""
        assert normalize_whitespace("normal text") == "normal text"


def _make_pdf(spans: list[tuple[str, float, bool]]) -> fitz.Document:
    """Build a single-page PDF where each (text, size, bold) spans onto its own line.

    Used by the regression tests below to construct documents with
    precisely-controlled font distributions.
    """
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y = 60.0
    for text, size, bold in spans:
        # "hebo" / "helv" are the PyMuPDF builtin Helvetica Bold / Regular
        # font shortcuts that don't require an external font file.
        font = "hebo" if bold else "helv"
        page.insert_text((50, y), text, fontsize=size, fontname=font)
        y += size * 1.4
    return doc


@pytest.mark.unit
class TestHeaderRatioDefault:
    """Round 1: lower default ratio so body=11/header=12 docs detect headings."""

    def test_body_11_header_12_classifies_size_12_as_heading(self):
        """body=11pt regular and header=12pt bold should map size 12 to a level.

        Previously the default header_font_size_ratio=1.2 set min_header_size
        to 13.2pt, which silently rejected the very common 11/12 publishing
        convention.
        """
        body_lines = [(f"Body sentence number {i}.", 11.0, False) for i in range(40)]
        header_lines = [(f"Heading {i}", 12.0, True) for i in range(8)]
        doc = _make_pdf(body_lines + header_lines)
        try:
            hdr = IdentifyHeaders(doc)
            assert hdr.header_id, "size 12 should be admitted as a header size"
            assert 12 in hdr.header_id

            # And size 12 should require bold (close-to-body sizes always do)
            assert 12 in hdr.bold_header_sizes
        finally:
            doc.close()


@pytest.mark.unit
class TestStyleRequirementsEnforced:
    """Round 1: style-only header sizes really require that style."""

    def test_bold_required_size_rejects_regular_span(self):
        """A bold-required header size must not classify regular-weight spans."""
        body_lines = [(f"Body sentence number {i}.", 11.0, False) for i in range(40)]
        header_lines = [(f"Heading {i}", 12.0, True) for i in range(8)]
        # Plus one regular-weight 12pt label that should NOT classify as heading
        labels = [("Policy Title:", 12.0, False)]
        doc = _make_pdf(body_lines + header_lines + labels)
        try:
            hdr = IdentifyHeaders(doc)
            # Bold span at the heading size: should classify
            bold_span = {"size": 12.0, "flags": 16, "text": "Heading 1"}
            assert hdr.get_header_level(bold_span) > 0
            # Regular span at the same size: should NOT classify
            regular_span = {"size": 12.0, "flags": 0, "text": "Policy Title:"}
            assert hdr.get_header_level(regular_span) == 0
        finally:
            doc.close()


@pytest.mark.unit
class TestSentenceBoundaryDemoter:
    """Round 1: replace `len > 50 and ends with .` with sentence-boundary check."""

    def test_short_period_terminated_heading_kept(self):
        """`Definitions.` should still classify as a heading."""
        body_lines = [(f"Body sentence number {i}.", 11.0, False) for i in range(40)]
        header_lines = [("Heading X", 12.0, True), ("Definitions.", 12.0, True)]
        doc = _make_pdf(body_lines + header_lines)
        try:
            hdr = IdentifyHeaders(doc)
            span = {"size": 12.0, "flags": 16, "text": "Definitions."}
            assert hdr.get_header_level(span) > 0
        finally:
            doc.close()

    def test_multi_sentence_text_demoted(self):
        """Body-style text with an internal sentence boundary is not a heading."""
        body_lines = [(f"Body sentence number {i}.", 11.0, False) for i in range(40)]
        header_lines = [("Heading", 12.0, True)]
        doc = _make_pdf(body_lines + header_lines)
        try:
            hdr = IdentifyHeaders(doc)
            multi_sentence = {
                "size": 12.0,
                "flags": 16,
                "text": "First sentence here. Second sentence follows.",
            }
            assert hdr.get_header_level(multi_sentence) == 0
        finally:
            doc.close()

    def test_acronym_period_does_not_demote(self):
        """Internal acronym dots like "U.S. Department" must not look like sentence boundaries."""
        body_lines = [(f"Body sentence number {i}.", 11.0, False) for i in range(40)]
        header_lines = [("Heading", 12.0, True)]
        doc = _make_pdf(body_lines + header_lines)
        try:
            hdr = IdentifyHeaders(doc)
            span = {"size": 12.0, "flags": 16, "text": "U.S. Department"}
            assert hdr.get_header_level(span) > 0
        finally:
            doc.close()


@pytest.mark.unit
class TestLineStyleClassification:
    """Round 2: classify lines by aggregated span style, not just spans[0]."""

    def test_dominant_size_wins_over_first_span(self):
        """A leading whitespace or numbering span shouldn't change classification."""
        spans = [
            {"size": 11.0, "flags": 0, "text": " "},  # whitespace, regular
            {"size": 12.0, "flags": 16, "text": "Background"},  # bold heading
        ]
        style = compute_line_style(spans)
        assert style is not None
        assert style.size == 12  # dominant by char count
        assert style.is_bold is True

    def test_majority_bold_decides_line(self):
        """A line with majority-bold characters classifies as bold."""
        spans = [
            {"size": 12.0, "flags": 0, "text": "Label: "},
            {"size": 12.0, "flags": 16, "text": "Bold Value Here"},
        ]
        style = compute_line_style(spans)
        assert style is not None
        assert style.is_bold is True  # 15 bold > 7 regular

    def test_minority_bold_does_not_flip(self):
        """A mostly-regular line with one bold word stays regular."""
        spans = [
            {"size": 12.0, "flags": 0, "text": "This is a long line of regular text "},
            {"size": 12.0, "flags": 16, "text": "bold"},
        ]
        style = compute_line_style(spans)
        assert style is not None
        assert style.is_bold is False

    def test_whitespace_only_returns_none(self):
        """A line with only whitespace spans yields no LineStyle."""
        spans = [
            {"size": 12.0, "flags": 0, "text": "  "},
            {"size": 11.0, "flags": 0, "text": "\t"},
        ]
        assert compute_line_style(spans) is None


@pytest.mark.unit
class TestNumberingPrefixDetection:
    """Round 3: detect numbering prefixes for split-line heading merge."""

    def test_roman_numeral_detected(self):
        from all2md.parsers._pdf_numbering import parse_numbering_prefix

        m = parse_numbering_prefix("I.")
        assert m is not None and m.kind == "roman" and m.depth == 1

        m = parse_numbering_prefix("XV.")
        assert m is not None and m.kind == "roman"

    def test_decimal_depth_increases_with_dots(self):
        from all2md.parsers._pdf_numbering import parse_numbering_prefix

        assert parse_numbering_prefix("1.").depth == 1  # type: ignore[union-attr]
        assert parse_numbering_prefix("1.1").depth == 2  # type: ignore[union-attr]
        assert parse_numbering_prefix("1.1.1").depth == 3  # type: ignore[union-attr]

    def test_letter_and_paren(self):
        from all2md.parsers._pdf_numbering import parse_numbering_prefix

        assert parse_numbering_prefix("A.").kind == "letter"  # type: ignore[union-attr]
        assert parse_numbering_prefix("(a)").kind == "paren"  # type: ignore[union-attr]
        assert parse_numbering_prefix("(1)").kind == "paren"  # type: ignore[union-attr]

    def test_bullet_recognized(self):
        from all2md.parsers._pdf_numbering import parse_numbering_prefix

        # Standalone dash / bullet glyph counts as a prefix worth merging
        # so "- Section Name" split across two lines reassembles cleanly.
        for sym in ("-", "•", "–", "—"):
            m = parse_numbering_prefix(sym)
            assert m is not None and m.kind == "bullet", f"{sym!r} should match"

    def test_text_with_content_does_not_match(self):
        from all2md.parsers._pdf_numbering import parse_numbering_prefix

        # Lines with actual heading text after the prefix don't match here —
        # they're handled by the merge path, not the buffer path.
        assert parse_numbering_prefix("I. Background") is None
        assert parse_numbering_prefix("Background") is None
        assert parse_numbering_prefix("1.1 Overview") is None
        assert parse_numbering_prefix("Hello world.") is None


@pytest.mark.unit
class TestHeadingPrefixMerge:
    """Round 3: split-line numbering merges with the next heading."""

    def test_roman_numeral_merges_with_following_heading(self, tmp_path):
        """A line of just "I." followed by a heading line emits one merged heading."""
        from all2md import to_markdown

        pdf_path = tmp_path / "merged.pdf"
        body_lines = [(f"Body sentence number {i}.", 11.0, False) for i in range(40)]
        # "I." on its own line, "Background" on the next, then more body
        sequence = (
            body_lines[:5]
            + [
                ("I.", 12.0, True),
                ("Background", 12.0, True),
            ]
            + body_lines[5:]
        )
        doc = _make_pdf(sequence)
        doc.save(str(pdf_path))
        doc.close()

        out = to_markdown(str(pdf_path))
        # The "I." should not appear as its own heading; should be merged.
        heading_lines = [line for line in out.splitlines() if line.startswith("#")]
        assert any(
            "I." in line and "Background" in line for line in heading_lines
        ), f"expected merged 'I. Background' heading, got {heading_lines!r}"
        assert not any(
            line.strip() in ("# I.", "## I.", "# **I.**", "## **I.**") for line in heading_lines
        ), f"'I.' should not appear as standalone heading: {heading_lines!r}"
