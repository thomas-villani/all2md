"""End-to-end tests for all2md generate-site CLI command.

This module tests the generate-site subcommand as a subprocess, verifying
Hugo and Jekyll site generation with various options.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from tests.utils import MINIMAL_PNG_BYTES, cleanup_test_dir, create_test_temp_dir


@pytest.mark.e2e
@pytest.mark.cli
@pytest.mark.slow
class TestGenerateSiteCLI:
    """End-to-end tests for generate-site CLI command."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = create_test_temp_dir()
        self.source_dir = self.temp_dir / "source"
        self.source_dir.mkdir()

    def teardown_method(self):
        """Clean up test environment."""
        cleanup_test_dir(self.temp_dir)

    def _run_cli(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run the CLI as a subprocess.

        Parameters
        ----------
        args : list[str]
            Command line arguments to pass to the CLI

        Returns
        -------
        subprocess.CompletedProcess
            Result of the subprocess execution

        """
        cmd = [sys.executable, "-m", "all2md", "generate-site"] + args
        return subprocess.run(cmd, capture_output=True, text=True, cwd=self.temp_dir)

    def _create_test_markdown(self, filename: str, with_metadata: bool = True, with_image: bool = False) -> Path:
        """Create a test markdown file.

        Parameters
        ----------
        filename : str
            Name of the file to create
        with_metadata : bool
            Whether to include frontmatter metadata
        with_image : bool
            Whether to include an image reference

        Returns
        -------
        Path
            Path to the created file

        """
        content_parts = []

        if with_metadata:
            content_parts.append(
                """---
title: Test Document
author: Test Author
creation_date: 2025-01-22T10:00:00
keywords: test, example, tutorial
description: A test document for static site generation
---
"""
            )

        content_parts.append(
            """# Test Document

This is a test document for the generate-site command.

## Section 1

Some content here with **bold** and *italic* text.

## Section 2

- Bullet point 1
- Bullet point 2
- Bullet point 3
"""
        )

        if with_image:
            content_parts.append("\n![Test Image](./images/test.png)\n")

        file_path = self.source_dir / filename
        file_path.write_text("".join(content_parts), encoding="utf-8")
        return file_path

    def _create_test_image(self) -> Path:
        """Create a test image file.

        Returns
        -------
        Path
            Path to the created image

        """
        images_dir = self.source_dir / "images"
        images_dir.mkdir(exist_ok=True)
        image_path = images_dir / "test.png"
        image_path.write_bytes(MINIMAL_PNG_BYTES)
        return image_path

    # Hugo Tests
    # ----------

    def test_hugo_with_scaffolding(self):
        """Test generating a Hugo site with scaffolding."""
        # Create test file
        self._create_test_markdown("test.md")

        output_dir = self.temp_dir / "hugo-site"

        # Run generate-site
        result = self._run_cli(
            [
                str(self.source_dir / "test.md"),
                "--output-dir",
                str(output_dir),
                "--generator",
                "hugo",
                "--scaffold",
            ]
        )

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Verify directory structure
        assert (output_dir / "config.toml").exists(), "config.toml not created"
        assert (output_dir / "content").exists(), "content directory not created"
        assert (output_dir / "content" / "_index.md").exists(), "_index.md not created"
        assert (output_dir / "static" / "images").exists(), "static/images directory not created"
        assert (output_dir / "themes").exists(), "themes directory not created"
        assert (output_dir / "layouts").exists(), "layouts directory not created"
        assert (output_dir / "data").exists(), "data directory not created"

        # Verify content file exists (filename is slugified from title: "Test Document" -> "test-document.md")
        assert (output_dir / "content" / "test-document.md").exists(), "Converted file not created"

        # Verify config.toml contents
        config_content = (output_dir / "config.toml").read_text()
        assert "baseURL" in config_content
        assert "title" in config_content

        # Verify converted file has TOML frontmatter (Hugo default)
        content = (output_dir / "content" / "test-document.md").read_text()
        assert content.startswith("+++"), "TOML frontmatter delimiter not found"
        assert 'title = "Test Document"' in content
        assert 'author = "Test Author"' in content
        assert "draft = false" in content

    def test_hugo_without_scaffolding(self):
        """Test generating a Hugo site without scaffolding."""
        # Create test file
        self._create_test_markdown("test.md")

        output_dir = self.temp_dir / "hugo-content"

        # Run generate-site
        result = self._run_cli(
            [
                str(self.source_dir / "test.md"),
                "--output-dir",
                str(output_dir),
                "--generator",
                "hugo",
            ]
        )

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Verify only content and static directories exist
        assert (output_dir / "content").exists(), "content directory not created"
        assert (output_dir / "static" / "images").exists(), "static/images directory not created"

        # Verify scaffolding files do NOT exist
        assert not (output_dir / "config.toml").exists(), "config.toml should not be created"
        assert not (output_dir / "themes").exists(), "themes directory should not be created"
        assert not (output_dir / "layouts").exists(), "layouts directory should not be created"

        # Verify content file exists (slugified from title)
        assert (output_dir / "content" / "test-document.md").exists(), "Converted file not created"

    def test_hugo_with_yaml_frontmatter(self):
        """Test generating a Hugo site with YAML frontmatter override."""
        # Create test file
        self._create_test_markdown("test.md")

        output_dir = self.temp_dir / "hugo-yaml"

        # Run generate-site with YAML format
        result = self._run_cli(
            [
                str(self.source_dir / "test.md"),
                "--output-dir",
                str(output_dir),
                "--generator",
                "hugo",
                "--frontmatter-format",
                "yaml",
            ]
        )

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Verify YAML frontmatter (check slugified filename)
        content = (output_dir / "content" / "test-document.md").read_text()
        assert content.startswith("---"), "YAML frontmatter delimiter not found"
        assert "title: Test Document" in content or 'title: "Test Document"' in content
        assert "draft: false" in content

    def test_hugo_with_images(self):
        """Test Hugo site generation with image copying."""
        # Create test file with image and actual image file
        self._create_test_image()
        self._create_test_markdown("test.md", with_image=True)

        output_dir = self.temp_dir / "hugo-images"

        # Run generate-site
        result = self._run_cli(
            [
                str(self.source_dir / "test.md"),
                "--output-dir",
                str(output_dir),
                "--generator",
                "hugo",
            ]
        )

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Verify image was copied to static/images
        assert (output_dir / "static" / "images" / "test.png").exists(), "Image not copied"

        # Verify image reference was updated (check slugified filename)
        content = (output_dir / "content" / "test-document.md").read_text()
        assert "![Test Image](/images/test.png)" in content, "Image path not updated"

    def test_hugo_content_subdirectory(self):
        """Test Hugo site with content subdirectory option."""
        # Create test file
        self._create_test_markdown("test.md")

        output_dir = self.temp_dir / "hugo-subdir"

        # Run generate-site with content-subdir
        result = self._run_cli(
            [
                str(self.source_dir / "test.md"),
                "--output-dir",
                str(output_dir),
                "--generator",
                "hugo",
                "--content-subdir",
                "posts",
            ]
        )

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Verify file is in content/posts subdirectory (slugified filename)
        assert (output_dir / "content" / "posts" / "test-document.md").exists(), "File not in subdirectory"

    # Jekyll Tests
    # ------------

    def test_jekyll_with_scaffolding(self):
        """Test generating a Jekyll site with scaffolding."""
        # Create test file
        self._create_test_markdown("test.md")

        output_dir = self.temp_dir / "jekyll-site"

        # Run generate-site
        result = self._run_cli(
            [
                str(self.source_dir / "test.md"),
                "--output-dir",
                str(output_dir),
                "--generator",
                "jekyll",
                "--scaffold",
            ]
        )

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Verify directory structure
        assert (output_dir / "_config.yml").exists(), "_config.yml not created"
        assert (output_dir / "_posts").exists(), "_posts directory not created"
        assert (output_dir / "assets" / "images").exists(), "assets/images directory not created"
        assert (output_dir / "_layouts").exists(), "_layouts directory not created"
        assert (output_dir / "_layouts" / "default.html").exists(), "default.html layout not created"
        assert (output_dir / "_layouts" / "post.html").exists(), "post.html layout not created"
        assert (output_dir / "_includes").exists(), "_includes directory not created"

        # Verify _config.yml contents
        config_content = (output_dir / "_config.yml").read_text()
        assert "title:" in config_content
        assert "baseurl:" in config_content

        # Verify layout template contents
        default_layout = (output_dir / "_layouts" / "default.html").read_text()
        assert "<!DOCTYPE html>" in default_layout
        assert "{{ content }}" in default_layout

    def test_jekyll_without_scaffolding(self):
        """Test generating a Jekyll site without scaffolding."""
        # Create test file
        self._create_test_markdown("test.md")

        output_dir = self.temp_dir / "jekyll-content"

        # Run generate-site
        result = self._run_cli(
            [
                str(self.source_dir / "test.md"),
                "--output-dir",
                str(output_dir),
                "--generator",
                "jekyll",
            ]
        )

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Verify only _posts and assets directories exist
        assert (output_dir / "_posts").exists(), "_posts directory not created"
        assert (output_dir / "assets" / "images").exists(), "assets/images directory not created"

        # Verify scaffolding files do NOT exist
        assert not (output_dir / "_config.yml").exists(), "_config.yml should not be created"
        assert not (output_dir / "_layouts").exists(), "_layouts directory should not be created"

    def test_jekyll_date_prefixed_filename(self):
        """Test Jekyll generates date-prefixed filenames."""
        # Create test file with date metadata
        self._create_test_markdown("welcome.md")

        output_dir = self.temp_dir / "jekyll-dates"

        # Run generate-site
        result = self._run_cli(
            [
                str(self.source_dir / "welcome.md"),
                "--output-dir",
                str(output_dir),
                "--generator",
                "jekyll",
            ]
        )

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Verify date-prefixed filename exists (title "Test Document" → "test-document")
        assert (output_dir / "_posts" / "2025-01-22-test-document.md").exists(), "Date-prefixed file not created"

        # Verify YAML frontmatter
        content = (output_dir / "_posts" / "2025-01-22-test-document.md").read_text()
        assert content.startswith("---"), "YAML frontmatter delimiter not found"
        assert "layout: post" in content

    def test_jekyll_with_toml_frontmatter(self):
        """Test generating a Jekyll site with TOML frontmatter override."""
        # Create test file
        self._create_test_markdown("test.md")

        output_dir = self.temp_dir / "jekyll-toml"

        # Run generate-site with TOML format
        result = self._run_cli(
            [
                str(self.source_dir / "test.md"),
                "--output-dir",
                str(output_dir),
                "--generator",
                "jekyll",
                "--frontmatter-format",
                "toml",
            ]
        )

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Find the generated file (may have date prefix)
        posts_dir = output_dir / "_posts"
        generated_files = list(posts_dir.glob("*.md"))
        assert len(generated_files) == 1, f"Expected 1 file, found {len(generated_files)}"

        # Verify TOML frontmatter
        content = generated_files[0].read_text()
        assert content.startswith("+++"), "TOML frontmatter delimiter not found"
        assert 'layout = "post"' in content

    def test_jekyll_with_images(self):
        """Test Jekyll site generation with image copying."""
        # Create test file with image and actual image file
        self._create_test_image()
        self._create_test_markdown("test.md", with_image=True)

        output_dir = self.temp_dir / "jekyll-images"

        # Run generate-site
        result = self._run_cli(
            [
                str(self.source_dir / "test.md"),
                "--output-dir",
                str(output_dir),
                "--generator",
                "jekyll",
            ]
        )

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Verify image was copied to assets/images
        assert (output_dir / "assets" / "images" / "test.png").exists(), "Image not copied"

        # Verify image reference was updated to Jekyll path
        posts_dir = output_dir / "_posts"
        generated_files = list(posts_dir.glob("*.md"))
        content = generated_files[0].read_text()
        assert "![Test Image](/assets/images/test.png)" in content, "Image path not updated to Jekyll format"

    # Options Tests
    # -------------

    def test_recursive_processing(self):
        """Test recursive directory processing."""
        # Create nested directory structure
        subdir = self.source_dir / "subdir"
        subdir.mkdir()

        self._create_test_markdown("root.md")
        (subdir / "nested.md").write_text(
            """---
title: Nested Document
---

# Nested Document

Content in subdirectory.
""",
            encoding="utf-8",
        )

        output_dir = self.temp_dir / "hugo-recursive"

        # Run generate-site with --recursive
        result = self._run_cli(
            [
                str(self.source_dir),
                "--output-dir",
                str(output_dir),
                "--generator",
                "hugo",
                "--recursive",
            ]
        )

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Verify both files were converted (slugified filenames)
        # "root.md" with "Test Document" title → "test-document.md"
        # "nested.md" with "Nested Document" title → "nested-document.md"
        assert (output_dir / "content" / "test-document.md").exists(), "Root file not converted"
        assert (output_dir / "content" / "nested-document.md").exists(), "Nested file not converted"

    def test_file_exclusion(self):
        """Test file exclusion patterns."""
        # Create multiple files
        self._create_test_markdown("include.md")
        self._create_test_markdown("draft-test.md")
        (self.source_dir / "README.md").write_text("# README\n\nDo not convert.", encoding="utf-8")

        output_dir = self.temp_dir / "hugo-exclude"

        # Run generate-site with exclusions
        result = self._run_cli(
            [
                str(self.source_dir),
                "--output-dir",
                str(output_dir),
                "--generator",
                "hugo",
                "--recursive",
                "--exclude",
                "draft-*",
                "--exclude",
                "README.md",
            ]
        )

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Verify only include.md was converted (slugified as "test-document.md")
        assert (output_dir / "content" / "test-document.md").exists(), "include.md not converted"
        # Check that excluded files don't exist
        content_files = list((output_dir / "content").glob("*.md"))
        assert len(content_files) == 1, f"Expected 1 file, found {len(content_files)}: {content_files}"

    def test_multiple_files(self):
        """Test converting multiple files at once."""
        # Create multiple files
        self._create_test_markdown("file1.md")
        self._create_test_markdown("file2.md")
        self._create_test_markdown("file3.md")

        output_dir = self.temp_dir / "hugo-multi"

        # Run generate-site with multiple inputs
        result = self._run_cli(
            [
                str(self.source_dir / "file1.md"),
                str(self.source_dir / "file2.md"),
                str(self.source_dir / "file3.md"),
                "--output-dir",
                str(output_dir),
                "--generator",
                "hugo",
            ]
        )

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Verify all files were converted (all have same title, so slugified to "test-document.md" with suffixes)
        content_files = list((output_dir / "content").glob("*.md"))
        assert len(content_files) == 3, f"Expected 3 files, found {len(content_files)}"

    # Edge Cases
    # ----------

    def test_document_without_metadata(self):
        """Test converting a document without frontmatter metadata."""
        # Create markdown without metadata
        file_path = self.source_dir / "no-metadata.md"
        file_path.write_text(
            """# Simple Document

This document has no frontmatter metadata.
""",
            encoding="utf-8",
        )

        output_dir = self.temp_dir / "hugo-no-meta"

        # Run generate-site
        result = self._run_cli(
            [
                str(file_path),
                "--output-dir",
                str(output_dir),
                "--generator",
                "hugo",
            ]
        )

        # Check process succeeded
        assert result.returncode == 0, f"CLI failed with stderr: {result.stderr}"

        # Verify file was created (filename from source file: "no-metadata.md")
        content_files = list((output_dir / "content").glob("*.md"))
        assert (
            len(content_files) == 1
        ), f"Expected 1 file, found {len(content_files)}: {[f.name for f in content_files]}"

        content = content_files[0].read_text()
        assert content.startswith("+++")
        # Minimum frontmatter should have draft field
        assert "draft = false" in content

    def test_taxonomy_extraction(self):
        """Test that tags/categories are extracted from keywords/category metadata."""
        # Create file with keywords
        file_path = self.source_dir / "taxonomy.md"
        file_path.write_text(
            """---
title: Test Taxonomy
keywords: python, programming, advanced, tips
category: tutorial
---

# Test Document
""",
            encoding="utf-8",
        )

        # Test Hugo (should extract tags)
        hugo_dir = self.temp_dir / "hugo-taxonomy"
        result = self._run_cli(
            [
                str(file_path),
                "--output-dir",
                str(hugo_dir),
                "--generator",
                "hugo",
            ]
        )
        assert result.returncode == 0

        # "Test Taxonomy" → "test-taxonomy.md"
        hugo_content = (hugo_dir / "content" / "test-taxonomy.md").read_text()
        # Tags should be extracted from keywords (may be as comma-separated string or list)
        assert "tags =" in hugo_content
        assert "python" in hugo_content

        # Test Jekyll (should extract categories)
        jekyll_dir = self.temp_dir / "jekyll-taxonomy"
        result = self._run_cli(
            [
                str(file_path),
                "--output-dir",
                str(jekyll_dir),
                "--generator",
                "jekyll",
            ]
        )
        assert result.returncode == 0

        # Find the generated file (may have date prefix if metadata has a date)
        jekyll_files = list((jekyll_dir / "_posts").glob("*.md"))
        assert len(jekyll_files) == 1, f"Expected 1 file, found {len(jekyll_files)}"
        jekyll_content = jekyll_files[0].read_text()
        assert "categories:" in jekyll_content
        assert "- tutorial" in jekyll_content

    def test_invalid_generator(self):
        """Test that invalid generator option fails gracefully."""
        self._create_test_markdown("test.md")
        output_dir = self.temp_dir / "invalid"

        result = self._run_cli(
            [
                str(self.source_dir / "test.md"),
                "--output-dir",
                str(output_dir),
                "--generator",
                "invalid",
            ]
        )

        # Should fail with non-zero return code
        assert result.returncode != 0
        assert "invalid" in result.stderr.lower() or "choice" in result.stderr.lower()

    def test_missing_required_arguments(self):
        """Test that missing required arguments fails gracefully."""
        self._create_test_markdown("test.md")

        # Missing --generator
        result = self._run_cli(
            [
                str(self.source_dir / "test.md"),
                "--output-dir",
                str(self.temp_dir / "output"),
            ]
        )
        assert result.returncode != 0

        # Missing --output-dir
        result = self._run_cli(
            [
                str(self.source_dir / "test.md"),
                "--generator",
                "hugo",
            ]
        )
        assert result.returncode != 0
