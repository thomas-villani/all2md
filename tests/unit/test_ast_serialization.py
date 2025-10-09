#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for AST serialization and deserialization."""
import json

import pytest

from all2md.ast import (
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
    Paragraph,
    SourceLocation,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.ast.serialization import ast_to_dict, ast_to_json, dict_to_ast, json_to_ast


@pytest.mark.unit
class TestAstToDictConversion:
    """Test AST to dictionary conversion."""

    def test_text_node_to_dict(self) -> None:
        """Test converting Text node to dict."""
        text = Text(content="Hello")
        result = ast_to_dict(text)

        assert result["node_type"] == "Text"
        assert result["content"] == "Hello"
        assert result["metadata"] == {}
        assert "source_location" not in result or result["source_location"] is None

    def test_heading_to_dict(self) -> None:
        """Test converting Heading node to dict."""
        heading = Heading(level=1, content=[Text(content="Title")])
        result = ast_to_dict(heading)

        assert result["node_type"] == "Heading"
        assert result["level"] == 1
        assert len(result["content"]) == 1
        assert result["content"][0]["node_type"] == "Text"
        assert result["content"][0]["content"] == "Title"

    def test_paragraph_to_dict(self) -> None:
        """Test converting Paragraph node to dict."""
        para = Paragraph(content=[Text(content="Hello "), Strong(content=[Text(content="World")])])
        result = ast_to_dict(para)

        assert result["node_type"] == "Paragraph"
        assert len(result["content"]) == 2
        assert result["content"][0]["node_type"] == "Text"
        assert result["content"][1]["node_type"] == "Strong"

    def test_document_to_dict(self) -> None:
        """Test converting Document node to dict."""
        doc = Document(
            children=[Heading(level=1, content=[Text(content="Title")]), Paragraph(content=[Text(content="Body")])]
        )
        result = ast_to_dict(doc)

        assert result["node_type"] == "Document"
        assert len(result["children"]) == 2
        assert result["children"][0]["node_type"] == "Heading"
        assert result["children"][1]["node_type"] == "Paragraph"

    def test_node_with_source_location(self) -> None:
        """Test converting node with source location."""
        loc = SourceLocation(format="pdf", page=1, line=10)
        text = Text(content="Test", source_location=loc)
        result = ast_to_dict(text)

        assert result["source_location"]["node_type"] == "SourceLocation"
        assert result["source_location"]["format"] == "pdf"
        assert result["source_location"]["page"] == 1
        assert result["source_location"]["line"] == 10

    def test_node_with_metadata(self) -> None:
        """Test converting node with metadata."""
        text = Text(content="Test", metadata={"author": "Alice", "date": "2025-01-01"})
        result = ast_to_dict(text)

        assert result["metadata"]["author"] == "Alice"
        assert result["metadata"]["date"] == "2025-01-01"

    def test_math_inline_to_dict_includes_notation(self) -> None:
        """MathInline serialization should include notation and representations."""
        node = MathInline(content="x^2", notation="latex", representations={"mathml": "<math>...</math>"})
        result = ast_to_dict(node)

        assert result["node_type"] == "MathInline"
        assert result["content"] == "x^2"
        assert result["notation"] == "latex"
        assert result["representations"]["mathml"] == "<math>...</math>"

    def test_math_block_to_dict_includes_representations(self) -> None:
        """MathBlock serialization should persist notation fields."""
        node = MathBlock(content="\\frac{a}{b}", notation="latex")
        result = ast_to_dict(node)

        assert result["node_type"] == "MathBlock"
        assert result["content"] == "\\frac{a}{b}"
        assert result["notation"] == "latex"


@pytest.mark.unit
class TestDictToAstConversion:
    """Test dictionary to AST conversion."""

    def test_dict_to_text_node(self) -> None:
        """Test converting dict to Text node."""
        data = {"node_type": "Text", "content": "Hello", "metadata": {}, "source_location": None}
        node = dict_to_ast(data)

        assert isinstance(node, Text)
        assert node.content == "Hello"
        assert node.metadata == {}

    def test_dict_to_heading(self) -> None:
        """Test converting dict to Heading node."""
        data = {
            "node_type": "Heading",
            "level": 2,
            "content": [{"node_type": "Text", "content": "Title", "metadata": {}, "source_location": None}],
            "metadata": {},
            "source_location": None,
        }
        node = dict_to_ast(data)

        assert isinstance(node, Heading)
        assert node.level == 2
        assert len(node.content) == 1
        assert isinstance(node.content[0], Text)
        assert node.content[0].content == "Title"

    def test_dict_to_document(self) -> None:
        """Test converting dict to Document node."""
        data = {
            "node_type": "Document",
            "children": [
                {
                    "node_type": "Paragraph",
                    "content": [{"node_type": "Text", "content": "Body", "metadata": {}, "source_location": None}],
                    "metadata": {},
                    "source_location": None,
                }
            ],
            "metadata": {},
            "source_location": None,
        }
        node = dict_to_ast(data)

        assert isinstance(node, Document)
        assert len(node.children) == 1
        assert isinstance(node.children[0], Paragraph)

    def test_dict_with_source_location(self) -> None:
        """Test converting dict with source location."""
        data = {
            "node_type": "Text",
            "content": "Test",
            "metadata": {},
            "source_location": {"node_type": "SourceLocation", "format": "html", "element_id": "para1"},
        }
        node = dict_to_ast(data)

        assert isinstance(node, Text)
        assert node.source_location is not None
        assert node.source_location.format == "html"
        assert node.source_location.element_id == "para1"

    def test_dict_to_math_inline(self) -> None:
        """Deserialize MathInline with notation metadata."""
        data = {
            "node_type": "MathInline",
            "content": "E=mc^2",
            "notation": "latex",
            "representations": {"html": "<span>E=mc^2</span>"},
            "metadata": {},
            "source_location": None,
        }

        node = dict_to_ast(data)

        assert isinstance(node, MathInline)
        assert node.notation == "latex"
        assert node.representations["html"] == "<span>E=mc^2</span>"

    def test_dict_to_math_block(self) -> None:
        """Deserialize MathBlock preserving notation."""
        data = {
            "node_type": "MathBlock",
            "content": "\\int_0^1 x dx",
            "notation": "latex",
            "metadata": {},
            "source_location": None,
        }

        node = dict_to_ast(data)

        assert isinstance(node, MathBlock)
        assert node.content == "\\int_0^1 x dx"
        assert node.notation == "latex"


@pytest.mark.unit
class TestJsonSerialization:
    """Test JSON serialization."""

    def test_ast_to_json_compact(self) -> None:
        """Test compact JSON serialization."""
        doc = Document(children=[Paragraph(content=[Text(content="Hello")])])
        json_str = ast_to_json(doc)

        # Should be compact (no indentation)
        assert "\n" not in json_str
        assert json.loads(json_str)  # Should be valid JSON

    def test_ast_to_json_pretty(self) -> None:
        """Test pretty JSON serialization."""
        doc = Document(children=[Paragraph(content=[Text(content="Hello")])])
        json_str = ast_to_json(doc, indent=2)

        # Should have indentation
        assert "\n" in json_str
        parsed = json.loads(json_str)
        assert parsed["node_type"] == "Document"

    def test_json_to_ast(self) -> None:
        """Test JSON deserialization."""
        json_str = '{"node_type": "Text", "content": "Hello", "metadata": {}, "source_location": null}'
        node = json_to_ast(json_str)

        assert isinstance(node, Text)
        assert node.content == "Hello"


@pytest.mark.unit
class TestRoundTripConversion:
    """Test round-trip conversion (AST -> JSON -> AST)."""

    def test_simple_document_roundtrip(self) -> None:
        """Test round-trip conversion of simple document."""
        original = Document(
            children=[Heading(level=1, content=[Text(content="Title")]), Paragraph(content=[Text(content="Body")])]
        )

        # Convert to JSON and back
        json_str = ast_to_json(original)
        restored = json_to_ast(json_str)

        # Verify structure is preserved
        assert isinstance(restored, Document)
        assert len(restored.children) == 2
        assert isinstance(restored.children[0], Heading)
        assert restored.children[0].level == 1
        assert isinstance(restored.children[1], Paragraph)

    def test_complex_document_roundtrip(self) -> None:
        """Test round-trip conversion of complex document."""
        original = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Hello "),
                        Strong(content=[Text(content="bold")]),
                        Text(content=" and "),
                        Emphasis(content=[Text(content="italic")]),
                    ]
                ),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                ),
            ]
        )

        json_str = ast_to_json(original)
        restored = json_to_ast(json_str)

        assert isinstance(restored, Document)
        assert len(restored.children) == 2
        assert isinstance(restored.children[0], Paragraph)
        assert len(restored.children[0].content) == 4
        assert isinstance(restored.children[1], List)
        assert len(restored.children[1].items) == 2

    def test_metadata_preservation(self) -> None:
        """Test that metadata is preserved in round-trip."""
        original = Document(
            children=[Paragraph(content=[Text(content="Test")])], metadata={"title": "Doc", "author": "Alice"}
        )

        json_str = ast_to_json(original)
        restored = json_to_ast(json_str)

        assert restored.metadata["title"] == "Doc"
        assert restored.metadata["author"] == "Alice"


@pytest.mark.unit
class TestTableSerialization:
    """Test serialization of table nodes."""

    def test_table_roundtrip(self) -> None:
        """Test round-trip conversion of table."""
        table = Table(
            header=TableRow(cells=[TableCell(content=[Text(content="Header")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="Cell")])])],
            alignments=["left"],
        )

        doc = Document(children=[table])
        json_str = ast_to_json(doc)
        restored = json_to_ast(json_str)

        assert isinstance(restored, Document)
        assert isinstance(restored.children[0], Table)
        assert restored.children[0].header is not None
        assert len(restored.children[0].rows) == 1


@pytest.mark.unit
class TestLinkAndImageSerialization:
    """Test serialization of links and images."""

    def test_link_roundtrip(self) -> None:
        """Test round-trip conversion of link."""
        link = Link(url="https://example.com", content=[Text(content="Click here")], title="Example")

        para = Paragraph(content=[link])
        json_str = ast_to_json(para)
        restored = json_to_ast(json_str)

        assert isinstance(restored, Paragraph)
        assert isinstance(restored.content[0], Link)
        assert restored.content[0].url == "https://example.com"
        assert restored.content[0].title == "Example"

    def test_image_roundtrip(self) -> None:
        """Test round-trip conversion of image."""
        image = Image(
            url="data:image/png;base64,abc123", alt_text="Test image", title="Title", width=100, height=200
        )

        para = Paragraph(content=[image])
        json_str = ast_to_json(para)
        restored = json_to_ast(json_str)

        assert isinstance(restored, Paragraph)
        assert isinstance(restored.content[0], Image)
        assert restored.content[0].url == "data:image/png;base64,abc123"
        assert restored.content[0].alt_text == "Test image"
        assert restored.content[0].width == 100
        assert restored.content[0].height == 200


@pytest.mark.unit
class TestDefinitionListSerialization:
    """Test serialization of definition list nodes."""

    def test_definition_list_to_dict(self) -> None:
        """Test converting DefinitionList to dict."""
        term = DefinitionTerm(content=[Text(content="Term 1")])
        desc1 = DefinitionDescription(content=[Text(content="Description 1")])
        desc2 = DefinitionDescription(content=[Text(content="Description 2")])
        dl = DefinitionList(items=[(term, [desc1, desc2])])

        result = ast_to_dict(dl)

        assert result["node_type"] == "DefinitionList"
        assert len(result["items"]) == 1
        assert result["items"][0]["term"]["node_type"] == "DefinitionTerm"
        assert len(result["items"][0]["descriptions"]) == 2
        assert result["items"][0]["descriptions"][0]["node_type"] == "DefinitionDescription"

    def test_definition_list_roundtrip(self) -> None:
        """Test round-trip conversion of definition list."""
        term1 = DefinitionTerm(content=[Text(content="API")])
        desc1 = DefinitionDescription(content=[Text(content="Application Programming Interface")])

        term2 = DefinitionTerm(content=[Text(content="CPU")])
        desc2a = DefinitionDescription(content=[Text(content="Central Processing Unit")])
        desc2b = DefinitionDescription(content=[Text(content="The main processor in a computer")])

        dl = DefinitionList(items=[(term1, [desc1]), (term2, [desc2a, desc2b])])

        doc = Document(children=[dl])
        json_str = ast_to_json(doc)
        restored = json_to_ast(json_str)

        assert isinstance(restored, Document)
        assert isinstance(restored.children[0], DefinitionList)

        restored_dl = restored.children[0]
        assert len(restored_dl.items) == 2

        # Check first item
        first_term, first_descs = restored_dl.items[0]
        assert isinstance(first_term, DefinitionTerm)
        assert len(first_term.content) == 1
        assert isinstance(first_term.content[0], Text)
        assert first_term.content[0].content == "API"
        assert len(first_descs) == 1
        assert isinstance(first_descs[0], DefinitionDescription)

        # Check second item
        second_term, second_descs = restored_dl.items[1]
        assert isinstance(second_term, DefinitionTerm)
        assert second_term.content[0].content == "CPU"  # type: ignore
        assert len(second_descs) == 2
        assert isinstance(second_descs[0], DefinitionDescription)
        assert isinstance(second_descs[1], DefinitionDescription)

    def test_definition_list_with_metadata(self) -> None:
        """Test definition list with metadata preservation."""
        term = DefinitionTerm(content=[Text(content="Term")], metadata={"lang": "en"})
        desc = DefinitionDescription(content=[Text(content="Desc")], metadata={"author": "Alice"})
        dl = DefinitionList(items=[(term, [desc])], metadata={"source": "glossary"})

        json_str = ast_to_json(dl)
        restored = json_to_ast(json_str)

        assert isinstance(restored, DefinitionList)
        assert restored.metadata["source"] == "glossary"

        restored_term, restored_descs = restored.items[0]
        assert restored_term.metadata["lang"] == "en"
        assert restored_descs[0].metadata["author"] == "Alice"

    def test_definition_list_with_source_location(self) -> None:
        """Test definition list with source location preservation."""
        loc = SourceLocation(format="html", element_id="glossary-1")
        term = DefinitionTerm(content=[Text(content="Term")], source_location=loc)
        desc = DefinitionDescription(content=[Text(content="Desc")])
        dl = DefinitionList(items=[(term, [desc])])

        json_str = ast_to_json(dl)
        restored = json_to_ast(json_str)

        assert isinstance(restored, DefinitionList)
        restored_term, _ = restored.items[0]
        assert restored_term.source_location is not None
        assert restored_term.source_location.format == "html"
        assert restored_term.source_location.element_id == "glossary-1"


@pytest.mark.unit
class TestFootnoteSerialization:
    """Test serialization of footnote nodes."""

    def test_footnote_reference_to_dict(self) -> None:
        """Test converting FootnoteReference to dict."""
        ref = FootnoteReference(identifier="1")
        result = ast_to_dict(ref)

        assert result["node_type"] == "FootnoteReference"
        assert result["identifier"] == "1"
        assert result["metadata"] == {}
        assert "source_location" not in result or result["source_location"] is None

    def test_footnote_definition_to_dict(self) -> None:
        """Test converting FootnoteDefinition to dict."""
        defn = FootnoteDefinition(identifier="note1", content=[Paragraph(content=[Text(content="Footnote text")])])
        result = ast_to_dict(defn)

        assert result["node_type"] == "FootnoteDefinition"
        assert result["identifier"] == "note1"
        assert len(result["content"]) == 1
        assert result["content"][0]["node_type"] == "Paragraph"
        assert result["metadata"] == {}

    def test_footnote_reference_roundtrip(self) -> None:
        """Test round-trip conversion of FootnoteReference."""
        original = FootnoteReference(identifier="ref1", metadata={"source": "docx"})
        json_str = ast_to_json(original)
        restored = json_to_ast(json_str)

        assert isinstance(restored, FootnoteReference)
        assert restored.identifier == "ref1"
        assert restored.metadata["source"] == "docx"

    def test_footnote_definition_roundtrip(self) -> None:
        """Test round-trip conversion of FootnoteDefinition."""
        original = FootnoteDefinition(
            identifier="fn2",
            content=[Paragraph(content=[Text(content="This is a "), Strong(content=[Text(content="footnote")])])],
        )

        json_str = ast_to_json(original)
        restored = json_to_ast(json_str)

        assert isinstance(restored, FootnoteDefinition)
        assert restored.identifier == "fn2"
        assert len(restored.content) == 1
        assert isinstance(restored.content[0], Paragraph)
        assert len(restored.content[0].content) == 2
        assert isinstance(restored.content[0].content[0], Text)
        assert isinstance(restored.content[0].content[1], Strong)

    def test_footnote_with_source_location(self) -> None:
        """Test footnote nodes with source location preservation."""
        loc = SourceLocation(format="pdf", page=5, line=42)
        ref = FootnoteReference(identifier="1", source_location=loc)

        json_str = ast_to_json(ref)
        restored = json_to_ast(json_str)

        assert isinstance(restored, FootnoteReference)
        assert restored.source_location is not None
        assert restored.source_location.format == "pdf"
        assert restored.source_location.page == 5
        assert restored.source_location.line == 42

    def test_document_with_footnotes_roundtrip(self) -> None:
        """Test document with footnotes round-trip conversion."""
        original = Document(
            children=[
                Paragraph(content=[Text(content="Main text"), FootnoteReference(identifier="1")]),
                FootnoteDefinition(identifier="1", content=[Paragraph(content=[Text(content="Footnote content")])]),
            ]
        )

        json_str = ast_to_json(original)
        restored = json_to_ast(json_str)

        assert isinstance(restored, Document)
        assert len(restored.children) == 2

        # Check paragraph with inline footnote reference
        para = restored.children[0]
        assert isinstance(para, Paragraph)
        assert len(para.content) == 2
        assert isinstance(para.content[1], FootnoteReference)
        assert para.content[1].identifier == "1"

        # Check footnote definition
        defn = restored.children[1]
        assert isinstance(defn, FootnoteDefinition)
        assert defn.identifier == "1"
        assert len(defn.content) == 1
        assert isinstance(defn.content[0], Paragraph)

    def test_multiple_footnotes_with_metadata(self) -> None:
        """Test multiple footnotes with metadata preservation."""
        ref1 = FootnoteReference(identifier="a", metadata={"type": "citation"})
        ref2 = FootnoteReference(identifier="b", metadata={"type": "comment"})
        defn1 = FootnoteDefinition(
            identifier="a", content=[Paragraph(content=[Text(content="Citation")])], metadata={"author": "Smith"}
        )
        defn2 = FootnoteDefinition(
            identifier="b", content=[Paragraph(content=[Text(content="Comment")])], metadata={"author": "Jones"}
        )

        doc = Document(children=[Paragraph(content=[ref1, ref2]), defn1, defn2])

        json_str = ast_to_json(doc)
        restored = json_to_ast(json_str)

        assert isinstance(restored, Document)

        # Check references
        para = restored.children[0]
        assert isinstance(para, Paragraph)
        assert para.content[0].metadata["type"] == "citation"  # type: ignore
        assert para.content[1].metadata["type"] == "comment"  # type: ignore

        # Check definitions
        assert restored.children[1].metadata["author"] == "Smith"  # type: ignore
        assert restored.children[2].metadata["author"] == "Jones"  # type: ignore
