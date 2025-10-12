#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/zip.py
"""ZIP archive parser that converts archive contents to AST representation.

This module provides the ZipToAstConverter class that extracts files from ZIP
archives, converts parseable files to AST, and handles resource files.
"""

from __future__ import annotations

import fnmatch
import io
import logging
import os
import zipfile
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast import Alignment, Document, Heading, Node, Paragraph, Table, TableCell, TableRow, Text
from all2md.converter_metadata import ConverterMetadata
from all2md.converter_registry import registry
from all2md.exceptions import (
    All2MdError,
    FormatError,
    MalformedFileError,
    ParsingError,
    ValidationError,
)
from all2md.options.zip import ZipOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.security import validate_zip_archive

logger = logging.getLogger(__name__)


class ZipToAstConverter(BaseParser):
    """Convert ZIP archive contents to AST representation.

    This parser extracts files from ZIP archives, converts each parseable
    file to AST using the appropriate parser, and combines them into a
    unified document. Resource files (images, etc.) can be extracted to
    an attachment directory.

    Parameters
    ----------
    options : ZipOptions or None
        ZIP conversion options

    """

    def __init__(self, options: ZipOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the ZIP parser with options and progress callback."""
        options = options or ZipOptions()
        super().__init__(options, progress_callback=progress_callback)
        self.options: ZipOptions = options
        # Track extracted resources for manifest
        self._extracted_resources: list[dict[str, Any]] = []

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse ZIP archive into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input ZIP file to parse

        Returns
        -------
        Document
            AST Document node representing the parsed archive contents

        Raises
        ------
        ZipFileSecurityError
            If archive fails security validation
        MalformedFileError
            If archive is corrupted or invalid
        ParsingError
            If parsing fails for other reasons

        """
        # Emit started event
        self._emit_progress(
            "started",
            "Extracting ZIP archive",
            current=0,
            total=1
        )

        # Handle different input types
        zip_bytes = None
        zip_path = None

        if isinstance(input_data, bytes):
            zip_bytes = input_data
        elif isinstance(input_data, (str, Path)):
            zip_path = str(input_data)
            # Validate ZIP archive security
            validate_zip_archive(zip_path)
        elif hasattr(input_data, 'read'):
            input_data.seek(0)
            zip_bytes = input_data.read()
        else:
            raise ValidationError(f"Unsupported input type: {type(input_data)}")

        # If we have bytes, validate them as well
        if zip_bytes:
            # Write to temporary location for validation
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                tmp.write(zip_bytes)
                tmp_path = tmp.name
            try:
                validate_zip_archive(tmp_path)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        # Open the ZIP file
        try:
            if zip_bytes:
                zf = zipfile.ZipFile(io.BytesIO(zip_bytes), 'r')
            else:
                # zip_path must be set if zip_bytes is None
                assert zip_path is not None
                zf = zipfile.ZipFile(zip_path, 'r')
        except zipfile.BadZipFile as e:
            raise MalformedFileError(f"Invalid ZIP archive: {e}") from e
        except Exception as e:
            raise ParsingError(
                f"Failed to open ZIP archive: {e}",
                parsing_stage="archive_opening",
                original_error=e
            ) from e

        try:
            # Convert to AST
            doc = self.convert_to_ast(zf)

            # Extract and attach metadata
            metadata = self.extract_metadata(zf)
            doc.metadata = metadata.to_dict()

            # Emit finished event
            self._emit_progress(
                "finished",
                "ZIP archive extraction completed",
                current=1,
                total=1
            )

            return doc
        finally:
            zf.close()

    def convert_to_ast(self, zf: zipfile.ZipFile) -> Document:
        """Convert ZIP archive to AST Document.

        Parameters
        ----------
        zf : zipfile.ZipFile
            Opened ZIP file object

        Returns
        -------
        Document
            AST document node

        """
        children: list[Node] = []
        # Reset extracted resources list
        self._extracted_resources = []

        # Get list of files to process
        file_list = self._get_file_list(zf)

        logger.debug(f"Found {len(file_list)} files to process: {file_list}")

        if not file_list:
            logger.warning("No files to process in ZIP archive")
            children.append(
                Paragraph(content=[Text(content="(Empty archive or no matching files)")])
            )
            return Document(children=children)

        total_files = len(file_list)
        processed_count = 0

        # Process each file
        for file_path in file_list:
            try:
                self._emit_progress(
                    "file_processing",
                    f"Processing {file_path}",
                    current=processed_count,
                    total=total_files,
                    file_path=file_path
                )

                # Extract file content
                file_data = zf.read(file_path)

                # Skip empty files if configured
                if not file_data and self.options.skip_empty_files:
                    logger.debug(f"Skipping empty file: {file_path}")
                    processed_count += 1
                    continue

                # Try to convert the file
                file_ast = self._convert_file(file_path, file_data)

                if file_ast and file_ast.children:
                    # Add section heading if configured
                    if self.options.create_section_headings:
                        display_path = self._get_display_path(file_path)
                        children.append(
                            Heading(level=2, content=[Text(content=display_path)])
                        )

                    # Add the file's content
                    children.extend(file_ast.children)
                elif not self.options.skip_empty_files:
                    # Add a note that the file couldn't be parsed
                    display_path = self._get_display_path(file_path)
                    if self.options.create_section_headings:
                        children.append(
                            Heading(level=2, content=[Text(content=display_path)])
                        )
                    children.append(
                        Paragraph(content=[Text(content="(Could not parse this file)")])
                    )

                processed_count += 1

            except Exception as e:
                logger.warning(f"Failed to process file {file_path}: {e}")
                if not self.options.skip_empty_files:
                    display_path = self._get_display_path(file_path)
                    if self.options.create_section_headings:
                        children.append(
                            Heading(level=2, content=[Text(content=display_path)])
                        )
                    children.append(
                        Paragraph(content=[
                            Text(content=f"(Error processing file: {str(e)})")
                        ])
                    )
                processed_count += 1
                continue

        # Add resource manifest if requested and resources were extracted
        if (self.options.include_resource_manifest and
                self.options.extract_resource_files and
                self._extracted_resources):
            self._add_resource_manifest(children)

        return Document(children=children)

    def _get_file_list(self, zf: zipfile.ZipFile) -> list[str]:
        """Get filtered list of files to process from archive.

        Parameters
        ----------
        zf : zipfile.ZipFile
            Opened ZIP file object

        Returns
        -------
        list[str]
            List of file paths to process

        """
        file_list = []

        for info in zf.infolist():
            # Skip directories
            if info.is_dir():
                continue

            file_path = info.filename

            # Check depth limit
            if self.options.max_depth is not None:
                depth = len(Path(file_path).parts) - 1
                if depth > self.options.max_depth:
                    continue

            # Check exclude patterns
            if self.options.exclude_patterns:
                excluded = False
                for pattern in self.options.exclude_patterns:
                    if fnmatch.fnmatch(file_path, pattern):
                        excluded = True
                        break
                if excluded:
                    continue

            # Check include patterns
            if self.options.include_patterns:
                included = False
                for pattern in self.options.include_patterns:
                    if fnmatch.fnmatch(file_path, pattern):
                        included = True
                        break
                if not included:
                    continue

            file_list.append(file_path)

        return file_list

    def _get_display_path(self, file_path: str) -> str:
        """Get display path for a file based on options.

        Parameters
        ----------
        file_path : str
            Original file path in archive

        Returns
        -------
        str
            Display path for section heading

        """
        if self.options.flatten_structure or not self.options.preserve_directory_structure:
            return Path(file_path).name
        return file_path

    def _convert_file(self, file_path: str, file_data: bytes) -> Document | None:
        """Convert a single file to AST.

        Parameters
        ----------
        file_path : str
            Path of file in archive
        file_data : bytes
            File content bytes

        Returns
        -------
        Document or None
            Converted AST document, or None if conversion failed

        """
        # Import here to avoid circular dependency
        from all2md import to_ast

        try:
            # Create a BytesIO object with a name attribute for better format detection
            file_obj = io.BytesIO(file_data)
            file_obj.name = file_path

            # Detect format using registry (with filename for better detection)
            detected_format = registry.detect_format(file_obj)

            # Check if we have a parser for this format
            try:
                _parser_class = registry.get_parser(detected_format)
            except FormatError:
                # No parser available
                logger.debug(f"No parser for format '{detected_format}': {file_path}")

                # If extract_resource_files is enabled, extract the resource
                if self.options.extract_resource_files and self.options.attachment_output_dir:
                    self._extract_resource_file(file_path, file_data)

                return None

            # Reset the file object position for parsing
            file_obj.seek(0)

            # Convert using the detected format
            doc = to_ast(
                file_obj,
                source_format=detected_format,  # type: ignore[arg-type]
                progress=self.progress_callback
            )

            return doc

        except All2MdError as e:
            logger.debug(f"Failed to convert {file_path}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error converting {file_path}: {e}")
            return None

    def extract_metadata(self, zf: zipfile.ZipFile) -> DocumentMetadata:
        """Extract metadata from ZIP archive.

        Parameters
        ----------
        zf : zipfile.ZipFile
            ZIP file object

        Returns
        -------
        DocumentMetadata
            Extracted metadata (basic info about the archive)

        """
        metadata = DocumentMetadata()

        # Get archive info
        file_count = len([f for f in zf.infolist() if not f.is_dir()])

        # Try to get a reasonable title from the filename if available
        if hasattr(zf, 'filename') and zf.filename:
            metadata.title = Path(zf.filename).stem

        # Add archive statistics to custom metadata
        metadata.custom = {
            "file_count": file_count,
            "format": "zip"
        }

        return metadata

    def _extract_resource_file(self, file_path: str, file_data: bytes) -> None:
        """Extract a resource file to the attachment directory.

        Parameters
        ----------
        file_path : str
            Path of file in archive
        file_data : bytes
            File content bytes

        """
        if not self.options.attachment_output_dir:
            return

        try:
            # Determine output path
            output_dir = Path(self.options.attachment_output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Preserve directory structure or flatten based on options
            if self.options.preserve_directory_structure and not self.options.flatten_structure:
                output_file = output_dir / file_path
                output_file.parent.mkdir(parents=True, exist_ok=True)
            else:
                output_file = output_dir / Path(file_path).name

            # Write the file
            output_file.write_bytes(file_data)

            # Track for manifest
            self._extracted_resources.append({
                "filename": Path(file_path).name,
                "path": file_path,
                "size": len(file_data),
                "output_path": str(output_file)
            })

            logger.debug(f"Extracted resource: {file_path} -> {output_file}")

        except Exception as e:
            logger.warning(f"Failed to extract resource {file_path}: {e}")

    def _add_resource_manifest(self, children: list[Node]) -> None:
        """Add a manifest table of extracted resources to the document.

        Parameters
        ----------
        children : list[Node]
            Document children list to append manifest to

        """
        # Add heading
        children.append(Heading(level=2, content=[Text(content="Extracted Resources")]))

        # Build manifest table
        header_cells = [
            TableCell(content=[Text(content="Filename")], alignment="left"),
            TableCell(content=[Text(content="Archive Path")], alignment="left"),
            TableCell(content=[Text(content="Size (bytes)")], alignment="right"),
        ]
        header_row = TableRow(cells=header_cells, is_header=True)

        # Build data rows
        data_rows = []
        for resource in self._extracted_resources:
            row_cells = [
                TableCell(content=[Text(content=resource["filename"])], alignment="left"),
                TableCell(content=[Text(content=resource["path"])], alignment="left"),
                TableCell(content=[Text(content=str(resource["size"]))], alignment="right"),
            ]
            data_rows.append(TableRow(cells=row_cells, is_header=False))

        # Create table
        alignments: list[Alignment | None] = ["left", "left", "right"]
        table = Table(header=header_row, rows=data_rows, alignments=alignments)
        children.append(table)


# Converter metadata for registry
CONVERTER_METADATA = ConverterMetadata(
    format_name="zip",
    extensions=[".zip"],
    mime_types=["application/zip"],
    magic_bytes=[
        (b"PK\x03\x04", 0),  # ZIP signature
    ],
    parser_class=ZipToAstConverter,
    renderer_class=None,
    parser_required_packages=[],  # Uses stdlib zipfile
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="",
    parser_options_class=ZipOptions,
    renderer_options_class=None,
    description="Extract and convert files from ZIP archives",
    priority=3  # Lower than specific formats to avoid conflicts with DOCX/EPUB
)
