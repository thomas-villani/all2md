#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/converters/html2ast.py
"""HTML to AST converter.

This module provides conversion from HTML documents to AST representation.
It replaces direct markdown string generation with structured AST building,
enabling multiple rendering strategies and improved testability.

"""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import urlparse

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Document,
    Emphasis,
    Heading,
    HTMLBlock,
    HTMLInline,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
    Node,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.options import HtmlOptions


class HtmlToAstConverter:
    """Convert HTML to AST representation.

    This converter parses HTML using BeautifulSoup and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : HtmlOptions or None, default = None
        Conversion options

    """

    def __init__(self, options: HtmlOptions | None = None):
        self.options = options or HtmlOptions()
        self._list_depth = 0
        self._in_code_block = False

    def convert_to_ast(self, html_content: str) -> Document:
        """Convert HTML string to AST Document.

        Parameters
        ----------
        html_content : str
            HTML content to convert

        Returns
        -------
        Document
            AST document node

        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")

        # Strip dangerous elements if requested
        if self.options.strip_dangerous_elements:
            # Remove script and style tags
            for tag in soup.find_all(['script', 'style']):
                tag.decompose()

            # Remove elements with dangerous attributes
            elements_to_remove = []
            for element in soup.find_all():
                if not self._sanitize_element(element):
                    elements_to_remove.append(element)
            for element in elements_to_remove:
                element.decompose()

        # Build document children
        children: list[Node] = []

        # Extract title if requested
        if self.options.extract_title:
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                title_heading = Heading(level=1, content=[Text(content=title_tag.string.strip())])
                children.append(title_heading)

        # Process body or root element
        body = soup.find("body")
        root = body if body else soup

        for child in root.children:
            nodes = self._process_node_to_ast(child)
            if nodes:
                if isinstance(nodes, list):
                    children.extend(nodes)
                else:
                    children.append(nodes)

        return Document(children=children)

    def _sanitize_element(self, element: Any) -> bool:
        """Check if element should be removed for security reasons.

        Parameters
        ----------
        element : Any
            BeautifulSoup element to check

        Returns
        -------
        bool
            True if element should be kept, False if it should be removed

        """
        from urllib.parse import urlparse

        from all2md.constants import DANGEROUS_HTML_ATTRIBUTES, DANGEROUS_HTML_ELEMENTS, DANGEROUS_SCHEMES

        if not self.options.strip_dangerous_elements:
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

    def _process_node_to_ast(self, node: Any) -> Node | list[Node] | None:
        """Process a BeautifulSoup node to AST nodes.

        Parameters
        ----------
        node : Any
            BeautifulSoup node to process

        Returns
        -------
        Node, list of Node, or None
            Resulting AST node(s)

        """
        from bs4.element import NavigableString

        # Handle text nodes
        if isinstance(node, NavigableString):
            text = self._decode_entities(str(node))
            if text.strip():
                return Text(content=text)
            return None

        # Handle nodes without name attribute
        if not hasattr(node, "name"):
            return None

        # Dispatch based on element type
        if node.name == "br":
            return LineBreak(soft=False)
        elif node.name == "hr":
            return ThematicBreak()
        elif node.name in ["p", "div"]:
            return self._process_block_to_ast(node)
        elif node.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            return self._process_heading_to_ast(node)
        elif node.name in ["ul", "ol"]:
            return self._process_list_to_ast(node)
        elif node.name == "pre":
            return self._process_code_block_to_ast(node)
        elif node.name == "blockquote":
            return self._process_blockquote_to_ast(node)
        elif node.name == "table":
            return self._process_table_to_ast(node)
        elif node.name in ["strong", "b"]:
            return self._process_strong_to_ast(node)
        elif node.name in ["em", "i"]:
            return self._process_emphasis_to_ast(node)
        elif node.name == "code":
            if self._in_code_block:
                # Inside pre tag - just return text
                return Text(content=node.get_text())
            else:
                return Code(content=node.get_text())
        elif node.name == "a":
            return self._process_link_to_ast(node)
        elif node.name == "img":
            return self._process_image_to_ast(node)
        elif node.name == "u":
            return self._process_underline_to_ast(node)
        else:
            # For unknown elements, process children
            return self._process_children_to_inline(node)

    def _process_block_to_ast(self, node: Any) -> Paragraph | None:
        """Process block element (p, div) to Paragraph node.

        Parameters
        ----------
        node : Any
            Block element node

        Returns
        -------
        Paragraph or None
            Paragraph node if content exists

        """
        content = self._process_children_to_inline(node)
        if content:
            return Paragraph(content=content)
        return None

    def _process_heading_to_ast(self, node: Any) -> Heading:
        """Process heading element to Heading node.

        Parameters
        ----------
        node : Any
            Heading element (h1-h6)

        Returns
        -------
        Heading
            Heading node

        """
        level = int(node.name[1])  # Extract number from h1, h2, etc.
        content = self._process_children_to_inline(node)
        return Heading(level=level, content=content)

    def _process_list_to_ast(self, node: Any) -> List:
        """Process list element to List node.

        Parameters
        ----------
        node : Any
            List element (ul or ol)

        Returns
        -------
        List
            List node with items

        """
        ordered = node.name == "ol"
        items: list[ListItem] = []

        for li in node.find_all("li", recursive=False):
            item = self._process_list_item_to_ast(li)
            if item:
                items.append(item)

        return List(ordered=ordered, items=items)

    def _process_list_item_to_ast(self, node: Any) -> ListItem:
        """Process list item element to ListItem node.

        Parameters
        ----------
        node : Any
            List item element (li)

        Returns
        -------
        ListItem
            List item node

        """
        from bs4.element import NavigableString

        # Process children, separating inline content from nested lists
        children: list[Node] = []
        inline_content: list[Node] = []

        for child in node.children:
            if hasattr(child, "name") and child.name in ["ul", "ol"]:
                # Nested list - first add accumulated inline content as paragraph
                if inline_content:
                    children.append(Paragraph(content=inline_content))
                    inline_content = []
                # Add nested list
                nested_list = self._process_list_to_ast(child)
                children.append(nested_list)
            else:
                # Inline content
                inline_nodes = self._process_node_to_ast(child)
                if inline_nodes:
                    if isinstance(inline_nodes, list):
                        inline_content.extend(inline_nodes)
                    else:
                        inline_content.append(inline_nodes)

        # Add any remaining inline content
        if inline_content:
            children.append(Paragraph(content=inline_content))

        return ListItem(children=children)

    def _process_code_block_to_ast(self, node: Any) -> CodeBlock:
        """Process pre element to CodeBlock node.

        Parameters
        ----------
        node : Any
            Pre element

        Returns
        -------
        CodeBlock
            Code block node

        """
        self._in_code_block = True
        code = node.get_text()
        self._in_code_block = False

        # Decode HTML entities
        code = html.unescape(code)

        # Normalize line endings
        lines = code.splitlines()
        normalized_lines = [line.rstrip() for line in lines]
        code = "\n".join(normalized_lines)

        # Extract language
        language = self._extract_language_from_attrs(node)

        return CodeBlock(content=code, language=language if language else None)

    def _process_blockquote_to_ast(self, node: Any) -> BlockQuote:
        """Process blockquote element to BlockQuote node.

        Parameters
        ----------
        node : Any
            Blockquote element

        Returns
        -------
        BlockQuote
            Block quote node

        """
        children: list[Node] = []
        for child in node.children:
            ast_nodes = self._process_node_to_ast(child)
            if ast_nodes:
                if isinstance(ast_nodes, list):
                    children.extend(ast_nodes)
                else:
                    children.append(ast_nodes)

        return BlockQuote(children=children)

    def _process_table_to_ast(self, node: Any) -> Table:
        """Process table element to Table node.

        Parameters
        ----------
        node : Any
            Table element

        Returns
        -------
        Table
            Table node

        """
        header: TableRow | None = None
        rows: list[TableRow] = []
        alignments: list[str | None] = []
        caption: str | None = None

        # Process caption
        caption_tag = node.find("caption")
        if caption_tag:
            caption = caption_tag.get_text().strip()

        # Process thead
        thead = node.find("thead")
        if thead:
            header_tr = thead.find("tr")
            if header_tr:
                header_cells = []
                for th in header_tr.find_all(["th", "td"]):
                    content = self._process_children_to_inline(th)
                    alignment = self._get_alignment(th)
                    alignments.append(alignment)
                    header_cells.append(TableCell(content=content))
                header = TableRow(cells=header_cells, is_header=True)

        # Process tbody or direct rows
        tbody = node.find("tbody")
        row_container = tbody if tbody else node

        for tr in row_container.find_all("tr", recursive=False):
            # Skip if already processed in thead
            if header and tr.parent.name == "thead":
                continue

            # Check if this row has th elements (header row without thead)
            has_th = bool(tr.find("th"))

            if has_th and not header:
                # This is a header row
                header_cells = []
                for th in tr.find_all(["th", "td"]):
                    content = self._process_children_to_inline(th)
                    alignment = self._get_alignment(th)
                    alignments.append(alignment)
                    header_cells.append(TableCell(content=content))
                header = TableRow(cells=header_cells, is_header=True)
            else:
                # This is a data row
                row_cells = []
                for td in tr.find_all(["td", "th"]):
                    content = self._process_children_to_inline(td)
                    row_cells.append(TableCell(content=content))
                rows.append(TableRow(cells=row_cells))

        return Table(header=header, rows=rows, alignments=alignments, caption=caption)

    def _process_strong_to_ast(self, node: Any) -> Strong:
        """Process strong/b element to Strong node.

        Parameters
        ----------
        node : Any
            Strong or b element

        Returns
        -------
        Strong
            Strong node

        """
        content = self._process_children_to_inline(node)
        return Strong(content=content)

    def _process_emphasis_to_ast(self, node: Any) -> Emphasis:
        """Process em/i element to Emphasis node.

        Parameters
        ----------
        node : Any
            Em or i element

        Returns
        -------
        Emphasis
            Emphasis node

        """
        content = self._process_children_to_inline(node)
        return Emphasis(content=content)

    def _process_underline_to_ast(self, node: Any) -> Underline:
        """Process u element to Underline node.

        Parameters
        ----------
        node : Any
            U element

        Returns
        -------
        Underline
            Underline node

        """
        content = self._process_children_to_inline(node)
        return Underline(content=content)

    def _process_link_to_ast(self, node: Any) -> Link:
        """Process a element to Link node.

        Parameters
        ----------
        node : Any
            A element

        Returns
        -------
        Link
            Link node

        """
        url = node.get("href", "")
        title = node.get("title")
        content = self._process_children_to_inline(node)

        # Resolve relative URLs
        if url:
            url = self._resolve_url(url)

        # Sanitize URL
        url = self._sanitize_link_url(url)

        return Link(url=url, content=content, title=title)

    def _process_image_to_ast(self, node: Any) -> Image:
        """Process img element to Image node.

        Parameters
        ----------
        node : Any
            Img element

        Returns
        -------
        Image
            Image node

        """
        import logging
        import os
        from urllib.parse import urlparse

        logger = logging.getLogger(__name__)

        src = node.get("src", "")
        alt_text = node.get("alt", "")
        title = node.get("title")

        if not src:
            return Image(url="", alt_text=alt_text, title=title)

        # For skip mode, return empty URL
        if self.options.attachment_mode == "skip":
            logger.info(f"Skipping image (attachment_mode=skip): {src} (alt: {alt_text})")
            return Image(url="", alt_text=alt_text, title=title)

        # Resolve relative URLs
        resolved_src = self._resolve_url(src)

        # Current attachment mode (may change on error)
        current_attachment_mode = self.options.attachment_mode

        # Download image data if needed for base64 or download modes
        image_data = None
        if current_attachment_mode in ["base64", "download"]:
            try:
                image_data = self._download_image_data(resolved_src)
            except Exception as e:
                # Fall back to alt_text mode if download fails
                logger.info(f"Image download failed for {resolved_src}, falling back to alt_text mode: {e}")
                current_attachment_mode = "alt_text"

        # Generate filename from URL or use generic name
        parsed_url = urlparse(resolved_src)
        filename = os.path.basename(parsed_url.path) or "image.png"

        # For alt_text mode with a resolved URL, use the URL
        if current_attachment_mode == "alt_text":
            if resolved_src and resolved_src != src:
                # URL was resolved, preserve it
                return Image(url=resolved_src, alt_text=alt_text, title=title)
            else:
                # No URL or same as original, just use alt text
                return Image(url=resolved_src, alt_text=alt_text, title=title)

        # Process image using unified attachment handling
        from all2md.utils.attachments import process_attachment

        processed_markdown = process_attachment(
            attachment_data=image_data,
            attachment_name=filename,
            alt_text=alt_text or title or filename,
            attachment_mode=current_attachment_mode,
            attachment_output_dir=self.options.attachment_output_dir,
            attachment_base_url=self.options.attachment_base_url,
            is_image=True,
            alt_text_mode="default",
        )

        # Parse the markdown string to extract the URL
        # process_attachment returns strings like:
        # - ![alt](url) for base64/download
        # - ![alt] for alt_text
        final_url = self._extract_url_from_markdown_image(processed_markdown)

        return Image(url=final_url, alt_text=alt_text, title=title)

    def _resolve_url(self, url: str) -> str:
        """Resolve relative URL to absolute URL if base URL is provided.

        Parameters
        ----------
        url : str
            URL to resolve

        Returns
        -------
        str
            Resolved absolute URL or original URL

        """
        from urllib.parse import urljoin, urlparse

        if not self.options.attachment_base_url or urlparse(url).scheme:
            return url
        return urljoin(self.options.attachment_base_url, url)

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
        import logging

        logger = logging.getLogger(__name__)

        from all2md.utils.network_security import NetworkSecurityError, fetch_image_securely, is_network_disabled

        # Check global network disable flag
        if is_network_disabled():
            raise Exception("Network access is globally disabled via ALL2MD_DISABLE_NETWORK environment variable")

        # Check if remote fetching is allowed
        if not self.options.network.allow_remote_fetch:
            raise Exception(
                "Remote URL fetching is disabled. Set allow_remote_fetch=True in NetworkFetchOptions to enable. "
                "Warning: This may expose your application to SSRF attacks if used with untrusted input."
            )

        try:
            # Use network options from HtmlOptions
            return fetch_image_securely(
                url=url,
                allowed_hosts=self.options.network.allowed_hosts,
                require_https=self.options.network.require_https,
                max_size_bytes=self.options.network.max_remote_asset_bytes,
                timeout=self.options.network.network_timeout,
            )
        except NetworkSecurityError as e:
            logger.warning(f"Network security validation failed for {url}: {e}")
            raise Exception(f"Network security validation failed: {e}") from e
        except Exception as e:
            logger.debug(f"Failed to download image from {url}: {e}")
            raise Exception(f"Failed to download image from {url}: {e}") from e

    def _extract_url_from_markdown_image(self, markdown_image: str) -> str:
        """Extract URL from markdown image string.

        Parameters
        ----------
        markdown_image : str
            Markdown image string like ![alt](url) or ![alt]

        Returns
        -------
        str
            Extracted URL or empty string

        """
        # Match ![alt](url) or ![alt](url "title")
        match = re.match(r'^!\[([^\]]*)\]\(([^)]+?)(?:\s+"[^"]*")?\)$', markdown_image)
        if match:
            return match.group(2)

        # Match ![alt] (no URL)
        alt_only_match = re.match(r'^!\[([^\]]*)\]$', markdown_image)
        if alt_only_match:
            return ""

        # If it doesn't match expected format, return empty
        return ""

    def _process_children_to_inline(self, node: Any) -> list[Node]:
        """Process node children to inline nodes.

        Parameters
        ----------
        node : Any
            Parent node

        Returns
        -------
        list of Node
            List of inline nodes

        """
        result: list[Node] = []

        for child in node.children:
            ast_nodes = self._process_node_to_ast(child)
            if ast_nodes:
                if isinstance(ast_nodes, list):
                    result.extend(ast_nodes)
                else:
                    result.append(ast_nodes)

        return result

    def _decode_entities(self, text: str) -> str:
        """Decode HTML entities in text.

        Parameters
        ----------
        text : str
            Text with HTML entities

        Returns
        -------
        str
            Decoded text

        """
        return html.unescape(text)

    def _extract_language_from_attrs(self, node: Any) -> str:
        """Extract language identifier from HTML attributes.

        Parameters
        ----------
        node : Any
            Code block node

        Returns
        -------
        str
            Language identifier

        """
        language = ""

        # Check class attribute
        if node.get("class"):
            classes = node.get("class")
            if isinstance(classes, str):
                classes = [classes]

            for cls in classes:
                if match := re.match(r"language-([a-zA-Z0-9_+\-]+)", cls):
                    return match.group(1)
                elif match := re.match(r"lang-([a-zA-Z0-9_+\-]+)", cls):
                    return match.group(1)

        # Check data-lang attribute
        if node.get("data-lang"):
            return node.get("data-lang")

        # Check child code element
        code_child = node.find("code")
        if code_child and code_child.get("class"):
            classes = code_child.get("class")
            if isinstance(classes, str):
                classes = [classes]

            for cls in classes:
                if match := re.match(r"language-([a-zA-Z0-9_+\-]+)", cls):
                    return match.group(1)

        return language

    def _get_alignment(self, cell: Any) -> str | None:
        """Get table cell alignment.

        Parameters
        ----------
        cell : Any
            Table cell element

        Returns
        -------
        str or None
            Alignment ('left', 'center', 'right') or None

        """
        # Check align attribute
        align = cell.get("align", "").lower()
        if align == "left":
            return "left"
        elif align == "center":
            return "center"
        elif align == "right":
            return "right"

        # Check CSS style
        style = cell.get("style", "").lower()
        if "text-align" in style:
            if "left" in style:
                return "left"
            elif "center" in style:
                return "center"
            elif "right" in style:
                return "right"

        return None

    def _sanitize_link_url(self, url: str) -> str:
        """Sanitize link URL to prevent XSS attacks.

        Parameters
        ----------
        url : str
            URL to sanitize

        Returns
        -------
        str
            Sanitized URL

        """
        if not url or not url.strip():
            return ""

        url_lower = url.lower().strip()

        # Preserve relative URLs
        if url_lower.startswith(("#", "/", "./", "../", "?")):
            return url

        # Parse URL scheme
        try:
            parsed = urlparse(url_lower)
            scheme = parsed.scheme.lower() if parsed.scheme else ""
        except Exception:
            return ""

        # Block dangerous schemes
        dangerous_schemes = {"javascript", "data", "vbscript"}
        if scheme in dangerous_schemes:
            return ""

        # Allow safe schemes
        safe_schemes = {"http", "https", "mailto", "ftp", "ftps", "tel", "sms"}
        if scheme and scheme not in safe_schemes:
            return ""

        return url
