#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/html2markdown.py
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
---------------------
- Hash-style vs. underline-style headings
- Emphasis symbols (* vs _)
- Custom bullet symbols for lists
- Image handling modes (embed, remove, convert)
- Title extraction from HTML head

Security Considerations
-----------------------
This module includes multiple layers of security protection to prevent XSS attacks
and other security vulnerabilities when converting HTML to Markdown.

**Link Scheme Validation (Always Active)**

All link URLs (href attributes in <a> tags) are automatically validated to prevent
XSS attacks via dangerous URL schemes. This validation is ALWAYS performed,
regardless of the `strip_dangerous_elements` setting, providing defense-in-depth
protection. Dangerous schemes that are blocked include:

- `javascript:` - Executes JavaScript when clicked
- `vbscript:` - Executes VBScript (older browsers)
- `data:text/html`, `data:text/javascript` - Can contain executable code

Only safe schemes are allowed: http, https, mailto, ftp, ftps, tel, sms.
Relative URLs (e.g., /page, ./file.html, #anchor) are preserved.

When `require_https=True`, only HTTPS links are allowed (except mailto, tel, sms).

**Content Sanitization (Optional)**

The `strip_dangerous_elements` option provides additional protection by removing
potentially dangerous HTML elements and attributes during DOM processing:

- Script and style tags (always removed, even when option is False)
- Event handler attributes (onclick, onerror, etc.)
- Potentially unsafe elements (object, embed, iframe, form, input, etc.)

**Best Practices for Production Applications**

For production applications handling untrusted HTML content:

1. **Use Specialized Sanitization Libraries**: Consider using dedicated HTML
   sanitization libraries such as Bleach (pip install bleach) which provide
   more comprehensive whitelist-based sanitization:

   ```python
   import bleach
   safe_html = bleach.clean(untrusted_html, tags=['p', 'em', 'strong'], strip=True)
   markdown = html_to_markdown(safe_html)
   ```

2. **Implement Content Security Policy (CSP)**: For web applications, implement
   CSP headers to provide defense-in-depth protection against XSS attacks.

3. **Validate User Input**: Always validate and sanitize user-provided HTML
   before processing.

4. **Network Security**: When `allow_remote_fetch=True`, be aware of potential
   SSRF (Server-Side Request Forgery) risks. Use `allowed_hosts` and `require_https`
   options to restrict which remote resources can be fetched.

HTML sanitization is complex, and new attack vectors are discovered regularly.
Always use defense-in-depth strategies and consider the security requirements of your
specific use case.

Encoding Handling
-----------------
HTML files are read with the following encoding fallback strategy:

1. **UTF-8** (default): Attempts to read as UTF-8
2. **UTF-8-sig**: Falls back to UTF-8 with BOM handling if UTF-8 fails
3. **chardet** (optional): If chardet is installed, attempts auto-detection
4. **Latin-1** (fallback): Final fallback that never fails but may produce mojibake

For best results with non-UTF-8 HTML files:
- Convert files to UTF-8 before processing, or
- Install chardet for automatic encoding detection: pip install chardet

Dependencies
------------
- beautifulsoup4: For HTML parsing and DOM manipulation
- re: For pattern matching and text processing
- chardet (optional): For automatic encoding detection of non-UTF-8 files

Examples
--------
Basic HTML string conversion:

    >>> from all2md.parsers.html2markdown import html_to_markdown
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
    DEFAULT_USE_HASH_HEADINGS,
    MARKDOWN_SPECIAL_CHARS,
    MAX_CODE_FENCE_LENGTH,
    MAX_LANGUAGE_IDENTIFIER_LENGTH,
    MIN_CODE_FENCE_LENGTH,
    SAFE_LANGUAGE_IDENTIFIER_PATTERN,
    SAFE_LINK_SCHEMES,
    TABLE_ALIGNMENT_MAPPING,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import InputError, MarkdownConversionError
from all2md.options import HtmlOptions, MarkdownOptions, create_updated_options
from all2md.utils.attachments import process_attachment
from all2md.utils.inputs import is_path_like, validate_and_convert_input
from all2md.utils.metadata import DocumentMetadata, prepend_metadata_if_enabled

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
    MarkdownConversionError
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
    last_error = None
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
    raise MarkdownConversionError(
        f"Failed to read HTML file with any encoding: {last_error}",
        conversion_stage="file_reading",
        original_error=last_error
    )


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
    converter_module="all2md.parsers.html2markdown",
    converter_function="html_to_markdown",
    required_packages=[("beautifulsoup4", "bs4", "")],
    optional_packages=[],
    import_error_message=("HTML conversion requires 'beautifulsoup4'. Install with: pip install beautifulsoup4"),
    options_class="HtmlOptions",
    description="Convert HTML documents to Markdown",
    priority=5,
)


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
    - Uses encoding fallback for file inputs: UTF-8 → UTF-8-sig → chardet (if installed) → Latin-1
    - Preserves HTML structure including tables, lists, and formatting
    - Configurable heading styles and list formatting

    Encoding Handling
    -----------------
    When reading HTML files from disk, the converter tries multiple encodings:
    1. UTF-8 (most common for modern HTML)
    2. UTF-8-sig (handles UTF-8 files with BOM)
    3. chardet auto-detection (if chardet package is installed)
    4. Latin-1 fallback (never fails but may produce incorrect characters)

    For best results with non-UTF-8 files, install chardet: pip install chardet
    """
    # Handle backward compatibility and merge options
    if options is None:
        options = HtmlOptions()

    # Determine if input_data is HTML content or a file path/object
    html_content = ""
    if isinstance(input_data, str):
        # Check if it's a file path or HTML content
        if is_path_like(input_data) and os.path.exists(str(input_data)):
            # It's a file path - read the file with encoding fallback
            try:
                html_content = _read_html_file_with_encoding_fallback(input_data)
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
                # Read from file path with encoding fallback
                html_content = _read_html_file_with_encoding_fallback(doc_input)
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

        # Use new AST-based conversion path
        from all2md.parsers.html import HtmlToAstConverter
        from all2md.ast import MarkdownRenderer

        # Convert HTML to AST
        ast_converter = HtmlToAstConverter(options)
        ast_document = ast_converter.convert_to_ast(html_content)

        # Get MarkdownOptions (use provided or create default)
        md_opts = options.markdown_options if options.markdown_options else MarkdownOptions()

        # Render AST to markdown using MarkdownOptions directly
        renderer = MarkdownRenderer(md_opts)
        result = renderer.render(ast_document)

        # Prepend metadata if enabled
        result = prepend_metadata_if_enabled(result, metadata, options.extract_metadata)

        return result
    except Exception as e:
        raise MarkdownConversionError(
            f"Failed to convert HTML to Markdown: {str(e)}", conversion_stage="html_parsing", original_error=e
        ) from e
