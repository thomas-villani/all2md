#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for nested renderer options handling in API."""

import pytest

from all2md.api import (
    _create_renderer_options_from_kwargs,
    _split_kwargs_for_parser_and_renderer,
)
from all2md.options.epub import EpubRendererOptions


class TestNestedRendererOptions:
    """Test nested dataclass field handling for renderer options."""

    def test_split_kwargs_includes_nested_renderer_fields(self):
        """Test that _split_kwargs_for_parser_and_renderer includes nested renderer fields."""
        # EpubRendererOptions has a nested 'network' field with NetworkFetchOptions
        # NetworkFetchOptions has fields like 'allow_remote_fetch', 'allowed_hosts', etc.
        kwargs = {
            "allow_remote_fetch": True,  # nested field in network
            "allowed_hosts": ["example.com"],  # nested field in network
            "title": "My Book",  # top-level field in EpubRendererOptions
            "pages": [1, 2, 3],  # parser option (not renderer)
        }

        parser_kwargs, renderer_kwargs = _split_kwargs_for_parser_and_renderer("pdf", "epub", kwargs)

        # Parser should get 'pages'
        assert "pages" in parser_kwargs
        assert parser_kwargs["pages"] == [1, 2, 3]

        # Renderer should get nested network fields AND top-level fields
        assert "allow_remote_fetch" in renderer_kwargs
        assert renderer_kwargs["allow_remote_fetch"] is True
        assert "allowed_hosts" in renderer_kwargs
        assert renderer_kwargs["allowed_hosts"] == ["example.com"]
        assert "title" in renderer_kwargs
        assert renderer_kwargs["title"] == "My Book"

    def test_create_renderer_options_handles_nested_dataclasses(self):
        """Test that _create_renderer_options_from_kwargs properly handles nested dataclasses."""
        kwargs = {
            "allow_remote_fetch": True,  # nested field in network
            "allowed_hosts": ["trusted.example.com"],  # nested field in network
            "require_https": True,  # nested field in network
            "title": "Test Book",  # top-level field
            "author": "Test Author",  # top-level field
            "chapter_split_mode": "heading",  # top-level field
        }

        options = _create_renderer_options_from_kwargs("epub", **kwargs)

        # Should be an EpubRendererOptions instance
        assert isinstance(options, EpubRendererOptions)

        # Top-level fields should be set
        assert options.title == "Test Book"
        assert options.author == "Test Author"
        assert options.chapter_split_mode == "heading"

        # Nested network field should be instantiated as NetworkFetchOptions
        assert options.network is not None
        assert options.network.allow_remote_fetch is True
        assert options.network.allowed_hosts == ["trusted.example.com"]
        assert options.network.require_https is True

    def test_create_renderer_options_with_partial_nested_fields(self):
        """Test creating renderer options with only some nested fields specified."""
        kwargs = {
            "allow_remote_fetch": True,  # nested field
            "title": "Partial Test",  # top-level field
        }

        options = _create_renderer_options_from_kwargs("epub", **kwargs)

        assert isinstance(options, EpubRendererOptions)
        assert options.title == "Partial Test"
        assert options.network is not None
        assert options.network.allow_remote_fetch is True
        # Other nested fields should have their defaults
        assert options.network.require_https is True  # default

    def test_create_renderer_options_without_nested_fields(self):
        """Test creating renderer options without any nested fields specified."""
        kwargs = {
            "title": "No Nested",
            "author": "Test",
        }

        options = _create_renderer_options_from_kwargs("epub", **kwargs)

        assert isinstance(options, EpubRendererOptions)
        assert options.title == "No Nested"
        assert options.author == "Test"
        # network should use defaults
        assert options.network is not None
        assert options.network.allow_remote_fetch is False  # default

    def test_nested_renderer_fields_not_marked_as_unmatched(self, caplog):
        """Test that nested renderer fields are not logged as unmatched kwargs."""
        import logging

        # Set both the caplog level AND the logger level to ensure DEBUG messages are captured
        caplog.set_level(logging.DEBUG)
        # Explicitly set the logger level for the api module
        api_logger = logging.getLogger("all2md.api")
        original_level = api_logger.level
        api_logger.setLevel(logging.DEBUG)

        try:
            kwargs = {
                "allow_remote_fetch": True,  # nested field
                "allowed_hosts": ["example.com"],  # nested field
                "title": "Test",
            }

            _split_kwargs_for_parser_and_renderer("pdf", "epub", kwargs)

            # Check that debug logs don't mention these as unmatched
            unmatched_logs = [record for record in caplog.records if "don't match parser or renderer" in record.message]

            if unmatched_logs:
                unmatched_msg = unmatched_logs[0].message
                assert "allow_remote_fetch" not in unmatched_msg
                assert "allowed_hosts" not in unmatched_msg
        finally:
            # Restore original logger level
            api_logger.setLevel(original_level)

    def test_renderer_with_multiple_nested_dataclasses(self):
        """Test renderer options that have multiple nested dataclass fields."""
        # Note: Currently EPUB only has one nested field (network),
        # but this test verifies the logic would work for multiple
        kwargs = {
            "allow_remote_fetch": True,
            "network_timeout": 30.0,
            "title": "Multi-Nested Test",
        }

        options = _create_renderer_options_from_kwargs("epub", **kwargs)

        assert isinstance(options, EpubRendererOptions)
        assert options.network.allow_remote_fetch is True
        assert options.network.network_timeout == 30.0

    def test_invalid_nested_field_is_logged(self, caplog):
        """Test that invalid field names are still logged as unknown."""
        import logging

        # Set both the caplog level AND the logger level to ensure DEBUG messages are captured
        caplog.set_level(logging.DEBUG)
        # Explicitly set the logger level for the api module
        api_logger = logging.getLogger("all2md.api")
        original_level = api_logger.level
        api_logger.setLevel(logging.DEBUG)

        try:
            kwargs = {
                "invalid_field_name": True,
                "title": "Test",
            }

            _create_renderer_options_from_kwargs("epub", **kwargs)

            # Should have a debug log about skipping unknown options
            assert any("Skipping unknown renderer options" in record.message for record in caplog.records)
            assert any("invalid_field_name" in record.message for record in caplog.records)
        finally:
            # Restore original logger level
            api_logger.setLevel(original_level)

    def test_nested_renderer_options_with_markdown_target(self):
        """Test that nested fields work correctly when target is markdown (no nested fields)."""
        kwargs = {
            "flavor": "gfm",  # markdown renderer option
            "pages": [1, 2],  # parser option
        }

        parser_kwargs, renderer_kwargs = _split_kwargs_for_parser_and_renderer("pdf", "markdown", kwargs)

        assert "pages" in parser_kwargs
        assert "flavor" in renderer_kwargs
        # Should not cause errors even though markdown renderer has no nested fields


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
