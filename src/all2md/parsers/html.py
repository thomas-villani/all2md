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
import json
import logging
import os
import re
import stat
from pathlib import Path
from typing import IO, Any, Optional, Union
from urllib.parse import urljoin, urlparse

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    CommentInline,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
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
    Strikethrough,
    Strong,
    Subscript,
    Superscript,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.constants import (
    DANGEROUS_HTML_ELEMENTS,
    DEPS_HTML,
    DEPS_HTML_READABILITY,
    MAX_JSON_LD_SIZE_BYTES,
    MAX_META_TAG_CONTENT_LENGTH,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import (
    DependencyError,
    NetworkSecurityError,
)
from all2md.options.html import HtmlOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.attachments import process_attachment
from all2md.utils.decorators import requires_dependencies
from all2md.utils.html_sanitizer import is_element_safe, sanitize_html_string
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.network_security import fetch_image_securely, is_network_disabled
from all2md.utils.parser_helpers import attachment_result_to_image_node
from all2md.utils.security import (
    resolve_file_url_to_path,
    sanitize_language_identifier,
    sanitize_null_bytes,
    validate_local_file_access,
)

logger = logging.getLogger(__name__)


class HtmlToAstConverter(BaseParser):
    """Convert HTML to AST representation.

    This converter parses HTML using BeautifulSoup and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : HtmlOptions or None, default = None
        Conversion options

    """

    # Block-level HTML elements that should create block nodes in AST
    BLOCK_ELEMENTS = frozenset(
        {
            "div",
            "p",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "section",
            "article",
            "header",
            "footer",
            "nav",
            "aside",
            "main",
            "ul",
            "ol",
            "li",
            "dl",
            "dt",
            "dd",
            "blockquote",
            "pre",
            "hr",
            "table",
            "caption",
            "thead",
            "tbody",
            "tfoot",
            "tr",
            "th",
            "td",
            "figure",
            "figcaption",
            "details",
            "summary",
            "address",
            "form",
            "fieldset",
            "legend",
            "hgroup",
            "dialog",  # Additional semantic HTML5 elements
            "en-note",  # Evernote ENEX note container
        }
    )

    # Inline HTML elements
    INLINE_ELEMENTS = frozenset(
        {
            "a",
            "span",
            "em",
            "strong",
            "i",
            "b",
            "u",
            "s",
            "del",
            "ins",
            "sub",
            "sup",
            "code",
            "br",
            "img",
            "svg",
            "abbr",
            "cite",
            "dfn",
            "kbd",
            "mark",
            "q",
            "samp",
            "small",
            "time",
            "var",
            "wbr",
            "bdi",
            "bdo",
            "data",  # Bidirectional text and data elements
        }
    )

    def __init__(self, options: HtmlOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the HTML parser with options and progress callback."""
        BaseParser._validate_options_type(options, HtmlOptions, "html")
        options = options or HtmlOptions()
        super().__init__(options, progress_callback)
        self.options: HtmlOptions = options
        self._list_depth = 0
        self._in_code_block = False
        self._heading_level_offset = 0
        self._attachment_footnotes: dict[str, str] = {}  # label -> content for footnote definitions

    @requires_dependencies("html", DEPS_HTML)
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
        html_content = self._load_text_content(input_data)

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

        # Emit started event
        self._emit_progress("started", "Converting HTML document", current=0, total=1)

        # M8: Sanitize null bytes and zero-width characters from HTML to prevent XSS bypass
        # This removes \x00, \ufeff, \u200b, \u200c, \u200d, \u2060 which can be used to
        # hide malicious payloads or bypass security filters
        html_content = sanitize_null_bytes(html_content)

        readability_title: str | None = None
        if self.options.extract_readable:
            html_content, readability_title = self._extract_readable_html(html_content)

        from bs4 import BeautifulSoup
        from bs4.element import Tag
        from bs4.exceptions import FeatureNotFound

        # M10: Use configurable parser (html.parser by default, html5lib for browser-like parsing)
        # html.parser: Fast, built-in, but may handle malformed HTML differently than browsers
        # html5lib: Standards-compliant, matches browser behavior, but slower, requires html5lib installed
        # lxml: Fast, requires C library
        try:
            soup = BeautifulSoup(html_content, self.options.html_parser)
        except FeatureNotFound as e:
            if "html5lib" in str(e):
                missing_packages = [("html5lib", "")]
            elif "lxml" in str(e):
                missing_packages = [("lxml", "")]
            else:
                missing_packages = []
            raise DependencyError(
                f"Error in HtmlToAstConverter! Selected HtmlOptions.html_parser " f"not found: {e}.",
                missing_packages=missing_packages,
            ) from e

        # Sanitize HTML: Use single-pass bleach when possible, fall back to multi-pass BeautifulSoup
        # This reduces duplication and aligns with HtmlRenderer's sanitization approach
        if self.options.strip_dangerous_elements and self.options.allowed_attributes is None:
            # Use shared sanitization utility from html_sanitizer module for single-pass approach
            # This provides comprehensive sanitization with bleach (when available) or BeautifulSoup fallback

            sanitized_html = sanitize_html_string(str(soup))
            soup = BeautifulSoup(sanitized_html, self.options.html_parser)
            logger.debug("Applied single-pass HTML sanitization via html_sanitizer utility")
        elif self.options.strip_dangerous_elements or self.options.allowed_attributes is not None:
            # Use multi-pass BeautifulSoup for custom attribute allowlists
            soup = self._apply_custom_sanitization(soup)

        # Build document children
        children: list[Node] = []

        # Extract title if requested - this will offset all headings by 1 level
        extracted_readability_title = False
        if self.options.extract_title:
            title_tag = soup.find("title")
            if isinstance(title_tag, Tag) and title_tag.string:
                title_heading = Heading(level=1, content=[Text(content=title_tag.string.strip())])
                children.append(title_heading)
                # Demote all body headings by 1 level to make room for extracted title
                self._heading_level_offset = 1
                extracted_readability_title = True

        if self.options.extract_title and not extracted_readability_title and readability_title:
            title_heading = Heading(level=1, content=[Text(content=readability_title.strip())])
            children.append(title_heading)
            self._heading_level_offset = 1
            extracted_readability_title = True

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
                children, self._attachment_footnotes, self.options.attachments_footnotes_section
            )

        # Emit finished event
        self._emit_progress("finished", "HTML conversion completed", current=1, total=1)

        return Document(children=children, metadata=metadata.to_dict())

    @staticmethod
    @requires_dependencies("html", DEPS_HTML_READABILITY)
    def _extract_readable_html(html_content: str) -> tuple[str, str | None]:
        """Extract the readable article content using readability-lxml.

        Parameters
        ----------
        html_content : str
            Raw HTML content to process.

        Returns
        -------
        tuple[str, str | None]
            A tuple containing the extracted readable HTML (or original content on failure)
            and an optional title discovered by readability.

        """
        import readability

        readability_doc = readability.Document(html_content)

        try:
            summary_html = readability_doc.summary(html_partial=True)
        except Exception as exc:
            logger.warning("Readability summary extraction failed: %s", exc)
            return html_content, None

        if not summary_html:
            logger.debug("Readability summary returned empty content; falling back to original HTML")
            return html_content, None

        logger.debug("Readability extraction succeeded; using article-only HTML content")

        readable_title = readability_doc.short_title() or readability_doc.title()

        return str(summary_html), (
            readable_title.strip() if isinstance(readable_title, str) and readable_title.strip() else None
        )

    def _process_meta_tag(self, meta_name: str, content: str, metadata: DocumentMetadata) -> None:
        """Process a single meta tag and update metadata accordingly.

        Parameters
        ----------
        meta_name : str
            The meta tag name (from name or property attribute), lowercased
        content : str
            The meta tag content
        metadata : DocumentMetadata
            The metadata object to update

        """
        # Author fields
        if meta_name in ["author", "dc.creator", "creator"]:
            metadata.author = content
        # Description fields
        elif meta_name in ["description", "dc.description", "og:description", "twitter:description"]:
            if not metadata.subject:
                metadata.subject = content
        # Keywords
        elif meta_name in ["keywords", "dc.subject"]:
            metadata.keywords = [k.strip() for k in re.split("[,;]", content) if k.strip()]
        # Language
        elif meta_name in ["language", "dc.language", "og:locale"]:
            metadata.language = content
        # Creator/Generator
        elif meta_name in ["generator", "application-name"]:
            metadata.creator = content
        # Published date
        elif meta_name in ["dc.date", "article:published_time", "publish_date"]:
            metadata.custom["published_date"] = content
        # Modified date
        elif meta_name in ["article:modified_time", "last-modified", "dc.modified"]:
            metadata.custom["modified_date"] = content
        # Title (from OG/Twitter)
        elif meta_name in ["og:title", "twitter:title"]:
            if not metadata.title:
                metadata.title = content
        # Author (from article/twitter)
        elif meta_name in ["article:author", "twitter:creator"]:
            if not metadata.author:
                metadata.author = content
        # Category
        elif meta_name in ["og:type", "article:section"]:
            metadata.category = content
        # Viewport
        elif meta_name == "viewport":
            metadata.custom["viewport"] = content
        # URL
        elif meta_name in ["og:url", "canonical"]:
            metadata.custom["url"] = content
        # Robots
        elif meta_name in ["robots", "googlebot"]:
            metadata.custom["robots"] = content

    def _detect_charset(self, head: Any, metadata: DocumentMetadata) -> None:
        """Detect and extract charset information from head section.

        Parameters
        ----------
        head : BeautifulSoup tag
            The HTML head section
        metadata : DocumentMetadata
            The metadata object to update

        """
        charset_meta = head.find("meta", {"charset": True})
        if charset_meta:
            metadata.custom["charset"] = charset_meta.get("charset")
        else:
            content_type_meta = head.find("meta", {"http-equiv": "Content-Type"})
            if content_type_meta:
                content = content_type_meta.get("content", "")
                if "charset=" in content:
                    charset = content.split("charset=")[-1].strip()
                    metadata.custom["charset"] = charset

    def _process_link_tags(self, head: Any, metadata: DocumentMetadata) -> None:
        """Process link tags for additional metadata.

        Parameters
        ----------
        head : BeautifulSoup tag
            The HTML head section
        metadata : DocumentMetadata
            The metadata object to update

        """
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

    def _extract_microdata(self, document: Any) -> dict[str, Any]:
        """Extract microdata and structured data from document.

        Parameters
        ----------
        document : BeautifulSoup
            Parsed HTML document

        Returns
        -------
        dict
            Dictionary containing extracted microdata (opengraph, twitter_card, items, json_ld)

        """
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
                item = {"type": scope.get("itemtype", ""), "properties": {}}

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

            json_ld_data = []
            for script in json_ld_scripts:
                try:
                    # M9: Check JSON-LD script size to prevent DoS via large JSON payloads
                    script_content = script.string or ""
                    if len(script_content) > MAX_JSON_LD_SIZE_BYTES:
                        logger.warning(
                            f"JSON-LD script exceeds maximum size "
                            f"({len(script_content)} > {MAX_JSON_LD_SIZE_BYTES} bytes), "
                            f"skipping to prevent DoS attack"
                        )
                        continue

                    data = json.loads(script_content)
                    json_ld_data.append(data)
                except Exception:
                    pass

            if json_ld_data:
                microdata["json_ld"] = json_ld_data

        return microdata

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        r"""Extract metadata from HTML document.

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

        - ``<title>`` tag in HTML head
        - ``<meta>`` tags with various name/property attributes
        - ``<link>`` tags with rel attributes
        - Open Graph (og:\*) and Twitter Card (twitter:\*) meta tags
        - Dublin Core (dc.\*) meta tags
        - Article meta tags (article:\*)

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

            # Process all meta tags
            meta_tags = head.find_all("meta")
            for meta in meta_tags:
                meta_name = meta.get("name", "").lower() or meta.get("property", "").lower()
                content = meta.get("content", "").strip()

                if meta_name and content:
                    # M13: Check meta tag content size to prevent DoS via oversized meta tags
                    if len(content) > MAX_META_TAG_CONTENT_LENGTH:
                        logger.warning(
                            f"Meta tag '{meta_name}' content exceeds maximum length "
                            f"({len(content)} > {MAX_META_TAG_CONTENT_LENGTH} bytes), "
                            f"truncating to prevent DoS attack"
                        )
                        content = content[:MAX_META_TAG_CONTENT_LENGTH]

                    self._process_meta_tag(meta_name, content, metadata)

            # Detect charset
            self._detect_charset(head, metadata)

            # Process link tags
            self._process_link_tags(head, metadata)

        # Fallback title extraction from Open Graph
        if not metadata.title:
            og_title = document.find("meta", property="og:title")
            if og_title:
                metadata.title = og_title.get("content", "").strip()

        # Fallback title extraction from body h1
        if not metadata.title:
            h1 = document.find("h1")
            if h1:
                metadata.title = h1.get_text(strip=True)

        # Extract enhanced microdata if enabled
        if self.options.extract_microdata:
            microdata = self._extract_microdata(document)
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

        # Use centralized element safety check from html_sanitizer utility
        return is_element_safe(element, strip_framework_attributes=self.options.strip_framework_attributes)

    def _apply_custom_sanitization(self, soup: Any) -> Any:
        """Apply custom sanitization with user-specified attribute allowlists.

        This method handles sanitization when custom allowed_elements or allowed_attributes
        are specified, using multi-pass BeautifulSoup processing. For standard sanitization
        without custom allowlists, use the shared html_sanitizer utility instead.

        Parameters
        ----------
        soup : BeautifulSoup
            BeautifulSoup object to sanitize

        Returns
        -------
        BeautifulSoup
            Sanitized BeautifulSoup object

        """
        # Strip dangerous elements if requested
        if self.options.strip_dangerous_elements:
            # Remove script and style tags completely (including all content for security)
            for tag in soup.find_all(["script", "style"]):
                # Decompose completely to avoid any script content in output
                tag.decompose()

            # Collect other dangerous elements and elements with dangerous attributes
            elements_to_remove = []
            for element in soup.find_all():
                if hasattr(element, "name"):
                    # Check for other dangerous elements (not script/style, already removed)
                    if element.name in DANGEROUS_HTML_ELEMENTS and element.name not in ["script", "style"]:
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
                    allowed_attrs: Union[tuple[str, ...], dict[str, tuple[str, ...]]]
                    if is_per_element:
                        # Per-element allowlist: check element-specific allowed attributes
                        assert isinstance(self.options.allowed_attributes, dict)
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
                if hasattr(element, "name"):
                    # Use _sanitize_element to check for dangerous attributes
                    if not self._sanitize_element(element):
                        elements_to_remove.append(element)

            # Remove elements that failed final sanitization check
            for element in elements_to_remove:
                # Decompose completely for security (don't preserve children from dangerous elements)
                element.decompose()

        return soup

    # Dispatch table mapping HTML element names to processing methods
    _ELEMENT_HANDLERS = {
        # Block elements
        "p": "_process_block_to_ast",
        "div": "_process_block_to_ast",
        "h1": "_process_heading_to_ast",
        "h2": "_process_heading_to_ast",
        "h3": "_process_heading_to_ast",
        "h4": "_process_heading_to_ast",
        "h5": "_process_heading_to_ast",
        "h6": "_process_heading_to_ast",
        "ul": "_process_list_to_ast",
        "ol": "_process_list_to_ast",
        "pre": "_process_code_block_to_ast",
        "blockquote": "_process_blockquote_to_ast",
        "figure": "_process_figure_to_ast",
        "details": "_process_details_to_ast",
        "table": "_process_table_to_ast",
        "dl": "_process_definition_list_to_ast",
        # Inline elements
        "strong": "_process_strong_to_ast",
        "b": "_process_strong_to_ast",
        "em": "_process_emphasis_to_ast",
        "i": "_process_emphasis_to_ast",
        "del": "_process_strikethrough_to_ast",
        "s": "_process_strikethrough_to_ast",
        "strike": "_process_strikethrough_to_ast",
        "sup": "_process_superscript_to_ast",
        "sub": "_process_subscript_to_ast",
        "a": "_process_link_to_ast",
        "img": "_process_image_to_ast",
        "u": "_process_underline_to_ast",
    }

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
        from bs4.element import Comment, NavigableString

        # Handle HTML comments
        if isinstance(node, Comment):
            if self.options.strip_comments:
                return None
            comment_text = str(node).strip()
            if comment_text:
                return CommentInline(content=comment_text, metadata={"comment_type": "html"})
            return None

        # Handle text nodes
        if isinstance(node, NavigableString):
            text = self._decode_entities(str(node))
            if self.options.collapse_whitespace:
                text = re.sub(r"\s+", " ", text)
            if text.strip():
                return Text(content=text)
            return None

        # Handle nodes without name attribute
        if not hasattr(node, "name"):
            return None

        # Skip script/style nodes
        if node.name in ("script", "style"):
            return None

        # Handle <br> with custom logic based on options
        if node.name == "br":
            if self.options.br_handling == "space":
                return Text(content=" ")
            else:  # "newline"
                return LineBreak(soft=False)

        # Handle <hr> as thematic break
        if node.name == "hr":
            return ThematicBreak()

        # Handle <code> with context-dependent logic
        if node.name == "code":
            if self._in_code_block:
                return Text(content=node.get_text())
            else:
                return Code(content=node.get_text())

        # Use dispatch table for other elements
        handler_name = self._ELEMENT_HANDLERS.get(node.name)
        if handler_name:
            handler = getattr(self, handler_name)
            return handler(node)

        # For unknown elements, route based on whether they're block or inline
        if self._is_block_element(node):
            # Unknown block element (e.g., <header>, <footer>, <nav>, <section>)
            # Process as block container to properly handle block children
            return self._process_block_to_ast(node)
        else:
            # Unknown inline element - process children as inline
            return self._process_children_to_inline(node)

    def _is_block_element(self, node: Any) -> bool:
        """Check if HTML element is block-level.

        Parameters
        ----------
        node : Any
            HTML element node

        Returns
        -------
        bool
            True if element is block-level, False otherwise

        """
        if not hasattr(node, "name") or not isinstance(node.name, str):
            return False
        return node.name in self.BLOCK_ELEMENTS

    def _has_block_children(self, node: Any) -> bool:
        """Check if node has any block-level children.

        Parameters
        ----------
        node : Any
            HTML element node

        Returns
        -------
        bool
            True if node contains block-level children, False otherwise

        """
        if not hasattr(node, "children"):
            return False
        for child in node.children:
            if self._is_block_element(child):
                return True
        return False

    def _process_block_container(self, node: Any) -> list[Node]:
        """Process a block container element (div, section, etc.).

        Extracts and returns direct block children, properly handling
        mixed inline/block content. When inline content is encountered
        between blocks, it is wrapped in a Paragraph node.

        Parameters
        ----------
        node : Any
            Block container element

        Returns
        -------
        list of Node
            List of block nodes (Paragraph, Heading, List, etc.)

        """
        children: list[Node] = []
        inline_buffer: list[Node] = []

        for child in node.children:
            if self._is_block_element(child):
                # Block element: flush inline buffer first
                if inline_buffer:
                    children.append(Paragraph(content=inline_buffer))
                    inline_buffer = []

                # Process block element
                block_node = self._process_node_to_ast(child)
                if block_node:
                    if isinstance(block_node, list):
                        children.extend(block_node)
                    else:
                        children.append(block_node)
            else:
                # Inline element or text: add to buffer
                inline_nodes = self._process_node_to_ast(child)
                if inline_nodes:
                    if isinstance(inline_nodes, list):
                        inline_buffer.extend(inline_nodes)
                    else:
                        inline_buffer.append(inline_nodes)

        # Flush remaining inline content
        if inline_buffer:
            children.append(Paragraph(content=inline_buffer))

        return children

    def _process_block_to_ast(self, node: Any) -> Paragraph | list[Node] | None:
        """Process block element (p, div) to Paragraph or list of block nodes.

        For <div> and other block containers: if they contain block children,
        returns a list of block nodes. If they only contain inline content,
        wraps it in a Paragraph.

        Parameters
        ----------
        node : Any
            Block element node

        Returns
        -------
        Paragraph, list of Node, or None
            - List of block nodes if element contains blocks (e.g., nested divs)
            - Paragraph node if element only contains inline content
            - None if element is empty

        """
        # Check if this container has block-level children
        if self._has_block_children(node):
            # Process as block container - extract and flatten block children
            return self._process_block_container(node)
        else:
            # Only inline content - wrap in paragraph
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
            Converted node based on figures_parsing option

        """
        if self.options.figures_parsing == "html":
            # Preserve as HTML
            return HTMLBlock(content=str(node))

        # Extract figcaption if present
        figcaption = node.find("figcaption")
        caption_text = figcaption.get_text(strip=True) if figcaption else None

        # Find image in figure
        img_node = node.find("img")

        if self.options.figures_parsing == "image_with_caption":
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
            Converted node based on details_parsing option

        """
        if self.options.details_parsing == "skip":
            return None

        if self.options.details_parsing == "html":
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
            if hasattr(child, "name") and child.name == "summary":
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

        # Process thead - use only first row as header, remaining as body rows
        thead = node.find("thead")
        if thead:
            thead_rows = thead.find_all("tr", recursive=False)

            if thead_rows:
                # Use only the first row as the header to avoid malformed tables
                # where header cell count doesn't match body cell count
                header_cells = []
                first_header_tr = thead_rows[0]
                for th in first_header_tr.find_all(["th", "td"]):
                    content = self._process_table_cell_content(th)
                    alignment = self._get_alignment(th)
                    alignments.append(alignment)
                    header_cells.append(TableCell(content=content))

                if header_cells:
                    header = TableRow(cells=header_cells, is_header=True)

                # Add remaining thead rows as body rows to preserve content
                for header_tr in thead_rows[1:]:
                    row_cells = []
                    for td in header_tr.find_all(["td", "th"]):
                        content = self._process_table_cell_content(td)
                        row_cells.append(TableCell(content=content))
                    rows.append(TableRow(cells=row_cells))

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
                    content = self._process_table_cell_content(th)
                    alignment = self._get_alignment(th)
                    alignments.append(alignment)
                    header_cells.append(TableCell(content=content))
                header = TableRow(cells=header_cells, is_header=True)
            else:
                # This is a data row
                row_cells = []
                for td in tr.find_all(["td", "th"]):
                    content = self._process_table_cell_content(td)
                    row_cells.append(TableCell(content=content))
                rows.append(TableRow(cells=row_cells))

        # Process tfoot rows (add them as regular data rows)
        tfoot = node.find("tfoot")
        if tfoot:
            for tr in tfoot.find_all("tr", recursive=False):
                row_cells = []
                for td in tr.find_all(["td", "th"]):
                    content = self._process_table_cell_content(td)
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

    def _process_definition_list_to_ast(self, node: Any) -> DefinitionList:
        """Process dl element to DefinitionList node.

        Parameters
        ----------
        node : Any
            DL element

        Returns
        -------
        DefinitionList
            Definition list node

        """
        items: list[tuple[DefinitionTerm, list[DefinitionDescription]]] = []
        current_term: DefinitionTerm | None = None
        current_descriptions: list[DefinitionDescription] = []

        for child in node.children:
            if not hasattr(child, "name"):
                continue

            if child.name == "dt":
                # Save previous term/descriptions if any
                if current_term is not None:
                    items.append((current_term, current_descriptions))

                # Start new term
                term_content = self._process_children_to_inline(child)
                current_term = DefinitionTerm(content=term_content)
                current_descriptions = []

            elif child.name == "dd":
                # Add description - process block-level content
                desc_children: list[Node] = []
                for desc_child in child.children:
                    ast_nodes = self._process_node_to_ast(desc_child)
                    if ast_nodes:
                        if isinstance(ast_nodes, list):
                            desc_children.extend(ast_nodes)
                        else:
                            desc_children.append(ast_nodes)

                if desc_children:
                    current_descriptions.append(DefinitionDescription(content=desc_children))

        # Add last term/descriptions
        if current_term is not None:
            items.append((current_term, current_descriptions))

        return DefinitionList(items=items)

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

    def _process_strikethrough_to_ast(self, node: Any) -> Strikethrough:
        """Process del/s/strike element to Strikethrough node.

        Parameters
        ----------
        node : Any
            Del, s, or strike element

        Returns
        -------
        Strikethrough
            Strikethrough node

        """
        content = self._process_children_to_inline(node)
        return Strikethrough(content=content)

    def _process_superscript_to_ast(self, node: Any) -> Superscript:
        """Process sup element to Superscript node.

        Parameters
        ----------
        node : Any
            Sup element

        Returns
        -------
        Superscript
            Superscript node

        """
        content = self._process_children_to_inline(node)
        return Superscript(content=content)

    def _process_subscript_to_ast(self, node: Any) -> Subscript:
        """Process sub element to Subscript node.

        Parameters
        ----------
        node : Any
            Sub element

        Returns
        -------
        Subscript
            Subscript node

        """
        content = self._process_children_to_inline(node)
        return Subscript(content=content)

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

        # Resolve relative URLs using base_url for links (separate from attachment_base_url)
        if url:
            url = self._resolve_url(url, base_url=self.options.base_url)

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
                allow_cwd_files=self.options.local_files.allow_cwd_files,
            )

            if not is_allowed:
                # Local file access denied - return image with empty URL and alt text only
                logger.warning(f"Local file access denied for file:// URL (security policy): {resolved_src[:100]}")
                return Image(url="", alt_text=alt_text, title=title)

        # Current attachment mode (may change on error)
        current_attachment_mode = self.options.attachment_mode

        # Fetch image data if needed for base64 or save modes
        image_data = None
        if current_attachment_mode in ["base64", "save"]:
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

        # Convert result to Image node using helper
        image_node = attachment_result_to_image_node(result, fallback_alt_text=alt_text or "image")
        if image_node and isinstance(image_node, Image):
            # Preserve title if provided
            if title:
                image_node.title = title
            return image_node

        return Image(url="", alt_text=alt_text, title=title)

    def _resolve_url(self, url: str, base_url: str | None = None) -> str:
        """Resolve relative URL to absolute URL if base URL is provided.

        Parameters
        ----------
        url : str
            URL to resolve
        base_url : str or None, default None
            Base URL to use for resolution. If None, uses attachment_base_url
            from options (for backward compatibility with images/assets).

        Returns
        -------
        str
            Resolved absolute URL or original URL

        """
        # Use provided base_url or fall back to attachment_base_url
        effective_base = base_url if base_url is not None else self.options.attachment_base_url

        if not effective_base or urlparse(url).scheme:
            return url
        return urljoin(effective_base, url)

    def _read_local_file(self, file_url: str) -> bytes:
        """Read image data from local file:// URL.

        SECURITY: This method should ONLY be called after validate_local_file_access
        has confirmed access is allowed. Uses file descriptors to prevent TOCTOU
        (Time-of-Check-Time-of-Use) race conditions.

        M11: Fixed TOCTOU vulnerability by using file descriptors. The file is opened
        first, then validated using fstat on the descriptor, then read. This prevents
        attacks where a file is swapped between validation and reading.

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
        # Resolve file URL to canonical path
        try:
            file_path = resolve_file_url_to_path(file_url)
        except ValueError as e:
            raise Exception(f"Invalid file URL: {e}") from e

        # M11: Use file descriptors to prevent TOCTOU attacks
        # Open the file first to get a file descriptor
        fd = None
        try:
            # Open file with O_RDONLY flag and get file descriptor
            fd = os.open(str(file_path), os.O_RDONLY)

            # Validate the file descriptor using fstat (prevents symlink swaps)
            stat_info = os.fstat(fd)

            # Check if it's a regular file (not a directory, device, etc.)
            if not stat.S_ISREG(stat_info.st_mode):
                raise Exception(f"Path is not a regular file: {file_path}")

            # Check file size before reading
            file_size = stat_info.st_size
            if file_size > self.options.max_asset_size_bytes:
                raise Exception(
                    f"Local file exceeds maximum allowed size: "
                    f"{file_size} bytes > {self.options.max_asset_size_bytes} bytes"
                )

            # Read from the file descriptor
            data = os.read(fd, file_size)

            return data

        except FileNotFoundError as e:
            raise Exception(f"Local file not found: {file_path}") from e
        except PermissionError as e:
            raise Exception(f"Permission denied reading local file: {file_path}") from e
        except Exception as e:
            if "not a regular file" in str(e):
                raise
            raise Exception(f"Failed to read local file {file_path}: {e}") from e
        finally:
            # Always close the file descriptor if it was opened
            if fd is not None:
                try:
                    os.close(fd)
                except Exception:
                    pass  # Best effort cleanup

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
                max_size_bytes=self.options.max_asset_size_bytes,
                timeout=self.options.network.network_timeout,
                require_head_success=self.options.network.require_head_success,
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
        alt_only_match = re.match(r"^!\[([^]]*)]$", markdown_image)
        if alt_only_match:
            return ""

        # If it doesn't match expected format, return empty
        return ""

    def _process_children_to_inline(self, node: Any) -> list[Node]:
        """Process node children to inline nodes ONLY.

        Handles consecutive BR tags by ensuring proper spacing when inline
        text follows multiple line breaks.

        If block elements are encountered, logs a warning and skips them.
        This should not happen with proper block/inline separation.

        Parameters
        ----------
        node : Any
            Parent node

        Returns
        -------
        list of Node
            List of inline nodes (no block nodes)

        """
        result: list[Node] = []
        consecutive_breaks = 0

        for child in node.children:
            # Skip block elements - they shouldn't be here with proper separation
            if self._is_block_element(child):
                logger.debug(
                    f"Block element <{child.name}> found in inline context - skipping. "
                    f"This indicates the element should be processed as a block container."
                )
                continue

            ast_nodes = self._process_node_to_ast(child)
            if ast_nodes:
                if isinstance(ast_nodes, list):
                    for ast_node in ast_nodes:
                        if isinstance(ast_node, LineBreak):
                            consecutive_breaks += 1
                            result.append(ast_node)
                        else:
                            # Non-LineBreak node: check if we need spacing after consecutive breaks
                            if consecutive_breaks > 1 and isinstance(ast_node, Text):
                                # Add a separator space to prevent text merging after multiple breaks
                                # Only if the text doesn't already start with whitespace
                                if ast_node.content and not ast_node.content[0].isspace():
                                    result.append(Text(content=" "))
                            result.append(ast_node)
                            consecutive_breaks = 0
                else:
                    if isinstance(ast_nodes, LineBreak):
                        consecutive_breaks += 1
                        result.append(ast_nodes)
                    else:
                        # Non-LineBreak node: check if we need spacing after consecutive breaks
                        if consecutive_breaks > 1 and isinstance(ast_nodes, Text):
                            # Add a separator space to prevent text merging after multiple breaks
                            # Only if the text doesn't already start with whitespace
                            if ast_nodes.content and not ast_nodes.content[0].isspace():
                                result.append(Text(content=" "))
                        result.append(ast_nodes)
                        consecutive_breaks = 0

        return result

    def _process_table_cell_content(self, cell_node: Any) -> list[Node]:
        """Process table cell content, handling both inline and block elements.

        Table cells can contain complex nested content including lists, paragraphs,
        and code blocks. This method flattens block content into an inline
        representation suitable for table cells while preserving inline formatting.

        Parameters
        ----------
        cell_node : Any
            Table cell node (td or th)

        Returns
        -------
        list of Node
            List of inline nodes representing the cell content

        """
        # Check if cell contains only inline content
        if not self._has_block_children(cell_node):
            # Simple case: only inline content
            return self._process_children_to_inline(cell_node)

        # Complex case: cell has block-level children
        # We need to flatten them into inline format while preserving inline formatting
        result: list[Node] = []

        for child in cell_node.children:
            from bs4.element import NavigableString

            # Handle text nodes directly
            if isinstance(child, NavigableString):
                text = self._decode_entities(str(child))
                if self.options.collapse_whitespace:
                    text = re.sub(r"\s+", " ", text)
                if text.strip():
                    result.append(Text(content=text))
                continue

            # Skip non-element nodes
            if not hasattr(child, "name"):
                continue

            # Process block elements by recursively extracting inline content
            if self._is_block_element(child):
                # Recursively extract inline nodes from within the block element
                block_inline_content = self._extract_inline_from_block(child)
                if block_inline_content:
                    # Add space before if we have prior content
                    if result and not (isinstance(result[-1], Text) and result[-1].content.endswith(" ")):
                        result.append(Text(content=" "))
                    result.extend(block_inline_content)
            else:
                # Process inline elements normally
                ast_nodes = self._process_node_to_ast(child)
                if ast_nodes:
                    if isinstance(ast_nodes, list):
                        result.extend(ast_nodes)
                    else:
                        result.append(ast_nodes)

        return result

    def _extract_inline_from_block(self, block_node: Any) -> list[Node]:
        """Extract inline content from a block element, flattening the structure.

        This is used for table cells and other contexts where block elements
        need to be represented inline.

        Parameters
        ----------
        block_node : Any
            Block element node

        Returns
        -------
        list of Node
            List of inline nodes extracted from the block

        """
        result: list[Node] = []

        for child in block_node.children:
            from bs4.element import NavigableString

            # Handle text nodes
            if isinstance(child, NavigableString):
                text = self._decode_entities(str(child))
                if self.options.collapse_whitespace:
                    text = re.sub(r"\s+", " ", text)
                if text.strip():
                    result.append(Text(content=text))
                continue

            # Skip non-element nodes
            if not hasattr(child, "name"):
                continue

            # Skip script/style nodes
            if child.name in ("script", "style"):
                continue

            # If we encounter another block element, recurse
            if self._is_block_element(child):
                nested_inline = self._extract_inline_from_block(child)
                if nested_inline:
                    # Add space separator between block elements
                    if result and not (isinstance(result[-1], Text) and result[-1].content.endswith(" ")):
                        result.append(Text(content=" "))
                    result.extend(nested_inline)
            else:
                # Process inline elements normally
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
            "js": "javascript",
            "ts": "typescript",
            "py": "python",
            "rb": "ruby",
            "sh": "bash",
            "yml": "yaml",
            "md": "markdown",
            "cs": "csharp",
            "fs": "fsharp",
            "kt": "kotlin",
            "rs": "rust",
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

        # M12: Check fragment content for dangerous schemes before preserving relative URLs
        # URLs like #javascript:alert(1) should be blocked
        if url_lower.startswith("#"):
            # Extract the fragment content (everything after #)
            fragment = url_lower[1:]
            # Check if the fragment contains dangerous schemes
            dangerous_schemes_in_fragment = ["javascript:", "data:", "vbscript:"]
            if any(scheme in fragment for scheme in dangerous_schemes_in_fragment):
                logger.warning(
                    f"Blocked anchor link with dangerous scheme in fragment: "
                    f"{url[:100]}{'...' if len(url) > 100 else ''}"
                )
                return ""
            # Safe fragment, preserve it
            return url

        # Preserve other relative URLs
        if url_lower.startswith(("/", "./", "../", "?")):
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
                f"Blocked link with unsupported scheme '{scheme}:' (URL: {url[:100]}{'...' if len(url) > 100 else ''})"
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
    parser_required_packages=[("beautifulsoup4", "bs4", ">=4.14.2")],
    renderer_required_packages=[],
    optional_packages=[("readability-lxml", "readability")],
    parser_options_class=HtmlOptions,
    renderer_options_class="all2md.options.html.HtmlRendererOptions",
    description="Convert HTML documents to/from AST",
    priority=5,
)
