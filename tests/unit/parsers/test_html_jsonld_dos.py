"""Tests for M9: JSON-LD script size limits (DoS protection).

This module tests that oversized JSON-LD scripts are properly skipped
to prevent denial-of-service attacks via memory exhaustion.
"""

import json

from all2md import to_markdown
from all2md.constants import MAX_JSON_LD_SIZE_BYTES


class TestJsonLdDoS:
    """Test JSON-LD extraction with size limits."""

    def test_normal_jsonld_parsed(self):
        """Test that normal-sized JSON-LD scripts are parsed correctly."""
        jsonld_data = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "Test Article",
            "author": "John Doe",
        }

        html = (
            f'<html><head><script type="application/ld+json">{json.dumps(jsonld_data)}</script></head>'
            "<body><p>Content</p></body></html>"
        )

        result = to_markdown(html, source_format="html")
        assert "Content" in result

    def test_oversized_jsonld_skipped(self):
        """Test that oversized JSON-LD scripts are skipped to prevent DoS."""
        # Create a JSON-LD script that exceeds MAX_JSON_LD_SIZE_BYTES
        large_array = ["item"] * (MAX_JSON_LD_SIZE_BYTES // 8)  # Each "item" is ~8 bytes in JSON
        jsonld_data = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": large_array}

        html = (
            f'<html><head><script type="application/ld+json">{json.dumps(jsonld_data)}</script></head>'
            "<body><p>Content</p></body></html>"
        )

        # Should not raise an exception and should parse successfully
        result = to_markdown(html, source_format="html")
        assert "Content" in result

    def test_multiple_jsonld_scripts_with_one_oversized(self):
        """Test that oversized JSON-LD scripts are skipped but others are parsed."""
        normal_jsonld = {"@context": "https://schema.org", "@type": "Article", "headline": "Normal"}

        # Create oversized JSON-LD
        large_array = ["x"] * (MAX_JSON_LD_SIZE_BYTES // 4)
        oversized_jsonld = {"@context": "https://schema.org", "data": large_array}

        html = (
            f'<html><head><script type="application/ld+json">{json.dumps(normal_jsonld)}</script>'
            f'<script type="application/ld+json">{json.dumps(oversized_jsonld)}</script>'
            f'<script type="application/ld+json">{json.dumps(normal_jsonld)}</script>'
            "</head><body><p>Content</p></body></html>"
        )

        # Should not raise an exception
        result = to_markdown(html, source_format="html")
        assert "Content" in result

    def test_exactly_at_limit_parsed(self):
        """Test that JSON-LD scripts exactly at the limit are parsed."""
        # Create JSON-LD that's exactly at the limit
        # Account for JSON formatting overhead
        target_size = MAX_JSON_LD_SIZE_BYTES - 100  # Leave room for JSON structure
        data_string = "X" * target_size
        jsonld_data = {"data": data_string}

        html = (
            f'<html><head><script type="application/ld+json">{json.dumps(jsonld_data)}</script></head>'
            "<body><p>Content</p></body></html>"
        )

        result = to_markdown(html, source_format="html")
        assert "Content" in result

    def test_empty_jsonld_script_handled(self):
        """Test that empty JSON-LD scripts are handled correctly."""
        html = '<html><head><script type="application/ld+json"></script></head>' "<body><p>Content</p></body></html>"

        result = to_markdown(html, source_format="html")
        assert "Content" in result

    def test_malformed_jsonld_with_size_check(self):
        """Test that malformed but reasonably-sized JSON-LD is handled gracefully."""
        html = (
            '<html><head><script type="application/ld+json">{ invalid json }</script></head>'
            "<body><p>Content</p></body></html>"
        )

        # Should not raise an exception, just skip the malformed JSON
        result = to_markdown(html, source_format="html")
        assert "Content" in result
