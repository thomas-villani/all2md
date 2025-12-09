#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/utils/test_static_site.py
"""Tests for static site generator utilities."""

from datetime import datetime
from pathlib import Path

import yaml

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from all2md.ast.nodes import Document, Heading, Image, Paragraph, Text
from all2md.utils.static_site import (
    FrontmatterFormat,
    FrontmatterGenerator,
    ImageCollector,
    SiteScaffolder,
    StaticSiteGenerator,
    copy_document_assets,
    generate_output_filename,
)


def _parse_toml_frontmatter(text: str) -> dict:
    assert text.startswith("+++\n")
    assert text.endswith("+++\n\n")
    return tomllib.loads(text[4:-5])


def _parse_yaml_frontmatter(text: str) -> dict:
    assert text.startswith("---\n")
    assert text.endswith("---\n\n")
    return yaml.safe_load(text[4:-5]) or {}


class TestFrontmatterGenerator:
    """Tests for FrontmatterGenerator class."""

    def test_hugo_toml_format(self):
        """Test generating Hugo frontmatter in TOML format."""
        gen = FrontmatterGenerator(StaticSiteGenerator.HUGO, FrontmatterFormat.TOML)
        metadata = {
            "title": "Test Post",
            "author": "John Doe",
            "date": "2025-01-22",
            "tags": ["python", "coding"],
        }

        result = gen.generate(metadata)

        data = _parse_toml_frontmatter(result)

        assert data["title"] == "Test Post"
        assert data["author"] == "John Doe"
        assert data["date"].startswith("2025-01-22")
        assert data["tags"] == ["python", "coding"]
        assert data["draft"] is False

    def test_jekyll_yaml_format(self):
        """Test generating Jekyll frontmatter in YAML format."""
        gen = FrontmatterGenerator(StaticSiteGenerator.JEKYLL, FrontmatterFormat.YAML)
        metadata = {
            "title": "Test Post",
            "author": "Jane Doe",
            "creation_date": "2025-01-22T10:00:00",
            "categories": ["documentation", "api"],
        }

        result = gen.generate(metadata)

        data = _parse_yaml_frontmatter(result)

        assert data["title"] == "Test Post"
        assert data["author"] == "Jane Doe"
        assert data["date"].startswith("2025-01-22")
        assert data["layout"] == "post"
        assert data["categories"] == ["documentation", "api"]

    def test_taxonomy_from_keywords(self):
        """Test extracting taxonomy from keywords field."""
        gen = FrontmatterGenerator(StaticSiteGenerator.HUGO)
        metadata = {
            "title": "Post",
            "keywords": "python, testing, automation",
        }

        result = gen.generate(metadata)

        data = _parse_toml_frontmatter(result)
        assert data["tags"] == ["python", "testing", "automation"]

    def test_taxonomy_from_category_string(self):
        """Test extracting categories from category string."""
        gen = FrontmatterGenerator(StaticSiteGenerator.JEKYLL)
        metadata = {
            "title": "Post",
            "category": "documentation",
        }

        result = gen.generate(metadata)

        data = _parse_yaml_frontmatter(result)
        assert data["categories"] == ["documentation"]

    def test_description_from_subject(self):
        """Test using subject as description fallback."""
        gen = FrontmatterGenerator(StaticSiteGenerator.HUGO)
        metadata = {
            "title": "Post",
            "subject": "This is a test subject",
        }

        result = gen.generate(metadata)

        data = _parse_toml_frontmatter(result)
        assert data["description"] == "This is a test subject"

    def test_empty_metadata(self):
        """Test generating frontmatter with minimal metadata."""
        gen = FrontmatterGenerator(StaticSiteGenerator.HUGO)
        metadata = {}

        result = gen.generate(metadata)

        data = _parse_toml_frontmatter(result)
        assert data["draft"] is False

    def test_date_formatting(self):
        """Test date formatting in frontmatter."""
        gen = FrontmatterGenerator(StaticSiteGenerator.HUGO)
        dt = datetime(2025, 1, 22, 14, 30, 0)
        metadata = {
            "title": "Post",
            "creation_date": dt,
        }

        result = gen.generate(metadata)

        data = _parse_toml_frontmatter(result)
        assert data["date"].startswith("2025-01-22T14:30:00")

    def test_yaml_special_char_quoting(self):
        """Test YAML quoting for special characters."""
        gen = FrontmatterGenerator(StaticSiteGenerator.JEKYLL, FrontmatterFormat.YAML)
        metadata = {
            "title": "Post: With Colon",
        }

        result = gen.generate(metadata)

        data = _parse_yaml_frontmatter(result)
        assert data["title"] == "Post: With Colon"

    def test_toml_string_escaping(self):
        """Test TOML string escaping for quotes."""
        gen = FrontmatterGenerator(StaticSiteGenerator.HUGO, FrontmatterFormat.TOML)
        metadata = {
            "title": 'Post with "quotes"',
        }

        result = gen.generate(metadata)

        data = _parse_toml_frontmatter(result)
        assert data["title"] == 'Post with "quotes"'

    def test_hugo_weight_field(self):
        """Test Hugo-specific weight field."""
        gen = FrontmatterGenerator(StaticSiteGenerator.HUGO)
        metadata = {
            "title": "Post",
            "weight": 10,
        }

        result = gen.generate(metadata)

        data = _parse_toml_frontmatter(result)
        assert data["weight"] == 10

    def test_jekyll_permalink_field(self):
        """Test Jekyll-specific permalink field."""
        gen = FrontmatterGenerator(StaticSiteGenerator.JEKYLL)
        metadata = {
            "title": "Post",
            "permalink": "/custom/path/",
        }

        result = gen.generate(metadata)

        data = _parse_yaml_frontmatter(result)
        assert data["permalink"] == "/custom/path/"


class TestImageCollector:
    """Tests for ImageCollector visitor."""

    def test_collect_single_image(self):
        """Test collecting a single image from document."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Hello "),
                        Image(url="/path/to/image.png", alt_text="Test image"),
                        Text(content=" world"),
                    ]
                )
            ]
        )

        collector = ImageCollector()
        collector.collect(doc)

        assert len(collector.images) == 1
        assert collector.images[0].url == "/path/to/image.png"
        assert collector.images[0].alt_text == "Test image"

    def test_collect_multiple_images(self):
        """Test collecting multiple images from document."""
        doc = Document(
            children=[
                Paragraph(content=[Image(url="/image1.png", alt_text="Image 1")]),
                Heading(level=2, content=[Text(content="Section")]),
                Paragraph(content=[Image(url="/image2.jpg", alt_text="Image 2")]),
            ]
        )

        collector = ImageCollector()
        collector.collect(doc)

        assert len(collector.images) == 2
        assert collector.images[0].url == "/image1.png"
        assert collector.images[1].url == "/image2.jpg"

    def test_collect_no_images(self):
        """Test collecting from document with no images."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(content=[Text(content="Just text")]),
            ]
        )

        collector = ImageCollector()
        collector.collect(doc)

        assert len(collector.images) == 0


class TestGenerateOutputFilename:
    """Tests for generate_output_filename function."""

    def test_filename_from_title(self):
        """Test generating filename from document title."""
        source = Path("document.pdf")
        metadata = {"title": "My Great Post"}
        result = generate_output_filename(source, metadata, StaticSiteGenerator.HUGO)

        assert result == "my-great-post"

    def test_filename_from_source_stem(self):
        """Test generating filename from source file when no title."""
        source = Path("my-document.pdf")
        metadata = {}
        result = generate_output_filename(source, metadata, StaticSiteGenerator.HUGO)

        assert result == "my-document"

    def test_filename_fallback_to_index(self):
        """Test fallback to index-based filename."""
        source = Path("___")  # Stem that slugifies to empty (underscores become hyphens, then stripped)
        metadata = {}
        result = generate_output_filename(source, metadata, StaticSiteGenerator.HUGO, index=5)

        assert result == "document-5"

    def test_jekyll_date_prefix(self):
        """Test Jekyll filename with date prefix."""
        source = Path("document.pdf")
        metadata = {
            "title": "My Post",
            "creation_date": "2025-01-22T10:00:00",
        }
        result = generate_output_filename(source, metadata, StaticSiteGenerator.JEKYLL)

        assert result == "2025-01-22-my-post"

    def test_jekyll_without_date(self):
        """Test Jekyll filename without date."""
        source = Path("document.pdf")
        metadata = {"title": "My Post"}
        result = generate_output_filename(source, metadata, StaticSiteGenerator.JEKYLL)

        assert result == "my-post"

    def test_hugo_no_date_prefix(self):
        """Test Hugo filename doesn't include date prefix."""
        source = Path("document.pdf")
        metadata = {
            "title": "My Post",
            "creation_date": "2025-01-22",
        }
        result = generate_output_filename(source, metadata, StaticSiteGenerator.HUGO)

        assert result == "my-post"


class TestSiteScaffolder:
    """Tests for SiteScaffolder class."""

    def test_hugo_scaffold_creates_directories(self, tmp_path):
        """Test Hugo scaffolding creates expected directory structure."""
        scaffolder = SiteScaffolder(StaticSiteGenerator.HUGO)
        scaffolder.scaffold(tmp_path)

        assert (tmp_path / "content").exists()
        assert (tmp_path / "static" / "images").exists()
        assert (tmp_path / "themes").exists()
        assert (tmp_path / "layouts").exists()
        assert (tmp_path / "data").exists()

    def test_hugo_scaffold_creates_config(self, tmp_path):
        """Test Hugo scaffolding creates config.toml."""
        scaffolder = SiteScaffolder(StaticSiteGenerator.HUGO)
        scaffolder.scaffold(tmp_path)

        config_file = tmp_path / "config.toml"
        assert config_file.exists()

        content = config_file.read_text()
        assert "baseURL" in content
        assert "title" in content

    def test_hugo_scaffold_creates_index(self, tmp_path):
        """Test Hugo scaffolding creates content/_index.md."""
        scaffolder = SiteScaffolder(StaticSiteGenerator.HUGO)
        scaffolder.scaffold(tmp_path)

        index_file = tmp_path / "content" / "_index.md"
        assert index_file.exists()

        content = index_file.read_text()
        assert "+++" in content
        assert "title" in content

    def test_jekyll_scaffold_creates_directories(self, tmp_path):
        """Test Jekyll scaffolding creates expected directory structure."""
        scaffolder = SiteScaffolder(StaticSiteGenerator.JEKYLL)
        scaffolder.scaffold(tmp_path)

        assert (tmp_path / "_posts").exists()
        assert (tmp_path / "assets" / "images").exists()
        assert (tmp_path / "_layouts").exists()
        assert (tmp_path / "_includes").exists()

    def test_jekyll_scaffold_creates_config(self, tmp_path):
        """Test Jekyll scaffolding creates _config.yml."""
        scaffolder = SiteScaffolder(StaticSiteGenerator.JEKYLL)
        scaffolder.scaffold(tmp_path)

        config_file = tmp_path / "_config.yml"
        assert config_file.exists()

        content = config_file.read_text()
        assert "title:" in content
        assert "baseurl:" in content

    def test_jekyll_scaffold_creates_layouts(self, tmp_path):
        """Test Jekyll scaffolding creates layout templates."""
        scaffolder = SiteScaffolder(StaticSiteGenerator.JEKYLL)
        scaffolder.scaffold(tmp_path)

        default_layout = tmp_path / "_layouts" / "default.html"
        post_layout = tmp_path / "_layouts" / "post.html"

        assert default_layout.exists()
        assert post_layout.exists()

        # Check templates contain expected content
        default_content = default_layout.read_text()
        assert "<!DOCTYPE html>" in default_content
        assert "{{ content }}" in default_content

        post_content = post_layout.read_text()
        assert "{{ page.title }}" in post_content


class TestCopyDocumentAssets:
    """Tests for copy_document_assets function."""

    def test_copy_local_image(self, tmp_path):
        """Test copying a local image file to static directory."""
        # Create a source image file
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        image_file = source_dir / "test-image.png"
        image_file.write_bytes(b"fake image data")

        # Create document with image reference
        doc = Document(children=[Paragraph(content=[Image(url=str(image_file), alt_text="Test")])])

        # Copy assets
        output_dir = tmp_path / "site"
        modified_doc, assets = copy_document_assets(doc, output_dir, StaticSiteGenerator.HUGO, source_file=image_file)

        # Check static directory was created
        static_dir = output_dir / "static" / "images"
        assert static_dir.exists()

        # Check image was copied
        assert len(assets) == 1
        copied_file = Path(assets[0])
        assert copied_file.exists()
        assert copied_file.read_bytes() == b"fake image data"

        # Check image URL was updated
        collector = ImageCollector()
        collector.collect(modified_doc)
        assert len(collector.images) == 1
        assert collector.images[0].url == "/images/test-image.png"

    def test_skip_data_uri_images(self, tmp_path):
        """Test that data URI images are not copied."""
        doc = Document(
            children=[Paragraph(content=[Image(url="data:image/png;base64,iVBORw0K...", alt_text="Embedded")])]
        )

        output_dir = tmp_path / "site"
        modified_doc, assets = copy_document_assets(doc, output_dir, StaticSiteGenerator.HUGO)

        # Should not copy data URIs
        assert len(assets) == 0

    def test_skip_remote_url_images(self, tmp_path):
        """Test that remote HTTP URLs are not copied."""
        doc = Document(children=[Paragraph(content=[Image(url="https://example.com/image.png", alt_text="Remote")])])

        output_dir = tmp_path / "site"
        modified_doc, assets = copy_document_assets(doc, output_dir, StaticSiteGenerator.HUGO)

        # Should not copy remote URLs
        assert len(assets) == 0

    def test_jekyll_asset_paths(self, tmp_path):
        """Test Jekyll uses /assets/images/ path prefix."""
        # Create a source image file
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        image_file = source_dir / "test.jpg"
        image_file.write_bytes(b"test")

        # Create document
        doc = Document(children=[Paragraph(content=[Image(url=str(image_file), alt_text="Test")])])

        # Copy with Jekyll generator
        output_dir = tmp_path / "site"
        modified_doc, assets = copy_document_assets(doc, output_dir, StaticSiteGenerator.JEKYLL, source_file=image_file)

        # Check Jekyll path
        collector = ImageCollector()
        collector.collect(modified_doc)
        assert collector.images[0].url == "/assets/images/test.jpg"

        # Check file exists in Jekyll location
        jekyll_static = output_dir / "assets" / "images"
        assert jekyll_static.exists()
        assert (jekyll_static / "test.jpg").exists()
