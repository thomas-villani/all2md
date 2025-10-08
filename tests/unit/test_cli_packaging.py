"""Unit tests for CLI packaging features.

Tests for --zip, --assets-layout flags and packaging utilities.
"""

import zipfile

import pytest


class TestOrganizeAssets:
    """Test organize_assets function."""

    def test_organize_assets_flat_layout(self, tmp_path):
        """Test flat asset layout."""
        from all2md.cli.packaging import organize_assets

        # Create test structure
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        # Create some asset files
        (output_dir / "img1.png").write_bytes(b"image1")
        (output_dir / "img2.jpg").write_bytes(b"image2")

        # Create markdown files
        md_files = [output_dir / "doc1.md", output_dir / "doc2.md"]
        for md_file in md_files:
            md_file.write_text("# Test")

        # Organize with flat layout
        mapping = organize_assets(md_files, output_dir, layout="flat")

        # All assets should map to assets/ directory
        for _original, new_path in mapping.items():
            assert new_path.parent.name == "assets"
            assert new_path.parent.parent == output_dir

    def test_organize_assets_by_stem_layout(self, tmp_path):
        """Test by-stem asset layout."""
        from all2md.cli.packaging import organize_assets

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        # Create markdown files
        md_files = [output_dir / "doc1.md", output_dir / "doc2.md"]
        for md_file in md_files:
            md_file.write_text("# Test")

        # Create asset with matching stem
        (output_dir / "doc1_img.png").write_bytes(b"image1")

        # Organize with by-stem layout
        mapping = organize_assets(md_files, output_dir, layout="by-stem")

        # Assets should be organized by document stem
        for _original, new_path in mapping.items():
            # Should be in assets/{stem}/ directory
            assert "assets" in str(new_path)
            assert "doc1" in str(new_path) or "doc2" in str(new_path)

    def test_organize_assets_structured_layout(self, tmp_path):
        """Test structured asset layout preserves directory structure."""
        from all2md.cli.packaging import organize_assets

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        # Create subdirectory structure
        subdir = output_dir / "subdir"
        subdir.mkdir()

        # Create assets in subdirectory
        (subdir / "img1.png").write_bytes(b"image1")

        md_files = [output_dir / "doc.md"]
        md_files[0].write_text("# Test")

        # Organize with structured layout
        mapping = organize_assets(md_files, output_dir, layout="structured")

        # Should preserve relative paths
        for _original, new_path in mapping.items():
            # Path should be relative to output_dir
            try:
                rel_path = new_path.relative_to(output_dir)
                assert "subdir" in str(rel_path)
            except ValueError:
                # Asset outside output_dir, should be in assets/
                assert "assets" in str(new_path)

    def test_organize_assets_no_assets(self, tmp_path):
        """Test organize_assets with no assets."""
        from all2md.cli.packaging import organize_assets

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        md_files = [output_dir / "doc.md"]
        md_files[0].write_text("# Test")

        # No assets to organize
        mapping = organize_assets(md_files, output_dir, layout="flat")

        # Should return empty mapping
        assert len(mapping) == 0

    def test_organize_assets_name_conflicts(self, tmp_path):
        """Test that asset organization handles name conflicts."""
        from all2md.cli.packaging import organize_assets

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        # Create multiple assets with same name in different dirs
        subdir1 = output_dir / "dir1"
        subdir2 = output_dir / "dir2"
        subdir1.mkdir()
        subdir2.mkdir()

        (subdir1 / "img.png").write_bytes(b"image1")
        (subdir2 / "img.png").write_bytes(b"image2")

        md_files = [output_dir / "doc.md"]
        md_files[0].write_text("# Test")

        # Organize with flat layout (will cause conflicts)
        mapping = organize_assets(md_files, output_dir, layout="flat")

        # Should handle conflicts by renaming
        new_names = [p.name for p in mapping.values()]
        # Should have different names (one original, one with suffix)
        assert len(set(new_names)) == len(new_names)


class TestUpdateMarkdownAssetLinks:
    """Test update_markdown_asset_links function."""

    def test_update_markdown_image_links(self, tmp_path):
        """Test updating markdown image links."""
        from all2md.cli.packaging import update_markdown_asset_links

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        # Create original asset
        old_asset = output_dir / "img.png"
        old_asset.write_bytes(b"image")

        # Create markdown with image reference
        md_file = output_dir / "doc.md"
        md_file.write_text("![alt text](img.png)")

        # New location
        new_asset = output_dir / "assets" / "img.png"

        # Update links
        asset_mapping = {old_asset: new_asset}
        update_markdown_asset_links(md_file, asset_mapping, output_dir)

        # Check updated content
        updated_content = md_file.read_text()
        assert "assets/img.png" in updated_content or "assets\\img.png" in updated_content

    def test_update_html_image_links(self, tmp_path):
        """Test updating HTML image tags."""
        from all2md.cli.packaging import update_markdown_asset_links

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        old_asset = output_dir / "img.png"
        old_asset.write_bytes(b"image")

        md_file = output_dir / "doc.md"
        md_file.write_text('<img src="img.png" alt="test">')

        new_asset = output_dir / "assets" / "img.png"

        asset_mapping = {old_asset: new_asset}
        update_markdown_asset_links(md_file, asset_mapping, output_dir)

        updated_content = md_file.read_text()
        assert "assets" in updated_content

    def test_update_links_skips_external_urls(self, tmp_path):
        """Test that external URLs are not modified."""
        from all2md.cli.packaging import update_markdown_asset_links

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        md_file = output_dir / "doc.md"
        original_content = "![alt](https://example.com/img.png)"
        md_file.write_text(original_content)

        # Empty mapping
        asset_mapping = {}
        update_markdown_asset_links(md_file, asset_mapping, output_dir)

        # Content should be unchanged
        assert md_file.read_text() == original_content

    def test_update_links_skips_data_urls(self, tmp_path):
        """Test that data URLs are not modified."""
        from all2md.cli.packaging import update_markdown_asset_links

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        md_file = output_dir / "doc.md"
        original_content = "![alt](data:image/png;base64,iVBORw0KG...)"
        md_file.write_text(original_content)

        asset_mapping = {}
        update_markdown_asset_links(md_file, asset_mapping, output_dir)

        # Content should be unchanged
        assert md_file.read_text() == original_content


class TestCreateOutputZip:
    """Test create_output_zip function."""

    def test_create_zip_basic(self, tmp_path):
        """Test basic zip creation."""
        from all2md.cli.packaging import create_output_zip

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        # Create files
        (output_dir / "doc.md").write_text("# Test")
        (output_dir / "img.png").write_bytes(b"image")

        # Create zip
        zip_path = create_output_zip(output_dir)

        # Zip should be created
        assert zip_path.exists()
        assert zip_path.suffix == ".zip"

        # Check zip contents
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            assert "doc.md" in names
            assert "img.png" in names

    def test_create_zip_custom_path(self, tmp_path):
        """Test zip creation with custom path."""
        from all2md.cli.packaging import create_output_zip

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        (output_dir / "doc.md").write_text("# Test")

        custom_zip = tmp_path / "custom.zip"

        # Create zip with custom path
        zip_path = create_output_zip(output_dir, zip_path=custom_zip)

        assert zip_path == custom_zip
        assert custom_zip.exists()

    def test_create_zip_with_subdirectories(self, tmp_path):
        """Test zip preserves subdirectory structure."""
        from all2md.cli.packaging import create_output_zip

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        # Create subdirectory structure
        subdir = output_dir / "subdir"
        subdir.mkdir()

        (subdir / "doc.md").write_text("# Test")

        zip_path = create_output_zip(output_dir)

        # Check structure is preserved
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            # Should have relative path
            assert any("subdir" in name for name in names)

    def test_create_zip_nonexistent_dir_raises(self, tmp_path):
        """Test that nonexistent directory raises error."""
        from all2md.cli.packaging import create_output_zip

        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(ValueError, match="does not exist"):
            create_output_zip(nonexistent)

    def test_create_zip_specific_files(self, tmp_path):
        """Test creating zip with specific files only."""
        from all2md.cli.packaging import create_output_zip

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        md1 = output_dir / "doc1.md"
        md2 = output_dir / "doc2.md"
        md1.write_text("# Doc 1")
        md2.write_text("# Doc 2")

        # Create zip with only one file
        zip_path = create_output_zip(
            output_dir,
            markdown_files=[md1],
            asset_files=[]
        )

        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            assert "doc1.md" in names
            assert "doc2.md" not in names


class TestZipCLIIntegration:
    """Test --zip CLI flag integration."""

    def test_zip_flag_is_recognized(self, tmp_path):
        """Test that --zip flag is recognized by the parser."""
        from all2md.cli import create_parser

        parser = create_parser()

        # Should parse without error
        args = parser.parse_args([
            str(tmp_path / "test.txt"),
            '--output-dir', str(tmp_path / 'out'),
            '--zip'
        ])

        # Zip should be set
        assert hasattr(args, 'zip')
        assert args.zip == 'auto'  # default const value

    def test_zip_with_custom_path(self, tmp_path):
        """Test --zip with custom path."""
        from all2md.cli import create_parser

        parser = create_parser()
        custom_zip = str(tmp_path / "custom.zip")

        args = parser.parse_args([
            str(tmp_path / "test.txt"),
            '--output-dir', str(tmp_path / 'out'),
            '--zip', custom_zip
        ])

        assert args.zip == custom_zip

    def test_assets_layout_flag(self, tmp_path):
        """Test --assets-layout flag."""
        from all2md.cli import create_parser

        parser = create_parser()

        args = parser.parse_args([
            str(tmp_path / "test.txt"),
            '--output-dir', str(tmp_path / 'out'),
            '--assets-layout', 'by-stem'
        ])

        assert args.assets_layout == 'by-stem'

    def test_assets_layout_choices(self, tmp_path, capsys):
        """Test that --assets-layout validates choices."""
        from all2md.cli import main

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # Try invalid layout
        with pytest.raises(SystemExit):
            main([
                str(test_file),
                '--output-dir', str(tmp_path / 'out'),
                '--assets-layout', 'invalid'
            ])


@pytest.mark.integration
class TestPackagingIntegration:
    """Integration tests for packaging features."""

    def test_create_zip_from_directory(self, tmp_path):
        """Test creating zip from output directory directly."""
        from all2md.cli.packaging import create_output_zip

        # Create test output directory with files
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        (output_dir / "doc1.md").write_text("# Doc 1")
        (output_dir / "doc2.md").write_text("# Doc 2")

        # Create zip
        zip_path = create_output_zip(output_dir)

        # Verify
        assert zip_path.exists()
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            assert "doc1.md" in names
            assert "doc2.md" in names

    def test_organize_and_update_links(self, tmp_path):
        """Test asset organization and link updates."""
        from all2md.cli.packaging import organize_assets, update_markdown_asset_links

        output_dir = tmp_path / "out"
        output_dir.mkdir()

        # Create asset
        asset = output_dir / "image.png"
        asset.write_bytes(b"fake image")

        # Create markdown with reference
        md_file = output_dir / "doc.md"
        md_file.write_text("![alt](image.png)")

        # Organize assets
        mapping = organize_assets([md_file], output_dir, layout="flat")

        # Update links
        update_markdown_asset_links(md_file, mapping, output_dir)

        # Verify link was updated
        content = md_file.read_text()
        assert "assets" in content.lower()
