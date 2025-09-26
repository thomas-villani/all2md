"""Unit tests for _merge_options field-wise merging functionality.

This module tests the _merge_options function to ensure that when merging
MarkdownOptions via kwargs, existing fields are preserved and only the
specified kwargs fields are overridden.
"""

import pytest

from all2md import _merge_options
from all2md.options import MarkdownOptions, PdfOptions


class TestMergeOptions:
    """Test _merge_options field-wise merging behavior."""

    def test_merge_markdown_options_preserves_existing_fields(self):
        """Test that merging MarkdownOptions preserves existing fields."""
        # Create base options with MarkdownOptions
        base_markdown = MarkdownOptions(
            emphasis_symbol="_",
            bullet_symbols="*-+",
            list_indent_width=2,
            include_page_numbers=True
        )
        base_options = PdfOptions(markdown_options=base_markdown)

        # Merge with only one markdown field
        result = _merge_options(
            base_options,
            "pdf",
            emphasis_symbol="*"  # Only override this field
        )

        # Check that the field was updated
        assert result.markdown_options.emphasis_symbol == "*"

        # Check that other fields were preserved
        assert result.markdown_options.bullet_symbols == "*-+"
        assert result.markdown_options.list_indent_width == 2
        assert result.markdown_options.include_page_numbers is True

    def test_merge_multiple_markdown_fields(self):
        """Test merging multiple MarkdownOptions fields at once."""
        base_markdown = MarkdownOptions(
            emphasis_symbol="_",
            bullet_symbols="*-+",
            list_indent_width=2,
            include_page_numbers=True,
            page_separator="---"
        )
        base_options = PdfOptions(markdown_options=base_markdown)

        # Merge with multiple markdown fields
        result = _merge_options(
            base_options,
            "pdf",
            emphasis_symbol="*",
            list_indent_width=4
        )

        # Check that specified fields were updated
        assert result.markdown_options.emphasis_symbol == "*"
        assert result.markdown_options.list_indent_width == 4

        # Check that other fields were preserved
        assert result.markdown_options.bullet_symbols == "*-+"
        assert result.markdown_options.include_page_numbers is True
        assert result.markdown_options.page_separator == "---"

    def test_merge_with_none_markdown_options(self):
        """Test merging when base options has no MarkdownOptions."""
        base_options = PdfOptions()  # No markdown_options set

        result = _merge_options(
            base_options,
            "pdf",
            emphasis_symbol="*",
            list_indent_width=2
        )

        # Should create new MarkdownOptions with specified fields
        assert result.markdown_options is not None
        assert result.markdown_options.emphasis_symbol == "*"
        assert result.markdown_options.list_indent_width == 2

        # Other fields should have defaults
        assert result.markdown_options.include_page_numbers is False  # default

    def test_merge_non_markdown_fields_preserved(self):
        """Test that non-markdown fields are still merged correctly."""
        base_markdown = MarkdownOptions(emphasis_symbol="_")
        base_options = PdfOptions(
            markdown_options=base_markdown,
            pages=[1, 2, 3],
            extract_metadata=True
        )

        result = _merge_options(
            base_options,
            "pdf",
            emphasis_symbol="*",  # markdown field
            pages=[4, 5, 6],  # non-markdown field
            attachment_mode="base64"  # non-markdown field
        )

        # Check markdown options
        assert result.markdown_options.emphasis_symbol == "*"

        # Check non-markdown options
        assert result.pages == [4, 5, 6]
        assert result.attachment_mode == "base64"

        # Check preserved non-markdown options
        assert result.extract_metadata is True

    def test_merge_immutability(self):
        """Test that original options are not modified (immutable)."""
        base_markdown = MarkdownOptions(emphasis_symbol="_")
        base_options = PdfOptions(markdown_options=base_markdown)

        # Store original values
        original_emphasis = base_options.markdown_options.emphasis_symbol

        # Merge and modify
        result = _merge_options(
            base_options,
            "pdf",
            emphasis_symbol="*"
        )

        # Original should be unchanged
        assert base_options.markdown_options.emphasis_symbol == original_emphasis
        assert base_options.markdown_options.emphasis_symbol == "_"

        # Result should have new value
        assert result.markdown_options.emphasis_symbol == "*"

    def test_merge_empty_kwargs(self):
        """Test merging with empty kwargs returns same options."""
        base_markdown = MarkdownOptions(emphasis_symbol="_")
        base_options = PdfOptions(markdown_options=base_markdown)

        result = _merge_options(base_options, "pdf")

        # Should be equal but not the same object (due to deepcopy)
        assert result.markdown_options.emphasis_symbol == base_options.markdown_options.emphasis_symbol
        assert result is not base_options

    def test_merge_only_non_markdown_kwargs(self):
        """Test merging with only non-markdown kwargs."""
        base_markdown = MarkdownOptions(emphasis_symbol="_")
        base_options = PdfOptions(
            markdown_options=base_markdown,
            pages=[1, 2, 3]
        )

        result = _merge_options(
            base_options,
            "pdf",
            extract_metadata=True  # Only non-markdown field
        )

        # Markdown options should be preserved unchanged
        assert result.markdown_options.emphasis_symbol == "_"

        # Non-markdown field should be updated
        assert result.extract_metadata is True

        # Other non-markdown fields should be preserved
        assert result.pages == [1, 2, 3]

    def test_merge_with_mixed_field_types(self):
        """Test comprehensive merge with various field types."""
        base_markdown = MarkdownOptions(
            emphasis_symbol="_",
            bullet_symbols="*-+",
            list_indent_width=2
        )
        base_options = PdfOptions(
            markdown_options=base_markdown,
            pages=[1, 2],
            attachment_mode="alt_text"
        )

        result = _merge_options(
            base_options,
            "pdf",
            emphasis_symbol="*",  # string field
            bullet_symbols="•→",  # string field
            extract_metadata=True,  # boolean field
            attachment_mode="base64"  # enum field
        )

        # Check markdown field updates
        assert result.markdown_options.emphasis_symbol == "*"
        assert result.markdown_options.bullet_symbols == "•→"

        # Check markdown field preservation
        assert result.markdown_options.list_indent_width == 2

        # Check non-markdown updates
        assert result.extract_metadata is True
        assert result.attachment_mode == "base64"

        # Check non-markdown preservation
        assert result.pages == [1, 2]


if __name__ == "__main__":
    pytest.main([__file__])
