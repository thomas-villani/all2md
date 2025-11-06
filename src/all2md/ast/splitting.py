#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/ast/splitting.py
"""Document splitting strategies.

This module provides strategies for splitting documents at semantic boundaries
based on different criteria: heading levels, word counts, number of parts,
thematic breaks, or automatic detection.

Classes
-------
SplitResult : Represents a split portion with metadata
DocumentSplitter : Main class for document splitting strategies

Functions
---------
parse_split_spec : Parse --split-by CLI argument

Examples
--------
Split by heading level:
    >>> splitter = DocumentSplitter()
    >>> splits = splitter.split_by_heading_level(doc, level=1)
    >>> for split in splits:
    ...     print(f"Part {split.index}: {split.title} ({split.word_count} words)")

Split by word count:
    >>> splits = splitter.split_by_word_count(doc, target_words=500)

Split into equal parts:
    >>> splits = splitter.split_by_parts(doc, num_parts=5)

Auto-detect best strategy:
    >>> splits = splitter.split_auto(doc)

Split by sections:
    >>> splits = splitter.split_by_sections(doc, include_preamble=True)

"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from all2md.ast.nodes import Document, Node, Paragraph, Text, ThematicBreak
from all2md.ast.sections import get_all_sections, get_preamble
from all2md.ast.utils import extract_text
from all2md.utils.text import slugify


@dataclass
class SplitResult:
    """Represents a split portion of a document.

    Attributes
    ----------
    document : Document
        The split document AST
    index : int
        1-based index of this split (001, 002, etc.)
    title : Optional[str]
        Title/heading text for this split (if available)
    word_count : int
        Approximate word count for this split
    metadata : dict
        Additional metadata for this split

    """

    document: Document
    index: int
    title: Optional[str] = None
    word_count: int = 0
    metadata: dict = field(default_factory=dict)

    def get_filename_slug(self) -> str:
        """Generate filesystem-safe slug from title.

        Returns
        -------
        str
            Sanitized slug suitable for filenames

        Examples
        --------
        >>> split = SplitResult(doc, 1, title="Chapter 1: Introduction")
        >>> split.get_filename_slug()
        'chapter-1-introduction'

        """
        if not self.title:
            return ""

        # Use the slugify function with max_length for filesystem safety
        slug = slugify(self.title, max_length=100)
        return slug


class DocumentSplitter:
    """Handles various document splitting strategies.

    This class provides methods to split documents at semantic boundaries
    based on different criteria: heading levels, word counts, number of parts,
    or automatic detection.

    """

    @staticmethod
    def split_by_heading_level(doc: Document, level: int, include_preamble: bool = True) -> list[SplitResult]:
        """Split document at every heading of specified level.

        Parameters
        ----------
        doc : Document
            Document to split
        level : int
            Heading level to split on (1-6)
        include_preamble : bool
            Whether to include content before first heading as separate split

        Returns
        -------
        list of SplitResult
            Split documents, one per section at specified level

        Raises
        ------
        ValueError
            If level is not between 1 and 6

        Examples
        --------
        >>> DocumentSplitter.split_by_heading_level(doc, level=1)

        """
        if not 1 <= level <= 6:
            raise ValueError(f"Heading level must be between 1 and 6, got {level}")

        sections = get_all_sections(doc, min_level=level, max_level=level)
        splits = []
        index = 1

        if include_preamble:
            preamble_nodes = get_preamble(doc)
            if preamble_nodes:
                preamble_doc = Document(
                    children=preamble_nodes,
                    metadata=doc.metadata.copy(),
                    source_location=doc.source_location,
                )
                text = extract_text(preamble_nodes, joiner=" ")
                word_count = len(text.split())

                splits.append(
                    SplitResult(
                        document=preamble_doc,
                        index=index,
                        title="Preamble",
                        word_count=word_count,
                    )
                )
                index += 1

        for section in sections:
            section_doc = section.to_document()
            section_doc.metadata = doc.metadata.copy()
            section_doc.source_location = doc.source_location

            text = extract_text(section_doc.children, joiner=" ")
            word_count = len(text.split())

            splits.append(
                SplitResult(
                    document=section_doc,
                    index=index,
                    title=section.get_heading_text(),
                    word_count=word_count,
                )
            )
            index += 1

        if not splits:
            full_text = extract_text(doc.children, joiner=" ")
            word_count = len(full_text.split())
            splits.append(
                SplitResult(
                    document=doc,
                    index=1,
                    title=None,
                    word_count=word_count,
                    metadata={"reason": "no_headings_found"},
                )
            )

        return splits

    @staticmethod
    def split_by_word_count(doc: Document, target_words: int) -> list[SplitResult]:
        """Split document by word count, maintaining section boundaries.

        Accumulates sections until target word count is reached, then creates
        a split. Ensures splits occur at section boundaries for semantic
        coherence.

        Parameters
        ----------
        doc : Document
            Document to split
        target_words : int
            Target word count per split (approximate)

        Returns
        -------
        list of SplitResult
            Split documents with roughly equal word counts

        Raises
        ------
        ValueError
            If target_words is less than 1

        Examples
        --------
        >>> DocumentSplitter.split_by_word_count(doc, target_words=500)

        """
        if target_words < 1:
            raise ValueError(f"target_words must be at least 1, got {target_words}")

        sections = get_all_sections(doc)
        if not sections:
            full_text = extract_text(doc.children, joiner=" ")
            word_count = len(full_text.split())
            return [
                SplitResult(
                    document=doc,
                    index=1,
                    title=None,
                    word_count=word_count,
                    metadata={"reason": "no_sections"},
                )
            ]

        splits = []
        current_children: list[Node] = []
        current_words = 0
        current_title = None
        index = 1

        preamble = get_preamble(doc)
        if preamble:
            current_children.extend(preamble)
            preamble_text = extract_text(preamble, joiner=" ")
            current_words += len(preamble_text.split())
            current_title = "Preamble"

        for section in sections:
            section_doc = section.to_document()
            section_text = extract_text(section_doc.children, joiner=" ")
            section_words = len(section_text.split())

            if current_words + section_words > target_words and current_children:
                split_doc = Document(
                    children=current_children.copy(),
                    metadata=doc.metadata.copy(),
                    source_location=doc.source_location,
                )
                splits.append(
                    SplitResult(
                        document=split_doc,
                        index=index,
                        title=current_title,
                        word_count=current_words,
                    )
                )
                index += 1
                current_children = []
                current_words = 0
                current_title = None

            current_children.extend(section_doc.children)
            current_words += section_words
            if current_title is None:
                current_title = section.get_heading_text()

        if current_children:
            split_doc = Document(
                children=current_children,
                metadata=doc.metadata.copy(),
                source_location=doc.source_location,
            )
            splits.append(
                SplitResult(
                    document=split_doc,
                    index=index,
                    title=current_title,
                    word_count=current_words,
                )
            )

        return (
            splits
            if splits
            else [
                SplitResult(
                    document=doc,
                    index=1,
                    title=None,
                    word_count=len(extract_text(doc.children, joiner=" ").split()),
                )
            ]
        )

    @staticmethod
    def split_by_parts(doc: Document, num_parts: int) -> list[SplitResult]:
        """Split document into N roughly equal parts at section boundaries.

        Calculates total word count and divides by num_parts to determine
        target words per part. Then uses word count splitting to create
        approximately equal splits.

        Parameters
        ----------
        doc : Document
            Document to split
        num_parts : int
            Number of parts to create

        Returns
        -------
        list of SplitResult
            Split documents with roughly equal word counts

        Raises
        ------
        ValueError
            If num_parts is less than 1

        Examples
        --------
        >>> DocumentSplitter.split_by_parts(doc, num_parts=5)

        """
        if num_parts < 1:
            raise ValueError(f"num_parts must be at least 1, got {num_parts}")

        total_text = extract_text(doc.children, joiner=" ")
        total_words = len(total_text.split())

        if total_words == 0:
            return [
                SplitResult(
                    document=doc,
                    index=1,
                    title=None,
                    word_count=0,
                )
            ]

        target_words_per_part = max(1, total_words // num_parts)

        return DocumentSplitter.split_by_word_count(doc, target_words=target_words_per_part)

    @staticmethod
    def split_by_break(doc: Document) -> list[SplitResult]:
        """Split document at thematic breaks (horizontal rules).

        Splits the document at any ThematicBreak nodes, which represent horizontal
        rules (``---``, ``***``, ``___``) in Markdown and similar separators in other formats.

        Parameters
        ----------
        doc : Document
            Document to split

        Returns
        -------
        list of SplitResult
            Split documents at thematic break boundaries

        Examples
        --------
        >>> DocumentSplitter.split_by_break(doc)

        """
        splits = []
        current_children: list[Node] = []
        split_index = 1

        for node in doc.children:
            if isinstance(node, ThematicBreak):
                # Found thematic break - create split if we have content
                if current_children:
                    split_doc = Document(
                        children=current_children.copy(),
                        metadata=doc.metadata.copy(),
                        source_location=doc.source_location,
                    )
                    text = extract_text(current_children, joiner=" ")
                    word_count = len(text.split())

                    splits.append(
                        SplitResult(
                            document=split_doc,
                            index=split_index,
                            title=f"Part {split_index}",
                            word_count=word_count,
                        )
                    )
                    split_index += 1
                    current_children = []
                # Skip the break itself
            else:
                current_children.append(node)

        # Add remaining content as final split
        if current_children:
            split_doc = Document(
                children=current_children,
                metadata=doc.metadata.copy(),
                source_location=doc.source_location,
            )
            text = extract_text(current_children, joiner=" ")
            word_count = len(text.split())

            splits.append(
                SplitResult(
                    document=split_doc,
                    index=split_index,
                    title=f"Part {split_index}",
                    word_count=word_count,
                )
            )

        # If no breaks found, return entire document as single split
        if not splits:
            full_text = extract_text(doc.children, joiner=" ")
            word_count = len(full_text.split())
            splits.append(
                SplitResult(
                    document=doc,
                    index=1,
                    title="Part 1",
                    word_count=word_count,
                    metadata={"reason": "no_breaks_found"},
                )
            )

        return splits

    @staticmethod
    def split_by_delimiter(doc: Document, delimiter: str) -> list[SplitResult]:
        """Split document at custom text delimiters.

        Searches for paragraphs or text nodes that contain only the delimiter text
        (allowing for whitespace) and splits the document at those points.

        Parameters
        ----------
        doc : Document
            Document to split
        delimiter : str
            Text delimiter to split on (e.g., ``"-----"``, ``"***"``, ``"<!-- split -->"``)

        Returns
        -------
        list of SplitResult
            Split documents at delimiter boundaries

        Examples
        --------
        >>> DocumentSplitter.split_by_delimiter(doc, delimiter="-----")

        """
        if not delimiter:
            raise ValueError("Delimiter cannot be empty")

        splits = []
        current_children: list[Node] = []
        split_index = 1

        delimiter_stripped = delimiter.strip()

        # Check if delimiter looks like a horizontal rule pattern
        is_hr_pattern = re.match(r"^-{3,}$|^\*{3,}$|^_{3,}$", delimiter_stripped)

        for node in doc.children:
            # Check if this node is a delimiter
            is_delimiter = False

            if isinstance(node, ThematicBreak) and is_hr_pattern:
                # ThematicBreak nodes represent horizontal rules (---, ***, ___)
                is_delimiter = True
            elif isinstance(node, Paragraph):
                # Check if paragraph contains only the delimiter text
                node_text = extract_text(node.content, joiner="").strip()
                if node_text == delimiter_stripped:
                    is_delimiter = True
            elif isinstance(node, Text):
                # Check if text node is the delimiter
                if node.content.strip() == delimiter_stripped:
                    is_delimiter = True

            if is_delimiter:
                # Found delimiter - create split if we have content
                if current_children:
                    split_doc = Document(
                        children=current_children.copy(),
                        metadata=doc.metadata.copy(),
                        source_location=doc.source_location,
                    )
                    text = extract_text(current_children, joiner=" ")
                    word_count = len(text.split())

                    splits.append(
                        SplitResult(
                            document=split_doc,
                            index=split_index,
                            title=f"Part {split_index}",
                            word_count=word_count,
                        )
                    )
                    split_index += 1
                    current_children = []
                # Skip the delimiter node itself
            else:
                current_children.append(node)

        # Add remaining content as final split
        if current_children:
            split_doc = Document(
                children=current_children,
                metadata=doc.metadata.copy(),
                source_location=doc.source_location,
            )
            text = extract_text(current_children, joiner=" ")
            word_count = len(text.split())

            splits.append(
                SplitResult(
                    document=split_doc,
                    index=split_index,
                    title=f"Part {split_index}",
                    word_count=word_count,
                )
            )

        # If no delimiters found, return entire document as single split
        if not splits:
            full_text = extract_text(doc.children, joiner=" ")
            word_count = len(full_text.split())
            splits.append(
                SplitResult(
                    document=doc,
                    index=1,
                    title="Part 1",
                    word_count=word_count,
                    metadata={"reason": "no_delimiters_found"},
                )
            )

        return splits

    @staticmethod
    def split_auto(doc: Document, target_words: int = 1500) -> list[SplitResult]:
        """Automatically determine best split strategy based on document structure.

        Analyzes document to find natural split points:
        1. Try h1 boundaries if sections are reasonable size
        2. Otherwise try h2 boundaries
        3. Fall back to word count splitting if sections too large

        Parameters
        ----------
        doc : Document
            Document to split
        target_words : int
            Target word count per split for fallback strategy

        Returns
        -------
        list of SplitResult
            Split documents using the best detected strategy

        Examples
        --------
        >>> DocumentSplitter.split_auto(doc)  # Target ~1500 words per split

        """
        sections_h1 = get_all_sections(doc, min_level=1, max_level=1)

        if sections_h1:
            h1_word_counts = []
            for section in sections_h1:
                section_text = extract_text(section.to_document().children, joiner=" ")
                h1_word_counts.append(len(section_text.split()))

            avg_h1_words = sum(h1_word_counts) / len(h1_word_counts)
            max_h1_words = max(h1_word_counts) if h1_word_counts else 0

            if avg_h1_words <= target_words * 2 and max_h1_words <= target_words * 3:
                splits = DocumentSplitter.split_by_heading_level(doc, level=1)
                for split in splits:
                    split.metadata["strategy"] = "auto:h1"
                return splits

        sections_h2 = get_all_sections(doc, min_level=2, max_level=2)
        if sections_h2:
            h2_word_counts = []
            for section in sections_h2:
                section_text = extract_text(section.to_document().children, joiner=" ")
                h2_word_counts.append(len(section_text.split()))

            avg_h2_words = sum(h2_word_counts) / len(h2_word_counts)

            if avg_h2_words <= target_words * 1.5:
                splits = DocumentSplitter.split_by_heading_level(doc, level=2)
                for split in splits:
                    split.metadata["strategy"] = "auto:h2"
                return splits

        splits = DocumentSplitter.split_by_word_count(doc, target_words=target_words)
        for split in splits:
            split.metadata["strategy"] = "auto:word_count"
        return splits

    @staticmethod
    def split_by_sections(doc: Document, include_preamble: bool = True) -> list[SplitResult]:
        """Split document into separate documents by sections.

        This method was moved from document_utils.py and adapted to return
        list[SplitResult] for consistency with other DocumentSplitter methods.

        Parameters
        ----------
        doc : Document
            Document to split
        include_preamble : bool, default = True
            If True and there is content before the first heading, include it
            as a separate split at the beginning

        Returns
        -------
        list of SplitResult
            List of split results, one per section (plus preamble if present)

        Examples
        --------
        >>> splits = DocumentSplitter.split_by_sections(doc)
        >>> for i, split_result in enumerate(splits):
        ...     print(f"Section {i}: {len(split_result.document.children)} nodes")

        """
        sections = get_all_sections(doc)
        splits = []
        index = 1

        # Handle preamble (content before first heading)
        if include_preamble:
            preamble = get_preamble(doc)
            if preamble:
                preamble_doc = Document(
                    children=preamble, metadata=doc.metadata.copy(), source_location=doc.source_location
                )
                text = extract_text(preamble, joiner=" ")
                word_count = len(text.split())

                splits.append(
                    SplitResult(
                        document=preamble_doc,
                        index=index,
                        title="Preamble",
                        word_count=word_count,
                    )
                )
                index += 1

        # Convert each section to a split result
        for section in sections:
            section_doc = section.to_document()
            section_doc.metadata = doc.metadata.copy()
            section_doc.source_location = doc.source_location

            text = extract_text(section_doc.children, joiner=" ")
            word_count = len(text.split())

            splits.append(
                SplitResult(
                    document=section_doc,
                    index=index,
                    title=section.get_heading_text(),
                    word_count=word_count,
                )
            )
            index += 1

        return splits


def parse_split_spec(spec: str) -> tuple[str, Any]:
    """Parse --split-by CLI argument into strategy and parameters.

    Parameters
    ----------
    spec : str
        Split specification string

    Returns
    -------
    tuple of (str, Any)
        (strategy_name, parameter) where:
        - ("heading", 1) for "h1"
        - ("heading", 2) for "h2"
        - ("length", 400) for "length=400"
        - ("parts", 4) for "parts=4"
        - ("delimiter", "-----") for "delimiter=-----"
        - ("break", None) for "break"
        - ("page", None) for "page"
        - ("chapter", None) for "chapter"
        - ("auto", None) for "auto"

    Raises
    ------
    ValueError
        If spec format is invalid

    Examples
    --------
    >>> parse_split_spec("h1")
    ('heading', 1)
    >>> parse_split_spec("length=500")
    ('length', 500)
    >>> parse_split_spec("parts=3")
    ('parts', 3)
    >>> parse_split_spec("delimiter=-----")
    ('delimiter', '-----')
    >>> parse_split_spec("auto")
    ('auto', None)

    """
    spec = spec.strip()

    # Check for heading levels (case-insensitive)
    if spec.lower().startswith("h") and len(spec) == 2 and spec[1].isdigit():
        level = int(spec[1])
        if not 1 <= level <= 6:
            raise ValueError(f"Heading level must be between 1 and 6, got {level}")
        return ("heading", level)

    if "=" in spec:
        key, value = spec.split("=", 1)
        key = key.strip().lower()
        value = value.strip()

        if key == "length":
            try:
                word_count = int(value)
                if word_count < 1:
                    raise ValueError("length must be at least 1")
                return ("length", word_count)
            except ValueError as e:
                raise ValueError(f"Invalid length value: {value}") from e

        if key == "parts":
            try:
                num_parts = int(value)
                if num_parts < 1:
                    raise ValueError("parts must be at least 1")
                return ("parts", num_parts)
            except ValueError as e:
                raise ValueError(f"Invalid parts value: {value}") from e

        if key == "delimiter":
            if not value:
                raise ValueError("Delimiter value cannot be empty")
            # Process escape sequences (e.g., \n, \t, etc.)
            try:
                # Use encode/decode to handle escape sequences
                processed_value = value.encode().decode("unicode_escape")
            except Exception:
                # If decoding fails, use the value as-is
                processed_value = value
            return ("delimiter", processed_value)

        raise ValueError(f"Unknown split strategy: {key}")

    if spec.lower() in ("page", "chapter", "auto", "break"):
        return (spec.lower(), None)

    raise ValueError(
        f"Invalid split specification: {spec}. "
        "Expected: h1-h6, length=N, parts=N, delimiter=TEXT, break, page, chapter, or auto"
    )


__all__ = [
    "SplitResult",
    "DocumentSplitter",
    "parse_split_spec",
]
