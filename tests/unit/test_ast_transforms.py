#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for AST transformation utilities."""
import pytest

from all2md.ast import Document, Emphasis, Heading, Image, Link, Paragraph, Strong, Text
from all2md.ast.transforms import (
    HeadingLevelTransformer,
    LinkRewriter,
    NodeCollector,
    TextReplacer,
    clone_node,
    extract_nodes,
    filter_nodes,
    merge_documents,
    transform_nodes,
)


@pytest.mark.unit
class TestCloneNode:
    """Test node cloning."""

    def test_clone_simple_node(self) -> None:
        """Test cloning a simple text node."""
        original = Text(content="Hello")
        cloned = clone_node(original)

        assert cloned is not original
        assert cloned.content == original.content
        assert isinstance(cloned, Text)

    def test_clone_preserves_metadata(self) -> None:
        """Test that cloning preserves metadata."""
        original = Text(content="Test", metadata={"key": "value"})
        cloned = clone_node(original)

        assert cloned.metadata == original.metadata
        assert cloned.metadata is not original.metadata  # Deep copy

    def test_clone_document(self) -> None:
        """Test cloning a complex document."""
        original = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        cloned = clone_node(original)

        assert cloned is not original
        assert isinstance(cloned, Document)
        assert len(cloned.children) == len(original.children)
        assert cloned.children[0] is not original.children[0]  # Deep copy


@pytest.mark.unit
class TestExtractNodes:
    """Test node extraction."""

    def test_extract_all_headings(self) -> None:
        """Test extracting all heading nodes."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="H1")]),
                Paragraph(content=[Text(content="Para")]),
                Heading(level=2, content=[Text(content="H2")]),
            ]
        )

        headings = extract_nodes(doc, Heading)

        assert len(headings) == 2
        assert all(isinstance(h, Heading) for h in headings)
        assert headings[0].level == 1
        assert headings[1].level == 2

    def test_extract_all_text_nodes(self) -> None:
        """Test extracting all text nodes."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(content=[Text(content="Para1"), Strong(content=[Text(content="Bold")])]),
            ]
        )

        texts = extract_nodes(doc, Text)

        assert len(texts) == 3
        assert all(isinstance(t, Text) for t in texts)

    def test_extract_with_none_type(self) -> None:
        """Test extracting all nodes (no type filter)."""
        doc = Document(
            children=[Heading(level=1, content=[Text(content="Title")]), Paragraph(content=[Text(content="Body")])]
        )

        all_nodes = extract_nodes(doc, None)

        # Should include Document, Heading, Paragraph, and Text nodes
        assert len(all_nodes) > 3


@pytest.mark.unit
class TestFilterNodes:
    """Test node filtering."""

    def test_filter_out_images(self) -> None:
        """Test filtering out all images."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Text"), Image(url="img.png", alt_text="Image")]),
                Paragraph(content=[Image(url="img2.png", alt_text="Another")]),
            ]
        )

        filtered = filter_nodes(doc, lambda n: not isinstance(n, Image))

        # Extract all nodes from filtered document
        all_nodes = extract_nodes(filtered, None)
        images = [n for n in all_nodes if isinstance(n, Image)]

        assert len(images) == 0

    def test_filter_keep_only_headings_and_paragraphs(self) -> None:
        """Test keeping only specific node types."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(content=[Text(content="Para")]),
                Image(url="test.png", alt_text="Test"),
            ]
        )

        filtered = filter_nodes(doc, lambda n: isinstance(n, (Heading, Paragraph, Text, Document)))

        # Should only have Document, Heading, Paragraph, Text
        all_nodes = extract_nodes(filtered, None)
        images = [n for n in all_nodes if isinstance(n, Image)]
        assert len(images) == 0


@pytest.mark.unit
class TestTransformNodes:
    """Test general node transformation."""

    def test_transform_with_heading_transformer(self) -> None:
        """Test applying heading level transformer."""
        doc = Document(
            children=[Heading(level=1, content=[Text(content="H1")]), Heading(level=2, content=[Text(content="H2")])]
        )

        transformer = HeadingLevelTransformer(offset=1)
        result = transform_nodes(doc, transformer)

        headings = extract_nodes(result, Heading)
        assert headings[0].level == 2
        assert headings[1].level == 3

    def test_transform_preserves_document_structure(self) -> None:
        """Test that transformation preserves document structure."""
        doc = Document(
            children=[Heading(level=1, content=[Text(content="Title")]), Paragraph(content=[Text(content="Body")])]
        )

        transformer = HeadingLevelTransformer(offset=0)  # No change
        result = transform_nodes(doc, transformer)

        assert isinstance(result, Document)
        assert len(result.children) == 2


@pytest.mark.unit
class TestMergeDocuments:
    """Test document merging."""

    def test_merge_two_documents(self) -> None:
        """Test merging two documents."""
        doc1 = Document(children=[Heading(level=1, content=[Text(content="Doc 1")])])
        doc2 = Document(children=[Paragraph(content=[Text(content="Doc 2")])])

        merged = merge_documents([doc1, doc2])

        assert isinstance(merged, Document)
        assert len(merged.children) == 2
        assert isinstance(merged.children[0], Heading)
        assert isinstance(merged.children[1], Paragraph)

    def test_merge_preserves_metadata(self) -> None:
        """Test that merging combines metadata."""
        doc1 = Document(children=[], metadata={"author": "Alice"})
        doc2 = Document(children=[], metadata={"date": "2025-01-01"})

        merged = merge_documents([doc1, doc2])

        assert merged.metadata.get("author") == "Alice"
        assert merged.metadata.get("date") == "2025-01-01"


@pytest.mark.unit
class TestHeadingLevelTransformer:
    """Test heading level transformation."""

    def test_increase_heading_levels(self) -> None:
        """Test increasing heading levels."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])

        transformer = HeadingLevelTransformer(offset=2)
        result = transformer.transform(doc)

        assert isinstance(result, Document)
        heading = result.children[0]
        assert isinstance(heading, Heading)
        assert heading.level == 3

    def test_decrease_heading_levels(self) -> None:
        """Test decreasing heading levels."""
        doc = Document(children=[Heading(level=3, content=[Text(content="Title")])])

        transformer = HeadingLevelTransformer(offset=-1)
        result = transformer.transform(doc)

        heading = result.children[0]
        assert heading.level == 2

    def test_clamp_to_min_level(self) -> None:
        """Test that levels are clamped to minimum."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])

        transformer = HeadingLevelTransformer(offset=-5)  # Would go to -4
        result = transformer.transform(doc)

        heading = result.children[0]
        assert heading.level == 1  # Clamped to minimum

    def test_clamp_to_max_level(self) -> None:
        """Test that levels are clamped to maximum."""
        doc = Document(children=[Heading(level=5, content=[Text(content="Title")])])

        transformer = HeadingLevelTransformer(offset=5)  # Would go to 10
        result = transformer.transform(doc)

        heading = result.children[0]
        assert heading.level == 6  # Clamped to maximum


@pytest.mark.unit
class TestLinkRewriter:
    """Test link URL rewriting."""

    def test_rewrite_link_urls(self) -> None:
        """Test rewriting link URLs."""
        doc = Document(
            children=[
                Paragraph(content=[Link(url="/relative/path", content=[Text(content="Link")], title=None)])
            ]
        )

        def make_absolute(url: str) -> str:
            if url.startswith("/"):
                return f"https://example.com{url}"
            return url

        transformer = LinkRewriter(make_absolute)
        result = transformer.transform(doc)

        link = result.children[0].content[0]
        assert isinstance(link, Link)
        assert link.url == "https://example.com/relative/path"

    def test_rewrite_image_urls(self) -> None:
        """Test rewriting image URLs."""
        doc = Document(children=[Paragraph(content=[Image(url="/img/test.png", alt_text="Test")])])

        def make_absolute(url: str) -> str:
            if url.startswith("/"):
                return f"https://example.com{url}"
            return url

        transformer = LinkRewriter(make_absolute)
        result = transformer.transform(doc)

        image = result.children[0].content[0]
        assert isinstance(image, Image)
        assert image.url == "https://example.com/img/test.png"


@pytest.mark.unit
class TestTextReplacer:
    """Test text replacement."""

    def test_replace_simple_text(self) -> None:
        """Test simple text replacement."""
        doc = Document(children=[Paragraph(content=[Text(content="Hello world")])])

        transformer = TextReplacer("world", "universe")
        result = transformer.transform(doc)

        text = result.children[0].content[0]
        assert isinstance(text, Text)
        assert text.content == "Hello universe"

    def test_replace_with_regex(self) -> None:
        """Test regex-based text replacement."""
        doc = Document(children=[Paragraph(content=[Text(content="Test 123 and 456")])])

        transformer = TextReplacer(r"\d+", "XXX", use_regex=True)
        result = transformer.transform(doc)

        text = result.children[0].content[0]
        assert text.content == "Test XXX and XXX"

    def test_replace_multiple_occurrences(self) -> None:
        """Test replacing multiple occurrences."""
        doc = Document(children=[Paragraph(content=[Text(content="foo bar foo")])])

        transformer = TextReplacer("foo", "baz")
        result = transformer.transform(doc)

        text = result.children[0].content[0]
        assert text.content == "baz bar baz"


@pytest.mark.unit
class TestNodeCollector:
    """Test node collection."""

    def test_collect_all_nodes(self) -> None:
        """Test collecting all nodes."""
        doc = Document(
            children=[Heading(level=1, content=[Text(content="Title")]), Paragraph(content=[Text(content="Body")])]
        )

        collector = NodeCollector()
        doc.accept(collector)

        # Should collect all nodes including Document
        assert len(collector.collected) > 3

    def test_collect_with_predicate(self) -> None:
        """Test collecting nodes with a predicate."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="H1")]),
                Heading(level=2, content=[Text(content="H2")]),
                Paragraph(content=[Text(content="Para")]),
            ]
        )

        collector = NodeCollector(predicate=lambda n: isinstance(n, Heading))
        doc.accept(collector)

        assert len(collector.collected) == 2
        assert all(isinstance(n, Heading) for n in collector.collected)
