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
# src/all2md/converters/html2markdown.py
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

    >>> from all2md.converters.html2markdown import html_to_markdown
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

import html
import logging
import os
import re
from pathlib import Path
from typing import IO, Any, Literal, Union
from urllib.parse import urljoin, urlparse

from all2md.constants import (
    DANGEROUS_HTML_ATTRIBUTES,
    DANGEROUS_HTML_ELEMENTS,
    DANGEROUS_SCHEMES,
    MARKDOWN_SPECIAL_CHARS,
    MAX_CODE_FENCE_LENGTH,
    MIN_CODE_FENCE_LENGTH,
    TABLE_ALIGNMENT_MAPPING,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import InputError, MarkdownConversionError
from all2md.options import HtmlOptions, MarkdownOptions, create_updated_options
from all2md.utils.attachments import process_attachment
from all2md.utils.inputs import is_path_like, validate_and_convert_input
from all2md.utils.metadata import DocumentMetadata, prepend_metadata_if_enabled

logger = logging.getLogger(__name__)

# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="html",
    extensions=[".html", ".htm", ".xhtml"],
    mime_types=["text/html", "application/xhtml+xml"],
    magic_bytes=[
        (b"<!DOCTYPE html", 0),
        (b"<!doctype html", 0),
        (b"<html", 0),
        (b"<HTML", 0),
    ],
    converter_module="all2md.converters.html2markdown",
    converter_function="html_to_markdown",
    required_packages=[("beautifulsoup4", "")],
    optional_packages=[],
    import_error_message=("HTML conversion requires 'beautifulsoup4'. Install with: pip install beautifulsoup4"),
    options_class="HtmlOptions",
    description="Convert HTML documents to Markdown",
    priority=5,
)


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
    convert_nbsp : bool, default = False
        Convert non-breaking spaces to regular spaces in output.
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
        convert_nbsp: bool = False,
        strip_dangerous_elements: bool = False,
        table_alignment_auto_detect: bool = True,
        preserve_nested_structure: bool = True,
        markdown_options: MarkdownOptions | None = None,
        # New unified attachment handling parameters
        attachment_mode: str = "alt_text",
        attachment_output_dir: str | None = None,
        attachment_base_url: str | None = None,
        # Network security parameters
        allow_remote_fetch: bool = False,
        allowed_hosts: list[str] | None = None,
        require_https: bool = False,
        network_timeout: float = 10.0,
        max_image_size_bytes: int = 20 * 1024 * 1024,
        max_download_bytes: int = 100 * 1024 * 1024,
    ):
        self.hash_headings = hash_headings
        self.extract_title = extract_title
        self.emphasis_symbol = emphasis_symbol
        self.bullet_symbols = bullet_symbols
        self.convert_nbsp = convert_nbsp

        # Set attachment handling options
        self.attachment_mode = attachment_mode
        self.attachment_output_dir = attachment_output_dir
        self.attachment_base_url = attachment_base_url
        self.strip_dangerous_elements = strip_dangerous_elements
        self.table_alignment_auto_detect = table_alignment_auto_detect
        self.preserve_nested_structure = preserve_nested_structure
        self.markdown_options = markdown_options or MarkdownOptions()

        # Set network security options
        self.allow_remote_fetch = allow_remote_fetch
        self.allowed_hosts = allowed_hosts
        self.require_https = require_https
        self.network_timeout = network_timeout
        self.max_image_size_bytes = max_image_size_bytes
        self.max_download_bytes = max_download_bytes

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

    def _escape_markdown_link_text(self, text: str) -> str:
        """Escape Markdown characters specifically for link text context.

        In link text, we want to escape formatting characters but preserve
        nested markdown syntax like images [alt](url) and links.

        Parameters
        ----------
        text : str
            Link text to escape.

        Returns
        -------
        str
            Text with selectively escaped Markdown characters.
        """
        if not self.markdown_options.escape_special or self._in_code_block:
            return text

        # Only escape formatting characters, not brackets/parentheses used for nested syntax
        formatting_chars = "*_#\\"  # Exclude []() to allow nested markdown syntax
        for char in formatting_chars:
            text = text.replace(char, f"\\{char}")
        return text

    def _decode_entities(self, text: str) -> str:
        """Decode HTML entities while handling non-breaking spaces as configured.

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

        # If convert_nbsp is True, convert non-breaking spaces to regular spaces
        if self.convert_nbsp:
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

                    # Enhanced URL scheme checking for href and src attributes
                    if isinstance(attr_value, str):
                        attr_value_lower = attr_value.lower().strip()

                        # Check specific URL attributes for dangerous schemes
                        if attr_name.lower() in ("href", "src", "action", "formaction"):
                            # Parse URL to check scheme precisely
                            parsed = urlparse(attr_value_lower)
                            if parsed.scheme in ("javascript", "data", "vbscript", "about"):
                                return False
                            # Also check for scheme-less dangerous schemes
                            if any(attr_value_lower.startswith(scheme) for scheme in DANGEROUS_SCHEMES):
                                return False

                        # Check for dangerous scheme content in other style-related attributes
                        elif attr_name.lower() in ("style", "background", "expression"):
                            if any(scheme in attr_value_lower for scheme in DANGEROUS_SCHEMES):
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
        """Download image data from URL using secure network client.

        Parameters
        ----------
        url : str
            URL to download from

        Returns
        -------
        bytes
            Raw image data

        Raises
        ------
        Exception
            If download fails, URL is invalid, or security validation fails
        """
        from all2md.utils.network_security import NetworkSecurityError, fetch_image_securely, is_network_disabled

        # Check global network disable flag
        if is_network_disabled():
            raise Exception("Network access is globally disabled via ALL2MD_DISABLE_NETWORK environment variable")

        # Check if remote fetching is allowed
        if not self.allow_remote_fetch:
            raise Exception(
                "Remote URL fetching is disabled. Set allow_remote_fetch=True in HtmlOptions to enable. "
                "Warning: This may expose your application to SSRF attacks if used with untrusted input."
            )

        try:
            # Use the smaller of max_download_bytes and max_image_size_bytes for security
            effective_max_size = min(self.max_download_bytes, self.max_image_size_bytes)
            return fetch_image_securely(
                url=url,
                allowed_hosts=self.allowed_hosts,
                require_https=self.require_https,
                max_size_bytes=effective_max_size,
                timeout=self.network_timeout,
            )
        except NetworkSecurityError as e:
            logger.warning(f"Network security validation failed for {url}: {e}")
            raise Exception(f"Network security validation failed: {e}") from e
        except Exception as e:
            logger.debug(f"Failed to download image from {url}: {e}")
            raise Exception(f"Failed to download image from {url}: {e}") from e

    def _extract_language_from_attrs(self, node: Any) -> str:
        """Extract language identifier from various HTML attributes and patterns.

        Checks for language in:
        - class attributes with patterns like language-xxx, lang-xxx, brush: xxx
        - data-lang attributes
        - child code elements' classes
        """

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
        from bs4 import BeautifulSoup

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

    def _process_node(self, node: Any, escape_markdown=False) -> str:
        """Process a BeautifulSoup node and its children recursively."""
        from bs4.element import NavigableString

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
        from bs4.element import NavigableString

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

        original_options = self.markdown_options
        temporary_options = create_updated_options(self.markdown_options, escape_special=False)
        # Temporarily disable general escaping to handle link text specially
        self.markdown_options = temporary_options

        # original_escape_setting = self.markdown_options.escape_special
        # self.markdown_options.escape_special = False

        # Process the link content without escaping
        content = "".join(self._process_node(child) for child in node.children)
        content = " ".join(content.split())

        # Restore original escaping setting
        self.markdown_options = original_options

        # Apply link-specific escaping that preserves nested markdown syntax
        if self.markdown_options.escape_special:
            content = self._escape_markdown_link_text(content)

        # Resolve relative URLs
        if href:
            href = self._resolve_url(href)

        if title:
            return f'[{content}]({href} "{title}")'
        return f"[{content}]({href})"

    def _process_image(self, node: Any) -> str:
        """Process images with enhanced handling options."""
        if self.attachment_mode == "skip":
            src = node.get("src", "")
            alt = node.get("alt", "image")
            logger.info(f"Skipping image (attachment_mode=skip): {src} (alt: {alt})")
            return ""

        src = node.get("src", "")
        alt = node.get("alt", "")
        title = node.get("title")

        if not src:
            return ""

        # Resolve relative URLs
        resolved_src = self._resolve_url(src)

        # Use local variable to avoid mutating instance state
        current_attachment_mode = self.attachment_mode

        # Download image data if needed for base64 or download modes
        image_data = None
        if current_attachment_mode in ["base64", "download"]:
            try:
                image_data = self._download_image_data(resolved_src)
            except Exception as e:
                # Fall back to alt_text mode if download fails (without mutating instance)
                logger.info(f"Image download failed for {resolved_src}, falling back to alt_text mode: {e}")
                current_attachment_mode = "alt_text"

        # Generate filename from URL or use generic name
        parsed_url = urlparse(resolved_src)
        filename = os.path.basename(parsed_url.path) or "image.png"

        # For HTML, if we have a resolved URL and alt_text mode, preserve the URL
        if current_attachment_mode == "alt_text" and resolved_src and resolved_src != src:
            # URL was resolved, preserve it
            title_attr = f' "{title}"' if title else ""
            return f"![{alt or filename}]({resolved_src}{title_attr})"

        # Process image using unified attachment handling
        processed_image = process_attachment(
            attachment_data=image_data,
            attachment_name=filename,
            alt_text=alt or title or filename,
            attachment_mode=current_attachment_mode,
            attachment_output_dir=self.attachment_output_dir,
            attachment_base_url=self.attachment_base_url,
            is_image=True,
            alt_text_mode="default",
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


def extract_html_metadata(soup: Any) -> DocumentMetadata:
    """Extract metadata from HTML document.

    Parameters
    ----------
    soup : BeautifulSoup
        Parsed HTML document

    Returns
    -------
    DocumentMetadata
        Extracted metadata
    """
    metadata = DocumentMetadata()

    # Extract from head section if available
    head = soup.find("head")
    if head:
        # Extract title
        title_tag = head.find("title")
        if title_tag and title_tag.string:
            metadata.title = title_tag.string.strip()

        # Extract meta tags
        meta_tags = head.find_all("meta")
        for meta in meta_tags:
            # Get meta name/property and content
            meta_name = meta.get("name", "").lower() or meta.get("property", "").lower()
            content = meta.get("content", "").strip()

            if not meta_name or not content:
                continue

            # Map common meta tags to standard fields
            if meta_name in ["author", "dc.creator", "creator"]:
                metadata.author = content
            elif meta_name in ["description", "dc.description", "og:description", "twitter:description"]:
                if not metadata.subject:  # Only set if not already set
                    metadata.subject = content
            elif meta_name in ["keywords", "dc.subject"]:
                # Split keywords by comma or semicolon
                import re

                metadata.keywords = [k.strip() for k in re.split("[,;]", content) if k.strip()]
            elif meta_name in ["language", "dc.language", "og:locale"]:
                metadata.language = content
            elif meta_name in ["generator", "application-name"]:
                metadata.creator = content
            elif meta_name in ["dc.date", "article:published_time", "publish_date"]:
                metadata.custom["published_date"] = content
            elif meta_name in ["article:modified_time", "last-modified", "dc.modified"]:
                metadata.custom["modified_date"] = content
            elif meta_name in ["og:title", "twitter:title"]:
                if not metadata.title:  # Only set if not already set from <title>
                    metadata.title = content
            elif meta_name in ["article:author", "twitter:creator"]:
                if not metadata.author:  # Only set if not already set
                    metadata.author = content
            elif meta_name in ["og:type", "article:section"]:
                metadata.category = content
            elif meta_name == "viewport":
                metadata.custom["viewport"] = content
            elif meta_name in ["og:url", "canonical"]:
                metadata.custom["url"] = content
            elif meta_name in ["robots", "googlebot"]:
                metadata.custom["robots"] = content

        # Check for charset
        charset_meta = head.find("meta", {"charset": True})
        if charset_meta:
            metadata.custom["charset"] = charset_meta.get("charset")
        else:
            # Try http-equiv Content-Type
            content_type_meta = head.find("meta", {"http-equiv": "Content-Type"})
            if content_type_meta:
                content = content_type_meta.get("content", "")
                if "charset=" in content:
                    charset = content.split("charset=")[-1].strip()
                    metadata.custom["charset"] = charset

        # Extract link tags for additional metadata
        link_tags = head.find_all("link")
        for link in link_tags:
            rel = link.get("rel", [])
            if isinstance(rel, list):
                rel = " ".join(rel)

            if "canonical" in rel:
                metadata.custom["canonical_url"] = link.get("href")
            elif "author" in rel:
                if not metadata.author:
                    metadata.author = link.get("href", "").replace("mailto:", "")

    # Extract Open Graph data if not already captured
    if not metadata.title:
        og_title = soup.find("meta", property="og:title")
        if og_title:
            metadata.title = og_title.get("content", "").strip()

    # Extract from body if head data is missing
    if not metadata.title:
        # Try to find first h1 as title
        h1 = soup.find("h1")
        if h1:
            metadata.title = h1.get_text(strip=True)

    return metadata


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
    InputError
        If input type is not supported or file cannot be read
    MarkdownConversionError
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
                raise MarkdownConversionError(
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
                raise InputError(
                    f"Unsupported input type for HTML conversion: {type(input_data).__name__}",
                    parameter_name="input_data",
                    parameter_value=input_data,
                )
        except Exception as e:
            if isinstance(e, (InputError, MarkdownConversionError)):
                raise
            else:
                raise MarkdownConversionError(
                    f"Failed to process HTML input: {str(e)}", conversion_stage="input_processing", original_error=e
                ) from e

    try:
        # Extract metadata if requested
        metadata = None
        if options.extract_metadata:
            try:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(html_content, "html.parser")
                metadata = extract_html_metadata(soup)
            except Exception as e:
                logger.warning(f"Failed to extract HTML metadata: {e}")

        # Prepare converter arguments, only passing non-None values
        converter_kwargs = {
            "hash_headings": options.use_hash_headings,
            "extract_title": options.extract_title,
            "convert_nbsp": options.convert_nbsp,
            "strip_dangerous_elements": options.strip_dangerous_elements,
            "table_alignment_auto_detect": options.table_alignment_auto_detect,
            "preserve_nested_structure": options.preserve_nested_structure,
            "markdown_options": options.markdown_options,
            "attachment_mode": options.attachment_mode,
            "attachment_output_dir": options.attachment_output_dir,
            "attachment_base_url": options.attachment_base_url,
            # Network security options
            "allow_remote_fetch": options.allow_remote_fetch,
            "allowed_hosts": options.allowed_hosts,
            "require_https": options.require_https,
            "network_timeout": options.network_timeout,
            "max_image_size_bytes": options.max_image_size_bytes,
            "max_download_bytes": options.max_download_bytes,
        }

        # Only add emphasis_symbol and bullet_symbols if markdown_options exists
        if options.markdown_options:
            if options.markdown_options.emphasis_symbol is not None:
                converter_kwargs["emphasis_symbol"] = options.markdown_options.emphasis_symbol
            if options.markdown_options.bullet_symbols is not None:
                converter_kwargs["bullet_symbols"] = options.markdown_options.bullet_symbols

        converter = HTMLToMarkdown(**converter_kwargs)
        result = converter.convert(html_content)

        # Prepend metadata if enabled
        result = prepend_metadata_if_enabled(result, metadata, options.extract_metadata)

        return result
    except Exception as e:
        raise MarkdownConversionError(
            f"Failed to convert HTML to Markdown: {str(e)}", conversion_stage="html_parsing", original_error=e
        ) from e
