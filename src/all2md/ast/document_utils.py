#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/ast/document_utils.py
"""High-level document manipulation utilities for AST structures.

This module provides utilities for working with document sections, table of contents
generation, and structural document manipulation. It builds on the low-level AST
visitor and transformer patterns to provide a more intuitive API for common
document operations.

A "section" is defined as a heading node plus all content nodes that follow it
until the next heading of the same or higher level (lower level number).

Examples
--------
Get all sections from a document:

    >>> sections = get_all_sections(doc)
    >>> for section in sections:
    ...     heading_text = extract_text(section.heading)
    ...     print(f"Level {section.level}: {heading_text}")

Find a specific section:

    >>> section = find_section_by_heading(doc, "Introduction")
    >>> if section:
    ...     print(f"Found section at index {section.start_index}")

Add a new section after another:

    >>> new_section = Section(
    ...     heading=Heading(level=2, content=[Text("New Section")]),
    ...     content=[Paragraph(content=[Text("Content here")])],
    ...     level=2, start_index=0, end_index=0
    ... )
    >>> updated_doc = add_section_after(doc, "Introduction", new_section)

Generate a table of contents:

    >>> toc_markdown = generate_toc(doc, max_level=3)
    >>> print(toc_markdown)

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

from all2md.ast.nodes import (
    Document,
    Heading,
    List,
    ListItem,
    Node,
    Paragraph,
    Text,
)
from all2md.ast.utils import extract_text


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


def get_all_sections(
        doc: Document,
        min_level: int = 1,
        max_level: int = 6
) -> list[Section]:
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
                    heading=node,
                    content=[],
                    level=node.level,
                    start_index=idx,
                    end_index=idx + 1
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


def find_section_by_heading(
        doc: Document,
        heading_text: str,
        level: int | None = None,
        case_sensitive: bool = False
) -> Section | None:
    """Find the first section with a matching heading text.

    Parameters
    ----------
    doc : Document
        Document to search
    heading_text : str
        Text to search for in headings
    level : int or None, default = None
        If specified, only match headings at this level
    case_sensitive : bool, default = False
        Whether to perform case-sensitive matching

    Returns
    -------
    Section or None
        First matching section, or None if not found

    Examples
    --------
    >>> section = find_section_by_heading(doc, "Introduction")
    >>> if section:
    ...     print(f"Found at level {section.level}")

    Find level 2 heading only:
        >>> section = find_section_by_heading(doc, "Overview", level=2)

    """
    sections = get_all_sections(doc)

    # Prepare search text
    search_text = heading_text if case_sensitive else heading_text.lower()

    for section in sections:
        # Extract and compare heading text
        section_text = section.get_heading_text()
        if not case_sensitive:
            section_text = section_text.lower()

        # Check level if specified
        if level is not None and section.level != level:
            continue

        # Check text match
        if section_text == search_text:
            return section

    return None


def find_sections(
        doc: Document,
        predicate: Callable[[Section], bool]
) -> list[Section]:
    """Find all sections matching a predicate function.

    Parameters
    ----------
    doc : Document
        Document to search
    predicate : callable
        Function that takes a Section and returns True to include it

    Returns
    -------
    list of Section
        All sections matching the predicate

    Examples
    --------
    Find all level 2 sections:
        >>> sections = find_sections(doc, lambda s: s.level == 2)

    Find sections with "API" in heading:
        >>> sections = find_sections(
        ...     doc,
        ...     lambda s: "API" in s.get_heading_text()
        ... )

    Find sections with more than 3 paragraphs:
        >>> sections = find_sections(
        ...     doc,
        ...     lambda s: sum(1 for n in s.content if isinstance(n, Paragraph)) > 3
        ... )

    """
    all_sections = get_all_sections(doc)
    return [section for section in all_sections if predicate(section)]


def get_section_by_index(
        doc: Document,
        section_index: int
) -> Section | None:
    """Get a section by its index in the document.

    Parameters
    ----------
    doc : Document
        Document to search
    section_index : int
        Zero-based index of the section (supports negative indexing)

    Returns
    -------
    Section or None
        Section at the specified index, or None if index is out of range

    Examples
    --------
    >>> first_section = get_section_by_index(doc, 0)
    >>> last_section = get_section_by_index(doc, -1)

    """
    sections = get_all_sections(doc)

    try:
        return sections[section_index]
    except IndexError:
        return None


def _resolve_target(
        doc: Document,
        target: str | int,
        case_sensitive: bool = False
) -> Section | None:
    """Resolve a target (heading text or index) to a Section.

    Parameters
    ----------
    doc : Document
        Document to search
    target : str or int
        Heading text or section index
    case_sensitive : bool, default = False
        Whether text matching is case-sensitive

    Returns
    -------
    Section or None
        Resolved section, or None if not found

    """
    if isinstance(target, int):
        return get_section_by_index(doc, target)
    else:
        return find_section_by_heading(doc, target, case_sensitive=case_sensitive)


def add_section_after(
        doc: Document,
        target: str | int,
        new_section: Section | Document,
        case_sensitive: bool = False
) -> Document:
    """Add a new section after the specified target section.

    Parameters
    ----------
    doc : Document
        Document to modify
    target : str or int
        Heading text or section index to insert after
    new_section : Section or Document
        Section or document to insert
    case_sensitive : bool, default = False
        Whether text matching is case-sensitive (for string targets)

    Returns
    -------
    Document
        New document with the section inserted

    Raises
    ------
    ValueError
        If target section is not found

    Examples
    --------
    >>> new_section = Section(
    ...     heading=Heading(level=2, content=[Text("New Section")]),
    ...     content=[Paragraph(content=[Text("Content")])],
    ...     level=2, start_index=0, end_index=0
    ... )
    >>> updated_doc = add_section_after(doc, "Introduction", new_section)

    """
    target_section = _resolve_target(doc, target, case_sensitive)
    if target_section is None:
        raise ValueError(f"Target section not found: {target}")

    # Convert Section to list of nodes
    if isinstance(new_section, Section):
        new_nodes = [new_section.heading] + new_section.content
    else:  # Document
        new_nodes = new_section.children

    # Insert after target section
    insert_pos = target_section.end_index
    new_children = (
            doc.children[:insert_pos] +
            new_nodes +
            doc.children[insert_pos:]
    )

    return Document(children=new_children, metadata=doc.metadata.copy())


def add_section_before(
        doc: Document,
        target: str | int,
        new_section: Section | Document,
        case_sensitive: bool = False
) -> Document:
    """Add a new section before the specified target section.

    Parameters
    ----------
    doc : Document
        Document to modify
    target : str or int
        Heading text or section index to insert before
    new_section : Section or Document
        Section or document to insert
    case_sensitive : bool, default = False
        Whether text matching is case-sensitive (for string targets)

    Returns
    -------
    Document
        New document with the section inserted

    Raises
    ------
    ValueError
        If target section is not found

    Examples
    --------
    >>> new_section = Section(
    ...     heading=Heading(level=2, content=[Text("Preface")]),
    ...     content=[Paragraph(content=[Text("Introduction text")])],
    ...     level=2, start_index=0, end_index=0
    ... )
    >>> updated_doc = add_section_before(doc, "Chapter 1", new_section)

    """
    target_section = _resolve_target(doc, target, case_sensitive)
    if target_section is None:
        raise ValueError(f"Target section not found: {target}")

    # Convert Section to list of nodes
    if isinstance(new_section, Section):
        new_nodes = [new_section.heading] + new_section.content
    else:  # Document
        new_nodes = new_section.children

    # Insert before target section
    insert_pos = target_section.start_index
    new_children = (
            doc.children[:insert_pos] +
            new_nodes +
            doc.children[insert_pos:]
    )

    return Document(children=new_children, metadata=doc.metadata.copy())


def remove_section(
        doc: Document,
        target: str | int,
        case_sensitive: bool = False
) -> Document:
    """Remove a section from the document.

    Parameters
    ----------
    doc : Document
        Document to modify
    target : str or int
        Heading text or section index to remove
    case_sensitive : bool, default = False
        Whether text matching is case-sensitive (for string targets)

    Returns
    -------
    Document
        New document with the section removed

    Raises
    ------
    ValueError
        If target section is not found

    Examples
    --------
    >>> updated_doc = remove_section(doc, "Obsolete Section")
    >>> updated_doc = remove_section(doc, 2)  # Remove third section

    """
    target_section = _resolve_target(doc, target, case_sensitive)
    if target_section is None:
        raise ValueError(f"Target section not found: {target}")

    # Remove section (heading + content)
    new_children = (
            doc.children[:target_section.start_index] +
            doc.children[target_section.end_index:]
    )

    return Document(children=new_children, metadata=doc.metadata.copy())


def replace_section(
        doc: Document,
        target: str | int,
        new_content: Section | Document | list[Node],
        case_sensitive: bool = False
) -> Document:
    """Replace a section with new content.

    Parameters
    ----------
    doc : Document
        Document to modify
    target : str or int
        Heading text or section index to replace
    new_content : Section, Document, or list of Node
        New content to replace the section with
    case_sensitive : bool, default = False
        Whether text matching is case-sensitive (for string targets)

    Returns
    -------
    Document
        New document with the section replaced

    Raises
    ------
    ValueError
        If target section is not found

    Examples
    --------
    Replace with a new section:
        >>> new_section = Section(
        ...     heading=Heading(level=2, content=[Text("Updated")]),
        ...     content=[Paragraph(content=[Text("New content")])],
        ...     level=2, start_index=0, end_index=0
        ... )
        >>> updated_doc = replace_section(doc, "Old Section", new_section)

    Replace with custom nodes:
        >>> new_nodes = [
        ...     Heading(level=2, content=[Text("New Heading")]),
        ...     Paragraph(content=[Text("Content here")])
        ... ]
        >>> updated_doc = replace_section(doc, 0, new_nodes)

    """
    target_section = _resolve_target(doc, target, case_sensitive)
    if target_section is None:
        raise ValueError(f"Target section not found: {target}")

    # Convert new_content to list of nodes
    if isinstance(new_content, Section):
        new_nodes = [new_content.heading] + new_content.content
    elif isinstance(new_content, Document):
        new_nodes = new_content.children
    else:  # list[Node]
        new_nodes = new_content

    # Replace section
    new_children = (
            doc.children[:target_section.start_index] +
            new_nodes +
            doc.children[target_section.end_index:]
    )

    return Document(children=new_children, metadata=doc.metadata.copy())


def insert_into_section(
        doc: Document,
        target: str | int,
        content: Node | list[Node],
        position: Literal["start", "end", "after_heading"] = "end",
        case_sensitive: bool = False
) -> Document:
    """Insert content into an existing section.

    Parameters
    ----------
    doc : Document
        Document to modify
    target : str or int
        Heading text or section index to insert into
    content : Node or list of Node
        Content to insert
    position : {"start", "end", "after_heading"}, default = "end"
        Where to insert the content within the section
    case_sensitive : bool, default = False
        Whether text matching is case-sensitive (for string targets)

    Returns
    -------
    Document
        New document with content inserted

    Raises
    ------
    ValueError
        If target section is not found

    Notes
    -----
    - "start": Insert at the beginning of the section content (before all content)
    - "after_heading": Insert immediately after the heading (same as "start")
    - "end": Insert at the end of the section content (after all content)

    Examples
    --------
    >>> new_para = Paragraph(content=[Text("Additional info")])
    >>> updated_doc = insert_into_section(doc, "Methods", new_para, position="end")

    """
    target_section = _resolve_target(doc, target, case_sensitive)
    if target_section is None:
        raise ValueError(f"Target section not found: {target}")

    # Convert content to list
    new_nodes = [content] if isinstance(content, Node) else content

    # Determine insert position
    if position == "start" or position == "after_heading":
        # Insert right after heading
        insert_pos = target_section.start_index + 1
    elif position == "end":
        # Insert at end of section
        insert_pos = target_section.end_index
    else:
        raise ValueError(f"Invalid position: {position}")

    # Insert content
    new_children = (
            doc.children[:insert_pos] +
            new_nodes +
            doc.children[insert_pos:]
    )

    return Document(children=new_children, metadata=doc.metadata.copy())


def split_by_sections(
        doc: Document,
        include_preamble: bool = True
) -> list[Document]:
    """Split a document into separate documents by sections.

    Parameters
    ----------
    doc : Document
        Document to split
    include_preamble : bool, default = True
        If True and there is content before the first heading, include it
        as a separate document at the beginning

    Returns
    -------
    list of Document
        List of documents, one per section (plus preamble if present)

    Examples
    --------
    >>> docs = split_by_sections(doc)
    >>> for i, section_doc in enumerate(docs):
    ...     print(f"Section {i}: {len(section_doc.children)} nodes")

    """
    sections = get_all_sections(doc)
    documents = []

    # Handle preamble (content before first heading)
    if include_preamble:
        preamble = get_preamble(doc)
        if preamble:
            documents.append(Document(children=preamble))

    # Convert each section to a document
    for section in sections:
        documents.append(section.to_document())

    return documents


def extract_section(
        doc: Document,
        target: str | int,
        case_sensitive: bool = False
) -> Document:
    """Extract a single section as a standalone document.

    Parameters
    ----------
    doc : Document
        Document to extract from
    target : str or int
        Heading text or section index to extract
    case_sensitive : bool, default = False
        Whether text matching is case-sensitive (for string targets)

    Returns
    -------
    Document
        New document containing only the specified section

    Raises
    ------
    ValueError
        If target section is not found

    Examples
    --------
    >>> section_doc = extract_section(doc, "Methods")
    >>> section_doc = extract_section(doc, 0)  # First section

    """
    target_section = _resolve_target(doc, target, case_sensitive)
    if target_section is None:
        raise ValueError(f"Target section not found: {target}")

    return target_section.to_document()


def generate_toc(
        doc: Document,
        max_level: int = 3,
        style: Literal["markdown", "list", "nested"] = "markdown"
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

    for section in sections:
        if section.level > max_level:
            continue

        # Extract heading text and create slug
        heading_text = section.get_heading_text()
        slug = heading_text.lower().replace(" ", "-").replace(".", "")

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

    """
    if flat:
        # Flat list with all headings
        items = []
        for section in sections:
            heading_text = section.get_heading_text()
            item = ListItem(children=[
                Paragraph(content=[
                    Text(content=heading_text)
                ])
            ])
            items.append(item)

        return List(ordered=False, items=items)
    else:
        # Nested list respecting hierarchy
        # This is more complex - for now, return flat list
        # TODO: Implement proper nesting
        return _generate_toc_list(sections, flat=True)


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
    from all2md.ast.nodes import Link

    if not sections:
        return []

    # Create TOC heading
    toc_heading = Heading(level=1, content=[Text(content="Table of Contents")])

    # Build list items with links
    items = []
    for section in sections:
        if section.level > max_level:
            continue

        # Extract heading text and create slug
        heading_text = section.get_heading_text()
        slug = heading_text.lower().replace(" ", "-").replace(".", "")

        # Create link node
        link = Link(
            url=f"#{slug}",
            content=[Text(content=heading_text)],
            title=None
        )

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
        style: Literal["markdown", "list", "nested"] = "markdown"
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
    new_children = (
            doc.children[:insert_pos] +
            toc_nodes +
            doc.children[insert_pos:]
    )

    return Document(children=new_children, metadata=doc.metadata.copy())


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


def count_sections(
        doc: Document,
        level: int | None = None
) -> int:
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


def find_heading(
        doc: Document,
        text: str,
        level: int | None = None,
        case_sensitive: bool = False
) -> tuple[int, Heading] | None:
    """Find a heading node in the document.

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


__all__ = [
    "Section",
    "get_all_sections",
    "find_section_by_heading",
    "find_sections",
    "get_section_by_index",
    "add_section_after",
    "add_section_before",
    "remove_section",
    "replace_section",
    "insert_into_section",
    "split_by_sections",
    "extract_section",
    "generate_toc",
    "insert_toc",
    "get_preamble",
    "count_sections",
    "find_heading",
]
