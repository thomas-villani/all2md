#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/text.py
"""Text processing utilities for AST transforms.

This module provides text manipulation functions commonly used by transforms,
including slugification for heading IDs and table of contents generation.

Functions
---------
slugify : Convert text to URL-safe slug
make_unique_slug : Generate unique slug with duplicate handling

Examples
--------
Basic slugification:

    >>> from all2md.utils.text import slugify
    >>> slugify("My Heading Title")
    'my-heading-title'

Custom separator:

    >>> slugify("My Heading Title", separator="_")
    'my_heading_title'

Unique slug generation with counter:

    >>> seen = {}
    >>> slug1 = make_unique_slug("my-heading", seen)  # 'my-heading'
    >>> slug2 = make_unique_slug("my-heading", seen)  # 'my-heading-2'
    >>> slug3 = make_unique_slug("my-heading", seen)  # 'my-heading-3'

"""

from __future__ import annotations

import re


def slugify(text: str, separator: str = "-") -> str:
    """Convert text to URL-safe slug.

    This function performs the following transformations:
    1. Convert to lowercase
    2. Remove non-alphanumeric characters (except spaces and hyphens)
    3. Replace whitespace and underscores with the separator
    4. Remove leading/trailing separators
    5. Return 'heading' as fallback for empty results

    Parameters
    ----------
    text : str
        Text to slugify
    separator : str, default = "-"
        Separator to use between words

    Returns
    -------
    str
        Slugified text (e.g., "my-heading-title")

    Examples
    --------
    Basic usage:

        >>> slugify("My Heading Title")
        'my-heading-title'

    With special characters:

        >>> slugify("Hello, World!")
        'hello-world'

    Custom separator:

        >>> slugify("My Heading", separator="_")
        'my_heading'

    Empty text fallback:

        >>> slugify("")
        'heading'

    Notes
    -----
    This function is used by AddHeadingIdsTransform and GenerateTocTransform
    to generate consistent IDs for headings.

    """
    # Convert to lowercase
    text = text.lower()

    # Remove non-alphanumeric characters (except spaces, hyphens, underscores)
    text = re.sub(r'[^\w\s-]', '', text)

    # Replace whitespace and underscores with separator
    text = re.sub(r'[\s_]+', separator, text)

    # Remove leading/trailing separators
    text = text.strip(separator)

    # Return fallback if empty
    return text or 'heading'


def make_unique_slug(
        slug: str,
        seen_slugs: dict[str, int],
        separator: str = "-"
) -> str:
    """Generate unique slug with duplicate handling.

    This function ensures slug uniqueness by appending a numeric suffix
    when duplicates are encountered. The seen_slugs dictionary tracks
    occurrence counts and is mutated in-place.

    Parameters
    ----------
    slug : str
        Base slug to make unique
    seen_slugs : dict[str, int]
        Dictionary tracking occurrence counts (mutated in-place).
        Maps base slug to count of occurrences.
    separator : str, default = "-"
        Separator to use before numeric suffix

    Returns
    -------
    str
        Unique slug (with numeric suffix if needed)

    Examples
    --------
    Basic usage:

        >>> seen = {}
        >>> make_unique_slug("my-heading", seen)
        'my-heading'
        >>> make_unique_slug("my-heading", seen)
        'my-heading-2'
        >>> make_unique_slug("my-heading", seen)
        'my-heading-3'

    Custom separator:

        >>> seen = {}
        >>> make_unique_slug("heading", seen, separator="_")
        'heading'
        >>> make_unique_slug("heading", seen, separator="_")
        'heading_2'

    Notes
    -----
    The seen_slugs dictionary is modified in-place to track counts.
    This allows callers to maintain state across multiple calls.

    The first occurrence of a slug does not get a numeric suffix.
    Subsequent occurrences get suffixes starting at 2.

    """
    # Check if we've seen this slug before
    if slug in seen_slugs:
        # Increment count and append to slug
        seen_slugs[slug] += 1
        return f"{slug}{separator}{seen_slugs[slug]}"
    else:
        # First occurrence - no suffix needed
        seen_slugs[slug] = 1
        return slug


__all__ = [
    "slugify",
    "make_unique_slug",
]
