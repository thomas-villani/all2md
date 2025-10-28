#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/zip.py
"""ZIP archive parser that converts archive contents to AST representation.

This module provides the ZipToAstConverter class that extracts files from ZIP
archives, converts parseable files to AST, and handles resource files.
"""

from __future__ import annotations

import fnmatch
import hashlib
import io
import logging
import os
import tempfile
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import IO, Any, Optional, Union, cast

from all2md.api import to_ast
from all2md.ast import Alignment, Document, Heading, Node, Paragraph, Table, TableCell, TableRow, Text
from all2md.constants import RESOURCE_FILE_EXTENSIONS, DocumentFormat
from all2md.converter_metadata import ConverterMetadata
from all2md.converter_registry import registry
from all2md.exceptions import (
    All2MdError,
    FormatError,
    MalformedFileError,
    ParsingError,
    ValidationError,
    ZipFileSecurityError,
)
from all2md.options.base import BaseParserOptions
from all2md.options.zip import ZipOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.security import validate_safe_extraction_path, validate_zip_archive

logger = logging.getLogger(__name__)


def _process_zip_file_worker(
    file_path: str, file_data: bytes, options_dict: dict[str, Any]
) -> tuple[str, Document | None, dict[str, Any] | None]:
    """Worker function for parallel file processing.

    This function is defined at module level to be picklable for multiprocessing.

    Parameters
    ----------
    file_path : str
        Path of file in archive
    file_data : bytes
        File content bytes
    options_dict : dict[str, Any]
        Serialized options dictionary (includes resource_file_extensions and attachment options)

    Returns
    -------
    tuple
        (file_path, Document or None, error_dict or None)
        Document is None on failure, error_dict contains error details if failed

    """
    try:
        # Check if this file should be treated as a resource
        resource_extensions = options_dict.get("resource_file_extensions")
        if resource_extensions is None:
            resource_extensions = RESOURCE_FILE_EXTENSIONS
        elif len(resource_extensions) == 0:
            resource_extensions = []

        file_ext = Path(file_path).suffix.lower()
        if file_ext and resource_extensions and file_ext in [ext.lower() for ext in resource_extensions]:
            # This is a resource file, don't parse it
            return (file_path, None, None)

        # Create a BytesIO object with a name attribute for better format detection
        file_obj = io.BytesIO(file_data)
        file_obj.name = file_path

        # Detect format using registry
        detected_format = cast(DocumentFormat, registry.detect_format(file_obj))

        # Check if we have a parser for this format
        try:
            _parser_class = registry.get_parser(detected_format)
        except FormatError:
            # No parser available
            return (file_path, None, None)

        # Reset the file object position for parsing
        file_obj.seek(0)

        # Create parser options with attachment settings from the options dict
        parser_options: Optional[BaseParserOptions] = None
        try:
            options_class = registry.get_parser_options_class(detected_format)
            if options_class is not None:
                from all2md.options.common import AttachmentOptionsMixin

                # Extract attachment options from the options dict (if present)
                attachment_opts = {
                    k: v
                    for k, v in options_dict.items()
                    if k
                    in (
                        "attachment_mode",
                        "alt_text_mode",
                        "attachment_output_dir",
                        "attachment_base_url",
                        "max_asset_size_bytes",
                        "attachment_filename_template",
                        "attachment_overwrite",
                        "attachment_deduplicate_by_hash",
                        "attachments_footnotes_section",
                    )
                }

                # Create options with attachment fields if the class supports them
                if attachment_opts and issubclass(options_class, AttachmentOptionsMixin):
                    default_options = options_class()
                    parser_options = cast(BaseParserOptions, default_options.create_updated(**attachment_opts))
        except Exception:
            # If option creation fails, continue without options
            pass

        # Convert using the detected format with attachment options (no progress callback in parallel mode)
        doc = to_ast(file_obj, source_format=detected_format, parser_options=parser_options, progress_callback=None)

        return (file_path, doc, None)

    except Exception as e:
        # Return error information
        error_dict = {
            "file_path": file_path,
            "error_type": type(e).__name__,
            "error_message": str(e),
        }
        return (file_path, None, error_dict)


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
        BaseParser._validate_options_type(options, ZipOptions, "zip")
        options = options or ZipOptions()
        super().__init__(options, progress_callback=progress_callback)
        self.options: ZipOptions = options
        # Track extracted resources for manifest
        self._extracted_resources: list[dict[str, Any]] = []
        # Track failed files for error reporting
        self._failed_files: list[dict[str, Any]] = []

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
        self._emit_progress("started", "Extracting ZIP archive", current=0, total=1)

        # Handle different input types
        zip_bytes = None
        zip_path = None

        if isinstance(input_data, bytes):
            zip_bytes = input_data
        elif isinstance(input_data, (str, Path)):
            zip_path = str(input_data)
            # Validate ZIP archive security
            validate_zip_archive(zip_path)
        elif hasattr(input_data, "read"):
            input_data.seek(0)
            zip_bytes = input_data.read()
        else:
            raise ValidationError(f"Unsupported input type: {type(input_data)}")

        # If we have bytes, validate them as well
        if zip_bytes:
            # Write to temporary location for validation
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
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
                zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
            else:
                # zip_path must be set if zip_bytes is None
                assert zip_path is not None
                zf = zipfile.ZipFile(zip_path, "r")
        except zipfile.BadZipFile as e:
            raise MalformedFileError(f"Invalid ZIP archive: {e}") from e
        except Exception as e:
            raise ParsingError(
                f"Failed to open ZIP archive: {e}", parsing_stage="archive_opening", original_error=e
            ) from e

        try:
            # Convert to AST
            doc = self.convert_to_ast(zf)

            # Extract and attach metadata
            metadata = self.extract_metadata(zf)
            doc.metadata = metadata.to_dict()

            # Emit finished event
            self._emit_progress("finished", "ZIP archive extraction completed", current=1, total=1)

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
        # Reset extracted resources and failed files lists
        self._extracted_resources = []
        self._failed_files = []

        # Get list of files to process
        file_list = self._get_file_list(zf)

        # Check if parallel processing should be used
        if self._should_use_parallel_processing(len(file_list)):
            return self._convert_to_ast_parallel(zf, file_list)

        # Otherwise use sequential processing (original code below)

        logger.debug(f"Found {len(file_list)} files to process: {file_list}")

        if not file_list:
            logger.warning("No files to process in ZIP archive")
            children.append(Paragraph(content=[Text(content="(Empty archive or no matching files)")]))
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
                    file_path=file_path,
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
                        children.append(Heading(level=2, content=[Text(content=display_path)]))

                    # Add the file's content
                    children.extend(file_ast.children)
                elif not self.options.skip_empty_files:
                    # Add a note that the file couldn't be parsed
                    display_path = self._get_display_path(file_path)
                    if self.options.create_section_headings:
                        children.append(Heading(level=2, content=[Text(content=display_path)]))
                    children.append(Paragraph(content=[Text(content="(Could not parse this file)")]))

                processed_count += 1

            except Exception as e:
                logger.warning(f"Failed to process file {file_path}: {e}")
                # Track error for error report
                error_type = type(e).__name__
                error_message = str(e)
                self._failed_files.append(
                    {
                        "file_path": file_path,
                        "error_type": error_type,
                        "error_message": error_message,
                    }
                )
                if not self.options.skip_empty_files:
                    display_path = self._get_display_path(file_path)
                    if self.options.create_section_headings:
                        children.append(Heading(level=2, content=[Text(content=display_path)]))
                    children.append(Paragraph(content=[Text(content=f"(Error processing file: {str(e)})")]))
                processed_count += 1
                continue

        # Add resource manifest if requested and resources were extracted
        if self.options.include_resource_manifest and self.options.extract_resource_files and self._extracted_resources:
            self._add_resource_manifest(children)

        # Add error report if any files failed to process
        if self._failed_files:
            self._add_error_report_table(children)

        return Document(children=children)

    def _should_use_parallel_processing(self, file_count: int) -> bool:
        """Check if parallel processing should be used based on file count and options.

        Parameters
        ----------
        file_count : int
            Number of files to process

        Returns
        -------
        bool
            True if parallel processing should be used

        """
        return self.options.enable_parallel_processing and file_count >= self.options.parallel_threshold

    def _convert_to_ast_parallel(self, zf: zipfile.ZipFile, file_list: list[str]) -> Document:
        """Convert ZIP archive to AST using parallel processing.

        Parameters
        ----------
        zf : zipfile.ZipFile
            Opened ZIP file object
        file_list : list[str]
            List of files to process

        Returns
        -------
        Document
            AST document node

        """
        children: list[Node] = []

        logger.info(f"Using parallel processing for {len(file_list)} files")

        if not file_list:
            logger.warning("No files to process in ZIP archive")
            children.append(Paragraph(content=[Text(content="(Empty archive or no matching files)")]))
            return Document(children=children)

        # Prepare options dict for workers (includes attachment options for nested parsers)
        options_dict = {
            "resource_file_extensions": self.options.resource_file_extensions,
        }
        # Add all attachment options for nested file parsing
        options_dict.update(self._get_attachment_options_dict())

        # Read all files into memory for parallel processing
        file_data_map: dict[str, bytes] = {}
        for file_path in file_list:
            try:
                file_data_map[file_path] = zf.read(file_path)
            except Exception as e:
                logger.warning(f"Failed to read file {file_path}: {e}")
                self._failed_files.append(
                    {
                        "file_path": file_path,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    }
                )

        # Process files in parallel
        max_workers = self.options.max_workers
        results_map: dict[str, tuple[Document | None, dict[str, Any] | None]] = {}

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_file = {}
            for file_path, file_data in file_data_map.items():
                if not file_data and self.options.skip_empty_files:
                    logger.debug(f"Skipping empty file: {file_path}")
                    continue
                future = executor.submit(_process_zip_file_worker, file_path, file_data, options_dict)
                future_to_file[future] = file_path

            # Track progress
            total_files = len(future_to_file)
            completed_count = 0

            # Collect results as they complete
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result_file_path, doc, error_dict = future.result()
                    results_map[result_file_path] = (doc, error_dict)

                    # Emit progress event as each file completes
                    completed_count += 1
                    self._emit_progress(
                        "file_processing",
                        f"Completed {result_file_path}",
                        current=completed_count,
                        total=total_files,
                        file_path=result_file_path,
                    )

                    # Track errors
                    if error_dict:
                        self._failed_files.append(error_dict)
                except Exception as e:
                    logger.warning(f"Worker exception for {file_path}: {e}")
                    completed_count += 1
                    self._emit_progress(
                        "file_processing",
                        f"Failed {file_path}",
                        current=completed_count,
                        total=total_files,
                        file_path=file_path,
                    )
                    self._failed_files.append(
                        {
                            "file_path": file_path,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                        }
                    )

        # Reconstruct document in original order
        for file_path in file_list:
            if file_path not in results_map:
                # File was skipped or failed to read
                continue

            doc, error_dict = results_map[file_path]

            # Handle resource files (doc is None but no error)
            if doc is None and error_dict is None:
                # This is a resource file
                if self.options.extract_resource_files and self.options.attachment_output_dir:
                    file_data = file_data_map.get(file_path, b"")
                    self._extract_resource_file(file_path, file_data)
                continue

            # Handle conversion errors (error_dict is not None)
            if error_dict:
                if not self.options.skip_empty_files:
                    display_path = self._get_display_path(file_path)
                    if self.options.create_section_headings:
                        children.append(Heading(level=2, content=[Text(content=display_path)]))
                    error_msg = f"(Error processing file: {error_dict['error_message']})"
                    children.append(Paragraph(content=[Text(content=error_msg)]))
                continue

            # Add successfully converted content
            if doc and doc.children:
                if self.options.create_section_headings:
                    display_path = self._get_display_path(file_path)
                    children.append(Heading(level=2, content=[Text(content=display_path)]))
                children.extend(doc.children)
            elif not self.options.skip_empty_files:
                display_path = self._get_display_path(file_path)
                if self.options.create_section_headings:
                    children.append(Heading(level=2, content=[Text(content=display_path)]))
                children.append(Paragraph(content=[Text(content="(Could not parse this file)")]))

        # Add resource manifest if requested and resources were extracted
        if self.options.include_resource_manifest and self.options.extract_resource_files and self._extracted_resources:
            self._add_resource_manifest(children)

        # Add error report if any files failed to process
        if self._failed_files:
            self._add_error_report_table(children)

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
        if not self.options.preserve_directory_structure:
            return Path(file_path).name
        return file_path

    def _is_resource_file(self, file_path: str) -> bool:
        """Check if a file should be treated as a resource based on its extension.

        Parameters
        ----------
        file_path : str
            Path of file in archive

        Returns
        -------
        bool
            True if file should be treated as a resource, False if it should be parsed

        """
        # Get the configured resource extensions (None means use defaults)
        resource_extensions = self.options.resource_file_extensions
        if resource_extensions is None:
            resource_extensions = RESOURCE_FILE_EXTENSIONS
        elif len(resource_extensions) == 0:
            # Empty list means treat nothing as a resource (parse everything)
            return False

        # Get file extension (case-insensitive)
        file_ext = Path(file_path).suffix.lower()
        if not file_ext:
            return False

        # Check if extension is in the resource list (case-insensitive)
        return file_ext in [ext.lower() for ext in resource_extensions]

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
        # Check if this file should be treated as a resource BEFORE attempting to parse
        if self._is_resource_file(file_path):
            logger.debug(f"Treating as resource file (by extension): {file_path}")
            if self.options.extract_resource_files and self.options.attachment_output_dir:
                self._extract_resource_file(file_path, file_data)
            return None

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

            # Create parser options with attachment settings from ZIP options
            parser_options = self._create_nested_parser_options(detected_format)

            # Convert using the detected format with attachment options
            doc = to_ast(
                file_obj,
                source_format=cast(DocumentFormat, detected_format),
                parser_options=parser_options,
                progress_callback=self.progress_callback,
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
        if hasattr(zf, "filename") and zf.filename:
            metadata.title = Path(zf.filename).stem

        # Add archive statistics to custom metadata
        metadata.custom = {"file_count": file_count, "format": "zip"}

        return metadata

    def _get_attachment_options_dict(self) -> dict[str, Any]:
        """Extract attachment-related options from ZipOptions as a dictionary.

        This creates a dictionary of attachment options that can be passed to nested
        parsers when converting files inside ZIP archives.

        Returns
        -------
        dict[str, Any]
            Dictionary of attachment option names and values

        """
        # Extract all attachment-related fields from self.options
        # These come from AttachmentOptionsMixin
        return {
            "attachment_mode": self.options.attachment_mode,
            "alt_text_mode": self.options.alt_text_mode,
            "attachment_output_dir": self.options.attachment_output_dir,
            "attachment_base_url": self.options.attachment_base_url,
            "max_asset_size_bytes": self.options.max_asset_size_bytes,
            "attachment_filename_template": self.options.attachment_filename_template,
            "attachment_overwrite": self.options.attachment_overwrite,
            "attachment_deduplicate_by_hash": self.options.attachment_deduplicate_by_hash,
            "attachments_footnotes_section": self.options.attachments_footnotes_section,
        }

    def _create_nested_parser_options(self, detected_format: str) -> BaseParserOptions | None:
        """Create parser options for a nested file with attachment settings from ZIP options.

        Parameters
        ----------
        detected_format : str
            The detected format of the nested file

        Returns
        -------
        BaseParserOptions or None
            Parser options with attachment settings, or None if format doesn't support attachments

        """
        # Get the options class for this format from the registry
        try:
            options_class = registry.get_parser_options_class(detected_format)
            if options_class is None:
                return None

            # Check if this options class supports attachment options (has AttachmentOptionsMixin)
            from all2md.options.base import BaseParserOptions
            from all2md.options.common import AttachmentOptionsMixin

            # Get attachment options as dict
            attachment_opts = self._get_attachment_options_dict()

            # Create options with attachment fields if the class supports them
            if issubclass(options_class, AttachmentOptionsMixin):
                # Use the create_updated method to create a new instance with modified fields
                default_options = options_class()
                # Replace with our attachment settings
                return cast(BaseParserOptions, default_options.create_updated(**attachment_opts))
            else:
                # Format doesn't support attachments, return default options
                return cast(BaseParserOptions, options_class())

        except Exception as e:
            logger.debug(f"Failed to create parser options for {detected_format}: {e}")
            return None

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

            # Validate and construct safe output path to prevent path traversal
            if self.options.preserve_directory_structure:
                # Use full path from archive, but validate it's safe
                output_file = validate_safe_extraction_path(output_dir, file_path)
                # Ensure parent directories exist
                output_file.parent.mkdir(parents=True, exist_ok=True)
            else:
                # Use only the filename (flatten structure), but still validate
                filename_only = Path(file_path).name
                output_file = validate_safe_extraction_path(output_dir, filename_only)

            # Write the file
            output_file.write_bytes(file_data)

            # Compute SHA256 hash for audit trail
            sha256_hash = hashlib.sha256(file_data).hexdigest()

            # Track for manifest
            self._extracted_resources.append(
                {
                    "filename": Path(file_path).name,
                    "path": file_path,
                    "size": len(file_data),
                    "sha256": sha256_hash,
                    "output_path": str(output_file),
                }
            )

            logger.debug(f"Extracted resource: {file_path} -> {output_file}")

        except ZipFileSecurityError as e:
            # Log security violations at warning level and skip the file
            logger.warning(f"Security violation - skipping resource {file_path}: {e}")
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
            TableCell(content=[Text(content="SHA256 Hash")], alignment="left"),
        ]
        header_row = TableRow(cells=header_cells, is_header=True)

        # Build data rows
        data_rows = []
        total_size = 0
        for resource in self._extracted_resources:
            row_cells = [
                TableCell(content=[Text(content=resource["filename"])], alignment="left"),
                TableCell(content=[Text(content=resource["path"])], alignment="left"),
                TableCell(content=[Text(content=str(resource["size"]))], alignment="right"),
                TableCell(content=[Text(content=resource.get("sha256", "N/A"))], alignment="left"),
            ]
            data_rows.append(TableRow(cells=row_cells, is_header=False))
            total_size += resource["size"]

        # Add total size summary row
        summary_cells = [
            TableCell(content=[Text(content="TOTAL")], alignment="left"),
            TableCell(content=[Text(content="")], alignment="left"),
            TableCell(content=[Text(content=str(total_size))], alignment="right"),
            TableCell(content=[Text(content="")], alignment="left"),
        ]
        data_rows.append(TableRow(cells=summary_cells, is_header=False))

        # Create table
        alignments: list[Alignment | None] = ["left", "left", "right", "left"]
        table = Table(header=header_row, rows=data_rows, alignments=alignments)
        children.append(table)

    def _add_error_report_table(self, children: list[Node]) -> None:
        """Add an error report table of failed files to the document.

        Parameters
        ----------
        children : list[Node]
            Document children list to append error report to

        """
        # Add heading
        children.append(Heading(level=2, content=[Text(content="Processing Errors")]))

        # Build error report table
        header_cells = [
            TableCell(content=[Text(content="File Path")], alignment="left"),
            TableCell(content=[Text(content="Error Type")], alignment="left"),
            TableCell(content=[Text(content="Error Message")], alignment="left"),
        ]
        header_row = TableRow(cells=header_cells, is_header=True)

        # Build data rows
        data_rows = []
        for error_info in self._failed_files:
            row_cells = [
                TableCell(content=[Text(content=error_info["file_path"])], alignment="left"),
                TableCell(content=[Text(content=error_info["error_type"])], alignment="left"),
                TableCell(content=[Text(content=error_info["error_message"])], alignment="left"),
            ]
            data_rows.append(TableRow(cells=row_cells, is_header=False))

        # Create table
        alignments: list[Alignment | None] = ["left", "left", "left"]
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
    priority=3,  # Lower than specific formats to avoid conflicts with DOCX/EPUB
)
