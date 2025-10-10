"""Output packaging utilities for all2md CLI.

This module provides utilities for creating zip packages of converted documents
directly from memory without intermediate disk I/O.
"""

import logging
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def create_package_from_conversions(
    input_files: List[Path],
    zip_path: Path,
    target_format: str = "markdown",
    options: Optional[Dict[str, Any]] = None,
    transforms: Optional[list] = None,
    source_format: str = "auto"
) -> Path:
    """Create zip package by converting files directly to memory without disk I/O.

    This function converts input files on-the-fly and writes them directly to
    a zip archive using BytesIO buffers, eliminating the need for intermediate
    disk writes. Files are processed one at a time to minimize memory usage.

    Parameters
    ----------
    input_files : List[Path]
        List of input files to convert and package
    zip_path : Path
        Path for the output zip file
    target_format : str, default="markdown"
        Target output format (e.g., "markdown", "html", "pdf")
    options : Dict[str, Any], optional
        Conversion options to pass to convert()
    transforms : list, optional
        AST transforms to apply during conversion
    source_format : str, default="auto"
        Source format (auto-detect if "auto")

    Returns
    -------
    Path
        Path to the created zip file

    Notes
    -----
    This function automatically uses base64 embedding for attachments to keep
    everything in memory. Files are processed incrementally to minimize RAM usage.

    Examples
    --------
    Create a zip of markdown files:

        >>> create_package_from_conversions(
        ...     [Path("doc1.pdf"), Path("doc2.pdf")],
        ...     Path("output.zip"),
        ...     target_format="markdown"
        ... )

    """
    from all2md import convert
    from all2md.converter_registry import registry

    # Get target extension
    if target_format in ('auto', 'markdown'):
        extension = '.md'
    else:
        try:
            metadata_list = registry.get_format_info(target_format)
            if metadata_list and len(metadata_list) > 0:
                metadata = metadata_list[0]
                if metadata.extensions:
                    extension = metadata.extensions[0]
                else:
                    extension = f'.{target_format}'
            else:
                extension = f'.{target_format}'
        except Exception:
            extension = f'.{target_format}'

    # Prepare options with base64 embedding for attachments
    conversion_options = options.copy() if options else {}
    # Force base64 embedding to keep everything in memory
    if 'attachment_mode' not in conversion_options:
        conversion_options['attachment_mode'] = 'base64'

    total_size = 0
    file_count = 0

    # Create zip and process files incrementally
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for input_file in input_files:
            try:
                # Generate output name
                output_name = input_file.stem + extension

                # Convert to BytesIO buffer (always binary)
                # BytesIO doesn't have a 'mode' attribute, so we need to manually
                # set it to indicate binary mode for convert()
                buffer = BytesIO()
                buffer.mode = 'wb'  # type: ignore[misc, attr-defined]
                convert(
                    source=input_file,
                    output=buffer,
                    source_format=source_format,
                    target_format=target_format,
                    transforms=transforms,
                    **conversion_options
                )

                # Write buffer contents to zip
                content_bytes = buffer.getvalue()
                zipf.writestr(output_name, content_bytes)

                total_size += len(content_bytes)
                file_count += 1

                logger.debug(f"Packaged {input_file.name} -> {output_name}")

                # Explicitly release buffer memory
                buffer.close()
                del buffer
                del content_bytes

            except Exception as e:
                logger.warning(f"Failed to convert {input_file}: {e}")
                continue

    # Get final zip size
    zip_size = zip_path.stat().st_size

    # Format sizes for display
    def format_size(size_bytes: int | float) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    logger.info(
        f"Created {zip_path.name} "
        f"({file_count} files, {format_size(zip_size)} compressed from {format_size(total_size)})"
    )

    return zip_path
