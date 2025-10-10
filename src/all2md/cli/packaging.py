"""Output packaging utilities for all2md CLI.

This module provides utilities for packaging conversion outputs including
zip creation and asset organization.
"""

import logging
import os
import re
import zipfile
from pathlib import Path
from typing import List, Literal, Optional, Tuple

logger = logging.getLogger(__name__)

AssetLayout = Literal["flat", "by-stem", "structured"]


def organize_assets(
    markdown_files: List[Path],
    output_dir: Path,
    layout: AssetLayout = "flat",
    attachment_dir: Optional[Path] = None
) -> dict[Path, Path]:
    """Organize assets according to specified layout.

    Works with any output format (markdown, HTML, PDF, etc.) to organize
    associated image and attachment files.

    Parameters
    ----------
    markdown_files : List[Path]
        List of generated output files (parameter name kept for backward compatibility,
        but works with any format)
    output_dir : Path
        Output directory containing files
    layout : AssetLayout, default "flat"
        Layout strategy: flat, by-stem, or structured
    attachment_dir : Path, optional
        Directory containing attachments (if separate from output_dir)

    Returns
    -------
    dict[Path, Path]
        Mapping of original asset paths to new organized paths

    """
    asset_mapping: dict[Path, Path] = {}

    # Find all asset files referenced in markdown files
    attachment_root = attachment_dir if attachment_dir else output_dir

    if not attachment_root.exists():
        logger.debug(f"Attachment directory does not exist: {attachment_root}")
        return asset_mapping

    # Collect all asset files (images and common attachment types)
    asset_extensions = {
        '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp',  # Images
        '.pdf', '.txt', '.csv', '.json', '.xml'  # Common attachments
    }
    all_assets: list[Path] = []

    for ext in asset_extensions:
        all_assets.extend(attachment_root.rglob(f'*{ext}'))

    if not all_assets:
        logger.debug("No assets found to organize")
        return asset_mapping

    if layout == "flat":
        # All assets in single assets/ directory
        assets_dir = output_dir / "assets"
        assets_dir.mkdir(exist_ok=True, parents=True)

        for asset in all_assets:
            # Generate unique name if conflicts exist
            new_path = assets_dir / asset.name
            counter = 1
            # Check if path is already in mapping values or exists on disk
            while new_path in asset_mapping.values() or (new_path.exists() and new_path != asset):
                stem = asset.stem
                suffix = asset.suffix
                new_path = assets_dir / f"{stem}_{counter}{suffix}"
                counter += 1

            asset_mapping[asset] = new_path

    elif layout == "by-stem":
        # Organize as assets/{markdown_stem}/image.png
        for md_file in markdown_files:
            md_stem = md_file.stem
            assets_dir = output_dir / "assets" / md_stem
            assets_dir.mkdir(exist_ok=True, parents=True)

            # Find assets that belong to this markdown file
            # This is heuristic-based on the asset name containing the md stem
            for asset in all_assets:
                if md_stem in asset.stem or asset.parent.name == md_stem:
                    new_path = assets_dir / asset.name
                    counter = 1
                    # Check if path is already in mapping values or exists on disk
                    while new_path in asset_mapping.values() or (new_path.exists() and new_path != asset):
                        stem = asset.stem
                        suffix = asset.suffix
                        new_path = assets_dir / f"{stem}_{counter}{suffix}"
                        counter += 1

                    asset_mapping[asset] = new_path

    elif layout == "structured":
        # Preserve original directory structure relative to output_dir
        for asset in all_assets:
            try:
                relative_path = asset.relative_to(output_dir)
                new_path = output_dir / relative_path
                asset_mapping[asset] = new_path
            except ValueError:
                # Asset is outside output_dir, put in assets/
                assets_dir = output_dir / "assets"
                assets_dir.mkdir(exist_ok=True, parents=True)
                new_path = assets_dir / asset.name
                asset_mapping[asset] = new_path

    return asset_mapping


def update_markdown_asset_links(
    markdown_file: Path,
    asset_mapping: dict[Path, Path],
    output_dir: Path
) -> None:
    """Update asset links in markdown file to point to new organized locations.

    Parameters
    ----------
    markdown_file : Path
        Markdown file to update
    asset_mapping : dict[Path, Path]
        Mapping of original asset paths to new locations
    output_dir : Path
        Output directory (for calculating relative paths)

    """
    if not markdown_file.exists():
        return

    content = markdown_file.read_text(encoding='utf-8')
    modified = False

    # Find all image references: ![alt](path) and <img src="path">
    img_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    html_img_pattern = r'<img\s+[^>]*src=["\']([^"\']+)["\']'

    def replace_link(match: re.Match) -> str:
        nonlocal modified
        if len(match.groups()) == 2:
            # Markdown image: ![alt](path)
            alt_text = match.group(1)
            img_path = match.group(2)
        else:
            # HTML img: src="path"
            img_path = match.group(1)
            alt_text = ""

        # Skip data URLs and external URLs
        if img_path.startswith(('data:', 'http://', 'https://')):
            return match.group(0)

        # Resolve the image path relative to markdown file
        try:
            resolved_path = (markdown_file.parent / img_path).resolve()

            # Check if this path is in our asset mapping
            if resolved_path in asset_mapping:
                new_path = asset_mapping[resolved_path]
                # Calculate relative path from markdown file to new location
                try:
                    relative_new_path = os.path.relpath(new_path, markdown_file.parent)
                    modified = True

                    if len(match.groups()) == 2:
                        return f'![{alt_text}]({relative_new_path})'
                    else:
                        return match.group(0).replace(img_path, relative_new_path)
                except ValueError:
                    # Paths on different drives on Windows
                    pass
        except Exception as e:
            logger.debug(f"Could not resolve asset path {img_path}: {e}")

        return match.group(0)

    # Replace markdown images
    content = re.sub(img_pattern, replace_link, content)

    # Replace HTML img tags
    content = re.sub(html_img_pattern, replace_link, content)

    if modified:
        markdown_file.write_text(content, encoding='utf-8')
        logger.debug(f"Updated asset links in {markdown_file}")


def create_output_zip(
    output_dir: Path,
    zip_path: Optional[Path] = None,
    output_files: Optional[List[Path]] = None,
    asset_files: Optional[List[Path]] = None,
    output_extension: str = ".md",
    markdown_files: Optional[List[Path]] = None
) -> Path:
    """Create a zip archive of conversion output.

    Supports all output formats by accepting any file extension. Works with
    both text-based formats (markdown, HTML, etc.) and binary formats (PDF, DOCX, etc.).

    Parameters
    ----------
    output_dir : Path
        Directory containing conversion output
    zip_path : Path, optional
        Path for the output zip file. If None, uses output_dir.zip
    output_files : List[Path], optional
        Specific output files to include. If None, includes all files with output_extension
    asset_files : List[Path], optional
        Specific asset files to include. If None, includes all common image/attachment formats
    output_extension : str, default=".md"
        File extension for output files to include (e.g., ".md", ".html", ".pdf")
    markdown_files : List[Path], optional
        Deprecated. Use output_files instead. Maintained for backward compatibility.

    Returns
    -------
    Path
        Path to the created zip file

    Raises
    ------
    ValueError
        If output_dir doesn't exist

    """
    if not output_dir.exists():
        raise ValueError(f"Output directory does not exist: {output_dir}")

    # Backward compatibility: support markdown_files parameter
    if markdown_files is not None and output_files is None:
        output_files = markdown_files

    # Determine zip file path
    if zip_path is None:
        zip_path = output_dir.parent / f"{output_dir.name}.zip"

    # Collect files to include
    files_to_zip: List[Tuple[Path, str]] = []

    if output_files is None:
        # Include all files with the specified extension in output_dir
        output_files = list(output_dir.rglob(f"*{output_extension}"))

    if asset_files is None:
        # Include all common image and attachment formats
        asset_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp', '.pdf', '.txt', '.csv'}
        asset_files = []
        for ext in asset_extensions:
            asset_files.extend(output_dir.rglob(f'*{ext}'))

    # Add output files with their relative paths
    for out_file in output_files:
        try:
            relative_path = out_file.relative_to(output_dir)
            files_to_zip.append((out_file, str(relative_path)))
        except ValueError:
            # File is outside output_dir, skip
            logger.warning(f"Skipping file outside output directory: {out_file}")

    # Add asset files with their relative paths
    for asset_file in asset_files:
        try:
            relative_path = asset_file.relative_to(output_dir)
            files_to_zip.append((asset_file, str(relative_path)))
        except ValueError:
            logger.warning(f"Skipping asset outside output directory: {asset_file}")

    # Create zip file
    total_size = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path, archive_name in files_to_zip:
            zipf.write(file_path, archive_name)
            total_size += file_path.stat().st_size

    # Get zip file size
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
        f"({len(files_to_zip)} files, {format_size(zip_size)} compressed from {format_size(total_size)})"
    )

    return zip_path
