"""Integration tests for ENEX (Evernote Export) conversion."""

from fixtures.generators.enex_fixtures import (
    generate_multiple_notes_enex,
    generate_note_with_image_enex,
    generate_note_with_table_enex,
    generate_simple_note_enex,
)

from all2md.api import to_markdown
from all2md.options.enex import EnexOptions


class TestEnexToMarkdownConversion:
    """Test full ENEX to Markdown conversion."""

    def test_simple_note_to_markdown(self, tmp_path) -> None:
        """Test converting simple note to Markdown."""
        enex_path = generate_simple_note_enex(tmp_path)

        markdown = to_markdown(enex_path, source_format="enex")

        assert isinstance(markdown, str)
        assert len(markdown) > 0

        # Check for note title
        assert "Test Note" in markdown

        # Check for content
        assert "bold" in markdown or "**bold**" in markdown
        assert "italic" in markdown or "*italic*" in markdown

        # Check for link
        assert "example.com" in markdown

    def test_multiple_notes_to_markdown(self, tmp_path) -> None:
        """Test converting multiple notes to Markdown."""
        enex_path = generate_multiple_notes_enex(tmp_path)

        markdown = to_markdown(enex_path, source_format="enex")

        assert isinstance(markdown, str)
        assert len(markdown) > 0

        # All three notes should be present
        assert "First Note" in markdown
        assert "Second Note" in markdown
        assert "Third Note" in markdown

    def test_note_with_metadata(self, tmp_path) -> None:
        """Test converting note with metadata included."""
        enex_path = generate_simple_note_enex(tmp_path)

        options = EnexOptions(include_note_metadata=True)
        markdown = to_markdown(enex_path, source_format="enex", parser_options=options)

        assert isinstance(markdown, str)
        assert "Created:" in markdown or "Updated:" in markdown

    def test_note_with_tags(self, tmp_path) -> None:
        """Test converting note with tags."""
        enex_path = generate_simple_note_enex(tmp_path)

        options = EnexOptions(include_tags=True, tags_format="inline")
        markdown = to_markdown(enex_path, source_format="enex", parser_options=options)

        assert isinstance(markdown, str)
        assert "Tags:" in markdown
        # Should include the test tags
        assert "test" in markdown or "example" in markdown

    def test_note_with_image(self, tmp_path) -> None:
        """Test converting note with embedded image."""
        enex_path = generate_note_with_image_enex(tmp_path)

        options = EnexOptions(attachment_mode="alt_text")
        markdown = to_markdown(enex_path, source_format="enex", parser_options=options)

        assert isinstance(markdown, str)
        assert len(markdown) > 0

        # Should have note title
        assert "Image" in markdown

    def test_note_with_table(self, tmp_path) -> None:
        """Test converting note with table."""
        enex_path = generate_note_with_table_enex(tmp_path)

        markdown = to_markdown(enex_path, source_format="enex")

        assert isinstance(markdown, str)
        assert len(markdown) > 0

        # Should have table content
        assert "Header 1" in markdown or "Cell 1" in markdown

    def test_sorted_notes(self, tmp_path) -> None:
        """Test converting notes with sorting."""
        enex_path = generate_multiple_notes_enex(tmp_path)

        options = EnexOptions(sort_notes_by="title")
        markdown = to_markdown(enex_path, source_format="enex", parser_options=options)

        assert isinstance(markdown, str)

        # Check order: First should appear before Second which should appear before Third
        first_pos = markdown.find("First Note")
        second_pos = markdown.find("Second Note")
        third_pos = markdown.find("Third Note")

        assert first_pos < second_pos < third_pos
