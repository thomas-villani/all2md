#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/parsers/test_mbox_conversion.py
"""Integration tests for MBOX mailbox archive conversion.

Tests cover:
- Basic MBOX parsing and conversion to Markdown
- Message filtering (date range, max messages)
- Output structure (flat vs hierarchical)
- Thread handling
- Real-world mailbox scenarios
"""

import datetime

import pytest

from all2md import to_markdown
from all2md.ast import Document, Heading, ThematicBreak
from all2md.options.mbox import MboxOptions
from all2md.parsers.mbox import MboxToAstConverter


@pytest.fixture
def simple_mbox_file(tmp_path):
    """Create a simple MBOX file for testing."""
    from tests.fixtures.generators.mbox_fixtures import create_simple_mbox, write_mbox_to_file

    mbox = create_simple_mbox()
    mbox_path = tmp_path / "test.mbox"
    write_mbox_to_file(mbox, str(mbox_path))
    return mbox_path


@pytest.fixture
def thread_mbox_file(tmp_path):
    """Create a threaded MBOX file for testing."""
    from tests.fixtures.generators.mbox_fixtures import create_mbox_with_thread, write_mbox_to_file

    mbox = create_mbox_with_thread()
    mbox_path = tmp_path / "thread.mbox"
    write_mbox_to_file(mbox, str(mbox_path))
    return mbox_path


@pytest.mark.integration
class TestMboxBasicConversion:
    """Test basic MBOX parsing and conversion."""

    def test_parse_simple_mbox(self, simple_mbox_file):
        """Test parsing a simple MBOX file."""
        parser = MboxToAstConverter()
        doc = parser.parse(simple_mbox_file)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Should have headings for messages
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) > 0

        # Should have thematic breaks between messages
        breaks = [node for node in doc.children if isinstance(node, ThematicBreak)]
        assert len(breaks) >= 3  # 3 messages = 3 breaks

    def test_convert_mbox_to_markdown(self, simple_mbox_file):
        """Test converting MBOX to Markdown."""
        markdown = to_markdown(simple_mbox_file)

        assert isinstance(markdown, str)
        assert len(markdown) > 0

        # Should contain message subjects
        assert "Welcome to the Team" in markdown
        assert "Project Kickoff Meeting" in markdown
        assert "Quarterly Review Results" in markdown

        # Should contain message separators
        assert "-----" in markdown or "---" in markdown

    def test_mbox_metadata_extraction(self, simple_mbox_file):
        """Test that metadata is properly extracted."""
        parser = MboxToAstConverter()
        doc = parser.parse(simple_mbox_file)

        assert "mailbox_format" in doc.metadata
        assert "message_count" in doc.metadata
        assert doc.metadata["message_count"] == 3


@pytest.mark.integration
class TestMboxMessageFiltering:
    """Test message filtering options."""

    def test_max_messages_limit(self, simple_mbox_file):
        """Test limiting the number of messages processed."""
        options = MboxOptions(max_messages=2)
        parser = MboxToAstConverter(options=options)
        doc = parser.parse(simple_mbox_file)

        # Count thematic breaks (one per message)
        breaks = [node for node in doc.children if isinstance(node, ThematicBreak)]
        assert len(breaks) == 2  # Should only process 2 messages

    def test_date_range_filtering(self, simple_mbox_file):
        """Test filtering messages by date range."""
        # Filter to only messages from February onwards
        options = MboxOptions(
            date_range_start=datetime.datetime(2024, 2, 1, tzinfo=datetime.timezone.utc),
        )
        markdown = to_markdown(simple_mbox_file, parser_options=options)

        # Should include February and March messages
        assert "Project Kickoff Meeting" in markdown
        assert "Quarterly Review Results" in markdown

        # Should NOT include January message
        assert "Welcome to the Team" not in markdown

    def test_date_range_end_filtering(self, simple_mbox_file):
        """Test filtering messages by end date."""
        # Filter to only messages before March
        options = MboxOptions(
            date_range_end=datetime.datetime(2024, 2, 28, tzinfo=datetime.timezone.utc),
        )
        markdown = to_markdown(simple_mbox_file, parser_options=options)

        # Should include January and February messages
        assert "Welcome to the Team" in markdown
        assert "Project Kickoff Meeting" in markdown

        # Should NOT include March message
        assert "Quarterly Review Results" not in markdown


@pytest.mark.integration
class TestMboxOutputStructure:
    """Test different output structure modes."""

    def test_flat_output_structure(self, simple_mbox_file):
        """Test flat output structure (all messages sequentially)."""
        options = MboxOptions(output_structure="flat")
        markdown = to_markdown(simple_mbox_file, parser_options=options)

        # All messages should be at H1 level
        assert markdown.count("# ") >= 3  # At least 3 H1 headings

    def test_header_inclusion(self, simple_mbox_file):
        """Test that email headers are included when requested."""
        options = MboxOptions(include_headers=True)
        markdown = to_markdown(simple_mbox_file, parser_options=options)

        # Should contain From: and To: headers
        assert "From:" in markdown
        assert "To:" in markdown
        assert "Date:" in markdown

    def test_header_exclusion(self, simple_mbox_file):
        """Test that email headers can be excluded."""
        options = MboxOptions(include_headers=False, subject_as_h1=True)
        markdown = to_markdown(simple_mbox_file, parser_options=options)

        # Should still have subjects as headings
        assert "Welcome to the Team" in markdown

        # But should NOT have From: To: headers
        assert "From:" not in markdown
        assert "To:" not in markdown


@pytest.mark.integration
class TestMboxThreadHandling:
    """Test handling of threaded conversations."""

    def test_parse_threaded_mbox(self, thread_mbox_file):
        """Test parsing a mailbox with threaded conversation."""
        parser = MboxToAstConverter()
        doc = parser.parse(thread_mbox_file)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Should have 3 messages in thread
        breaks = [node for node in doc.children if isinstance(node, ThematicBreak)]
        assert len(breaks) == 3

    def test_thread_message_order(self, thread_mbox_file):
        """Test that messages are ordered chronologically."""
        options = MboxOptions(sort_order="asc")
        markdown = to_markdown(thread_mbox_file, parser_options=options)

        # Find positions of message subjects
        original_pos = markdown.find("Bug in Production")
        reply1_pos = markdown.find("Looking into it now")
        reply2_pos = markdown.find("Fix deployed")

        # Messages should appear in chronological order
        assert original_pos < reply1_pos < reply2_pos

    def test_thread_reverse_order(self, thread_mbox_file):
        """Test reverse chronological order."""
        options = MboxOptions(sort_order="desc")
        markdown = to_markdown(thread_mbox_file, parser_options=options)

        # Find positions of unique message content
        original_content_pos = markdown.find("critical bug in the payment flow")
        reply2_content_pos = markdown.find("Fix deployed")

        # Newest should come first (Fix deployed is the last/newest message)
        assert reply2_content_pos < original_content_pos


@pytest.mark.integration
class TestMboxFormats:
    """Test different mailbox formats."""

    def test_auto_format_detection(self, simple_mbox_file):
        """Test automatic format detection."""
        options = MboxOptions(mailbox_format="auto")
        markdown = to_markdown(simple_mbox_file, parser_options=options)

        assert len(markdown) > 0
        assert "Welcome to the Team" in markdown

    def test_explicit_mbox_format(self, simple_mbox_file):
        """Test explicit mbox format specification."""
        options = MboxOptions(mailbox_format="mbox")
        markdown = to_markdown(simple_mbox_file, parser_options=options)

        assert len(markdown) > 0
        assert "Welcome to the Team" in markdown


@pytest.mark.integration
class TestMboxEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_mailbox(self, tmp_path):
        """Test parsing an empty mailbox."""
        import mailbox

        empty_mbox_path = tmp_path / "empty.mbox"
        mbox = mailbox.mbox(str(empty_mbox_path))
        mbox.close()

        parser = MboxToAstConverter()
        doc = parser.parse(empty_mbox_path)

        assert isinstance(doc, Document)
        # Should have minimal or no content
        assert len(doc.children) <= 1  # Might have empty structure

    def test_nonexistent_file(self, tmp_path):
        """Test that nonexistent file raises appropriate error."""
        from all2md.exceptions import ValidationError

        parser = MboxToAstConverter()
        nonexistent = tmp_path / "nonexistent.mbox"

        with pytest.raises(ValidationError):
            parser.parse(nonexistent)

    def test_io_stream_not_supported(self):
        """Test that IO streams are not supported."""
        import io

        from all2md.exceptions import ValidationError

        parser = MboxToAstConverter()

        with pytest.raises(ValidationError, match="IO streams"):
            parser.parse(io.BytesIO(b"test"))


@pytest.mark.integration
class TestMboxDateFormatting:
    """Test date formatting options."""

    def test_iso8601_date_format(self, simple_mbox_file):
        """Test ISO 8601 date formatting."""
        options = MboxOptions(
            date_format_mode="iso8601",
            include_headers=True,
        )
        markdown = to_markdown(simple_mbox_file, parser_options=options)

        # Should contain ISO 8601 formatted dates
        assert "2024-" in markdown  # Year format
        assert "T" in markdown or "Date:" in markdown  # ISO format has T separator

    def test_custom_strftime_format(self, simple_mbox_file):
        """Test custom strftime date formatting."""
        options = MboxOptions(
            date_format_mode="strftime",
            date_strftime_pattern="%Y-%m-%d",
            include_headers=True,
        )
        markdown = to_markdown(simple_mbox_file, parser_options=options)

        # Should contain custom formatted dates
        assert "2024-" in markdown
