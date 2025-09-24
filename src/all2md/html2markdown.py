"""HTML to Markdown conversion module.

This module provides comprehensive HTML to Markdown conversion capabilities with
extensive customization options. It processes HTML content by parsing the DOM
structure and converting elements to their Markdown equivalents while preserving
formatting, links, images, and document structure.

The converter handles complex HTML structures including nested elements, tables,
lists, and various formatting options. It offers configurable behavior for
different conversion scenarios and output preferences.

Key Features
------------
- Comprehensive HTML element support (headings, paragraphs, lists, tables)
- Configurable conversion options (heading styles, emphasis symbols)
- Smart whitespace and line break handling
- Table structure preservation
- Link and image processing with multiple handling modes
- Custom bullet symbols for lists
- Title extraction capabilities
- Robust error handling for malformed HTML

Supported HTML Elements
-----------------------
- Text formatting: bold, italic, underline, strikethrough, code
- Structure: headings (h1-h6), paragraphs, line breaks, horizontal rules
- Lists: ordered, unordered, with proper nesting
- Tables: with headers, cells, and basic formatting
- Links: inline, reference-style options
- Images: inline embedding, removal, or conversion options
- Code blocks and inline code
- Blockquotes with proper nesting

Configuration Options
--------------------
- Hash-style vs. underline-style headings
- Emphasis symbols (* vs _)
- Custom bullet symbols for lists
- Image handling modes (embed, remove, convert)
- Title extraction from HTML head

Dependencies
------------
- beautifulsoup4: For HTML parsing and DOM manipulation
- re: For pattern matching and text processing

Examples
--------
Basic HTML string conversion:

    >>> from all2md.html2markdown import html_to_markdown
    >>> html = '<h1>Title</h1><p>Content with <strong>bold</strong> text.</p>'
    >>> markdown = html_to_markdown(html)
    >>> print(markdown)

Convert HTML file:

    >>> markdown = html_to_markdown('document.html')
    >>> print(markdown)

Convert with file-like object:

    >>> from io import StringIO
    >>> html_content = StringIO('<h2>Header</h2><p>Content</p>')
    >>> markdown = html_to_markdown(html_content)

Custom configuration with options:

    >>> from all2md.options import HtmlOptions, MarkdownOptions
    >>> options = HtmlOptions(
    ...     use_hash_headings=False,
    ...     extract_title=True,
    ...     markdown_options=MarkdownOptions(emphasis_symbol="_")
    ... )
    >>> markdown = html_to_markdown('document.html', options=options)
"""

#  Copyright (c) 2023-2025 Tom Villani, Ph.D.
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

import base64
import html
import os
import re
from pathlib import Path
from typing import IO, Any, Literal, Union
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

from bs4 import BeautifulSoup, NavigableString

from ._attachment_utils import process_attachment
from ._input_utils import is_path_like, validate_and_convert_input
from .constants import (
    DANGEROUS_HTML_ATTRIBUTES,
    DANGEROUS_HTML_ELEMENTS,
    MARKDOWN_SPECIAL_CHARS,
    MAX_CODE_FENCE_LENGTH,
    MIN_CODE_FENCE_LENGTH,
    TABLE_ALIGNMENT_MAPPING,
)
from .exceptions import MdparseConversionError, MdparseInputError
from .options import HtmlOptions, MarkdownOptions


class HTMLToMarkdown:
    """HTML to Markdown Converter

    A comprehensive HTML to Markdown converter with advanced features including
    content sanitization, image handling, entity decoding, and performance optimizations.

    Parameters
    ----------
    hash_headings : bool, default = True
        Use # syntax for headings instead of underline style.
    extract_title : bool, default = False
        Extract and use HTML <title> element as main heading.
    emphasis_symbol : Literal["*", "_"], default = "*"
        Symbol to use for emphasis formatting.
    bullet_symbols : str, default = "*-+"
        Characters to cycle through for nested bullet lists.
    preserve_nbsp : bool, default = False
        Preserve non-breaking spaces in output.
    strip_dangerous_elements : bool, default = False
        Remove potentially dangerous HTML elements.
    table_alignment_auto_detect : bool, default = True
        Auto-detect table column alignment.
    preserve_nested_structure : bool, default = True
        Maintain proper nesting for complex structures.
    markdown_options : MarkdownOptions or None, default = None
        Common Markdown formatting options.
    """

    def __init__(
        self,
        hash_headings: bool = True,
        extract_title: bool = False,
        emphasis_symbol: Literal["*", "_"] = "*",
        bullet_symbols: str = "*-+",
        preserve_nbsp: bool = False,
        strip_dangerous_elements: bool = False,
        table_alignment_auto_detect: bool = True,
        preserve_nested_structure: bool = True,
        markdown_options: MarkdownOptions | None = None,
        # New unified attachment handling parameters
        attachment_mode: str = "alt_text",
        attachment_output_dir: str | None = None,
        attachment_base_url: str | None = None,
    ):
        self.hash_headings = hash_headings
        self.extract_title = extract_title
        self.emphasis_symbol = emphasis_symbol
        self.bullet_symbols = bullet_symbols
        self.preserve_nbsp = preserve_nbsp

        # Set attachment handling options
        self.attachment_mode = attachment_mode
        self.attachment_output_dir = attachment_output_dir
        self.attachment_base_url = attachment_base_url
        self.strip_dangerous_elements = strip_dangerous_elements
        self.table_alignment_auto_detect = table_alignment_auto_detect
        self.preserve_nested_structure = preserve_nested_structure
        self.markdown_options = markdown_options or MarkdownOptions()

        # Internal state
        self._list_depth = 0
        self._in_code_block = False
        self._init_heading_level = 0
        self._output_parts: list[str] = []  # Performance optimization: use list instead of string concatenation

    def _escape_markdown(self, text: str) -> str:
        """Escape special Markdown characters to prevent unintended formatting.

        Parameters
        ----------
        text : str
            Text to escape.

        Returns
        -------
        str
            Text with escaped Markdown special characters.
        """
        if not self.markdown_options.escape_special or self._in_code_block:
            return text

        # Escape Markdown special characters
        for char in MARKDOWN_SPECIAL_CHARS:
            text = text.replace(char, f"\\{char}")
        return text

    def _decode_entities(self, text: str) -> str:
        """Decode HTML entities while preserving special ones if configured.

        Parameters
        ----------
        text : str
            Text containing HTML entities.

        Returns
        -------
        str
            Text with decoded entities.
        """
        # First decode all entities
        decoded = html.unescape(text)

        # If preserve_nbsp is True, convert back to explicit space
        if self.preserve_nbsp and "&nbsp;" in text:
            decoded = decoded.replace("\u00a0", " ")  # Non-breaking space to regular space

        return decoded

    def _sanitize_element(self, element: Any) -> bool:
        """Check if element should be removed for security reasons.

        Parameters
        ----------
        element : BeautifulSoup element
            Element to check.

        Returns
        -------
        bool
            True if element should be kept, False if it should be removed.
        """
        if not self.strip_dangerous_elements:
            return True

        if hasattr(element, "name"):
            # Remove dangerous elements
            if element.name in DANGEROUS_HTML_ELEMENTS:
                return False

            # Check for dangerous attributes
            if element.attrs:
                for attr_name, attr_value in element.attrs.items():
                    if attr_name in DANGEROUS_HTML_ATTRIBUTES:
                        return False
                    if isinstance(attr_value, str) and any(
                        danger in attr_value.lower() for danger in DANGEROUS_HTML_ATTRIBUTES
                    ):
                        return False

        return True

    def _resolve_url(self, url: str) -> str:
        """Resolve relative URLs using base_url if provided.

        Parameters
        ----------
        url : str
            URL to resolve.

        Returns
        -------
        str
            Resolved absolute URL or original URL if no base_url.
        """
        if not self.attachment_base_url or urlparse(url).scheme:
            return url
        return urljoin(self.attachment_base_url, url)

    def _download_image_data(self, url: str) -> bytes:
        """Download image data from URL."""
        try:
            with urlopen(url) as response:
                return response.read()
        except Exception as e:
            raise Exception(f"Failed to download image from {url}: {e}") from e

    def _download_image_as_data_uri(self, url: str) -> str:
        """Download image and convert to data URI.

        Parameters
        ----------
        url : str
            URL of image to download.

        Returns
        -------
        str
            Data URI representation of image, or original URL if download fails.
        """
        try:
            with urlopen(url) as response:
                content_type = response.headers.get("Content-Type", "image/png")
                image_data = response.read()
                encoded_data = base64.b64encode(image_data).decode("utf-8")
                return f"data:{content_type};base64,{encoded_data}"
        except Exception:
            # Fallback to original URL if download fails
            return url

    def _extract_language_from_attrs(self, node: Any) -> str:
        """Extract language identifier from various HTML attributes and patterns.

        Checks for language in:
        - class attributes with patterns like language-xxx, lang-xxx, brush: xxx
        - data-lang attributes
        - child code elements' classes
        """
        import re

        language = ""

        # Check node's class attribute
        if node.get("class"):
            classes = node.get("class")
            if isinstance(classes, str):
                classes = [classes]

            for cls in classes:
                # Check for language-xxx pattern
                if match := re.match(r"language-(\w+)", cls):
                    return match.group(1)
                # Check for lang-xxx pattern
                elif match := re.match(r"lang-(\w+)", cls):
                    return match.group(1)
                # Check for brush: xxx pattern
                elif match := re.match(r"brush:\s*(\w+)", cls):
                    return match.group(1)
                # Use the class as-is if it's a simple language name
                elif cls and not cls.startswith("hljs") and not cls.startswith("highlight"):
                    language = cls

        # Check data-lang attribute
        if node.get("data-lang"):
            return node.get("data-lang")

        # Check child code element's classes (for pre > code structures)
        code_child = node.find("code")
        if code_child and code_child.get("class"):
            classes = code_child.get("class")
            if isinstance(classes, str):
                classes = [classes]

            for cls in classes:
                if match := re.match(r"language-(\w+)", cls):
                    return match.group(1)
                elif match := re.match(r"lang-(\w+)", cls):
                    return match.group(1)

        return language

    def _get_optimal_code_fence(self, code_content: str) -> str:
        """Determine optimal code fence length based on content.

        Parameters
        ----------
        code_content : str
            Code content to analyze.

        Returns
        -------
        str
            Optimal fence string (e.g., '```' or '````').
        """
        # Find longest sequence of backticks in content
        max_backticks = 0
        current_backticks = 0

        for char in code_content:
            if char == "`":
                current_backticks += 1
                max_backticks = max(max_backticks, current_backticks)
            else:
                current_backticks = 0

        # Use at least one more backtick than found in content
        fence_length = max(MIN_CODE_FENCE_LENGTH, max_backticks + 1)
        fence_length = min(fence_length, MAX_CODE_FENCE_LENGTH)

        return "`" * fence_length

    def convert(self, html: str) -> str:
        """Convert HTML string to Markdown."""
        soup = BeautifulSoup(html, "html.parser")

        # Reset output parts for this conversion
        self._output_parts = []

        # Remove doctype if present
        if doctype_el := soup.find("doctype"):
            doctype_el.decompose()

        # Content sanitization - remove dangerous elements if enabled
        if self.strip_dangerous_elements:
            elements_to_remove = []
            for element in soup.find_all():
                if not self._sanitize_element(element):
                    elements_to_remove.append(element)
            for element in elements_to_remove:
                element.decompose()
        else:
            # Default behavior: always remove script and style
            for strip_block in ("script", "style"):
                for to_strip in soup.find_all(strip_block):
                    to_strip.decompose()

        title = ""
        if self.extract_title and (title_tag := soup.find("title")):
            content = self._decode_entities(" ".join(title_tag.text.split()))
            if self.markdown_options.escape_special:
                content = self._escape_markdown(content)
            title = f"# {content}\n\n" if self.hash_headings else f"{content}\n{'=' * len(content)}\n\n"
            self._init_heading_level = 1

        # Process body only if it exists, otherwise process the whole document
        body_or_soup: Any = soup.body if soup.body else soup
        processed = self._process_node(body_or_soup).strip()
        processed = re.sub(r"\n{4,}", "\n\n\n", processed)
        return title + processed

    def _process_node(self, node: Any) -> str:
        """Process a BeautifulSoup node and its children recursively."""
        if isinstance(node, NavigableString):
            text = self._decode_entities(str(node))
            return self._escape_markdown(text) if not self._in_code_block else text

        if not hasattr(node, "name"):
            return "".join(self._process_node(child) for child in node.children)

        if node.name == "br":
            return "\n"
        elif node.name == "hr":
            return "\n\n---\n\n"
        # Handle block elements
        elif node.name in ["p", "div"]:
            return self._process_block(node)
        elif node.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            return self._process_heading(node)
        elif node.name in ["ul", "ol"]:
            return self._process_list(node)
        elif node.name == "li":
            return self._process_list_item(node)
        elif node.name == "pre":
            return self._process_code_block(node)
        elif node.name == "blockquote":
            return self._process_blockquote(node)
        elif node.name == "table":
            return self._process_table(node)
        elif node.name == "dl":
            return self._process_definition_list(node)
        elif node.name in ["dt", "dd"]:
            return self._process_definition_term(node)

        # Handle inline elements
        elif node.name in {"strong", "b"}:
            return self._wrap_text(self.emphasis_symbol * 2, node)
        elif node.name in {"em", "i"}:
            return self._wrap_text(self.emphasis_symbol, node)
        elif node.name == "code":
            self._in_code_block = True
            result = self._wrap_text("`", node)
            self._in_code_block = False
            return result
        elif node.name == "a":
            return self._process_link(node)
        elif node.name == "img":
            return self._process_image(node)
        elif node.name in ["html", "body"]:
            # Skip these container tags but process their children
            return "".join(self._process_node(child) for child in node.children)

        # Default: process children
        return "".join(self._process_node(child) for child in node.children)

    def _process_block(self, node: Any) -> str:
        """Process block-level elements like p and div."""
        content = "".join(self._process_node(child) for child in node.children)
        if not content.strip():
            return ""
        return f"{content}\n\n"

    def _process_heading(self, node: Any) -> str:
        """Process heading elements."""
        level = int(node.name[1])
        content = "".join(self._process_node(child) for child in node.children)
        content = " ".join(content.split())
        if self.hash_headings:
            return f"{'#' * (level + self._init_heading_level)} {content}\n\n"
        else:
            underline_char = "=" if (level + self._init_heading_level) == 1 else "-"
            return f"{content}\n{underline_char * len(content)}\n\n"

    def _process_list(self, node: Any, parent_is_ordered: bool = False) -> str:
        """Process ordered and unordered lists."""
        self._list_depth += 1
        output = ""  # '\n' if self.list_depth == 1 and node.find_previous_sibling() else ''

        for item in node.find_all("li", recursive=False):
            # Determine if this is a numbered list
            is_ordered = node.name == "ol"

            # Calculate proper indentation based on parent and current list type
            indent = ""
            for level in range(self._list_depth - 1):
                # If we're in a numbered list or our parent was numbered,
                # use 3 spaces, otherwise use 2
                if level == 0:
                    # First level indentation depends on parent
                    indent += "   " if parent_is_ordered else "  "
                else:
                    # Subsequent levels depend on their parent level
                    indent += "   " if is_ordered or parent_is_ordered else "  "

            current_index = list(node.find_all("li", recursive=False)).index(item) + 1
            bullet_symbol = self.bullet_symbols[(self._list_depth - 1) % len(self.bullet_symbols)]
            marker = f"{current_index}. " if is_ordered else f"{bullet_symbol} "

            # Process content as before
            content_parts = []
            for child in item.children:
                if isinstance(child, NavigableString):
                    content_parts.append(child.string.strip())
                elif child.name not in ["ul", "ol"]:
                    content_parts.append(self._process_node(child).strip())

            main_content = " ".join(part for part in content_parts if part)
            if main_content:
                output += f"{indent}{marker}{main_content}\n"
            elif item.find_next_sibling() or item.find_previous_sibling():
                output += f"{indent}{marker}\n"

            # Process nested lists with current list type
            for child in item.children:
                if child.name in ["ul", "ol"]:
                    nested_content = self._process_list(child, is_ordered)
                    output += nested_content

        self._list_depth -= 1

        return output  # + ('\n' if self.list_depth == 0 and node.find_next_sibling() else '')

    def _process_list_item(self, node: Any) -> str:
        """Process list items."""
        return "".join(self._process_node(child) for child in node.children)

    def _process_code_block(self, node: Any) -> str:
        """Process code blocks with dynamic fence selection."""
        import html

        self._in_code_block = True
        code = node.get_text()
        self._in_code_block = False

        # Decode HTML entities in code content
        code = html.unescape(code)

        # Normalize line endings and trim trailing spaces
        lines = code.splitlines()
        normalized_lines = [line.rstrip() for line in lines]
        code = "\n".join(normalized_lines)

        # Get optimal fence length
        fence = self._get_optimal_code_fence(code)

        # Get language from various attributes
        language = self._extract_language_from_attrs(node)

        return f"{fence}{language}\n{code}\n{fence}\n\n"

    def _process_blockquote(self, node: Any) -> str:
        """Process blockquotes with improved nested structure handling."""
        content = "".join(self._process_node(child) for child in node.children)
        content = content.strip()

        if not content:
            return ""

        lines = content.split("\n")
        quoted_lines = []

        for line in lines:
            if line.strip():
                # Handle nested blockquotes
                if line.startswith("> "):
                    quoted_lines.append(f"> {line}")  # Already quoted, add another level
                else:
                    quoted_lines.append(f"> {line}")
            else:
                quoted_lines.append(">")  # Empty lines in blockquotes

        return "\n".join(quoted_lines) + "\n\n"

    def _process_table(self, node: Any) -> str:
        """Process tables with enhanced alignment detection and caption support."""
        output = []

        # Process caption if present
        caption = ""
        if caption_element := node.find("caption"):
            caption = self._process_node(caption_element).strip()

        # Process headers - support multiple header rows
        all_headers: list[list[str]] = []
        alignments: list[str] = []

        thead = node.find("thead")
        if thead:
            for header_row in thead.find_all("tr"):
                header_cells = header_row.find_all(["th", "td"])
                if not all_headers:  # First header row determines alignments
                    alignments = [self._get_alignment(cell) for cell in header_cells]
                headers = [self._process_node(cell).strip() for cell in header_cells]
                all_headers.append(headers)

        # Process data rows
        rows = []
        tbody = node.find("tbody")
        if tbody:
            row_elements = tbody.find_all("tr")
        else:
            row_elements = [row for row in node.find_all("tr") if row.parent.name not in ("thead", "tfoot")]

        for row in row_elements:
            cells = [self._process_node(cell).strip() for cell in row.find_all(["td", "th"])]
            rows.append(cells)

        # Process footer rows (tfoot)
        tfoot = node.find("tfoot")
        if tfoot:
            for row in tfoot.find_all("tr"):
                cells = [self._process_node(cell).strip() for cell in row.find_all(["td", "th"])]
                rows.append(cells)

        # If no headers were found but we have rows, check if first row contains th elements
        if not all_headers and rows:
            # Find the first actual tr element to check for th elements
            first_tr = None
            for tr in node.find_all("tr"):
                if tr.parent.name not in ("thead", "tfoot"):
                    first_tr = tr
                    break

            if first_tr and first_tr.find_all("th"):
                # First row has th elements, use it as header
                header_cells = first_tr.find_all(["th", "td"])
                alignments = [self._get_alignment(cell) for cell in header_cells]
                headers = [self._process_node(cell).strip() for cell in header_cells]
                all_headers = [headers]
                rows.pop(0)  # Remove the header row from data rows
            else:
                # No th elements, treat first row as regular header
                first_row = rows.pop(0)
                all_headers = [first_row]
                alignments = [self._get_alignment_from_text(cell) for cell in first_row]

        # Add caption if present
        if caption:
            output.append(f"*{caption}*\n")

        # Build the table
        if all_headers:
            # Use the first (or main) header row
            main_headers = all_headers[0]
            max_cols = max(len(main_headers), max((len(row) for row in rows), default=0))

            # Ensure alignments match column count
            while len(alignments) < max_cols:
                alignments.append(":---:")

            # Add main header
            padded_headers = main_headers + [""] * (max_cols - len(main_headers))
            output.append("| " + " | ".join(padded_headers) + " |")

            # Add separator with alignment
            output.append("|" + "|".join(alignments[:max_cols]) + "|")

            # Add additional header rows if any (as regular rows)
            for additional_header in all_headers[1:]:
                padded_header = additional_header + [""] * (max_cols - len(additional_header))
                output.append("| " + " | ".join(padded_header) + " |")

        # Add data rows
        for row in rows:
            # Pad row if necessary
            max_cols = len(alignments) if alignments else len(row)
            while len(row) < max_cols:
                row.append("")
            output.append("| " + " | ".join(row[:max_cols]) + " |")

        return "\n".join(output) + "\n\n"

    def _get_alignment(self, cell: Any) -> str:
        """Get markdown alignment for table cell with enhanced detection."""
        if not self.table_alignment_auto_detect:
            return ":---:"

        # Check align attribute
        align = cell.get("align", "").lower()
        if align in TABLE_ALIGNMENT_MAPPING:
            return TABLE_ALIGNMENT_MAPPING[align]

        # Check CSS style attribute
        style = cell.get("style", "").lower()
        if "text-align" in style:
            # Handle both 'text-align: value' and 'text-align:value' formats
            normalized_style = style.replace(" ", "")
            for css_align, markdown_align in TABLE_ALIGNMENT_MAPPING.items():
                if f"text-align:{css_align}" in normalized_style:
                    return markdown_align

        # Check CSS class (basic heuristic)
        css_class = " ".join(cell.get("class", [])).lower() if cell.get("class") else ""
        if "center" in css_class or "text-center" in css_class:
            return ":---:"
        elif "right" in css_class or "text-right" in css_class:
            return "---:"
        elif "left" in css_class or "text-left" in css_class:
            return ":---"

        # Default to center alignment (standard markdown table default)
        return ":---:"

    def _get_alignment_from_text(self, text: str) -> str:
        """Infer alignment from text content (fallback method)."""
        text = text.strip()
        if not text:
            return ":---:"

        # Simple heuristic: if text looks like a number, right-align
        try:
            float(text.replace(",", "").replace("%", ""))
            return "---:"
        except ValueError:
            pass

        return ":---:"

    def _process_link(self, node: Any) -> str:
        """Process hyperlinks with URL resolution."""
        href = node.get("href", "")
        title = node.get("title")
        content = "".join(self._process_node(child) for child in node.children)
        content = " ".join(content.split())

        # Resolve relative URLs
        if href:
            href = self._resolve_url(href)

        if title:
            return f'[{content}]({href} "{title}")'
        return f"[{content}]({href})"

    def _process_image(self, node: Any) -> str:
        """Process images with enhanced handling options."""
        if self.attachment_mode == "skip":
            return ""

        src = node.get("src", "")
        alt = node.get("alt", "")
        title = node.get("title")

        if not src:
            return ""

        # Resolve relative URLs
        resolved_src = self._resolve_url(src)

        # Download image data if needed for base64 or download modes
        image_data = None
        if self.attachment_mode in ["base64", "download"]:
            try:
                image_data = self._download_image_data(resolved_src)
            except Exception:
                # Fall back to alt_text mode if download fails
                self.attachment_mode = "alt_text"

        # Generate filename from URL or use generic name
        from urllib.parse import urlparse

        parsed_url = urlparse(resolved_src)
        filename = os.path.basename(parsed_url.path) or "image.png"

        # For HTML, if we have a resolved URL and alt_text mode, preserve the URL
        if self.attachment_mode == "alt_text" and resolved_src and resolved_src != src:
            # URL was resolved, preserve it
            title_attr = f' "{title}"' if title else ""
            return f"![{alt or filename}]({resolved_src}{title_attr})"

        # Process image using unified attachment handling
        processed_image = process_attachment(
            attachment_data=image_data,
            attachment_name=filename,
            alt_text=alt or title or filename,
            attachment_mode=self.attachment_mode,
            attachment_output_dir=self.attachment_output_dir,
            attachment_base_url=self.attachment_base_url,
            is_image=True,
        )

        return processed_image

    def _wrap_text(self, wrapper: str, node: Any) -> str:
        """Wrap text with markdown syntax."""
        content = "".join(self._process_node(child) for child in node.children)
        return f"{wrapper}{content}{wrapper}"

    def _process_definition_list(self, node: Any) -> str:
        """Process definition lists (dl elements)."""
        output = []
        current_term = None

        for child in node.children:
            if hasattr(child, "name"):
                if child.name == "dt":
                    current_term = self._process_node(child).strip()
                elif child.name == "dd":
                    definition = self._process_node(child).strip()
                    if current_term:
                        output.append(f"**{current_term}**")
                        output.append(f": {definition}")
                        output.append("")  # Add empty line between definitions
                        current_term = None
                    else:
                        # Definition without term
                        output.append(f": {definition}")
                        output.append("")

        return "\n".join(output) + "\n"

    def _process_definition_term(self, node: Any) -> str:
        """Process definition terms and definitions (dt/dd elements)."""
        content = "".join(self._process_node(child) for child in node.children)
        return content.strip()


def html_to_markdown(input_data: Union[str, Path, IO[str], IO[bytes]], options: HtmlOptions | None = None) -> str:
    """Convert HTML to Markdown format.

    Processes HTML content from various input sources and converts it to
    well-formatted Markdown while preserving document structure, formatting,
    tables, lists, and embedded content. Handles complex HTML structures
    with configurable conversion options.

    Parameters
    ----------
    input_data : str, pathlib.Path, or file-like object
        HTML content to convert. Can be:
        - String containing HTML content directly
        - String path to HTML file
        - pathlib.Path object pointing to HTML file
        - File-like object (StringIO, TextIOWrapper) containing HTML content
        - File-like object opened in binary mode (will be decoded as UTF-8)
    options : HtmlOptions or None, default None
        Configuration options for HTML conversion. If None, uses default settings.

    Returns
    -------
    str
        Markdown representation of the HTML content with preserved formatting,
        structure, and content.

    Raises
    ------
    MdparseInputError
        If input type is not supported or file cannot be read
    MdparseConversionError
        If HTML parsing or conversion fails

    Examples
    --------
    Convert HTML string directly:

        >>> html = '<h1>Title</h1><p>Content with <strong>bold</strong> text.</p>'
        >>> markdown = html_to_markdown(html)
        >>> print(markdown)
        # Title

        Content with **bold** text.

    Convert HTML file:

        >>> markdown = html_to_markdown('document.html')
        >>> print(markdown)

    Convert with custom options:

        >>> from all2md.options import HtmlOptions, MarkdownOptions
        >>> options = HtmlOptions(
        ...     use_hash_headings=False,
        ...     extract_title=True,
        ...     markdown_options=MarkdownOptions(emphasis_symbol="_")
        ... )
        >>> markdown = html_to_markdown('document.html', options=options)

    Use with file-like object:

        >>> from io import StringIO
        >>> html_content = StringIO('<h2>Header</h2><p>Paragraph</p>')
        >>> markdown = html_to_markdown(html_content)

    Notes
    -----
    - Automatically detects whether string input is file path or HTML content
    - Supports both text and binary file-like objects
    - Handles UTF-8 encoding for file inputs
    - Preserves HTML structure including tables, lists, and formatting
    - Configurable heading styles and list formatting
    """
    # Handle backward compatibility and merge options
    if options is None:
        options = HtmlOptions()

    # Determine if input_data is HTML content or a file path/object
    html_content = ""
    if isinstance(input_data, str):
        # Check if it's a file path or HTML content
        if is_path_like(input_data) and os.path.exists(str(input_data)):
            # It's a file path - read the file
            try:
                with open(str(input_data), "r", encoding="utf-8") as f:
                    html_content = f.read()
            except Exception as e:
                raise MdparseConversionError(
                    f"Failed to read HTML file: {str(e)}", conversion_stage="file_reading", original_error=e
                ) from e
        else:
            # It's HTML content as a string
            html_content = input_data
    else:
        # Use validate_and_convert_input for other types
        try:
            doc_input, input_type = validate_and_convert_input(
                input_data, supported_types=["path-like", "file-like", "HTML strings"]
            )

            if input_type == "path":
                # Read from file path
                with open(str(doc_input), "r", encoding="utf-8") as f:
                    html_content = f.read()
            elif input_type == "file":
                # Read from file-like object
                html_content = doc_input.read()
                if isinstance(html_content, bytes):
                    html_content = html_content.decode("utf-8")
            else:
                raise MdparseInputError(
                    f"Unsupported input type for HTML conversion: {type(input_data).__name__}",
                    parameter_name="input_data",
                    parameter_value=input_data,
                )
        except Exception as e:
            if isinstance(e, (MdparseInputError, MdparseConversionError)):
                raise
            else:
                raise MdparseConversionError(
                    f"Failed to process HTML input: {str(e)}", conversion_stage="input_processing", original_error=e
                ) from e

    try:
        # Prepare converter arguments, only passing non-None values
        converter_kwargs = {
            "hash_headings": options.use_hash_headings,
            "extract_title": options.extract_title,
            "preserve_nbsp": options.preserve_nbsp,
            "strip_dangerous_elements": options.strip_dangerous_elements,
            "table_alignment_auto_detect": options.table_alignment_auto_detect,
            "preserve_nested_structure": options.preserve_nested_structure,
            "markdown_options": options.markdown_options,
            "attachment_mode": options.attachment_mode,
            "attachment_output_dir": options.attachment_output_dir,
            "attachment_base_url": options.attachment_base_url,
        }

        # Only add emphasis_symbol and bullet_symbols if markdown_options exists
        if options.markdown_options:
            if options.markdown_options.emphasis_symbol is not None:
                converter_kwargs["emphasis_symbol"] = options.markdown_options.emphasis_symbol
            if options.markdown_options.bullet_symbols is not None:
                converter_kwargs["bullet_symbols"] = options.markdown_options.bullet_symbols

        converter = HTMLToMarkdown(**converter_kwargs)
        return converter.convert(html_content)
    except ImportError as e:
        raise MdparseConversionError(
            "BeautifulSoup4 library is required for HTML conversion. Install with: pip install beautifulsoup4",
            conversion_stage="dependency_check",
            original_error=e,
        ) from e
    except Exception as e:
        raise MdparseConversionError(
            f"Failed to convert HTML to Markdown: {str(e)}", conversion_stage="html_parsing", original_error=e
        ) from e


def _test() -> None:
    test_doc = r"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>HTML to Markdown Converter Test</title>
    </head>
    <body>
        <h1>Main Heading</h1>
        <h2>Secondary Heading</h2>
        <h3>Tertiary Heading</h3>

        <p>This is a paragraph with <strong>bold text</strong>, <em>italic text</em>, and <code>inline code</code>.</p>

        <p>Here's a <a href="https://example.com" title="Example Link">link with title</a> and a <a href="https://example.com">link without title</a>.</p>

        <img src="image.jpg" alt="Test Image" title="An example image">

        <h3>Unordered List</h3>
        <ul>
            <li>First item</li>
            <li>Second item
                <ul>
                    <li>Nested item 1</li>
                    <li>Nested item 2
                        <ul>
                            <li>Deep nested item</li>
                        </ul>
                    </li>
                </ul>
            </li>
            <li>Third item</li>
        </ul>

        <h3>Ordered List</h3>
        <ol>
            <li>First numbered item</li>
            <li>Second numbered item
                <ol>
                    <li>Nested numbered item 1</li>
                    <li>Nested numbered item 2
                        <ul>
                            <li>Mixed nested item</li>
                        </ul>
                    </li>
                </ol>
            </li>
            <li>Third numbered item</li>
        </ol>

        <h3>List of Links</h3>
        <ul>
            <li><a href="http://first-item.com">First item</a></li>
            <li><a href="http://second-item.com">Second item</a></li>
            <li><a href="http://third.com">
            Third item with
            extra spacing and
            breaks</a>
            </li>
        </ul>

        <h3>Code Block</h3>
        <pre class="python"><code>
    def hello_world():
        print("Hello, **world**!")  # Special characters should be preserved
        return None

    # This is a comment
    class TestClass:
        def __init__(self):
            self.value = 42
        </code></pre>

        <h3>Blockquote</h3>
        <blockquote>
            <p>This is a blockquote with multiple paragraphs.</p>
            <p>Second paragraph in blockquote.</p>
            <ul>
                <li>List inside blockquote</li>
                <li>Another item</li>
            </ul>
        </blockquote>

        <h3>Table</h3>
        <table>
            <thead>
                <tr>
                    <th align="left">Left Header</th>
                    <th align="center">Centered Header</th>
                    <th align="right">Right Header</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td align="left">Cell 1</td>
                    <td align="center">Cell 2</td>
                    <td align="right">Cell 3</td>
                </tr>
                <tr>
                    <td align="left">**Bold** in table</td>
                    <td align="center">`code` in table</td>
                    <td align="right">[link](https://example.com) in table</td>
                </tr>
            </tbody>
        </table>

        <h3>Mixed Content</h3>
        <div>
            <p>A paragraph with <strong>bold text</strong> followed by a list:</p>
            <ul>
                <li>Item with <em>italic</em> text</li>
                <li>Item with <code>inline code</code></li>
                <li>Item with <a href="https://example.com">a link</a></li>
            </ul>
        </div>

        <h3>Special Characters</h3>
        <p>Testing special characters: * _ ` # + - . ! [ ] ( ) { } \ </p>

        <h3>Empty Elements</h3>
        <p></p>
        <ul>
            <li></li>
        </ul>
    </body>
    </html>"""
    md = html_to_markdown(test_doc, extract_title=True)
    # print(md)
    with open("test-md.md", "w") as f:
        f.write(md)
    print("Done!")
