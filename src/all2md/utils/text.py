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
import unicodedata
from typing import Set


def make_unique_slug(slug: str, seen_slugs: dict[str, int], separator: str = "-") -> str:
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


def slugify(text: str, *, seen_slugs: Set[str] | None = None, max_length: int = 100, separator: str = "-") -> str:
    """Create a URL-safe slug from text with collision avoidance.

    This function generates GitHub-flavored Markdown compatible slugs by:
    - Normalizing Unicode characters (NFD decomposition)
    - Converting to lowercase
    - Replacing spaces and underscores with hyphens
    - Removing non-alphanumeric characters (except hyphens)
    - Collapsing multiple consecutive hyphens
    - Stripping leading/trailing hyphens
    - Handling collisions by appending -2, -3, etc.
    - Limiting length to max_length characters

    Parameters
    ----------
    text : str
        Text to slugify (e.g., heading text, filename)
    seen_slugs : Set[str] or None, default = None
        Set of previously generated slugs for collision detection.
        If provided and the generated slug already exists, a numeric
        suffix will be appended (-2, -3, etc.). The function will
        automatically add the new slug to this set.
    max_length : int, default = 100
        Maximum length of the slug. Slugs longer than this will be
        truncated before adding collision suffixes.
    separator : str, default = "-"
        The separator between words in the slug

    Returns
    -------
    str
        URL-safe slug, unique if seen_slugs is provided

    Examples
    --------
    Basic slugification:
        >>> slugify("Hello World!")
        'hello-world'

    Handle special characters:
        >>> slugify("API Reference (v2.0)")
        'api-reference-v20'

    Collision detection:
        >>> seen = set()
        >>> slug1 = slugify("Introduction", seen_slugs=seen)
        >>> slug1
        'introduction'
        >>> slug2 = slugify("Introduction", seen_slugs=seen)
        >>> slug2
        'introduction-2'

    Length limiting:
        >>> slugify("A" * 150, max_length=50)
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'

    Unicode normalization:
        >>> slugify("Café résumé")
        'cafe-resume'

    """
    # Normalize Unicode: decompose accented characters
    normalized = unicodedata.normalize("NFD", text)

    # Remove combining characters (accents)
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")

    # Convert to lowercase
    slug = normalized.lower()

    # Replace spaces and underscores with separator
    slug = re.sub(r"[\s_]+", separator, slug)

    replace_pattern = "^a-z0-9\\-" + "\\" + separator
    # Remove all non-alphanumeric characters except hyphens
    slug = re.sub(rf"[{replace_pattern}]", "", slug)

    # Collapse multiple consecutive separator
    slug = re.sub(rf"{separator}+", separator, slug)

    # Strip leading and trailing separator
    slug = slug.strip(separator)

    # If empty after processing, use a default
    if not slug:
        slug = "section"

    # Apply length limit
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")

    # Handle collisions if seen_slugs is provided
    if seen_slugs is not None:
        if slug not in seen_slugs:
            seen_slugs.add(slug)
            return slug

        # Slug exists, find next available suffix
        counter = 2
        while f"{slug}-{counter}" in seen_slugs:
            counter += 1

        unique_slug = f"{slug}-{counter}"
        seen_slugs.add(unique_slug)
        return unique_slug

    return slug


__all__ = [
    "slugify",
    "make_unique_slug",
]
