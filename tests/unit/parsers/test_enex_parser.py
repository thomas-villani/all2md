"""Unit tests for ENEX (Evernote Export) parser."""

import datetime
from io import BytesIO

import pytest

from all2md.ast import Document, Heading, Paragraph, ThematicBreak
from all2md.exceptions import MalformedFileError
from all2md.options.enex import EnexOptions
from all2md.parsers.enex import EnexToAstConverter, _format_enex_date, _parse_enex_date
from tests.fixtures.generators.enex_fixtures import (
    generate_empty_note_enex,
    generate_multiple_notes_enex,
    generate_note_with_image_enex,
    generate_note_with_table_enex,
    generate_simple_note_enex,
)


class TestEnexDateParsing:
    """Test ENEX date parsing utilities."""

    def test_parse_enex_date_valid(self) -> None:
        """Test parsing valid ENEX date string."""
        date_str = "20250115T143000Z"
        result = _parse_enex_date(date_str)

        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 0
        assert result.tzinfo == datetime.timezone.utc

    def test_parse_enex_date_none(self) -> None:
        """Test parsing None date."""
        result = _parse_enex_date(None)
        assert result is None

    def test_parse_enex_date_empty(self) -> None:
        """Test parsing empty date string."""
        result = _parse_enex_date("")
        assert result is None

    def test_parse_enex_date_invalid_format(self) -> None:
        """Test parsing invalid date format."""
        result = _parse_enex_date("invalid-date")
        assert result is None

    def test_format_enex_date_iso8601(self) -> None:
        """Test formatting date as ISO 8601."""
        dt = datetime.datetime(2025, 1, 15, 14, 30, 0, tzinfo=datetime.timezone.utc)
        options = EnexOptions(date_format_mode="iso8601")
        result = _format_enex_date(dt, options)

        assert "2025-01-15" in result
        assert "14:30:00" in result

    def test_format_enex_date_strftime(self) -> None:
        """Test formatting date with strftime pattern."""
        dt = datetime.datetime(2025, 1, 15, 14, 30, 0, tzinfo=datetime.timezone.utc)
        options = EnexOptions(date_format_mode="strftime", date_strftime_pattern="%Y-%m-%d")
        result = _format_enex_date(dt, options)

        assert result == "2025-01-15"

    def test_format_enex_date_none(self) -> None:
        """Test formatting None date."""
        options = EnexOptions()
        result = _format_enex_date(None, options)

        assert result == ""


class TestEnexOptionsValidation:
    """Test EnexOptions validation."""

    def test_valid_note_title_level(self) -> None:
        """Test valid note title levels."""
        for level in range(1, 7):
            options = EnexOptions(note_title_level=level)
            assert options.note_title_level == level

    def test_invalid_note_title_level_low(self) -> None:
        """Test invalid note title level (too low)."""
        with pytest.raises(ValueError, match="note_title_level must be between 1 and 6"):
            EnexOptions(note_title_level=0)

    def test_invalid_note_title_level_high(self) -> None:
        """Test invalid note title level (too high)."""
        with pytest.raises(ValueError, match="note_title_level must be between 1 and 6"):
            EnexOptions(note_title_level=7)

    def test_empty_strftime_pattern(self) -> None:
        """Test empty strftime pattern with strftime mode."""
        with pytest.raises(ValueError, match="date_strftime_pattern cannot be empty"):
            EnexOptions(date_format_mode="strftime", date_strftime_pattern="")


class TestEnexParserBasic:
    """Test basic ENEX parsing functionality."""

    def test_parse_simple_note_from_file(self, tmp_path) -> None:
        """Test parsing simple note from file path."""
        enex_path = generate_simple_note_enex(tmp_path)

        parser = EnexToAstConverter()
        doc = parser.parse(enex_path)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Check for title heading
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) > 0
        assert any("Test Note" in str(h.content) for h in headings)

    def test_parse_simple_note_from_bytes(self, tmp_path) -> None:
        """Test parsing simple note from bytes."""
        enex_path = generate_simple_note_enex(tmp_path)
        enex_bytes = enex_path.read_bytes()

        parser = EnexToAstConverter()
        doc = parser.parse(enex_bytes)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

    def test_parse_simple_note_from_stream(self, tmp_path) -> None:
        """Test parsing simple note from file-like object."""
        enex_path = generate_simple_note_enex(tmp_path)
        enex_bytes = enex_path.read_bytes()

        parser = EnexToAstConverter()
        doc = parser.parse(BytesIO(enex_bytes))

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

    def test_parse_multiple_notes(self, tmp_path) -> None:
        """Test parsing file with multiple notes."""
        enex_path = generate_multiple_notes_enex(tmp_path)

        parser = EnexToAstConverter()
        doc = parser.parse(enex_path)

        assert isinstance(doc, Document)

        # Should have multiple headings (one per note)
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) >= 3  # At least 3 notes

        # Check for note titles
        heading_texts = [str(h.content) for h in headings]
        assert any("First Note" in text for text in heading_texts)
        assert any("Second Note" in text for text in heading_texts)
        assert any("Third Note" in text for text in heading_texts)

    def test_parse_empty_note(self, tmp_path) -> None:
        """Test parsing note with no content."""
        enex_path = generate_empty_note_enex(tmp_path)

        parser = EnexToAstConverter()
        doc = parser.parse(enex_path)

        assert isinstance(doc, Document)
        # Should still have a heading for the note title
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) > 0


class TestEnexParserOptions:
    """Test ENEX parsing with different options."""

    def test_include_note_metadata(self, tmp_path) -> None:
        """Test including note metadata."""
        enex_path = generate_simple_note_enex(tmp_path)

        options = EnexOptions(include_note_metadata=True)
        parser = EnexToAstConverter(options=options)
        doc = parser.parse(enex_path)

        # Check for metadata paragraph (should contain "Created" or "Updated")
        paragraphs = [node for node in doc.children if isinstance(node, Paragraph)]
        has_metadata = any("Created" in str(p.content) or "Updated" in str(p.content) for p in paragraphs)
        assert has_metadata

    def test_exclude_note_metadata(self, tmp_path) -> None:
        """Test excluding note metadata."""
        enex_path = generate_simple_note_enex(tmp_path)

        options = EnexOptions(include_note_metadata=False)
        parser = EnexToAstConverter(options=options)
        doc = parser.parse(enex_path)

        # Metadata paragraphs should not be present
        paragraphs = [node for node in doc.children if isinstance(node, Paragraph)]
        has_metadata = any("Created:" in str(p.content) or "Updated:" in str(p.content) for p in paragraphs)
        assert not has_metadata

    def test_include_tags_inline(self, tmp_path) -> None:
        """Test including tags in inline format."""
        enex_path = generate_simple_note_enex(tmp_path)

        options = EnexOptions(include_tags=True, tags_format="inline")
        parser = EnexToAstConverter(options=options)
        doc = parser.parse(enex_path)

        # Check for tags paragraph
        paragraphs = [node for node in doc.children if isinstance(node, Paragraph)]
        has_tags = any("Tags:" in str(p.content) for p in paragraphs)
        assert has_tags

    def test_skip_tags(self, tmp_path) -> None:
        """Test skipping tags."""
        enex_path = generate_simple_note_enex(tmp_path)

        options = EnexOptions(tags_format="skip")
        parser = EnexToAstConverter(options=options)
        doc = parser.parse(enex_path)

        # Tags should not be present
        paragraphs = [node for node in doc.children if isinstance(node, Paragraph)]
        has_tags = any("Tags:" in str(p.content) for p in paragraphs)
        assert not has_tags

    def test_note_title_level(self, tmp_path) -> None:
        """Test custom note title heading level."""
        enex_path = generate_simple_note_enex(tmp_path)

        options = EnexOptions(note_title_level=2)
        parser = EnexToAstConverter(options=options)
        doc = parser.parse(enex_path)

        # Find note title heading
        headings = [node for node in doc.children if isinstance(node, Heading)]
        note_headings = [h for h in headings if "Test Note" in str(h.content)]
        assert len(note_headings) > 0
        assert note_headings[0].level == 2

    def test_sort_notes_by_title(self, tmp_path) -> None:
        """Test sorting notes by title."""
        enex_path = generate_multiple_notes_enex(tmp_path)

        options = EnexOptions(sort_notes_by="title")
        parser = EnexToAstConverter(options=options)
        doc = parser.parse(enex_path)

        # Extract note titles in order
        headings = [node for node in doc.children if isinstance(node, Heading)]
        # Filter to get main note headings (not metadata headings)
        note_headings = [h for h in headings if any(title in str(h.content) for title in ["First", "Second", "Third"])]

        # Should be alphabetically sorted: First, Second, Third
        assert len(note_headings) >= 3
        titles = [str(h.content) for h in note_headings]
        # "First" should come before "Second" which should come before "Third" alphabetically
        first_idx = next(i for i, t in enumerate(titles) if "First" in t)
        second_idx = next(i for i, t in enumerate(titles) if "Second" in t)
        third_idx = next(i for i, t in enumerate(titles) if "Third" in t)
        assert first_idx < second_idx < third_idx


class TestEnexParserAttachments:
    """Test ENEX parsing with attachments."""

    def test_parse_note_with_image(self, tmp_path) -> None:
        """Test parsing note with embedded image."""
        enex_path = generate_note_with_image_enex(tmp_path)

        options = EnexOptions(attachment_mode="alt_text")
        parser = EnexToAstConverter(options=options)
        doc = parser.parse(enex_path)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Should have parsed successfully
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert any("Image" in str(h.content) for h in headings)


class TestEnexParserTableHandling:
    """Test ENEX parsing with tables."""

    def test_parse_note_with_table(self, tmp_path) -> None:
        """Test parsing note with table."""
        enex_path = generate_note_with_table_enex(tmp_path)

        parser = EnexToAstConverter()
        doc = parser.parse(enex_path)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Should have parsed successfully
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert any("Table" in str(h.content) for h in headings)


class TestEnexParserMetadata:
    """Test ENEX metadata extraction."""

    def test_extract_metadata_from_simple_note(self, tmp_path) -> None:
        """Test extracting metadata from ENEX file."""
        enex_path = generate_simple_note_enex(tmp_path)

        parser = EnexToAstConverter()
        doc = parser.parse(enex_path)

        metadata = doc.metadata
        assert metadata is not None
        assert "note_count" in metadata
        assert metadata["note_count"] == 1
        assert "title" in metadata
        assert metadata["title"] == "Test Note"

    def test_extract_metadata_tags(self, tmp_path) -> None:
        """Test extracting aggregated tags from metadata."""
        enex_path = generate_multiple_notes_enex(tmp_path)

        parser = EnexToAstConverter()
        doc = parser.parse(enex_path)

        metadata = doc.metadata
        assert metadata is not None
        assert "keywords" in metadata
        # Should have aggregated all tags from all notes
        keywords = metadata["keywords"]
        assert isinstance(keywords, list)
        assert len(keywords) > 0


class TestEnexParserErrorHandling:
    """Test ENEX parser error handling."""

    def test_parse_invalid_xml(self, tmp_path) -> None:
        """Test parsing invalid XML."""
        enex_path = tmp_path / "invalid.enex"
        enex_path.write_text("<invalid xml", encoding="utf-8")

        parser = EnexToAstConverter()
        with pytest.raises(MalformedFileError):
            parser.parse(enex_path)

    def test_parse_wrong_root_element(self, tmp_path) -> None:
        """Test parsing XML with wrong root element."""
        enex_path = tmp_path / "wrong_root.enex"
        enex_path.write_text('<?xml version="1.0"?><wrong-root></wrong-root>', encoding="utf-8")

        parser = EnexToAstConverter()
        with pytest.raises(MalformedFileError, match="expected <en-export> root element"):
            parser.parse(enex_path)

    def test_parse_empty_enex(self, tmp_path) -> None:
        """Test parsing ENEX with no notes."""
        enex_path = tmp_path / "empty.enex"
        content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">
<en-export export-date="20250128T120000Z" application="Evernote" version="10.0">
</en-export>"""
        enex_path.write_text(content, encoding="utf-8")

        parser = EnexToAstConverter()
        doc = parser.parse(enex_path)

        # Should return empty document
        assert isinstance(doc, Document)
        # May have no children or only separators
        assert len(doc.children) == 0 or all(isinstance(node, ThematicBreak) for node in doc.children)
