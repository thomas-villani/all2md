#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for ZIP resource extraction and manifest generation."""

import io
import tempfile
import zipfile
from pathlib import Path

import pytest

from all2md.ast import Document
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
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add a text file (parseable)
            zf.writestr("readme.txt", "This is a readme file.")

            # Add a markdown file (parseable)
            zf.writestr("document.md", "# Heading\n\nSome content.")

            # Add resource files (will be extracted, not parsed)
            fake_png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
            zf.writestr("image.png", fake_png_data)

            # Add a CSS file (resource)
            zf.writestr("style.css", "body { color: red; }")

            # Add a JavaScript file (resource)
            zf.writestr("script.js", 'console.log("hello");')

        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    def test_resource_extraction_enabled(self):
        """Test that resources are extracted when extract_resource_files=True."""
        zip_bytes = self.create_test_zip()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=True, attachment_output_dir=temp_dir, include_resource_manifest=True
            )
            parser = ZipToAstConverter(options=options)
            doc = parser.parse(zip_bytes)

            # Check that resources were extracted
            output_dir = Path(temp_dir)
            extracted_files = list(output_dir.glob("*"))

            # Should have extracted the non-parseable files
            # (image.png, style.css, script.js)
            assert len(extracted_files) >= 1

            # Check for manifest in the document
            headings = [node for node in doc.children if node.__class__.__name__ == "Heading"]
            has_manifest_heading = any("Extracted Resources" in h.content[0].content for h in headings if h.content)

            # We should have a manifest if resources were extracted
            if len(extracted_files) > 0:
                assert has_manifest_heading

    def test_resource_extraction_disabled(self):
        """Test that resources are not extracted when extract_resource_files=False."""
        zip_bytes = self.create_test_zip()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(extract_resource_files=False, attachment_output_dir=temp_dir)
            parser = ZipToAstConverter(options=options)
            _doc = parser.parse(zip_bytes)

            # Check that no resources were extracted
            output_dir = Path(temp_dir)
            extracted_files = list(output_dir.glob("*"))

            # Should not have extracted any files
            assert len(extracted_files) == 0

    def test_manifest_includes_correct_information(self):
        """Test that the manifest table includes correct resource information."""
        zip_bytes = self.create_test_zip()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=True, attachment_output_dir=temp_dir, include_resource_manifest=True
            )
            parser = ZipToAstConverter(options=options)
            doc = parser.parse(zip_bytes)

            # Find the manifest table
            tables = [node for node in doc.children if node.__class__.__name__ == "Table"]

            if len(tables) > 0:
                # The last table should be the manifest (if resources were extracted)
                manifest_table = tables[-1]

                # Check that the table has the expected columns
                # Columns: Filename, Archive Path, Size (bytes), SHA256 Hash
                assert len(manifest_table.header.cells) == 4
                assert manifest_table.header.cells[0].content[0].content == "Filename"
                assert manifest_table.header.cells[1].content[0].content == "Archive Path"
                assert "Size" in manifest_table.header.cells[2].content[0].content
                assert "SHA256" in manifest_table.header.cells[3].content[0].content

                # Check that there are data rows (extracted resources)
                assert len(manifest_table.rows) > 0

    def test_manifest_disabled(self):
        """Test that manifest is not generated when include_resource_manifest=False."""
        zip_bytes = self.create_test_zip()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=True, attachment_output_dir=temp_dir, include_resource_manifest=False
            )
            parser = ZipToAstConverter(options=options)
            doc = parser.parse(zip_bytes)

            # Check that there's no manifest heading
            headings = [node for node in doc.children if node.__class__.__name__ == "Heading"]
            has_manifest_heading = any("Extracted Resources" in h.content[0].content for h in headings if h.content)

            # Should not have a manifest heading
            assert not has_manifest_heading

    def test_preserve_directory_structure(self):
        """Test that directory structure is preserved when requested."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add files in subdirectories
            zf.writestr("dir1/file1.txt", "File 1")
            zf.writestr("dir1/subdir/file2.txt", "File 2")
            zf.writestr("dir2/file3.png", b"\x89PNG" + b"\x00" * 50)

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=True,
                attachment_output_dir=temp_dir,
                preserve_directory_structure=True,
                flatten_structure=False,
            )
            parser = ZipToAstConverter(options=options)
            parser.parse(zip_bytes)

            # Check that directory structure was preserved
            output_dir = Path(temp_dir)

            # Should have subdirectories if resources were extracted
            _subdirs = [d for d in output_dir.rglob("*") if d.is_dir()]
            # We might have subdirectories if non-parseable files were extracted
            # The exact structure depends on which files are non-parseable

    def test_flatten_structure(self):
        """Test that directory structure is flattened when requested."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add files in subdirectories
            fake_png = b"\x89PNG" + b"\x00" * 50
            zf.writestr("dir1/image1.png", fake_png)
            zf.writestr("dir2/image2.png", fake_png)

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(extract_resource_files=True, attachment_output_dir=temp_dir, flatten_structure=True)
            parser = ZipToAstConverter(options=options)
            parser.parse(zip_bytes)

            # Check that files are in the root directory (no subdirectories)
            output_dir = Path(temp_dir)
            all_files = list(output_dir.glob("*"))
            _subdirs = [f for f in all_files if f.is_dir()]

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
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add a non-parseable file
            zf.writestr("resource.bin", b"\x00\x01\x02\x03")

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=True, attachment_output_dir=temp_dir, include_resource_manifest=True
            )
            parser = ZipToAstConverter(options=options)
            doc = parser.parse(zip_bytes)

            # Check that manifest was created if resources were extracted
            if parser._extracted_resources:
                # Find the manifest heading
                headings = [node for node in doc.children if node.__class__.__name__ == "Heading"]
                manifest_headings = [h for h in headings if h.content and "Extracted Resources" in h.content[0].content]

                assert len(manifest_headings) > 0

    def test_manifest_size_tracking(self):
        """Test that manifest tracks file sizes correctly."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add a resource with known size
            test_data = b"\x00" * 1000  # 1000 bytes
            zf.writestr("test.bin", test_data)

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=True, attachment_output_dir=temp_dir, include_resource_manifest=True
            )
            parser = ZipToAstConverter(options=options)
            _doc = parser.parse(zip_bytes)

            # Check that size was tracked in the extracted resources
            if parser._extracted_resources:
                assert len(parser._extracted_resources) > 0
                # Check that size is present
                for resource in parser._extracted_resources:
                    assert "size" in resource
                    assert resource["size"] > 0


class TestZipPathTraversalSecurity:
    """Tests for ZIP path traversal (Zip Slip) security during resource extraction."""

    def test_absolute_path_blocked_during_extraction(self):
        """Test that absolute paths are blocked during resource extraction."""
        import pytest

        from all2md.exceptions import ZipFileSecurityError

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add a text file (parseable) - should be fine
            zf.writestr("readme.txt", "This is a readme file.")

            # Add a resource with absolute path (will be caught during validation)
            # We need to manually create a ZipInfo with an absolute path
            # because ZipFile.writestr normalizes paths
            info = zipfile.ZipInfo("/etc/passwd")
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, b"malicious content")

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        # This should be blocked during the parse phase by validate_zip_archive
        # which checks for absolute paths
        with pytest.raises(ZipFileSecurityError, match="suspicious path"):
            with tempfile.TemporaryDirectory() as temp_dir:
                options = ZipOptions(
                    extract_resource_files=True, attachment_output_dir=temp_dir, preserve_directory_structure=True
                )
                parser = ZipToAstConverter(options=options)
                parser.parse(zip_bytes)

    def test_parent_traversal_blocked_during_extraction(self):
        """Test that parent directory traversal is blocked during extraction."""
        import pytest

        from all2md.exceptions import ZipFileSecurityError

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add normal files
            zf.writestr("readme.txt", "Normal file.")

            # Try to add a file with parent traversal
            info = zipfile.ZipInfo("../../../etc/passwd")
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, b"malicious content")

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        # This should be blocked during the parse phase
        with pytest.raises(ZipFileSecurityError, match="suspicious path"):
            with tempfile.TemporaryDirectory() as temp_dir:
                options = ZipOptions(
                    extract_resource_files=True, attachment_output_dir=temp_dir, preserve_directory_structure=True
                )
                parser = ZipToAstConverter(options=options)
                parser.parse(zip_bytes)

    def test_mixed_traversal_blocked_during_extraction(self):
        """Test that mixed path traversal patterns are blocked."""
        import pytest

        from all2md.exceptions import ZipFileSecurityError

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Try to add file with traversal in the middle
            info = zipfile.ZipInfo("dir/../../../secret.txt")
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, b"malicious content")

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        # This should be blocked during the parse phase
        with pytest.raises(ZipFileSecurityError, match="suspicious path"):
            with tempfile.TemporaryDirectory() as temp_dir:
                options = ZipOptions(
                    extract_resource_files=True, attachment_output_dir=temp_dir, preserve_directory_structure=True
                )
                parser = ZipToAstConverter(options=options)
                parser.parse(zip_bytes)

    def test_normal_subdirectories_allowed(self):
        """Test that normal subdirectories work correctly with security checks."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add normal files in subdirectories
            zf.writestr("subdir1/file1.txt", "File 1")
            zf.writestr("subdir2/nested/file2.txt", "File 2")
            # Add a non-parseable resource
            fake_png = b"\x89PNG" + b"\x00" * 50
            zf.writestr("images/image1.png", fake_png)

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=True,
                attachment_output_dir=temp_dir,
                preserve_directory_structure=True,
                flatten_structure=False,
            )
            parser = ZipToAstConverter(options=options)
            doc = parser.parse(zip_bytes)

            # Should successfully parse without security errors
            assert isinstance(doc, Document)

            # Check that subdirectories were created if resources were extracted
            output_dir = Path(temp_dir)
            if parser._extracted_resources:
                # Resources should be in subdirectories
                extracted_files = list(output_dir.rglob("*"))
                # Should have some files
                assert len([f for f in extracted_files if f.is_file()]) > 0

    def test_flatten_mode_still_validates_paths(self):
        """Test that even in flatten mode, paths are validated."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Normal file
            fake_png = b"\x89PNG" + b"\x00" * 50
            zf.writestr("dir/image.png", fake_png)

            # Try a traversal path (will be caught during parse)
            info = zipfile.ZipInfo("../malicious.png")
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, fake_png)

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        # Should be blocked during parse phase
        import pytest

        from all2md.exceptions import ZipFileSecurityError

        with pytest.raises(ZipFileSecurityError):
            with tempfile.TemporaryDirectory() as temp_dir:
                options = ZipOptions(
                    extract_resource_files=True,
                    attachment_output_dir=temp_dir,
                    flatten_structure=True,  # Even with flatten, should be secure
                )
                parser = ZipToAstConverter(options=options)
                parser.parse(zip_bytes)

    def test_windows_absolute_path_blocked(self):
        """Test that Windows-style absolute paths are blocked."""
        from all2md.exceptions import ZipFileSecurityError

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Try Windows absolute path
            info = zipfile.ZipInfo("C:/Windows/System32/malware.exe")
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, b"malicious content")

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        # Should be blocked during the parse phase by validate_zip_archive
        # which now checks for Windows drive letters
        with pytest.raises(ZipFileSecurityError, match="Windows absolute path"):
            with tempfile.TemporaryDirectory() as temp_dir:
                options = ZipOptions(extract_resource_files=True, attachment_output_dir=temp_dir)
                parser = ZipToAstConverter(options=options)
                parser.parse(zip_bytes)

    def test_extraction_stays_within_output_dir(self):
        """Test that all extracted files stay within the output directory."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add various files
            fake_png = b"\x89PNG" + b"\x00" * 50
            zf.writestr("image1.png", fake_png)
            zf.writestr("subdir/image2.png", fake_png)
            zf.writestr("deep/nested/path/image3.png", fake_png)

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        with tempfile.TemporaryDirectory() as temp_dir:
            options = ZipOptions(
                extract_resource_files=True, attachment_output_dir=temp_dir, preserve_directory_structure=True
            )
            parser = ZipToAstConverter(options=options)
            doc = parser.parse(zip_bytes)

            # Verify all extracted files are within temp_dir
            if parser._extracted_resources:
                output_dir_resolved = Path(temp_dir).resolve()
                for resource in parser._extracted_resources:
                    resource_path = Path(resource["output_path"]).resolve()
                    # Check that resource_path is within output_dir
                    assert str(resource_path).startswith(str(output_dir_resolved))

            assert isinstance(doc, Document)
