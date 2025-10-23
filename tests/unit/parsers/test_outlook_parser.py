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
        try:
            import pypff

            # pypff is available, skip this test
            pytest.skip("pypff is installed, cannot test missing dependency error")
        except ImportError:
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
