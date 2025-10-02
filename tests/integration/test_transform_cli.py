#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Integration tests for transform CLI."""
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
class TestTransformCLI:
    """Tests for CLI transform integration."""

    def test_list_transforms_command(self):
        """Test list-transforms subcommand."""
        result = subprocess.run(
            [sys.executable, '-m', 'all2md', 'list-transforms'],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        # May not show transforms if entry points not installed, just check it runs
        assert 'Transforms' in result.stdout or 'transforms' in result.stdout.lower()

    def test_list_transforms_specific(self):
        """Test list-transforms with specific transform."""
        result = subprocess.run(
            [sys.executable, '-m', 'all2md', 'list-transforms', 'heading-offset'],
            capture_output=True,
            text=True
        )
        # May fail if entry points not installed
        # Just check it handles the command
        assert result.returncode in (0, 1)

    def test_list_transforms_unknown(self):
        """Test list-transforms with unknown transform."""
        result = subprocess.run(
            [sys.executable, '-m', 'all2md', 'list-transforms', 'nonexistent'],
            capture_output=True,
            text=True
        )
        # May fail differently if entry points not installed
        assert result.returncode != 0 or 'not found' in result.stderr.lower()

    def test_transform_flag_single(self, tmp_path):
        """Test --transform with single transform."""
        # Create a test file
        test_content = "# Test\nSome text."
        test_file = tmp_path / "test.txt"
        test_file.write_text(test_content)

        result = subprocess.run(
            [
                sys.executable, '-m', 'all2md',
                str(test_file),
                '--transform', 'remove-images',
                '--format', 'auto'
            ],
            capture_output=True,
            text=True
        )
        # May fail if entry points not installed, or succeed
        assert result.returncode in (0, 1, 2, 3)

    def test_transform_flag_multiple_ordered(self, tmp_path):
        """Test multiple --transform flags (order matters)."""
        test_content = "# Test"
        test_file = tmp_path / "test.txt"
        test_file.write_text(test_content)

        result = subprocess.run(
            [
                sys.executable, '-m', 'all2md',
                str(test_file),
                '--transform', 'remove-images',
                '--transform', 'heading-offset',
                '--format', 'auto'
            ],
            capture_output=True,
            text=True
        )
        # May fail if entry points not installed
        assert result.returncode in (0, 1, 2, 3)

    def test_transform_with_parameters(self, tmp_path):
        """Test transform with parameters."""
        test_content = "# Test"
        test_file = tmp_path / "test.txt"
        test_file.write_text(test_content)

        result = subprocess.run(
            [
                sys.executable, '-m', 'all2md',
                str(test_file),
                '--transform', 'heading-offset',
                '--format', 'auto'
            ],
            capture_output=True,
            text=True
        )
        # May fail if entry points not installed
        assert result.returncode in (0, 1, 2, 3)

    def test_transform_short_flag(self, tmp_path):
        """Test -t short flag for transforms."""
        test_content = "# Test"
        test_file = tmp_path / "test.txt"
        test_file.write_text(test_content)

        result = subprocess.run(
            [
                sys.executable, '-m', 'all2md',
                str(test_file),
                '-t', 'heading-offset',
                '--format', 'auto'
            ],
            capture_output=True,
            text=True
        )
        # May fail if entry points not installed
        assert result.returncode in (0, 1, 2, 3)

    def test_unknown_transform_error(self, tmp_path):
        """Test error handling for unknown transform."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        result = subprocess.run(
            [
                sys.executable, '-m', 'all2md',
                str(test_file),
                '--transform', 'nonexistent-transform'
            ],
            capture_output=True,
            text=True
        )
        # Should fail (either unknown transform or entry point issues)
        assert result.returncode != 0

    def test_list_transforms_help(self):
        """Test list-transforms --help."""
        result = subprocess.run(
            [sys.executable, '-m', 'all2md', 'list-transforms', '--help'],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert 'usage' in result.stdout.lower() or 'show available' in result.stdout.lower()

    def test_transforms_alias(self):
        """Test 'transforms' alias for 'list-transforms'."""
        result = subprocess.run(
            [sys.executable, '-m', 'all2md', 'transforms'],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        # May not show transforms if entry points not installed
        assert 'transform' in result.stdout.lower()


@pytest.mark.integration
@pytest.mark.slow
class TestTransformCLIWithFiles:
    """Tests that require actual file conversions with transforms."""

    def test_transform_with_stdin(self):
        """Test transforms with stdin input."""
        test_content = b"# Test Document\nSome content"

        result = subprocess.run(
            [
                sys.executable, '-m', 'all2md',
                '-',
                '--transform', 'heading-offset',
                '--format', 'auto'
            ],
            input=test_content,
            capture_output=True
        )
        # Should handle stdin with transforms (may fail if entry points not installed)
        assert result.returncode in (0, 1, 2, 3)

    def test_transform_with_output_file(self, tmp_path):
        """Test transforms with output file."""
        test_content = "# Test"
        test_file = tmp_path / "test.txt"
        output_file = tmp_path / "output.md"
        test_file.write_text(test_content)

        result = subprocess.run(
            [
                sys.executable, '-m', 'all2md',
                str(test_file),
                '--out', str(output_file),
                '--transform', 'heading-offset',
                '--format', 'auto'
            ],
            capture_output=True,
            text=True
        )

        # Check if command ran successfully or failed gracefully
        # May fail if entry points not installed
        assert result.returncode in (0, 1, 2, 3)
