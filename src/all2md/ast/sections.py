#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/ast/sections.py
"""Core section utilities for document AST structures.

This module provides the fundamental Section dataclass and basic section
extraction and querying operations. Sections are the building blocks for
document manipulation, representing a heading and all content up to the
next same-or-higher level heading.

Functions
---------
Section : Dataclass representing a document section
get_all_sections : Extract all sections from a document with level filtering
get_preamble : Get content before first heading
parse_section_ranges : Parse section range specifications like "1-3,5"
query_sections : Universal section query function (consolidates finding by heading, index, predicate)
find_heading : Find a heading node in the document
count_sections : Count sections in a document

Examples
--------
Get all sections:
    >>> sections = get_all_sections(doc)
    >>> for section in sections:
    ...     print(f"Level {section.level}: {section.get_heading_text()}")

Query sections flexibly:
    >>> sections = query_sections(doc, "Introduction")  # by name
    >>> sections = query_sections(doc, 0)  # by index
    >>> sections = query_sections(doc, lambda s: s.level == 2)  # by predicate
    >>> sections = query_sections(doc, level=2)  # by level

Parse section ranges:
    >>> indices = parse_section_ranges("1-3,5", total_sections=10)
    >>> indices
    [0, 1, 2, 4]

"""

from __future__ import annotations

import difflib
import fnmatch
from dataclasses import dataclass, field
from typing import Callable, Literal

from all2md.ast import Link, List, ListItem, Paragraph, Text
from all2md.ast.nodes import Document, Heading, Node, ThematicBreak
from all2md.ast.utils import extract_text
from all2md.utils.text import slugify


@dataclass
class Section:
    """Represents a document section with heading and content.

    A section consists of a heading node and all content nodes that follow
    it until the next heading of the same or higher level.

    Parameters
    ----------
    heading : Heading
        The heading node for this section
    content : list of Node
        All nodes between this heading and the next same-or-higher level heading
    level : int
        Heading level (1-6)
    start_index : int
        Index of the heading in the parent document's children list
    end_index : int
        Exclusive end index (one past the last content node)

    Examples
    --------
    >>> section = Section(
    ...     heading=Heading(level=1, content=[Text("Title")]),
    ...     content=[Paragraph(content=[Text("Content")])],
    ...     level=1,
    ...     start_index=0,
    ...     end_index=2
    ... )

    """

    heading: Heading
    content: list[Node] = field(default_factory=list)
    level: int = 1
    start_index: int = 0
    end_index: int = 0

    def to_document(self) -> Document:
        """Convert this section to a standalone document.

        Returns
        -------
        Document
            New document containing the heading and content

        Examples
        --------
        >>> doc = section.to_document()
        >>> len(doc.children)
        2

        """
        return Document(children=[self.heading] + self.content)

    def get_heading_text(self) -> str:
        """Extract plain text from the heading.

        Returns
        -------
        str
            Plain text content of the heading

        Examples
        --------
        >>> section.get_heading_text()
        'Introduction'

        """
        return extract_text(self.heading)


def get_all_sections(doc: Document, min_level: int = 1, max_level: int = 6) -> list[Section]:
    """Extract all sections from a document.

    Parameters
    ----------
    doc : Document
        Document to extract sections from
    min_level : int, default = 1
        Minimum heading level to include (1 is highest)
    max_level : int, default = 6
        Maximum heading level to include (6 is lowest)

    Returns
    -------
    list of Section
        All sections in document order

    Notes
    -----
    A section is defined as a heading plus all content until the next
    same-or-higher level heading. Content before the first heading is
    not included in any section (see get_preamble).

    Examples
    --------
    >>> sections = get_all_sections(doc)
    >>> for section in sections:
    ...     print(f"Level {section.level}: {section.get_heading_text()}")

    Get only top-level sections:
        >>> top_sections = get_all_sections(doc, min_level=1, max_level=1)

    """
    if not (1 <= min_level <= max_level <= 6):
        raise ValueError(
            f"Invalid level range: min_level={min_level}, max_level={max_level}. "
            "Levels must be between 1 and 6, with min_level <= max_level."
        )

    sections: list[Section] = []
    current_section: Section | None = None
    current_content: list[Node] = []

    for idx, node in enumerate(doc.children):
        if isinstance(node, Heading):
            # Check if this heading is in the desired level range
            if min_level <= node.level <= max_level:
                # Save previous section if exists
                if current_section is not None:
                    current_section.content = current_content
                    current_section.end_index = idx
                    sections.append(current_section)

                # Start new section
                current_section = Section(
                    heading=node, content=[], level=node.level, start_index=idx, end_index=idx + 1
                )
                current_content = []
            elif current_section is not None:
                # This heading is outside the level range but we're in a section
                # Check if it would close the current section
                # (only if it's same or higher level than current section)
                if node.level <= current_section.level:
                    # Close current section
                    current_section.content = current_content
                    current_section.end_index = idx
                    sections.append(current_section)
                    current_section = None
                    current_content = []
                else:
                    # Lower level heading within section - include as content
                    current_content.append(node)
            else:
                # Not in a section and heading is outside range - skip
                pass
        elif current_section is not None:
            # Add content to current section
            current_content.append(node)

    # Don't forget the last section
    if current_section is not None:
        current_section.content = current_content
        current_section.end_index = len(doc.children)
        sections.append(current_section)

    return sections


def get_preamble(doc: Document) -> list[Node]:
    """Get all content before the first heading.

    Parameters
    ----------
    doc : Document
        Document to extract preamble from

    Returns
    -------
    list of Node
        All nodes before the first heading (empty if document starts with heading)

    Examples
    --------
    >>> preamble = get_preamble(doc)
    >>> if preamble:
    ...     print(f"Found {len(preamble)} preamble nodes")

    """
    preamble = []
    for node in doc.children:
        if isinstance(node, Heading):
            break
        preamble.append(node)

    return preamble


def parse_section_ranges(section_spec: str, total_sections: int) -> list[int]:
    """Parse section range specification into list of 0-based section indices.

    Supports various formats (all 1-indexed input):
    - "1-3" -> [0, 1, 2]
    - "5" -> [4]
    - "10-" -> [9, 10, ..., total_sections-1]
    - "1-3,5,10-" -> combined ranges
    - "5-3" -> [2, 3, 4] (automatically swaps to "3-5")

    Reversed ranges (where start > end) are automatically corrected by swapping
    the values. For example, "10-5" is treated as "5-10".

    Parameters
    ----------
    section_spec : str
        Section range specification (1-based section numbers)
    total_sections : int
        Total number of sections in document

    Returns
    -------
    list of int
        Sorted list of 0-based section indices

    Examples
    --------
    >>> parse_section_ranges("1-3,5", 10)
    [0, 1, 2, 4]
    >>> parse_section_ranges("8-", 10)
    [7, 8, 9]
    >>> parse_section_ranges("10-5", 10)
    [4, 5, 6, 7, 8, 9]

    """
    sections = set()

    # Split by comma to handle multiple ranges
    parts = section_spec.split(",")

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Handle range (e.g., "1-3" or "10-")
        if "-" in part:
            range_parts = part.split("-", 1)
            start_str = range_parts[0].strip()
            end_str = range_parts[1].strip()

            # Parse start (1-based to 0-based)
            if start_str:
                start = int(start_str) - 1
            else:
                start = 0

            # Parse end (1-based to 0-based, or use total_sections if empty)
            if end_str:
                end = int(end_str) - 1
            else:
                end = total_sections - 1

            # Swap if reversed range (e.g., "10-5" becomes "5-10")
            if start > end:
                start, end = end, start

            # Add all sections in range
            for s in range(start, end + 1):
                if 0 <= s < total_sections:
                    sections.add(s)
        else:
            # Single section (1-based to 0-based)
            section = int(part) - 1
            if 0 <= section < total_sections:
                sections.add(section)

    # Return sorted list
    return sorted(sections)


def query_sections(
    doc: Document,
    spec: str | int | list[int] | Callable[[Section], bool] | None = None,
    *,
    level: int | None = None,
    min_level: int = 1,
    max_level: int = 6,
    case_sensitive: bool = False,
) -> list[Section]:
    """Universal section query function with flexible parameters.

    This function consolidates multiple section-finding functions into one
    powerful interface that handles querying by name, index, pattern, predicate,
    or level filtering.

    Parameters
    ----------
    doc : Document
        Document to search
    spec : str, int, list[int], callable, or None
        Query specification:
        - None: return all sections (respects level filters)
        - str: heading text or pattern ("Introduction", "Chapter*")
        - int: single section index (0-based)
        - list[int]: multiple section indices (0-based)
        - callable: predicate function(section) -> bool
    level : int or None, default = None
        If specified, only return sections at this exact level (1-6)
    min_level : int, default = 1
        Minimum heading level to include
    max_level : int, default = 6
        Maximum heading level to include
    case_sensitive : bool, default = False
        Whether text matching is case-sensitive (for string specs)

    Returns
    -------
    list of Section
        Matching sections in document order

    Raises
    ------
    ValueError
        If spec is invalid or indices are out of range
    IndexError
        If a specified index is out of range

    Examples
    --------
    Find all sections:
        >>> sections = query_sections(doc)

    Find by exact heading text:
        >>> sections = query_sections(doc, "Introduction")

    Find by pattern (wildcards):
        >>> sections = query_sections(doc, "Chapter*")

    Find by single index:
        >>> sections = query_sections(doc, 0)  # First section

    Find by multiple indices:
        >>> sections = query_sections(doc, [0, 2, 4])

    Find by predicate:
        >>> sections = query_sections(doc, lambda s: len(s.content) > 5)

    Find by level:
        >>> sections = query_sections(doc, level=2)

    Find by level range:
        >>> sections = query_sections(doc, min_level=2, max_level=3)

    Combined filters:
        >>> sections = query_sections(doc, "Chapter*", level=1)

    """
    # If level is specified, use it for both min and max
    if level is not None:
        min_level = max_level = level

    # Get all sections within the level range
    all_sections = get_all_sections(doc, min_level=min_level, max_level=max_level)

    # If no spec, return all sections (already filtered by level)
    if spec is None:
        return all_sections

    # Handle different spec types
    if isinstance(spec, int):
        # Single index
        try:
            return [all_sections[spec]]
        except IndexError:
            raise IndexError(f"Section index {spec} out of range (0-{len(all_sections) - 1})") from None

    elif isinstance(spec, list):
        # Multiple indices
        result = []
        for idx in spec:
            if not isinstance(idx, int):
                raise TypeError(f"List elements must be integers, got {type(idx).__name__}")
            try:
                result.append(all_sections[idx])
            except IndexError:
                raise IndexError(f"Section index {idx} out of range (0-{len(all_sections) - 1})") from None
        return result

    elif callable(spec):
        # Predicate function
        return [section for section in all_sections if spec(section)]

    elif isinstance(spec, str):
        # Text pattern matching (with wildcards support)
        pattern = spec

        # Prepare pattern for case-insensitive matching if needed
        pattern_to_match = pattern if case_sensitive else pattern.lower()

        # Check if pattern contains wildcards
        has_wildcards = "*" in pattern or "?" in pattern

        matching_sections = []
        for section in all_sections:
            heading_text = section.get_heading_text()
            text_to_match = heading_text if case_sensitive else heading_text.lower()

            if has_wildcards:
                # Use fnmatch for wildcard patterns
                if fnmatch.fnmatch(text_to_match, pattern_to_match):
                    matching_sections.append(section)
            else:
                # Exact match
                if text_to_match == pattern_to_match:
                    matching_sections.append(section)

        return matching_sections

    else:
        raise TypeError(
            f"Invalid spec type: {type(spec).__name__}. " "Expected str, int, list[int], callable, or None."
        )


def find_heading(
    doc: Document, text: str, level: int | None = None, case_sensitive: bool = False
) -> tuple[int, Heading] | None:
    """Find a heading node in the document.

    This function finds heading nodes directly, not sections. Use query_sections()
    if you want to find sections (heading + content).

    Parameters
    ----------
    doc : Document
        Document to search
    text : str
        Text to search for
    level : int or None, default = None
        If specified, only match headings at this level
    case_sensitive : bool, default = False
        Whether to perform case-sensitive matching

    Returns
    -------
    tuple of (int, Heading) or None
        Tuple of (index, heading_node) if found, None otherwise

    Examples
    --------
    >>> result = find_heading(doc, "Introduction")
    >>> if result:
    ...     idx, heading = result
    ...     print(f"Found at index {idx}, level {heading.level}")

    """
    search_text = text if case_sensitive else text.lower()

    for idx, node in enumerate(doc.children):
        if isinstance(node, Heading):
            # Check level if specified
            if level is not None and node.level != level:
                continue

            # Check text match
            node_text = extract_text(node)
            if not case_sensitive:
                node_text = node_text.lower()

            if node_text == search_text:
                return (idx, node)

    return None


def count_sections(doc: Document, level: int | None = None) -> int:
    """Count the number of sections in a document.

    Parameters
    ----------
    doc : Document
        Document to count sections in
    level : int or None, default = None
        If specified, only count sections at this level

    Returns
    -------
    int
        Number of sections

    Examples
    --------
    >>> total_sections = count_sections(doc)
    >>> top_level = count_sections(doc, level=1)

    """
    if level is None:
        sections = get_all_sections(doc)
    else:
        sections = get_all_sections(doc, min_level=level, max_level=level)

    return len(sections)


def extract_sections(
    doc: Document,
    spec: str | int | list[int],
    *,
    case_sensitive: bool = False,
    combine: bool = True,
    separator: Node | None = None,
) -> Document:
    """Extract sections from document using flexible specification.

    This function provides powerful section extraction with support for ranges,
    wildcards, multiple sections, and fuzzy matching with helpful suggestions.

    Parameters
    ----------
    doc : Document
        Source document
    spec : str or int or list of int
        Extraction specification:
        - Name: "Introduction" (exact match)
        - Pattern: "Intro*", "*Results*" (uses fnmatch)
        - Single index: 0 or "#:1" (0-based or 1-based with #:)
        - Range: "#:1-3", "#:3-" (1-based, inclusive)
        - Multiple: "#:1,3,5" or [0, 2, 4] (1-based or 0-based list)
    case_sensitive : bool, default False
        Whether name matching is case-sensitive
    combine : bool, default True
        If True, combine sections into single document with separators.
        If False, return document with just the first match.
    separator : Node or None, default None
        Node to insert between sections (default: ThematicBreak)

    Returns
    -------
    Document
        Document with extracted sections

    Raises
    ------
    ValueError
        If spec is invalid or no sections match

    Examples
    --------
    Extract by name:
        >>> extracted = extract_sections(doc, "Introduction")

    Extract with wildcards:
        >>> extracted = extract_sections(doc, "Chapter*")

    Extract by range:
        >>> extracted = extract_sections(doc, "#:1-3")

    Extract multiple specific sections:
        >>> extracted = extract_sections(doc, "#:1,3,5")
        >>> extracted = extract_sections(doc, [0, 2, 4])

    Extract without separators:
        >>> extracted = extract_sections(doc, "#:1-3", separator=None)

    """
    # Get all sections from document
    sections = get_all_sections(doc)

    if not sections:
        raise ValueError("Document contains no sections (headings)")

    # Determine extraction type and get matched sections
    extracted_sections: list[Section] = []

    if isinstance(spec, list):
        # List of 0-based indices
        try:
            extracted_sections = [sections[i] for i in spec if 0 <= i < len(sections)]
            if not extracted_sections:
                raise ValueError(f"No valid sections in index list: {spec}")
        except IndexError as e:
            raise ValueError(f"Invalid section index in list: {e}") from e

    elif isinstance(spec, int):
        # Single 0-based index
        if not 0 <= spec < len(sections):
            raise ValueError(f"Section index {spec} out of range (0-{len(sections) - 1})")
        extracted_sections = [sections[spec]]

    elif isinstance(spec, str):
        # String specification
        if spec.startswith("#:"):
            # Index-based extraction (1-based)
            index_spec = spec[2:]  # Remove "#:" prefix

            try:
                # Parse section indices (returns 0-based)
                section_indices = parse_section_ranges(index_spec, len(sections))

                if not section_indices:
                    raise ValueError(f"No valid sections in range: {spec}")

                # Extract sections by index
                extracted_sections = [sections[i] for i in section_indices]

            except (ValueError, IndexError) as e:
                raise ValueError(f"Invalid section index specification '{spec}': {e}") from e
        else:
            # Name pattern-based extraction (use fnmatch for wildcards)
            pattern = spec

            # Collect all heading texts for pattern matching and fuzzy suggestions
            all_heading_texts = []
            for section in sections:
                heading_text = section.get_heading_text()
                all_heading_texts.append(heading_text)

                # Match against pattern
                pattern_to_match = pattern if case_sensitive else pattern.lower()
                text_to_match = heading_text if case_sensitive else heading_text.lower()

                if fnmatch.fnmatch(text_to_match, pattern_to_match):
                    extracted_sections.append(section)

            if not extracted_sections:
                # Check if wildcards were used in the pattern
                has_wildcards = "*" in pattern or "?" in pattern

                # If no wildcards, try fuzzy matching to provide helpful suggestions
                if not has_wildcards and all_heading_texts:
                    # Find close matches (case-insensitive comparison)
                    suggestions = difflib.get_close_matches(
                        pattern.lower(), [h.lower() for h in all_heading_texts], n=3, cutoff=0.6
                    )

                    # Map back to original case
                    if suggestions:
                        original_suggestions = []
                        for suggestion in suggestions:
                            for original in all_heading_texts:
                                if original.lower() == suggestion:
                                    original_suggestions.append(original)
                                    break

                        error_msg = (
                            f"No sections match pattern: {pattern}\nDid you mean: {', '.join(original_suggestions)}?"
                        )
                        raise ValueError(error_msg)

                # Fallback to simple error message
                raise ValueError(f"No sections match pattern: {pattern}")
    else:
        raise TypeError(f"Invalid spec type: {type(spec).__name__}. Expected str, int, or list of int.")

    # If not combining, return just the first section
    if not combine:
        return extracted_sections[0].to_document()

    # Build new document with extracted sections separated by separator
    merged_children: list[Node] = []

    # Default separator is ThematicBreak
    if separator is None:
        separator = ThematicBreak()

    for i, section in enumerate(extracted_sections):
        # Add section heading
        merged_children.append(section.heading)

        # Add section content
        merged_children.extend(section.content)

        # Add separator between sections (but not after the last one)
        if i < len(extracted_sections) - 1 and separator is not None:
            merged_children.append(separator)

    # Create new document with extracted content
    extracted_doc = Document(children=merged_children, metadata=doc.metadata.copy())

    return extracted_doc


def section_or_doc_to_nodes(content: Section | Document | list[Node]) -> list[Node]:
    """Convert Section, Document, or list to list of nodes.

    This helper consolidates the repeated pattern of converting various
    content types to a flat list of nodes.

    Parameters
    ----------
    content : Section, Document, or list of Node
        Content to convert

    Returns
    -------
    list of Node
        Flat list of nodes

    Examples
    --------
    >>> nodes = section_or_doc_to_nodes(section)
    >>> nodes = section_or_doc_to_nodes(document)
    >>> nodes = section_or_doc_to_nodes([para1, para2])

    """
    if isinstance(content, Section):
        return [content.heading] + content.content
    elif isinstance(content, Document):
        return content.children
    elif isinstance(content, Node) or (isinstance(content, list) and all(isinstance(a, Node) for a in content)):
        return content
    else:
        raise TypeError(f"Expected `Document`, `Section` or `Node/list[Node]` found: `{type(content).__name__}`")


def generate_toc(
    doc: Document, max_level: int = 3, style: Literal["markdown", "list", "nested"] = "markdown"
) -> str | List:
    """Generate a table of contents from document headings.

    Parameters
    ----------
    doc : Document
        Document to generate TOC from
    max_level : int, default = 3
        Maximum heading level to include (1-6)
    style : {"markdown", "list", "nested"}, default = "markdown"
        Output style for the TOC

    Returns
    -------
    str or List
        Table of contents as markdown string (for "markdown" style)
        or List node (for "list" and "nested" styles)

    Notes
    -----
    - "markdown": Returns markdown-formatted TOC as a string
    - "list": Returns a flat List AST node with all headings
    - "nested": Returns nested List AST nodes respecting heading hierarchy

    Examples
    --------
    >>> toc = generate_toc(doc, max_level=3)
    >>> print(toc)
    # Table of Contents

    - [Introduction](#introduction)
      - [Background](#background)
      - [Motivation](#motivation)
    - [Methods](#methods)

    """
    if not 1 <= max_level <= 6:
        raise ValueError(f"max_level must be between 1 and 6, got {max_level}")

    sections = get_all_sections(doc, min_level=1, max_level=max_level)

    if style == "markdown":
        return _generate_toc_markdown(sections, max_level)
    elif style == "list":
        return _generate_toc_list(sections, flat=True)
    elif style == "nested":
        return _generate_toc_list(sections, flat=False)
    else:
        raise ValueError(f"Invalid style: {style}")


def _generate_toc_markdown(sections: list[Section], max_level: int) -> str:
    """Generate markdown-formatted table of contents.

    Parameters
    ----------
    sections : list of Section
        Sections to include in TOC
    max_level : int
        Maximum heading level

    Returns
    -------
    str
        Markdown-formatted TOC

    """
    if not sections:
        return ""

    lines = ["# Table of Contents", ""]
    seen_slugs: set[str] = set()

    for section in sections:
        if section.level > max_level:
            continue

        # Extract heading text and create robust slug with collision handling
        heading_text = section.get_heading_text()
        slug = slugify(heading_text, seen_slugs=seen_slugs)

        # Add indentation based on level
        indent = "  " * (section.level - 1)
        lines.append(f"{indent}- [{heading_text}](#{slug})")

    return "\n".join(lines)


def _generate_toc_list(sections: list[Section], flat: bool) -> List:
    """Generate List node table of contents.

    Parameters
    ----------
    sections : list of Section
        Sections to include in TOC
    flat : bool
        If True, generate flat list; if False, generate nested list

    Returns
    -------
    List
        List node containing TOC

    Notes
    -----
    When flat=False, the function builds a nested list structure that respects
    the heading hierarchy. Headings at level N are nested under the most recent
    heading at level N-1. If there are level jumps (e.g., H1 directly to H3),
    intermediate lists are created as needed.

    """
    if flat:
        # Flat list with all headings
        items = []
        for section in sections:
            heading_text = section.get_heading_text()
            item = ListItem(children=[Paragraph(content=[Text(content=heading_text)])])
            items.append(item)

        return List(ordered=False, items=items)
    else:
        # Nested list respecting hierarchy using stack-based algorithm
        if not sections:
            return List(ordered=False, items=[])

        # Find the minimum level to use as the base
        min_level = min((s.level for s in sections), default=1)

        # Root list for top-level items
        root_list = List(ordered=False, items=[])

        # Stack tracks (list_node, level) tuples
        # The level in the stack represents which heading level items in that list represent
        stack: list[tuple[List, int]] = [(root_list, min_level)]

        for section in sections:
            level = section.level
            heading_text = section.get_heading_text()

            # Pop stack while current stack level > section level
            # This handles moving back up the hierarchy
            while len(stack) > 1 and stack[-1][1] > level:
                stack.pop()

            # Get current list and level
            current_list, current_level = stack[-1]

            # Create intermediate levels if needed (level jumps like H1 -> H3)
            while current_level < level - 1:
                # Create an intermediate list and item
                if not current_list.items:
                    # Need a parent item to nest under, create empty one
                    empty_item = ListItem(children=[])
                    current_list.items.append(empty_item)

                # Get the last item to nest under
                last_item = current_list.items[-1]

                # Create nested list for intermediate level
                intermediate_list = List(ordered=False, items=[])
                last_item.children.append(intermediate_list)

                # Move to intermediate level
                current_level += 1
                stack.append((intermediate_list, current_level))
                current_list = intermediate_list

            # Create the list item for this section
            item = ListItem(children=[Paragraph(content=[Text(content=heading_text)])])

            if level == current_level:
                # Same level: add as sibling to current list
                current_list.items.append(item)
            elif level == current_level + 1:
                # One level deeper: nest under last item in current list
                if not current_list.items:
                    # No items yet, add to current level instead
                    current_list.items.append(item)
                else:
                    # Get the last item to nest under
                    last_item = current_list.items[-1]

                    # Create nested list if it doesn't exist
                    nested_list = None
                    for child in last_item.children:
                        if isinstance(child, List):
                            nested_list = child
                            break

                    if nested_list is None:
                        nested_list = List(ordered=False, items=[])
                        last_item.children.append(nested_list)

                    # Add item to nested list
                    nested_list.items.append(item)

                    # Push nested list onto stack for future deeper items
                    stack.append((nested_list, level))
            else:
                # Level > current_level + 1: should have been handled by intermediate levels
                # Add to current list as fallback
                current_list.items.append(item)

        return root_list


def _build_toc_ast(sections: list[Section], max_level: int) -> list[Node]:
    """Build table of contents as AST nodes directly without markdown round-trip.

    This function generates the same structure as the markdown-style TOC but builds
    the AST nodes directly instead of generating markdown and parsing it back.

    Parameters
    ----------
    sections : list of Section
        Sections to include in TOC
    max_level : int
        Maximum heading level to include

    Returns
    -------
    list of Node
        List containing Heading and List nodes for the TOC

    Notes
    -----
    This function avoids the coupling issue of generating markdown text and then
    parsing it back to AST, which creates a circular dependency on the markdown parser.

    """
    if not sections:
        return []

    # Create TOC heading
    toc_heading = Heading(level=1, content=[Text(content="Table of Contents")])

    # Build list items with links
    items = []
    seen_slugs: set[str] = set()

    for section in sections:
        if section.level > max_level:
            continue

        # Extract heading text and create robust slug with collision handling
        heading_text = section.get_heading_text()
        slug = slugify(heading_text, seen_slugs=seen_slugs)

        # Create link node
        link = Link(url=f"#{slug}", content=[Text(content=heading_text)], title=None)

        # Create list item
        list_item = ListItem(children=[Paragraph(content=[link])])
        items.append(list_item)

    # Create list
    toc_list = List(ordered=False, items=items, tight=True)

    return [toc_heading, toc_list]


def insert_toc(
    doc: Document,
    position: Literal["start", "after_first_heading"] = "start",
    max_level: int = 3,
    style: Literal["markdown", "list", "nested"] = "markdown",
) -> Document:
    """Insert a table of contents into the document.

    Parameters
    ----------
    doc : Document
        Document to modify
    position : {"start", "after_first_heading"}, default = "start"
        Where to insert the TOC
    max_level : int, default = 3
        Maximum heading level to include
    style : {"markdown", "list", "nested"}, default = "markdown"
        Style of the TOC

    Returns
    -------
    Document
        New document with TOC inserted

    Examples
    --------
    >>> doc_with_toc = insert_toc(doc, position="start", max_level=3)

    """
    # Build TOC as AST nodes directly to avoid markdown parsing round-trip
    if style == "markdown":
        sections = get_all_sections(doc, min_level=1, max_level=max_level)
        toc_nodes = _build_toc_ast(sections, max_level)
    else:
        # For "list" and "nested" styles, use generate_toc which already returns AST
        toc_content = generate_toc(doc, max_level=max_level, style=style)
        # When style is not "markdown", generate_toc returns a List node
        assert isinstance(toc_content, List), "generate_toc must return List for non-markdown styles"
        toc_nodes = [toc_content]

    # Determine insert position
    if position == "start":
        insert_pos = 0
    elif position == "after_first_heading":
        # Find first heading
        for idx, node in enumerate(doc.children):
            if isinstance(node, Heading):
                insert_pos = idx + 1
                break
        else:
            # No heading found, insert at start
            insert_pos = 0
    else:
        raise ValueError(f"Invalid position: {position}")

    # Insert TOC
    new_children = doc.children[:insert_pos] + toc_nodes + doc.children[insert_pos:]

    return Document(children=new_children, metadata=doc.metadata.copy(), source_location=doc.source_location)


__all__ = [
    "Section",
    "get_all_sections",
    "get_preamble",
    "parse_section_ranges",
    "query_sections",
    "find_heading",
    "extract_sections",
    "count_sections",
    "section_or_doc_to_nodes",
    "generate_toc",
    "insert_toc",
]
