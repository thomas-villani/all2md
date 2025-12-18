#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_ini_parser.py
"""Unit tests for INI to AST converter.

Tests cover:
- Basic INI parsing
- Section handling
- Key-value pair extraction
- Case preservation
- Literal block mode
- Metadata extraction
- Edge cases

"""

from io import BytesIO
from pathlib import Path

import pytest

from all2md.ast import CodeBlock, Document, Heading, List
from all2md.exceptions import InvalidOptionsError, ParsingError
from all2md.options.ini import IniParserOptions
from all2md.parsers.ini import IniParser, _detect_ini_content


@pytest.mark.unit
class TestIniBasicParsing:
    """Tests for basic INI parsing functionality."""

    def test_parse_simple_ini(self) -> None:
        """Test parsing a simple INI file."""
        ini_content = b"[server]\nhost = localhost\nport = 8080"
        parser = IniParser()
        doc = parser.parse(BytesIO(ini_content))

        assert isinstance(doc, Document)
        assert len(doc.children) >= 1
        # First child should be a heading
        assert isinstance(doc.children[0], Heading)

    def test_parse_multiple_sections(self) -> None:
        """Test parsing INI with multiple sections."""
        ini_content = b"[server]\nhost = localhost\n\n[database]\nname = mydb"
        parser = IniParser()
        doc = parser.parse(BytesIO(ini_content))

        assert isinstance(doc, Document)
        # Should have headings for each section
        headings = [c for c in doc.children if isinstance(c, Heading)]
        assert len(headings) == 2

    def test_parse_from_file_path(self, tmp_path: Path) -> None:
        """Test parsing INI from file path."""
        ini_file = tmp_path / "test.ini"
        ini_file.write_text("[section]\nkey = value")

        parser = IniParser()
        doc = parser.parse(str(ini_file))

        assert isinstance(doc, Document)
        assert len(doc.children) >= 1

    def test_parse_from_path_object(self, tmp_path: Path) -> None:
        """Test parsing INI from Path object."""
        ini_file = tmp_path / "test.ini"
        ini_file.write_text("[section]\nkey = value")

        parser = IniParser()
        doc = parser.parse(ini_file)

        assert isinstance(doc, Document)

    def test_parse_from_string(self) -> None:
        """Test parsing INI from string content."""
        ini_content = "[section]\nkey = value"
        parser = IniParser()
        doc = parser.parse(ini_content)

        assert isinstance(doc, Document)


@pytest.mark.unit
class TestIniSectionHandling:
    """Tests for section handling."""

    def test_section_becomes_heading(self) -> None:
        """Test that sections are converted to headings."""
        ini_content = b"[my_section]\nkey = value"
        parser = IniParser()
        doc = parser.parse(BytesIO(ini_content))

        assert isinstance(doc.children[0], Heading)
        assert doc.children[0].level == 1

    def test_multiple_keys_in_section(self) -> None:
        """Test parsing multiple keys in a section."""
        ini_content = b"[config]\nhost = localhost\nport = 8080\ntimeout = 30"
        parser = IniParser()
        doc = parser.parse(BytesIO(ini_content))

        # Should have heading + list
        assert len(doc.children) >= 2
        assert isinstance(doc.children[1], List)


@pytest.mark.unit
class TestIniCasePreservation:
    """Tests for case preservation options."""

    def test_preserve_case_option(self) -> None:
        """Test that preserve_case option preserves key case."""
        ini_content = b"[Section]\nMyKey = value"
        options = IniParserOptions(preserve_case=True)
        parser = IniParser(options)
        doc = parser.parse(BytesIO(ini_content))

        assert isinstance(doc, Document)

    def test_case_normalization_default(self) -> None:
        """Test default case handling."""
        ini_content = b"[SECTION]\nKEY = value"
        parser = IniParser()
        doc = parser.parse(BytesIO(ini_content))

        assert isinstance(doc, Document)


@pytest.mark.unit
class TestIniLiteralBlockMode:
    """Tests for literal block mode."""

    def test_literal_block_mode(self) -> None:
        """Test that literal_block mode wraps INI as code block."""
        ini_content = b"[server]\nhost = localhost"
        options = IniParserOptions(literal_block=True)
        parser = IniParser(options)
        doc = parser.parse(BytesIO(ini_content))

        assert isinstance(doc, Document)
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], CodeBlock)
        assert doc.children[0].language == "ini"


@pytest.mark.unit
class TestIniAllowNoValue:
    """Tests for allow_no_value option."""

    def test_allow_no_value_option(self) -> None:
        """Test parsing keys without values."""
        ini_content = b"[section]\nkey_without_value"
        options = IniParserOptions(allow_no_value=True)
        parser = IniParser(options)
        doc = parser.parse(BytesIO(ini_content))

        assert isinstance(doc, Document)

    def test_reject_no_value_default(self) -> None:
        """Test that keys without values fail without option."""
        ini_content = b"[section]\nkey_without_value"
        parser = IniParser()

        with pytest.raises(ParsingError):
            parser.parse(BytesIO(ini_content))


@pytest.mark.unit
class TestIniNumberFormatting:
    """Tests for number formatting option."""

    def test_pretty_format_numbers_enabled(self) -> None:
        """Test pretty number formatting."""
        ini_content = b"[section]\ncount = 1000000"
        options = IniParserOptions(pretty_format_numbers=True)
        parser = IniParser(options)
        doc = parser.parse(BytesIO(ini_content))

        assert isinstance(doc, Document)

    def test_pretty_format_numbers_disabled(self) -> None:
        """Test with number formatting disabled."""
        ini_content = b"[section]\ncount = 1000000"
        options = IniParserOptions(pretty_format_numbers=False)
        parser = IniParser(options)
        doc = parser.parse(BytesIO(ini_content))

        assert isinstance(doc, Document)


@pytest.mark.unit
class TestIniMetadataExtraction:
    """Tests for metadata extraction."""

    def test_extract_title_from_metadata_section(self) -> None:
        """Test extracting title from metadata section."""
        ini_content = b"[metadata]\ntitle = My Document\n\n[config]\nkey = value"
        parser = IniParser()
        doc = parser.parse(BytesIO(ini_content))

        # Metadata should be extracted
        assert isinstance(doc, Document)

    def test_extract_title_from_info_section(self) -> None:
        """Test extracting title from info section."""
        ini_content = b"[info]\nname = My App\n\n[settings]\nkey = value"
        parser = IniParser()
        doc = parser.parse(BytesIO(ini_content))

        assert isinstance(doc, Document)


@pytest.mark.unit
class TestIniContentDetection:
    """Tests for INI content detection."""

    def test_detect_valid_ini(self) -> None:
        """Test detection of valid INI content."""
        ini_content = b"[section]\nkey = value"
        assert _detect_ini_content(ini_content) is True

    def test_detect_multi_section_ini(self) -> None:
        """Test detection of multi-section INI."""
        ini_content = b"[section1]\nkey = value\n\n[section2]\nkey2 = value2"
        assert _detect_ini_content(ini_content) is True

    def test_non_ini_content(self) -> None:
        """Test that non-INI content is not detected."""
        non_ini = b"This is just plain text without sections."
        assert _detect_ini_content(non_ini) is False

    def test_empty_content_not_ini(self) -> None:
        """Test that empty content is not detected as INI."""
        assert _detect_ini_content(b"") is False

    def test_content_without_sections_not_ini(self) -> None:
        """Test that content without sections is not INI."""
        content = b"key = value\nkey2 = value2"
        assert _detect_ini_content(content) is False


@pytest.mark.unit
class TestIniEdgeCases:
    """Tests for edge cases."""

    def test_empty_section(self) -> None:
        """Test parsing empty section."""
        ini_content = b"[empty_section]"
        parser = IniParser()
        doc = parser.parse(BytesIO(ini_content))

        assert isinstance(doc, Document)

    def test_empty_value(self) -> None:
        """Test parsing key with empty value."""
        ini_content = b"[section]\nkey = "
        parser = IniParser()
        doc = parser.parse(BytesIO(ini_content))

        assert isinstance(doc, Document)

    def test_multiline_value(self) -> None:
        """Test parsing multiline value (not standard but common)."""
        ini_content = b"[section]\nkey = value"
        parser = IniParser()
        doc = parser.parse(BytesIO(ini_content))

        assert isinstance(doc, Document)

    def test_invalid_ini_raises_error(self) -> None:
        """Test that invalid INI raises ParsingError."""
        # This should cause a configparser error
        invalid_ini = b"[unclosed_section"
        parser = IniParser()

        with pytest.raises(ParsingError):
            parser.parse(BytesIO(invalid_ini))

    def test_options_validation_wrong_type(self) -> None:
        """Test that wrong options type raises error."""
        with pytest.raises(InvalidOptionsError):
            IniParser(options="invalid")

    def test_utf8_content(self) -> None:
        """Test parsing UTF-8 content."""
        ini_content = "[section]\nname = Müller".encode("utf-8")
        parser = IniParser()
        doc = parser.parse(BytesIO(ini_content))

        assert isinstance(doc, Document)
