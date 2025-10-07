#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/transforms/options.py
"""Parameter dataclasses for built-in transforms.

This module defines dataclasses for transform parameters, following the same
pattern as all2md.options. These are used for CLI argument generation and
validation.

Examples
--------
Create options for HeadingOffsetTransform:

    >>> options = HeadingOffsetOptions(offset=2)
    >>> transform = HeadingOffsetTransform(offset=options.offset)

"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RemoveNodesOptions:
    """Options for RemoveNodesTransform.

    Parameters
    ----------
    node_types : list[str], default = ['image']
        List of node types to remove (e.g., 'image', 'table', 'code_block')

    Examples
    --------
    >>> options = RemoveNodesOptions(node_types=['image', 'table'])

    """

    node_types: list[str] = field(default_factory=lambda: ['image'])


@dataclass
class HeadingOffsetOptions:
    """Options for HeadingOffsetTransform.

    Parameters
    ----------
    offset : int, default = 1
        Number of levels to shift headings (positive or negative)

    Examples
    --------
    >>> options = HeadingOffsetOptions(offset=2)

    """

    offset: int = 1


@dataclass
class LinkRewriterOptions:
    """Options for LinkRewriterTransform.

    Parameters
    ----------
    pattern : str
        Regex pattern to match in URLs
    replacement : str
        Replacement string for matched pattern

    Examples
    --------
    >>> options = LinkRewriterOptions(
    ...     pattern=r'^/docs/',
    ...     replacement='https://example.com/docs/'
    ... )

    """

    pattern: str = ""
    replacement: str = ""


@dataclass
class TextReplacerOptions:
    """Options for TextReplacerTransform.

    Parameters
    ----------
    find : str
        Text to find
    replace : str
        Replacement text

    Examples
    --------
    >>> options = TextReplacerOptions(find="TODO", replace="DONE")

    """

    find: str = ""
    replace: str = ""


@dataclass
class AddHeadingIdsOptions:
    """Options for AddHeadingIdsTransform.

    Parameters
    ----------
    id_prefix : str, default = ""
        Prefix to add to all generated IDs
    separator : str, default = "-"
        Separator for multi-word slugs and duplicate handling

    Examples
    --------
    >>> options = AddHeadingIdsOptions(id_prefix="doc-", separator="-")

    """

    id_prefix: str = ""
    separator: str = "-"


@dataclass
class RemoveBoilerplateOptions:
    r"""Options for RemoveBoilerplateTextTransform.

    Parameters
    ----------
    patterns : list[str], default = common patterns
        List of regex patterns to match for removal

    Examples
    --------
    >>> options = RemoveBoilerplateOptions(
    ...     patterns=[r"^CONFIDENTIAL$", r"^Page \d+ of \d+$"]
    ... )

    """

    patterns: list[str] = field(default_factory=lambda: [
        r"^CONFIDENTIAL$",
        r"^Page \d+ of \d+$",
        r"^Internal Use Only$",
        r"^\[DRAFT\]$"
    ])


@dataclass
class AddTimestampOptions:
    """Options for AddConversionTimestampTransform.

    Parameters
    ----------
    field_name : str, default = "conversion_timestamp"
        Metadata field name for timestamp
    format : str, default = "iso"
        Timestamp format: "iso", "unix", or strftime format string

    Examples
    --------
    >>> options = AddTimestampOptions(
    ...     field_name="converted_at",
    ...     format="%Y-%m-%d %H:%M:%S"
    ... )

    """

    field_name: str = "conversion_timestamp"
    format: str = "iso"


@dataclass
class WordCountOptions:
    """Options for CalculateWordCountTransform.

    Parameters
    ----------
    word_field : str, default = "word_count"
        Metadata field name for word count
    char_field : str, default = "char_count"
        Metadata field name for character count

    Examples
    --------
    >>> options = WordCountOptions(
    ...     word_field="words",
    ...     char_field="characters"
    ... )

    """

    word_field: str = "word_count"
    char_field: str = "char_count"


__all__ = [
    "RemoveNodesOptions",
    "HeadingOffsetOptions",
    "LinkRewriterOptions",
    "TextReplacerOptions",
    "AddHeadingIdsOptions",
    "RemoveBoilerplateOptions",
    "AddTimestampOptions",
    "WordCountOptions",
]
