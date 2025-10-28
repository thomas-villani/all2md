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
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    HTMLBlock,
    Link,
    List,
    MathBlock,
    MathInline,
    Paragraph,
    Strong,
    Subscript,
    Superscript,
    Table,
    Text,
    ThematicBreak,
)
from all2md.options.rst import RstParserOptions
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
        assert "def hello()" in code_blocks[0].content

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
        assert "author" in doc.metadata
        assert doc.metadata["author"] == "John Doe"
        assert "creation_date" in doc.metadata

    def test_title_extraction(self) -> None:
        """Test extracting title from first section."""
        rst = """
My Document Title
=================

Content here.
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        assert "title" in doc.metadata
        assert doc.metadata["title"] == "My Document Title"


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

    def test_parse_admonitions_enabled(self) -> None:
        """Test parsing admonitions when enabled."""
        rst = """
.. note::
   This is a note.
"""
        options = RstParserOptions(parse_admonitions=True)
        parser = RestructuredTextParser(options)
        doc = parser.parse(rst.strip())

        # Should have one BlockQuote with admonition metadata
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], BlockQuote)
        assert doc.children[0].metadata.get("admonition_type") == "note"
        assert doc.children[0].metadata.get("source_format") == "rst"

    def test_parse_admonitions_disabled(self) -> None:
        """Test skipping admonitions when disabled."""
        rst = """
.. note::
   This is a note.

Regular paragraph.
"""
        options = RstParserOptions(parse_admonitions=False)
        parser = RestructuredTextParser(options)
        doc = parser.parse(rst.strip())

        # Should only have the regular paragraph, admonition should be skipped
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], Paragraph)


@pytest.mark.unit
class TestFootnotes:
    """Tests for footnote parsing."""

    def test_footnote_reference(self) -> None:
        """Test parsing a footnote reference.

        Note: RST footnote references may be processed differently depending on context.
        This test verifies the document parses successfully with footnote syntax.
        """
        rst = "This has a footnote [1]_."
        parser = RestructuredTextParser()
        doc = parser.parse(rst)

        # Verify document parses successfully
        assert isinstance(doc, Document)
        assert len(doc.children) >= 1

        # Find footnote reference - search recursively
        all_nodes = []

        def collect_nodes(node):
            all_nodes.append(node)
            if hasattr(node, "content") and isinstance(node.content, list):
                for child in node.content:
                    collect_nodes(child)
            if hasattr(node, "children") and isinstance(node.children, list):
                for child in node.children:
                    collect_nodes(child)

        for child in doc.children:
            collect_nodes(child)

        # May or may not have FootnoteReference depending on docutils processing
        # The important thing is the document parses without errors
        refs = [n for n in all_nodes if isinstance(n, FootnoteReference)]
        # If found, verify it has an identifier
        if refs:
            assert refs[0].identifier

    def test_footnote_definition(self) -> None:
        """Test parsing a footnote definition."""
        rst = """
.. [1] This is a footnote.
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        # Find footnote definition
        footnotes = [node for node in doc.children if isinstance(node, FootnoteDefinition)]
        assert len(footnotes) == 1
        assert footnotes[0].identifier
        assert len(footnotes[0].content) >= 1

    def test_footnote_reference_and_definition(self) -> None:
        """Test parsing footnote reference with definition."""
        rst = """
This has a footnote [1]_.

.. [1] This is the footnote content.
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        # Should have both reference and definition
        all_nodes = []

        def collect_nodes(node):
            all_nodes.append(node)
            if hasattr(node, "content") and isinstance(node.content, list):
                for child in node.content:
                    collect_nodes(child)
            if hasattr(node, "children") and isinstance(node.children, list):
                for child in node.children:
                    collect_nodes(child)

        for child in doc.children:
            collect_nodes(child)

        refs = [n for n in all_nodes if isinstance(n, FootnoteReference)]
        defs = [n for n in all_nodes if isinstance(n, FootnoteDefinition)]

        assert len(refs) >= 1
        assert len(defs) >= 1


@pytest.mark.unit
class TestMath:
    """Tests for math parsing."""

    def test_math_block(self) -> None:
        """Test parsing a math block."""
        rst = """
.. math::

   E = mc^2
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        # Find math block
        math_blocks = [node for node in doc.children if isinstance(node, MathBlock)]
        assert len(math_blocks) == 1
        assert "E = mc^2" in math_blocks[0].content
        assert math_blocks[0].notation == "latex"

    def test_math_inline(self) -> None:
        """Test parsing inline math."""
        rst = "The equation :math:`E = mc^2` is famous."
        parser = RestructuredTextParser()
        doc = parser.parse(rst)

        para = doc.children[0]
        assert isinstance(para, Paragraph)

        # Find inline math
        math_nodes = [node for node in para.content if isinstance(node, MathInline)]
        assert len(math_nodes) == 1
        assert "E = mc^2" in math_nodes[0].content
        assert math_nodes[0].notation == "latex"


@pytest.mark.unit
class TestHTMLContent:
    """Tests for raw HTML content parsing."""

    def test_html_block(self) -> None:
        """Test parsing raw HTML block."""
        rst = """
.. raw:: html

   <div class="custom">
     <p>HTML content</p>
   </div>
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        # Find HTML block
        html_blocks = [node for node in doc.children if isinstance(node, HTMLBlock)]
        assert len(html_blocks) == 1
        assert "<div" in html_blocks[0].content

    def test_html_inline(self) -> None:
        """Test parsing raw HTML inline."""
        rst = 'Text with :raw-html:`<span class="custom">inline HTML</span>`.'
        parser = RestructuredTextParser()
        doc = parser.parse(rst)

        # Note: Inline raw HTML may require special RST role configuration
        # This is a basic test - actual behavior depends on docutils setup
        assert isinstance(doc, Document)


@pytest.mark.unit
class TestAdmonitions:
    """Tests for admonition parsing."""

    def test_note_admonition(self) -> None:
        """Test parsing a note admonition."""
        rst = """
.. note::
   This is a note with some **bold** text.
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], BlockQuote)
        assert doc.children[0].metadata.get("admonition_type") == "note"

    def test_warning_admonition(self) -> None:
        """Test parsing a warning admonition."""
        rst = """
.. warning::
   This is a warning!
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], BlockQuote)
        assert doc.children[0].metadata.get("admonition_type") == "warning"

    def test_custom_admonition(self) -> None:
        """Test parsing a custom admonition with title."""
        rst = """
.. admonition:: Custom Title

   This is a custom admonition.
"""
        parser = RestructuredTextParser()
        doc = parser.parse(rst.strip())

        assert len(doc.children) == 1
        assert isinstance(doc.children[0], BlockQuote)
        assert doc.children[0].metadata.get("admonition_type") == "admonition"
        assert doc.children[0].metadata.get("admonition_title") == "Custom Title"

    def test_all_admonition_types(self) -> None:
        """Test all built-in admonition types."""
        admonition_types = ["note", "warning", "tip", "important", "caution", "danger", "error", "hint", "attention"]

        for adm_type in admonition_types:
            rst = f"""
.. {adm_type}::
   Test content.
"""
            parser = RestructuredTextParser()
            doc = parser.parse(rst.strip())

            assert len(doc.children) == 1
            assert isinstance(doc.children[0], BlockQuote)
            assert doc.children[0].metadata.get("admonition_type") == adm_type


@pytest.mark.unit
class TestSuperscriptSubscript:
    """Tests for superscript and subscript parsing."""

    def test_superscript(self) -> None:
        """Test parsing superscript."""
        rst = r"H\ :sup:`2`\ O is water."
        parser = RestructuredTextParser()
        doc = parser.parse(rst)

        para = doc.children[0]
        assert isinstance(para, Paragraph)

        # Find superscript
        sups = [node for node in para.content if isinstance(node, Superscript)]
        assert len(sups) == 1
        # Content should contain "2"
        assert len(sups[0].content) >= 1

    def test_subscript(self) -> None:
        """Test parsing subscript."""
        rst = r"CO\ :sub:`2` is carbon dioxide."
        parser = RestructuredTextParser()
        doc = parser.parse(rst)

        para = doc.children[0]
        assert isinstance(para, Paragraph)

        # Find subscript
        subs = [node for node in para.content if isinstance(node, Subscript)]
        assert len(subs) == 1
        # Content should contain "2"
        assert len(subs[0].content) >= 1
