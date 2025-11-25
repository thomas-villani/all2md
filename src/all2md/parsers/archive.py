#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/archive.py
"""Archive (TAR/7Z/RAR) parser that converts archive contents to AST representation.

This module provides the ArchiveToAstConverter class that extracts files from
TAR, 7Z, and RAR archives, converts parseable files to AST, and handles resource files.
"""

from __future__ import annotations

import fnmatch
import hashlib
import io
import logging
import os
import tarfile
import tempfile
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import IO, Any, cast

from all2md.api import to_ast
from all2md.ast import Alignment, Document, Heading, Node, Paragraph, Table, TableCell, TableRow, Text
from all2md.constants import RESOURCE_FILE_EXTENSIONS, DocumentFormat
from all2md.converter_metadata import ConverterMetadata
from all2md.converter_registry import registry
from all2md.exceptions import (
    All2MdError,
    ArchiveSecurityError,
    DependencyError,
    FormatError,
    MalformedFileError,
    ParsingError,
    ValidationError,
)
from all2md.options.archive import ArchiveOptions
from all2md.options.base import BaseParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.security import (
    validate_7z_archive,
    validate_rar_archive,
    validate_safe_extraction_path,
    validate_tar_archive,
)

logger = logging.getLogger(__name__)


def _process_archive_file_worker(
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
        Serialized options dictionary including attachment options

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
        detected_format = registry.detect_format(file_obj)

        # Check if we have a parser for this format
        try:
            _parser_class = registry.get_parser(detected_format)
        except FormatError:
            # No parser available
            return (file_path, None, None)

        # Reset the file object position for parsing
        file_obj.seek(0)

        # Create parser options with attachment settings if available
        parser_options = None
        attachment_opts = options_dict.get("attachment_options")
        if attachment_opts:
            try:
                from all2md.options.common import AttachmentOptionsMixin

                options_class = registry.get_parser_options_class(detected_format)
                if options_class and issubclass(options_class, AttachmentOptionsMixin):
                    default_options = options_class()
                    parser_options = default_options.create_updated(**attachment_opts)
                elif options_class:
                    parser_options = options_class()
            except Exception:
                # If options creation fails, fall back to None (use defaults)
                parser_options = None

        # Convert using the detected format (no progress callback in parallel mode)
        doc = to_ast(
            file_obj,
            source_format=cast(DocumentFormat, detected_format),
            parser_options=cast(BaseParserOptions | None, parser_options),
            progress_callback=None,
        )

        return (file_path, doc, None)

    except Exception as e:
        # Return error information
        error_dict = {
            "file_path": file_path,
            "error_type": type(e).__name__,
            "error_message": str(e),
        }
        return (file_path, None, error_dict)


class ArchiveToAstConverter(BaseParser):
    """Convert archive (TAR/7Z/RAR) contents to AST representation.

    This parser extracts files from TAR, 7Z, and RAR archives, converts each
    parseable file to AST using the appropriate parser, and combines them into
    a unified document. Resource files (images, etc.) can be extracted to an
    attachment directory.

    Parameters
    ----------
    options : ArchiveOptions or None
        Archive conversion options

    """

    def __init__(self, options: ArchiveOptions | None = None, progress_callback: ProgressCallback | None = None):
        """Initialize the archive parser with options and progress callback."""
        BaseParser._validate_options_type(options, ArchiveOptions, "archive")
        options = options or ArchiveOptions()
        super().__init__(options, progress_callback=progress_callback)
        self.options: ArchiveOptions = options
        # Track extracted resources for manifest
        self._extracted_resources: list[dict[str, Any]] = []
        # Track failed files for error reporting
        self._failed_files: list[dict[str, Any]] = []
        # Store archive type for metadata extraction
        self._archive_type: str = ""

    def parse(self, input_data: str | Path | IO[bytes] | bytes) -> Document:
        """Parse archive into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input archive file to parse

        Returns
        -------
        Document
            AST Document node representing the parsed archive contents

        Raises
        ------
        ArchiveSecurityError
            If archive fails security validation
        MalformedFileError
            If archive is corrupted or invalid
        ParsingError
            If parsing fails for other reasons

        """
        # Emit started event
        self._emit_progress("started", "Extracting archive", current=0, total=1)

        # Detect archive type
        archive_type = self._detect_archive_type(input_data)
        self._archive_type = archive_type
        logger.debug(f"Detected archive type: {archive_type}")

        # Handle different input types and open archive
        try:
            if archive_type.startswith("tar"):
                archive_obj, cleanup_func = self._open_tar(input_data, archive_type)
            elif archive_type == "7z":
                archive_obj, cleanup_func = self._open_7z(input_data)
            elif archive_type == "rar":
                archive_obj, cleanup_func = self._open_rar(input_data)
            else:
                raise ParsingError(f"Unsupported archive type: {archive_type}", parsing_stage="archive_opening")
        except Exception as e:
            if isinstance(e, (All2MdError,)):
                raise
            raise ParsingError(
                f"Failed to open archive: {e!r}", parsing_stage="archive_opening", original_error=e
            ) from e

        try:
            # Convert to AST
            doc = self.convert_to_ast(archive_obj, archive_type)

            # Extract and attach metadata
            metadata = self.extract_metadata(archive_obj)
            doc.metadata = metadata.to_dict()

            # Emit finished event
            self._emit_progress("finished", "Archive extraction completed", current=1, total=1)

            return doc
        finally:
            # Cleanup archive object
            if cleanup_func:
                cleanup_func()

    def _detect_archive_type(self, input_data: str | Path | IO[bytes] | bytes) -> str:
        """Detect specific archive type from input.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Input data to detect

        Returns
        -------
        str
            Archive type: 'tar', 'tar.gz', 'tar.bz2', 'tar.xz', '7z', or 'rar'

        """
        # Try filename first (most reliable)
        filename = None
        if isinstance(input_data, (str, Path)):
            filename = str(input_data)
        elif hasattr(input_data, "name") and input_data.name:
            filename = input_data.name

        if filename:
            filename_lower = filename.lower()
            # Check compressed tar variants first (most specific)
            if filename_lower.endswith((".tar.gz", ".tgz")):
                return "tar.gz"
            if filename_lower.endswith((".tar.bz2", ".tbz2", ".tb2")):
                return "tar.bz2"
            if filename_lower.endswith((".tar.xz", ".txz")):
                return "tar.xz"
            if filename_lower.endswith(".tar"):
                return "tar"
            if filename_lower.endswith(".7z"):
                return "7z"
            if filename_lower.endswith(".rar"):
                return "rar"

        # Try magic bytes
        magic = self._read_magic_bytes(input_data, 8)

        # Check for compressed formats
        if magic.startswith(b"\x1f\x8b"):  # GZIP
            return "tar.gz"
        if magic.startswith(b"BZ"):  # BZIP2
            return "tar.bz2"
        if magic.startswith(b"\xfd7zXZ\x00"):  # XZ
            return "tar.xz"
        if magic.startswith(b"7z\xbc\xaf\x27\x1c"):  # 7Z
            return "7z"
        if magic.startswith(b"Rar!\x1a\x07"):  # RAR (both RAR4 and RAR5)
            return "rar"
        if b"ustar" in magic or magic.startswith(b"0"):  # Uncompressed TAR
            return "tar"

        # Default to tar if we can't detect
        logger.warning("Could not detect archive type, defaulting to tar")
        return "tar"

    def _read_magic_bytes(self, input_data: str | Path | IO[bytes] | bytes, num_bytes: int) -> bytes:
        """Read magic bytes from input for format detection.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Input to read from
        num_bytes : int
            Number of bytes to read

        Returns
        -------
        bytes
            Magic bytes

        """
        if isinstance(input_data, bytes):
            return input_data[:num_bytes]
        if isinstance(input_data, (str, Path)):
            try:
                with open(input_data, "rb") as f:
                    return f.read(num_bytes)
            except Exception:
                return b""
        elif hasattr(input_data, "read") and hasattr(input_data, "seek"):
            try:
                pos = input_data.tell()
                input_data.seek(0)
                data = input_data.read(num_bytes)
                input_data.seek(pos)
                return data
            except Exception:
                return b""
        return b""

    def _open_tar(
        self, input_data: str | Path | IO[bytes] | bytes, archive_type: str
    ) -> tuple[tarfile.TarFile, Callable[[], None] | None]:
        """Open a TAR archive.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Input data
        archive_type : str
            Archive type (tar, tar.gz, tar.bz2, tar.xz)

        Returns
        -------
        tuple
            (TarFile object, cleanup function or None)

        """
        # Import security validation

        # Determine mode based on archive type
        mode_map = {
            "tar": "r",
            "tar.gz": "r:gz",
            "tar.bz2": "r:bz2",
            "tar.xz": "r:xz",
        }
        mode = mode_map.get(archive_type, "r:*")

        cleanup_func = None

        try:
            if isinstance(input_data, bytes):
                # Write to temp file for validation
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".tar")
                os.write(tmp_fd, input_data)
                os.close(tmp_fd)

                # Validate
                validate_tar_archive(tmp_path)

                # Open
                tar = tarfile.open(tmp_path, mode)  # type: ignore[call-overload]

                # Setup cleanup
                def cleanup() -> None:
                    tar.close()
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

                cleanup_func = cleanup

            elif isinstance(input_data, (str, Path)):
                # Validate
                validate_tar_archive(str(input_data))

                # Open
                tar = tarfile.open(str(input_data), mode)  # type: ignore[call-overload]
                cleanup_func = tar.close

            elif hasattr(input_data, "read"):
                # Read to bytes for validation
                input_data.seek(0)
                data = input_data.read()

                # Write to temp file for validation
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".tar")
                os.write(tmp_fd, data)
                os.close(tmp_fd)

                # Validate
                validate_tar_archive(tmp_path)

                # Open
                tar = tarfile.open(tmp_path, mode)  # type: ignore[call-overload]

                # Setup cleanup
                def cleanup() -> None:
                    tar.close()
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

                cleanup_func = cleanup
            else:
                raise ValidationError(f"Unsupported input type: {type(input_data)}")

            return tar, cleanup_func

        except tarfile.TarError as e:
            raise MalformedFileError(f"Invalid TAR archive: {e}") from e

    def _open_7z(self, input_data: str | Path | IO[bytes] | bytes) -> tuple[Any, Callable[[], None] | None]:
        """Open a 7Z archive.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Input data

        Returns
        -------
        tuple
            (SevenZipFile object, cleanup function or None)

        """
        try:
            import py7zr
        except ImportError as e:
            raise DependencyError(
                converter_name="archive",
                missing_packages=[("py7zr", ">=0.22.0")],
                install_command="pip install all2md[archive]",
                message="py7zr is required for 7Z archive support. Install with: pip install all2md[archive]",
                original_import_error=e,
            ) from e

        # Import security validation

        cleanup_func = None

        try:
            if isinstance(input_data, bytes):
                # Write to temp file
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".7z")
                os.write(tmp_fd, input_data)
                os.close(tmp_fd)

                # Validate
                validate_7z_archive(tmp_path)

                # Open
                sz = py7zr.SevenZipFile(tmp_path, mode="r")

                # Setup cleanup
                def cleanup() -> None:
                    sz.close()  # type: ignore[no-untyped-call]
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

                cleanup_func = cleanup

            elif isinstance(input_data, (str, Path)):
                # Validate
                validate_7z_archive(str(input_data))

                # Open
                sz = py7zr.SevenZipFile(str(input_data), mode="r")
                cleanup_func = sz.close

            elif hasattr(input_data, "read"):
                # Read to bytes
                input_data.seek(0)
                data = input_data.read()

                # Write to temp file
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".7z")
                os.write(tmp_fd, data)
                os.close(tmp_fd)

                # Validate
                validate_7z_archive(tmp_path)

                # Open
                sz = py7zr.SevenZipFile(tmp_path, mode="r")

                # Setup cleanup
                def cleanup() -> None:
                    sz.close()  # type: ignore[no-untyped-call]
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

                cleanup_func = cleanup
            else:
                raise ValidationError(f"Unsupported input type: {type(input_data)}")

            return sz, cleanup_func

        except py7zr.Bad7zFile as e:
            raise MalformedFileError(f"Invalid 7Z archive: {e}") from e

    def _open_rar(self, input_data: str | Path | IO[bytes] | bytes) -> tuple[Any, Callable[[], None] | None]:
        """Open a RAR archive.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Input data

        Returns
        -------
        tuple
            (RarFile object, cleanup function or None)

        """
        try:
            import rarfile
        except ImportError as e:
            raise DependencyError(
                converter_name="archive",
                missing_packages=[("rarfile", ">=4.2")],
                install_command="pip install all2md[archive]",
                message="rarfile is required for RAR archive support. "
                "Install with: pip install all2md[archive]. "
                "Note: RAR extraction also requires UnRAR binary to be installed on your system.",
                original_import_error=e,
            ) from e

        # Import security validation

        cleanup_func = None

        try:
            if isinstance(input_data, bytes):
                # Write to temp file
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".rar")
                os.write(tmp_fd, input_data)
                os.close(tmp_fd)

                # Validate
                validate_rar_archive(tmp_path)

                # Open
                rar = rarfile.RarFile(tmp_path)

                # Setup cleanup
                def cleanup() -> None:
                    rar.close()
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

                cleanup_func = cleanup

            elif isinstance(input_data, (str, Path)):
                # Validate
                validate_rar_archive(str(input_data))

                # Open
                rar = rarfile.RarFile(str(input_data))
                cleanup_func = rar.close

            elif hasattr(input_data, "read"):
                # Read to bytes
                input_data.seek(0)
                data = input_data.read()

                # Write to temp file
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".rar")
                os.write(tmp_fd, data)
                os.close(tmp_fd)

                # Validate
                validate_rar_archive(tmp_path)

                # Open
                rar = rarfile.RarFile(tmp_path)

                # Setup cleanup
                def cleanup() -> None:
                    rar.close()
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

                cleanup_func = cleanup
            else:
                raise ValidationError(f"Unsupported input type: {type(input_data)}")

            return rar, cleanup_func

        except rarfile.BadRarFile as e:
            raise MalformedFileError(f"Invalid RAR archive: {e}") from e

    def convert_to_ast(self, archive: Any, archive_type: str) -> Document:
        """Convert archive to AST Document.

        Parameters
        ----------
        archive : Any
            Opened archive object (TarFile, SevenZipFile, or RarFile)
        archive_type : str
            Type of archive

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
        file_list = self._get_file_list(archive, archive_type)

        # Check if parallel processing should be used
        if self._should_use_parallel_processing(len(file_list)):
            return self._convert_to_ast_parallel(archive, archive_type, file_list)

        # Otherwise use sequential processing (original code below)

        logger.debug(f"Found {len(file_list)} files to process: {file_list}")

        if not file_list:
            logger.warning("No files to process in archive")
            children.append(Paragraph(content=[Text(content="(Empty archive or no matching files)")]))
            return Document(children=children)

        # For 7z archives, extract all files at once since py7zr.read() consumes the archive
        file_data_cache: dict[str, bytes] = {}
        if archive_type == "7z":
            try:
                data_dict = archive.read(file_list)
                for fname, bio in data_dict.items():
                    if hasattr(bio, "read"):
                        file_data_cache[fname] = bio.read()
                    elif isinstance(bio, bytes):
                        file_data_cache[fname] = bio
                    else:
                        file_data_cache[fname] = b""
            except Exception as e:
                logger.warning(f"Failed to extract 7z files: {e}")
                children.append(Paragraph(content=[Text(content=f"(Error extracting archive: {e!s})")]))
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
                # For 7z, use cached data; for others, read directly
                if archive_type == "7z" and file_path in file_data_cache:
                    file_data = file_data_cache[file_path]
                else:
                    file_data = self._read_archive_file(archive, archive_type, file_path)

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
                    children.append(Paragraph(content=[Text(content=f"(Error processing file: {e!s})")]))
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

    def _prepare_file_data_cache(
        self, archive: Any, archive_type: str, file_list: list[str]
    ) -> dict[str, bytes] | None:
        """Prepare file data cache for parallel processing.

        Parameters
        ----------
        archive : Any
            Opened archive object
        archive_type : str
            Type of archive
        file_list : list[str]
            List of files to process

        Returns
        -------
        dict[str, bytes] or None
            Map of file paths to file data, or None if preparation failed

        """
        # For 7z archives, extract all files at once since py7zr.read() consumes the archive
        file_data_cache: dict[str, bytes] = {}
        if archive_type == "7z":
            try:
                data_dict = archive.read(file_list)
                for fname, bio in data_dict.items():
                    if hasattr(bio, "read"):
                        file_data_cache[fname] = bio.read()
                    elif isinstance(bio, bytes):
                        file_data_cache[fname] = bio
                    else:
                        file_data_cache[fname] = b""
            except Exception as e:
                logger.warning(f"Failed to extract 7z files: {e}")
                return None

        # Read all files into memory for parallel processing
        file_data_map: dict[str, bytes] = {}
        for file_path in file_list:
            try:
                # For 7z, use cached data; for others, read directly
                if archive_type == "7z" and file_path in file_data_cache:
                    file_data_map[file_path] = file_data_cache[file_path]
                else:
                    file_data = self._read_archive_file(archive, archive_type, file_path)
                    file_data_map[file_path] = file_data
            except Exception as e:
                logger.warning(f"Failed to read file {file_path}: {e}")
                self._failed_files.append(
                    {
                        "file_path": file_path,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    }
                )

        return file_data_map

    def _execute_parallel_processing(
        self, file_data_map: dict[str, bytes], options_dict: dict[str, Any]
    ) -> dict[str, tuple[Document | None, dict[str, Any] | None]]:
        """Execute parallel processing of archive files.

        Parameters
        ----------
        file_data_map : dict[str, bytes]
            Map of file paths to file data
        options_dict : dict[str, Any]
            Options to pass to worker processes

        Returns
        -------
        dict[str, tuple[Document | None, dict[str, Any] | None]]
            Map of file paths to (document, error_dict) tuples

        """
        max_workers = self.options.max_workers
        results_map: dict[str, tuple[Document | None, dict[str, Any] | None]] = {}

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_file = {}
            for file_path, file_data in file_data_map.items():
                if not file_data and self.options.skip_empty_files:
                    logger.debug(f"Skipping empty file: {file_path}")
                    continue
                future = executor.submit(_process_archive_file_worker, file_path, file_data, options_dict)
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

        return results_map

    def _build_document_from_results(
        self,
        file_list: list[str],
        results_map: dict[str, tuple[Document | None, dict[str, Any] | None]],
        file_data_map: dict[str, bytes],
    ) -> list[Node]:
        """Build document children from processing results.

        Parameters
        ----------
        file_list : list[str]
            Original list of files (for ordering)
        results_map : dict[str, tuple[Document | None, dict[str, Any] | None]]
            Map of file paths to (document, error_dict) tuples
        file_data_map : dict[str, bytes]
            Map of file paths to file data

        Returns
        -------
        list[Node]
            List of document children nodes

        """
        children: list[Node] = []

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

        return children

    def _convert_to_ast_parallel(self, archive: Any, archive_type: str, file_list: list[str]) -> Document:
        """Convert archive to AST using parallel processing.

        Parameters
        ----------
        archive : Any
            Opened archive object
        archive_type : str
            Type of archive
        file_list : list[str]
            List of files to process

        Returns
        -------
        Document
            AST document node

        """
        logger.info(f"Using parallel processing for {len(file_list)} files")

        if not file_list:
            logger.warning("No files to process in archive")
            children: list[Node] = [Paragraph(content=[Text(content="(Empty archive or no matching files)")])]
            return Document(children=children)

        # Prepare options dict for workers
        options_dict = {
            "resource_file_extensions": self.options.resource_file_extensions,
            "attachment_options": self._get_attachment_options_dict(),
        }

        # Prepare file data cache
        file_data_map = self._prepare_file_data_cache(archive, archive_type, file_list)
        if file_data_map is None:
            # Failed to prepare file data (7z extraction error)
            children = [Paragraph(content=[Text(content="(Error extracting archive)")])]
            return Document(children=children)

        # Execute parallel processing
        results_map = self._execute_parallel_processing(file_data_map, options_dict)

        # Build document from results
        children = self._build_document_from_results(file_list, results_map, file_data_map)

        # Add resource manifest if requested and resources were extracted
        if self.options.include_resource_manifest and self.options.extract_resource_files and self._extracted_resources:
            self._add_resource_manifest(children)

        # Add error report if any files failed to process
        if self._failed_files:
            self._add_error_report_table(children)

        return Document(children=children)

    def _get_file_list(self, archive: Any, archive_type: str) -> list[str]:
        """Get filtered list of files to process from archive.

        Parameters
        ----------
        archive : Any
            Opened archive object
        archive_type : str
            Type of archive

        Returns
        -------
        list[str]
            List of file paths to process

        """
        file_list = []

        # Get member list based on archive type
        if archive_type.startswith("tar"):
            members = [m for m in archive.getmembers() if m.isfile()]
            member_names = [m.name for m in members]
        elif archive_type == "7z":
            all_names = archive.getnames()
            # Filter out directories (7z doesn't have a direct isdir check, but dirs end with /)
            member_names = [name for name in all_names if not name.endswith("/")]
        elif archive_type == "rar":
            members = [m for m in archive.infolist() if not m.isdir()]
            member_names = [m.filename for m in members]
        else:
            return []

        for file_path in member_names:
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

    def _read_archive_file(self, archive: Any, archive_type: str, file_path: str) -> bytes:
        """Read a file from the archive.

        Parameters
        ----------
        archive : Any
            Opened archive object
        archive_type : str
            Type of archive
        file_path : str
            Path of file in archive

        Returns
        -------
        bytes
            File content

        """
        if archive_type.startswith("tar"):
            member = archive.getmember(file_path)
            f = archive.extractfile(member)
            if f is None:
                return b""
            return f.read()
        if archive_type == "7z":
            # Extract to memory using readall() which returns dict[filename, BytesIO]
            # py7zr.SevenZipFile.read() extracts files and returns dict of BytesIO objects
            data_dict = archive.read([file_path])
            # The dict maps filename to BytesIO object
            if file_path in data_dict:
                bio = data_dict[file_path]
                if hasattr(bio, "read"):
                    return bio.read()
                # If it's already bytes (older py7zr versions)
                return bio if isinstance(bio, bytes) else b""
            return b""
        if archive_type == "rar":
            return archive.read(file_path)
        return b""

    def _get_attachment_options_dict(self) -> dict[str, Any]:
        """Extract attachment-related options from ArchiveOptions as a dictionary.

        This creates a dictionary of attachment options that can be passed to nested
        parsers when converting files inside archives.

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
        """Create parser options for a nested file with attachment settings from archive options.

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

            # Create parser options with attachment settings from archive options
            parser_options = self._create_nested_parser_options(detected_format)

            # Convert using the detected format with options
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

    def extract_metadata(self, archive: Any) -> DocumentMetadata:
        """Extract metadata from archive.

        Parameters
        ----------
        archive : Any
            Archive object (TarFile, SevenZipFile, or RarFile)

        Returns
        -------
        DocumentMetadata
            Extracted metadata (basic info about the archive)

        """
        metadata = DocumentMetadata()

        # Get archive info based on type (from instance variable)
        archive_type = self._archive_type
        if archive_type.startswith("tar"):
            file_count = len([m for m in archive.getmembers() if m.isfile()])
            if hasattr(archive, "name") and archive.name:
                metadata.title = Path(archive.name).stem
        elif archive_type == "7z":
            all_names = archive.getnames()
            file_count = len([name for name in all_names if not name.endswith("/")])
            if hasattr(archive, "filename") and archive.filename:
                metadata.title = Path(archive.filename).stem
        elif archive_type == "rar":
            file_count = len([m for m in archive.infolist() if not m.isdir()])
            if hasattr(archive, "filename") and archive.filename:
                metadata.title = Path(archive.filename).stem
        else:
            file_count = 0

        # Add archive statistics to custom metadata
        metadata.custom = {"file_count": file_count, "format": archive_type}

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

        except ArchiveSecurityError as e:
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
    format_name="archive",
    extensions=[
        ".tar",
        ".tgz",
        ".tar.gz",
        ".tbz2",
        ".tb2",
        ".tar.bz2",
        ".txz",
        ".tar.xz",
        ".7z",
        ".rar",
    ],
    mime_types=[
        "application/x-tar",
        "application/gzip",
        "application/x-gzip",
        "application/x-bzip2",
        "application/x-xz",
        "application/x-7z-compressed",
        "application/vnd.rar",
        "application/x-rar-compressed",
    ],
    magic_bytes=[
        (b"\x1f\x8b", 0),  # GZIP (tar.gz, .tgz)
        (b"BZ", 0),  # BZIP2 (tar.bz2, .tbz2)
        (b"\xfd7zXZ\x00", 0),  # XZ (tar.xz, .txz)
        (b"7z\xbc\xaf\x27\x1c", 0),  # 7Z
        (b"Rar!\x1a\x07\x00", 0),  # RAR4
        (b"Rar!\x1a\x07\x01\x00", 0),  # RAR5
    ],
    parser_class=ArchiveToAstConverter,
    renderer_class=None,
    parser_required_packages=[],  # tarfile is stdlib
    renderer_required_packages=[],
    optional_packages=[
        ("py7zr", ">=0.22.0"),
        ("rarfile", ">=4.2"),
    ],
    import_error_message="",
    parser_options_class=ArchiveOptions,
    renderer_options_class=None,
    description="Extract and convert files from TAR, 7Z, and RAR archives",
    priority=3,  # Same as ZIP - lower than specific formats to avoid conflicts
)
