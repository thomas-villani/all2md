#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for AST transformation utilities."""
import pytest

from all2md.ast import (
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Heading,
    Image,
    Link,
    Paragraph,
    Strong,
    Text,
)
from all2md.ast.transforms import (
    HeadingLevelTransformer,
    LinkRewriter,
    NodeCollector,
    NodeTransformer,
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

    def test_filter_preserves_document_even_when_excluded_by_predicate(self) -> None:
        """Test that Document is always preserved even if predicate excludes it."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(content=[Text(content="Content")]),
            ]
        )

        # Predicate that only keeps Paragraph nodes (excludes Document)
        filtered = filter_nodes(doc, lambda n: isinstance(n, Paragraph))

        # Should still return a Document, not None
        assert isinstance(filtered, Document)
        # But children should be filtered
        assert len(filtered.children) == 1
        assert isinstance(filtered.children[0], Paragraph)


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

    def test_invalid_regex_pattern_raises_error(self) -> None:
        """Test that invalid regex patterns raise ValueError."""
        # Invalid regex: unmatched parenthesis
        with pytest.raises(ValueError, match="Invalid regular expression pattern"):
            TextReplacer(r"(invalid", "replacement", use_regex=True)

        # Invalid regex: invalid escape sequence
        with pytest.raises(ValueError, match="Invalid regular expression pattern"):
            TextReplacer(r"\k", "replacement", use_regex=True)

        # Invalid regex: nested quantifiers (catastrophic backtracking)
        # Note: Python's re will accept this but it's still a valid regex
        # The pattern itself compiles, so we test with an actually invalid one
        with pytest.raises(ValueError, match="Invalid regular expression pattern"):
            TextReplacer(r"(?P<invalid)", "replacement", use_regex=True)

    def test_valid_regex_compiles_once(self) -> None:
        """Test that valid regex is compiled once in __init__."""
        transformer = TextReplacer(r"\d+", "NUM", use_regex=True)

        # Compiled pattern should be stored
        assert transformer._compiled_pattern is not None
        assert transformer._compiled_pattern.pattern == r"\d+"

        # Use it multiple times
        doc1 = Document(children=[Paragraph(content=[Text(content="Test 123")])])
        doc2 = Document(children=[Paragraph(content=[Text(content="Value 456")])])

        result1 = transformer.transform(doc1)
        result2 = transformer.transform(doc2)

        assert result1.children[0].content[0].content == "Test NUM"
        assert result2.children[0].content[0].content == "Value NUM"


@pytest.mark.unit
class TestLinkRewriterValidation:
    """Test LinkRewriter URL validation."""

    def test_validate_urls_rejects_javascript_scheme(self) -> None:
        """Test that javascript: URLs are rejected by default."""
        doc = Document(
            children=[
                Paragraph(content=[Link(url="/test", content=[Text(content="Link")], title=None)])
            ]
        )

        def dangerous_mapper(url: str) -> str:
            # Malicious mapper that creates javascript: URL
            return "javascript:alert(1)"

        transformer = LinkRewriter(dangerous_mapper, validate_urls=True)

        with pytest.raises(ValueError, match="dangerous scheme"):
            transformer.transform(doc)

    def test_validate_urls_rejects_vbscript_scheme(self) -> None:
        """Test that vbscript: URLs are rejected by default."""
        doc = Document(
            children=[
                Paragraph(content=[Link(url="/test", content=[Text(content="Link")], title=None)])
            ]
        )

        def dangerous_mapper(url: str) -> str:
            return "vbscript:msgbox(1)"

        transformer = LinkRewriter(dangerous_mapper, validate_urls=True)

        with pytest.raises(ValueError, match="dangerous scheme"):
            transformer.transform(doc)

    def test_validate_urls_accepts_safe_schemes(self) -> None:
        """Test that safe URL schemes are accepted."""
        doc = Document(
            children=[
                Paragraph(content=[Link(url="/test", content=[Text(content="Link")], title=None)])
            ]
        )

        def safe_mapper(url: str) -> str:
            return "https://example.com" + url

        transformer = LinkRewriter(safe_mapper, validate_urls=True)
        result = transformer.transform(doc)

        link = result.children[0].content[0]
        assert isinstance(link, Link)
        assert link.url == "https://example.com/test"

    def test_validate_urls_can_be_disabled(self) -> None:
        """Test that URL validation can be disabled."""
        doc = Document(
            children=[
                Paragraph(content=[Link(url="/test", content=[Text(content="Link")], title=None)])
            ]
        )

        def custom_mapper(url: str) -> str:
            # Creates a non-standard but intentional URL
            return "custom-scheme://test"

        transformer = LinkRewriter(custom_mapper, validate_urls=False)
        result = transformer.transform(doc)

        link = result.children[0].content[0]
        assert link.url == "custom-scheme://test"

    def test_validate_urls_for_images(self) -> None:
        """Test that image URL validation works."""
        doc = Document(children=[Paragraph(content=[Image(url="/img.png", alt_text="Test")])])

        def dangerous_mapper(url: str) -> str:
            return "javascript:alert(1)"

        transformer = LinkRewriter(dangerous_mapper, validate_urls=True)

        with pytest.raises(ValueError, match="dangerous scheme"):
            transformer.transform(doc)

    def test_relative_urls_accepted(self) -> None:
        """Test that relative URLs are accepted."""
        doc = Document(
            children=[
                Paragraph(content=[Link(url="/test", content=[Text(content="Link")], title=None)])
            ]
        )

        def identity_mapper(url: str) -> str:
            return url

        transformer = LinkRewriter(identity_mapper, validate_urls=True)
        result = transformer.transform(doc)

        link = result.children[0].content[0]
        assert link.url == "/test"


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


@pytest.mark.unit
class TestDefinitionListTransformation:
    """Test definition list transformation with None filtering."""

    def test_transform_definition_list_filters_none_term(self) -> None:
        """Test that None terms are filtered out during transformation."""

        class RemoveFirstTermTransformer(NodeTransformer):
            def __init__(self):
                self.first_term_seen = False

            def visit_definition_term(self, node):
                if not self.first_term_seen:
                    self.first_term_seen = True
                    return None
                return super().visit_definition_term(node)

        dl = DefinitionList(
            items=[
                (
                    DefinitionTerm(content=[Text(content="Term 1")]),
                    [DefinitionDescription(content=[Text(content="Desc 1")])]
                ),
                (
                    DefinitionTerm(content=[Text(content="Term 2")]),
                    [DefinitionDescription(content=[Text(content="Desc 2")])]
                ),
            ]
        )

        transformer = RemoveFirstTermTransformer()
        result = transformer.transform(dl)

        assert isinstance(result, DefinitionList)
        assert len(result.items) == 1
        assert result.items[0][0].content[0].content == "Term 2"

    def test_transform_definition_list_filters_none_descriptions(self) -> None:
        """Test that None descriptions are filtered out during transformation."""

        class RemoveFirstDescriptionTransformer(NodeTransformer):
            def __init__(self):
                self.first_desc_seen = False

            def visit_definition_description(self, node):
                if not self.first_desc_seen:
                    self.first_desc_seen = True
                    return None
                return super().visit_definition_description(node)

        dl = DefinitionList(
            items=[
                (
                    DefinitionTerm(content=[Text(content="Term")]),
                    [
                        DefinitionDescription(content=[Text(content="Desc 1")]),
                        DefinitionDescription(content=[Text(content="Desc 2")])
                    ]
                ),
            ]
        )

        transformer = RemoveFirstDescriptionTransformer()
        result = transformer.transform(dl)

        assert isinstance(result, DefinitionList)
        assert len(result.items) == 1
        assert len(result.items[0][1]) == 1
        assert result.items[0][1][0].content[0].content == "Desc 2"

    def test_transform_definition_list_removes_item_if_all_descriptions_none(self) -> None:
        """Test that items with all None descriptions are removed."""

        class RemoveAllDescriptionsTransformer(NodeTransformer):
            def visit_definition_description(self, node):
                return None

        dl = DefinitionList(
            items=[
                (
                    DefinitionTerm(content=[Text(content="Term 1")]),
                    [DefinitionDescription(content=[Text(content="Desc 1")])]
                ),
                (
                    DefinitionTerm(content=[Text(content="Term 2")]),
                    [DefinitionDescription(content=[Text(content="Desc 2")])]
                ),
            ]
        )

        transformer = RemoveAllDescriptionsTransformer()
        result = transformer.transform(dl)

        assert isinstance(result, DefinitionList)
        assert len(result.items) == 0

    def test_transform_definition_list_preserves_valid_items(self) -> None:
        """Test that valid items are preserved during transformation."""
        dl = DefinitionList(
            items=[
                (
                    DefinitionTerm(content=[Text(content="Term 1")]),
                    [DefinitionDescription(content=[Text(content="Desc 1")])]
                ),
                (
                    DefinitionTerm(content=[Text(content="Term 2")]),
                    [
                        DefinitionDescription(content=[Text(content="Desc 2a")]),
                        DefinitionDescription(content=[Text(content="Desc 2b")])
                    ]
                ),
            ]
        )

        transformer = NodeTransformer()
        result = transformer.transform(dl)

        assert isinstance(result, DefinitionList)
        assert len(result.items) == 2
        assert result.items[0][0].content[0].content == "Term 1"
        assert len(result.items[0][1]) == 1
        assert result.items[1][0].content[0].content == "Term 2"
        assert len(result.items[1][1]) == 2
