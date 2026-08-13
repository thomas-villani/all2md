#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for MBOX parser.

Tests the MBOX mailbox archive parser with various configurations.
"""

import datetime
import mailbox

import pytest

from all2md.ast import Document, Heading, Text, ThematicBreak
from all2md.options.mbox import MboxOptions
from all2md.parsers.mbox import MboxToAstConverter, _detect_mailbox_format, _filter_message, _get_mailbox_class


class TestMboxFormatDetection:
    """Test mailbox format detection."""

    def test_detect_mbox_from_magic_bytes(self, tmp_path):
        """Test detection of mbox format from magic bytes."""
        # Create a simple mbox file
        mbox_file = tmp_path / "test.mbox"
        mbox_file.write_text("From test@example.com Mon Jan 01 00:00:00 2024\n\nTest message\n")

        assert _detect_mailbox_format(mbox_file) == "mbox"

    def test_detect_maildir_from_structure(self, tmp_path):
        """Test detection of maildir format from directory structure."""
        # Create maildir structure
        maildir = tmp_path / "maildir"
        maildir.mkdir()
        (maildir / "cur").mkdir()
        (maildir / "new").mkdir()
        (maildir / "tmp").mkdir()

        assert _detect_mailbox_format(maildir) == "maildir"

    def test_get_mailbox_class(self):
        """Test getting mailbox class for format."""
        assert _get_mailbox_class("mbox") == mailbox.mbox
        assert _get_mailbox_class("maildir") == mailbox.Maildir
        assert _get_mailbox_class("mh") == mailbox.MH
        assert _get_mailbox_class("babyl") == mailbox.Babyl
        assert _get_mailbox_class("mmdf") == mailbox.MMDF


class TestMboxMessageFiltering:
    """Test message filtering logic."""

    def test_filter_message_no_filters(self):
        """Test that messages pass when no filters are set."""
        msg_data = {
            "from": "test@example.com",
            "to": "recipient@example.com",
            "subject": "Test",
            "date": datetime.datetime(2024, 6, 15, tzinfo=datetime.timezone.utc),
            "content": "Test content",
        }
        options = MboxOptions()
        assert _filter_message(msg_data, options) is True

    def test_filter_message_by_date_range(self):
        """Test filtering messages by date range."""
        msg_data = {
            "from": "test@example.com",
            "to": "recipient@example.com",
            "subject": "Test",
            "date": datetime.datetime(2024, 6, 15, tzinfo=datetime.timezone.utc),
            "content": "Test content",
        }

        # Message should pass when in range
        options = MboxOptions(
            date_range_start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            date_range_end=datetime.datetime(2024, 12, 31, tzinfo=datetime.timezone.utc),
        )
        assert _filter_message(msg_data, options) is True

        # Message should not pass when before range
        options = MboxOptions(
            date_range_start=datetime.datetime(2024, 7, 1, tzinfo=datetime.timezone.utc),
        )
        assert _filter_message(msg_data, options) is False

        # Message should not pass when after range
        options = MboxOptions(
            date_range_end=datetime.datetime(2024, 6, 1, tzinfo=datetime.timezone.utc),
        )
        assert _filter_message(msg_data, options) is False

    def test_filter_message_without_date(self):
        """Test that messages without dates are filtered out when date filtering is active."""
        msg_data = {
            "from": "test@example.com",
            "to": "recipient@example.com",
            "subject": "Test",
            "date": None,
            "content": "Test content",
        }

        options = MboxOptions(
            date_range_start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )
        assert _filter_message(msg_data, options) is False


class TestMboxOptions:
    """Test MBOX options validation."""

    def test_default_options(self):
        """Test default MBOX options."""
        options = MboxOptions()
        assert options.mailbox_format == "auto"
        assert options.output_structure == "flat"
        assert options.max_messages is None
        assert options.date_range_start is None
        assert options.date_range_end is None
        assert options.folder_filter is None

    def test_invalid_date_range(self):
        """Test that invalid date range raises ValueError."""
        with pytest.raises(ValueError, match="date_range_start must be before"):
            MboxOptions(
                date_range_start=datetime.datetime(2024, 12, 31, tzinfo=datetime.timezone.utc),
                date_range_end=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            )

    def test_invalid_max_messages(self):
        """Test that invalid max_messages raises ValueError."""
        with pytest.raises(ValueError, match="max_messages must be a positive integer"):
            MboxOptions(max_messages=0)

        with pytest.raises(ValueError, match="max_messages must be a positive integer"):
            MboxOptions(max_messages=-1)

    def test_folder_filter_defensive_copy(self):
        """Test that folder_filter is defensively copied."""
        original_list = ["folder1", "folder2"]
        options = MboxOptions(folder_filter=original_list)

        # Modifying original should not affect options
        original_list.append("folder3")
        assert len(options.folder_filter) == 2


class TestMboxParser:
    """Test MBOX parser functionality."""

    def test_parse_simple_mbox(self, tmp_path):
        """Test parsing a simple mbox file."""
        # Create a simple mbox file with one message
        mbox_file = tmp_path / "test.mbox"
        mbox_content = """From test@example.com Mon Jan 01 00:00:00 2024
From: test@example.com
To: recipient@example.com
Subject: Test Message
Date: Mon, 01 Jan 2024 12:00:00 +0000

This is a test message.
"""
        mbox_file.write_text(mbox_content)

        # Parse
        parser = MboxToAstConverter()
        doc = parser.parse(mbox_file)

        # Verify
        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Check for subject heading
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) > 0
        assert any("Test Message" in h.content[0].content for h in headings if isinstance(h.content[0], Text))

    def test_parse_with_max_messages_limit(self, tmp_path):
        """Test parsing with max_messages limit."""
        # Create mbox with 3 messages
        mbox_file = tmp_path / "test.mbox"
        mbox = mailbox.mbox(str(mbox_file))

        for i in range(3):
            msg = mailbox.mboxMessage()
            msg["From"] = f"sender{i}@example.com"
            msg["To"] = "recipient@example.com"
            msg["Subject"] = f"Message {i}"
            msg.set_payload(f"Content {i}")
            mbox.add(msg)

        mbox.close()

        # Parse with limit of 2
        parser = MboxToAstConverter(options=MboxOptions(max_messages=2))
        doc = parser.parse(mbox_file)

        # Count message separators (ThematicBreak) - should be 2 (one per message)
        breaks = [node for node in doc.children if isinstance(node, ThematicBreak)]
        assert len(breaks) == 2

    def test_parse_hierarchical_output(self, tmp_path):
        """Test parsing with hierarchical output structure."""
        # Create maildir with folders
        maildir_path = tmp_path / "maildir"
        mbox = mailbox.Maildir(str(maildir_path))

        # Add message to inbox
        msg = mailbox.MaildirMessage()
        msg["From"] = "sender@example.com"
        msg["To"] = "recipient@example.com"
        msg["Subject"] = "Inbox Message"
        msg.set_payload("Inbox content")
        mbox.add(msg)

        mbox.close()

        # Parse with hierarchical structure
        parser = MboxToAstConverter(options=MboxOptions(output_structure="hierarchical"))
        doc = parser.parse(maildir_path)

        # Verify hierarchical structure (should have folder heading at level 1)
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) > 0

        # First heading should be level 1 (folder name)
        assert headings[0].level == 1

    def test_parse_io_stream_raises_validation_error(self):
        """Test that parsing from IO stream raises ValidationError."""
        import io

        parser = MboxToAstConverter()

        with pytest.raises(Exception):  # Should raise ValidationError
            parser.parse(io.BytesIO(b"test"))

    def test_metadata_extraction(self, tmp_path):
        """Test metadata extraction from mbox."""
        # Create simple mbox
        mbox_file = tmp_path / "test.mbox"
        mbox = mailbox.mbox(str(mbox_file))
        msg = mailbox.mboxMessage()
        msg["From"] = "test@example.com"
        msg["Subject"] = "Test"
        msg.set_payload("Content")
        mbox.add(msg)
        mbox.close()

        # Parse
        parser = MboxToAstConverter()
        doc = parser.parse(mbox_file)

        # Check metadata
        assert "mailbox_format" in doc.metadata
        assert "message_count" in doc.metadata
        assert doc.metadata["message_count"] == 1


def _mbox_bytes(message_bytes: bytes) -> bytes:
    """Wrap a raw RFC-822 message in an mbox ``From `` envelope."""
    return b"From sender@example.com Mon Jan  1 00:00:00 2024\r\n" + message_bytes + b"\r\n"


@pytest.mark.unit
class TestMboxAttachmentAndMarkdownBodyParity:
    r"""The mbox path must agree with the .eml path on attachments and rich bodies.

    ``_process_single_message`` concatenated the attachment section's Markdown
    onto the body string, and ``_add_message_nodes`` flattened every body into
    ``Paragraph(content=[Text(...)])`` regardless of ``content_is_markdown``. The
    renderer then escaped both, producing ``\## Attachments`` and ``\*\*bold\*\*``
    where the .eml parser produced a real heading and real emphasis.
    """

    def _render(self, doc) -> str:
        from all2md.renderers.markdown import MarkdownRenderer

        return MarkdownRenderer().render_to_string(doc)

    def test_plain_body_attachment_is_not_escaped(self, tmp_path):
        """A plain-text body plus an attachment renders a real heading and image."""
        from tests.unit.parsers.test_eml_parser import _plain_email_with_png_attachment

        mbox_file = tmp_path / "test.mbox"
        mbox_file.write_bytes(_mbox_bytes(_plain_email_with_png_attachment()))

        doc = MboxToAstConverter(MboxOptions(attachment_mode="base64")).parse(mbox_file)
        markdown = self._render(doc)

        assert r"\##" not in markdown
        assert r"!\[" not in markdown
        assert "## Attachments" in markdown
        assert "![pic.png](data:image/png;base64," in markdown

    def test_attachment_output_matches_eml_path(self, tmp_path):
        """Same message, .eml parser vs mbox parser: identical attachment rendering."""
        from io import BytesIO

        from all2md.options import EmlOptions
        from all2md.parsers.eml import EmlToAstConverter
        from tests.unit.parsers.test_eml_parser import _plain_email_with_png_attachment

        raw = _plain_email_with_png_attachment()
        mbox_file = tmp_path / "test.mbox"
        mbox_file.write_bytes(_mbox_bytes(raw))

        eml_md = self._render(EmlToAstConverter(EmlOptions(attachment_mode="base64")).parse(BytesIO(raw)))
        mbox_md = self._render(MboxToAstConverter(MboxOptions(attachment_mode="base64")).parse(mbox_file))

        assert eml_md == mbox_md

    def test_rtf_body_renders_real_emphasis(self, tmp_path):
        r"""Default options: an RTF body's bold run survives as emphasis, not ``\*\*``."""
        from tests.unit.parsers.test_eml_parser import RTF_BODY_EMAIL

        mbox_file = tmp_path / "rtf.mbox"
        mbox_file.write_bytes(_mbox_bytes(RTF_BODY_EMAIL))

        markdown = self._render(MboxToAstConverter(MboxOptions()).parse(mbox_file))

        assert "**Bold heading**" in markdown
        assert r"\*\*" not in markdown

    def test_rtf_body_output_matches_eml_path(self, tmp_path):
        """Same RTF message, .eml parser vs mbox parser: identical body rendering."""
        from io import BytesIO

        from all2md.options import EmlOptions
        from all2md.parsers.eml import EmlToAstConverter
        from tests.unit.parsers.test_eml_parser import RTF_BODY_EMAIL

        mbox_file = tmp_path / "rtf.mbox"
        mbox_file.write_bytes(_mbox_bytes(RTF_BODY_EMAIL))

        eml_md = self._render(EmlToAstConverter(EmlOptions()).parse(BytesIO(RTF_BODY_EMAIL)))
        mbox_md = self._render(MboxToAstConverter(MboxOptions()).parse(mbox_file))

        assert eml_md == mbox_md
