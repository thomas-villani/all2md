"""Watch mode implementation for all2md CLI.

This module provides file system monitoring for automatic conversion of files
when they change. Supports bidirectional conversion between any formats.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from all2md.api import convert
from all2md.cli.builder import EXIT_DEPENDENCY_ERROR
from all2md.cli.processors import generate_output_path
from all2md.constants import IMAGE_EXTENSIONS, DocumentFormat
from all2md.converter_registry import registry
from all2md.exceptions import All2MdError

try:
    from watchdog.events import FileSystemEventHandler
except ImportError:
    # Stub for when watchdog is not installed
    class FileSystemEventHandler:  # type: ignore
        """Stub class when watchdog is not installed."""

        pass


logger = logging.getLogger(__name__)


class ConversionEventHandler(FileSystemEventHandler):
    """File system event handler for watch mode.

    Parameters
    ----------
    paths_to_watch : List[Path]
        Paths to monitor (files or directories)
    output_dir : Path
        Directory to write converted files
    options : Dict[str, Any]
        Conversion options
    format_arg : str
        Source format specification
    target_format : DocumentFormat, default "markdown"
        Target output format
    output_extension : str, optional
        Custom output file extension (overrides target_format default)
    transforms : list, optional
        Transform instances to apply
    debounce_seconds : float, default 1.0
        Debounce delay in seconds
    preserve_structure : bool, default False
        Whether to preserve directory structure
    recursive : bool, default False
        Whether to watch directories recursively
    exclude_patterns : List[str], optional
        Patterns to exclude from processing

    """

    def __init__(
        self,
        paths_to_watch: List[Path],
        output_dir: Path,
        options: Dict[str, Any],
        format_arg: DocumentFormat,
        target_format: DocumentFormat = "markdown",
        output_extension: Optional[str] = None,
        transforms: Optional[list] = None,
        debounce_seconds: float = 1.0,
        preserve_structure: bool = False,
        recursive: bool = False,
        exclude_patterns: Optional[List[str]] = None,
    ) -> None:
        """Initialize the conversion event handler with watch settings."""
        self.paths_to_watch = paths_to_watch
        self.output_dir = output_dir
        self.options = options
        self.format_arg: DocumentFormat = format_arg
        self.target_format: DocumentFormat = target_format
        self.output_extension = output_extension
        self.transforms = transforms
        self.debounce_seconds = debounce_seconds
        self.preserve_structure = preserve_structure
        self.recursive = recursive
        self.exclude_patterns = exclude_patterns or []

        # Debouncing state
        self._last_processed: Dict[str, float] = {}
        self._processing: Set[str] = set()

        # Determine base directory for structure preservation
        self.base_dir: Optional[Path] = None
        if preserve_structure and paths_to_watch:
            # Use the first directory as base
            for path in paths_to_watch:
                if path.is_dir():
                    self.base_dir = path
                    break
            if self.base_dir is None:
                # All paths are files, use their common parent

                self.base_dir = Path(os.path.commonpath([p.parent for p in paths_to_watch]))

    def should_process(self, file_path: str) -> bool:
        """Check if file should be processed.

        Parameters
        ----------
        file_path : str
            Path to the file

        Returns
        -------
        bool
            True if file should be processed

        """
        path = Path(file_path)

        # Skip if already processing
        if file_path in self._processing:
            logger.debug(f"Skipping {file_path}: already processing")
            return False

        # Check extension - use supported extensions dynamically from registry
        supported_extensions = registry.get_all_extensions()
        # Add IMAGE_EXTENSIONS for watch mode (images can be converted)
        all_extensions = supported_extensions | set(IMAGE_EXTENSIONS)

        if path.suffix.lower() not in all_extensions:
            logger.debug(f"Skipping {file_path}: unsupported extension")
            return False

        # Check exclude patterns
        if self.exclude_patterns:

            for pattern in self.exclude_patterns:
                if fnmatch.fnmatch(str(path), pattern) or fnmatch.fnmatch(path.name, pattern):
                    logger.debug(f"Skipping {file_path}: matches exclude pattern {pattern}")
                    return False

        # Check debounce
        now = time.time()
        last_processed = self._last_processed.get(file_path, 0)

        if now - last_processed < self.debounce_seconds:
            logger.debug(f"Skipping {file_path}: debounce delay not met")
            return False

        return True

    def convert_file(self, file_path: str) -> None:
        """Convert a single file.

        Parameters
        ----------
        file_path : str
            Path to the file to convert

        """
        path = Path(file_path)

        if not path.exists():
            logger.warning(f"File does not exist: {file_path}")
            return

        try:
            # Mark as processing
            self._processing.add(file_path)

            # Determine output path with target format
            output_path = generate_output_path(
                path, self.output_dir, self.preserve_structure, self.base_dir, target_format=self.target_format
            )

            # Apply custom output extension if specified
            if self.output_extension:
                output_path = output_path.with_suffix(self.output_extension)

            # Convert
            logger.info(f"Converting {file_path} to {self.target_format}...")
            start_time = time.time()

            # Use convert() API for bidirectional conversion
            convert(
                path,
                output=output_path,
                source_format=self.format_arg,
                target_format=self.target_format,
                transforms=self.transforms,
                **self.options,
            )

            elapsed = time.time() - start_time
            logger.info(f"Converted {file_path} -> {output_path} ({elapsed:.2f}s)")

            # Update last processed time
            self._last_processed[file_path] = time.time()

        except All2MdError as e:
            logger.error(f"Conversion error for {file_path}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error converting {file_path}: {e}")
        finally:
            # Remove from processing set
            self._processing.discard(file_path)

    def on_modified(self, event: Any) -> None:
        """Handle file modification events.

        Parameters
        ----------
        event : FileSystemEvent
            The file system event

        """
        if event.is_directory:
            return

        if self.should_process(event.src_path):
            self.convert_file(event.src_path)

    def on_created(self, event: Any) -> None:
        """Handle file creation events.

        Parameters
        ----------
        event : FileSystemEvent
            The file system event

        """
        if event.is_directory:
            return

        if self.should_process(event.src_path):
            self.convert_file(event.src_path)

    def on_moved(self, event: Any) -> None:
        """Handle file move events.

        Parameters
        ----------
        event : FileSystemEvent
            The file system event

        """
        if event.is_directory:
            return

        # Process the destination path
        if self.should_process(event.dest_path):
            self.convert_file(event.dest_path)


def run_watch_mode(
    paths: List[Path],
    output_dir: Path,
    options: Dict[str, Any],
    format_arg: DocumentFormat,
    target_format: DocumentFormat = "markdown",
    output_extension: Optional[str] = None,
    transforms: Optional[list] = None,
    debounce: float = 1.0,
    preserve_structure: bool = False,
    recursive: bool = False,
    exclude_patterns: Optional[List[str]] = None,
) -> int:
    """Run watch mode to monitor and convert files on change.

    Supports bidirectional conversion between any formats using the convert() API.

    Parameters
    ----------
    paths : List[Path]
        Paths to monitor (files or directories)
    output_dir : Path
        Directory to write converted files
    options : Dict[str, Any]
        Conversion options
    format_arg : DocumentFormat
        Source format specification
    target_format : DocumentFormat, default "markdown"
        Target output format for conversion
    output_extension : str, optional
        Custom output file extension (overrides target_format default)
    transforms : list, optional
        Transform instances to apply
    debounce : float, default 1.0
        Debounce delay in seconds
    preserve_structure : bool, default False
        Whether to preserve directory structure
    recursive : bool, default False
        Whether to watch directories recursively
    exclude_patterns : List[str], optional
        Patterns to exclude from processing

    Returns
    -------
    int
        Exit code (0 for success)

    """
    try:
        from watchdog.observers import Observer
    except ImportError:
        logger.error("Watch mode (--watch) requires the watchdog library. Install with: pip install all2md[cli_extras]")
        return EXIT_DEPENDENCY_ERROR

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create event handler
    handler = ConversionEventHandler(
        paths_to_watch=paths,
        output_dir=output_dir,
        options=options,
        format_arg=format_arg,
        target_format=target_format,
        output_extension=output_extension,
        transforms=transforms,
        debounce_seconds=debounce,
        preserve_structure=preserve_structure,
        recursive=recursive,
        exclude_patterns=exclude_patterns,
    )

    # Set up observer
    observer = Observer()

    # Schedule observers for each path
    for path in paths:
        if path.is_dir():
            observer.schedule(handler, str(path), recursive=recursive)
            logger.info(f"Watching directory: {path} (recursive: {recursive})")
        elif path.is_file():
            # Watch the parent directory but only process this specific file
            observer.schedule(handler, str(path.parent), recursive=False)
            logger.info(f"Watching file: {path}")
        else:
            logger.warning(f"Path does not exist: {path}")

    # Start observer
    observer.start()

    print(f"Watch mode active. Monitoring {len(paths)} path(s). Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping watch mode...")
        observer.stop()

    observer.join()
    logger.info("Watch mode stopped")
    return 0
