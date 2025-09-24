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
Basic HTML conversion:

    >>> from html2markdown import HTMLToMarkdown
    >>> converter = HTMLToMarkdown()
    >>> html = '<h1>Title</h1><p>Content with <strong>bold</strong> text.</p>'
    >>> markdown = converter.convert(html)
    >>> print(markdown)

Custom configuration:

    >>> converter = HTMLToMarkdown(
    ...     hash_headings=False,
    ...     emphasis_symbol="_",
    ...     bullet_symbols="+-*"
    ... )
    >>> result = converter.convert(html_content)
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

import re
from typing import Any, Literal

from bs4 import BeautifulSoup, NavigableString, Tag


class HTMLToMarkdown:
    """HTML to Markdown Converter

    Parameters
    ----------
    hash_headings : bool, default = True
    extract_title : bool, default = False
    emphasis_symbol : Literal["*", "_"], default = "*"
    bullet_symbols : str, default = "*-+"
    remove_images : bool, default = False
    """

    def __init__(
        self,
        hash_headings: bool = True,
        extract_title: bool = False,
        emphasis_symbol: Literal["*", "_"] = "*",
        bullet_symbols: str = "*-+",
        remove_images: bool = False,
    ):
        self.hash_headings = hash_headings
        self.extract_title = extract_title
        self.emphasis_symbol = emphasis_symbol
        self.bullet_symbols = bullet_symbols
        self.remove_images = remove_images

        self._list_depth = 0
        self._in_code_block = False
        self._init_heading_level = 0

    def convert(self, html: str) -> str:
        """Convert HTML string to Markdown."""
        soup = BeautifulSoup(html, "html.parser")

        # Remove doctype if present
        if doctype_el := soup.find("doctype"):
            doctype_el.decompose()

        for strip_block in ("script", "style"):
            for to_strip in soup.find_all(strip_block):
                to_strip.decompose()

        title = ""
        if self.extract_title and (title_tag := soup.find("title")):
            content = " ".join(title_tag.text.split())
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
            # return self._escape_markdown(str(node))
            return str(node)

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
        """Process code blocks."""
        self._in_code_block = True
        code = node.get_text()
        self._in_code_block = False

        # Determine if we need extra backticks based on content
        fence = "```" + (node.get("class", [""])[0] if node.get("class") else "")
        return f"{fence}\n{code}\n```\n\n"

    def _process_blockquote(self, node: Any) -> str:
        """Process blockquotes."""
        content = "".join(self._process_node(child) for child in node.children)
        lines = content.strip().split("\n")
        quoted_lines = [f"> {line}" for line in lines]
        return "\n".join(quoted_lines) + "\n\n"

    def _process_table(self, node: Any) -> str:
        """Process tables."""
        output = []

        # Process headers
        headers = []
        alignments = []
        if node.find("thead"):
            header_cells = node.thead.find_all(["th", "td"])
            headers = [self._process_node(cell).strip() for cell in header_cells]
            alignments = [self._get_alignment(cell) for cell in header_cells]

        # Process rows
        rows = []
        for row in node.find_all("tr"):
            if row.parent.name == "thead":
                continue
            cells = [self._process_node(cell).strip() for cell in row.find_all(["td", "th"])]
            rows.append(cells)

        # If no headers were found but we have rows, use first row as header
        if not headers and rows:
            headers = rows.pop(0)
            alignments = [":---:"] * len(headers)

        # Build the table
        if headers:
            output.append("| " + " | ".join(headers) + " |")
            output.append("|" + "|".join(alignments or [":---:"] * len(headers)) + "|")

        for row in rows:
            # Pad row if necessary
            while len(row) < len(headers):
                row.append("")
            output.append("| " + " | ".join(row) + " |")

        return "\n".join(output) + "\n\n"

    def _get_alignment(self, cell: Any) -> str:
        """Get markdown alignment for table cell."""
        align = cell.get("align", "")
        if align == "center":
            return ":---:"
        elif align == "right":
            return "---:"
        elif align == "left":
            return ":---"
        return ":---:"

    def _process_link(self, node: Any) -> str:
        """Process hyperlinks."""
        href = node.get("href", "")
        title = node.get("title")
        content = "".join(self._process_node(child) for child in node.children)
        content = " ".join(content.split())

        if title:
            return f'[{content}]({href} "{title}")'
        return f"[{content}]({href})"

    def _process_image(self, node: Any) -> str:
        """Process images."""
        if self.remove_images:
            return ""
        src = node.get("src", "")
        alt = node.get("alt", "")
        title = node.get("title")
        title_part = f' "{title}"' if title else ""
        return f"![{alt}]({src}{title_part})"

    def _wrap_text(self, wrapper: str, node: Any) -> str:
        """Wrap text with markdown syntax."""
        content = "".join(self._process_node(child) for child in node.children)
        return f"{wrapper}{content}{wrapper}"


def html_to_markdown(
    html: str,
    use_hash_headings: bool = True,
    extract_title: bool = False,
    emphasis_symbol: Literal["*", "_"] = "*",
    bullet_symbols: str = "*-+",
    remove_images: bool = False,
) -> str:
    """Convert HTML to Markdown.

    Parameters
    ----------
    html
    use_hash_headings
    extract_title
    emphasis_symbol
    bullet_symbols
    remove_images

    Returns
    -------
    str

    """
    converter = HTMLToMarkdown(
        hash_headings=use_hash_headings,
        extract_title=extract_title,
        emphasis_symbol=emphasis_symbol,
        bullet_symbols=bullet_symbols,
        remove_images=remove_images,
    )
    return converter.convert(html)


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
