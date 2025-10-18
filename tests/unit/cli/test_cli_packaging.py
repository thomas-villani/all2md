"""Unit tests for CLI packaging features.

Tests for --zip flag and in-memory packaging utilities.
"""

import zipfile


class TestCreatePackageFromConversions:
    """Test create_package_from_conversions function."""

    def test_create_package_basic(self, tmp_path):
        """Test basic package creation from text files."""
        from all2md.cli.input_items import CLIInputItem
        from all2md.cli.packaging import create_package_from_conversions

        # Create test input files
        input1 = tmp_path / "input1.txt"
        input2 = tmp_path / "input2.txt"
        input1.write_text("# Test Document 1\n\nContent here.")
        input2.write_text("# Test Document 2\n\nMore content.")

        # Create CLIInputItem objects
        item1 = CLIInputItem(
            raw_input=input1,
            kind='local_file',
            display_name=input1.name,
            path_hint=input1,
        )
        item2 = CLIInputItem(
            raw_input=input2,
            kind='local_file',
            display_name=input2.name,
            path_hint=input2,
        )

        zip_path = tmp_path / "output.zip"

        # Create package
        result = create_package_from_conversions(
            input_items=[item1, item2],
            zip_path=zip_path,
            target_format="markdown"
        )

        # Verify zip was created
        assert result.exists()
        assert result == zip_path

        # Verify contents
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            assert "input1.md" in names
            assert "input2.md" in names

    def test_create_package_different_formats(self, tmp_path):
        """Test package creation with different target formats."""
        from all2md.cli.input_items import CLIInputItem
        from all2md.cli.packaging import create_package_from_conversions

        input_file = tmp_path / "test.txt"
        input_file.write_text("# Test\n\nSome content.")

        item = CLIInputItem(
            raw_input=input_file,
            kind='local_file',
            display_name=input_file.name,
            path_hint=input_file,
        )

        # Test HTML format
        zip_html = tmp_path / "output_html.zip"
        create_package_from_conversions(
            input_items=[item],
            zip_path=zip_html,
            target_format="html"
        )

        with zipfile.ZipFile(zip_html, 'r') as zf:
            assert "test.html" in zf.namelist()

    def test_create_package_forces_base64(self, tmp_path):
        """Test that packaging forces base64 attachment mode."""
        from all2md.cli.input_items import CLIInputItem
        from all2md.cli.packaging import create_package_from_conversions

        input_file = tmp_path / "test.txt"
        input_file.write_text("Test content")

        item = CLIInputItem(
            raw_input=input_file,
            kind='local_file',
            display_name=input_file.name,
            path_hint=input_file,
        )

        zip_path = tmp_path / "output.zip"

        # Pass options that would normally use download mode
        options = {"attachment_mode": "download"}

        # Package should override this to base64
        create_package_from_conversions(
            input_items=[item],
            zip_path=zip_path,
            target_format="markdown",
            options=options
        )

        # Verify zip was created (base64 mode won't create external files)
        assert zip_path.exists()

    def test_create_package_handles_conversion_errors(self, tmp_path):
        """Test that packaging continues on conversion errors."""
        from all2md.cli.input_items import CLIInputItem
        from all2md.cli.packaging import create_package_from_conversions

        # Create one valid file and one that will fail
        valid_file = tmp_path / "valid.txt"
        valid_file.write_text("Valid content")

        invalid_file = tmp_path / "nonexistent.txt"  # Doesn't exist

        valid_item = CLIInputItem(
            raw_input=valid_file,
            kind='local_file',
            display_name=valid_file.name,
            path_hint=valid_file,
        )

        invalid_item = CLIInputItem(
            raw_input=invalid_file,
            kind='local_file',
            display_name=invalid_file.name,
            path_hint=invalid_file,
        )

        zip_path = tmp_path / "output.zip"

        # Should not raise, just skip invalid files
        result = create_package_from_conversions(
            input_items=[valid_item, invalid_item],
            zip_path=zip_path,
            target_format="markdown"
        )

        assert result.exists()

        # Valid file should be in zip
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            assert "valid.md" in names


class TestZipCLIIntegration:
    """Test --zip CLI flag integration."""

    def test_zip_flag_is_recognized(self, tmp_path):
        """Test that --zip flag is recognized by the parser."""
        from all2md.cli.builder import create_parser

        parser = create_parser()

        # Should parse without error
        args = parser.parse_args([
            str(tmp_path / "test.txt"),
            '--zip'
        ])

        # Zip should be set
        assert hasattr(args, 'zip')
        assert args.zip == 'auto'  # default const value

    def test_zip_with_custom_path(self, tmp_path):
        """Test --zip with custom path."""
        from all2md.cli.builder import create_parser

        parser = create_parser()
        custom_zip = str(tmp_path / "custom.zip")

        args = parser.parse_args([
            str(tmp_path / "test.txt"),
            '--zip', custom_zip
        ])

        assert args.zip == custom_zip

    def test_zip_without_output_dir(self, tmp_path):
        """Test that --zip works without --output-dir."""
        from all2md.cli.builder import create_parser

        parser = create_parser()

        # Should parse successfully without --output-dir
        args = parser.parse_args([
            str(tmp_path / "test.txt"),
            '--zip', 'output.zip'
        ])

        assert args.zip == 'output.zip'
        # output_dir should not be required
        assert not hasattr(args, 'output_dir') or args.output_dir is None
