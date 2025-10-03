#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for built-in transforms."""

import pytest

from all2md.ast import Document, Heading, Image, Link, Paragraph, Text
from all2md.transforms.builtin import (
    AddAttachmentFootnotesTransform,
    AddConversionTimestampTransform,
    AddHeadingIdsTransform,
    CalculateWordCountTransform,
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

        transform = AddConversionTimestampTransform(format="unix")
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

        transform = AddConversionTimestampTransform(format="%Y-%m-%d")
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
        from all2md.ast.nodes import Heading, FootnoteDefinition

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
