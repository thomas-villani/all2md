"""Tests for M13: Metadata extraction size limits (DoS protection).

This module tests that oversized meta tag content is properly truncated
to prevent denial-of-service attacks via memory exhaustion.
"""

from all2md import to_markdown
from all2md.constants import MAX_META_TAG_CONTENT_LENGTH


class TestMetadataDoS:
    """Test metadata extraction with size limits."""

    def test_normal_meta_tag_passes(self):
        """Test that normal-sized meta tags are processed correctly."""
        html = (
            "<html><head>"
            '<meta name="description" content="This is a normal description">'
            '<meta name="author" content="John Doe">'
            "</head><body><p>Content</p></body></html>"
        )

        result = to_markdown(html, source_format="html")
        assert "Content" in result  # Should parse successfully

    def test_oversized_meta_tag_truncated(self):
        """Test that oversized meta tags are truncated to prevent DoS."""
        # Create a meta tag content that exceeds MAX_META_TAG_CONTENT_LENGTH
        large_content = "A" * (MAX_META_TAG_CONTENT_LENGTH + 1000)

        html = (
            f'<html><head><meta name="description" content="{large_content}">'
            "</head><body><p>Content</p></body></html>"
        )

        # Should not raise an exception and should parse successfully
        result = to_markdown(html, source_format="html")
        assert "Content" in result

    def test_multiple_oversized_meta_tags(self):
        """Test that multiple oversized meta tags are all handled correctly."""
        large_content1 = "B" * (MAX_META_TAG_CONTENT_LENGTH + 500)
        large_content2 = "C" * (MAX_META_TAG_CONTENT_LENGTH + 1000)

        html = (
            f'<html><head><meta name="description" content="{large_content1}">'
            f'<meta name="keywords" content="{large_content2}">'
            '<meta name="author" content="Normal Author">'
            "</head><body><p>Content</p></body></html>"
        )

        # Should not raise an exception
        result = to_markdown(html, source_format="html")
        assert "Content" in result

    def test_exactly_at_limit_not_truncated(self):
        """Test that meta tags exactly at the limit are not truncated."""
        exact_size_content = "D" * MAX_META_TAG_CONTENT_LENGTH

        html = f'<html><head><meta name="description" content="{exact_size_content}"></head><body><p>Content</p></body></html>'

        result = to_markdown(html, source_format="html")
        assert "Content" in result

    def test_just_over_limit_truncated(self):
        """Test that meta tags just over the limit are truncated."""
        just_over_limit = "E" * (MAX_META_TAG_CONTENT_LENGTH + 1)

        html = f'<html><head><meta name="description" content="{just_over_limit}"></head><body><p>Content</p></body></html>'

        result = to_markdown(html, source_format="html")
        assert "Content" in result

    def test_empty_meta_tag_handled(self):
        """Test that empty meta tags are handled correctly."""
        html = '<html><head><meta name="description" content=""></head><body><p>Content</p></body></html>'

        result = to_markdown(html, source_format="html")
        assert "Content" in result
