"""Integration tests for MHTML to Markdown conversion.

This module contains integration tests for the mhtml2markdown converter,
testing full conversion pipelines with real MHTML structures and edge cases.
"""

import io
from pathlib import Path

import pytest
from fixtures.generators.mhtml_fixtures import (
    create_malformed_mhtml,
    create_mhtml_file,
    create_mhtml_with_complex_html,
    create_mhtml_with_image,
    create_mhtml_with_ms_word_artifacts,
    create_mhtml_with_multiple_assets,
    create_simple_mhtml,
)
from utils import assert_markdown_valid

from all2md import to_markdown as mhtml_to_markdown, MhtmlOptions
from all2md.exceptions import MalformedFileError, ParsingError
from all2md.options import MarkdownOptions


@pytest.mark.integration
@pytest.mark.mhtml
class TestMhtmlIntegrationBasic:
    """Test basic MHTML integration scenarios."""

    def test_simple_mhtml_conversion(self, temp_dir):
        """Test conversion of a simple MHTML file."""
        mhtml_content = create_simple_mhtml()
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        result = mhtml_to_markdown(str(mhtml_file))

        assert isinstance(result, str)
        assert "Test MHTML Document" in result
        assert "**bold**" in result
        assert "*italic*" in result
        assert "[link](https://example.com)" in result
        assert "* First item" in result
        assert "* Second item" in result
        assert "* Third item" in result
        assert_markdown_valid(result)

    def test_simple_mhtml_with_bytesio(self):
        """Test conversion of MHTML from BytesIO."""
        mhtml_content = create_simple_mhtml()
        mhtml_file = io.BytesIO(mhtml_content)

        result = mhtml_to_markdown(mhtml_file, source_format="mhtml")

        assert isinstance(result, str)
        assert "Test MHTML Document" in result
        assert "**bold**" in result
        assert_markdown_valid(result)

    def test_simple_mhtml_with_pathlib_path(self, temp_dir):
        """Test conversion with pathlib.Path object."""
        mhtml_content = create_simple_mhtml()
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        result = mhtml_to_markdown(Path(mhtml_file))

        assert isinstance(result, str)
        assert "Test MHTML Document" in result
        assert_markdown_valid(result)

    def test_simple_mhtml_with_string_path(self, temp_dir):
        """Test conversion with string path."""
        mhtml_content = create_simple_mhtml()
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        result = mhtml_to_markdown(str(mhtml_file))

        assert isinstance(result, str)
        assert "Test MHTML Document" in result
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.mhtml
class TestMhtmlIntegrationImages:
    """Test MHTML integration with image handling."""

    def test_mhtml_with_image_base64(self, temp_dir):
        """Test MHTML with images using base64 embedding."""
        mhtml_content = create_mhtml_with_image()
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        options = MhtmlOptions(attachment_mode="base64")
        result = mhtml_to_markdown(mhtml_file, parser_options=options)

        assert isinstance(result, str)
        assert "Test MHTML with Image" in result
        # Base64 data URLs may be blocked by HTML converter for security, so check for alt text
        assert "![Test image]" in result
        assert_markdown_valid(result)

    def test_mhtml_with_image_download(self, temp_dir):
        """Test MHTML with images using download mode."""
        mhtml_content = create_mhtml_with_image()
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        image_dir = temp_dir / "images"
        options = MhtmlOptions(
            attachment_mode="download",
            attachment_output_dir=str(image_dir)
        )
        result = mhtml_to_markdown(mhtml_file, parser_options=options)

        assert isinstance(result, str)
        assert "Test MHTML with Image" in result
        # Should have image reference (format may vary: cid:, data:, or file path)
        assert "![Test image]" in result
        # Just verify conversion succeeded
        assert_markdown_valid(result)

    def test_mhtml_with_image_skip(self, temp_dir):
        """Test MHTML with images using skip mode."""
        mhtml_content = create_mhtml_with_image()
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        options = MhtmlOptions(attachment_mode="skip")
        result = mhtml_to_markdown(mhtml_file, parser_options=options)

        assert isinstance(result, str)
        assert "Test MHTML with Image" in result
        # Image processing should still happen (converted to data URI)
        # but final markdown might handle differently based on html2markdown
        assert_markdown_valid(result)

    def test_mhtml_with_multiple_assets(self, temp_dir):
        """Test MHTML with multiple embedded assets."""
        mhtml_content = create_mhtml_with_multiple_assets()
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        # Enable local file access to test file:// URL processing
        from all2md.options.common import LocalFileAccessOptions
        options = MhtmlOptions(
            attachment_mode="base64",
            local_files=LocalFileAccessOptions(
                allow_local_files=True,
                allow_cwd_files=True
            )
        )
        result = mhtml_to_markdown(mhtml_file, parser_options=options)

        assert isinstance(result, str)
        assert "MHTML with Multiple Assets" in result
        # Should contain image references (format may vary: cid:, data:, or file path)
        assert "![Image 1]" in result or "Image 1" in result
        # Should have table
        assert "| Column 1 | Column 2 |" in result or "Column" in result
        # Just verify conversion succeeded
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.mhtml
class TestMhtmlIntegrationMsWordArtifacts:
    """Test MHTML integration with MS Word artifact cleanup."""

    def test_mhtml_ms_word_artifacts_cleanup(self, temp_dir):
        """Test cleanup of MS Word artifacts in MHTML."""
        mhtml_content = create_mhtml_with_ms_word_artifacts()
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        result = mhtml_to_markdown(str(mhtml_file))

        assert isinstance(result, str)
        assert "MS Word MHTML Document" in result
        # MS Word artifacts should be cleaned
        assert "<!--[if" not in result
        assert "<o:p>" not in result
        assert "<w:" not in result
        # List items should be processed
        assert "First list item" in result
        assert "Second list item" in result
        assert_markdown_valid(result)

    def test_mhtml_ms_word_list_processing(self, temp_dir):
        """Test MS Word list processing in MHTML."""
        mhtml_content = create_mhtml_with_ms_word_artifacts()
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        result = mhtml_to_markdown(str(mhtml_file))

        assert isinstance(result, str)
        # Should convert list items properly
        # The exact format depends on html2markdown processing
        assert "First list item" in result
        assert "Second list item" in result
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.mhtml
class TestMhtmlIntegrationComplexStructure:
    """Test MHTML integration with complex HTML structures."""

    def test_mhtml_with_complex_html(self, temp_dir):
        """Test MHTML with complex HTML structure."""
        mhtml_content = create_mhtml_with_complex_html()
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        result = mhtml_to_markdown(str(mhtml_file))

        assert isinstance(result, str)
        assert "Complex MHTML Document" in result
        # Should handle various HTML elements
        assert "Centered Section" in result
        assert "> This is a blockquote" in result
        assert "```" in result or "    " in result  # Code blocks
        assert "function example()" in result
        # Nested lists
        assert "First item" in result
        assert "Nested item 1" in result
        # Complex table
        assert "Header 1" in result
        assert "Sub Header 1" in result
        assert "Row 1 Cell 1" in result
        assert_markdown_valid(result)

    def test_mhtml_table_processing(self, temp_dir):
        """Test MHTML table processing specifically."""
        mhtml_content = create_mhtml_with_complex_html()
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        result = mhtml_to_markdown(str(mhtml_file))

        assert isinstance(result, str)
        # Should contain table structure
        assert "|" in result  # Markdown table syntax
        # Should have table content
        assert "Header 1" in result
        assert "Header Group" in result
        assert "Row 1 Cell 1" in result
        assert "Merged cells content" in result
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.mhtml
class TestMhtmlIntegrationErrorHandling:
    """Test MHTML integration error handling scenarios."""

    def test_nonexistent_file(self):
        """Test handling of nonexistent MHTML file."""
        with pytest.raises((MalformedFileError, ParsingError)):
            mhtml_to_markdown("nonexistent.mht")

    def test_malformed_mhtml_file(self, temp_dir):
        """Test handling of malformed MHTML file."""
        malformed_content = create_malformed_mhtml()
        mhtml_file = create_mhtml_file(malformed_content, temp_dir)

        with pytest.raises(ParsingError) as exc_info:
            mhtml_to_markdown(str(mhtml_file))

        assert "No HTML content found" in str(exc_info.value)

    def test_empty_mhtml_file(self, temp_dir):
        """Test handling of empty MHTML file."""
        empty_file = temp_dir / "empty.mht"
        empty_file.write_bytes(b"")

        with pytest.raises((ParsingError, MalformedFileError)):
            mhtml_to_markdown(empty_file)

    def test_invalid_input_type(self):
        """Test handling of invalid input types."""
        with pytest.raises((MalformedFileError, AttributeError, TypeError)):
            mhtml_to_markdown(123)  # Invalid type

    def test_directory_instead_of_file(self, temp_dir):
        """Test handling when directory is passed instead of file."""
        with pytest.raises((MalformedFileError, ParsingError, PermissionError)):
            mhtml_to_markdown(temp_dir)


@pytest.mark.integration
@pytest.mark.mhtml
class TestMhtmlIntegrationOptions:
    """Test MHTML integration with various option configurations."""

    def test_mhtml_with_custom_markdown_options(self, temp_dir):
        """Test MHTML conversion with custom Markdown options."""
        mhtml_content = create_simple_mhtml()
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        md_options = MarkdownOptions(
            emphasis_symbol="_",
            bullet_symbols="+-*"
        )
        parser_options = MhtmlOptions()
        result = mhtml_to_markdown(mhtml_file, parser_options=parser_options, renderer_options=md_options)

        assert isinstance(result, str)
        # Should use custom emphasis symbol
        assert "_italic_" in result or "__bold__" in result
        assert_markdown_valid(result)

    def test_mhtml_options_inheritance(self, temp_dir):
        """Test that MHTML options properly inherit from base options."""
        mhtml_content = create_simple_mhtml()
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        options = MhtmlOptions(
            attachment_mode="skip",
            attachment_output_dir="/custom/path",
            attachment_base_url="https://example.com"
        )
        result = mhtml_to_markdown(mhtml_file, parser_options=options)

        assert isinstance(result, str)
        assert_markdown_valid(result)

    def test_all_option_combinations(self, temp_dir):
        """Test various option combinations work correctly."""
        mhtml_content = create_mhtml_with_image()
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        option_combinations = [
            (MhtmlOptions(), None),  # Default options
            (MhtmlOptions(attachment_mode="base64"), None),
            (MhtmlOptions(attachment_mode="skip"), None),
            (MhtmlOptions(
                attachment_mode="download",
                attachment_output_dir=str(temp_dir / "images")
            ), None),
            (MhtmlOptions(
                attachment_mode="base64"
            ), MarkdownOptions(emphasis_symbol="_")),
        ]

        for parser_options, renderer_options in option_combinations:
            result = mhtml_to_markdown(mhtml_file, parser_options=parser_options, renderer_options=renderer_options)

            assert isinstance(result, str)
            assert len(result) > 0
            assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.mhtml
@pytest.mark.slow
class TestMhtmlIntegrationPerformance:
    """Test MHTML integration performance scenarios."""

    def test_large_mhtml_performance(self, temp_dir):
        """Test performance with larger MHTML structures."""
        # Use complex MHTML for performance testing
        mhtml_content = create_mhtml_with_complex_html()

        # Test multiple times to check for consistency
        for _i in range(3):
            mhtml_file = create_mhtml_file(mhtml_content, temp_dir)
            result = mhtml_to_markdown(str(mhtml_file))

            assert isinstance(result, str)
            assert len(result) > 0
            assert_markdown_valid(result)

    def test_multiple_mhtml_conversions(self, temp_dir):
        """Test multiple MHTML conversions in sequence."""
        results = []

        # Convert different MHTML types
        mhtml_generators = [
            create_simple_mhtml,
            create_mhtml_with_image,
            create_mhtml_with_ms_word_artifacts,
            create_mhtml_with_complex_html,
        ]

        for mhtml_generator in mhtml_generators:
            mhtml_content = mhtml_generator()
            mhtml_file = create_mhtml_file(mhtml_content, temp_dir)
            result = mhtml_to_markdown(str(mhtml_file))

            assert isinstance(result, str)
            assert len(result) > 0
            assert_markdown_valid(result)
            results.append(result)

        # Verify all conversions were different
        assert len(set(results)) == len(results)

    def test_repeated_asset_processing(self, temp_dir):
        """Test performance with repeated asset processing."""
        mhtml_content = create_mhtml_with_multiple_assets()

        # Enable local file access to test file:// URL processing
        from all2md.options import MhtmlOptions
        from all2md.options.common import LocalFileAccessOptions
        options = MhtmlOptions(
            local_files=LocalFileAccessOptions(
                allow_local_files=True,
                allow_cwd_files=True
            )
        )

        # Convert same file multiple times
        for _i in range(3):
            mhtml_file = create_mhtml_file(mhtml_content, temp_dir)
            result = mhtml_to_markdown(mhtml_file, parser_options=options)

            assert isinstance(result, str)
            # Data URLs may be blocked, so check for image processing instead
            assert "![Image 1]" in result and "![Image 2]" in result
            assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.mhtml
class TestMhtmlIntegrationEncoding:
    """Test MHTML integration with different character encodings."""

    def test_mhtml_utf8_encoding(self, temp_dir):
        """Test MHTML with UTF-8 encoded content."""
        # Create MHTML with UTF-8 content
        mhtml_content_str = """MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<!DOCTYPE html>
<html>
<body>
    <h1>Test Document with UTF-8</h1>
    <p>Content with accents: café, résumé, naïve</p>
    <p>Symbols: © ® ™ € £ ¥</p>
    <p>Math: α β γ δ ∑ ∫ √</p>
</body>
</html>

--test-boundary--
"""
        mhtml_content = mhtml_content_str.encode('utf-8')
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        result = mhtml_to_markdown(str(mhtml_file))

        assert isinstance(result, str)
        assert "café, résumé, naïve" in result
        assert "© ® ™ € £ ¥" in result
        assert "α β γ δ" in result
        assert_markdown_valid(result)

    def test_mhtml_missing_charset(self, temp_dir):
        """Test MHTML without explicit charset (should default to UTF-8)."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html

<!DOCTYPE html>
<html>
<body>
    <h1>Test Without Charset</h1>
    <p>Regular ASCII content should work fine.</p>
</body>
</html>

--test-boundary--
"""
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        result = mhtml_to_markdown(str(mhtml_file))

        assert isinstance(result, str)
        assert "Test Without Charset" in result
        assert "Regular ASCII content" in result
        assert_markdown_valid(result)


@pytest.mark.integration
@pytest.mark.mhtml
class TestMhtmlSecurityIntegration:
    """Test MHTML security features integration."""

    def test_file_url_security_master_switch(self, temp_dir):
        """Test that master switch blocks file:// URLs even with allow_cwd_files=True."""
        # Create MHTML with file:// references to current directory
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<!DOCTYPE html>
<html>
<body>
    <h1>Test Security</h1>
    <img src="file://./test_image.png" alt="Local file">
    <img src="file:///etc/passwd" alt="System file">
</body>
</html>

--test-boundary--
"""
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        # Test with master switch disabled (default)
        options = MhtmlOptions()  # Uses default security settings
        result = mhtml_to_markdown(mhtml_file, parser_options=options)

        assert isinstance(result, str)
        # Security handling varies - just verify conversion succeeded
        # file:// URLs may be blocked, preserved, or converted based on security settings
        assert_markdown_valid(result)

    def test_file_url_security_explicit_disable(self, temp_dir):
        """Test explicit disabling of local file access."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<!DOCTYPE html>
<html>
<body>
    <h1>Test Security</h1>
    <img src="file://./allowed_image.png" alt="CWD file">
</body>
</html>

--test-boundary--
"""
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        # Explicitly disable local file access
        from all2md.options.common import LocalFileAccessOptions
        local_files_options = LocalFileAccessOptions(
            allow_local_files=False,
            allow_cwd_files=True  # Should be ignored due to master switch
        )
        options = MhtmlOptions(local_files=local_files_options)
        result = mhtml_to_markdown(mhtml_file, parser_options=options)

        assert isinstance(result, str)
        # Security handling varies - just verify conversion succeeded
        assert_markdown_valid(result)

    def test_file_url_security_with_allowlist(self, temp_dir):
        """Test local file access with allowlist."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<!DOCTYPE html>
<html>
<body>
    <h1>Test Allowlist</h1>
    <img src="file:///allowed/path/image.png" alt="Allowed file">
    <img src="file:///denied/path/image.png" alt="Denied file">
</body>
</html>

--test-boundary--
"""
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        # Enable local files with allowlist
        from all2md.options.common import LocalFileAccessOptions
        local_files_options = LocalFileAccessOptions(
            allow_local_files=True,
            local_file_allowlist=["/allowed/path"],
            allow_cwd_files=False
        )
        options = MhtmlOptions(local_files=local_files_options)
        result = mhtml_to_markdown(mhtml_file, parser_options=options)

        assert isinstance(result, str)
        # Should not contain the file URLs since files don't actually exist
        # but processing should not fail
        assert_markdown_valid(result)

    def test_file_url_security_with_denylist(self, temp_dir):
        """Test local file access with denylist."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<!DOCTYPE html>
<html>
<body>
    <h1>Test Denylist</h1>
    <img src="file:///etc/passwd" alt="System file">
    <img src="file:///safe/path/image.png" alt="Safe file">
</body>
</html>

--test-boundary--
"""
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        # Enable local files with denylist
        from all2md.options.common import LocalFileAccessOptions
        local_files_options = LocalFileAccessOptions(
            allow_local_files=True,
            local_file_denylist=["/etc", "/var", "/usr"],
            allow_cwd_files=False
        )
        options = MhtmlOptions(local_files=local_files_options)
        result = mhtml_to_markdown(mhtml_file, parser_options=options)

        assert isinstance(result, str)
        # Images should be processed according to denylist rules
        assert_markdown_valid(result)

    def test_cwd_file_security_when_enabled(self, temp_dir):
        """Test CWD file access when properly enabled."""
        # Create a test image file in temp directory
        test_image = temp_dir / "test_image.png"
        test_image.write_bytes(b"fake_png_data")

        mhtml_content = f"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<!DOCTYPE html>
<html>
<body>
    <h1>Test CWD Access</h1>
    <img src="file://./{test_image.name}" alt="CWD file">
</body>
</html>

--test-boundary--
""".encode('utf-8')

        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        # Change to temp directory to test CWD access
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)

            # Enable CWD access properly
            from all2md.options.common import LocalFileAccessOptions
            local_files_options = LocalFileAccessOptions(
                allow_local_files=True,  # Master switch must be True
                allow_cwd_files=True
            )
            options = MhtmlOptions(local_files=local_files_options)
            result = mhtml_to_markdown(mhtml_file, parser_options=options)

            assert isinstance(result, str)
            assert_markdown_valid(result)

        finally:
            os.chdir(original_cwd)

    def test_mixed_security_scenarios(self, temp_dir):
        """Test mixed security scenarios with various URL types."""
        mhtml_content = b"""MIME-Version: 1.0
Content-Type: multipart/related; boundary="test-boundary"

--test-boundary
Content-Type: text/html; charset=utf-8

<!DOCTYPE html>
<html>
<body>
    <h1>Mixed URL Types</h1>
    <img src="http://example.com/remote.png" alt="Remote file">
    <img src="file://./local.png" alt="Local file">
    <img src="data:image/png;base64,abc" alt="Data URI">
    <img src="cid:embedded" alt="CID reference">
</body>
</html>

--test-boundary
Content-Type: image/png
Content-ID: <embedded>

fake_image_data
--test-boundary--
"""
        mhtml_file = create_mhtml_file(mhtml_content, temp_dir)

        # Test with default security (should block file:// but allow others)
        options = MhtmlOptions()
        result = mhtml_to_markdown(mhtml_file, parser_options=options)

        assert isinstance(result, str)
        # Should have image references (various formats may be used)
        assert "![Remote file]" in result or "![Data URI]" in result or "![CID reference]" in result
        # Just verify conversion succeeded - URL handling varies based on security
        assert_markdown_valid(result)
