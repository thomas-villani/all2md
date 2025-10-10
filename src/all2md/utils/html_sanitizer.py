#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/html_sanitizer.py
"""HTML sanitization utilities for security.

This module provides utilities for sanitizing HTML content to prevent XSS
and other security vulnerabilities. It supports both string-based sanitization
(for renderers) and BeautifulSoup element validation (for parsers).

The module supports multiple sanitization strategies:
- pass-through: No sanitization (use only with trusted content)
- escape: HTML-escape all content
- drop: Remove HTML nodes entirely
- sanitize: Remove dangerous elements/attributes but preserve safe HTML
"""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import urlparse
import logging

from all2md.constants import (
    DANGEROUS_HTML_ATTRIBUTES,
    DANGEROUS_HTML_ELEMENTS,
    DANGEROUS_SCHEMES, HtmlPassthroughMode,
)

logger = logging.getLogger(__name__)

def sanitize_html_content(
    content: str,
    mode: HtmlPassthroughMode = "pass-through"
) -> str:
    """Sanitize HTML content string according to the specified mode.

    This function is designed for use in renderers when processing HTMLBlock
    and HTMLInline AST nodes.

    Parameters
    ----------
    content : str
        HTML content to sanitize
    mode : {"pass-through", "escape", "drop", "sanitize"}, default "pass-through"
        Sanitization mode:
        - "pass-through": Return content unchanged (for trusted sources)
        - "escape": HTML-escape all content
        - "drop": Return empty string (remove all HTML)
        - "sanitize": Remove dangerous elements and attributes

    Returns
    -------
    str
        Sanitized HTML content

    Examples
    --------
    >>> sanitize_html_content("<script>alert('xss')</script>", mode="escape")
    '&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;'

    >>> sanitize_html_content("<script>alert('xss')</script>", mode="drop")
    ''

    >>> sanitize_html_content("<p>Hello <strong>world</strong></p>", mode="sanitize")
    '<p>Hello <strong>world</strong></p>'

    >>> sanitize_html_content("<script>alert('xss')</script>", mode="sanitize")
    ''
    """
    if mode == "pass-through":
        return content

    if mode == "escape":
        return html.escape(content)

    if mode == "drop":
        return ""

    if mode == "sanitize":
        return _sanitize_html_string(content)

    # Fallback to pass-through for unknown modes (defensive programming)
    return content  # type: ignore[unreachable]


def _sanitize_html_string(content: str) -> str:
    """Sanitize HTML string by removing dangerous elements and attributes.

    This is a basic string-based sanitizer. For more robust sanitization,
    consider using the bleach library if available.

    Parameters
    ----------
    content : str
        HTML content to sanitize

    Returns
    -------
    str
        Sanitized HTML with dangerous elements/attributes removed
    """
    # Try to use bleach if available for better sanitization
    try:
        import bleach  # type: ignore[import-untyped]

        # Define allowed tags (basic safe HTML)
        allowed_tags = [
            'a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'code',
            'div', 'em', 'i', 'li', 'ol', 'p', 'pre', 'span', 'strong',
            'sub', 'sup', 'u', 'ul', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'table', 'thead', 'tbody', 'tr', 'th', 'td', 'caption',
            'dl', 'dt', 'dd', 'hr', 'img'
        ]

        # Define allowed attributes per tag
        allowed_attributes = {
            'a': ['href', 'title', 'rel'],
            'img': ['src', 'alt', 'title', 'width', 'height'],
            'abbr': ['title'],
            'acronym': ['title'],
            '*': ['class', 'id']  # Allow class and id on all elements
        }

        # Define allowed protocols for URLs
        allowed_protocols = ['http', 'https', 'mailto', 'ftp']

        return bleach.clean(
            content,
            tags=allowed_tags,
            attributes=allowed_attributes,
            protocols=allowed_protocols,
            strip=True
        )
    except ImportError:
        logger.debug("`bleach` not found, falling back to beautifulsoup sanitization")
        # Fallback to basic regex-based sanitization
        return _basic_sanitize_html_string(content)


def _basic_sanitize_html_string(content: str) -> str:
    """BeautifulSoup-based HTML sanitization (fallback when bleach unavailable).

    This provides basic security by removing dangerous elements and attributes
    using BeautifulSoup for proper HTML parsing.

    Parameters
    ----------
    content : str
        HTML content to sanitize

    Returns
    -------
    str
        Sanitized HTML
    """
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(content, 'html.parser')

        # Remove dangerous elements entirely
        for element in DANGEROUS_HTML_ELEMENTS:
            for tag in soup.find_all(element):
                tag.decompose()

        # Remove dangerous attributes from all remaining elements
        for element in soup.find_all():
            if hasattr(element, 'attrs'):
                # Remove dangerous attributes
                attrs_to_remove = []
                for attr_name in element.attrs:
                    if attr_name.lower() in DANGEROUS_HTML_ATTRIBUTES:
                        attrs_to_remove.append(attr_name)

                    # Check URL attributes for dangerous schemes
                    if attr_name.lower() in ('href', 'src', 'action', 'formaction'):
                        attr_value = element.attrs[attr_name]
                        if isinstance(attr_value, str) and not is_url_safe(attr_value):
                            attrs_to_remove.append(attr_name)

                    # Check style-related attributes for dangerous content
                    if attr_name.lower() in ('style', 'background', 'expression'):
                        attr_value = element.attrs[attr_name]
                        if isinstance(attr_value, str):
                            attr_value_lower = attr_value.lower()
                            if any(scheme in attr_value_lower for scheme in DANGEROUS_SCHEMES):
                                attrs_to_remove.append(attr_name)

                for attr in attrs_to_remove:
                    del element.attrs[attr]

        return str(soup)

    except ImportError:
        logger.warning("`bleach` and `beautifulsoup` were not detected for HTML sanitization. "
                       "Falling back to stripping all HTML tags")
        # If BeautifulSoup is not available, fall back to basic text stripping
        # This is a last resort and should rarely happen since bs4 is a core dependency
        return strip_html_tags(content)


def strip_html_tags(content: str) -> str:
    """Remove all HTML tags from content, leaving only text.

    This is useful for extracting plain text from HTML (e.g., for TOC entries).

    Parameters
    ----------
    content : str
        HTML content

    Returns
    -------
    str
        Plain text with HTML tags removed

    Examples
    --------
    >>> strip_html_tags("<p>Hello <strong>world</strong>!</p>")
    'Hello world!'

    >>> strip_html_tags("Plain text")
    'Plain text'
    """
    # Remove all HTML tags
    text = re.sub(r'<[^>]+>', '', content)
    # Decode HTML entities
    text = html.unescape(text)
    return text


def is_element_safe(element: Any) -> bool:
    """Check if a BeautifulSoup element is safe (no dangerous tags/attributes).

    This function is designed for use in the HTML parser (HtmlToAstConverter)
    to validate elements during parsing.

    Parameters
    ----------
    element : Any
        BeautifulSoup element to check

    Returns
    -------
    bool
        True if element is safe, False if it contains dangerous content

    Examples
    --------
    >>> from bs4 import BeautifulSoup
    >>> soup = BeautifulSoup("<p>Safe content</p>", "html.parser")
    >>> is_element_safe(soup.p)
    True

    >>> soup = BeautifulSoup("<script>alert('xss')</script>", "html.parser")
    >>> is_element_safe(soup.script)
    False
    """
    if not hasattr(element, "name"):
        return True

    # Check for dangerous elements
    if element.name in DANGEROUS_HTML_ELEMENTS:
        return False

    # Check for dangerous attributes
    if hasattr(element, 'attrs') and element.attrs:
        for attr_name, attr_value in element.attrs.items():
            if attr_name in DANGEROUS_HTML_ATTRIBUTES:
                return False

            # Enhanced URL scheme checking for href and src attributes
            if isinstance(attr_value, str):
                attr_value_lower = attr_value.lower().strip()

                # Check specific URL attributes for dangerous schemes
                if attr_name.lower() in ("href", "src", "action", "formaction"):
                    if not is_url_safe(attr_value):
                        return False

                # Check for dangerous scheme content in style-related attributes
                elif attr_name.lower() in ("style", "background", "expression"):
                    if any(scheme in attr_value_lower for scheme in DANGEROUS_SCHEMES):
                        return False

    return True


def is_url_safe(url: str) -> bool:
    """Check if a URL is safe (no dangerous schemes).

    Parameters
    ----------
    url : str
        URL to validate

    Returns
    -------
    bool
        True if URL is safe, False if it uses a dangerous scheme

    Examples
    --------
    >>> is_url_safe("https://example.com")
    True

    >>> is_url_safe("javascript:alert('xss')")
    False

    >>> is_url_safe("data:text/html,<script>alert('xss')</script>")
    False
    """
    if not url or not url.strip():
        return True

    url_lower = url.lower().strip()

    # Allow relative URLs
    if url_lower.startswith(("#", "/", "./", "../", "?")):
        return True

    # Parse URL scheme
    try:
        parsed = urlparse(url_lower)
        # Check for explicitly dangerous schemes
        if parsed.scheme in ("javascript", "data", "vbscript", "about"):
            return False

        # Check for dangerous scheme patterns
        if any(url_lower.startswith(scheme) for scheme in DANGEROUS_SCHEMES):
            return False

    except ValueError:
        # If URL parsing fails, consider it unsafe
        return False

    return True


def sanitize_url(url: str) -> str:
    """Sanitize a URL by removing dangerous schemes.

    Parameters
    ----------
    url : str
        URL to sanitize

    Returns
    -------
    str
        Sanitized URL, or empty string if the URL is dangerous

    Examples
    --------
    >>> sanitize_url("https://example.com")
    'https://example.com'

    >>> sanitize_url("javascript:alert('xss')")
    ''

    >>> sanitize_url("/relative/path")
    '/relative/path'
    """
    if not is_url_safe(url):
        return ""
    return url


__all__ = [
    "sanitize_html_content",
    "strip_html_tags",
    "is_element_safe",
    "is_url_safe",
    "sanitize_url",
]
