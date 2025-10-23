#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_odp_parser.py
"""Unit tests for ODP parser.

Tests cover:
- Speaker notes extraction
- Notes option handling
- ODP parsing basics

"""

import pytest
from fixtures import FIXTURES_PATH

try:
    import odf  # noqa: F401

    ODFPY_AVAILABLE = True
except ImportError:
    ODFPY_AVAILABLE = False

from all2md.ast import Document, Heading
from all2md.options.odp import OdpOptions

if ODFPY_AVAILABLE:
    from all2md.parsers.odp import OdpToAstConverter


@pytest.mark.unit
@pytest.mark.skipif(not ODFPY_AVAILABLE, reason="odfpy not installed")
class TestOdpParser:
    """Basic ODP parser tests."""

    def test_parser_initialization(self) -> None:
        """Test that ODP parser initializes correctly."""
        parser = OdpToAstConverter()
        assert parser is not None
        assert parser.options.include_notes is True

    def test_parser_with_notes_disabled(self) -> None:
        """Test that parser respects include_notes=False option."""
        options = OdpOptions(include_notes=False)
        parser = OdpToAstConverter(options=options)
        assert parser.options.include_notes is False

    def test_extract_slide_notes_method_exists(self) -> None:
        """Test that _extract_slide_notes method exists and is callable."""
        parser = OdpToAstConverter()
        assert hasattr(parser, "_extract_slide_notes")
        assert callable(parser._extract_slide_notes)

    def test_extract_slide_notes_with_no_notes(self) -> None:
        """Test that _extract_slide_notes returns empty list for slide without notes."""
        parser = OdpToAstConverter()

        # Create a mock slide element without notes
        class MockSlide:
            def __init__(self):
                self.childNodes = []

        mock_slide = MockSlide()
        mock_doc = None

        result = parser._extract_slide_notes(mock_slide, mock_doc)
        assert result == []

    def test_parse_existing_odp_with_notes_enabled(self) -> None:
        """Test parsing an existing ODP file with include_notes=True."""
        parser = OdpToAstConverter(options=OdpOptions(include_notes=True))
        doc = parser.parse(FIXTURES_PATH / "documents" / "basic.odp")

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

    def test_parse_existing_odp_with_notes_disabled(self) -> None:
        """Test parsing an existing ODP file with include_notes=False."""
        parser = OdpToAstConverter(options=OdpOptions(include_notes=False))
        doc = parser.parse(FIXTURES_PATH / "documents" / "basic.odp")

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Should not have any "Speaker Notes" headings
        headings = [child for child in doc.children if isinstance(child, Heading)]
        speaker_notes_headings = [h for h in headings if "Speaker Notes" in str(h.content[0].content)]
        assert len(speaker_notes_headings) == 0


@pytest.mark.unit
@pytest.mark.skipif(not ODFPY_AVAILABLE, reason="odfpy not installed")
class TestOdpNotesExtraction:
    """Tests for ODP speaker notes extraction.

    Note:
        Comprehensive testing of notes extraction requires an ODP file with
        speaker notes. The basic.odp fixture does not contain speaker notes.
        Future improvements could add an ODP fixture generator or manually
        created ODP file with notes for more thorough testing.

    """

    def test_notes_extraction_does_not_crash(self) -> None:
        """Test that notes extraction does not crash on normal ODP files."""
        parser = OdpToAstConverter(options=OdpOptions(include_notes=True))

        # Parse a real ODP file - should not crash even if no notes present
        doc = parser.parse(FIXTURES_PATH / "documents" / "basic.odp")
        assert isinstance(doc, Document)

    @pytest.mark.skip(reason="Requires ODP fixture with speaker notes - to be created")
    def test_slide_with_notes_extraction(self) -> None:
        """Test that speaker notes are extracted when present.

        This test is skipped pending creation of an ODP test fixture with
        speaker notes. The test can be implemented once a suitable fixture
        is available.

        """
        # TODO: Create ODP fixture with notes
        # parser = OdpToAstConverter(options=OdpOptions(include_notes=True))
        # doc = parser.parse("tests/fixtures/documents/odp-with-notes.odp")
        #
        # # Should have "Speaker Notes" heading
        # headings = [child for child in doc.children if isinstance(child, Heading)]
        # speaker_notes_headings = [
        #     h for h in headings
        #     if isinstance(h.content[0], Text) and "Speaker Notes" in h.content[0].content
        # ]
        # assert len(speaker_notes_headings) > 0
        pass

    @pytest.mark.skip(reason="Requires ODP fixture with speaker notes - to be created")
    def test_slide_with_formatted_notes(self) -> None:
        """Test that formatted speaker notes are extracted correctly.

        This test is skipped pending creation of an ODP test fixture with
        formatted speaker notes (bold, italic, etc.).

        """
        pass

    @pytest.mark.skip(reason="Requires ODP fixture with speaker notes - to be created")
    def test_multiple_slides_with_notes(self) -> None:
        """Test that multiple slides can each have their own notes.

        This test is skipped pending creation of an ODP test fixture with
        multiple slides containing speaker notes.

        """
        pass
