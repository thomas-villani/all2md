#  Copyright (c) 2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the “Software”), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the “Software”), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
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
from typing import IO, Any, Union

# Try to import dependencies and raise helpful errors
try:
    import ebooklib
    from ebooklib import epub
except ImportError as e:
    raise ImportError("`ebooklib` is required for EPUB conversion. Install with: `pip install ebooklib`") from e

try:
    from bs4 import BeautifulSoup
except ImportError as e:
    raise ImportError(
        "`beautifulsoup4` is required for EPUB conversion. Install with: `pip install beautifulsoup4`") from e

from all2md.utils.attachments import process_attachment
from all2md.exceptions import MarkdownConversionError
from all2md.converters.html2markdown import html_to_markdown
from all2md.options import EpubOptions, HtmlOptions, MarkdownOptions

logger = logging.getLogger(__name__)


def _build_toc_map(toc: list) -> dict[str, str]:
    """Recursively build a map of hrefs to chapter titles from the TOC."""
    toc_map = {}
    for item in toc:
        if isinstance(item, epub.Link):
            # Clean up href by removing anchor tags
            href = item.href.split("#")[0]
            toc_map[href] = item.title
        elif isinstance(item, tuple) and len(item) == 2:
            # Handle nested sections
            section, nested_toc = item
            if isinstance(section, epub.Link):
                href = section.href.split("#")[0]
                toc_map[href] = section.title
            toc_map.update(_build_toc_map(nested_toc))
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
        book: epub.EpubBook,
        options: EpubOptions,
) -> tuple[str, list[str]]:
    """Pre-process HTML to handle images and footnotes before Markdown conversion."""
    soup = BeautifulSoup(html_content, "html.parser")

    # --- Handle Images ---
    current_dir = PurePosixPath(item.get_name()).parent
    for img_tag in soup.find_all("img"):
        src = img_tag.get("src")
        if not src:
            continue

        # Resolve relative path inside the EPUB archive
        # Note: PurePosixPath doesn't have resolve(), so we normalize manually
        combined_path = current_dir / src
        # Convert to string and normalize any relative components
        resolved_path = str(combined_path).replace("\\", "/")
        # Handle relative path components like '../' manually
        path_parts = resolved_path.split("/")
        normalized_parts = []
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
            alt_text = img_tag.get("alt", "") or Path(image_name).stem

            new_src = process_attachment(
                attachment_data=image_data,
                attachment_name=image_name,
                alt_text=alt_text,
                attachment_mode=options.attachment_mode,
                attachment_output_dir=options.attachment_output_dir,
                attachment_base_url=options.attachment_base_url,
                is_image=True,
            )
            # If process_attachment returns a full markdown string, replace the tag entirely
            if new_src.startswith("!["):
                img_tag.replace_with(new_src)
            else:  # Otherwise, just update the src attribute
                img_tag["src"] = new_src
        else:
            logger.warning(f"Could not find image item for src: {src} (resolved to {resolved_path})")

    # --- Handle Footnotes ---
    footnotes = OrderedDict()
    # Prioritize standard epub:type attribute
    footnote_refs = soup.find_all("a", attrs={"epub:type": "noteref"})
    if not footnote_refs:  # Fallback for non-standard footnotes
        footnote_refs = soup.find_all("a", href=re.compile(r"#fn|#ftn|#note"))

    for ref in footnote_refs:
        href = ref.get("href")
        if not href or not href.startswith("#"):
            continue

        note_id = href[1:]
        note_elem = soup.find(id=note_id)

        if note_elem:
            # Use a simple counter for footnote reference to ensure uniqueness and order
            ref_num = len(footnotes) + 1

            # Extract footnote content and convert it to plain text
            note_text = note_elem.get_text(separator=" ", strip=True)

            # Store the footnote definition for later
            footnotes[ref_num] = f"[^{ref_num}]: {note_text}"

            # Replace the original link with a Markdown footnote reference
            ref.replace_with(f"[^{ref_num}]")

            # Remove the original footnote definition element to avoid duplication
            note_elem.decompose()

    return str(soup), list(footnotes.values())


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
            epub_path = input_data

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

    md_options = options.markdown_options or MarkdownOptions()
    html_options = HtmlOptions(
        attachment_mode=options.attachment_mode,
        attachment_output_dir=options.attachment_output_dir,
        attachment_base_url=options.attachment_base_url,
        markdown_options=md_options,
    )

    toc_map = _build_toc_map(book.toc)

    md_toc = ""
    if options.include_toc:
        # Generate a TOC that links to slugified chapter titles
        spine_hrefs = [item.get_name().split("#")[0] for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)]
        toc_titles = [toc_map.get(href) for href in spine_hrefs if toc_map.get(href)]

        md_toc_items = []
        for title in toc_titles:
            md_toc_items.append(f"- [{title}](#{_slugify(title)})")

        if md_toc_items:
            md_toc = "## Table of Contents\n\n" + "\n".join(md_toc_items) + "\n\n"

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
                chapter_parts.append(f"# {chapter_title}\n")

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

    return (md_toc + final_content).strip()