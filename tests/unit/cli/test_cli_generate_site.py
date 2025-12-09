"""Unit tests for the generate-site CLI command."""

from pathlib import Path

import pytest

from all2md.cli.commands.generate_site import handle_generate_site_command


@pytest.fixture
def sample_markdown_files(tmp_path: Path) -> list[Path]:
    """Create sample markdown files for testing."""
    files = []

    # Create multiple markdown files
    for i in range(3):
        path = tmp_path / f"doc{i + 1}.md"
        path.write_text(
            f"""---
title: Document {i + 1}
date: 2024-01-0{i + 1}
---

# Document {i + 1}

This is document {i + 1}.

## Section A

Content for section A.
""",
            encoding="utf-8",
        )
        files.append(path)

    return files


@pytest.fixture
def sample_text_file(tmp_path: Path) -> Path:
    """Create a sample text file for testing."""
    path = tmp_path / "sample.txt"
    path.write_text("This is a plain text file.\n\nWith multiple paragraphs.")
    return path


@pytest.mark.unit
class TestHandleGenerateSiteCommand:
    """Test handle_generate_site_command() function."""

    def test_help_returns_zero(self):
        """Test --help returns exit code 0."""
        result = handle_generate_site_command(["--help"])
        assert result == 0

    def test_missing_required_args(self):
        """Test error when required arguments are missing."""
        # Missing --output-dir and --generator
        result = handle_generate_site_command(["input.md"])
        assert result != 0

    def test_missing_generator(self, tmp_path: Path, sample_markdown_files):
        """Test error when --generator is missing."""
        output_dir = tmp_path / "site"
        result = handle_generate_site_command([str(sample_markdown_files[0]), "--output-dir", str(output_dir)])
        assert result != 0

    def test_missing_output_dir(self, sample_markdown_files):
        """Test error when --output-dir is missing."""
        result = handle_generate_site_command([str(sample_markdown_files[0]), "--generator", "hugo"])
        assert result != 0

    def test_hugo_basic(self, tmp_path: Path, sample_markdown_files):
        """Test basic Hugo site generation."""
        output_dir = tmp_path / "hugo_site"

        result = handle_generate_site_command(
            [str(sample_markdown_files[0]), "--output-dir", str(output_dir), "--generator", "hugo"]
        )

        assert result == 0
        assert output_dir.exists()
        # Check content directory was created
        content_dir = output_dir / "content"
        assert content_dir.exists()

    def test_jekyll_basic(self, tmp_path: Path, sample_markdown_files):
        """Test basic Jekyll site generation."""
        output_dir = tmp_path / "jekyll_site"

        result = handle_generate_site_command(
            [str(sample_markdown_files[0]), "--output-dir", str(output_dir), "--generator", "jekyll"]
        )

        assert result == 0
        assert output_dir.exists()
        # Check _posts directory was created
        posts_dir = output_dir / "_posts"
        assert posts_dir.exists()

    def test_hugo_scaffold(self, tmp_path: Path, sample_markdown_files):
        """Test Hugo site generation with scaffolding."""
        output_dir = tmp_path / "hugo_site"

        result = handle_generate_site_command(
            [str(sample_markdown_files[0]), "--output-dir", str(output_dir), "--generator", "hugo", "--scaffold"]
        )

        assert result == 0
        # Scaffolded site should have additional structure
        assert (output_dir / "content").exists()

    def test_jekyll_scaffold(self, tmp_path: Path, sample_markdown_files):
        """Test Jekyll site generation with scaffolding."""
        output_dir = tmp_path / "jekyll_site"

        result = handle_generate_site_command(
            [str(sample_markdown_files[0]), "--output-dir", str(output_dir), "--generator", "jekyll", "--scaffold"]
        )

        assert result == 0
        assert output_dir.exists()

    def test_multiple_input_files(self, tmp_path: Path, sample_markdown_files):
        """Test generating site from multiple files."""
        output_dir = tmp_path / "site"

        inputs = [str(f) for f in sample_markdown_files]
        result = handle_generate_site_command([*inputs, "--output-dir", str(output_dir), "--generator", "hugo"])

        assert result == 0
        # Should have content for all files
        content_dir = output_dir / "content"
        md_files = list(content_dir.glob("*.md"))
        assert len(md_files) >= len(sample_markdown_files)

    def test_frontmatter_format_yaml(self, tmp_path: Path, sample_markdown_files):
        """Test YAML frontmatter format."""
        output_dir = tmp_path / "site"

        result = handle_generate_site_command(
            [
                str(sample_markdown_files[0]),
                "--output-dir",
                str(output_dir),
                "--generator",
                "hugo",
                "--frontmatter-format",
                "yaml",
            ]
        )

        assert result == 0

    def test_frontmatter_format_toml(self, tmp_path: Path, sample_markdown_files):
        """Test TOML frontmatter format."""
        output_dir = tmp_path / "site"

        result = handle_generate_site_command(
            [
                str(sample_markdown_files[0]),
                "--output-dir",
                str(output_dir),
                "--generator",
                "hugo",
                "--frontmatter-format",
                "toml",
            ]
        )

        assert result == 0

    def test_content_subdir(self, tmp_path: Path, sample_markdown_files):
        """Test content subdirectory option."""
        output_dir = tmp_path / "site"

        result = handle_generate_site_command(
            [
                str(sample_markdown_files[0]),
                "--output-dir",
                str(output_dir),
                "--generator",
                "hugo",
                "--content-subdir",
                "posts",
            ]
        )

        assert result == 0
        # Content should be in subdirectory
        assert (output_dir / "content" / "posts").exists()

    def test_no_valid_input_files(self, tmp_path: Path, capsys):
        """Test error when no valid input files found."""
        output_dir = tmp_path / "site"

        result = handle_generate_site_command(
            [str(tmp_path / "nonexistent.md"), "--output-dir", str(output_dir), "--generator", "hugo"]
        )

        assert result != 0

    def test_recursive_directory(self, tmp_path: Path):
        """Test recursive directory processing."""
        # Create nested directory structure
        subdir = tmp_path / "docs" / "nested"
        subdir.mkdir(parents=True)

        file1 = tmp_path / "docs" / "doc1.md"
        file2 = subdir / "doc2.md"
        file1.write_text("# Doc 1")
        file2.write_text("# Doc 2")

        output_dir = tmp_path / "site"

        result = handle_generate_site_command(
            [str(tmp_path / "docs"), "--output-dir", str(output_dir), "--generator", "hugo", "--recursive"]
        )

        assert result == 0

    def test_exclude_pattern(self, tmp_path: Path, sample_markdown_files):
        """Test exclude pattern option."""
        output_dir = tmp_path / "site"

        # Create a file to exclude
        excluded = sample_markdown_files[0].parent / "excluded.md"
        excluded.write_text("# Should be excluded")

        result = handle_generate_site_command(
            [
                str(sample_markdown_files[0].parent),
                "--output-dir",
                str(output_dir),
                "--generator",
                "hugo",
                "--recursive",
                "--exclude",
                "excluded*.md",
            ]
        )

        assert result == 0

    def test_text_file_conversion(self, tmp_path: Path, sample_text_file):
        """Test converting non-markdown files."""
        output_dir = tmp_path / "site"

        result = handle_generate_site_command(
            [str(sample_text_file), "--output-dir", str(output_dir), "--generator", "hugo"]
        )

        assert result == 0
