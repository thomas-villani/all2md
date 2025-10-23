#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/parsers/test_encoding_detection.py
"""Integration tests for encoding detection across parsers."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

from all2md.parsers.asciidoc import AsciiDocParser
from all2md.parsers.csv import CsvToAstConverter
from all2md.parsers.dokuwiki import DokuWikiParser
from all2md.parsers.markdown import MarkdownToAstConverter
from all2md.parsers.mediawiki import MediaWikiParser
from all2md.parsers.mhtml import MhtmlToAstConverter
from all2md.parsers.org import OrgParser
from all2md.parsers.plaintext import PlainTextToAstConverter
from all2md.parsers.rst import RestructuredTextParser
from all2md.parsers.sourcecode import SourceCodeToAstConverter
from all2md.parsers.textile import TextileParser


class TestCSVEncodingDetection:
    """Test CSV parser with various encodings."""

    def test_csv_utf8(self):
        """Test CSV with UTF-8 encoding."""
        csv_content = "Name,Age,City\nJohn,25,NYC\nJané,30,Café"
        data = csv_content.encode("utf-8")

        parser = CsvToAstConverter()
        doc = parser.parse(data)

        assert doc is not None
        assert len(doc.children) > 0

    def test_csv_latin1(self):
        """Test CSV with Latin-1 encoding."""
        csv_content = "Name,Age,City\nJohn,25,NYC\nJane,30,LA"
        data = csv_content.encode("latin-1")

        parser = CsvToAstConverter()
        doc = parser.parse(data)

        assert doc is not None
        assert len(doc.children) > 0

    def test_csv_with_bom(self):
        """Test CSV with UTF-8 BOM."""
        csv_content = "Name,Age\nJohn,25"
        data = csv_content.encode("utf-8-sig")

        parser = CsvToAstConverter()
        doc = parser.parse(data)

        assert doc is not None

    def test_csv_dialect_validation(self):
        """Test CSV dialect detection and validation."""
        # Sparse CSV that might confuse sniffer
        csv_content = "A\nB\nC\nD,E,F\nG,H,I"
        data = csv_content.encode("utf-8")

        parser = CsvToAstConverter()
        doc = parser.parse(data)

        assert doc is not None

    def test_csv_from_file_path(self):
        """Test CSV encoding detection from file path."""
        csv_content = "Name,Value\nTest,123\nÉlève,456"

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as f:
            f.write(csv_content.encode("utf-8"))
            temp_path = f.name

        try:
            parser = CsvToAstConverter()
            doc = parser.parse(temp_path)
            assert doc is not None
        finally:
            Path(temp_path).unlink()


class TestMHTMLEncodingDetection:
    """Test MHTML parser with charset detection."""

    def test_mhtml_with_charset_header(self):
        """Test MHTML with charset in Content-Type header."""
        mhtml_content = """MIME-Version: 1.0
Content-Type: multipart/related; boundary="boundary123"

--boundary123
Content-Type: text/html; charset=utf-8

<html><body>Hello World 你好</body></html>
--boundary123--
"""
        data = mhtml_content.encode("utf-8")

        parser = MhtmlToAstConverter()
        doc = parser.parse(data)

        assert doc is not None

    def test_mhtml_latin1_charset(self):
        """Test MHTML with Latin-1 charset declaration."""
        html_body = "<html><body>Café</body></html>"
        mhtml_content = f"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="boundary123"

--boundary123
Content-Type: text/html; charset=iso-8859-1

{html_body}
--boundary123--
"""
        # Encode the HTML part with latin-1
        data = mhtml_content.encode("latin-1", errors="replace")

        parser = MhtmlToAstConverter()
        doc = parser.parse(data)

        assert doc is not None

    def test_mhtml_no_charset(self):
        """Test MHTML without charset (should use encoding detection)."""
        mhtml_content = """MIME-Version: 1.0
Content-Type: multipart/related; boundary="boundary123"

--boundary123
Content-Type: text/html

<html><body>Hello World</body></html>
--boundary123--
"""
        data = mhtml_content.encode("utf-8")

        parser = MhtmlToAstConverter()
        doc = parser.parse(data)

        assert doc is not None


class TestPlainTextEncoding:
    """Test plain text parser with various encodings."""

    def test_txt_utf8(self):
        """Test plain text with UTF-8."""
        content = "Hello, world!\n你好世界\nBonjour le monde"
        data = content.encode("utf-8")

        parser = PlainTextToAstConverter()
        doc = parser.parse(data)

        assert doc is not None
        assert len(doc.children) > 0

    def test_txt_latin1(self):
        """Test plain text with Latin-1."""
        content = "Café\nrésumé\nnaïve"
        data = content.encode("latin-1")

        parser = PlainTextToAstConverter()
        doc = parser.parse(data)

        assert doc is not None

    def test_txt_windows1252(self):
        """Test plain text with Windows-1252."""
        content = "Project — Report"  # em dash
        data = content.encode("windows-1252", errors="ignore")

        parser = PlainTextToAstConverter()
        doc = parser.parse(data)

        assert doc is not None

    def test_txt_from_file(self):
        """Test plain text encoding detection from file."""
        content = "Hello World\nÉlève français"

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            f.write(content.encode("utf-8"))
            temp_path = f.name

        try:
            parser = PlainTextToAstConverter()
            doc = parser.parse(temp_path)
            assert doc is not None
        finally:
            Path(temp_path).unlink()


class TestMarkdownEncoding:
    """Test Markdown parser with various encodings."""

    def test_markdown_utf8(self):
        """Test Markdown with UTF-8."""
        content = "# Hello 世界\n\nThis is **bold** text."
        data = content.encode("utf-8")

        parser = MarkdownToAstConverter()
        doc = parser.parse(data)

        assert doc is not None
        assert len(doc.children) > 0

    def test_markdown_with_emoji(self):
        """Test Markdown with emoji."""
        content = "# Hello ✨\n\nTest with émojis 🎉"
        data = content.encode("utf-8")

        parser = MarkdownToAstConverter()
        doc = parser.parse(data)

        assert doc is not None

    def test_markdown_latin1(self):
        """Test Markdown with Latin-1."""
        content = "# Café\n\nrésumé"
        data = content.encode("latin-1")

        parser = MarkdownToAstConverter()
        doc = parser.parse(data)

        assert doc is not None


class TestReStructuredTextEncoding:
    """Test RST parser with various encodings."""

    def test_rst_utf8(self):
        """Test RST with UTF-8."""
        content = """
Title
=====

Hello 世界
"""
        data = content.encode("utf-8")

        parser = RestructuredTextParser()
        doc = parser.parse(data)

        assert doc is not None

    def test_rst_latin1(self):
        """Test RST with Latin-1."""
        content = """
Café
====

résumé
"""
        data = content.encode("latin-1")

        parser = RestructuredTextParser()
        doc = parser.parse(data)

        assert doc is not None


class TestOrgModeEncoding:
    """Test Org-mode parser with various encodings."""

    def test_org_utf8(self):
        """Test Org with UTF-8."""
        content = """
* Hello 世界

This is a test.
"""
        data = content.encode("utf-8")

        parser = OrgParser()
        doc = parser.parse(data)

        assert doc is not None

    def test_org_latin1(self):
        """Test Org with Latin-1."""
        content = """
* Café

résumé
"""
        data = content.encode("latin-1")

        parser = OrgParser()
        doc = parser.parse(data)

        assert doc is not None


class TestAsciiDocEncoding:
    """Test AsciiDoc parser with various encodings."""

    def test_asciidoc_utf8(self):
        """Test AsciiDoc with UTF-8."""
        content = """
= Hello 世界

This is a test.
"""
        data = content.encode("utf-8")

        parser = AsciiDocParser()
        doc = parser.parse(data)

        assert doc is not None

    def test_asciidoc_latin1(self):
        """Test AsciiDoc with Latin-1."""
        content = """
= Café

résumé
"""
        data = content.encode("latin-1")

        parser = AsciiDocParser()
        doc = parser.parse(data)

        assert doc is not None


class TestMediaWikiEncoding:
    """Test MediaWiki parser with various encodings."""

    def test_mediawiki_utf8(self):
        """Test MediaWiki with UTF-8."""
        content = """
== Hello 世界 ==

This is '''bold''' text.
"""
        data = content.encode("utf-8")

        parser = MediaWikiParser()
        doc = parser.parse(data)

        assert doc is not None

    def test_mediawiki_latin1(self):
        """Test MediaWiki with Latin-1."""
        content = """
== Café ==

résumé
"""
        data = content.encode("latin-1")

        parser = MediaWikiParser()
        doc = parser.parse(data)

        assert doc is not None


class TestDokuWikiEncoding:
    """Test DokuWiki parser with various encodings."""

    def test_dokuwiki_utf8(self):
        """Test DokuWiki with UTF-8."""
        content = """
====== Hello 世界 ======

This is **bold** text.
"""
        data = content.encode("utf-8")

        parser = DokuWikiParser()
        doc = parser.parse(data)

        assert doc is not None

    def test_dokuwiki_latin1(self):
        """Test DokuWiki with Latin-1."""
        content = """
====== Café ======

résumé
"""
        data = content.encode("latin-1")

        parser = DokuWikiParser()
        doc = parser.parse(data)

        assert doc is not None


class TestTextileEncoding:
    """Test Textile parser with various encodings."""

    def test_textile_utf8(self):
        """Test Textile with UTF-8."""
        content = """
h1. Hello 世界

This is *bold* text.
"""
        data = content.encode("utf-8")

        parser = TextileParser()
        doc = parser.parse(data)

        assert doc is not None

    def test_textile_latin1(self):
        """Test Textile with Latin-1."""
        content = """
h1. Café

résumé
"""
        data = content.encode("latin-1")

        parser = TextileParser()
        doc = parser.parse(data)

        assert doc is not None


class TestSourceCodeEncoding:
    """Test source code parser with various encodings."""

    def test_python_utf8(self):
        """Test Python source with UTF-8."""
        content = """
# -*- coding: utf-8 -*-
def test():
    print('Hello 世界')
"""
        data = content.encode("utf-8")

        parser = SourceCodeToAstConverter()
        doc = parser.parse(data)

        assert doc is not None
        assert len(doc.children) > 0

    def test_python_latin1(self):
        """Test Python source with Latin-1."""
        content = """
def test():
    # Café
    pass
"""
        data = content.encode("latin-1")

        parser = SourceCodeToAstConverter()
        doc = parser.parse(data)

        assert doc is not None

    def test_javascript_utf8(self):
        """Test JavaScript source with UTF-8."""
        content = """
function test() {
    console.log('Hello 世界');
}
"""
        data = content.encode("utf-8")

        parser = SourceCodeToAstConverter()
        doc = parser.parse(data)

        assert doc is not None


class TestEncodingEdgeCases:
    """Test edge cases in encoding detection."""

    def test_very_small_file(self):
        """Test encoding detection with very small files."""
        content = "Hi"
        data = content.encode("utf-8")

        parser = PlainTextToAstConverter()
        doc = parser.parse(data)

        assert doc is not None

    def test_empty_file(self):
        """Test encoding detection with empty files."""
        data = b""

        parser = PlainTextToAstConverter()
        doc = parser.parse(data)

        assert doc is not None

    def test_binary_like_text(self):
        """Test with text containing binary-like sequences."""
        content = "Test\x00\x01\x02"
        data = content.encode("latin-1")

        parser = PlainTextToAstConverter()
        doc = parser.parse(data)

        assert doc is not None

    def test_mixed_line_endings(self):
        """Test file with mixed line endings."""
        content = "Line 1\nLine 2\r\nLine 3\rLine 4"
        data = content.encode("utf-8")

        parser = PlainTextToAstConverter()
        doc = parser.parse(data)

        assert doc is not None

    def test_file_with_replacement_chars(self):
        """Test that malformed encoding uses replacement characters."""
        # Invalid UTF-8 sequence
        data = b"Hello \xff\xfe World"

        parser = PlainTextToAstConverter()
        doc = parser.parse(data)

        # Should not raise exception
        assert doc is not None


class TestEncodingFromFileIO:
    """Test encoding detection from file-like objects."""

    def test_bytesio_utf8(self):
        """Test encoding detection from BytesIO."""
        content = "Hello 世界"
        data = content.encode("utf-8")
        file_obj = io.BytesIO(data)

        parser = PlainTextToAstConverter()
        doc = parser.parse(file_obj)

        assert doc is not None

    def test_bytesio_latin1(self):
        """Test encoding detection from BytesIO with Latin-1."""
        content = "Café résumé"
        data = content.encode("latin-1")
        file_obj = io.BytesIO(data)

        parser = PlainTextToAstConverter()
        doc = parser.parse(file_obj)

        assert doc is not None

    def test_csv_from_bytesio(self):
        """Test CSV encoding detection from BytesIO."""
        csv_content = "Name,Value\nTest,123"
        data = csv_content.encode("utf-8")
        file_obj = io.BytesIO(data)

        parser = CsvToAstConverter()
        doc = parser.parse(file_obj)

        assert doc is not None

    def test_markdown_from_bytesio(self):
        """Test Markdown encoding detection from BytesIO."""
        content = "# Hello\n\nWorld"
        data = content.encode("utf-8")
        file_obj = io.BytesIO(data)

        parser = MarkdownToAstConverter()
        doc = parser.parse(file_obj)

        assert doc is not None
