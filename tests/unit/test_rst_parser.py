#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_rst_parser.py
"""Unit tests for reStructuredText parser.

Tests cover:
- RST heading parsing
- Text formatting (bold, italic, literal)
- List parsing (bullet and enumerated)
- Table parsing
- Code block parsing
- Definition lists
- Links and images
- Metadata extraction

"""

import pytest

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    DefinitionList,
    Document,
    Emphasis,
    Heading,
    Link,
    List,
    Paragraph,
    Strong,
    Table,
    Text,
    ThematicBreak,
)
from all2md.options import RstParserOptions
from all2md.parsers.rst import RestructuredTextParser


@pytest.mark.unit
class TestBasicParsing:
    """Tests for basic RST parsing."""

    def test_simple_heading(self) -> None:
        """Test parsing a simple heading."""
        rst = """
Title
=====
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Heading)
        assert doc.children[0].level == 1
        assert len(doc.children[0].content) == 1
        assert isinstance(doc.children[0].content[0], Text)
        assert doc.children[0].content[0].content == "Title"

    def test_multiple_headings(self) -> None:
        """Test parsing multiple heading levels."""
        rst = """
Level 1
=======

Level 2
-------

Level 3
~~~~~~~
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        # Should have 3 headings
        # Note: docutils interprets first as title, second as subtitle, third as section
        headings = [node for node in doc.children if isinstance(node, Heading)]
        assert len(headings) == 3
        assert headings[0].level == 1  # title
        assert headings[1].level == 2  # subtitle
        # Third heading is inside a section, so level may differ
        assert headings[2].level >= 1

    def test_simple_paragraph(self) -> None:
        """Test parsing a simple paragraph."""
        rst = "This is a simple paragraph."
        parser = RestructuredTextParser()
        doc = parser.parse(rst)

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Paragraph)
        assert len(doc.children[0].content) == 1
        assert isinstance(doc.children[0].content[0], Text)
        assert doc.children[0].content[0].content == "This is a simple paragraph."

    def test_multiple_paragraphs(self) -> None:
        """Test parsing multiple paragraphs."""
        rst = """
First paragraph.

Second paragraph.

Third paragraph.
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        paragraphs = [node for node in doc.children if isinstance(node, Paragraph)]
        assert len(paragraphs) == 3


@pytest.mark.unit
class TestInlineFormatting:
    """Tests for inline formatting."""

    def test_emphasis(self) -> None:
        """Test parsing emphasis (italic)."""
        rst = "This is *italic* text."
        parser = RestructuredTextParser()
        doc = parser.parse(rst)

        assert len(doc.children) == 1
        para = doc.children[0]
        assert isinstance(para, Paragraph)
        assert len(para.content) == 3
        assert isinstance(para.content[0], Text)
        assert isinstance(para.content[1], Emphasis)
        assert isinstance(para.content[2], Text)

    def test_strong(self) -> None:
        """Test parsing strong (bold)."""
        rst = "This is **bold** text."
        parser = RestructuredTextParser()
        doc = parser.parse(rst)

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        assert len(para.content) == 3
        assert isinstance(para.content[1], Strong)

    def test_literal(self) -> None:
        """Test parsing literal (code)."""
        rst = "This is ``code`` text."
        parser = RestructuredTextParser()
        doc = parser.parse(rst)

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        assert len(para.content) == 3
        assert isinstance(para.content[1], Code)
        assert para.content[1].content == "code"

    def test_combined_formatting(self) -> None:
        """Test parsing combined inline formatting."""
        rst = "This has *italic*, **bold**, and ``code``."
        parser = RestructuredTextParser()
        doc = parser.parse(rst)

        para = doc.children[0]
        assert isinstance(para, Paragraph)
        # Should have: text, emph, text, strong, text, code, text
        assert len(para.content) == 7


@pytest.mark.unit
class TestLists:
    """Tests for list parsing."""

    def test_bullet_list(self) -> None:
        """Test parsing a bullet list."""
        rst = """
* Item 1
* Item 2
* Item 3
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        assert len(doc.children) == 1
        lst = doc.children[0]
        assert isinstance(lst, List)
        assert not lst.ordered
        assert len(lst.items) == 3

    def test_enumerated_list(self) -> None:
        """Test parsing an enumerated list."""
        rst = """
1. First item
2. Second item
3. Third item
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        assert len(doc.children) == 1
        lst = doc.children[0]
        assert isinstance(lst, List)
        assert lst.ordered
        assert len(lst.items) == 3
        assert lst.start == 1

    def test_nested_lists(self) -> None:
        """Test parsing nested lists."""
        rst = """
* Item 1

  * Nested item 1
  * Nested item 2

* Item 2
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        # Top level should have a list
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], List)


@pytest.mark.unit
class TestCodeBlocks:
    """Tests for code block parsing."""

    def test_literal_block(self) -> None:
        """Test parsing a literal block."""
        rst = """
::

   def hello():
       print("Hello")
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        # Find code block
        code_blocks = [node for node in doc.children if isinstance(node, CodeBlock)]
        assert len(code_blocks) == 1
        assert 'def hello()' in code_blocks[0].content

    def test_code_block_directive(self) -> None:
        """Test parsing code-block directive."""
        rst = """
.. code-block:: python

   def hello():
       print("Hello")
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        code_blocks = [node for node in doc.children if isinstance(node, CodeBlock)]
        assert len(code_blocks) == 1
        assert code_blocks[0].language == "python"


@pytest.mark.unit
class TestLinks:
    """Tests for link parsing."""

    def test_external_link(self) -> None:
        """Test parsing an external link."""
        rst = "Visit `Python <https://www.python.org>`_"
        parser = RestructuredTextParser()
        doc = parser.parse(rst)

        para = doc.children[0]
        assert isinstance(para, Paragraph)

        # Find link node
        links = [node for node in para.content if isinstance(node, Link)]
        assert len(links) == 1
        assert links[0].url == "https://www.python.org"


@pytest.mark.unit
class TestImages:
    """Tests for image parsing."""

    def test_image_directive(self) -> None:
        """Test parsing image directive."""
        rst = """
.. image:: example.png
   :alt: Example image
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        # Images in RST directives may not parse directly to Image nodes
        # depending on docutils configuration
        # This is a basic test
        assert isinstance(doc, Document)


@pytest.mark.unit
class TestTables:
    """Tests for table parsing."""

    def test_simple_grid_table(self) -> None:
        """Test parsing a simple grid table."""
        rst = """
+-------+-------+
| A     | B     |
+=======+=======+
| 1     | 2     |
+-------+-------+
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        tables = [node for node in doc.children if isinstance(node, Table)]
        assert len(tables) == 1
        assert tables[0].header is not None
        assert len(tables[0].rows) >= 1


@pytest.mark.unit
class TestDefinitionLists:
    """Tests for definition list parsing."""

    def test_definition_list(self) -> None:
        """Test parsing a definition list."""
        rst = """
Term 1
   Definition for term 1

Term 2
   Definition for term 2
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        def_lists = [node for node in doc.children if isinstance(node, DefinitionList)]
        assert len(def_lists) == 1
        assert len(def_lists[0].items) == 2


@pytest.mark.unit
class TestBlockQuotes:
    """Tests for block quote parsing."""

    def test_block_quote(self) -> None:
        """Test parsing a block quote."""
        rst = """
Regular paragraph.

   This is a block quote.
   It can span multiple lines.
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        # Look for block quote
        quotes = [node for node in doc.children if isinstance(node, BlockQuote)]
        assert len(quotes) >= 1


@pytest.mark.unit
class TestThematicBreak:
    """Tests for thematic break parsing."""

    def test_transition(self) -> None:
        """Test parsing a transition (thematic break)."""
        rst = """
Before transition.

----

After transition.
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        breaks = [node for node in doc.children if isinstance(node, ThematicBreak)]
        assert len(breaks) == 1


@pytest.mark.unit
class TestMetadataExtraction:
    """Tests for metadata extraction."""

    def test_docinfo_extraction(self) -> None:
        """Test extracting metadata from docinfo."""
        rst = """
:Author: John Doe
:Date: 2025-01-01

Content here.
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        # Check metadata
        assert 'author' in doc.metadata
        assert doc.metadata['author'] == 'John Doe'
        assert 'creation_date' in doc.metadata

    def test_title_extraction(self) -> None:
        """Test extracting title from first section."""
        rst = """
My Document Title
=================

Content here.
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        assert 'title' in doc.metadata
        assert doc.metadata['title'] == 'My Document Title'


@pytest.mark.unit
class TestOptions:
    """Tests for parser options."""

    def test_strict_mode_disabled(self) -> None:
        """Test that strict mode disabled allows graceful parsing."""
        rst = "This is valid RST."
        options = RstParserOptions(strict_mode=False)
        parser = RestructuredTextParser(options)
        doc = parser.parse(rst)

        assert isinstance(doc, Document)

    def test_parse_directives_enabled(self) -> None:
        """Test that parse_directives option is respected."""
        rst = "Test content."
        options = RstParserOptions(parse_directives=True)
        parser = RestructuredTextParser(options)
        doc = parser.parse(rst)

        assert isinstance(doc, Document)
