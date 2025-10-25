"""Tests for frontmatter format selection (YAML, TOML, JSON)."""

from all2md.ast.nodes import Document, Paragraph, Text
from all2md.options import MarkdownRendererOptions
from all2md.renderers.markdown import MarkdownRenderer
from all2md.utils.metadata import (
    DocumentMetadata,
    MetadataRenderPolicy,
    format_json_frontmatter,
    format_toml_frontmatter,
    format_yaml_frontmatter,
)


def test_format_yaml_frontmatter():
    """Test YAML frontmatter formatting."""
    metadata = DocumentMetadata(
        title="Test Document",
        author="John Doe",
        keywords=["python", "testing"],
        page_count=5,
        word_count=1000,
    )

    result = format_yaml_frontmatter(metadata)

    assert result.startswith("---\n")
    assert result.endswith("---\n\n")
    assert "title: Test Document" in result
    assert "author: John Doe" in result
    assert "keywords:" in result
    assert "python" in result
    assert "testing" in result
    assert "page_count: 5" in result
    assert "word_count: 1000" in result


def test_format_toml_frontmatter():
    """Test TOML frontmatter formatting."""
    metadata = DocumentMetadata(
        title="Test Document",
        author="Jane Smith",
        keywords=["rust", "toml"],
        page_count=3,
    )

    result = format_toml_frontmatter(metadata)

    assert result.startswith("+++\n")
    assert result.endswith("+++\n\n")
    assert 'title = "Test Document"' in result
    assert 'author = "Jane Smith"' in result
    assert 'keywords = ["rust", "toml"]' in result
    assert "page_count = 3" in result


def test_format_json_frontmatter():
    """Test JSON frontmatter formatting."""
    metadata = DocumentMetadata(
        title="JSON Test",
        author="Bob Johnson",
        word_count=500,
    )

    result = format_json_frontmatter(metadata)

    assert result.startswith("```json\n")
    assert result.endswith("```\n\n")
    assert '"title": "JSON Test"' in result
    assert '"author": "Bob Johnson"' in result
    assert '"word_count": 500' in result


def test_markdown_renderer_yaml_frontmatter():
    """Test MarkdownRenderer with YAML frontmatter."""
    doc = Document(
        children=[Paragraph(content=[Text(content="Hello world")])],
        metadata={
            "title": "Test",
            "author": "Alice",
        },
    )

    options = MarkdownRendererOptions(metadata_frontmatter=True, metadata_format="yaml")
    renderer = MarkdownRenderer(options)
    result = renderer.render_to_string(doc)

    assert result.startswith("---\n")
    assert "title: Test" in result
    assert "author: Alice" in result
    assert "Hello world" in result


def test_markdown_renderer_toml_frontmatter():
    """Test MarkdownRenderer with TOML frontmatter."""
    doc = Document(
        children=[Paragraph(content=[Text(content="Hello world")])],
        metadata={
            "title": "Test",
            "author": "Alice",
        },
    )

    options = MarkdownRendererOptions(metadata_frontmatter=True, metadata_format="toml")
    renderer = MarkdownRenderer(options)
    result = renderer.render_to_string(doc)

    assert result.startswith("+++\n")
    assert 'title = "Test"' in result
    assert 'author = "Alice"' in result
    assert "Hello world" in result


def test_markdown_renderer_json_frontmatter():
    """Test MarkdownRenderer with JSON frontmatter."""
    doc = Document(
        children=[Paragraph(content=[Text(content="Hello world")])],
        metadata={
            "title": "Test",
            "page_count": 1,
        },
    )

    options = MarkdownRendererOptions(metadata_frontmatter=True, metadata_format="json")
    renderer = MarkdownRenderer(options)
    result = renderer.render_to_string(doc)

    assert result.startswith("```json\n")
    assert '"title": "Test"' in result
    assert '"page_count": 1' in result
    assert "Hello world" in result


def test_extended_metadata_fields():
    """Test that extended metadata fields are included with default policy."""
    metadata = DocumentMetadata(
        title="Extended Test",
        url="https://example.com",
        source_path="/path/to/file.pdf",
        page_count=10,
        word_count=2000,
        sha256="abc123",
        extraction_date="2025-01-01 12:00:00",
    )

    result = format_yaml_frontmatter(metadata)

    assert 'source: "https://example.com"' in result
    assert "page_count: 10" in result
    assert "word_count: 2000" in result
    assert 'accessed_date: "2025-01-01 12:00:00"' in result
    assert "source_path" not in result
    assert "sha256" not in result


def test_metadata_policy_all_visibility():
    """Test that all metadata fields can be rendered via policy changes."""
    metadata = DocumentMetadata(
        title="Extended Test",
        url="https://example.com",
        source_path="/path/to/file.pdf",
        page_count=10,
        word_count=2000,
        sha256="abc123",
        extraction_date="2025-01-01 12:00:00",
    )

    policy = MetadataRenderPolicy(visibility="all")
    result = format_yaml_frontmatter(metadata, policy=policy)

    assert 'source: "https://example.com"' in result
    assert "source_path: /path/to/file.pdf" in result
    assert "sha256: abc123" in result
    assert 'extraction_date: "2025-01-01 12:00:00"' in result


def test_empty_metadata():
    """Test that empty metadata produces empty frontmatter."""
    metadata = DocumentMetadata()

    yaml_result = format_yaml_frontmatter(metadata)
    toml_result = format_toml_frontmatter(metadata)
    json_result = format_json_frontmatter(metadata)

    assert yaml_result == ""
    assert toml_result == ""
    assert json_result == ""
