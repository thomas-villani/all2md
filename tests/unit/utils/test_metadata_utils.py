"""Unit tests for metadata utilities."""

import pytest
import tomllib
import yaml

from all2md.utils.metadata import (
    DocumentMetadata,
    MetadataRenderPolicy,
    format_yaml_frontmatter,
    prepare_metadata_for_render,
    prepend_metadata_if_enabled,
)


def _extract_yaml_frontmatter_block(frontmatter: str) -> str:
    assert frontmatter.startswith("---\n")
    assert frontmatter.endswith("---\n\n")
    return frontmatter[4:-5]


def _parse_yaml_frontmatter(frontmatter: str) -> dict:
    return yaml.safe_load(_extract_yaml_frontmatter_block(frontmatter)) or {}


def _extract_toml_frontmatter_block(frontmatter: str) -> str:
    assert frontmatter.startswith("+++\n")
    assert frontmatter.endswith("+++\n\n")
    return frontmatter[4:-5]


def _parse_toml_frontmatter(frontmatter: str) -> dict:
    return tomllib.loads(_extract_toml_frontmatter_block(frontmatter))


def _split_yaml_frontmatter_and_body(text: str) -> tuple[dict, str]:
    marker = "\n---\n\n"
    boundary = text.find(marker)
    assert boundary != -1
    frontmatter = text[: boundary + len(marker)]
    body = text[boundary + len(marker) :]
    return _parse_yaml_frontmatter(frontmatter), body


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
            language="en",
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
        metadata.custom["document_type"] = "pdf"
        metadata.custom["page_count"] = 10
        metadata.custom["word_count"] = 500

        assert metadata.custom["document_type"] == "pdf"
        assert metadata.custom["page_count"] == 10
        assert metadata.custom["word_count"] == 500


@pytest.mark.unit
class TestFormatYamlFrontmatter:
    """Test YAML front matter formatting."""

    def test_format_yaml_frontmatter_basic(self):
        """Test basic YAML formatting."""
        metadata = DocumentMetadata(title="Test Document", author="Test Author")

        result = format_yaml_frontmatter(metadata)

        assert result.startswith("---\n")
        assert result.endswith("---\n\n")
        data = _parse_yaml_frontmatter(result)
        assert data["title"] == "Test Document"
        assert data["author"] == "Test Author"

    def test_format_yaml_frontmatter_with_keywords(self):
        """Test YAML formatting with keyword list."""
        metadata = DocumentMetadata(title="Test Document", keywords=["python", "testing", "metadata"])

        result = format_yaml_frontmatter(metadata)

        data = _parse_yaml_frontmatter(result)
        assert data["title"] == "Test Document"
        assert data["keywords"] == ["python", "testing", "metadata"]

    def test_format_yaml_frontmatter_with_quotes_needed(self):
        """Test YAML formatting with values that need quotes."""
        metadata = DocumentMetadata(
            title="Document: With Colon", author="Author, With Comma", creation_date="2025-01-01"
        )

        result = format_yaml_frontmatter(metadata)

        data = _parse_yaml_frontmatter(result)
        assert data["title"] == "Document: With Colon"
        assert data["author"] == "Author, With Comma"
        assert data["creation_date"] == "2025-01-01"

    def test_format_yaml_frontmatter_with_custom_fields(self):
        """Test YAML formatting with custom fields."""
        metadata = DocumentMetadata(title="Test")
        metadata.custom["page_count"] = 5
        metadata.custom["document_type"] = "html"
        metadata.custom["tags"] = ["web", "document"]

        result = format_yaml_frontmatter(metadata)

        data = _parse_yaml_frontmatter(result)
        assert data["title"] == "Test"
        assert data["page_count"] == 5
        assert data["document_type"] == "html"
        assert data["tags"] == ["web", "document"]

    def test_format_yaml_frontmatter_empty_metadata(self):
        """Test YAML formatting with empty metadata."""
        metadata = DocumentMetadata()

        result = format_yaml_frontmatter(metadata)

        # Should return empty string for empty metadata
        assert result == ""

    def test_format_yaml_frontmatter_with_dict_input(self):
        """Test YAML formatting with dictionary input."""
        metadata_dict = {"title": "Dict Test", "author": "Dict Author", "keywords": ["dict", "test"]}

        result = format_yaml_frontmatter(metadata_dict)

        data = _parse_yaml_frontmatter(result)
        assert data["title"] == "Dict Test"
        assert data["author"] == "Dict Author"
        assert data["keywords"] == ["dict", "test"]

    def test_format_yaml_frontmatter_multiline_handling(self):
        """Test YAML formatting with multiline values."""
        metadata = DocumentMetadata(
            title="Test Title",
            subject="This is a very long description that might contain\nmultiple lines and should be handled properly",
        )

        result = format_yaml_frontmatter(metadata)

        data = _parse_yaml_frontmatter(result)
        assert data["title"] == "Test Title"
        assert data["description"] == (
            "This is a very long description that might contain\nmultiple lines and should be handled properly"
        )


@pytest.mark.unit
class TestPrependMetadataIfEnabled:
    """Test metadata prepending functionality."""

    def test_prepend_metadata_enabled_with_metadata(self):
        """Test prepending metadata when enabled with valid metadata."""
        content = "# Test Document\n\nThis is content."
        metadata = DocumentMetadata(title="Test", author="Author")

        result = prepend_metadata_if_enabled(content, metadata, True)

        data, body = _split_yaml_frontmatter_and_body(result)

        assert data["title"] == "Test"
        assert data["author"] == "Author"
        assert body.startswith("# Test Document")
        assert "This is content." in body

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

        data, body = _split_yaml_frontmatter_and_body(result)

        assert data["title"] == "Metadata Title"
        assert body.startswith("# Title")


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

        data, _ = _split_yaml_frontmatter_and_body(result)
        assert "sha256" not in data
        assert data["title"] == "Title"
