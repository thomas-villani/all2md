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
#
#  This file is part of the llmcli project.
#
#  llmcli is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  llmcli is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with llmcli. If not, see <https://www.gnu.org/licenses/>.
#
#  For inquiries, please contact: thomas.villani@gmail.com
#
#  SPDX-License-Identifier: GPL-3.0-or-later
# src/llmcli/mdparse/markdown2pdf.py

"""
markdown2pdf - A module to convert Markdown to PDF using PyMuPDF (fitz).

This module provides functionality to convert Markdown documents to PDF format
using the PyMuPDF library.
"""

import os
from html.parser import HTMLParser
from typing import Any, Literal

import fitz  # PyMuPDF
import markdown_it


class MarkdownHTMLParser(HTMLParser):
    """
    Custom HTML parser to extract structured content from HTML generated from Markdown.
    Converts HTML elements into a structured format that can be rendered to PDF.
    """

    def __init__(self) -> None:
        super().__init__()
        self.elements: list[dict[str, Any]] = []
        self.current_element: dict[str, Any] | None = None
        self.in_code_block = False
        self.list_stack: list[dict[str, Any]] = []
        self.current_link: dict[str, Any] | None = None
        self.data_buffer = ""
        self.formatting_stack: list[tuple[str, int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle opening HTML tags."""
        attrs_dict = dict(attrs)

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush_buffer()
            level = int(tag[1])
            self.current_element = {
                "type": "heading",
                "level": level,
                "text": "",
                "attrs": attrs_dict,
            }
        elif tag == "p":
            self._flush_buffer()
            self.current_element = {"type": "paragraph", "text": "", "attrs": attrs_dict}
        elif tag == "pre":
            self._flush_buffer()
            self.in_code_block = True
            self.current_element = {
                "type": "code_block",
                "language": "",
                "text": "",
                "attrs": attrs_dict,
            }
        elif tag == "code":
            class_attr = attrs_dict.get("class")
            if class_attr and class_attr.startswith("language-"):
                if self.in_code_block and self.current_element and self.current_element["type"] == "code_block":
                    self.current_element["language"] = class_attr[9:]  # Remove 'language-' prefix
            elif not self.in_code_block:
                self._flush_buffer()
                self.formatting_stack.append(("code", len(self.data_buffer)))
        elif tag in {"ul", "ol"}:
            self._flush_buffer()
            list_type = "unordered" if tag == "ul" else "ordered"
            parent_index = len(self.elements) if not self.list_stack else self.list_stack[-1]["parent_index"]

            list_element: dict[str, Any] = {
                "type": "list",
                "list_type": list_type,
                "items": [],
                "parent_index": parent_index,
                "level": len(self.list_stack),
                "attrs": attrs_dict,
            }

            self.list_stack.append({"element": list_element, "parent_index": len(self.elements)})

            self.elements.append(list_element)
            self.current_element = None
        elif tag == "li":
            self._flush_buffer()
            if self.list_stack:
                self.current_element = {"type": "list_item", "text": "", "attrs": attrs_dict}
                self.list_stack[-1]["element"]["items"].append(self.current_element)
        elif tag == "a":
            self._flush_buffer()
            self.current_link = {"href": attrs_dict.get("href", ""), "text": ""}
        elif tag == "br":
            if self.current_element and "text" in self.current_element:
                self.current_element["text"] += "\n"
        elif tag == "hr":
            self._flush_buffer()
            self.elements.append({"type": "horizontal_rule"})
        elif tag == "img":
            self._flush_buffer()
            self.elements.append(
                {
                    "type": "image",
                    "src": attrs_dict.get("src", ""),
                    "alt": attrs_dict.get("alt", ""),
                    "attrs": attrs_dict,
                }
            )
        elif tag in ("strong", "b"):
            self._flush_buffer()
            self.formatting_stack.append(("bold", len(self.data_buffer)))
        elif tag in ("em", "i"):
            self._flush_buffer()
            self.formatting_stack.append(("italic", len(self.data_buffer)))
        elif tag == "table":
            self._flush_buffer()
            self.current_element = {"type": "table", "headers": [], "rows": [], "attrs": attrs_dict}
        elif tag == "thead":
            # Handle table header
            pass
        elif tag == "tr":
            if self.current_element and self.current_element["type"] == "table":
                self.current_element["rows"].append([])
        elif tag in ("th", "td"):
            # Will handle in data collection
            pass
        elif tag == "blockquote":
            self._flush_buffer()
            self.current_element = {"type": "blockquote", "text": "", "attrs": attrs_dict}

    def handle_endtag(self, tag: str) -> None:
        """Handle closing HTML tags."""
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote"):
            self._flush_buffer()
            if self.current_element:
                self.elements.append(self.current_element)
                self.current_element = None
        elif tag == "pre":
            self._flush_buffer()
            self.in_code_block = False
            if self.current_element and self.current_element["type"] == "code_block":
                self.elements.append(self.current_element)
                self.current_element = None
        elif tag == "code" and not self.in_code_block:
            if self.formatting_stack and self.formatting_stack[-1][0] == "code":
                start_pos = self.formatting_stack.pop()[1]
                self.data_buffer = self.data_buffer[:start_pos] + "`" + self.data_buffer[start_pos:] + "`"
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
        elif tag == "a":
            if self.current_link and self.current_element:
                if "text" in self.current_element:
                    link_text = f"[{self.current_link['text']}]({self.current_link['href']})"
                    self.current_element["text"] += link_text
                self.current_link = None
        elif tag in ("strong", "b"):
            if self.formatting_stack and self.formatting_stack[-1][0] == "bold":
                start_pos = self.formatting_stack.pop()[1]
                self.data_buffer = self.data_buffer[:start_pos] + "**" + self.data_buffer[start_pos:] + "**"
        elif tag in ("em", "i"):
            if self.formatting_stack and self.formatting_stack[-1][0] == "italic":
                start_pos = self.formatting_stack.pop()[1]
                self.data_buffer = self.data_buffer[:start_pos] + "*" + self.data_buffer[start_pos:] + "*"
        elif tag == "table":
            self._flush_buffer()
            if self.current_element and self.current_element["type"] == "table":
                self.elements.append(self.current_element)
                self.current_element = None

    def handle_data(self, data: str) -> None:
        """Handle text data."""
        if self.current_link:
            self.current_link["text"] += data
        elif self.current_element and "text" in self.current_element:
            self.current_element["text"] += data
        else:
            self.data_buffer += data

    def _flush_buffer(self) -> None:
        """Flush the data buffer to the current element."""
        if self.data_buffer and self.current_element and "text" in self.current_element:
            self.current_element["text"] += self.data_buffer
        self.data_buffer = ""

    def get_elements(self) -> list[dict[str, Any]]:
        """Return the parsed elements."""
        self._flush_buffer()
        if self.current_element:
            self.elements.append(self.current_element)
        return self.elements


class MarkdownToPDF:
    """
    Class to convert Markdown to PDF using PyMuPDF.
    """

    # Default styles for different element types
    DEFAULT_STYLES: dict[str, Any] = {
        "heading": {
            1: {
                "font": "helv",
                "size": 24,
                "weight": "bold",
                "margin_top": 20,
                "margin_bottom": 10,
            },
            2: {"font": "helv", "size": 20, "weight": "bold", "margin_top": 15, "margin_bottom": 8},
            3: {"font": "helv", "size": 16, "weight": "bold", "margin_top": 12, "margin_bottom": 6},
            4: {"font": "helv", "size": 14, "weight": "bold", "margin_top": 10, "margin_bottom": 5},
            5: {"font": "helv", "size": 12, "weight": "bold", "margin_top": 8, "margin_bottom": 4},
            6: {"font": "helv", "size": 11, "weight": "bold", "margin_top": 6, "margin_bottom": 3},
        },
        "paragraph": {"font": "times", "size": 11, "margin_top": 0, "margin_bottom": 10},
        "code_block": {
            "font": "courier",
            "size": 10,
            "margin_top": 10,
            "margin_bottom": 10,
            "background_color": (0.95, 0.95, 0.95),
        },
        "list_item": {
            "font": "times",
            "size": 11,
            "margin_top": 2,
            "margin_bottom": 2,
            "bullet_indent": 20,
            "text_indent": 30,
        },
        "link": {"font": "times", "size": 11, "color": (0, 0, 1)},  # Blue color for links
        "blockquote": {
            "font": "times",
            "size": 11,
            "margin_top": 10,
            "margin_bottom": 10,
            "left_indent": 20,
            "right_indent": 20,
            "background_color": (0.95, 0.95, 0.95),
        },
    }

    # Font mappings for PyMuPDF
    FONT_MAPPINGS: dict[str, str] = {
        "times": "times-roman",
        "helv": "helv",
        "courier": "courier",
        "symbol": "symbol",
        "zapf": "zapfdingbats",
    }

    def __init__(
        self,
        styles: dict[str, dict] | None = None,
        page_size: tuple[float, float] = (595.0, 842.0),  # A4 size
        margins: tuple[float, float, float, float] = (50, 50, 50, 50),
    ):  # left, top, right, bottom
        """
        Initialize MarkdownToPDF converter with custom styles if provided.

        Args:
            styles: Custom styles to override defaults
            page_size: Width and height of the page in points (default is A4)
            margins: Margins in points (left, top, right, bottom)
        """
        self.styles: dict[str, Any] = self.DEFAULT_STYLES.copy()
        if styles:
            self._update_nested_dict(self.styles, styles)

        self.page_size = page_size
        self.margins = margins

        # Working area dimensions
        self.text_width = page_size[0] - margins[0] - margins[2]
        self.text_height = page_size[1] - margins[1] - margins[3]

    def _update_nested_dict(self, d: dict, u: dict) -> dict:
        """Helper method to update nested dictionaries."""
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = self._update_nested_dict(d.get(k, {}), v)
            else:
                d[k] = v
        return d

    def convert(self, markdown_text: str, output_path: str) -> None:
        """
        Convert markdown text to PDF and save to the specified path.

        Args:
            markdown_text: Markdown text to convert
            output_path: Path to save the PDF file
        """
        # Convert markdown to HTML
        markdowner = markdown_it.MarkdownIt()
        html = markdowner.render(markdown_text)

        # Parse HTML to structured elements
        parser = MarkdownHTMLParser()
        parser.feed(html)
        elements = parser.get_elements()

        # Create PDF document
        doc = fitz.open()
        self._render_elements_to_pdf(doc, elements)

        # Save the PDF
        doc.save(output_path)
        doc.close()

    def convert_file(self, input_path: str, output_path: str | None = None) -> None:
        """
        Convert a markdown file to PDF.

        Args:
            input_path: Path to markdown file
            output_path: Path to save the PDF file. If None, uses input path with .pdf extension
        """
        if not output_path:
            output_path = os.path.splitext(input_path)[0] + ".pdf"

        with open(input_path, encoding="utf-8") as f:
            markdown_text = f.read()

        self.convert(markdown_text, output_path)

    def _render_elements_to_pdf(self, doc: fitz.Document, elements: list[dict[str, Any]]) -> None:
        """
        Render structured elements to PDF.

        Args:
            doc: PyMuPDF document object
            elements: List of structured elements from the HTML parser
        """
        page = doc.new_page(width=self.page_size[0], height=self.page_size[1])
        y_pos = self.margins[1]  # Start at top margin

        for element in elements:
            element_type = element.get("type", "")

            if element_type == "heading":
                y_pos = self._render_heading(page, element, y_pos)
            elif element_type == "paragraph":
                y_pos = self._render_paragraph(page, element, y_pos)
            elif element_type == "code_block":
                y_pos = self._render_code_block(page, element, y_pos)
            elif element_type == "list":
                y_pos = self._render_list(page, element, y_pos)
            elif element_type == "horizontal_rule":
                y_pos = self._render_horizontal_rule(page, y_pos)
            elif element_type == "image":
                y_pos = self._render_image(page, element, y_pos, doc)
            elif element_type == "blockquote":
                y_pos = self._render_blockquote(page, element, y_pos)

            # Check if we need a new page
            if y_pos > self.page_size[1] - self.margins[3] - 20:  # 20 points buffer
                page = doc.new_page(width=self.page_size[0], height=self.page_size[1])
                y_pos = self.margins[1]

    def _render_heading(self, page: fitz.Page, element: dict[str, Any], y_pos: float) -> float:
        """Render a heading element."""
        level = element.get("level", 1)
        text = element.get("text", "")
        style = self.styles["heading"].get(level, self.styles["heading"][1])

        # Apply top margin
        y_pos += style.get("margin_top", 0)

        # Get font
        font_name = self.FONT_MAPPINGS.get(style.get("font", "helv"), "helv")
        font_size = style.get("size", 11)

        # Add text to page
        text_rect = fitz.Rect(self.margins[0], y_pos, self.page_size[0] - self.margins[2], y_pos + font_size)

        # Compute text height and add it
        text_params = {
            "fontname": font_name,
            "fontsize": font_size,
            "render_mode": 2 if style.get("weight") == "bold" else 0,
        }
        text_width, text_height = page.insert_text(
            text_rect.br - (0, text_rect.height),  # Position at top-left of rect
            text,
            **text_params,
        )

        # Move position down by text height and add bottom margin
        y_pos += text_height + style.get("margin_bottom", 0)

        return y_pos

    def _render_paragraph(self, page: fitz.Page, element: dict[str, Any], y_pos: float) -> float:
        """Render a paragraph element."""
        text = element.get("text", "")
        style = self.styles["paragraph"]

        # Apply top margin
        y_pos += style.get("margin_top", 0)

        # Get font
        font_name = self.FONT_MAPPINGS.get(style.get("font", "times"), "times-roman")
        font_size = style.get("size", 11)

        # Process text for formatting
        formatted_text = self._process_text_formatting(text)

        # Split text into lines that fit within text width
        lines = self._split_text_into_lines(page, formatted_text, font_name, font_size, self.text_width)

        for line in lines:
            text_rect = fitz.Rect(self.margins[0], y_pos, self.page_size[0] - self.margins[2], y_pos + font_size)

            # Add text
            text_params = {"fontname": font_name, "fontsize": font_size}
            _, text_height = page.insert_text(text_rect.br - (0, text_rect.height), line, **text_params)

            y_pos += text_height * 1.2  # Add line spacing

        # Add bottom margin
        y_pos += style.get("margin_bottom", 0)

        return y_pos

    def _render_code_block(self, page: fitz.Page, element: dict[str, Any], y_pos: float) -> float:
        """Render a code block element."""
        text = element.get("text", "")
        element.get("language", "")
        style = self.styles["code_block"]

        # Apply top margin
        y_pos += style.get("margin_top", 0)

        # Get font
        font_name = self.FONT_MAPPINGS.get(style.get("font", "courier"), "courier")
        font_size = style.get("size", 10)

        # Draw background
        bg_color = style.get("background_color", (0.95, 0.95, 0.95))

        # Split text into lines
        code_lines = text.split("\n")

        # Calculate height needed for code block
        line_height = font_size * 1.2
        total_height = line_height * len(code_lines) + 10  # Add padding

        # Draw background rectangle
        code_rect = fitz.Rect(self.margins[0], y_pos, self.page_size[0] - self.margins[2], y_pos + total_height)
        page.draw_rect(code_rect, color=bg_color, fill=bg_color)

        # Add code lines
        current_y = y_pos + 5  # Start with a bit of padding
        for line in code_lines:
            text_rect = fitz.Rect(
                self.margins[0] + 5,  # Add left padding
                current_y,
                self.page_size[0] - self.margins[2] - 5,  # Add right padding
                current_y + font_size,
            )

            # Add text
            text_params = {"fontname": font_name, "fontsize": font_size}
            _, text_height = page.insert_text(text_rect.br - (0, text_rect.height), line, **text_params)

            current_y += line_height

        # Update position
        y_pos += total_height + style.get("margin_bottom", 0)

        return y_pos

    def _render_list(self, page: fitz.Page, element: dict[str, Any], y_pos: float) -> float:
        """Render a list element."""
        list_type = element.get("list_type", "unordered")
        items = element.get("items", [])
        level = element.get("level", 0)
        style = self.styles["list_item"]

        # Get font
        font_name = self.FONT_MAPPINGS.get(style.get("font", "times"), "times-roman")
        font_size = style.get("size", 11)

        bullet_indent = style.get("bullet_indent", 20) * (level + 1)
        text_indent = style.get("text_indent", 30) * (level + 1)

        for i, item in enumerate(items):
            # Apply top margin
            y_pos += style.get("margin_top", 0)

            item_text = item.get("text", "")

            # Draw bullet or number
            bullet_rect = fitz.Rect(
                self.margins[0] + bullet_indent - 15,
                y_pos,
                self.margins[0] + bullet_indent,
                y_pos + font_size,
            )

            # Add bullet/number
            bullet_text = "•" if list_type == "unordered" else f"{i + 1}."
            page.insert_text(
                bullet_rect.br - (0, bullet_rect.height),
                bullet_text,
                fontname=font_name,
                fontsize=font_size,
            )

            # Process text for formatting
            formatted_text = self._process_text_formatting(item_text)

            # Split text into lines that fit within text width
            available_width = self.text_width - text_indent
            lines = self._split_text_into_lines(page, formatted_text, font_name, font_size, available_width)

            for line in lines:
                text_rect = fitz.Rect(
                    self.margins[0] + text_indent,
                    y_pos,
                    self.page_size[0] - self.margins[2],
                    y_pos + font_size,
                )

                # Add text
                _, text_height = page.insert_text(
                    text_rect.br - (0, text_rect.height),
                    line,
                    fontname=font_name,
                    fontsize=font_size,
                )

                y_pos += text_height * 1.2  # Add line spacing

            # Add bottom margin
            y_pos += style.get("margin_bottom", 0)

        return y_pos

    def _render_horizontal_rule(self, page: fitz.Page, y_pos: float) -> float:
        """Render a horizontal rule."""
        # Apply margin
        y_pos += 10

        # Draw line
        line_rect = fitz.Rect(self.margins[0], y_pos, self.page_size[0] - self.margins[2], y_pos)
        page.draw_line(line_rect.tl, line_rect.tr, color=(0, 0, 0), width=1)

        # Add margin
        y_pos += 10

        return y_pos

    def _render_image(self, page: fitz.Page, element: dict[str, Any], y_pos: float, doc: fitz.Document) -> float:
        """Render an image element."""
        src = element.get("src", "")
        alt = element.get("alt", "")

        if not src:
            return y_pos

        try:
            # Apply margin
            y_pos += 10

            # Load image if it's a local file
            if os.path.isfile(src):
                try:
                    img = fitz.Pixmap(src)

                    # Scale image to fit width if needed
                    width = img.width
                    height = img.height

                    if width > self.text_width:
                        scale = self.text_width / width
                        width = self.text_width
                        height = height * scale

                    # Add image
                    rect = fitz.Rect(self.margins[0], y_pos, self.margins[0] + width, y_pos + height)
                    page.insert_image(rect, pixmap=img)

                    # Update position
                    y_pos += height

                except Exception:
                    # If image loading fails, show alt text
                    text_rect = fitz.Rect(self.margins[0], y_pos, self.page_size[0] - self.margins[2], y_pos + 11)
                    page.insert_text(
                        text_rect.br - (0, text_rect.height),
                        f"[Image: {alt or src}]",
                        fontname="helv",
                        fontsize=11,
                    )
                    y_pos += 20
            else:
                # Just show alt text for non-local images
                text_rect = fitz.Rect(self.margins[0], y_pos, self.page_size[0] - self.margins[2], y_pos + 11)
                page.insert_text(
                    text_rect.br - (0, text_rect.height),
                    f"[Image: {alt or src}]",
                    fontname="helv",
                    fontsize=11,
                )
                y_pos += 20

            # Add margin
            y_pos += 10

        except Exception:
            # Fallback for any errors
            text_rect = fitz.Rect(self.margins[0], y_pos, self.page_size[0] - self.margins[2], y_pos + 11)
            page.insert_text(
                text_rect.br - (0, text_rect.height),
                f"[Image error: {alt or src}]",
                fontname="helv",
                fontsize=11,
            )
            y_pos += 20

        return y_pos

    def _render_blockquote(self, page: fitz.Page, element: dict[str, Any], y_pos: float) -> float:
        """Render a blockquote element."""
        text = element.get("text", "")
        style = self.styles["blockquote"]

        # Apply top margin
        y_pos += style.get("margin_top", 0)

        # Get font
        font_name = self.FONT_MAPPINGS.get(style.get("font", "times"), "times-roman")
        font_size = style.get("size", 11)

        # Calculate left and right indents
        left_indent = style.get("left_indent", 20)
        right_indent = style.get("right_indent", 20)

        # Process text for formatting
        formatted_text = self._process_text_formatting(text)

        # Split text into lines that fit within text width
        available_width = self.text_width - left_indent - right_indent
        lines = self._split_text_into_lines(page, formatted_text, font_name, font_size, available_width)

        # Calculate total height
        line_height = font_size * 1.2
        total_height = line_height * len(lines) + 10  # Add padding

        # Draw background
        bg_color = style.get("background_color", (0.95, 0.95, 0.95))
        bg_rect = fitz.Rect(
            self.margins[0] + left_indent - 5,
            y_pos,
            self.page_size[0] - self.margins[2] - right_indent + 5,
            y_pos + total_height,
        )
        page.draw_rect(bg_rect, color=bg_color, fill=bg_color)

        # Draw vertical bar on the left
        bar_rect = fitz.Rect(
            self.margins[0] + left_indent - 5,
            y_pos,
            self.margins[0] + left_indent - 2,
            y_pos + total_height,
        )
        page.draw_rect(bar_rect, color=(0.7, 0.7, 0.7), fill=(0.7, 0.7, 0.7))

        # Add text lines
        current_y = y_pos + 5  # Start with a bit of padding
        for line in lines:
            text_rect = fitz.Rect(
                self.margins[0] + left_indent,
                current_y,
                self.page_size[0] - self.margins[2] - right_indent,
                current_y + font_size,
            )

            # Add text
            _, text_height = page.insert_text(
                text_rect.br - (0, text_rect.height), line, fontname=font_name, fontsize=font_size
            )

            current_y += line_height

        # Update position
        y_pos += total_height + style.get("margin_bottom", 0)

        return y_pos

    def _process_text_formatting(self, text: str) -> str:
        """Process text for bold, italic, etc. formatting."""
        # This is a simplified version - in a real implementation,
        # we would parse the markdown formatting and apply different fonts
        return text

    def _split_text_into_lines(
        self, page: fitz.Page, text: str, font_name: str, font_size: float, max_width: float
    ) -> list[str]:
        """Split text into lines that fit within max_width."""
        # Split text by newlines first
        paragraphs = text.split("\n")
        lines = []

        for paragraph in paragraphs:
            if not paragraph:
                lines.append("")
                continue

            words = paragraph.split(" ")
            current_line = words[0]

            for word in words[1:]:
                # Check if adding this word would exceed the line width
                test_line = current_line + " " + word
                text_width = fitz.get_text_length(test_line, fontname=font_name, fontsize=font_size)

                if text_width <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word

            # Add the last line
            lines.append(current_line)

        return lines


def markdown_to_pdf(
    input_text_or_path: str,
    output_path: str,
    styles: dict[str, dict] | None = None,
    page_size: Literal["A4", "Letter", "Legal", "A3", "A5"] = "A4",
    margins: tuple[float, float, float, float] | None = None,
) -> str:
    """
    Convert markdown content or a markdown file to PDF.

    Args:
        input_text_or_path: Either a string containing markdown content or a path to a markdown file
        output_path: Path to save the PDF file (required)
        styles: Custom styles to override defaults
        page_size: Page size (A4, Letter, etc.)
        margins: Margins in points (left, top, right, bottom)

    Returns:
        Path to the generated PDF file
    """
    # Set page size
    page_sizes = {
        "A4": (595.0, 842.0),
        "Letter": (612.0, 792.0),
        "Legal": (612.0, 1008.0),
        "A3": (842.0, 1190.0),
        "A5": (420.0, 595.0),
    }

    page_dimensions = page_sizes.get(page_size, page_sizes["A4"])

    # Set margins
    if not margins:
        margins = (50, 50, 50, 50)  # left, top, right, bottom

    converter = MarkdownToPDF(styles=styles, page_size=page_dimensions, margins=margins)

    # Check if input is a file path or markdown content
    if os.path.isfile(input_text_or_path):
        # It's a file path
        converter.convert_file(input_text_or_path, output_path)
    else:
        # Treat it as markdown content
        converter.convert(input_text_or_path, output_path)

    return output_path
