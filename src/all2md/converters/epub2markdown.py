#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/epub2markdown.py
"""EPUB to Markdown conversion module.

This module provides functionality to convert EPUB files to Markdown,
preserving the document structure, reading order, and embedded content.
It processes EPUB files by respecting the spine order, converting HTML
content from each chapter, and handling images, links, and footnotes.

The converter uses 'ebooklib' to parse the EPUB container and 'html2markdown'
for the core HTML-to-Markdown conversion of each content document.

Key Features
------------
- Respects reading order defined in the EPUB spine.
- Generates a table of contents from the EPUB's navigation.
- Converts chapter content to Markdown.
- Handles images with support for various output modes (base64, download).
- Converts EPUB footnotes/endnotes to Markdown reference style.
- Preserves hyperlinks.

Dependencies
------------
- ebooklib: For parsing EPUB file structure.
- beautifulsoup4: For pre-processing HTML content before Markdown conversion.
- html2markdown: For converting HTML content to Markdown.
"""

import logging
import os
import re
import tempfile
from collections import OrderedDict
from pathlib import Path, PurePosixPath
from typing import IO, TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    import ebooklib

from all2md.converter_metadata import ConverterMetadata
from all2md.converters.html2markdown import html_to_markdown
from all2md.exceptions import MarkdownConversionError
from all2md.options import EpubOptions, HtmlOptions, MarkdownOptions
from all2md.utils.attachments import process_attachment
from all2md.utils.inputs import format_markdown_heading
from all2md.utils.metadata import DocumentMetadata, prepend_metadata_if_enabled
from all2md.utils.security import validate_zip_archive

logger = logging.getLogger(__name__)


def _build_toc_map(toc: list, epub_module: Any = None) -> dict[str, str]:
    """Recursively build a map of hrefs to chapter titles from the TOC."""
    toc_map = {}
    for item in toc:
        # Check if item has href and title attributes and href is not empty
        if hasattr(item, 'href') and hasattr(item, 'title') and item.href:
            # Clean up href by removing anchor tags
            href = item.href.split("#")[0]
            toc_map[href] = item.title
        elif isinstance(item, tuple) and len(item) == 2:
            # Handle nested sections (Section, [Links])
            section, nested_toc = item
            # Only add section to map if it has a non-empty href
            if hasattr(section, 'href') and hasattr(section, 'title') and section.href:
                href = section.href.split("#")[0]
                toc_map[href] = section.title
            # Always process nested TOC regardless of section type
            toc_map.update(_build_toc_map(nested_toc, epub_module))
    return toc_map


def _slugify(text: str) -> str:
    """Create a simple slug from text for anchor links."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def _preprocess_html(
        html_content: str,
        item: Any,
        book: Any,  # epub.EpubBook when dependencies available
        options: EpubOptions,
) -> tuple[str, list[str]]:
    """Pre-process HTML to handle images and footnotes before Markdown conversion."""
    # Import BeautifulSoup here to handle dependencies gracefully
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # If BeautifulSoup is not available, return unchanged content
        return html_content, []

    soup = BeautifulSoup(html_content, "html.parser")

    # --- Handle Images ---
    current_dir = PurePosixPath(item.get_name()).parent
    for img_tag in soup.find_all("img"):
        # img_tag from find_all could be various types, need to check
        if not hasattr(img_tag, 'get'):
            continue
        src = img_tag.get("src")
        if not src:
            continue

        # Resolve relative path inside the EPUB archive
        # Note: PurePosixPath doesn't have resolve(), so we normalize manually
        # src could be str, list, or other types from AttributeValueList
        src_str = str(src) if not isinstance(src, str) else src
        combined_path = current_dir / src_str
        # Convert to string and normalize any relative components
        resolved_path = str(combined_path).replace("\\", "/")
        # Handle relative path components like '../' manually
        path_parts = resolved_path.split("/")
        normalized_parts: list[str] = []
        for part in path_parts:
            if part == "..":
                if normalized_parts:
                    normalized_parts.pop()
            elif part and part != ".":
                normalized_parts.append(part)
        resolved_path = "/".join(normalized_parts)

        image_item = book.get_item_with_href(resolved_path)
        if image_item:
            image_data = image_item.get_content()
            image_name = Path(image_item.get_name()).name
            alt_attr = img_tag.get("alt", "")
            alt_text = str(alt_attr) if alt_attr else Path(image_name).stem

            markdown_result = process_attachment(
                attachment_data=image_data,
                attachment_name=image_name,
                alt_text=alt_text,
                attachment_mode=options.attachment_mode,
                attachment_output_dir=options.attachment_output_dir,
                attachment_base_url=options.attachment_base_url,
                is_image=True,
                alt_text_mode=options.alt_text_mode,
            )

            # Extract URL from markdown result to update the img tag
            # process_attachment returns markdown like ![alt](url) or ![alt]
            # We need to extract the URL and set it as the src attribute
            if markdown_result.startswith("!["):
                # Parse markdown to extract URL
                # Pattern: ![alt](url) or ![alt](url "title") or ![alt]
                import re
                url_match = re.search(r'!\[([^\]]*)\]\(([^)]+?)\)', markdown_result)
                if url_match:
                    # Found URL - update src attribute
                    extracted_url = url_match.group(2)
                    # Remove title if present (e.g., 'url "title"' -> 'url')
                    extracted_url = extracted_url.split('"')[0].strip()
                    if hasattr(img_tag, '__setitem__'):
                        img_tag["src"] = extracted_url
                elif options.attachment_mode == "skip":
                    # Skip mode - remove the image tag
                    if hasattr(img_tag, 'decompose'):
                        img_tag.decompose()
                else:
                    # Alt-text only (no URL) - remove the image tag
                    if hasattr(img_tag, 'decompose'):
                        img_tag.decompose()
            else:
                # Unexpected format - keep original
                pass
        else:
            logger.warning(f"Could not find image item for src: {src} (resolved to {resolved_path})")

    # --- Handle Footnotes ---
    footnotes: dict[str, str] = OrderedDict()
    # Prioritize standard epub:type attribute
    footnote_refs = soup.find_all("a", attrs={"epub:type": "noteref"})
    if not footnote_refs:  # Fallback for non-standard footnotes
        footnote_refs = soup.find_all("a", href=re.compile(r"#fn|#ftn|#note"))

    for ref in footnote_refs:
        # ref from find_all could be various types, need to check
        if not hasattr(ref, 'get'):
            continue
        href = ref.get("href")
        if not href:
            continue
        # href could be str or AttributeValueList, convert to str
        href_str = str(href) if not isinstance(href, str) else href
        if not href_str.startswith("#"):
            continue

        note_id = href_str[1:]
        note_elem = soup.find(id=note_id)

        if note_elem:
            # Use a simple counter for footnote reference to ensure uniqueness and order
            ref_num = len(footnotes) + 1

            # Extract footnote content and convert it to plain text
            note_text = note_elem.get_text(separator=" ", strip=True)

            # Store the footnote definition for later
            footnotes[str(ref_num)] = f"[^{ref_num}]: {note_text}"

            # Replace the original link with a Markdown footnote reference
            ref.replace_with(f"[^{ref_num}]")

            # Remove the original footnote definition element to avoid duplication
            note_elem.decompose()

    return str(soup), list(footnotes.values())


def extract_epub_metadata(book: Any) -> DocumentMetadata:  # epub.EpubBook when dependencies available
    """Extract metadata from EPUB book.

    Parameters
    ----------
    book : epub.EpubBook
        EPUB book object from ebooklib

    Returns
    -------
    DocumentMetadata
        Extracted metadata
    """
    metadata = DocumentMetadata()

    # Extract Dublin Core metadata
    dc_metadata = book.get_metadata('DC', '')

    # Process each metadata item
    for _namespace, name, value, attrs in dc_metadata:
        if name == 'title':
            metadata.title = value
        elif name == 'creator':
            # EPUB can have multiple creators
            if not metadata.author:
                metadata.author = value
            else:
                # Add to custom if there are multiple authors
                if 'authors' not in metadata.custom:
                    metadata.custom['authors'] = [metadata.author]
                metadata.custom['authors'].append(value)
        elif name == 'description':
            metadata.subject = value
        elif name == 'subject':
            # Subjects as keywords
            if not metadata.keywords:
                metadata.keywords = []
            metadata.keywords.append(value)
        elif name == 'date':
            metadata.creation_date = value
        elif name == 'language':
            metadata.language = value
        elif name == 'publisher':
            metadata.custom['publisher'] = value
        elif name == 'rights':
            metadata.custom['rights'] = value
        elif name == 'identifier':
            # Handle different identifier schemes
            scheme = attrs.get('scheme', 'unknown') if attrs else 'unknown'
            if scheme.lower() == 'isbn':
                metadata.custom['isbn'] = value
            elif scheme.lower() == 'uuid':
                metadata.custom['uuid'] = value
            else:
                metadata.custom[f'identifier_{scheme}'] = value

    # Extract additional metadata
    opf_metadata = book.get_metadata('OPF', '')
    for _namespace, name, _value, attrs in opf_metadata:
        if name == 'meta':
            # Handle OPF meta elements
            if attrs and 'name' in attrs:
                meta_name = attrs['name']
                if meta_name == 'cover' and 'content' in attrs:
                    metadata.custom['cover_id'] = attrs['content']

    # Get chapter/document count
    documents = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    if documents:
        metadata.custom['chapter_count'] = len(documents)

    # Check for images
    images = list(book.get_items_of_type(ebooklib.ITEM_IMAGE))
    if images:
        metadata.custom['image_count'] = len(images)

    # EPUB version
    if hasattr(book, 'version'):
        metadata.custom['epub_version'] = book.version

    return metadata


def epub_to_markdown(
        input_data: Union[str, Path, IO[bytes]], options: EpubOptions | None = None
) -> str:
    """Convert an EPUB file to Markdown format.

    Processes an EPUB file by respecting its reading order (spine), extracting
    content from each chapter, and converting it to Markdown. It handles
    images, links, and footnotes, and can optionally generate a table of contents.

    Parameters
    ----------
    input_data : str, Path, or file-like object
        EPUB file to convert. Can be:
        - String path to EPUB file
        - pathlib.Path object pointing to EPUB file
        - File-like object opened in binary mode
    options : EpubOptions or None, default None
        Configuration options for EPUB conversion. If None, uses default settings.

    Returns
    -------
    str
        Markdown representation of the EPUB document.

    Raises
    ------
    MarkdownConversionError
        If the EPUB file cannot be parsed or processed.
    ImportError
        If required libraries (ebooklib, beautifulsoup4) are not installed.
    """
    # Import dependencies inside function to avoid import-time failures
    try:
        import ebooklib
        from ebooklib import epub
    except ImportError as e:
        from all2md.exceptions import DependencyError
        if "ebooklib" in str(e):
            raise DependencyError(
                converter_name="epub",
                missing_packages=[("ebooklib", "")],
                install_command="pip install ebooklib"
            ) from e
        elif "bs4" in str(e) or "beautifulsoup4" in str(e):
            raise DependencyError(
                converter_name="epub",
                missing_packages=[("beautifulsoup4", "")],
                install_command="pip install beautifulsoup4"
            ) from e
        else:
            # Re-raise if it's a different import error
            raise

    if options is None:
        options = EpubOptions()

    # Handle BytesIO objects by creating a temporary file
    temp_file = None
    try:
        if hasattr(input_data, 'read') and hasattr(input_data, 'seek'):
            # It's a file-like object (BytesIO)
            input_data.seek(0)  # Ensure we're at the beginning
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.epub')
            temp_file.write(input_data.read())
            temp_file.close()
            epub_path = temp_file.name
        else:
            # It's a file path
            epub_path = str(input_data)

        # Validate ZIP archive security (only for real file paths, not temporary files)
        if not hasattr(input_data, 'read') and Path(epub_path).exists():
            try:
                validate_zip_archive(epub_path)
            except Exception as e:
                raise MarkdownConversionError(
                    f"EPUB archive failed security validation: {str(e)}",
                    conversion_stage="archive_validation",
                    original_error=e
                ) from e

        book = epub.read_epub(epub_path)

    except Exception as e:
        raise MarkdownConversionError(
            f"Failed to read or parse EPUB file: {e!r}",
            conversion_stage="document_opening",
            original_error=e,
        ) from e
    finally:
        # Clean up temporary file if created
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass  # Ignore cleanup errors

    # Extract metadata if requested
    metadata = None
    if options.extract_metadata:
        metadata = extract_epub_metadata(book)

    md_options = options.markdown_options or MarkdownOptions()
    html_options = HtmlOptions(
        attachment_mode=options.attachment_mode,
        attachment_output_dir=options.attachment_output_dir,
        attachment_base_url=options.attachment_base_url,
        markdown_options=md_options,
    )

    toc_map = _build_toc_map(book.toc, epub)

    md_toc = ""
    if options.include_toc:
        # Generate a TOC that links to slugified chapter titles
        spine_hrefs = [item.get_name().split("#")[0] for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)]
        toc_titles = [toc_map.get(href) for href in spine_hrefs if toc_map.get(href)]

        md_toc_items = []
        for title in toc_titles:
            if title:  # Only process non-None titles
                md_toc_items.append(f"- [{title}](#{_slugify(title)})")

        if md_toc_items:
            use_hash = options.markdown_options.use_hash_headings if options.markdown_options else True
            toc_heading = format_markdown_heading("Table of Contents", 2, use_hash)
            md_toc = toc_heading + "\n".join(md_toc_items) + "\n\n"

    spine_items = [book.get_item_with_id(item[0]) for item in book.spine]
    all_md_parts = []

    for item in spine_items:
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        try:
            html_content = item.get_content().decode("utf-8")
            processed_html, footnotes = _preprocess_html(html_content, item, book, options)

            clean_href = item.get_name().split("#")[0]
            chapter_title = toc_map.get(clean_href)

            chapter_parts = []
            if chapter_title:
                use_hash = options.markdown_options.use_hash_headings if options.markdown_options else True
                chapter_parts.append(format_markdown_heading(chapter_title, 1, use_hash))

            main_content = html_to_markdown(processed_html, options=html_options)
            chapter_parts.append(main_content)

            if footnotes:
                chapter_parts.append("\n" + "\n".join(footnotes))

            all_md_parts.append("\n".join(chapter_parts))

        except Exception as e:
            logger.error(f"Failed to process chapter {item.get_name()}: {e!r}")
            all_md_parts.append(f"\n\n> [ERROR: Failed to convert chapter: {item.get_name()}]\n\n")

    separator = "\n\n-----\n\n" if not options.merge_chapters and len(all_md_parts) > 1 else "\n\n"
    final_content = separator.join(part.strip() for part in all_md_parts if part.strip())

    result = (md_toc + final_content).strip()

    # Prepend metadata if enabled
    result = prepend_metadata_if_enabled(result, metadata, options.extract_metadata)

    return result


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="epub",
    extensions=[".epub"],
    mime_types=["application/epub+zip"],
    magic_bytes=[
        (b"PK\x03\x04", 0),  # ZIP signature
    ],
    converter_module="all2md.converters.epub2markdown",
    converter_function="epub_to_markdown",
    required_packages=[("ebooklib", ""), ("beautifulsoup4", "")],
    import_error_message=(
        "EPUB conversion requires 'ebooklib' and 'beautifulsoup4'. "
        "Install with: pip install ebooklib beautifulsoup4"
    ),
    options_class="EpubOptions",
    description="Convert EPUB e-books to Markdown",
    priority=6
)
