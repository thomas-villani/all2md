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
import logging
import re
from typing import Any

from all2md.constants import (
    DANGEROUS_HTML_ATTRIBUTES,
    DANGEROUS_HTML_ELEMENTS,
    DANGEROUS_SCHEMES,
    HtmlPassthroughMode,
)

logger = logging.getLogger(__name__)


def _is_style_safe(style_value: str) -> bool:
    """Check if a CSS style attribute value is safe.

    Checks for dangerous patterns in CSS including:
    - expression() function (IE-specific XSS)
    - url() function with dangerous schemes (javascript:, data:text/html, etc.)

    Parameters
    ----------
    style_value : str
        CSS style attribute value to check

    Returns
    -------
    bool
        True if style is safe, False if it contains dangerous patterns

    Examples
    --------
        >>> _is_style_safe("color: red; font-size: 12px;")
        True
        >>> _is_style_safe("background: url(javascript:alert(1))")
        False
        >>> _is_style_safe("width: expression(alert(1))")
        False

    """
    if not style_value:
        return True

    style_lower = style_value.lower()

    # Check for IE-specific expression() function
    if 'expression(' in style_lower or 'expression (' in style_lower:
        return False

    # Check for url() with dangerous schemes
    # Match url(...) patterns and extract the URL
    url_pattern = r'url\s*\(\s*["\']?\s*([^)"\']+)'
    matches = re.finditer(url_pattern, style_lower)

    for match in matches:
        url = match.group(1).strip()
        # Check if the URL uses a dangerous scheme
        if not is_url_safe(url):
            return False

    return True


def _sanitize_srcset(srcset_value: str) -> str | None:
    """Sanitize an HTML srcset attribute value.

    Parses srcset format and removes or rejects URLs with dangerous schemes.
    The srcset format is: "url1 descriptor1, url2 descriptor2, ..."

    Parameters
    ----------
    srcset_value : str
        srcset attribute value to sanitize

    Returns
    -------
    str or None
        Sanitized srcset with only safe URLs, or None if all URLs are unsafe

    Examples
    --------
        >>> _sanitize_srcset("image1.jpg 1x, image2.jpg 2x")
        'image1.jpg 1x, image2.jpg 2x'
        >>> _sanitize_srcset("javascript:alert(1) 1x")
        None
        >>> _sanitize_srcset("safe.jpg 1x, javascript:alert(1) 2x")
        'safe.jpg 1x'

    """
    if not srcset_value:
        return None

    # Split by comma to get individual srcset entries
    entries = srcset_value.split(',')
    safe_entries = []

    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue

        # Split by whitespace to separate URL from descriptor
        # Format: "url descriptor" or just "url"
        parts = entry.split(None, 1)
        if not parts:
            continue

        url = parts[0]
        descriptor = parts[1] if len(parts) > 1 else ''

        # Check if URL is safe
        if is_url_safe(url):
            # Reconstruct the entry with the descriptor if present
            if descriptor:
                safe_entries.append(f"{url} {descriptor}")
            else:
                safe_entries.append(url)

    # Return None if no safe entries remain
    if not safe_entries:
        return None

    return ', '.join(safe_entries)


def sanitize_html_content(
        content: str,
        mode: HtmlPassthroughMode = "escape"
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
        from bleach.css_sanitizer import CSSSanitizer  # type: ignore[import-untyped]

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
            'img': ['src', 'srcset', 'alt', 'title', 'width', 'height'],
            'abbr': ['title'],
            'acronym': ['title'],
            '*': ['class', 'id', 'style']  # Allow class, id, and style on all elements
        }

        # Define allowed protocols for URLs
        allowed_protocols = ['http', 'https', 'mailto', 'ftp']

        # Define CSS sanitizer with common safe properties
        css_sanitizer = CSSSanitizer(
            allowed_css_properties=[
                'color', 'background-color', 'font-size', 'font-family', 'font-weight',
                'text-align', 'text-decoration', 'margin', 'padding', 'border',
                'width', 'height', 'display', 'float', 'position', 'top', 'bottom',
                'left', 'right', 'z-index', 'line-height', 'letter-spacing',
                'background', 'border-radius', 'box-shadow', 'opacity'
            ]
        )

        # Create a custom filter to sanitize srcset attributes
        def filter_attributes(tag: str, name: str, value: str) -> bool:
            """Filter function to sanitize srcset attributes."""
            # Check if attribute is in the allowed list for this tag
            tag_attrs = allowed_attributes.get(tag, [])
            global_attrs = allowed_attributes.get('*', [])

            if name not in tag_attrs and name not in global_attrs:
                return False

            # Additional checks for style attribute
            if name == 'style':
                return _is_style_safe(value)

            # Additional checks for srcset attribute
            if name == 'srcset':
                # Sanitize srcset and update value
                # Note: bleach doesn't allow modifying values in filter, so we'll handle this differently
                return _sanitize_srcset(value) is not None

            return True

        cleaned = bleach.clean(
            content,
            tags=allowed_tags,
            attributes=filter_attributes,
            protocols=allowed_protocols,
            css_sanitizer=css_sanitizer,
            strip=True
        )

        # Post-process to sanitize srcset values (bleach doesn't allow modifying attribute values)
        # We need to parse the HTML again and fix srcset attributes
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(cleaned, 'html.parser')

            for img in soup.find_all('img'):
                if 'srcset' in img.attrs:
                    sanitized = _sanitize_srcset(img['srcset'])
                    if sanitized:
                        img['srcset'] = sanitized
                    else:
                        del img['srcset']

            return str(soup)
        except ImportError:
            return cleaned
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
                attrs_to_update = {}  # For attributes we want to sanitize rather than remove

                for attr_name in element.attrs:
                    if attr_name.lower() in DANGEROUS_HTML_ATTRIBUTES:
                        attrs_to_remove.append(attr_name)

                    # Check URL attributes for dangerous schemes
                    elif attr_name.lower() in ('href', 'src', 'action', 'formaction'):
                        attr_value = element.attrs[attr_name]
                        if isinstance(attr_value, str) and not is_url_safe(attr_value):
                            attrs_to_remove.append(attr_name)

                    # Check and sanitize srcset attribute
                    elif attr_name.lower() == 'srcset':
                        attr_value = element.attrs[attr_name]
                        if isinstance(attr_value, str):
                            sanitized_srcset = _sanitize_srcset(attr_value)
                            if sanitized_srcset is None:
                                # All URLs in srcset were unsafe, remove the attribute
                                attrs_to_remove.append(attr_name)
                            elif sanitized_srcset != attr_value:
                                # Some URLs were removed, update with sanitized version
                                attrs_to_update[attr_name] = sanitized_srcset

                    # Enhanced style attribute checking
                    elif attr_name.lower() == 'style':
                        attr_value = element.attrs[attr_name]
                        if isinstance(attr_value, str):
                            # Use the comprehensive style safety check
                            if not _is_style_safe(attr_value):
                                attrs_to_remove.append(attr_name)

                    # Check other style-related attributes (background, expression) for dangerous content
                    elif attr_name.lower() in ('background', 'expression'):
                        attr_value = element.attrs[attr_name]
                        if isinstance(attr_value, str):
                            attr_value_lower = attr_value.lower()
                            # Check for dangerous schemes
                            if any(scheme in attr_value_lower for scheme in DANGEROUS_SCHEMES):
                                attrs_to_remove.append(attr_name)

                # Apply attribute removals
                for attr in attrs_to_remove:
                    del element.attrs[attr]

                # Apply attribute updates
                for attr, value in attrs_to_update.items():
                    element.attrs[attr] = value

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
    from all2md.utils.security import is_url_scheme_dangerous

    if not url or not url.strip():
        return True

    # Use consolidated dangerous scheme checking
    return not is_url_scheme_dangerous(url)


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
