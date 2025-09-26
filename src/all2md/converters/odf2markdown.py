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
# src/all2md/converters/odf2markdown.py


"""OpenDocument to Markdown conversion module.

This module provides functionality to convert OpenDocument Text (ODT) and
Presentation (ODP) files to Markdown. It processes the document's XML
structure to preserve formatting, tables, lists, and images.

The converter uses the odfpy library to parse the OpenDocument format
natively, mapping elements like paragraphs, headings, lists, tables, and
images to their Markdown equivalents.

Key Features
------------
- Text formatting preservation (bold, italic)
- Heading level detection from document structure
- List conversion (bulleted and numbered) with nesting
- Table structure preservation
- Image extraction and handling via the unified attachment system

Dependencies
------------
- odfpy: For parsing OpenDocument file structure
- logging: For debug and error reporting

Examples
--------
Basic conversion:

    >>> from all2md.converters.odf2markdown import odf_to_markdown
    >>> with open('document.odt', 'rb') as f:
    ...     markdown = odf_to_markdown(f)
    >>> print(markdown)

Note
----
Requires the odfpy package. Some advanced OpenDocument features may not have
direct Markdown equivalents and will be approximated or omitted.
"""

import logging
import re
from pathlib import Path
from typing import IO, Union

from odf import draw, opendocument, table, text
from odf.draw import DRAWNS
from odf.element import Element
from odf.style import STYLENS
from odf.table import TABLENS
from odf.text import TEXTNS

from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import MarkdownConversionError
from all2md.options import MarkdownOptions, OdfOptions
from all2md.utils.attachments import process_attachment
from all2md.utils.metadata import DocumentMetadata, prepend_metadata_if_enabled
from all2md.utils.security import validate_zip_archive

logger = logging.getLogger(__name__)


class OdfConverter:
    """Stateful converter for ODF documents."""

    def __init__(self, doc: opendocument.OpenDocument, options: OdfOptions):
        self.doc = doc
        self.options = options
        self.md_options = options.markdown_options or MarkdownOptions()
        self.style_cache: dict[str, dict[str, bool]] = {}
        self.list_level = 0

    def _get_style_properties(self, style_name: str) -> dict[str, bool]:
        """Get and cache formatting properties (bold, italic) for a given style."""
        if style_name in self.style_cache:
            return self.style_cache[style_name]

        properties = {"bold": False, "italic": False}
        try:
            style = self.doc.styles.getStyleByName(style_name)
            if style:
                for child in style.childNodes:
                    if hasattr(child, 'qname') and child.qname == (STYLENS, 'text-properties'):
                        if child.getAttribute("fontweight") == "bold":
                            properties["bold"] = True
                        if child.getAttribute("fontstyle") == "italic":
                            properties["italic"] = True
        except Exception as e:
            logger.debug(f"Error during style parsing, using defaults. Error: {e!r}", exc_info=e)
            # Style not found or error parsing, use defaults
            pass

        self.style_cache[style_name] = properties
        return properties

    def _process_text_runs(self, element: Element) -> str:
        """Process an element's children, handling text and formatted spans."""
        parts = []
        for node in element.childNodes:
            if node.nodeType == node.TEXT_NODE:
                parts.append(str(node.data))
            elif hasattr(node, 'qname') and node.qname == (TEXTNS, 'span'):
                content = self._process_text_runs(node)
                style_name = node.getAttribute("stylename")
                if style_name:
                    props = self._get_style_properties(style_name)
                    if props["bold"]:
                        content = f"**{content}**"
                    if props["italic"]:
                        content = f"*{content}*"
                parts.append(content)
            elif hasattr(node, 'qname') and node.qname == (TEXTNS, 'a'):  # Handle hyperlinks
                href = node.getAttribute("href")
                link_text = self._process_text_runs(node)
                if href and link_text:
                    parts.append(f"[{link_text}]({href})")
            elif hasattr(node, 'qname') and node.qname == (TEXTNS, 's'):  # Handle spaces
                parts.append(" ")
        return "".join(parts)

    def _process_paragraph(self, p: Union[text.P, text.H]) -> str:
        """Convert a paragraph or heading element to Markdown."""
        content = self._process_text_runs(p).strip()
        if not content:
            return ""

        if hasattr(p, 'qname') and p.qname == (TEXTNS, 'h'):
            level = int(p.getAttribute("outlinelevel") or 1)
            return f"{'#' * level} {content}"

        return content

    def _process_list(self, lst: text.List) -> str:
        """Convert a list element to Markdown, handling nesting."""
        self.list_level += 1
        lines = []
        # Detect if it's ordered by checking the list style
        is_ordered = self._is_ordered_list(lst)

        for i, item in enumerate(lst.childNodes):
            if not hasattr(item, 'qname') or item.qname != (TEXTNS, 'list-item'):
                continue
            item_content = []
            for element in item.childNodes:
                if hasattr(element, 'qname'):
                    if element.qname == (TEXTNS, 'p'):
                        item_content.append(self._process_paragraph(element))
                    elif element.qname == (TEXTNS, 'list'):
                        item_content.append(self._process_list(element))

            full_content = "\n".join(item_content)
            indent = "  " * (self.list_level - 1)
            marker = f"{i + 1}." if is_ordered else "*"
            lines.append(f"{indent}{marker} {full_content}")

        self.list_level -= 1
        return "\n".join(lines)

    def _process_table(self, tbl: table.Table) -> str:
        """Convert a table element to a Markdown table."""
        if not self.options.preserve_tables:
            return ""

        md_rows = []
        rows = tbl.getElementsByType(table.TableRow)

        if not rows:
            return ""

        # Process header
        header_cells = rows[0].getElementsByType(table.TableCell)
        header_content = [self._process_element(cell).replace("\n", " ") for cell in header_cells]
        md_rows.append("| " + " | ".join(header_content) + " |")
        md_rows.append("| " + " | ".join(["---"] * len(header_content)) + " |")

        # Process data rows
        for row in rows[1:]:
            data_cells = row.getElementsByType(table.TableCell)
            data_content = [self._process_element(cell).replace("\n", " ") for cell in data_cells]
            md_rows.append("| " + " | ".join(data_content) + " |")

        return "\n".join(md_rows)

    def _process_image(self, frame: draw.Frame) -> str:
        """Extract and process an image."""
        image_element = frame.getElementsByType(draw.Image)
        if not image_element:
            return ""

        href = image_element[0].getAttribute("href")
        if not href:
            return ""

        try:
            # odfpy stores parts in a dict-like object
            image_data = self.doc.getPart(href)
        except KeyError:
            logger.warning(f"Image not found in ODF package: {href}")
            return ""

        alt_text = "image"
        # Note: Title and Desc elements may not be available in all ODF implementations
        # Using a simple default alt text for now

        return process_attachment(
            attachment_data=image_data,
            attachment_name=href.split("/")[-1],
            alt_text=alt_text,
            attachment_mode=self.options.attachment_mode,
            attachment_output_dir=self.options.attachment_output_dir,
            attachment_base_url=self.options.attachment_base_url,
            is_image=True,
            alt_text_mode=self.options.alt_text_mode,
        )

    def _process_element(self, element: Element) -> str:
        """Recursively process an ODF element and its children."""
        if hasattr(element, 'qname'):
            qname = element.qname
            if qname == (TEXTNS, 'p') or qname == (TEXTNS, 'h'):
                return self._process_paragraph(element)
            elif qname == (TEXTNS, 'list'):
                return self._process_list(element)
            elif qname == (TABLENS, 'table'):
                return self._process_table(element)
            elif qname == (DRAWNS, 'frame'):
                return self._process_image(element)
        if hasattr(element, "childNodes"):
            return "\n".join(self._process_element(child) for child in element.childNodes)
        return ""

    def convert(self) -> str:
        """Perform the conversion of the entire document."""
        markdown_lines = []
        # For ODT, content is in doc.text. For ODP, it's in doc.presentation
        content_root = self.doc.text if hasattr(self.doc, 'text') else self.doc.presentation

        for element in content_root.childNodes:
            result = self._process_element(element).strip()
            if result:
                markdown_lines.append(result)

        # Clean up multiple blank lines
        markdown = "\n\n".join(markdown_lines)
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)
        return markdown.strip()

    def _is_ordered_list(self, lst: text.List) -> bool:
        """Determine if a list is ordered by examining its style."""
        style_name = lst.getAttribute("stylename")
        if not style_name:
            return False

        # Look up the list style in automatic styles
        auto_styles = self.doc.automaticstyles
        if hasattr(auto_styles, 'childNodes'):
            for style in auto_styles.childNodes:
                if (hasattr(style, 'getAttribute') and hasattr(style, 'qname') and
                        style.qname == (TEXTNS, 'list-style')):
                    try:
                        if style.getAttribute('name') == style_name:
                            # Check the first level style to determine list type
                            for child in style.childNodes:
                                if hasattr(child, 'qname'):
                                    if child.qname == (TEXTNS, 'list-level-style-number'):
                                        return True  # It's a numbered list
                                    elif child.qname == (TEXTNS, 'list-level-style-bullet'):
                                        return False  # It's a bulleted list
                    except Exception:
                        continue

        # Fallback: assume unordered if we can't determine
        return False


def extract_odf_metadata(doc: opendocument.OpenDocument) -> DocumentMetadata:
    """Extract metadata from ODF document.

    Parameters
    ----------
    doc : opendocument.OpenDocument
        ODF document object from odfpy

    Returns
    -------
    DocumentMetadata
        Extracted metadata
    """
    metadata = DocumentMetadata()

    # Access document metadata
    if hasattr(doc, 'meta'):
        meta = doc.meta

        # Extract Dublin Core metadata
        if hasattr(meta, 'getElementsByType'):
            from odf.dc import Creator, Description, Language, Subject, Title
            from odf.meta import CreationDate, Generator, InitialCreator, Keyword

            # Title
            titles = meta.getElementsByType(Title)
            if titles:
                metadata.title = str(titles[0]).strip()

            # Creator/Author
            creators = meta.getElementsByType(Creator)
            if creators:
                metadata.author = str(creators[0]).strip()
            else:
                # Try initial creator
                initial_creators = meta.getElementsByType(InitialCreator)
                if initial_creators:
                    metadata.author = str(initial_creators[0]).strip()

            # Description/Subject
            descriptions = meta.getElementsByType(Description)
            if descriptions:
                metadata.subject = str(descriptions[0]).strip()
            else:
                subjects = meta.getElementsByType(Subject)
                if subjects:
                    metadata.subject = str(subjects[0]).strip()

            # Keywords
            keywords = meta.getElementsByType(Keyword)
            if keywords:
                # ODF can have multiple keyword elements
                keyword_list = []
                for kw in keywords:
                    kw_text = str(kw).strip()
                    if kw_text:
                        # Split by common delimiters
                        import re
                        parts = [k.strip() for k in re.split('[,;]', kw_text) if k.strip()]
                        keyword_list.extend(parts)
                if keyword_list:
                    metadata.keywords = keyword_list

            # Creation date
            creation_dates = meta.getElementsByType(CreationDate)
            if creation_dates:
                metadata.creation_date = str(creation_dates[0]).strip()

            # Generator (application)
            generators = meta.getElementsByType(Generator)
            if generators:
                metadata.creator = str(generators[0]).strip()

            # Language
            languages = meta.getElementsByType(Language)
            if languages:
                metadata.language = str(languages[0]).strip()

    # Document type and statistics
    if hasattr(doc, 'mimetype'):
        doc_type = 'presentation' if 'presentation' in doc.mimetype else 'text'
        metadata.custom['document_type'] = doc_type

    # Count pages/slides if it's a presentation
    if hasattr(doc, 'body'):
        try:
            from odf.draw import Page
            pages = doc.body.getElementsByType(Page)
            if pages:
                metadata.custom['page_count'] = len(pages)
        except Exception:
            pass

        # Count paragraphs for text documents
        try:
            from odf.text import P
            paragraphs = doc.body.getElementsByType(P)
            if paragraphs:
                metadata.custom['paragraph_count'] = len(paragraphs)
        except Exception:
            pass

        # Count tables
        try:
            from odf.table import Table
            tables = doc.body.getElementsByType(Table)
            if tables:
                metadata.custom['table_count'] = len(tables)
        except Exception:
            pass

    return metadata


def odf_to_markdown(
        input_data: Union[str, Path, IO[bytes]], options: OdfOptions | None = None
) -> str:
    """Convert OpenDocument file (ODT, ODP) to Markdown format.

    Processes OpenDocument files by parsing their XML structure and converting
    content to well-formatted Markdown, preserving text formatting, tables,
    lists, and embedded images.

    Parameters
    ----------
    input_data : str or file-like object
        OpenDocument file to convert. Can be:
        - String path to ODT/ODP file
        - File-like object containing ODT/ODP data
    options : OdfOptions or None, default None
        Configuration options for ODF conversion. If None, uses default settings.

    Returns
    -------
    str
        Markdown representation of the OpenDocument file.

    Raises
    ------
    MarkdownConversionError
        If the document cannot be opened or processed.
    """
    if options is None:
        options = OdfOptions()

    # Validate ZIP archive security for file-based inputs (only for existing files)
    if isinstance(input_data, (str, Path)) and Path(input_data).exists():
        try:
            validate_zip_archive(input_data)
        except Exception as e:
            raise MarkdownConversionError(
                f"ODF archive failed security validation: {str(e)}",
                conversion_stage="archive_validation",
                original_error=e
            ) from e

    try:
        doc = opendocument.load(input_data)
    except ImportError as e:
        raise MarkdownConversionError(
            "odfpy library is required for ODF conversion. Install with: pip install odfpy",
            conversion_stage="dependency_check",
            original_error=e,
        ) from e
    except Exception as e:
        raise MarkdownConversionError(
            f"Failed to open ODF document: {str(e)}", conversion_stage="document_opening", original_error=e
        ) from e

    # Extract metadata if requested
    metadata = None
    if options.extract_metadata:
        metadata = extract_odf_metadata(doc)

    converter = OdfConverter(doc, options)
    markdown_content = converter.convert()

    # Prepend metadata if enabled
    result = prepend_metadata_if_enabled(markdown_content, metadata, options.extract_metadata)

    return result


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="odf",
    extensions=[".odt", ".odp"],
    mime_types=["application/vnd.oasis.opendocument.text", "application/vnd.oasis.opendocument.presentation"],
    magic_bytes=[
        (b"PK\x03\x04", 0),  # ZIP signature
    ],
    converter_module="all2md.converters.odf2markdown",
    converter_function="odf_to_markdown",
    required_packages=[("odfpy", "")],
    import_error_message="ODF conversion requires 'odfpy'. Install with: pip install odfpy",
    options_class="OdfOptions",
    description="Convert OpenDocument files to Markdown",
    priority=4
)
