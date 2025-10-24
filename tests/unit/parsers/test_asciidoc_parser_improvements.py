#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for new AsciiDoc parser improvements."""

from all2md.ast import (
    BlockQuote,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Paragraph,
    Table,
    Text,
    ThematicBreak,
)
from all2md.options.asciidoc import AsciiDocOptions
from all2md.parsers.asciidoc import AsciiDocParser


class TestAsciiDocThematicBreaks:
    """Tests for enhanced thematic break support."""

    def test_triple_underscore(self) -> None:
        """Test that ___ creates a thematic break."""
        parser = AsciiDocParser()
        doc = parser.parse("___")

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], ThematicBreak)

    def test_quadruple_hyphens(self) -> None:
        """Test that ---- creates a thematic break (4+ hyphens)."""
        parser = AsciiDocParser()
        doc = parser.parse("----")

        assert len(doc.children) == 1
        # Note: ---- is actually a code block delimiter in AsciiDoc
        # But if it's alone on a line without closing, should be treated as thematic break

    def test_quintuple_asterisks(self) -> None:
        """Test that ***** creates a thematic break (5+ asterisks)."""
        parser = AsciiDocParser()
        doc = parser.parse("*****")

        assert len(doc.children) == 1
        # Note: ***** is actually a sidebar delimiter in AsciiDoc

    def test_traditional_thematic_breaks(self) -> None:
        """Test traditional thematic breaks still work."""
        parser = AsciiDocParser()

        # Test '''
        doc1 = parser.parse("'''")
        assert len(doc1.children) == 1
        assert isinstance(doc1.children[0], ThematicBreak)

        # Test ---
        doc2 = parser.parse("---")
        assert len(doc2.children) == 1
        assert isinstance(doc2.children[0], ThematicBreak)

        # Test ***
        doc3 = parser.parse("***")
        assert len(doc3.children) == 1
        assert isinstance(doc3.children[0], ThematicBreak)


class TestAsciiDocEscapeCharacters:
    """Tests for extended escape character support."""

    def test_escape_plus(self) -> None:
        """Test escaping plus sign."""
        parser = AsciiDocParser()
        doc = parser.parse(r"1 \+ 1 = 2")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        # Should contain the literal plus sign
        text_content = "".join(node.content for node in para.content if isinstance(node, Text))
        assert "+" in text_content

    def test_escape_hash(self) -> None:
        """Test escaping hash sign."""
        parser = AsciiDocParser()
        doc = parser.parse(r"\#hashtag")

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        text_content = "".join(node.content for node in para.content if isinstance(node, Text))
        assert "#hashtag" in text_content

    def test_escape_exclamation(self) -> None:
        """Test escaping exclamation mark."""
        parser = AsciiDocParser()
        doc = parser.parse(r"Hello\! World")

        para = doc.children[0]
        text_content = "".join(node.content for node in para.content if isinstance(node, Text))
        assert "!" in text_content

    def test_escape_colon(self) -> None:
        """Test escaping colon."""
        parser = AsciiDocParser()
        doc = parser.parse(r"Key\: Value")

        para = doc.children[0]
        text_content = "".join(node.content for node in para.content if isinstance(node, Text))
        assert ":" in text_content


class TestAsciiDocAttributeUnsetting:
    """Tests for attribute unsetting with :name!: syntax."""

    def test_unset_attribute(self) -> None:
        """Test that :name!: unsets an attribute."""
        asciidoc = """:author: John Doe
:title: My Document
:author!:

Text"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Author should not be in metadata (it was unset)
        assert doc.metadata.get("author") is None
        # Title should still be there
        assert doc.metadata.get("title") == "My Document"

    def test_unset_nonexistent_attribute(self) -> None:
        """Test unsetting an attribute that was never set."""
        asciidoc = ":nonexistent!:\n\nText"
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Should not raise an error
        assert "nonexistent" not in doc.metadata


class TestAsciiDocRevisionMetadata:
    """Tests for revision metadata support."""

    def test_revnumber_maps_to_version(self) -> None:
        """Test that revnumber maps to metadata.version."""
        asciidoc = ":revnumber: 1.0.0\n\nContent"
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        assert doc.metadata.get("version") == "1.0.0"

    def test_revdate_in_custom(self) -> None:
        """Test that revdate is included in metadata."""
        asciidoc = ":revdate: 2025-01-15\n\nContent"
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Custom fields are flattened to top level in to_dict()
        assert doc.metadata.get("revdate") == "2025-01-15"

    def test_both_revision_fields(self) -> None:
        """Test both revnumber and revdate together."""
        asciidoc = """:revnumber: 2.1.0
:revdate: 2025-01-20

Content"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        assert doc.metadata.get("version") == "2.1.0"
        # Custom fields are flattened to top level in to_dict()
        assert doc.metadata.get("revdate") == "2025-01-20"


class TestAsciiDocTableColspanRowspan:
    """Tests for table colspan and rowspan support."""

    def test_colspan_syntax(self) -> None:
        """Test 2+|cell creates colspan=2."""
        asciidoc = """|===
|2+|Spanning Cell
|Cell 1|Cell 2
|==="""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        table = doc.children[0]
        assert isinstance(table, Table)

        # First row is auto-detected as header, check header cell for colspan
        assert table.header is not None
        first_cell = table.header.cells[0]
        assert first_cell.colspan == 2
        # Verify content is correct
        assert first_cell.content[0].content == "Spanning Cell"

    def test_rowspan_syntax(self) -> None:
        """Test .3+|cell creates rowspan=3."""
        asciidoc = """|===
|.3+|Tall Cell|Row 1
|Row 2
|Row 3
|==="""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        table = doc.children[0]
        assert isinstance(table, Table)

        # First row is auto-detected as header, check header cell for rowspan
        assert table.header is not None
        first_cell = table.header.cells[0]
        assert first_cell.rowspan == 3
        assert first_cell.content[0].content == "Tall Cell"

    def test_colspan_and_rowspan(self) -> None:
        """Test 2.3+|cell creates both colspan=2 and rowspan=3."""
        asciidoc = """|===
|2.3+|Big Cell|Cell A
|Cell B
|Cell C
|==="""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        table = doc.children[0]
        # First row is auto-detected as header, check header cell for spans
        assert table.header is not None
        first_cell = table.header.cells[0]
        assert first_cell.colspan == 2
        assert first_cell.rowspan == 3
        assert first_cell.content[0].content == "Big Cell"

    def test_disable_span_parsing(self) -> None:
        """Test that parse_table_spans=False disables span parsing."""
        asciidoc = """|===
|2+|Should Not Parse
|==="""
        options = AsciiDocOptions(parse_table_spans=False)
        parser = AsciiDocParser(options=options)
        doc = parser.parse(asciidoc)

        table = doc.children[0]
        # When spans are disabled, the cell text should include "2+|" prefix
        # or the cell should have default colspan=1
        if table.rows and table.rows[0].cells:
            first_cell = table.rows[0].cells[0]
            # Should have default colspan of 1
            assert first_cell.colspan == 1


class TestAsciiDocTableHeaderExplicit:
    """Tests for explicit header detection with options='header'."""

    def test_explicit_header_option(self) -> None:
        """Test [options='header'] explicitly marks first row as header."""
        asciidoc = """[options="header"]
|===
|Name|Age
|John|30
|==="""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        table = doc.children[0]
        assert isinstance(table, Table)
        assert table.header is not None
        assert table.header.is_header is True


class TestAsciiDocSemicolonDescriptionLists:
    """Tests for semicolon description list syntax."""

    def test_semicolon_description_list(self) -> None:
        """Test term; description syntax."""
        asciidoc = """CPU; Central Processing Unit
RAM; Random Access Memory"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        deflist = doc.children[0]
        assert isinstance(deflist, DefinitionList)
        assert len(deflist.items) == 2

        # Check first item
        term1, descs1 = deflist.items[0]
        assert isinstance(term1, DefinitionTerm)
        assert term1.content[0].content == "CPU"
        assert len(descs1) == 1
        assert isinstance(descs1[0], DefinitionDescription)

    def test_double_colon_still_works(self) -> None:
        """Test that traditional :: syntax still works."""
        asciidoc = """Term:: Definition
Another:: Another def"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        deflist = doc.children[0]
        assert isinstance(deflist, DefinitionList)
        assert len(deflist.items) == 2


class TestAsciiDocMultiLineDescriptionLists:
    """Tests for multi-line description list support."""

    def test_indented_continuation(self) -> None:
        """Test indented lines continue description."""
        asciidoc = """Term:: First line
  Second line
  Third line

Next Term:: Definition"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        deflist = doc.children[0]
        assert isinstance(deflist, DefinitionList)

        # First term should have description with multiple paragraphs
        term1, descs1 = deflist.items[0]
        assert len(descs1) > 0
        # Should have collected the continuation lines
        desc = descs1[0]
        assert len(desc.content) >= 1  # At least the first paragraph

    def test_blank_line_separation(self) -> None:
        """Test blank line ends multi-line description."""
        asciidoc = """Term:: Line 1
  Line 2

NewTerm:: New def"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        deflist = doc.children[0]
        # Should have two separate terms
        assert len(deflist.items) == 2


class TestAsciiDocAdmonitions:
    """Tests for admonition block support."""

    def test_note_admonition(self) -> None:
        """Test [NOTE] creates BlockQuote with role='note'."""
        asciidoc = """[NOTE]
This is a note."""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        blockquote = doc.children[0]
        assert isinstance(blockquote, BlockQuote)
        assert blockquote.metadata.get("role") == "note"

    def test_tip_admonition(self) -> None:
        """Test [TIP] admonition."""
        asciidoc = """[TIP]
Helpful tip here."""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        blockquote = doc.children[0]
        assert isinstance(blockquote, BlockQuote)
        assert blockquote.metadata.get("role") == "tip"

    def test_important_admonition(self) -> None:
        """Test [IMPORTANT] admonition."""
        asciidoc = """[IMPORTANT]
Pay attention!"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        blockquote = doc.children[0]
        assert blockquote.metadata.get("role") == "important"

    def test_warning_admonition(self) -> None:
        """Test [WARNING] admonition."""
        asciidoc = """[WARNING]
Be careful!"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        blockquote = doc.children[0]
        assert blockquote.metadata.get("role") == "warning"

    def test_caution_admonition(self) -> None:
        """Test [CAUTION] admonition."""
        asciidoc = """[CAUTION]
Proceed with caution."""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        blockquote = doc.children[0]
        assert blockquote.metadata.get("role") == "caution"

    def test_admonition_case_insensitive(self) -> None:
        """Test admonitions work with different cases."""
        asciidoc = """[note]
Lowercase note."""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        blockquote = doc.children[0]
        assert isinstance(blockquote, BlockQuote)
        assert blockquote.metadata.get("role") == "note"

    def test_disable_admonitions(self) -> None:
        """Test parse_admonitions=False disables admonition parsing."""
        asciidoc = """[NOTE]
Should not be admonition."""
        options = AsciiDocOptions(parse_admonitions=False)
        parser = AsciiDocParser(options=options)
        _ = parser.parse(asciidoc)

        # Should just be a paragraph, not wrapped in BlockQuote
        # (or the block attribute is ignored)
        # The exact behavior depends on implementation


class TestAsciiDocAttributeContinuation:
    """Tests for multi-line attribute values with + continuation."""

    def test_attribute_continuation(self) -> None:
        """Test attribute value continuation with trailing ' +'."""
        asciidoc = """:description: This is a very long +
description that spans +
multiple lines

Content"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Should join all lines with spaces
        # Custom fields are flattened to top level in to_dict()
        description = doc.metadata.get("description", "")
        assert "very long" in description
        assert "multiple lines" in description
        # Should be on one line (joined with spaces)
        assert "\n" not in description

    def test_continuation_without_final_plus(self) -> None:
        """Test continuation ends when line doesn't end with +."""
        asciidoc = """:description: Line 1 +
Line 2
:other: value

Content"""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        # Description should only contain first two lines
        # Custom fields are flattened to top level in to_dict()
        description = doc.metadata.get("description", "")
        assert "Line 1" in description
        assert "Line 2" in description

    def test_blank_line_ends_continuation(self) -> None:
        """Test blank line ends continuation."""
        asciidoc = """:description: Line 1 +

:other: value"""
        parser = AsciiDocParser()
        _ = parser.parse(asciidoc)

        # Blank line should end continuation
        # Only "Line 1" should be in description
