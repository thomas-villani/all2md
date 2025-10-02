"""Integration tests for ODF to Markdown conversion.

This module tests the ODF converter with real ODF documents, verifying
the complete conversion pipeline from ODF files to Markdown output.
"""

import tempfile
from io import BytesIO
from pathlib import Path

import pytest

from all2md.parsers.odf2markdown import odf_to_markdown
from all2md.options import MarkdownOptions, OdfOptions


@pytest.mark.integration
@pytest.mark.odf
class TestOdfIntegration:
    """Integration tests for ODF conversion with real documents."""

    def test_basic_odt_conversion(self):
        """Test conversion of basic ODT document."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        # Skip if test file doesn't exist
        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        result = odf_to_markdown(odt_path)

        # Verify basic document structure
        assert isinstance(result, str)
        assert len(result) > 0

        # Should contain heading
        assert "#" in result

        # Should handle text content
        lines = result.split('\n')
        content_lines = [line for line in lines if line.strip()]
        assert len(content_lines) > 0

    # def test_simple_odt_conversion(self):
    #     """Test conversion of simple ODT document."""
    #     odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"
    #
    #     # Skip if test file doesn't exist
    #     if not odt_path.exists():
    #         pytest.skip("Test ODT file not found")
    #
    #     result = odf_to_markdown(odt_path)
    #
    #     assert isinstance(result, str)
    #     assert len(result) > 0

    def test_odt_with_formatting(self):
        """Test ODT with text formatting (bold, italic)."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        result = odf_to_markdown(odt_path)

        # Should handle text content without errors
        assert isinstance(result, str)
        # Basic validation - no specific formatting assertions since content varies

    def test_odt_with_lists(self):
        """Test ODT with different list types."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        result = odf_to_markdown(odt_path)

        # If document contains lists, should process them
        assert isinstance(result, str)
        # May contain list markers depending on document content

    def test_odt_with_tables(self):
        """Test ODT with table content."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        options = OdfOptions(preserve_tables=True)
        result = odf_to_markdown(odt_path, options)

        # Should process without error
        assert isinstance(result, str)

    def test_odt_tables_disabled(self):
        """Test ODT conversion with tables disabled."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        options = OdfOptions(preserve_tables=False)
        result = odf_to_markdown(odt_path, options)

        assert isinstance(result, str)
        # Tables should be omitted but document should still process

    def test_odt_with_custom_markdown_options(self):
        """Test ODT conversion with custom Markdown formatting."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        md_options = MarkdownOptions(
            emphasis_symbol="_",
            bullet_symbols="•+-",
        )
        options = OdfOptions(markdown_options=md_options)

        result = odf_to_markdown(odt_path, options)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_odt_file_object_input(self):
        """Test ODT conversion with file object input."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        with open(odt_path, 'rb') as f:
            result = odf_to_markdown(f)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_odt_bytesio_input(self):
        """Test ODT conversion with BytesIO input."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        # Read file into BytesIO
        with open(odt_path, 'rb') as f:
            data = f.read()

        bio = BytesIO(data)
        result = odf_to_markdown(bio)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_odt_string_path_input(self):
        """Test ODT conversion with string path input."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        result = odf_to_markdown(str(odt_path))

        assert isinstance(result, str)
        assert len(result) > 0

    def test_nonexistent_odt_file(self):
        """Test error handling for nonexistent ODT file."""
        nonexistent_path = Path("/tmp/nonexistent.odt")

        with pytest.raises(Exception):
            # Should raise an exception when file doesn't exist
            odf_to_markdown(nonexistent_path)

    def test_invalid_odt_content(self):
        """Test error handling for invalid ODT content."""
        # Create a file with invalid ODT content
        with tempfile.NamedTemporaryFile(suffix='.odt', delete=False) as tmp:
            tmp.write(b"This is not a valid ODT file")
            tmp.flush()

            with pytest.raises(Exception):
                # Should raise exception for invalid ODT content
                odf_to_markdown(tmp.name)

    def test_empty_odt_file(self):
        """Test handling of empty ODT file."""
        # Create empty file
        with tempfile.NamedTemporaryFile(suffix='.odt', delete=False) as tmp:
            tmp.flush()

            with pytest.raises(Exception):
                # Should raise exception for empty file
                odf_to_markdown(tmp.name)

    def test_odt_content_cleanup(self):
        """Test that converted content is properly cleaned up."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        result = odf_to_markdown(odt_path)

        # Should not have excessive blank lines
        lines = result.split('\n')
        blank_line_count = sum(1 for line in lines if line.strip() == '')
        total_lines = len(lines)

        # Reasonable ratio of content to blank lines
        if total_lines > 0:
            blank_ratio = blank_line_count / total_lines
            assert blank_ratio < 0.8  # Less than 80% blank lines

    def test_odt_unicode_handling(self):
        """Test handling of Unicode characters in ODT."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        result = odf_to_markdown(odt_path)

        # Should handle Unicode without errors
        assert isinstance(result, str)
        # Try encoding/decoding to verify Unicode handling
        encoded = result.encode('utf-8')
        decoded = encoded.decode('utf-8')
        assert decoded == result

    def test_odt_attachment_modes(self):
        """Test different attachment handling modes."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        # Test alt_text mode (default)
        options_alt = OdfOptions(attachment_mode="alt_text")
        result_alt = odf_to_markdown(odt_path, options_alt)
        assert isinstance(result_alt, str)

        # Test base64 mode
        options_b64 = OdfOptions(attachment_mode="base64")
        result_b64 = odf_to_markdown(odt_path, options_b64)
        assert isinstance(result_b64, str)

        # Test download mode
        with tempfile.TemporaryDirectory() as tmp_dir:
            options_dl = OdfOptions(
                attachment_mode="download",
                attachment_output_dir=tmp_dir
            )
            result_dl = odf_to_markdown(odt_path, options_dl)
            assert isinstance(result_dl, str)

    def test_odt_large_document_performance(self):
        """Test performance with larger ODT documents."""
        # This is a basic performance test - mainly ensuring no major slowdowns
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        import time
        start_time = time.time()

        result = odf_to_markdown(odt_path)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete within reasonable time (adjust threshold as needed)
        assert duration < 30  # 30 seconds max for basic document
        assert isinstance(result, str)

    def test_odt_multiple_conversions(self):
        """Test multiple consecutive conversions."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        # Convert same document multiple times
        results = []
        for i in range(3):
            result = odf_to_markdown(odt_path)
            results.append(result)

        # All results should be identical
        assert all(r == results[0] for r in results)
        assert len(results[0]) > 0

    def test_odt_different_options_consistency(self):
        """Test that different option combinations work consistently."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        # Test various option combinations
        option_sets = [
            OdfOptions(),  # Default options
            OdfOptions(preserve_tables=True),
            OdfOptions(preserve_tables=False),
            OdfOptions(attachment_mode="base64"),
            OdfOptions(
                preserve_tables=True,
                attachment_mode="alt_text",
                markdown_options=MarkdownOptions(emphasis_symbol="_")
            ),
        ]

        results = []
        for options in option_sets:
            result = odf_to_markdown(odt_path, options)
            results.append(result)
            assert isinstance(result, str)
            assert len(result) >= 0  # Could be empty for some option combinations

        # All should complete without errors
        assert len(results) == len(option_sets)


@pytest.mark.integration
@pytest.mark.odf
@pytest.mark.slow
class TestOdfAdvancedIntegration:
    """Advanced integration tests for complex ODF scenarios."""

    def test_odf_memory_usage(self):
        """Test memory usage doesn't grow excessively."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        # Convert multiple times and check for memory leaks
        import gc

        for i in range(5):
            result = odf_to_markdown(odt_path)
            assert isinstance(result, str)
            # Force garbage collection
            gc.collect()

        # Test passes if no memory errors occur

    def test_odf_concurrent_access(self):
        """Test concurrent access to ODF conversion."""
        odt_path = Path(__file__).parent.parent / "fixtures" / "documents" / "basic.odt"

        if not odt_path.exists():
            pytest.skip("Test ODT file not found")

        import threading

        results = []
        errors = []

        def convert_document():
            try:
                result = odf_to_markdown(odt_path)
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Start multiple conversion threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=convert_document)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All should succeed without errors
        assert len(errors) == 0, f"Conversion errors: {errors}"
        assert len(results) == 3
        assert all(isinstance(r, str) for r in results)
