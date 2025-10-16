"""Unit tests for metadata utilities."""

import pytest

from all2md.utils.metadata import (
    DocumentMetadata,
    MetadataRenderPolicy,
    format_yaml_frontmatter,
    prepare_metadata_for_render,
    prepend_metadata_if_enabled,
)


@pytest.mark.unit
class TestDocumentMetadata:
    """Test DocumentMetadata dataclass."""

    def test_document_metadata_creation(self):
        """Test creating DocumentMetadata with default values."""
        metadata = DocumentMetadata()

        assert metadata.title is None
        assert metadata.author is None
        assert metadata.subject is None
        assert metadata.keywords is None
        assert metadata.creation_date is None
        assert metadata.modification_date is None
        assert metadata.creator is None
        assert metadata.producer is None
        assert metadata.category is None
        assert metadata.language is None
        assert isinstance(metadata.custom, dict)
        assert len(metadata.custom) == 0

    def test_document_metadata_with_values(self):
        """Test creating DocumentMetadata with values."""
        metadata = DocumentMetadata(
            title="Test Title",
            author="Test Author",
            subject="Test Subject",
            keywords=["test", "metadata"],
            creation_date="2025-09-26",
            creator="Test Creator",
            language="en"
        )

        assert metadata.title == "Test Title"
        assert metadata.author == "Test Author"
        assert metadata.subject == "Test Subject"
        assert metadata.keywords == ["test", "metadata"]
        assert metadata.creation_date == "2025-09-26"
        assert metadata.creator == "Test Creator"
        assert metadata.language == "en"

    def test_document_metadata_custom_fields(self):
        """Test using custom fields in metadata."""
        metadata = DocumentMetadata()
        metadata.custom['document_type'] = 'pdf'
        metadata.custom['page_count'] = 10
        metadata.custom['word_count'] = 500

        assert metadata.custom['document_type'] == 'pdf'
        assert metadata.custom['page_count'] == 10
        assert metadata.custom['word_count'] == 500


@pytest.mark.unit
class TestFormatYamlFrontmatter:
    """Test YAML front matter formatting."""

    def test_format_yaml_frontmatter_basic(self):
        """Test basic YAML formatting."""
        metadata = DocumentMetadata(
            title="Test Document",
            author="Test Author"
        )

        result = format_yaml_frontmatter(metadata)

        assert result.startswith("---\n")
        assert result.endswith("---\n\n")
        assert "title: Test Document" in result
        assert "author: Test Author" in result

    def test_format_yaml_frontmatter_with_keywords(self):
        """Test YAML formatting with keyword list."""
        metadata = DocumentMetadata(
            title="Test Document",
            keywords=["python", "testing", "metadata"]
        )

        result = format_yaml_frontmatter(metadata)

        assert "title: Test Document" in result
        assert "keywords: [python, testing, metadata]" in result

    def test_format_yaml_frontmatter_with_quotes_needed(self):
        """Test YAML formatting with values that need quotes."""
        metadata = DocumentMetadata(
            title="Document: With Colon",
            author="Author, With Comma",
            creation_date="2025-01-01"
        )

        result = format_yaml_frontmatter(metadata)

        assert 'title: "Document: With Colon"' in result
        assert 'author: Author, With Comma' in result  # Commas don't require quotes in our implementation
        assert "creation_date: 2025-01-01" in result

    def test_format_yaml_frontmatter_with_custom_fields(self):
        """Test YAML formatting with custom fields."""
        metadata = DocumentMetadata(title="Test")
        metadata.custom['page_count'] = 5
        metadata.custom['document_type'] = 'html'
        metadata.custom['tags'] = ['web', 'document']

        result = format_yaml_frontmatter(metadata)

        assert "title: Test" in result
        assert "page_count: 5" in result
        assert "document_type: html" in result
        assert "tags: [web, document]" in result

    def test_format_yaml_frontmatter_empty_metadata(self):
        """Test YAML formatting with empty metadata."""
        metadata = DocumentMetadata()

        result = format_yaml_frontmatter(metadata)

        # Should return empty string for empty metadata
        assert result == ""

    def test_format_yaml_frontmatter_with_dict_input(self):
        """Test YAML formatting with dictionary input."""
        metadata_dict = {
            'title': 'Dict Test',
            'author': 'Dict Author',
            'keywords': ['dict', 'test']
        }

        result = format_yaml_frontmatter(metadata_dict)

        assert "title: Dict Test" in result
        assert "author: Dict Author" in result
        assert "keywords: [dict, test]" in result

    def test_format_yaml_frontmatter_multiline_handling(self):
        """Test YAML formatting with multiline values."""
        metadata = DocumentMetadata(
            title="Test Title",
            subject="This is a very long description that might contain\nmultiple lines and should be handled properly"
        )

        result = format_yaml_frontmatter(metadata)

        # Multiline strings should use literal block scalar format
        assert "title: Test Title" in result
        assert 'description: |' in result  # subject maps to description
        assert '  This is a very long description' in result


@pytest.mark.unit
class TestPrependMetadataIfEnabled:
    """Test metadata prepending functionality."""

    def test_prepend_metadata_enabled_with_metadata(self):
        """Test prepending metadata when enabled with valid metadata."""
        content = "# Test Document\n\nThis is content."
        metadata = DocumentMetadata(title="Test", author="Author")

        result = prepend_metadata_if_enabled(content, metadata, True)

        assert result.startswith("---\n")
        assert "title: Test" in result
        assert "author: Author" in result
        assert "# Test Document" in result
        assert "This is content." in result

    def test_prepend_metadata_enabled_no_metadata(self):
        """Test prepending when enabled but no metadata provided."""
        content = "# Test Document\n\nThis is content."

        result = prepend_metadata_if_enabled(content, None, True)

        # Should return original content when no metadata
        assert result == content
        assert not result.startswith("---")

    def test_prepend_metadata_disabled(self):
        """Test that metadata is not prepended when disabled."""
        content = "# Test Document\n\nThis is content."
        metadata = DocumentMetadata(title="Test", author="Author")

        result = prepend_metadata_if_enabled(content, metadata, False)

        # Should return original content when disabled
        assert result == content
        assert not result.startswith("---")
        assert "title:" not in result

    def test_prepend_metadata_enabled_empty_metadata(self):
        """Test prepending with empty metadata object."""
        content = "# Test Document\n\nThis is content."
        metadata = DocumentMetadata()  # Empty metadata

        result = prepend_metadata_if_enabled(content, metadata, True)

        # Should return original content when metadata is empty
        assert result == content
        assert not result.startswith("---")

    def test_prepend_metadata_proper_separation(self):
        """Test that metadata and content are properly separated."""
        content = "# Title\n\nContent here."
        metadata = DocumentMetadata(title="Metadata Title")

        result = prepend_metadata_if_enabled(content, metadata, True)

        lines = result.split('\n')

        # Find the end of front matter
        end_frontmatter_idx = None
        start_frontmatter_idx = None
        for i, line in enumerate(lines):
            if line == '---':
                if start_frontmatter_idx is None:
                    start_frontmatter_idx = i
                else:
                    end_frontmatter_idx = i
                    break

        assert start_frontmatter_idx is not None
        assert end_frontmatter_idx is not None

        # Should have proper separation
        assert lines[end_frontmatter_idx + 1] == ''  # Empty line after front matter
        assert lines[end_frontmatter_idx + 2] == '# Title'  # Content starts after empty line


@pytest.mark.unit
class TestMetadataRenderPolicy:
    """Tests for metadata policy normalization and filtering."""

    def test_prepare_metadata_aliases(self):
        """Ensure URL and extraction_date aliases are normalized."""
        metadata = DocumentMetadata(
            title="Alias Test",
            url="https://example.com",
            extraction_date="2025-02-01",
        )

        result = prepare_metadata_for_render(metadata)

        assert result["source"] == "https://example.com"
        assert result["accessed_date"] == "2025-02-01"
        assert "extraction_date" not in result

    def test_prepare_metadata_visibility_all(self):
        """Ensure internal fields are available when requested."""
        metadata = DocumentMetadata(sha256="abc123", extraction_date="2025-02-01")
        policy = MetadataRenderPolicy(visibility="all")

        result = prepare_metadata_for_render(metadata, policy)

        assert result["sha256"] == "abc123"
        assert result["extraction_date"] == "2025-02-01"

    def test_prepend_metadata_with_policy(self):
        """Verify prepend respects custom policy exclusions."""
        content = "# Heading\n\nBody"
        metadata = DocumentMetadata(title="Title", sha256="ignored")
        policy = MetadataRenderPolicy(visibility="core")

        result = prepend_metadata_if_enabled(content, metadata, True, policy=policy)

        assert "sha256" not in result
        assert "title: Title" in result
