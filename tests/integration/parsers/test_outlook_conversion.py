#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/parsers/test_outlook_conversion.py
"""Integration tests for Outlook (MSG/PST/OST) conversion.

Tests cover:
- Basic MSG parsing and conversion to Markdown
- Message filtering (date range, max messages, folders)
- Output structure (flat vs hierarchical)
- Real-world Outlook scenarios
- PST/OST handling (when pypff is available)

Note: These tests use EML files as proxies for MSG files since creating
real MSG files requires extract-msg which may not be installed in CI.
"""

import datetime
from pathlib import Path

import pytest

from all2md import to_markdown
from all2md.ast import Document, Heading
from all2md.options.outlook import OutlookOptions
from all2md.parsers.outlook import OutlookToAstConverter


@pytest.fixture
def msg_simple_file():
    """Get path to simple MSG fixture (stored as EML)."""
    # Use the generated fixture
    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "documents" / "generated" / "outlook-simple.eml"
    if fixture_path.exists():
        return fixture_path
    pytest.skip("Outlook simple fixture not generated")


@pytest.fixture
def msg_attachments_file():
    """Get path to MSG with attachments fixture (stored as EML)."""
    fixture_path = (
        Path(__file__).parent.parent.parent / "fixtures" / "documents" / "generated" / "outlook-attachments.eml"
    )
    if fixture_path.exists():
        return fixture_path
    pytest.skip("Outlook attachments fixture not generated")


@pytest.mark.integration
class TestOutlookBasicConversion:
    """Test basic Outlook MSG parsing and conversion."""

    @pytest.mark.skipif(
        not pytest.importorskip("extract_msg", reason="extract-msg not installed"),
        reason="extract-msg required for Outlook tests",
    )
    def test_parse_simple_msg(self, msg_simple_file):
        """Test parsing a simple MSG file."""
        # Note: This uses EML as proxy for MSG testing
        from all2md.parsers.eml import EmlToAstConverter

        parser = EmlToAstConverter()
        doc = parser.parse(msg_simple_file)

        assert isinstance(doc, Document)
        assert len(doc.children) > 0

        # Should have heading for message
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) > 0

    def test_convert_msg_to_markdown(self, msg_simple_file):
        """Test converting MSG to Markdown."""
        markdown = to_markdown(msg_simple_file)

        assert isinstance(markdown, str)
        assert len(markdown) > 0

        # Should contain message subject
        assert "Important Project Update" in markdown or "alice" in markdown.lower()

    @pytest.mark.skipif(
        not pytest.importorskip("extract_msg", reason="extract-msg not installed"),
        reason="extract-msg required",
    )
    def test_msg_metadata_extraction(self, msg_simple_file):
        """Test that metadata is properly extracted."""
        from all2md.parsers.eml import EmlToAstConverter

        parser = EmlToAstConverter()
        doc = parser.parse(msg_simple_file)

        assert "title" in doc.metadata or "author" in doc.metadata
        # Email metadata should be present in some form


@pytest.mark.integration
class TestOutlookOptions:
    """Test Outlook-specific options."""

    def test_default_skip_folders(self):
        """Test that default skip folders are configured."""
        options = OutlookOptions()

        assert "Deleted Items" in options.skip_folders
        assert "Junk Email" in options.skip_folders
        assert "Trash" in options.skip_folders

    def test_custom_skip_folders(self):
        """Test custom skip folders configuration."""
        options = OutlookOptions(skip_folders=["Drafts"])

        assert options.skip_folders == ["Drafts"]
        assert "Deleted Items" not in options.skip_folders

    def test_empty_skip_folders(self):
        """Test processing all folders with empty skip list."""
        options = OutlookOptions(skip_folders=[])

        assert options.skip_folders == []

    def test_folder_filter(self):
        """Test folder filtering configuration."""
        options = OutlookOptions(folder_filter=["Inbox", "Sent Items"])

        assert options.folder_filter == ["Inbox", "Sent Items"]

    def test_subfolder_inclusion(self):
        """Test subfolder inclusion option."""
        options1 = OutlookOptions(include_subfolders=True)
        options2 = OutlookOptions(include_subfolders=False)

        assert options1.include_subfolders is True
        assert options2.include_subfolders is False


@pytest.mark.integration
class TestOutlookMessageFiltering:
    """Test message filtering options."""

    def test_max_messages_option(self):
        """Test max messages configuration."""
        options = MboxOptions(max_messages=100)

        assert options.max_messages == 100

    def test_date_range_filtering(self):
        """Test date range filtering configuration."""
        start = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2024, 12, 31, tzinfo=datetime.timezone.utc)

        options = OutlookOptions(date_range_start=start, date_range_end=end)

        assert options.date_range_start == start
        assert options.date_range_end == end


@pytest.mark.integration
class TestOutlookOutputStructure:
    """Test different output structure modes."""

    def test_flat_output_structure(self):
        """Test flat output structure configuration."""
        options = OutlookOptions(output_structure="flat")

        assert options.output_structure == "flat"

    def test_hierarchical_output_structure(self):
        """Test hierarchical output structure configuration."""
        options = OutlookOptions(output_structure="hierarchical")

        assert options.output_structure == "hierarchical"

    def test_preserve_folder_metadata(self):
        """Test folder metadata preservation."""
        options1 = OutlookOptions(preserve_folder_metadata=True)
        options2 = OutlookOptions(preserve_folder_metadata=False)

        assert options1.preserve_folder_metadata is True
        assert options2.preserve_folder_metadata is False


@pytest.mark.integration
class TestOutlookAttachments:
    """Test handling of email attachments."""

    def test_msg_with_attachments(self, msg_attachments_file):
        """Test parsing MSG with attachments."""
        markdown = to_markdown(msg_attachments_file)

        assert isinstance(markdown, str)
        assert len(markdown) > 0

        # Should contain message content
        assert "Q2" in markdown or "report" in markdown.lower()


@pytest.mark.integration
class TestOutlookPSTHandling:
    """Test PST/OST file handling."""

    def test_pst_requires_pypff(self, tmp_path):
        """Test that PST files require pypff dependency."""
        # Create a fake PST file with PST magic bytes
        pst_file = tmp_path / "test.pst"
        pst_file.write_bytes(b"!BDN" + b"\x00" * 100)

        try:
            import pypff

            # pypff is available, skip this test
            pytest.skip("pypff is installed, cannot test missing dependency")
        except ImportError:
            # pypff not available - should get clear error
            from all2md.exceptions import DependencyError

            parser = OutlookToAstConverter()

            with pytest.raises(DependencyError) as exc_info:
                parser.parse(pst_file)

            error_msg = str(exc_info.value).lower()
            assert "libpff-python" in error_msg

    def test_pst_validation_requires_file_path(self):
        """Test that PST files require file path input."""
        import io


        parser = OutlookToAstConverter()

        # PST parser requires file path, not IO streams
        with pytest.raises(Exception):  # Will raise either ValidationError or DependencyError
            parser.parse(io.BytesIO(b"!BDN\x00\x00\x00\x00"))


@pytest.mark.integration
class TestOutlookFormatDetection:
    """Test Outlook format detection."""

    def test_detect_msg_format(self, tmp_path):
        """Test MSG format detection from file."""
        from all2md.parsers.outlook import _detect_outlook_format

        msg_file = tmp_path / "test.msg"
        msg_file.write_bytes(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"\x00" * 100)

        format_type = _detect_outlook_format(msg_file)
        assert format_type == "msg"

    def test_detect_pst_format(self, tmp_path):
        """Test PST format detection from file."""
        from all2md.parsers.outlook import _detect_outlook_format

        pst_file = tmp_path / "test.pst"
        pst_file.write_bytes(b"!BDN" + b"\x00" * 100)

        format_type = _detect_outlook_format(pst_file)
        assert format_type == "pst"

    def test_detect_ost_format(self, tmp_path):
        """Test OST format detection from file."""
        from all2md.parsers.outlook import _detect_outlook_format

        ost_file = tmp_path / "test.ost"
        ost_file.write_bytes(b"!BDN" + b"\x00" * 100)

        format_type = _detect_outlook_format(ost_file)
        assert format_type == "ost"


@pytest.mark.integration
class TestOutlookEdgeCases:
    """Test edge cases and error handling."""

    def test_options_validation_invalid_date_range(self):
        """Test that invalid date range raises error."""
        with pytest.raises(ValueError, match="date_range_start"):
            OutlookOptions(
                date_range_start=datetime.datetime(2024, 12, 31, tzinfo=datetime.timezone.utc),
                date_range_end=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
            )

    def test_options_validation_invalid_max_messages(self):
        """Test that invalid max_messages raises error."""
        with pytest.raises(ValueError, match="max_messages"):
            OutlookOptions(max_messages=0)

        with pytest.raises(ValueError, match="max_messages"):
            OutlookOptions(max_messages=-1)

    def test_defensive_copying_folder_filter(self):
        """Test that folder filter is defensively copied."""
        original = ["Inbox", "Sent Items"]
        options = OutlookOptions(folder_filter=original)

        # Modify original
        original.append("Drafts")

        # Options should not be affected
        assert len(options.folder_filter) == 2
        assert "Drafts" not in options.folder_filter

    def test_defensive_copying_skip_folders(self):
        """Test that skip folders is defensively copied."""
        original = ["Deleted Items"]
        options = OutlookOptions(skip_folders=original)

        # Modify original
        original.append("Junk Email")

        # Options should not be affected
        assert len(options.skip_folders) == 1
        assert "Junk Email" not in options.skip_folders


# Note: Import here to avoid circular dependency
from all2md.options.mbox import MboxOptions
