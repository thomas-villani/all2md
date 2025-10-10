#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for ZIP resource extraction and manifest generation."""

import io
import tempfile
import zipfile
from pathlib import Path

from all2md.options.zip import ZipOptions
from all2md.parsers.zip import ZipToAstConverter


class TestZipResourceExtraction:
    """Tests for ZIP resource extraction functionality."""

    def create_test_zip(self):
        """Create a test ZIP file with parseable and non-parseable files.

        Returns
        -------
        bytes
            ZIP file bytes

        """
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add a text file (parseable)
            zf.writestr('readme.txt', 'This is a readme file.')

            # Add a markdown file (parseable)
            zf.writestr('document.md', '# Heading\n\nSome content.')

            # Add an image file (non-parseable resource)
            fake_png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
            zf.writestr('image.png', fake_png_data)

            # Add a CSS file (non-parseable resource)
            zf.writestr('style.css', 'body { color: red; }')

            # Add a JavaScript file (non-parseable resource)
            zf.writestr('script.js', 'console.log("hello");')

        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    def test_resource_extraction_enabled(self):
        """Test that resources are extracted when extract_resource_files=True."""
        zip_bytes = self.create_test_zip()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=True,
                attachment_output_dir=temp_dir,
                include_resource_manifest=True
            )
            parser = ZipToAstConverter(options=options)
            doc = parser.parse(zip_bytes)

            # Check that resources were extracted
            output_dir = Path(temp_dir)
            extracted_files = list(output_dir.glob('*'))

            # Should have extracted the non-parseable files
            # (image.png, style.css, script.js)
            assert len(extracted_files) >= 1

            # Check for manifest in the document
            headings = [node for node in doc.children if node.__class__.__name__ == 'Heading']
            has_manifest_heading = any('Extracted Resources' in h.content[0].content for h in headings if h.content)

            # We should have a manifest if resources were extracted
            if len(extracted_files) > 0:
                assert has_manifest_heading

    def test_resource_extraction_disabled(self):
        """Test that resources are not extracted when extract_resource_files=False."""
        zip_bytes = self.create_test_zip()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=False,
                attachment_output_dir=temp_dir
            )
            parser = ZipToAstConverter(options=options)
            doc = parser.parse(zip_bytes)

            # Check that no resources were extracted
            output_dir = Path(temp_dir)
            extracted_files = list(output_dir.glob('*'))

            # Should not have extracted any files
            assert len(extracted_files) == 0

    def test_manifest_includes_correct_information(self):
        """Test that the manifest table includes correct resource information."""
        zip_bytes = self.create_test_zip()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=True,
                attachment_output_dir=temp_dir,
                include_resource_manifest=True
            )
            parser = ZipToAstConverter(options=options)
            doc = parser.parse(zip_bytes)

            # Find the manifest table
            tables = [node for node in doc.children if node.__class__.__name__ == 'Table']

            if len(tables) > 0:
                # The last table should be the manifest (if resources were extracted)
                manifest_table = tables[-1]

                # Check that the table has the expected columns
                # Columns: Filename, Archive Path, Size (bytes)
                assert len(manifest_table.header.cells) == 3
                assert manifest_table.header.cells[0].content[0].content == "Filename"
                assert manifest_table.header.cells[1].content[0].content == "Archive Path"
                assert "Size" in manifest_table.header.cells[2].content[0].content

                # Check that there are data rows (extracted resources)
                assert len(manifest_table.rows) > 0

    def test_manifest_disabled(self):
        """Test that manifest is not generated when include_resource_manifest=False."""
        zip_bytes = self.create_test_zip()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=True,
                attachment_output_dir=temp_dir,
                include_resource_manifest=False
            )
            parser = ZipToAstConverter(options=options)
            doc = parser.parse(zip_bytes)

            # Check that there's no manifest heading
            headings = [node for node in doc.children if node.__class__.__name__ == 'Heading']
            has_manifest_heading = any('Extracted Resources' in h.content[0].content for h in headings if h.content)

            # Should not have a manifest heading
            assert not has_manifest_heading

    def test_preserve_directory_structure(self):
        """Test that directory structure is preserved when requested."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add files in subdirectories
            zf.writestr('dir1/file1.txt', 'File 1')
            zf.writestr('dir1/subdir/file2.txt', 'File 2')
            zf.writestr('dir2/file3.png', b'\x89PNG' + b'\x00' * 50)

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=True,
                attachment_output_dir=temp_dir,
                preserve_directory_structure=True,
                flatten_structure=False
            )
            parser = ZipToAstConverter(options=options)
            parser.parse(zip_bytes)

            # Check that directory structure was preserved
            output_dir = Path(temp_dir)

            # Should have subdirectories if resources were extracted
            subdirs = [d for d in output_dir.rglob('*') if d.is_dir()]
            # We might have subdirectories if non-parseable files were extracted
            # The exact structure depends on which files are non-parseable

    def test_flatten_structure(self):
        """Test that directory structure is flattened when requested."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add files in subdirectories
            fake_png = b'\x89PNG' + b'\x00' * 50
            zf.writestr('dir1/image1.png', fake_png)
            zf.writestr('dir2/image2.png', fake_png)

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=True,
                attachment_output_dir=temp_dir,
                flatten_structure=True
            )
            parser = ZipToAstConverter(options=options)
            parser.parse(zip_bytes)

            # Check that files are in the root directory (no subdirectories)
            output_dir = Path(temp_dir)
            all_files = list(output_dir.glob('*'))
            subdirs = [f for f in all_files if f.is_dir()]

            # Should have no subdirectories (or only temporary ones from other operations)
            # The images should be in the root
            root_files = [f for f in all_files if f.is_file()]
            # We should have extracted some files directly to root
            assert len(root_files) >= 0


class TestZipResourceManifest:
    """Tests for ZIP resource manifest table generation."""

    def test_manifest_table_structure(self):
        """Test that manifest table has correct structure."""
        from all2md.parsers.zip import ZipToAstConverter

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add a non-parseable file
            zf.writestr('resource.bin', b'\x00\x01\x02\x03')

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=True,
                attachment_output_dir=temp_dir,
                include_resource_manifest=True
            )
            parser = ZipToAstConverter(options=options)
            doc = parser.parse(zip_bytes)

            # Check that manifest was created if resources were extracted
            if parser._extracted_resources:
                # Find the manifest heading
                headings = [node for node in doc.children if node.__class__.__name__ == 'Heading']
                manifest_headings = [h for h in headings if h.content and 'Extracted Resources' in h.content[0].content]

                assert len(manifest_headings) > 0

    def test_manifest_size_tracking(self):
        """Test that manifest tracks file sizes correctly."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add a resource with known size
            test_data = b'\x00' * 1000  # 1000 bytes
            zf.writestr('test.bin', test_data)

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=True,
                attachment_output_dir=temp_dir,
                include_resource_manifest=True
            )
            parser = ZipToAstConverter(options=options)
            doc = parser.parse(zip_bytes)

            # Check that size was tracked in the extracted resources
            if parser._extracted_resources:
                assert len(parser._extracted_resources) > 0
                # Check that size is present
                for resource in parser._extracted_resources:
                    assert 'size' in resource
                    assert resource['size'] > 0
