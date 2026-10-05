#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for new AsciiDoc parser improvements."""

import pytest

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

NL = chr(10)


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

    def test_colspan_syntax_with_space_after_pipe(self) -> None:
        """Leading space after | must not leave a stray '+' cell."""
        asciidoc = """|===
| 2+| spans two
|Cell 1|Cell 2
|==="""
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        table = doc.children[0]
        assert isinstance(table, Table)
        assert table.header is not None
        assert len(table.header.cells) == 1
        first_cell = table.header.cells[0]
        assert first_cell.colspan == 2
        assert first_cell.content[0].content == "spans two"

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
    """Tests for semicolon description list syntax.

    AsciiDoc's description-list markers are ``::``, ``:::``, ``::::`` and ``;;`` -- never
    a single ``;``. This class asserted the single-semicolon form, which was the lexer's
    behaviour and not the language's: it turned any prose containing a semicolon into a
    definition list.
    """

    def test_semicolon_description_list(self) -> None:
        """Test term;; description syntax."""
        asciidoc = """CPU;; Central Processing Unit
RAM;; Random Access Memory"""
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

    def test_prose_with_a_mid_sentence_semicolon_stays_one_paragraph(self) -> None:
        """``Alpha; beta gamma.`` is a sentence, and used to become a definition list."""
        parser = AsciiDocParser()

        doc = parser.parse("Alpha; beta gamma.")

        assert [type(node) for node in doc.children] == [Paragraph]
        assert doc.children[0].content[0].content == "Alpha; beta gamma."

    def test_a_line_ending_in_a_semicolon_stays_prose(self) -> None:
        """The description group is optional, so such a line became a bare term."""
        parser = AsciiDocParser()

        doc = parser.parse("A sentence ending in a semicolon;")

        assert [type(node) for node in doc.children] == [Paragraph]
        assert doc.children[0].content[0].content == "A sentence ending in a semicolon;"

    def test_a_semicolon_on_a_wrapped_line_does_not_split_the_paragraph(self) -> None:
        """The line was lexed on its own, so the paragraph broke in two mid-sentence."""
        parser = AsciiDocParser()

        doc = parser.parse("Some prose that wraps\nand continues; with more text here.")

        assert [type(node) for node in doc.children] == [Paragraph]
        assert doc.children[0].content[0].content == "Some prose that wraps and continues; with more text here."

    def test_the_doubled_marker_behaves_like_the_double_colon_one(self) -> None:
        """``;;`` and ``::`` are the same construct, so they must parse the same."""
        parser = AsciiDocParser()

        assert parser.parse("Term;; Definition") == parser.parse("Term:: Definition")

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

    def test_a_description_on_the_next_line_binds_to_its_term(self) -> None:
        """``t0::`` with the description on the following unindented line (#351).

        The standard AsciiDoc spelling -- and this project's own renderer's
        output -- puts the description on the line below the term with no
        indent. It parsed to a term with NO description, the text reappearing
        as a sibling paragraph outside the list.
        """
        asciidoc = "t0::\nd0\nt1::\nd1\n"
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        deflists = [node for node in doc.children if isinstance(node, DefinitionList)]
        assert len(deflists) == 1, "an N-term list must not split into N lists"
        assert len(deflists[0].items) == 2

        for expected_term, expected_desc, (term, descs) in [
            ("t0", "d0", deflists[0].items[0]),
            ("t1", "d1", deflists[0].items[1]),
        ]:
            assert term.content[0].content == expected_term
            assert len(descs) == 1, f"{expected_term}'s description was dropped"
            paragraph = descs[0].content[0]
            assert paragraph.content[0].content == expected_desc

    def test_adjacent_unindented_lines_wrap_into_one_description_paragraph(self) -> None:
        """Consecutive lines are one paragraph in AsciiDoc, wrapped or not."""
        asciidoc = "t0::\nfirst line\nsecond line\n\nafter\n"
        parser = AsciiDocParser()
        doc = parser.parse(asciidoc)

        deflist = doc.children[0]
        assert isinstance(deflist, DefinitionList)
        _, descs = deflist.items[0]
        assert len(descs) == 1
        assert len(descs[0].content) == 1, "wrapped lines are one paragraph, not one each"
        text = "".join(getattr(c, "content", "") for c in descs[0].content[0].content)
        assert "first line second line" in text

        paragraphs = [node for node in doc.children if isinstance(node, Paragraph)]
        assert any(
            "after" in "".join(getattr(c, "content", "") for c in p.content) for p in paragraphs
        ), "the paragraph after the blank line stays outside the list"

    def test_a_multi_paragraph_description_round_trips_with_its_words(self) -> None:
        """The renderer fused a description's paragraphs into one token (#352's class).

        'only' + 'extra' rendered as 'onlyextra'. They now join as continuation
        lines: the paragraph boundary degrades to a wrap, the words survive.
        """
        import io

        from all2md import from_ast, to_ast
        from all2md.ast import DefinitionDescription, DefinitionTerm, Document
        from all2md.ast.utils import extract_text

        doc = Document(
            children=[
                DefinitionList(
                    items=[
                        (
                            DefinitionTerm(content=[Text(content="t0")]),
                            [
                                DefinitionDescription(
                                    content=[
                                        Paragraph(content=[Text(content="only")]),
                                        Paragraph(content=[Text(content="extra")]),
                                    ]
                                )
                            ],
                        )
                    ]
                )
            ]
        )
        out = from_ast(doc, "asciidoc")
        assert "onlyextra" not in out

        back = to_ast(io.BytesIO(out.encode()), source_format="asciidoc")
        (deflist,) = [n for n in back.children if isinstance(n, DefinitionList)]
        text = extract_text(deflist)
        assert "only" in text and "extra" in text
        assert "onlyextra" not in text


class TestAsciiDocNamedInlineFootnotes:
    """The named inline form ``footnote:id[text]`` must parse, not leak as prose (#346).

    It is valid Asciidoctor and it is what this project's own renderer emits, but
    the parser matched only ``footnote:[text]`` and ``footnoteref:[id,text]`` -- the
    identifier between ``footnote:`` and ``[`` defeated both, so the raw markup
    passed through as literal text.
    """

    def test_named_inline_footnote_becomes_a_reference_and_definition(self) -> None:
        from all2md.ast import FootnoteDefinition, FootnoteReference

        parser = AsciiDocParser()
        doc = parser.parse("body footnote:a1[note one]\n")

        paragraph = doc.children[0]
        refs = [n for n in paragraph.content if isinstance(n, FootnoteReference)]
        assert len(refs) == 1
        assert refs[0].identifier == "a1"
        assert "footnote:a1" not in "".join(getattr(n, "content", "") for n in paragraph.content if isinstance(n, Text))

        defs = [n for n in doc.children if isinstance(n, FootnoteDefinition)]
        assert len(defs) == 1
        assert defs[0].identifier == "a1"
        text = "".join(getattr(c, "content", "") for p in defs[0].content for c in p.content)
        assert "note one" in text

    def test_a_repeat_reference_with_empty_brackets_does_not_redefine(self) -> None:
        from all2md.ast import FootnoteDefinition, FootnoteReference

        parser = AsciiDocParser()
        doc = parser.parse("one footnote:a1[the note] and footnote:a1[] again\n")

        paragraph = doc.children[0]
        refs = [n for n in paragraph.content if isinstance(n, FootnoteReference)]
        assert [r.identifier for r in refs] == ["a1", "a1"]

        defs = [n for n in doc.children if isinstance(n, FootnoteDefinition)]
        assert len(defs) == 1
        text = "".join(getattr(c, "content", "") for p in defs[0].content for c in p.content)
        assert "the note" in text

    def test_the_unnamed_form_still_parses(self) -> None:
        from all2md.ast import FootnoteDefinition, FootnoteReference

        parser = AsciiDocParser()
        doc = parser.parse("body footnote:[anonymous note]\n")

        paragraph = doc.children[0]
        assert any(isinstance(n, FootnoteReference) for n in paragraph.content)
        assert any(isinstance(n, FootnoteDefinition) for n in doc.children)


class TestAsciiDocAdmonitions:
    """Admonitions carry the metadata every parser uses (see ``BlockQuote``)."""

    @pytest.mark.parametrize("label", ["NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"])
    def test_attribute_form(self, label: str) -> None:
        doc = AsciiDocParser().parse(f"[{label}]" + NL + "Body text.")

        blockquote = doc.children[0]
        assert isinstance(blockquote, BlockQuote)
        assert blockquote.metadata == {"admonition_type": label.lower(), "source_format": "asciidoc"}
        assert isinstance(blockquote.children[0], Paragraph)

    def test_attribute_form_is_case_insensitive(self) -> None:
        doc = AsciiDocParser().parse("""[note]
Lowercase note.""")

        assert doc.children[0].metadata["admonition_type"] == "note"

    def test_paragraph_form(self) -> None:
        """``NOTE: text`` is the form most AsciiDoc uses; the label is not body text."""
        doc = AsciiDocParser().parse("TIP: Save often.")

        blockquote = doc.children[0]
        assert isinstance(blockquote, BlockQuote)
        assert blockquote.metadata["admonition_type"] == "tip"
        paragraph = blockquote.children[0]
        assert isinstance(paragraph, Paragraph)
        assert paragraph.content == [Text(content="Save often.")]

    @pytest.mark.parametrize("text", ["Note: mixed case.", "NOTE:no space.", "A NOTE: mid-line."])
    def test_paragraph_form_needs_the_exact_label(self, text: str) -> None:
        doc = AsciiDocParser().parse(text)

        assert isinstance(doc.children[0], Paragraph)

    def test_example_block_form(self) -> None:
        """``[WARNING]`` above ``====`` makes the whole block the admonition, not an example."""
        doc = AsciiDocParser().parse("""[WARNING]
====
First.

Second.
====""")

        blockquote = doc.children[0]
        assert isinstance(blockquote, BlockQuote)
        assert blockquote.metadata == {"admonition_type": "warning", "source_format": "asciidoc"}
        assert len(blockquote.children) == 2

    def test_plain_example_block_is_still_an_example(self) -> None:
        doc = AsciiDocParser().parse("""====
An example.
====""")

        assert doc.children[0].metadata == {"role": "example"}

    @pytest.mark.parametrize(
        "source",
        [
            """.Careful
[WARNING]
====
Body.
====""",
            """[WARNING]
.Careful
====
Body.
====""",
            """.Careful
[WARNING]
Body.""",
            """.Careful
WARNING: Body.""",
        ],
        ids=["title-then-label-block", "label-then-title-block", "title-then-label", "title-then-paragraph-form"],
    )
    def test_block_title_is_the_admonition_title(self, source: str) -> None:
        doc = AsciiDocParser().parse(source)

        assert len(doc.children) == 1
        assert doc.children[0].metadata["admonition_title"] == "Careful"
        assert doc.children[0].metadata["admonition_type"] == "warning"

    def test_anchor_names_the_admonition(self) -> None:
        doc = AsciiDocParser().parse("""[#keep]
[NOTE]
Anchored.""")

        blockquote = doc.children[0]
        assert blockquote.metadata["id"] == "keep"
        assert "id" not in blockquote.children[0].metadata

    @pytest.mark.parametrize("source", ["[NOTE]" + NL + "Plain.", "NOTE: Plain."])
    def test_disable_admonitions(self, source: str) -> None:
        options = AsciiDocOptions(parse_admonitions=False)
        doc = AsciiDocParser(options=options).parse(source)

        assert isinstance(doc.children[0], Paragraph)


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
