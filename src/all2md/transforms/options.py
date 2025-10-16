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

from all2md.constants import DEFAULT_BOILERPLATE_PATTERNS


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

    node_types: list[str] = field(default_factory=lambda: ["image"])


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
    skip_if_truncated : bool, default = True
        Skip pattern matching when text exceeds MAX_TEXT_LENGTH_FOR_REGEX
        to avoid false positives with end-anchored patterns

    Examples
    --------
    >>> options = RemoveBoilerplateOptions(
    ...     patterns=[r"^CONFIDENTIAL$", r"^Page \d+ of \d+$"]
    ... )

    """

    patterns: list[str] = field(default_factory=lambda: DEFAULT_BOILERPLATE_PATTERNS.copy())
    skip_if_truncated: bool = True


@dataclass
class AddTimestampOptions:
    """Options for AddConversionTimestampTransform.

    Parameters
    ----------
    field_name : str, default = "conversion_timestamp"
        Metadata field name for timestamp
    format : str, default = "iso"
        Timestamp format: "iso", "unix", or strftime format string
    timespec : str, default = "seconds"
        Time precision for ISO format timestamps. Valid values are:
        "auto", "hours", "minutes", "seconds", "milliseconds", "microseconds".
        Only applies when format="iso".

    Examples
    --------
    >>> options = AddTimestampOptions(
    ...     field_name="converted_at",
    ...     format="%Y-%m-%d %H:%M:%S"
    ... )

    >>> options = AddTimestampOptions(
    ...     format="iso",
    ...     timespec="microseconds"
    ... )

    """

    field_name: str = "conversion_timestamp"
    format: str = "iso"
    timespec: str = "seconds"


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


@dataclass
class AddAttachmentFootnotesOptions:
    """Options for AddAttachmentFootnotesTransform.

    Parameters
    ----------
    section_title : str or None, default = "Attachments"
        Title for the footnote section heading (None to skip heading)
    add_definitions_for_images : bool, default = True
        Add definitions for image footnote references
    add_definitions_for_links : bool, default = True
        Add definitions for link footnote references

    Examples
    --------
    >>> options = AddAttachmentFootnotesOptions(
    ...     section_title="Image Sources",
    ...     add_definitions_for_images=True
    ... )

    """

    section_title: str | None = "Attachments"
    add_definitions_for_images: bool = True
    add_definitions_for_links: bool = True


@dataclass
class GenerateTocOptions:
    """Options for GenerateTocTransform.

    Parameters
    ----------
    title : str, default = "Table of Contents"
        Title for the TOC section
    max_depth : int, default = 3
        Maximum heading level to include (1-6)
    position : str, default = "top"
        Position to insert the TOC ("top" or "bottom")
    add_links : bool, default = True
        Whether to create links to headings (requires heading IDs)
    separator : str, default = "-"
        Separator for generating heading IDs when not present
    set_ids_if_missing : bool, default = False
        Inject generated IDs into heading metadata when missing

    Examples
    --------
    >>> options = GenerateTocOptions(
    ...     title="Contents",
    ...     max_depth=2,
    ...     position="bottom"
    ... )

    """

    title: str = "Table of Contents"
    max_depth: int = 3
    position: str = "top"
    add_links: bool = True
    separator: str = "-"
    set_ids_if_missing: bool = False


__all__ = [
    "RemoveNodesOptions",
    "HeadingOffsetOptions",
    "LinkRewriterOptions",
    "TextReplacerOptions",
    "AddHeadingIdsOptions",
    "RemoveBoilerplateOptions",
    "AddTimestampOptions",
    "WordCountOptions",
    "AddAttachmentFootnotesOptions",
    "GenerateTocOptions",
]
