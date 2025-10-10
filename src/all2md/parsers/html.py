#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/html.py
"""HTML to AST converter.

This module provides conversion from HTML documents to AST representation.
It replaces direct markdown string generation with structured AST building,
enabling multiple rendering strategies and improved testability.

"""

from __future__ import annotations

import html
import logging
import os
import re
from pathlib import Path
from typing import IO, Any, Optional, Union
from urllib.parse import urljoin, urlparse

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Document,
    Emphasis,
    Heading,
    HTMLBlock,
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
from all2md.constants import (
    DANGEROUS_HTML_ATTRIBUTES,
    DANGEROUS_HTML_ELEMENTS,
    DANGEROUS_SCHEMES,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import (
    FileAccessError,
    MalformedFileError,
    NetworkSecurityError,
    ParsingError,
    ValidationError,
)
from all2md.options.html import HtmlOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.attachments import process_attachment
from all2md.utils.decorators import requires_dependencies
from all2md.utils.inputs import is_path_like, validate_and_convert_input
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.network_security import fetch_image_securely, is_network_disabled
from all2md.utils.security import sanitize_language_identifier, validate_local_file_access

logger = logging.getLogger(__name__)


def _read_html_file_with_encoding_fallback(file_path: Union[str, Path]) -> str:
    """Read HTML file with multiple encoding fallback strategies.

    Tries encodings in order: UTF-8, UTF-8-sig, chardet (if available), Latin-1.

    Parameters
    ----------
    file_path : Union[str, Path]
        Path to HTML file

    Returns
    -------
    str
        File content as string

    Raises
    ------
    ParsingError
        If file cannot be read with any encoding

    """
    encodings_to_try = ["utf-8", "utf-8-sig"]

    # Try chardet if available
    chardet_encoding = None
    try:
        import chardet
        with open(str(file_path), "rb") as f:
            raw_data = f.read()
        detection = chardet.detect(raw_data)
        if detection and detection.get("encoding"):
            chardet_encoding = detection["encoding"]
            logger.debug(f"chardet detected encoding: {chardet_encoding}")
    except ImportError:
        logger.debug("chardet not available for encoding detection")
    except Exception as e:
        logger.debug(f"chardet detection failed: {e}")

    # Add chardet result to try list if detected
    if chardet_encoding and chardet_encoding.lower() not in [e.lower() for e in encodings_to_try]:
        encodings_to_try.append(chardet_encoding)

    # Add latin-1 as final fallback (never fails but may produce mojibake)
    encodings_to_try.append("latin-1")

    # Try each encoding
    last_error: Exception | None = None
    for encoding in encodings_to_try:
        try:
            with open(str(file_path), "r", encoding=encoding) as f:
                content = f.read()
            logger.debug(f"Successfully read HTML file with encoding: {encoding}")
            return content
        except UnicodeDecodeError as e:
            logger.debug(f"Failed to read with {encoding}: {e}")
            last_error = e
            continue
        except Exception as e:
            logger.debug(f"Error reading with {encoding}: {e}")
            last_error = e
            continue

    # If we get here, all encodings failed (should not happen with latin-1 fallback)
    raise ParsingError(
        f"Failed to read HTML file with any encoding: {last_error}",
        parsing_stage="file_reading",
        original_error=last_error
    )


class HtmlToAstConverter(BaseParser):
    """Convert HTML to AST representation.

    This converter parses HTML using BeautifulSoup and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : HtmlOptions or None, default = None
        Conversion options

    """

    def __init__(self, options: HtmlOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the HTML parser with options and progress callback."""
        options = options or HtmlOptions()
        super().__init__(options, progress_callback)
        self.options: HtmlOptions = options
        self._list_depth = 0
        self._in_code_block = False
        self._heading_level_offset = 0
        self._attachment_footnotes: dict[str, str] = {}  # label -> content for footnote definitions

    @requires_dependencies("html", [("beautifulsoup4", "bs4", "")])
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse HTML document into an AST.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input HTML document to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw HTML bytes
            - HTML string content

        Returns
        -------
        Document
            AST Document node representing the parsed HTML structure

        Raises
        ------
        ParsingError
            If parsing fails due to invalid HTML or corruption
        FileAccessError
            If input file cannot be accessed
        MalformedFileError
            If input data is malformed
        ValidationError
            If input type is not supported

        """
        if self.options.attachment_mode not in ("skip", "alt_text"):
            pass

        # Determine if input_data is HTML content or a file path/object
        html_content = ""
        if isinstance(input_data, str):
            # Check if it's a file path or HTML content
            if is_path_like(input_data) and os.path.exists(str(input_data)):
                # It's a file path - read the file with encoding fallback
                try:
                    html_content = _read_html_file_with_encoding_fallback(input_data)
                except Exception as e:
                    raise FileAccessError(
                        file_path=str(input_data),
                        message=f"Failed to read HTML file: {e!r}",
                        original_error=e
                    ) from e
            else:
                # It's HTML content as a string
                html_content = input_data
        elif isinstance(input_data, bytes):
            # Decode bytes as UTF-8
            try:
                html_content = input_data.decode("utf-8")
            except UnicodeDecodeError as e:
                raise MalformedFileError(
                    f"Failed to decode HTML bytes as UTF-8: {e!r}",
                    file_path=None,
                    original_error=e
                ) from e
        else:
            # Use validate_and_convert_input for other types (file-like objects)
            # Note: str and bytes are already handled above, so only path-like/file-like reach here
            try:
                doc_input, input_type = validate_and_convert_input(
                    input_data, supported_types=["path-like", "file-like"]
                )

                if input_type == "path":
                    # Read from file path with encoding fallback
                    html_content = _read_html_file_with_encoding_fallback(doc_input)
                elif input_type == "file":
                    # Read from file-like object
                    html_content = doc_input.read()
                    if isinstance(html_content, bytes):
                        html_content = html_content.decode("utf-8")
                else:
                    raise ValidationError(
                        f"Unsupported input type for HTML conversion: {type(input_data).__name__}",
                        parameter_name="input_data",
                        parameter_value=input_data,
                    )
            except Exception as e:
                if isinstance(e, (FileAccessError, MalformedFileError, ParsingError, ValidationError)):
                    raise
                else:
                    raise MalformedFileError(
                        f"Failed to process HTML input: {e!r}",
                        file_path=None,
                        original_error=e
                    ) from e

        # Convert the HTML content to AST
        return self.convert_to_ast(html_content)

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
        # Reset parser state to prevent leakage across parse calls
        self._attachment_footnotes = {}
        self._list_depth = 0
        self._in_code_block = False
        self._heading_level_offset = 0

        from bs4 import BeautifulSoup
        from bs4.element import Comment, Tag

        # Emit started event
        self._emit_progress(
            "started",
            "Converting HTML document",
            current=0,
            total=1
        )

        # Sanitize null bytes from HTML to prevent XSS bypass
        html_content = html_content.replace('\x00', '')

        soup = BeautifulSoup(html_content, "html.parser")

        # Strip comments if requested
        if self.options.strip_comments:
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()

        # Strip dangerous elements if requested
        if self.options.strip_dangerous_elements:
            # Remove script and style tags completely (including all content for security)
            for tag in soup.find_all(['script', 'style']):
                # Decompose completely to avoid any script content in output
                tag.decompose()

            # Collect other dangerous elements and elements with dangerous attributes
            elements_to_remove = []
            for element in soup.find_all():
                if hasattr(element, 'name'):
                    # Check for other dangerous elements (not script/style, already removed)
                    if element.name in DANGEROUS_HTML_ELEMENTS and element.name not in ['script', 'style']:
                        elements_to_remove.append(element)
                    # Check for dangerous attributes
                    elif not self._sanitize_element(element):
                        elements_to_remove.append(element)

            # Remove collected elements completely for security (defense-in-depth)
            for element in elements_to_remove:
                # Decompose all dangerous elements and elements with dangerous attributes.
                # This fully removes both tags and their content to prevent fallback content,
                # misleading text, or edge cases in malformed HTML from being preserved.
                element.decompose()

        # Apply whitelist filters if specified
        if self.options.allowed_elements is not None:
            elements_to_remove = []
            for element in soup.find_all():
                if hasattr(element, "name") and element.name not in self.options.allowed_elements:
                    elements_to_remove.append(element)
            for element in elements_to_remove:
                # Unwrap instead of decompose to keep children
                element.unwrap()

        if self.options.allowed_attributes is not None:
            # Support both global allowlist (tuple) and per-element allowlist (dict)
            is_per_element = isinstance(self.options.allowed_attributes, dict)

            for element in soup.find_all():
                if hasattr(element, "attrs") and hasattr(element, "name"):
                    if is_per_element:
                        # Per-element allowlist: check element-specific allowed attributes
                        allowed_attrs = self.options.allowed_attributes.get(element.name, ())
                    else:
                        # Global allowlist: same attributes allowed for all elements
                        allowed_attrs = self.options.allowed_attributes

                    # Remove attributes not in the allowlist
                    attrs_to_remove = [attr for attr in element.attrs if attr not in allowed_attrs]
                    for attr in attrs_to_remove:
                        del element.attrs[attr]

        # Final security pass: sanitize attributes on all remaining elements (defense-in-depth)
        # This catches any dangerous attributes that may have been preserved during whitelisting
        if self.options.strip_dangerous_elements:
            elements_to_remove = []
            for element in soup.find_all():
                if hasattr(element, 'name'):
                    # Use _sanitize_element to check for dangerous attributes
                    if not self._sanitize_element(element):
                        elements_to_remove.append(element)

            # Remove elements that failed final sanitization check
            for element in elements_to_remove:
                # Decompose completely for security (don't preserve children from dangerous elements)
                element.decompose()

        # Build document children
        children: list[Node] = []

        # Extract title if requested - this will offset all headings by 1 level
        if self.options.extract_title:
            title_tag = soup.find("title")
            if isinstance(title_tag, Tag) and title_tag.string:
                title_heading = Heading(level=1, content=[Text(content=title_tag.string.strip())])
                children.append(title_heading)
                # Demote all body headings by 1 level to make room for extracted title
                self._heading_level_offset = 1

        # Process body or root element
        body = soup.find("body")
        root = body if isinstance(body, Tag) else soup

        for child in root.children:
            if not isinstance(child, Tag):
                continue
            nodes = self._process_node_to_ast(child)
            if nodes:
                if isinstance(nodes, list):
                    children.extend(nodes)
                else:
                    children.append(nodes)

        # Extract and attach metadata
        metadata = self.extract_metadata(soup)

        # Append attachment footnote definitions if any were collected
        if self.options.attachments_footnotes_section:
            self._append_attachment_footnotes(
                children,
                self._attachment_footnotes,
                self.options.attachments_footnotes_section
            )

        # Emit finished event
        self._emit_progress(
            "finished",
            "HTML conversion completed",
            current=1,
            total=1
        )

        return Document(children=children, metadata=metadata.to_dict())

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from HTML document.

        This method extracts metadata from the parsed HTML document, including
        title, author, description, keywords, and other standard metadata fields
        from HTML head section meta tags and Open Graph properties.

        Parameters
        ----------
        document : BeautifulSoup
            Parsed HTML document (BeautifulSoup object)

        Returns
        -------
        DocumentMetadata
            Extracted metadata including title, author, subject, keywords, language,
            creator, category, and custom fields. Returns empty DocumentMetadata if
            no metadata is available.

        Notes
        -----
        This method extracts metadata from:
        - <title> tag in HTML head
        - <meta> tags with various name/property attributes
        - <link> tags with rel attributes
        - Open Graph (og:*) and Twitter Card (twitter:*) meta tags
        - Dublin Core (dc.*) meta tags
        - Article meta tags (article:*)

        The method maps common meta tag names to standardized DocumentMetadata
        fields and stores unmapped tags in the custom dictionary.

        Examples
        --------
        >>> from bs4 import BeautifulSoup
        >>> html = '<html><head><title>My Page</title><meta name="author" content="John Doe"></head></html>'
        >>> soup = BeautifulSoup(html, "html.parser")
        >>> converter = HtmlToAstConverter()
        >>> metadata = converter.extract_metadata(soup)
        >>> metadata.title
        'My Page'
        >>> metadata.author
        'John Doe'

        """
        metadata = DocumentMetadata()

        # Extract from head section if available
        head = document.find("head")
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
            og_title = document.find("meta", property="og:title")
            if og_title:
                metadata.title = og_title.get("content", "").strip()

        # Extract from body if head data is missing
        if not metadata.title:
            # Try to find first h1 as title
            h1 = document.find("h1")
            if h1:
                metadata.title = h1.get_text(strip=True)

        # Extract enhanced microdata and structured data if enabled
        if self.options.extract_microdata:
            microdata: dict[str, Any] = {}

            # Extract all Open Graph tags
            og_tags = {}
            for meta in document.find_all("meta", property=re.compile(r"^og:")):
                prop = meta.get("property", "")
                content = meta.get("content", "").strip()
                if content:
                    og_tags[prop] = content

            if og_tags:
                microdata["opengraph"] = og_tags

            # Extract all Twitter Card metadata
            twitter_tags = {}
            for meta in document.find_all("meta", attrs={"name": re.compile(r"^twitter:")}):
                name = meta.get("name", "")
                content = meta.get("content", "").strip()
                if content:
                    twitter_tags[name] = content

            if twitter_tags:
                microdata["twitter_card"] = twitter_tags

            # Extract microdata (itemscope/itemprop)
            itemscopes = document.find_all(attrs={"itemscope": True})
            if itemscopes:
                microdata_items = []
                for scope in itemscopes:
                    item = {
                        "type": scope.get("itemtype", ""),
                        "properties": {}
                    }

                    # Find all itemprop elements within this scope
                    props = scope.find_all(attrs={"itemprop": True})
                    for prop in props:
                        prop_name = prop.get("itemprop")
                        # Get content from various sources
                        if prop.get("content"):
                            prop_value = prop.get("content")
                        elif prop.name == "meta":
                            prop_value = prop.get("content", "")
                        elif prop.name == "link":
                            prop_value = prop.get("href", "")
                        else:
                            prop_value = prop.get_text(strip=True)

                        if prop_name and prop_value:
                            item["properties"][prop_name] = prop_value

                    if item["properties"]:
                        microdata_items.append(item)

                if microdata_items:
                    microdata["items"] = microdata_items

            # Extract JSON-LD structured data
            json_ld_scripts = document.find_all("script", type="application/ld+json")
            if json_ld_scripts:
                import json
                json_ld_data = []
                for script in json_ld_scripts:
                    try:
                        data = json.loads(script.string)
                        json_ld_data.append(data)
                    except Exception:
                        pass  # Skip malformed JSON-LD

                if json_ld_data:
                    microdata["json_ld"] = json_ld_data

            # Store all microdata in custom fields
            if microdata:
                metadata.custom["microdata"] = microdata

        return metadata

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

            # Apply whitespace collapsing if enabled
            if self.options.collapse_whitespace:
                # Collapse multiple spaces/newlines into single space
                text = re.sub(r'\s+', ' ', text)

            if text.strip():
                return Text(content=text)
            return None

        # Handle nodes without name attribute
        if not hasattr(node, "name"):
            return None

        # Dispatch based on element type
        if node.name == "br":
            # Handle <br> based on br_handling option
            if self.options.br_handling == "space":
                return Text(content=" ")
            else:  # "newline"
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
        elif node.name == "figure":
            return self._process_figure_to_ast(node)
        elif node.name == "details":
            return self._process_details_to_ast(node)
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
        # Apply heading level offset (for title extraction)
        level = min(level + self._heading_level_offset, 6)  # Cap at h6
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

    def _process_figure_to_ast(self, node: Any) -> BlockQuote | Paragraph | HTMLBlock | None:
        """Process HTML figure element to AST node.

        Parameters
        ----------
        node : BeautifulSoup element
            Figure element to process

        Returns
        -------
        BlockQuote, Paragraph, HTMLBlock, or None
            Converted node based on figure_rendering option

        """
        if self.options.figure_rendering == "html":
            # Preserve as HTML
            return HTMLBlock(content=str(node))

        # Extract figcaption if present
        figcaption = node.find("figcaption")
        caption_text = figcaption.get_text(strip=True) if figcaption else None

        # Find image in figure
        img_node = node.find("img")

        if self.options.figure_rendering == "image_with_caption":
            # Render as image with caption in alt text or below
            if img_node:
                img_ast = self._process_image_to_ast(img_node)
                if caption_text and isinstance(img_ast, Image):
                    # Update alt text with caption if not already set
                    if not img_ast.alt_text or img_ast.alt_text == "Image":
                        img_ast.alt_text = caption_text

                # Return image in a paragraph
                if img_ast:
                    return Paragraph(content=[img_ast])

        # Default: blockquote rendering
        children: list[Node] = []

        # Add image if present
        if img_node:
            img_ast = self._process_image_to_ast(img_node)
            if img_ast:
                children.append(Paragraph(content=[img_ast]))

        # Add caption as italic text if present
        if caption_text:
            caption_inline = Emphasis(content=[Text(content=caption_text)])
            children.append(Paragraph(content=[caption_inline]))

        if children:
            return BlockQuote(children=children)

        return None

    def _process_details_to_ast(self, node: Any) -> BlockQuote | HTMLBlock | None:
        """Process HTML details/summary element to AST node.

        Parameters
        ----------
        node : BeautifulSoup element
            Details element to process

        Returns
        -------
        BlockQuote, HTMLBlock, or None
            Converted node based on details_rendering option

        """
        if self.options.details_rendering == "ignore":
            return None

        if self.options.details_rendering == "html":
            # Preserve as HTML
            return HTMLBlock(content=str(node))

        # Default: blockquote rendering
        children: list[Node] = []

        # Extract summary if present
        summary = node.find("summary")
        if summary:
            summary_text = summary.get_text(strip=True)
            if summary_text:
                # Add summary as bold text
                summary_inline = Strong(content=[Text(content=summary_text)])
                children.append(Paragraph(content=[summary_inline]))

        # Process remaining content
        for child in node.children:
            if hasattr(child, 'name') and child.name == "summary":
                continue  # Skip summary, already processed

            ast_nodes = self._process_node_to_ast(child)
            if ast_nodes:
                if isinstance(ast_nodes, list):
                    children.extend(ast_nodes)
                else:
                    children.append(ast_nodes)

        if children:
            return BlockQuote(children=children)

        return None

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

        # Process thead - collect cells from ALL header rows
        thead = node.find("thead")
        if thead:
            header_cells = []
            # Find ALL <tr> elements in thead, not just the first one
            for header_tr in thead.find_all("tr", recursive=False):
                for th in header_tr.find_all(["th", "td"]):
                    content = self._process_children_to_inline(th)
                    alignment = self._get_alignment(th)
                    alignments.append(alignment)
                    header_cells.append(TableCell(content=content))

            if header_cells:
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

        # Process tfoot rows (add them as regular data rows)
        tfoot = node.find("tfoot")
        if tfoot:
            for tr in tfoot.find_all("tr", recursive=False):
                row_cells = []
                for td in tr.find_all(["td", "th"]):
                    content = self._process_children_to_inline(td)
                    row_cells.append(TableCell(content=content))
                rows.append(TableRow(cells=row_cells))

        # If no header was found but we have rows, use first row as header
        if not header and rows:
            header = TableRow(cells=rows[0].cells, is_header=True)
            rows.pop(0)
            # Set default alignments if none were set
            if not alignments:
                alignments = [None] * len(header.cells)

        return Table(header=header, rows=rows, alignments=alignments, caption=caption)  # type: ignore[arg-type]

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

        # Check for file:// URLs and enforce local file access policy
        is_file_url = resolved_src.lower().startswith("file://")
        if is_file_url:
            # Validate against local file access options
            is_allowed = validate_local_file_access(
                resolved_src,
                allow_local_files=self.options.local_files.allow_local_files,
                local_file_allowlist=self.options.local_files.local_file_allowlist,
                local_file_denylist=self.options.local_files.local_file_denylist,
                allow_cwd_files=self.options.local_files.allow_cwd_files
            )

            if not is_allowed:
                # Local file access denied - return image with empty URL and alt text only
                logger.warning(
                    f"Local file access denied for file:// URL (security policy): {resolved_src[:100]}"
                )
                return Image(url="", alt_text=alt_text, title=title)

        # Current attachment mode (may change on error)
        current_attachment_mode = self.options.attachment_mode

        # Download image data if needed for base64 or download modes
        image_data = None
        if current_attachment_mode in ["base64", "download"]:
            try:
                if is_file_url:
                    # For local files, read directly from filesystem
                    image_data = self._read_local_file(resolved_src)
                else:
                    # For remote URLs, download via network
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

        result = process_attachment(
            attachment_data=image_data,
            attachment_name=filename,
            alt_text=alt_text or title or filename,
            attachment_mode=current_attachment_mode,
            attachment_output_dir=self.options.attachment_output_dir,
            attachment_base_url=self.options.attachment_base_url,
            is_image=True,
            alt_text_mode="default",
        )

        # Collect footnote info if present
        if result.get("footnote_label") and result.get("footnote_content"):
            self._attachment_footnotes[result["footnote_label"]] = result["footnote_content"]

        # Extract URL from result
        final_url = result.get("url", "")

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
        if not self.options.attachment_base_url or urlparse(url).scheme:
            return url
        return urljoin(self.options.attachment_base_url, url)

    def _read_local_file(self, file_url: str) -> bytes:
        """Read image data from local file:// URL.

        This method should only be called after validate_local_file_access
        has confirmed access is allowed.

        Parameters
        ----------
        file_url : str
            file:// URL to read from

        Returns
        -------
        bytes
            Raw file data

        Raises
        ------
        Exception
            If file cannot be read or does not exist

        """
        # Parse file:// URL to get local path
        parsed = urlparse(file_url)

        # Handle different file:// URL formats
        if file_url.startswith("file://./") or file_url.startswith("file://../"):
            # Relative paths: file://./image.png or file://../image.png
            path = file_url[7:]  # Remove "file://" prefix
            file_path = Path.cwd() / path
        elif file_url.startswith("file://") and not file_url.startswith("file:///"):
            # file://filename (without leading slash) - treat as relative to CWD
            path = file_url[7:]  # Remove "file://" prefix
            file_path = Path.cwd() / path
        else:
            # Standard absolute file:///path
            file_path = Path(parsed.path)

        # Resolve and read file
        try:
            file_path = file_path.resolve()
            with open(file_path, "rb") as f:
                data = f.read()

            # Check against max asset size
            if len(data) > self.options.max_asset_bytes:
                raise Exception(
                    f"Local file exceeds maximum allowed size: "
                    f"{len(data)} bytes > {self.options.max_asset_bytes} bytes"
                )

            return data
        except FileNotFoundError as e:
            raise Exception(f"Local file not found: {file_path}") from e
        except PermissionError as e:
            raise Exception(f"Permission denied reading local file: {file_path}") from e
        except Exception as e:
            raise Exception(f"Failed to read local file {file_path}: {e}") from e

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
                require_head_success=self.options.network.require_head_success
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
        alt_only_match = re.match(r'^!\[([^]]*)]$', markdown_image)
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

        Checks for language in:
        - class attributes with patterns like language-xxx, lang-xxx, brush: xxx, hljs-xxx
        - data-lang, data-language attributes
        - child code elements' classes
        - Common aliases (js→javascript, py→python)

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

        # Language alias mapping for common abbreviations
        aliases = {
            'js': 'javascript',
            'ts': 'typescript',
            'py': 'python',
            'rb': 'ruby',
            'sh': 'bash',
            'yml': 'yaml',
            'md': 'markdown',
            'cs': 'csharp',
            'fs': 'fsharp',
            'kt': 'kotlin',
            'rs': 'rust',
        }

        # Check class attribute
        if node.get("class"):
            classes = node.get("class")
            if isinstance(classes, str):
                classes = [classes]

            for idx, cls in enumerate(classes):
                # Check for language-xxx pattern (Prism.js)
                if match := re.match(r"language-([a-zA-Z0-9_+\-]+)", cls):
                    lang = match.group(1)
                    return sanitize_language_identifier(aliases.get(lang, lang))
                # Check for lang-xxx pattern
                elif match := re.match(r"lang-([a-zA-Z0-9_+\-]+)", cls):
                    lang = match.group(1)
                    return sanitize_language_identifier(aliases.get(lang, lang))
                # Check for hljs-xxx pattern (Highlight.js)
                elif match := re.match(r"hljs-([a-zA-Z0-9_+\-]+)", cls):
                    lang = match.group(1)
                    return sanitize_language_identifier(aliases.get(lang, lang))
                # Check for brush: xxx pattern - BeautifulSoup splits "brush: sql" into ["brush:", "sql"]
                elif cls == "brush:" and idx + 1 < len(classes):
                    # Next class is the language identifier
                    lang = classes[idx + 1]
                    return sanitize_language_identifier(aliases.get(lang, lang))
                elif match := re.match(r"brush:\s*([a-zA-Z0-9_+\-]+)", cls):
                    # Fallback for cases where brush:lang is together without space
                    lang = match.group(1)
                    return sanitize_language_identifier(aliases.get(lang, lang))
                # Use the class as-is if it's a simple language name (only if we haven't found one yet)
                elif (
                    not language
                    and cls
                    and not cls.startswith("hljs")
                    and not cls.startswith("highlight")
                    and cls != "brush:"
                ):
                    language = aliases.get(cls, cls)

        # Check data-lang attribute
        if node.get("data-lang"):
            lang = node.get("data-lang")
            return sanitize_language_identifier(aliases.get(lang, lang))

        # Check data-language attribute (alternative)
        if node.get("data-language"):
            lang = node.get("data-language")
            return sanitize_language_identifier(aliases.get(lang, lang))

        # Check child code element
        code_child = node.find("code")
        if code_child:
            # Check class on code element
            if code_child.get("class"):
                classes = code_child.get("class")
                if isinstance(classes, str):
                    classes = [classes]

                for cls in classes:
                    if match := re.match(r"language-([a-zA-Z0-9_+\-]+)", cls):
                        lang = match.group(1)
                        return sanitize_language_identifier(aliases.get(lang, lang))
                    elif match := re.match(r"lang-([a-zA-Z0-9_+\-]+)", cls):
                        lang = match.group(1)
                        return sanitize_language_identifier(aliases.get(lang, lang))
                    elif match := re.match(r"hljs-([a-zA-Z0-9_+\-]+)", cls):
                        lang = match.group(1)
                        return sanitize_language_identifier(aliases.get(lang, lang))

            # Check data attributes on code element
            if code_child.get("data-lang"):
                lang = code_child.get("data-lang")
                return sanitize_language_identifier(aliases.get(lang, lang))
            if code_child.get("data-language"):
                lang = code_child.get("data-language")
                return sanitize_language_identifier(aliases.get(lang, lang))

        return sanitize_language_identifier(language)

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

        This method validates URL schemes to prevent XSS attacks through
        javascript:, data:, vbscript:, and other dangerous URL schemes.
        Link scheme validation is performed regardless of the
        strip_dangerous_elements setting to ensure defense-in-depth.

        Parameters
        ----------
        url : str
            URL to sanitize

        Returns
        -------
        str
            Sanitized URL, or empty string if the URL contains a dangerous scheme

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
            logger.warning(f"Failed to parse URL for scheme validation: {url}")
            return ""

        # If no scheme detected, treat as relative URL
        if not scheme:
            # Check if it looks like a relative path without scheme
            if not url_lower.startswith(("http://", "https://", "ftp://", "ftps://", "mailto:", "tel:", "sms:")):
                # Could be a relative path like "page.html" or "path/to/page"
                return url

        # Block dangerous schemes
        dangerous_schemes = {"javascript", "data", "vbscript"}
        if scheme in dangerous_schemes:
            logger.warning(
                f"Blocked link with potentially dangerous scheme '{scheme}:' "
                f"(URL: {url[:100]}{'...' if len(url) > 100 else ''})"
            )
            return ""

        # Allow safe schemes
        safe_schemes = {"http", "https", "mailto", "ftp", "ftps", "tel", "sms"}
        if scheme and scheme not in safe_schemes:
            logger.warning(
                f"Blocked link with unsupported scheme '{scheme}:' "
                f"(URL: {url[:100]}{'...' if len(url) > 100 else ''})"
            )
            return ""

        # If require_https is enabled, block non-https schemes (except mailto, tel, sms)
        if self.options.network.require_https and scheme not in ("https", "mailto", "tel", "sms", ""):
            logger.warning(
                f"Blocked link with non-HTTPS scheme '{scheme}:' due to require_https setting "
                f"(URL: {url[:100]}{'...' if len(url) > 100 else ''})"
            )
            return ""

        return url


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
    parser_class=HtmlToAstConverter,
    renderer_class="all2md.renderers.html.HtmlRenderer",
    renders_as_string=True,
    parser_required_packages=[("beautifulsoup4", "bs4", "")],
    renderer_required_packages=[("jinja2", "jinja2", ">=3.1.0")],
    optional_packages=[],
    import_error_message=("HTML conversion requires 'beautifulsoup4'. Install with: pip install beautifulsoup4"),
    parser_options_class=HtmlOptions,
    renderer_options_class="HtmlRendererOptions",
    description="Convert HTML documents to/from AST",
    priority=5,
)

