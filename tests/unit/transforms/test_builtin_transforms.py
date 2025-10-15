#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for built-in transforms."""

import pytest

from all2md.ast import Document, Heading, Image, Link, Paragraph, Text
from all2md.transforms.builtin import (
    AddAttachmentFootnotesTransform,
    AddConversionTimestampTransform,
    AddHeadingIdsTransform,
    CalculateWordCountTransform,
    GenerateTocTransform,
    HeadingOffsetTransform,
    LinkRewriterTransform,
    RemoveBoilerplateTextTransform,
    RemoveImagesTransform,
    RemoveNodesTransform,
    TextReplacerTransform,
)

# Fixtures

@pytest.fixture
def sample_document():
    """Create a sample document for testing."""
    return Document(
        children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[
                Text(content="Hello "),
                Link(url="https://example.com", content=[Text(content="world")])
            ]),
            Paragraph(content=[
                Image(url="image.png", alt_text="An image")
            ]),
            Paragraph(content=[Text(content="CONFIDENTIAL")]),
        ],
        metadata={"author": "Test"}
    )


# RemoveImagesTransform tests

class TestRemoveImagesTransform:
    """Tests for RemoveImagesTransform."""

    def test_removes_all_images(self, sample_document):
        """Test that all images are removed."""
        transform = RemoveImagesTransform()
        result = transform.transform(sample_document)

        # Check no images remain
        assert isinstance(result, Document)
        # Count images in result
        image_count = 0
        for child in result.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Image):
                        image_count += 1
        assert image_count == 0

    def test_preserves_other_nodes(self, sample_document):
        """Test that other nodes are preserved."""
        transform = RemoveImagesTransform()
        result = transform.transform(sample_document)

        # Should still have headings and paragraphs
        assert len(result.children) > 0
        assert any(isinstance(child, Heading) for child in result.children)

    def test_empty_document(self):
        """Test with empty document."""
        doc = Document(children=[])
        transform = RemoveImagesTransform()
        result = transform.transform(doc)

        assert isinstance(result, Document)
        assert len(result.children) == 0


# RemoveNodesTransform tests

class TestRemoveNodesTransform:
    """Tests for RemoveNodesTransform."""

    def test_removes_specified_node_type(self, sample_document):
        """Test removing specific node type."""
        transform = RemoveNodesTransform(node_types=['image'])
        result = transform.transform(sample_document)

        # No images should remain
        image_count = 0
        for child in result.children:
            if isinstance(child, Paragraph):
                for node in child.content:
                    if isinstance(node, Image):
                        image_count += 1
        assert image_count == 0

    def test_removes_multiple_node_types(self):
        """Test removing multiple node types."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[Text(content="Text")]),
            Paragraph(content=[Image(url="test.png")])
        ])

        transform = RemoveNodesTransform(node_types=['heading', 'image'])
        result = transform.transform(doc)

        # Heading should be removed, image removed from paragraph
        # Should have 2 paragraphs (one with text, one empty after image removal)
        assert len(result.children) == 2
        assert all(isinstance(child, Paragraph) for child in result.children)
        # First paragraph should have text
        assert len(result.children[0].content) == 1
        # Second paragraph should be empty (image was removed)
        assert len(result.children[1].content) == 0

    def test_preserves_unspecified_types(self, sample_document):
        """Test that unspecified types are preserved."""
        transform = RemoveNodesTransform(node_types=['image'])
        result = transform.transform(sample_document)

        # Should still have headings
        assert any(isinstance(child, Heading) for child in result.children)

    def test_raises_error_for_document_type(self):
        """Test that attempting to remove 'document' raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            RemoveNodesTransform(node_types=['document'])

        assert "Cannot remove 'document' node type" in str(exc_info.value)
        assert "break the pipeline" in str(exc_info.value)

    def test_allows_other_types_with_document_excluded(self):
        """Test that other types work normally when document is not included."""
        # This should work fine
        transform = RemoveNodesTransform(node_types=['image', 'heading'])
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[Text(content="Text")]),
        ])

        result = transform.transform(doc)

        # Document should still exist, heading removed
        assert isinstance(result, Document)
        assert len(result.children) == 1
        assert isinstance(result.children[0], Paragraph)


# HeadingOffsetTransform tests

class TestHeadingOffsetTransform:
    """Tests for HeadingOffsetTransform."""

    def test_increases_heading_levels(self):
        """Test increasing heading levels."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="H1")]),
            Heading(level=2, content=[Text(content="H2")]),
        ])

        transform = HeadingOffsetTransform(offset=1)
        result = transform.transform(doc)

        headings = [child for child in result.children if isinstance(child, Heading)]
        assert headings[0].level == 2  # H1 -> H2
        assert headings[1].level == 3  # H2 -> H3

    def test_decreases_heading_levels(self):
        """Test decreasing heading levels."""
        doc = Document(children=[
            Heading(level=3, content=[Text(content="H3")]),
            Heading(level=4, content=[Text(content="H4")]),
        ])

        transform = HeadingOffsetTransform(offset=-1)
        result = transform.transform(doc)

        headings = [child for child in result.children if isinstance(child, Heading)]
        assert headings[0].level == 2  # H3 -> H2
        assert headings[1].level == 3  # H4 -> H3

    def test_clamps_to_valid_range(self):
        """Test that levels are clamped to 1-6."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="H1")]),
            Heading(level=6, content=[Text(content="H6")]),
        ])

        # Try to go below 1
        transform = HeadingOffsetTransform(offset=-2)
        result = transform.transform(doc)
        headings = [child for child in result.children if isinstance(child, Heading)]
        assert headings[0].level == 1  # Clamped at 1

        # Try to go above 6
        transform = HeadingOffsetTransform(offset=2)
        result = transform.transform(doc)
        headings = [child for child in result.children if isinstance(child, Heading)]
        assert headings[1].level == 6  # Clamped at 6


# LinkRewriterTransform tests

class TestLinkRewriterTransform:
    """Tests for LinkRewriterTransform."""

    def test_rewrites_matching_links(self):
        """Test rewriting links that match pattern."""
        doc = Document(children=[
            Paragraph(content=[
                Link(url="/docs/page", content=[Text(content="Link")])
            ])
        ])

        transform = LinkRewriterTransform(
            pattern=r'^/docs/',
            replacement='https://example.com/docs/'
        )
        result = transform.transform(doc)

        link = result.children[0].content[0]
        assert link.url == "https://example.com/docs/page"

    def test_preserves_non_matching_links(self):
        """Test that non-matching links are unchanged."""
        doc = Document(children=[
            Paragraph(content=[
                Link(url="https://other.com/page", content=[Text(content="Link")])
            ])
        ])

        transform = LinkRewriterTransform(
            pattern=r'^/docs/',
            replacement='https://example.com/docs/'
        )
        result = transform.transform(doc)

        link = result.children[0].content[0]
        assert link.url == "https://other.com/page"

    def test_regex_groups(self):
        """Test using regex capture groups."""
        doc = Document(children=[
            Paragraph(content=[
                Link(url="/docs/guide/intro", content=[Text(content="Link")])
            ])
        ])

        transform = LinkRewriterTransform(
            pattern=r'^/docs/(.+)$',
            replacement=r'https://example.com/documentation/\1'
        )
        result = transform.transform(doc)

        link = result.children[0].content[0]
        assert link.url == "https://example.com/documentation/guide/intro"


# TextReplacerTransform tests

class TestTextReplacerTransform:
    """Tests for TextReplacerTransform."""

    def test_replaces_text(self):
        """Test basic text replacement."""
        doc = Document(children=[
            Paragraph(content=[Text(content="TODO: finish this")])
        ])

        transform = TextReplacerTransform(find="TODO", replace="DONE")
        result = transform.transform(doc)

        text = result.children[0].content[0]
        assert text.content == "DONE: finish this"

    def test_replaces_all_occurrences(self):
        """Test that all occurrences are replaced."""
        doc = Document(children=[
            Paragraph(content=[Text(content="TODO: do TODO items")])
        ])

        transform = TextReplacerTransform(find="TODO", replace="DONE")
        result = transform.transform(doc)

        text = result.children[0].content[0]
        assert text.content == "DONE: do DONE items"

    def test_case_sensitive(self):
        """Test that replacement is case-sensitive."""
        doc = Document(children=[
            Paragraph(content=[Text(content="TODO todo Todo")])
        ])

        transform = TextReplacerTransform(find="TODO", replace="DONE")
        result = transform.transform(doc)

        text = result.children[0].content[0]
        assert text.content == "DONE todo Todo"


# AddHeadingIdsTransform tests

class TestAddHeadingIdsTransform:
    """Tests for AddHeadingIdsTransform."""

    def test_adds_ids_to_headings(self):
        """Test that IDs are added to headings."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="My Title")])
        ])

        transform = AddHeadingIdsTransform()
        result = transform.transform(doc)

        heading = result.children[0]
        assert 'id' in heading.metadata
        assert heading.metadata['id'] == "my-title"

    def test_handles_duplicates(self):
        """Test that duplicate headings get unique IDs."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Heading(level=2, content=[Text(content="Title")]),
        ])

        transform = AddHeadingIdsTransform()
        result = transform.transform(doc)

        h1, h2 = result.children
        assert h1.metadata['id'] == "title"
        assert h2.metadata['id'] == "title-2"

    def test_adds_prefix(self):
        """Test ID prefix."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")])
        ])

        transform = AddHeadingIdsTransform(id_prefix="doc-")
        result = transform.transform(doc)

        heading = result.children[0]
        assert heading.metadata['id'] == "doc-title"

    def test_custom_separator(self):
        """Test custom separator."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="My Title")])
        ])

        transform = AddHeadingIdsTransform(separator="_")
        result = transform.transform(doc)

        heading = result.children[0]
        assert heading.metadata['id'] == "my_title"

    def test_handles_special_characters(self):
        """Test that special characters are removed."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title! With @#$ Special")])
        ])

        transform = AddHeadingIdsTransform()
        result = transform.transform(doc)

        heading = result.children[0]
        assert heading.metadata['id'] == "title-with-special"


# RemoveBoilerplateTextTransform tests

class TestRemoveBoilerplateTextTransform:
    """Tests for RemoveBoilerplateTextTransform."""

    def test_removes_default_boilerplate(self):
        """Test removing default boilerplate patterns."""
        doc = Document(children=[
            Paragraph(content=[Text(content="CONFIDENTIAL")]),
            Paragraph(content=[Text(content="Page 1 of 5")]),
            Paragraph(content=[Text(content="Normal text")]),
        ])

        transform = RemoveBoilerplateTextTransform()
        result = transform.transform(doc)

        # Should only have normal text paragraph
        assert len(result.children) == 1
        text = result.children[0].content[0]
        assert text.content == "Normal text"

    def test_custom_patterns(self):
        """Test custom boilerplate patterns."""
        doc = Document(children=[
            Paragraph(content=[Text(content="DRAFT")]),
            Paragraph(content=[Text(content="Normal text")]),
        ])

        transform = RemoveBoilerplateTextTransform(patterns=[r"^DRAFT$"])
        result = transform.transform(doc)

        assert len(result.children) == 1
        text = result.children[0].content[0]
        assert text.content == "Normal text"

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        doc = Document(children=[
            Paragraph(content=[Text(content="confidential")]),
            Paragraph(content=[Text(content="CONFIDENTIAL")]),
        ])

        transform = RemoveBoilerplateTextTransform()
        result = transform.transform(doc)

        # Both should be removed
        assert len(result.children) == 0


# AddConversionTimestampTransform tests

class TestAddConversionTimestampTransform:
    """Tests for AddConversionTimestampTransform."""

    def test_adds_iso_timestamp(self):
        """Test adding ISO format timestamp."""
        doc = Document(children=[])

        transform = AddConversionTimestampTransform()
        result = transform.transform(doc)

        assert 'conversion_timestamp' in result.metadata
        # Check it's ISO format (contains T)
        assert 'T' in result.metadata['conversion_timestamp']

    def test_adds_unix_timestamp(self):
        """Test adding Unix timestamp."""
        doc = Document(children=[])

        transform = AddConversionTimestampTransform(timestamp_format="unix")
        result = transform.transform(doc)

        assert 'conversion_timestamp' in result.metadata
        # Unix timestamp should be numeric
        assert result.metadata['conversion_timestamp'].isdigit()

    def test_custom_field_name(self):
        """Test custom field name."""
        doc = Document(children=[])

        transform = AddConversionTimestampTransform(field_name="converted_at")
        result = transform.transform(doc)

        assert 'converted_at' in result.metadata

    def test_custom_format(self):
        """Test custom strftime format."""
        doc = Document(children=[])

        transform = AddConversionTimestampTransform(timestamp_format="%Y-%m-%d")
        result = transform.transform(doc)

        # Should be in YYYY-MM-DD format
        timestamp = result.metadata['conversion_timestamp']
        assert len(timestamp) == 10
        assert timestamp.count('-') == 2


# CalculateWordCountTransform tests

class TestCalculateWordCountTransform:
    """Tests for CalculateWordCountTransform."""

    def test_calculates_word_count(self):
        """Test word count calculation."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Hello world this is a test")])
        ])

        transform = CalculateWordCountTransform()
        result = transform.transform(doc)

        assert result.metadata['word_count'] == 6

    def test_calculates_char_count(self):
        """Test character count calculation."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Hello")])
        ])

        transform = CalculateWordCountTransform()
        result = transform.transform(doc)

        assert result.metadata['char_count'] == 5

    def test_counts_across_multiple_nodes(self):
        """Test counting across document."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[Text(content="Hello world")]),
        ])

        transform = CalculateWordCountTransform()
        result = transform.transform(doc)

        assert result.metadata['word_count'] == 3  # "Title Hello world"
        assert result.metadata['char_count'] > 0

    def test_custom_field_names(self):
        """Test custom field names."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test")])
        ])

        transform = CalculateWordCountTransform(
            word_field="words",
            char_field="characters"
        )
        result = transform.transform(doc)

        assert 'words' in result.metadata
        assert 'characters' in result.metadata

    def test_empty_document(self):
        """Test with empty document."""
        doc = Document(children=[])

        transform = CalculateWordCountTransform()
        result = transform.transform(doc)

        assert result.metadata['word_count'] == 0
        assert result.metadata['char_count'] == 0

    def test_char_count_includes_synthetic_spaces(self):
        """Test that char_count includes spaces inserted during text extraction.

        This test verifies the documented behavior where text from separate
        AST nodes is joined with spaces, creating synthetic spacing in the
        character count.
        """
        # Create document where we know the exact text content
        # Two Text nodes: "hello" (5 chars) + "world" (5 chars) = 10 chars of actual text
        # But extract_text will join with space: "hello world" = 11 chars
        doc = Document(children=[
            Paragraph(content=[
                Text(content="hello"),
                Text(content="world")
            ])
        ])

        transform = CalculateWordCountTransform()
        result = transform.transform(doc)

        # Word count should be 2
        assert result.metadata['word_count'] == 2

        # Character count includes the synthetic space inserted by extract_text
        # "hello" + " " + "world" = 11 characters
        assert result.metadata['char_count'] == 11

    def test_char_count_multiple_paragraphs(self):
        """Test char_count with multiple paragraphs (block-level synthetic spaces)."""
        # Two paragraphs with single-word text
        # "First" (5 chars) + "Second" (6 chars) = 11 chars actual
        # But joined: "First Second" = 12 chars with synthetic space
        doc = Document(children=[
            Paragraph(content=[Text(content="First")]),
            Paragraph(content=[Text(content="Second")])
        ])

        transform = CalculateWordCountTransform()
        result = transform.transform(doc)

        assert result.metadata['word_count'] == 2
        # Includes synthetic space between paragraphs
        assert result.metadata['char_count'] == 12


# AddAttachmentFootnotesTransform tests

class TestAddAttachmentFootnotesTransform:
    """Tests for AddAttachmentFootnotesTransform."""

    def test_adds_footnote_for_image_with_empty_url(self):
        """Test adding footnote definition for image with empty URL."""
        from all2md.ast.nodes import FootnoteDefinition

        doc = Document(children=[
            Paragraph(content=[
                Image(url="", alt_text="test_image.png")
            ])
        ])

        transform = AddAttachmentFootnotesTransform()
        result = transform.transform(doc)

        # Should have original paragraph plus heading plus footnote definition
        assert len(result.children) >= 3

        # Find footnote definition
        footnote_defs = [n for n in result.children if isinstance(n, FootnoteDefinition)]
        assert len(footnote_defs) == 1

        # Check footnote identifier matches label extraction
        assert footnote_defs[0].identifier == "test_image"

    def test_adds_footnote_for_link_with_empty_url(self):
        """Test adding footnote definition for link with empty URL."""
        from all2md.ast.nodes import FootnoteDefinition

        doc = Document(children=[
            Paragraph(content=[
                Link(url="", content=[Text(content="document.pdf")])
            ])
        ])

        transform = AddAttachmentFootnotesTransform()
        result = transform.transform(doc)

        # Find footnote definition
        footnote_defs = [n for n in result.children if isinstance(n, FootnoteDefinition)]
        assert len(footnote_defs) == 1
        assert footnote_defs[0].identifier == "document"

    def test_no_footnotes_for_images_with_urls(self):
        """Test that images with URLs are not processed."""
        from all2md.ast.nodes import FootnoteDefinition

        doc = Document(children=[
            Paragraph(content=[
                Image(url="http://example.com/image.png", alt_text="test")
            ])
        ])

        transform = AddAttachmentFootnotesTransform()
        result = transform.transform(doc)

        # Should not add footnote definitions
        footnote_defs = [n for n in result.children if isinstance(n, FootnoteDefinition)]
        assert len(footnote_defs) == 0

    def test_custom_section_title(self):
        """Test custom section title for footnotes."""
        from all2md.ast.nodes import Heading

        doc = Document(children=[
            Paragraph(content=[
                Image(url="", alt_text="test.png")
            ])
        ])

        transform = AddAttachmentFootnotesTransform(section_title="Image Sources")
        result = transform.transform(doc)

        # Find heading
        headings = [n for n in result.children if isinstance(n, Heading)]
        assert any(h.content[0].content == "Image Sources" for h in headings if isinstance(h.content[0], Text))

    def test_no_section_title(self):
        """Test omitting section title."""
        from all2md.ast.nodes import FootnoteDefinition, Heading

        doc = Document(children=[
            Paragraph(content=[
                Image(url="", alt_text="test.png")
            ])
        ])

        transform = AddAttachmentFootnotesTransform(section_title=None)
        result = transform.transform(doc)

        # Should have footnote but no "Attachments" heading
        footnote_defs = [n for n in result.children if isinstance(n, FootnoteDefinition)]
        assert len(footnote_defs) == 1

        # Count headings added by transform (original may have some)
        original_headings = [n for n in doc.children if isinstance(n, Heading)]
        result_headings = [n for n in result.children if isinstance(n, Heading)]
        assert len(result_headings) == len(original_headings)  # No new headings

    def test_multiple_attachments(self):
        """Test handling multiple attachment footnotes."""
        from all2md.ast.nodes import FootnoteDefinition

        doc = Document(children=[
            Paragraph(content=[
                Image(url="", alt_text="first.png"),
                Text(content=" and "),
                Image(url="", alt_text="second.jpg")
            ])
        ])

        transform = AddAttachmentFootnotesTransform()
        result = transform.transform(doc)

        # Should have 2 footnote definitions
        footnote_defs = [n for n in result.children if isinstance(n, FootnoteDefinition)]
        assert len(footnote_defs) == 2

        # Check identifiers
        identifiers = {fd.identifier for fd in footnote_defs}
        assert "first" in identifiers
        assert "second" in identifiers

    def test_disable_image_footnotes(self):
        """Test disabling image footnote processing."""
        from all2md.ast.nodes import FootnoteDefinition

        doc = Document(children=[
            Paragraph(content=[
                Image(url="", alt_text="test.png"),
                Link(url="", content=[Text(content="doc.pdf")])
            ])
        ])

        transform = AddAttachmentFootnotesTransform(add_definitions_for_images=False)
        result = transform.transform(doc)

        # Should only have footnote for link, not image
        footnote_defs = [n for n in result.children if isinstance(n, FootnoteDefinition)]
        assert len(footnote_defs) == 1
        assert footnote_defs[0].identifier == "doc"

    def test_empty_document_no_footnotes(self):
        """Test that empty document is unchanged."""
        doc = Document(children=[])

        transform = AddAttachmentFootnotesTransform()
        result = transform.transform(doc)

        assert len(result.children) == 0

    def test_label_sanitization(self):
        """Test that labels are properly sanitized."""
        from all2md.ast.nodes import FootnoteDefinition

        doc = Document(children=[
            Paragraph(content=[
                Image(url="", alt_text="my image (1).png"),
                Image(url="", alt_text="file with spaces.jpg")
            ])
        ])

        transform = AddAttachmentFootnotesTransform()
        result = transform.transform(doc)

        footnote_defs = [n for n in result.children if isinstance(n, FootnoteDefinition)]
        identifiers = {fd.identifier for fd in footnote_defs}

        # Labels should be sanitized
        assert "my_image_1" in identifiers
        assert "file_with_spaces" in identifiers

    def test_duplicate_labels_get_numeric_suffix(self):
        """Test that duplicate labels are handled with numeric suffixes."""
        from all2md.ast.nodes import FootnoteDefinition

        # Create document with three images that would generate the same base label
        doc = Document(children=[
            Paragraph(content=[
                Image(url="", alt_text="test.png"),
                Text(content=" "),
                Image(url="", alt_text="test.jpg"),  # Different extension, same base
                Text(content=" "),
                Image(url="", alt_text="test.gif")   # Different extension, same base
            ])
        ])

        transform = AddAttachmentFootnotesTransform()
        result = transform.transform(doc)

        # Should have 3 footnote definitions with unique identifiers
        footnote_defs = [n for n in result.children if isinstance(n, FootnoteDefinition)]
        assert len(footnote_defs) == 3

        identifiers = [fd.identifier for fd in footnote_defs]
        # First occurrence should not have suffix, subsequent ones should
        assert "test" in identifiers
        assert "test-2" in identifiers
        assert "test-3" in identifiers

    def test_transform_children_is_called(self):
        """Test that transform pipeline is properly maintained via _transform_children."""
        from all2md.ast.nodes import FootnoteDefinition

        # This test verifies that the transform properly calls _transform_children
        # so that if this transform is part of a pipeline, other transforms can work
        doc = Document(children=[
            Paragraph(content=[
                Image(url="", alt_text="test.png")
            ])
        ])

        # Apply the transform
        transform = AddAttachmentFootnotesTransform()
        result = transform.transform(doc)

        # The result should be a properly transformed Document
        # with children that went through _transform_children
        assert isinstance(result, Document)
        # Original paragraph should still be there
        assert any(isinstance(child, Paragraph) for child in result.children)
        # Footnote should be added
        footnote_defs = [n for n in result.children if isinstance(n, FootnoteDefinition)]
        assert len(footnote_defs) == 1


# GenerateTocTransform tests

class TestGenerateTocTransform:
    """Tests for GenerateTocTransform."""

    def test_generates_basic_toc(self):
        """Test basic TOC generation with simple headings."""
        from all2md.ast.nodes import List as ListNode

        doc = Document(children=[
            Heading(level=1, content=[Text(content="Introduction")]),
            Paragraph(content=[Text(content="Some text")]),
            Heading(level=1, content=[Text(content="Conclusion")]),
        ])

        transform = GenerateTocTransform()
        result = transform.transform(doc)

        # Should have TOC heading + TOC list + original content
        assert len(result.children) == 5

        # First should be TOC heading
        assert isinstance(result.children[0], Heading)
        assert result.children[0].content[0].content == "Table of Contents"

        # Second should be TOC list
        assert isinstance(result.children[1], ListNode)
        assert len(result.children[1].items) == 2

    def test_toc_with_nested_headings(self):
        """Test TOC with nested headings at different levels."""
        from all2md.ast.nodes import List as ListNode

        doc = Document(children=[
            Heading(level=1, content=[Text(content="Chapter 1")]),
            Heading(level=2, content=[Text(content="Section 1.1")]),
            Heading(level=2, content=[Text(content="Section 1.2")]),
            Heading(level=1, content=[Text(content="Chapter 2")]),
        ])

        transform = GenerateTocTransform()
        result = transform.transform(doc)

        # Check TOC list exists
        toc_list = result.children[1]
        assert isinstance(toc_list, ListNode)

        # Should have 2 top-level items (Chapter 1, Chapter 2)
        assert len(toc_list.items) == 2

        # First item should have nested list with 2 sub-items
        first_item = toc_list.items[0]
        # Look for nested list in children
        nested_lists = [child for child in first_item.children if isinstance(child, ListNode)]
        assert len(nested_lists) == 1
        assert len(nested_lists[0].items) == 2

    def test_toc_depth_limiting(self):
        """Test that max_depth limits TOC depth."""
        from all2md.ast.nodes import List as ListNode

        doc = Document(children=[
            Heading(level=1, content=[Text(content="H1")]),
            Heading(level=2, content=[Text(content="H2")]),
            Heading(level=3, content=[Text(content="H3")]),
            Heading(level=4, content=[Text(content="H4")]),
        ])

        # Only include levels 1-2
        transform = GenerateTocTransform(max_depth=2)
        result = transform.transform(doc)

        # Get TOC list
        toc_list = result.children[1]
        assert isinstance(toc_list, ListNode)

        # Should only have H1
        assert len(toc_list.items) == 1

        # H1 should have nested H2
        nested_lists = [child for child in toc_list.items[0].children if isinstance(child, ListNode)]
        assert len(nested_lists) == 1
        assert len(nested_lists[0].items) == 1

    def test_toc_position_top(self):
        """Test TOC at top of document."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[Text(content="Content")]),
        ])

        transform = GenerateTocTransform(position="top")
        result = transform.transform(doc)

        # TOC heading should be first
        assert isinstance(result.children[0], Heading)
        assert result.children[0].content[0].content == "Table of Contents"

        # Original heading should come after TOC
        assert result.children[2].content[0].content == "Title"

    def test_toc_position_bottom(self):
        """Test TOC at bottom of document."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[Text(content="Content")]),
        ])

        transform = GenerateTocTransform(position="bottom")
        result = transform.transform(doc)

        # Original content should come first
        assert isinstance(result.children[0], Heading)
        assert result.children[0].content[0].content == "Title"

        # TOC heading should be at end
        assert isinstance(result.children[-2], Heading)
        assert result.children[-2].content[0].content == "Table of Contents"

    def test_empty_document_no_toc(self):
        """Test that empty document is unchanged."""
        doc = Document(children=[])

        transform = GenerateTocTransform()
        result = transform.transform(doc)

        assert len(result.children) == 0

    def test_document_without_headings_no_toc(self):
        """Test that document without headings gets no TOC."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Just text")]),
            Paragraph(content=[Text(content="More text")]),
        ])

        transform = GenerateTocTransform()
        result = transform.transform(doc)

        # Should be unchanged (no TOC added)
        assert len(result.children) == 2
        assert all(isinstance(child, Paragraph) for child in result.children)

    def test_custom_toc_title(self):
        """Test custom TOC title."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Section")]),
        ])

        transform = GenerateTocTransform(title="Contents")
        result = transform.transform(doc)

        # Check custom title
        assert result.children[0].content[0].content == "Contents"

    def test_toc_with_links(self):
        """Test TOC includes links to headings with IDs."""
        doc = Document(children=[
            Heading(
                level=1,
                content=[Text(content="Introduction")],
                metadata={"id": "intro"}
            ),
        ])

        transform = GenerateTocTransform(add_links=True)
        result = transform.transform(doc)

        # Get TOC list item
        toc_list = result.children[1]
        first_item = toc_list.items[0]

        # Should have a paragraph with a link
        para = first_item.children[0]
        assert isinstance(para, Paragraph)
        link = para.content[0]
        assert isinstance(link, Link)
        assert link.url == "#intro"
        assert link.content[0].content == "Introduction"

    def test_toc_without_links(self):
        """Test TOC without links when add_links=False."""
        doc = Document(children=[
            Heading(
                level=1,
                content=[Text(content="Introduction")],
                metadata={"id": "intro"}
            ),
        ])

        transform = GenerateTocTransform(add_links=False)
        result = transform.transform(doc)

        # Get TOC list item
        toc_list = result.children[1]
        first_item = toc_list.items[0]

        # Should have a paragraph with plain text (no link)
        para = first_item.children[0]
        assert isinstance(para, Paragraph)
        text = para.content[0]
        assert isinstance(text, Text)
        assert text.content == "Introduction"

    def test_toc_generates_ids_when_missing(self):
        """Test that TOC generates IDs for headings that don't have them."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="My Title")]),
        ])

        transform = GenerateTocTransform(add_links=True)
        result = transform.transform(doc)

        # Get TOC list item
        toc_list = result.children[1]
        first_item = toc_list.items[0]

        # Should have generated an ID (with dash separator for multi-word)
        para = first_item.children[0]
        link = para.content[0]
        assert isinstance(link, Link)
        assert link.url == "#my-title"

    def test_toc_handles_duplicate_heading_text(self):
        """Test that duplicate heading text gets unique IDs."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Section")]),
            Heading(level=1, content=[Text(content="Section")]),
            Heading(level=1, content=[Text(content="Section")]),
        ])

        transform = GenerateTocTransform(add_links=True)
        result = transform.transform(doc)

        # Get TOC list items
        toc_list = result.children[1]

        # Check all three items have different link URLs
        urls = []
        for item in toc_list.items:
            para = item.children[0]
            link = para.content[0]
            urls.append(link.url)

        assert urls[0] == "#section"
        assert urls[1] == "#section-2"
        assert urls[2] == "#section-3"

    def test_custom_separator(self):
        """Test custom separator for ID generation."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="My Title")]),
        ])

        transform = GenerateTocTransform(add_links=True, separator="_")
        result = transform.transform(doc)

        # Get TOC link
        toc_list = result.children[1]
        first_item = toc_list.items[0]
        para = first_item.children[0]
        link = para.content[0]

        # Should use underscore separator
        assert link.url == "#my_title"

    def test_invalid_max_depth_raises_error(self):
        """Test that invalid max_depth raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            GenerateTocTransform(max_depth=0)
        assert "max_depth must be 1-6" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            GenerateTocTransform(max_depth=7)
        assert "max_depth must be 1-6" in str(exc_info.value)

    def test_invalid_position_raises_error(self):
        """Test that invalid position raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            GenerateTocTransform(position="middle")
        assert "position must be 'top' or 'bottom'" in str(exc_info.value)

    def test_toc_with_complex_nested_structure(self):
        """Test TOC with complex multi-level nesting."""
        from all2md.ast.nodes import List as ListNode

        doc = Document(children=[
            Heading(level=1, content=[Text(content="Chapter 1")]),
            Heading(level=2, content=[Text(content="Section 1.1")]),
            Heading(level=3, content=[Text(content="Subsection 1.1.1")]),
            Heading(level=3, content=[Text(content="Subsection 1.1.2")]),
            Heading(level=2, content=[Text(content="Section 1.2")]),
            Heading(level=1, content=[Text(content="Chapter 2")]),
        ])

        transform = GenerateTocTransform(max_depth=3)
        result = transform.transform(doc)

        # Get TOC list
        toc_list = result.children[1]

        # Should have 2 top-level items
        assert len(toc_list.items) == 2

        # First chapter should have nested structure
        chapter1_item = toc_list.items[0]
        chapter1_nested = [child for child in chapter1_item.children if isinstance(child, ListNode)]
        assert len(chapter1_nested) == 1

        # Should have 2 sections
        assert len(chapter1_nested[0].items) == 2

        # First section should have 2 subsections
        section1_item = chapter1_nested[0].items[0]
        section1_nested = [child for child in section1_item.children if isinstance(child, ListNode)]
        assert len(section1_nested) == 1
        assert len(section1_nested[0].items) == 2

    def test_headings_with_special_characters(self):
        """Test TOC with headings containing special characters."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title! With @#$ Special")]),
        ])

        transform = GenerateTocTransform(add_links=True)
        result = transform.transform(doc)

        # Get TOC link
        toc_list = result.children[1]
        first_item = toc_list.items[0]
        para = first_item.children[0]
        link = para.content[0]

        # Special characters should be removed from ID, words separated by dashes
        assert link.url == "#title-with-special"
        # But link text should be unchanged
        assert link.content[0].content == "Title! With @#$ Special"

    def test_empty_toc_title(self):
        """Test TOC with empty title (no title heading)."""
        from all2md.ast.nodes import List as ListNode

        doc = Document(children=[
            Heading(level=1, content=[Text(content="Section")]),
        ])

        transform = GenerateTocTransform(title="")
        result = transform.transform(doc)

        # First element should be the TOC list (no heading)
        assert isinstance(result.children[0], ListNode)

        # Original heading should come after TOC
        assert result.children[1].content[0].content == "Section"
