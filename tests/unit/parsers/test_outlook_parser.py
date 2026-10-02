#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for Outlook parser.

Tests the Outlook (MSG/PST/OST) parser with various configurations.
"""

import datetime

import pytest

from all2md.options.outlook import OutlookOptions
from all2md.parsers.outlook import _detect_outlook_format, _filter_message


class TestOutlookFormatDetection:
    """Test Outlook format detection."""

    def test_detect_msg_from_extension(self, tmp_path):
        """Test detection of MSG format from file extension."""
        msg_file = tmp_path / "test.msg"
        msg_file.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100)

        assert _detect_outlook_format(msg_file) == "msg"

    def test_detect_pst_from_extension(self, tmp_path):
        """Test detection of PST format from file extension."""
        pst_file = tmp_path / "test.pst"
        pst_file.write_bytes(b"!BDN" + b"\x00" * 100)

        assert _detect_outlook_format(pst_file) == "pst"

    def test_detect_ost_from_extension(self, tmp_path):
        """Test detection of OST format from file extension."""
        ost_file = tmp_path / "test.ost"
        ost_file.write_bytes(b"!BDN" + b"\x00" * 100)

        assert _detect_outlook_format(ost_file) == "ost"

    def test_detect_msg_from_magic_bytes(self):
        """Test detection of MSG format from magic bytes."""
        # OLE/CFBF magic bytes
        magic = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        assert _detect_outlook_format(magic) == "msg"

    def test_detect_pst_from_magic_bytes(self):
        """Test detection of PST format from magic bytes."""
        # PST magic bytes
        magic = b"!BDN\x00\x00\x00\x00"
        assert _detect_outlook_format(magic) == "pst"


class TestOutlookMessageFiltering:
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
        options = OutlookOptions()
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
        options = OutlookOptions(
            date_range_start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            date_range_end=datetime.datetime(2024, 12, 31, tzinfo=datetime.timezone.utc),
        )
        assert _filter_message(msg_data, options) is True

        # Message should not pass when before range
        options = OutlookOptions(
            date_range_start=datetime.datetime(2024, 7, 1, tzinfo=datetime.timezone.utc),
        )
        assert _filter_message(msg_data, options) is False

        # Message should not pass when after range
        options = OutlookOptions(
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

        options = OutlookOptions(
            date_range_start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )
        assert _filter_message(msg_data, options) is False


class TestOutlookOptions:
    """Test Outlook options validation."""

    def test_default_options(self):
        """Test default Outlook options."""
        options = OutlookOptions()
        assert options.output_structure == "flat"
        assert options.max_messages is None
        assert options.date_range_start is None
        assert options.date_range_end is None
        assert options.folder_filter is None
        assert options.skip_folders == ["Deleted Items", "Junk Email", "Trash", "Drafts"]
        assert options.include_subfolders is True

    def test_invalid_date_range(self):
        """Test that invalid date range raises ValueError."""
        with pytest.raises(ValueError, match="date_range_start must be before"):
            OutlookOptions(
                date_range_start=datetime.datetime(2024, 12, 31, tzinfo=datetime.timezone.utc),
                date_range_end=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            )

    def test_invalid_max_messages(self):
        """Test that invalid max_messages raises ValueError."""
        with pytest.raises(ValueError, match="max_messages must be a positive integer"):
            OutlookOptions(max_messages=0)

        with pytest.raises(ValueError, match="max_messages must be a positive integer"):
            OutlookOptions(max_messages=-1)

    def test_folder_filter_defensive_copy(self):
        """Test that folder_filter is defensively copied."""
        original_list = ["Inbox", "Sent Items"]
        options = OutlookOptions(folder_filter=original_list)

        # Modifying original should not affect options
        original_list.append("Drafts")
        assert len(options.folder_filter) == 2

    def test_skip_folders_defensive_copy(self):
        """Test that skip_folders is defensively copied."""
        original_list = ["Deleted Items"]
        options = OutlookOptions(skip_folders=original_list)

        # Modifying original should not affect options
        original_list.append("Junk Email")
        assert len(options.skip_folders) == 1

    def test_empty_skip_folders(self):
        """Test that skip_folders can be set to empty list."""
        options = OutlookOptions(skip_folders=[])
        assert options.skip_folders == []


class TestOutlookParser:
    """Test Outlook parser functionality."""

    def test_parse_msg_requires_extract_msg(self, tmp_path):
        """Test that parsing MSG requires extract-msg dependency."""
        pytest.importorskip("extract_msg", reason="extract-msg not installed")

        from all2md.parsers.outlook import OutlookToAstConverter

        # Create a dummy MSG file (won't actually parse, just test dependency check)
        msg_file = tmp_path / "test.msg"
        msg_file.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100)

        parser = OutlookToAstConverter()

        # This should require extract-msg and fail if not present
        # We can't test full MSG parsing without a real MSG file
        # So we just verify the parser can be instantiated
        assert parser is not None

    def test_parse_pst_requires_pypff(self, tmp_path):
        """Test that parsing PST requires pypff dependency."""
        pytest.importorskip("extract_msg", reason="extract-msg not installed")

        from all2md.exceptions import DependencyError
        from all2md.parsers.outlook import OutlookToAstConverter

        # Create a dummy PST file
        pst_file = tmp_path / "test.pst"
        pst_file.write_bytes(b"!BDN" + b"\x00" * 100)

        parser = OutlookToAstConverter()

        # Try to parse PST - should raise DependencyError if pypff not available
        import importlib.util

        if importlib.util.find_spec("pypff") is not None:
            # pypff is available, skip this test
            pytest.skip("pypff is installed, cannot test missing dependency error")
        else:
            # pypff not available - should get clear error message
            with pytest.raises(DependencyError) as exc_info:
                parser.parse(pst_file)

            assert "libpff-python" in str(exc_info.value).lower()

    def test_metadata_extraction(self):
        """Test metadata extraction from Outlook file."""
        pytest.importorskip("extract_msg", reason="extract-msg not installed")

        from all2md.parsers.outlook import OutlookToAstConverter

        parser = OutlookToAstConverter()
        metadata = parser.extract_metadata({"format": "msg", "message_count": 1})

        assert metadata.custom["outlook_format"] == "msg"
        assert metadata.custom["message_count"] == 1


@pytest.mark.unit
class TestOutlookMessageNodes:
    r"""``_add_message_nodes`` must honour ``content_is_markdown`` and attachment nodes.

    The Outlook path flattened every body into ``Paragraph(content=[Text(...)])``
    and appended the attachment section's Markdown to the body string, so the
    renderer escaped both -- ``\## Heading`` for an RTF/HTML-converted body and
    ``\## Attachments`` for the attachment section. The .eml parser already
    honoured the body flag; this asserts the Outlook path now matches it.
    """

    def _render(self, children) -> str:
        from all2md.ast import Document
        from all2md.renderers.markdown import MarkdownRenderer

        return MarkdownRenderer().render_to_string(Document(children=children))

    def test_markdown_body_becomes_rich_nodes(self):
        """A body flagged ``content_is_markdown`` is re-parsed into real headings/links."""
        from all2md.parsers.outlook import OutlookToAstConverter

        parser = OutlookToAstConverter(OutlookOptions(subject_as_h1=False, include_headers=False))
        children = []
        parser._add_message_nodes(
            children,
            {
                "content": "## Heading\n\nSee [site](https://example.com).",
                "content_is_markdown": True,
            },
            heading_level=1,
        )
        markdown = self._render(children)

        assert "## Heading" in markdown
        assert "[site](https://example.com)" in markdown
        assert r"\#\#" not in markdown
        assert r"\[site\]" not in markdown

    def test_plain_body_is_still_treated_as_plain_text(self):
        """Without the flag, Markdown-looking characters stay literal."""
        from all2md.parsers.outlook import OutlookToAstConverter

        parser = OutlookToAstConverter(OutlookOptions(subject_as_h1=False, include_headers=False))
        children = []
        parser._add_message_nodes(
            children,
            {"content": "## Not a heading", "content_is_markdown": False},
            heading_level=1,
        )

        assert r"\## Not a heading" in self._render(children)

    def test_attachment_nodes_are_emitted_after_the_body(self):
        """Attachment AST nodes render as a real heading and image, not escaped text."""
        from all2md.ast import Heading, Image, Paragraph, Text
        from all2md.parsers.outlook import OutlookToAstConverter

        parser = OutlookToAstConverter(OutlookOptions(subject_as_h1=False, include_headers=False))
        children = []
        parser._add_message_nodes(
            children,
            {
                "content": "Body text.",
                "attachment_nodes": [
                    Heading(level=2, content=[Text(content="Attachments")]),
                    Paragraph(content=[Image(url="https://example.com/pic.png", alt_text="pic.png")]),
                ],
            },
            heading_level=1,
        )
        markdown = self._render(children)

        assert "Body text." in markdown
        assert "## Attachments" in markdown
        assert "![pic.png](https://example.com/pic.png)" in markdown
        assert r"\##" not in markdown


def _fake_recipient(name, address, kind):
    """A recipient shaped like extract-msg's: ``type`` is an enum, not an int."""
    import types

    return types.SimpleNamespace(name=name, email=address, smtpAddress=address, type=types.SimpleNamespace(value=kind))


def _fake_message(**overrides):
    """A message exposing the attributes extract-msg 0.56 really has."""
    import types

    fields = {
        "sender": "Alice <alice@example.com>",
        "to": None,
        "cc": None,
        "recipients": [],
        "subject": "Subject",
        "date": None,
        "messageId": None,
        "body": "Plain body.",
        "htmlBody": None,
        "attachments": [],
    }
    fields.update(overrides)
    return types.SimpleNamespace(**fields)


@pytest.mark.unit
class TestExtractMsgApiContract:
    """The parser's view of extract-msg must match the installed library.

    The test stubs used to invent ``message_id`` and a ``str`` HTML body, so every
    real ``.msg`` failed with AttributeError while the suite passed.
    """

    def test_message_attributes_exist(self):
        extract_msg = pytest.importorskip("extract_msg")
        for attribute in ("sender", "subject", "date", "messageId", "body", "htmlBody", "recipients", "attachments"):
            assert hasattr(extract_msg.Message, attribute), attribute

    def test_recipient_type_values(self):
        pytest.importorskip("extract_msg")
        from extract_msg.enums import RecipientType

        assert (RecipientType.TO.value, RecipientType.CC.value) == (1, 2)


@pytest.mark.unit
class TestConvertMsgToEmailMessage:
    """extract-msg's message becomes the EmailMessage the EML pipeline reads."""

    def test_message_id_comes_from_message_id_attribute(self):
        from all2md.parsers.outlook import _convert_msg_to_email_message

        email_msg = _convert_msg_to_email_message(_fake_message(messageId="<abc@example.com>"))
        assert email_msg["Message-ID"] == "<abc@example.com>"

    def test_datetime_date(self):
        from all2md.parsers.outlook import _convert_msg_to_email_message

        sent = datetime.datetime(2026, 9, 30, 14, 5, tzinfo=datetime.timezone.utc)
        email_msg = _convert_msg_to_email_message(_fake_message(date=sent))
        assert email_msg["Date"].datetime == sent

    def test_string_date_kept(self):
        from all2md.parsers.outlook import _convert_msg_to_email_message

        email_msg = _convert_msg_to_email_message(_fake_message(date="Wed, 30 Sep 2026 14:05:00 +0000"))
        assert email_msg["Date"].datetime.day == 30

    def test_every_recipient_kept(self):
        """Joined with ``;``, all recipients after the first used to be dropped."""
        from all2md.parsers.outlook import _convert_msg_to_email_message

        recipients = [
            _fake_recipient("alice@example.com", None, 1),  # unresolved: the name is the address
            _fake_recipient("Bob Jones", "bob@example.com", 1),
            _fake_recipient("carol@example.com", "carol@example.com", 2),
            _fake_recipient("Hidden", "hidden@example.com", 3),  # Bcc is not shown
        ]
        email_msg = _convert_msg_to_email_message(
            _fake_message(recipients=recipients, to="alice@example.com <None>; Bob Jones <bob@example.com>")
        )
        assert str(email_msg["To"]) == "alice@example.com, Bob Jones <bob@example.com>"
        assert str(email_msg["Cc"]) == "carol@example.com"
        assert "hidden" not in str(email_msg).lower()

    def test_joined_strings_used_without_structured_recipients(self):
        from all2md.parsers.outlook import _convert_msg_to_email_message

        email_msg = _convert_msg_to_email_message(_fake_message(to="a@example.com; b@example.com"))
        assert str(email_msg["To"]) == "a@example.com, b@example.com"

    def test_html_body_bytes_kept_as_alternative(self):
        from all2md.parsers.outlook import _convert_msg_to_email_message

        email_msg = _convert_msg_to_email_message(_fake_message(htmlBody=b"<p>Caf\xc3\xa9 <b>bold</b></p>"))
        assert email_msg.get_content_type() == "multipart/alternative"
        html = email_msg.get_body(preferencelist=("html",))
        assert html is not None and "Café <b>bold</b>" in html.get_content()
        assert email_msg.get_body(preferencelist=("plain",)).get_content().strip() == "Plain body."

    def test_html_only_body_in_windows_1252(self):
        from all2md.parsers.outlook import _convert_msg_to_email_message

        email_msg = _convert_msg_to_email_message(_fake_message(body=None, htmlBody=b"<p>Caf\xe9</p>"))
        assert email_msg.get_content_type() == "text/html"
        assert "Café" in email_msg.get_content()

    def test_failing_html_body_logged_and_plain_kept(self, caplog):
        import types

        from all2md.parsers.outlook import _convert_msg_to_email_message

        class _Message(types.SimpleNamespace):
            @property
            def htmlBody(self):
                raise AttributeError("'bytes' object has no attribute 'encode'")

        fields = vars(_fake_message())
        del fields["htmlBody"]
        with caplog.at_level("WARNING", logger="all2md.parsers.outlook"):
            email_msg = _convert_msg_to_email_message(_Message(**fields))
        assert email_msg.get_content().strip() == "Plain body."
        assert "HTML body" in caplog.text

    def test_html_route_through_eml_options(self):
        from all2md.parsers.eml import extract_message_content
        from all2md.parsers.outlook import _convert_msg_to_email_message

        email_msg = _convert_msg_to_email_message(_fake_message(htmlBody=b"<h1>Title</h1><p>Text <b>bold</b></p>"))
        content, is_markdown = extract_message_content(
            email_msg, OutlookOptions(include_plain_parts=False, convert_html_to_markdown=True)
        )
        assert is_markdown and "# Title" in content and "**bold**" in content
