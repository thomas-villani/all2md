#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/transforms/builtin.py
"""Built-in transforms for common document processing tasks.

This module provides a collection of ready-to-use transforms for common
document manipulation operations. All transforms are registered via entry
points for discovery and CLI usage.

Available Transforms
--------------------
- RemoveImagesTransform: Remove all images
- RemoveNodesTransform: Remove nodes of specified types
- HeadingOffsetTransform: Shift heading levels
- LinkRewriterTransform: Rewrite URLs with regex patterns
- TextReplacerTransform: Find and replace text
- AddHeadingIdsTransform: Generate unique IDs for headings
- RemoveBoilerplateTextTransform: Remove common boilerplate patterns
- AddConversionTimestampTransform: Add timestamp to metadata
- CalculateWordCountTransform: Calculate word and character counts
- AddAttachmentFootnotesTransform: Add footnote definitions for attachment references
- GenerateTocTransform: Generate table of contents from document headings

Examples
--------
Remove all images:

    >>> transform = RemoveImagesTransform()
    >>> new_doc = transform.transform(doc)

Offset headings by 2 levels:

    >>> transform = HeadingOffsetTransform(offset=2)
    >>> new_doc = transform.transform(doc)

Add unique IDs to headings:

    >>> transform = AddHeadingIdsTransform(id_prefix="doc-")
    >>> new_doc = transform.transform(doc)

Add footnote definitions for attachment references:

    >>> transform = AddAttachmentFootnotesTransform(section_title="Image Sources")
    >>> new_doc = transform.transform(doc)

Generate table of contents:

    >>> transform = GenerateTocTransform(max_depth=3, position="top")
    >>> new_doc = transform.transform(doc)

"""

from __future__ import annotations

import difflib
import re
from datetime import datetime, timezone
from typing import cast

from all2md.ast.nodes import (
    Document,
    FootnoteDefinition,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    Node,
    Paragraph,
    Text,
    replace_node_children,
)
from all2md.ast.transforms import NodeTransformer
from all2md.ast.utils import extract_text
from all2md.constants import DEFAULT_BOILERPLATE_PATTERNS, MAX_TEXT_LENGTH_FOR_REGEX, MAX_URL_LENGTH
from all2md.transforms.hooks import _NODE_TYPE_MAP, HookManager
from all2md.utils.attachments import sanitize_footnote_label
from all2md.utils.security import validate_user_regex_pattern
from all2md.utils.text import make_unique_slug, slugify


class RemoveImagesTransform(NodeTransformer):
    """Remove all Image nodes from the AST.

    This transform removes every Image node it encounters, useful for
    creating text-only versions of documents or reducing document size.

    Examples
    --------
    >>> transform = RemoveImagesTransform()
    >>> doc_without_images = transform.transform(document)

    """

    def visit_image(self, node: Image) -> None:  # type: ignore[override]
        """Remove image by returning None.

        Parameters
        ----------
        node : Image
            Image node to remove

        Returns
        -------
        None
            Always returns None to remove the node

        """
        return None


class RemoveNodesTransform(NodeTransformer):
    """Remove nodes of specified types from the AST.

    This is a generic transform that can remove any combination of node
    types. Useful for stripping specific elements like tables, code blocks,
    or any other node type.

    Parameters
    ----------
    node_types : list[str]
        List of node type names to remove (e.g., ['image', 'table', 'code_block'])

    Examples
    --------
    Remove images and tables:

        >>> transform = RemoveNodesTransform(node_types=['image', 'table'])
        >>> cleaned_doc = transform.transform(document)

    """

    def __init__(self, node_types: list[str]):
        """Initialize with list of node types to remove.

        Parameters
        ----------
        node_types : list[str]
            Node type names to remove

        Raises
        ------
        ValueError
            If 'document' is in node_types (cannot remove root node), or
            if any node_type is unknown (typo detection)

        """
        # Validate that 'document' is not in node_types
        if "document" in node_types:
            raise ValueError(
                "Cannot remove 'document' node type - this would break the pipeline. "
                "Consider using specific child node types instead (e.g., 'heading', 'paragraph')."
            )

        # Build set of known node types from _NODE_TYPE_MAP
        known_types = {node_type for _, node_type in _NODE_TYPE_MAP}

        # Validate each node_type against known types
        invalid_types = []
        for node_type in node_types:
            if node_type not in known_types:
                # Find close matches using difflib
                suggestions = difflib.get_close_matches(node_type, known_types, n=3, cutoff=0.6)
                if suggestions:
                    suggestion_str = ", ".join(f"'{s}'" for s in suggestions)
                    invalid_types.append(f"'{node_type}' (did you mean {suggestion_str}?)")
                else:
                    invalid_types.append(f"'{node_type}'")

        if invalid_types:
            raise ValueError(
                f"Unknown node type(s): {', '.join(invalid_types)}. "
                f"Valid types are: {', '.join(sorted(known_types))}"
            )

        self.node_types = set(node_types)

    def transform(self, node: Node) -> Node | None:
        """Transform node, removing it if it matches specified types.

        Parameters
        ----------
        node : Node
            Node to potentially remove

        Returns
        -------
        Node or None
            None if node should be removed, otherwise transformed node

        """
        # Get node type string using static method (no instantiation needed)
        node_type = HookManager.get_node_type(node)

        # Remove if it matches (node_type can be None for unknown types)
        if node_type and node_type in self.node_types:
            return None

        # Otherwise continue normal traversal
        return super().transform(node)


class HeadingOffsetTransform(NodeTransformer):
    """Shift heading levels by a specified offset.

    This transform adjusts all heading levels in the document by adding
    an offset value. Levels are clamped to the valid range of 1-6.

    Parameters
    ----------
    offset : int, default = 1
        Number of levels to shift (positive to increase, negative to decrease)

    Examples
    --------
    Increase all heading levels by 1 (H1 becomes H2):

        >>> transform = HeadingOffsetTransform(offset=1)
        >>> new_doc = transform.transform(document)

    Decrease all heading levels by 1 (H2 becomes H1):

        >>> transform = HeadingOffsetTransform(offset=-1)
        >>> new_doc = transform.transform(document)

    """

    def __init__(self, offset: int = 1):
        """Initialize with heading level offset.

        Parameters
        ----------
        offset : int
            Heading level adjustment

        """
        self.offset = offset

    def visit_heading(self, node: Heading) -> Heading:
        """Adjust heading level.

        Parameters
        ----------
        node : Heading
            Heading node to adjust

        Returns
        -------
        Heading
            Heading with adjusted level

        """
        # Calculate new level, clamped to 1-6
        new_level = max(1, min(6, node.level + self.offset))

        return Heading(
            level=new_level,
            content=self._transform_children(node.content),
            metadata=node.metadata.copy(),
            source_location=node.source_location,
        )


class LinkRewriterTransform(NodeTransformer):
    r"""Rewrite link URLs using regex pattern matching.

    This transform allows flexible URL rewriting using regular expressions.
    Useful for converting relative links to absolute, updating base URLs,
    or modifying link schemes.

    Parameters
    ----------
    pattern : str
        Regex pattern to match in URLs
    replacement : str
        Replacement string (can include regex groups like \\1, \\2)

    Raises
    ------
    SecurityError
        If the pattern contains dangerous constructs that could lead to
        ReDoS (Regular Expression Denial of Service) attacks

    Examples
    --------
    Convert relative links to absolute:

        >>> transform = LinkRewriterTransform(
        ...     pattern=r'^/docs/',
        ...     replacement='https://example.com/docs/'
        ... )
        >>> new_doc = transform.transform(document)

    Notes
    -----
    For security reasons, this transform validates user-supplied regex patterns
    to prevent ReDoS attacks. Patterns with nested quantifiers or excessive
    backtracking potential are rejected. See `validate_user_regex_pattern()`
    for details on what patterns are considered safe.

    """

    def __init__(self, pattern: str, replacement: str):
        """Initialize with pattern and replacement.

        Parameters
        ----------
        pattern : str
            Regex pattern
        replacement : str
            Replacement string

        Raises
        ------
        SecurityError
            If pattern contains dangerous constructs

        """
        # Validate pattern for ReDoS protection
        validate_user_regex_pattern(pattern)

        self.pattern = re.compile(pattern)
        self.replacement = replacement

    def visit_link(self, node: Link) -> Link:
        """Rewrite link URL if it matches pattern.

        Parameters
        ----------
        node : Link
            Link node to potentially rewrite

        Returns
        -------
        Link
            Link with potentially rewritten URL

        """
        # Skip rewriting for excessively long URLs to prevent excessive processing
        # Preserve the original URL instead of truncating (prevents data loss)
        if len(node.url) > MAX_URL_LENGTH:
            new_url = node.url
        else:
            # Apply regex substitution to safe-length URLs
            new_url = self.pattern.sub(self.replacement, node.url)

        return Link(
            url=new_url,
            content=self._transform_children(node.content),
            title=node.title,
            metadata=node.metadata.copy(),
            source_location=node.source_location,
        )


class TextReplacerTransform(NodeTransformer):
    """Find and replace text in Text nodes.

    This transform performs simple text replacement across all Text nodes
    in the document. For regex-based replacement, use a custom transform.

    Parameters
    ----------
    find : str
        Text to find
    replace : str
        Replacement text

    Examples
    --------
    Replace all instances of "TODO":

        >>> transform = TextReplacerTransform(find="TODO", replace="DONE")
        >>> new_doc = transform.transform(document)

    """

    def __init__(self, find: str, replace: str):
        """Initialize with find and replace strings.

        Parameters
        ----------
        find : str
            Text to find
        replace : str
            Replacement text

        """
        self.find = find
        self.replace = replace

    def visit_text(self, node: Text) -> Text:
        """Replace text in node content.

        Parameters
        ----------
        node : Text
            Text node to process

        Returns
        -------
        Text
            Text node with replacements applied

        """
        new_content = node.content.replace(self.find, self.replace)

        return Text(content=new_content, metadata=node.metadata.copy(), source_location=node.source_location)


class AddHeadingIdsTransform(NodeTransformer):
    """Generate and add unique IDs to heading nodes.

    This transform creates slugified IDs from heading text and adds them
    to the heading metadata. These IDs can be used by renderers to create
    HTML anchors for linkable sections.

    Parameters
    ----------
    id_prefix : str, default = ""
        Prefix to add to all generated IDs
    separator : str, default = "-"
        Separator for multi-word slugs and duplicate handling

    Examples
    --------
    Basic usage:

        >>> transform = AddHeadingIdsTransform()
        >>> new_doc = transform.transform(document)
        >>> # "My Heading" -> metadata['id'] = "my-heading"

    With prefix:

        >>> transform = AddHeadingIdsTransform(id_prefix="doc-")
        >>> new_doc = transform.transform(document)
        >>> # "My Heading" -> metadata['id'] = "doc-my-heading"

    """

    def __init__(self, id_prefix: str = "", separator: str = "-"):
        """Initialize with prefix and separator.

        Parameters
        ----------
        id_prefix : str
            Prefix for IDs
        separator : str
            Word separator

        """
        self.id_prefix = id_prefix
        self.separator = separator
        self._id_counts: dict[str, int] = {}

    def visit_heading(self, node: Heading) -> Heading:
        """Add unique ID to heading.

        Parameters
        ----------
        node : Heading
            Heading to process

        Returns
        -------
        Heading
            Heading with ID in metadata

        """
        # Extract text from heading content (no joiner for slugification)
        text = extract_text(node.content, joiner="")

        # Generate slug using shared utility
        base_slug = slugify(text, separator=self.separator)

        # Make unique using shared utility
        slug = make_unique_slug(base_slug, self._id_counts, separator=self.separator)

        # Add prefix
        final_id = f"{self.id_prefix}{slug}" if self.id_prefix else slug

        # Add to metadata
        new_metadata = node.metadata.copy()
        new_metadata["id"] = final_id

        return Heading(
            level=node.level,
            content=self._transform_children(node.content),
            metadata=new_metadata,
            source_location=node.source_location,
        )


class RemoveBoilerplateTextTransform(NodeTransformer):
    r"""Remove paragraphs matching common boilerplate patterns.

    This transform removes paragraphs whose text matches predefined
    patterns like "CONFIDENTIAL", "Page X of Y", etc. Useful for
    cleaning up corporate documents and reports.

    Parameters
    ----------
    patterns : list[str], optional
        List of regex patterns to match (default: common boilerplate)
    skip_if_truncated : bool, default = True
        If True, skip pattern matching when text exceeds MAX_TEXT_LENGTH_FOR_REGEX
        to avoid false positives with end-anchored patterns ($). If False, match
        against truncated text (may produce incorrect results with anchors).

    Raises
    ------
    SecurityError
        If any user-supplied pattern contains dangerous constructs that
        could lead to ReDoS (Regular Expression Denial of Service) attacks

    Examples
    --------
    Use default patterns:

        >>> transform = RemoveBoilerplateTextTransform()
        >>> cleaned_doc = transform.transform(document)

    Custom patterns with anchoring:

        >>> transform = RemoveBoilerplateTextTransform(
        ...     patterns=[r"^DRAFT$", r"^INTERNAL ONLY$", r"^Page \d+ of \d+$"]
        ... )
        >>> cleaned_doc = transform.transform(document)

    Allow matching truncated text (not recommended):

        >>> transform = RemoveBoilerplateTextTransform(skip_if_truncated=False)
        >>> cleaned_doc = transform.transform(document)

    Notes
    -----
    **Pattern Matching Semantics**: This transform uses Python's `re.match()`,
    which implicitly anchors at the start of the string (equivalent to adding
    `^` at the beginning). For exact matching of entire paragraphs, patterns
    should include an end anchor (`$`). For example:

    - `r"CONFIDENTIAL"` - Matches paragraphs starting with "CONFIDENTIAL"
    - `r"CONFIDENTIAL$"` - Matches paragraphs that are exactly "CONFIDENTIAL"
      or start with "CONFIDENTIAL" followed by only whitespace
    - `r"^CONFIDENTIAL$"` - Explicitly anchored (redundant `^`, but clearer)

    If you need to match patterns anywhere in the text (not just at the start),
    use `re.search()` semantics by implementing a custom transform.

    **Security**: For security reasons, this transform validates user-supplied
    regex patterns to prevent ReDoS attacks. Default patterns are pre-validated
    and trusted. Patterns with nested quantifiers or excessive backtracking
    potential are rejected. See `validate_user_regex_pattern()` for details.

    **Truncation Behavior**: Text longer than MAX_TEXT_LENGTH_FOR_REGEX
    (10000 characters) is truncated before matching for ReDoS protection.
    With ``skip_if_truncated=True`` (default), such paragraphs are preserved
    to avoid false positives from patterns using end anchors ($). This is
    safer but may miss some boilerplate. With ``skip_if_truncated=False``,
    matching proceeds on truncated text, which may incorrectly match or
    not match patterns with anchors.

    """

    def __init__(self, patterns: list[str] | None = None, skip_if_truncated: bool = True):
        """Initialize with patterns.

        Parameters
        ----------
        patterns : list[str] or None
            Regex patterns to match (None uses defaults)
        skip_if_truncated : bool
            Skip matching when text is truncated (safer default)

        Raises
        ------
        SecurityError
            If any user-supplied pattern contains dangerous constructs

        """
        self.patterns = patterns if patterns is not None else DEFAULT_BOILERPLATE_PATTERNS
        self.skip_if_truncated = skip_if_truncated

        # Only validate user-supplied patterns (not defaults, which we trust)
        if patterns is not None:
            for pattern in patterns:
                validate_user_regex_pattern(pattern)

        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.patterns]

    def visit_paragraph(self, node: Paragraph) -> Paragraph | None:  # type: ignore[override]
        """Remove paragraph if it matches boilerplate pattern.

        Parameters
        ----------
        node : Paragraph
            Paragraph to check

        Returns
        -------
        Paragraph or None
            None if matches boilerplate, otherwise paragraph

        """
        # Extract text from paragraph (no joiner to match exact text)
        text = extract_text(node.content, joiner="")

        # Limit text length to prevent excessive regex processing
        text_stripped = text.strip()
        is_truncated = len(text_stripped) > MAX_TEXT_LENGTH_FOR_REGEX

        if is_truncated:
            if self.skip_if_truncated:
                # Skip matching entirely to avoid false positives with end anchors
                # Preserve the paragraph unchanged
                return super().visit_paragraph(node)
            else:
                # Use truncated text (may produce incorrect results with anchors)
                text_to_check = text_stripped[:MAX_TEXT_LENGTH_FOR_REGEX]
        else:
            text_to_check = text_stripped

        # Check against patterns
        for pattern in self._compiled:
            if pattern.match(text_to_check):
                return None  # Remove

        # Keep paragraph
        return super().visit_paragraph(node)


class AddConversionTimestampTransform(NodeTransformer):
    """Add conversion timestamp to document metadata.

    This transform adds a timezone-aware UTC timestamp to the document metadata
    indicating when the conversion occurred. Useful for tracking document versions
    and conversion history. All timestamps are generated in UTC to ensure consistency
    across different time zones.

    Parameters
    ----------
    field_name : str, default = "conversion_timestamp"
        Metadata field name for the timestamp
    timestamp_format : str, default = "iso"
        Timestamp format: "iso" for ISO 8601 with timezone, "unix" for Unix timestamp,
        or any strftime format string
    timespec : str, default = "seconds"
        Time precision for ISO format timestamps. Valid values are:
        - "auto": Automatic precision
        - "hours": Hours precision
        - "minutes": Minutes precision
        - "seconds": Seconds precision (default, reduces noisy diffs)
        - "milliseconds": Milliseconds precision
        - "microseconds": Microseconds precision
        Only applies when timestamp_format="iso". Ignored for other formats.

    Examples
    --------
    Add ISO 8601 timestamp with second precision (default):

        >>> transform = AddConversionTimestampTransform()
        >>> new_doc = transform.transform(document)
        >>> # metadata['conversion_timestamp'] = "2025-01-01T12:00:00+00:00"

    Add ISO 8601 timestamp with microsecond precision:

        >>> transform = AddConversionTimestampTransform(timespec="microseconds")
        >>> new_doc = transform.transform(document)
        >>> # metadata['conversion_timestamp'] = "2025-01-01T12:00:00.123456+00:00"

    Add Unix timestamp:

        >>> transform = AddConversionTimestampTransform(timestamp_format="unix")
        >>> new_doc = transform.transform(document)
        >>> # metadata['conversion_timestamp'] = "1735732800"

    Custom strftime format:

        >>> transform = AddConversionTimestampTransform(
        ...     field_name="converted_at",
        ...     timestamp_format="%Y-%m-%d %H:%M:%S UTC"
        ... )
        >>> new_doc = transform.transform(document)
        >>> # metadata['converted_at'] = "2025-01-01 12:00:00 UTC"

    Notes
    -----
    All timestamps are generated in UTC (Coordinated Universal Time) using
    `datetime.now(timezone.utc)`. This ensures consistent timestamps regardless
    of the server's local timezone.

    The default timespec="seconds" is recommended to reduce noisy git diffs
    when regenerating documents, as subsecond precision is rarely needed for
    document conversion timestamps.

    """

    def __init__(
        self, field_name: str = "conversion_timestamp", timestamp_format: str = "iso", timespec: str = "seconds"
    ):
        """Initialize with field name, format, and time precision.

        Parameters
        ----------
        field_name : str
            Metadata field name
        timestamp_format : str
            Timestamp format
        timespec : str
            Time precision for ISO format (default: "seconds")

        """
        self.field_name = field_name
        self.timestamp_format = timestamp_format
        self.timespec = timespec

    def visit_document(self, node: Document) -> Document:
        """Add timestamp to document metadata.

        Parameters
        ----------
        node : Document
            Document to process

        Returns
        -------
        Document
            Document with timestamp in metadata

        """
        # Generate timestamp (timezone-aware UTC)
        now = datetime.now(timezone.utc)

        if self.timestamp_format == "iso":
            timestamp = now.isoformat(timespec=self.timespec)
        elif self.timestamp_format == "unix":
            timestamp = str(int(now.timestamp()))
        else:
            # Custom strftime format
            timestamp = now.strftime(self.timestamp_format)

        # Add to metadata
        new_metadata = node.metadata.copy()
        new_metadata[self.field_name] = timestamp

        return Document(
            children=self._transform_children(node.children),
            metadata=new_metadata,
            source_location=node.source_location,
        )


class CalculateWordCountTransform(NodeTransformer):
    """Calculate word and character counts and add to metadata.

    This transform traverses the entire document, extracts all text,
    and calculates word and character counts. The counts are added
    to the document metadata.

    Parameters
    ----------
    word_field : str, default = "word_count"
        Metadata field name for word count
    char_field : str, default = "char_count"
        Metadata field name for character count

    Examples
    --------
    Basic usage:

        >>> transform = CalculateWordCountTransform()
        >>> new_doc = transform.transform(document)
        >>> # metadata['word_count'] = 150
        >>> # metadata['char_count'] = 890

    Custom field names:

        >>> transform = CalculateWordCountTransform(
        ...     word_field="words",
        ...     char_field="characters"
        ... )
        >>> new_doc = transform.transform(document)

    Notes
    -----
    **Character Count Behavior**: The `char_count` metric represents the length
    of normalized text extracted from the AST, not the original document's
    character count. During text extraction, text fragments from separate AST
    nodes are joined with spaces, which may introduce synthetic spacing not
    present in the original document. For example, if the AST contains two
    adjacent Text nodes ``Text("hello")`` and ``Text("world")``, the extracted
    text will be ``"hello world"`` (11 characters including the inserted space),
    even though the original text nodes only contain 10 characters total.

    This normalized approach provides consistent metrics across different AST
    structures, though it may not exactly match the original document's byte
    count. Word count is calculated by splitting the normalized text on
    whitespace, which is generally more robust to these variations.

    """

    def __init__(self, word_field: str = "word_count", char_field: str = "char_count"):
        """Initialize with field names.

        Parameters
        ----------
        word_field : str
            Field name for word count
        char_field : str
            Field name for character count

        """
        self.word_field = word_field
        self.char_field = char_field

    def visit_document(self, node: Document) -> Document:
        """Calculate counts and add to metadata.

        Parameters
        ----------
        node : Document
            Document to analyze

        Returns
        -------
        Document
            Document with counts in metadata

        """
        # Extract all text (with space joiner for word counting)
        all_text = extract_text(node, joiner=" ")

        # Calculate counts
        word_count = len(all_text.split())
        char_count = len(all_text)

        # Add to metadata
        new_metadata = node.metadata.copy()
        new_metadata[self.word_field] = word_count
        new_metadata[self.char_field] = char_count

        return Document(
            children=self._transform_children(node.children),
            metadata=new_metadata,
            source_location=node.source_location,
        )


class AddAttachmentFootnotesTransform(NodeTransformer):
    """Add footnote definitions for attachment references.

    When attachments are processed with alt_text_mode="footnote", they generate
    footnote-style references like ![image][^label] but no corresponding definitions.
    This transform scans the AST for such references and adds FootnoteDefinition
    nodes with source information.

    Parameters
    ----------
    section_title : str or None, default "Attachments"
        Title for the footnote section heading. If None, no heading is added.
    add_definitions_for_images : bool, default True
        Add definitions for image footnote references
    add_definitions_for_links : bool, default True
        Add definitions for link footnote references

    Examples
    --------
    Add footnote definitions after conversion:

        >>> transform = AddAttachmentFootnotesTransform()
        >>> doc_with_footnotes = transform.transform(document)

    Custom section title:

        >>> transform = AddAttachmentFootnotesTransform(section_title="Image Sources")
        >>> doc_with_footnotes = transform.transform(document)

    Notes
    -----
    This transform works by:
    1. Collecting all Image and Link nodes with empty URLs (indicates footnote mode)
    2. Extracting footnote labels from alt text or title
    3. Handling duplicate labels by appending numeric suffixes (-2, -3, etc.)
    4. Creating FootnoteDefinition nodes with source information
    5. Appending definitions to the end of the document

    Duplicate labels are resolved using a counter mechanism similar to heading ID
    generation. When a label appears multiple times, subsequent occurrences get
    a numeric suffix to ensure unique footnote identifiers

    """

    def __init__(
        self,
        section_title: str | None = "Attachments",
        add_definitions_for_images: bool = True,
        add_definitions_for_links: bool = True,
    ):
        """Initialize transform with options.

        Parameters
        ----------
        section_title : str or None
            Heading for footnotes section
        add_definitions_for_images : bool
            Whether to process image footnotes
        add_definitions_for_links : bool
            Whether to process link footnotes

        """
        self.section_title = section_title
        self.add_definitions_for_images = add_definitions_for_images
        self.add_definitions_for_links = add_definitions_for_links
        self._footnote_refs: dict[str, str] = {}  # label -> source info
        self._label_counts: dict[str, int] = {}  # base label -> occurrence count

    def visit_document(self, node: Document) -> Document:
        """Process document and add footnote definitions.

        Parameters
        ----------
        node : Document
            Document to process

        Returns
        -------
        Document
            Document with footnote definitions added

        """
        # Reset footnote collection
        self._footnote_refs = {}
        self._label_counts = {}

        # Traverse document to collect footnote references
        self._collect_footnote_refs(node)

        # If no footnotes found, still perform normal traversal
        # This ensures subclasses and other transforms work correctly
        if not self._footnote_refs:
            return super().visit_document(node)

        # Create footnote definitions
        new_children = list(node.children)

        # Add section heading if specified
        if self.section_title:
            new_children.append(Heading(level=2, content=[Text(content=self.section_title)]))

        # Add footnote definitions
        for label, source_info in sorted(self._footnote_refs.items()):
            definition = FootnoteDefinition(
                identifier=label, content=[Paragraph(content=[Text(content=f"Source: {source_info}")])]
            )
            new_children.append(definition)

        return Document(
            children=self._transform_children(new_children),
            metadata=node.metadata,
            source_location=node.source_location,
        )

    def _collect_footnote_refs(self, node: Node) -> None:
        """Recursively collect footnote references from AST.

        Parameters
        ----------
        node : Node
            Node to scan

        """
        # Check if this is an Image or Link with empty URL (footnote mode)
        if self.add_definitions_for_images and isinstance(node, Image) and not node.url:
            # Extract footnote label from alt_text, metadata, or fallback
            source_text = node.alt_text or node.metadata.get("original_filename") or "attachment"
            base_label = sanitize_footnote_label(source_text)
            # Use helper to add label with automatic duplicate handling
            self._add_footnote_label(base_label, source_text)

        if self.add_definitions_for_links and isinstance(node, Link) and not node.url:
            # Extract label from link content or metadata
            link_text = self._get_link_text(node)
            source_text = link_text or node.metadata.get("original_filename") or "attachment"
            base_label = sanitize_footnote_label(source_text)
            # Use helper to add label with automatic duplicate handling
            self._add_footnote_label(base_label, source_text)

        # Recurse into children
        if hasattr(node, "children") and isinstance(node.children, list):
            for child in node.children:
                self._collect_footnote_refs(child)

        # Recurse into content
        if hasattr(node, "content") and isinstance(node.content, list):
            for child in node.content:
                self._collect_footnote_refs(child)

    def _add_footnote_label(self, base_label: str, source_text: str) -> None:
        """Add a footnote label with automatic duplicate handling.

        This helper method handles the common logic for adding footnote labels
        with numeric suffixes when duplicates are encountered. It updates both
        _label_counts and _footnote_refs.

        Parameters
        ----------
        base_label : str
            Base label to use (will be made unique if necessary)
        source_text : str
            Source text to store in the footnote reference

        """
        if not base_label:
            return

        # Handle duplicate labels with numeric suffix
        if base_label in self._label_counts:
            self._label_counts[base_label] += 1
            label = f"{base_label}-{self._label_counts[base_label]}"
        else:
            self._label_counts[base_label] = 1
            label = base_label

        self._footnote_refs[label] = source_text

    def _get_link_text(self, node: Link) -> str:
        """Extract text content from link node.

        This method uses extract_text to capture all nested text content,
        including text inside Emphasis, Strong, and other formatting nodes.

        Parameters
        ----------
        node : Link
            Link node

        Returns
        -------
        str
            Text content of link

        """
        # Use extract_text to get all nested text content
        return extract_text(node.content, joiner="")


class GenerateTocTransform(NodeTransformer):
    """Generate a table of contents from document headings.

    This transform extracts headings from the document and generates a
    nested list representing the table of contents. The TOC can be placed
    at the top or bottom of the document.

    Parameters
    ----------
    title : str, default = "Table of Contents"
        Title for the TOC section
    max_depth : int, default = 3
        Maximum heading level to include (1-6)
    position : {"top", "bottom"}, default = "top"
        Position to insert the TOC
    add_links : bool, default = True
        Whether to create links to headings (requires heading IDs)
    separator : str, default = "-"
        Separator for generating heading IDs when not present
    set_ids_if_missing : bool, default = False
        If True, inject generated IDs into heading metadata when missing.
        This ensures renderers create anchors matching the TOC links.
        If False (default), IDs are only used for TOC links.

    Examples
    --------
    Basic usage:

        >>> transform = GenerateTocTransform()
        >>> doc_with_toc = transform.transform(document)

    Custom depth and position:

        >>> transform = GenerateTocTransform(
        ...     title="Contents",
        ...     max_depth=2,
        ...     position="bottom"
        ... )
        >>> doc_with_toc = transform.transform(document)

    Inject IDs into headings:

        >>> transform = GenerateTocTransform(set_ids_if_missing=True)
        >>> doc_with_toc = transform.transform(document)
        >>> # Headings now have 'id' in metadata for renderer anchors

    Notes
    -----
    This transform works best when combined with AddHeadingIdsTransform,
    which generates unique IDs for headings that can be used for navigation.
    If headings don't have IDs, the transform will generate slugified IDs
    on-the-fly for link targets.

    **ID Injection**: With ``set_ids_if_missing=True``, generated IDs are
    injected into heading metadata so renderers can create matching anchors.
    This is recommended when not using AddHeadingIdsTransform. Alternatively,
    run AddHeadingIdsTransform before GenerateTocTransform to ensure all
    headings have IDs upfront.

    """

    def __init__(
        self,
        title: str = "Table of Contents",
        max_depth: int = 3,
        position: str = "top",
        add_links: bool = True,
        separator: str = "-",
        set_ids_if_missing: bool = False,
    ):
        """Initialize with TOC generation options.

        Parameters
        ----------
        title : str
            TOC section title
        max_depth : int
            Maximum heading level (1-6)
        position : str
            Position for TOC ("top" or "bottom")
        add_links : bool
            Whether to generate links
        separator : str
            Separator for ID generation
        set_ids_if_missing : bool
            Inject generated IDs into heading metadata

        Raises
        ------
        ValueError
            If max_depth is not between 1 and 6, or position is invalid

        """
        if not 1 <= max_depth <= 6:
            raise ValueError(f"max_depth must be 1-6, got {max_depth}")
        if position not in ("top", "bottom"):
            raise ValueError(f"position must be 'top' or 'bottom', got {position!r}")

        self.title = title
        self.max_depth = max_depth
        self.position = position
        self.add_links = add_links
        self.separator = separator
        self.set_ids_if_missing = set_ids_if_missing
        self._headings: list[tuple[int, str, str | None]] = []  # (level, text, id)
        self._id_counts: dict[str, int] = {}
        self._heading_id_map: dict[int, str] = {}  # heading index -> generated ID

    def visit_document(self, node: Document) -> Document:
        """Generate TOC and add to document.

        Parameters
        ----------
        node : Document
            Document to process

        Returns
        -------
        Document
            Document with TOC added

        """
        # Reset heading collection
        self._headings = []
        self._id_counts = {}
        self._heading_id_map = {}

        # First pass: collect headings and track which need IDs injected
        self._collect_headings(node)

        # If no headings found, return unchanged
        if not self._headings:
            return node

        # Second pass: if set_ids_if_missing is True, inject IDs into headings
        if self.set_ids_if_missing and self._heading_id_map:
            # Create a new document with updated headings

            node = cast(Document, self._inject_heading_ids(node))

        # Generate TOC structure
        toc_nodes = self._generate_toc()

        # Build new document with TOC inserted
        new_children = list(node.children)
        if self.position == "top":
            new_children = toc_nodes + new_children
        else:  # bottom
            new_children = new_children + toc_nodes

        return Document(
            children=self._transform_children(new_children),
            metadata=node.metadata,
            source_location=node.source_location,
        )

    def _collect_headings(self, node: Node) -> None:
        """Recursively collect headings from AST.

        Parameters
        ----------
        node : Node
            Node to scan

        """
        # Check if this is a heading within our depth range
        if isinstance(node, Heading) and node.level <= self.max_depth:
            # Extract text from heading
            text = extract_text(node.content, joiner="")

            # Get or generate heading ID
            heading_id = node.metadata.get("id")
            if not heading_id and self.add_links:
                heading_id = self._generate_id(text)
                # Track heading index and generated ID for potential injection
                if self.set_ids_if_missing:
                    heading_idx = len(self._headings)
                    self._heading_id_map[heading_idx] = heading_id

            self._headings.append((node.level, text, heading_id))

        # Recurse into children
        if hasattr(node, "children") and isinstance(node.children, list):
            for child in node.children:
                self._collect_headings(child)

        # Recurse into content
        if hasattr(node, "content") and isinstance(node.content, list):
            for child in node.content:
                self._collect_headings(child)

    def _generate_id(self, text: str) -> str:
        """Generate a slugified ID from heading text.

        Parameters
        ----------
        text : str
            Heading text

        Returns
        -------
        str
            Slugified ID

        """
        # Generate slug using shared utility
        base_slug = slugify(text, separator=self.separator)

        # Make unique using shared utility
        slug = make_unique_slug(base_slug, self._id_counts, separator=self.separator)

        return slug

    def _inject_heading_ids(self, node: Node) -> Node:
        """Recursively inject generated IDs into headings.

        This method traverses the document and injects IDs from _heading_id_map
        into headings that were missing them during collection.

        Parameters
        ----------
        node : Node
            Node to process

        Returns
        -------
        Node
            Node with updated headings

        """
        # Track current heading index during traversal
        if not hasattr(self, "_current_heading_idx"):
            self._current_heading_idx = 0

        # If this is a heading within our depth range, inject ID if needed
        if isinstance(node, Heading) and node.level <= self.max_depth:
            current_idx = self._current_heading_idx
            self._current_heading_idx += 1

            # If this heading needs an ID injected
            if current_idx in self._heading_id_map:
                new_metadata = node.metadata.copy()
                new_metadata["id"] = self._heading_id_map[current_idx]
                return Heading(
                    level=node.level,
                    content=node.content,  # Don't recurse into content for headings
                    metadata=new_metadata,
                    source_location=node.source_location,
                )
            else:
                return node

        # Recurse into children
        if hasattr(node, "children") and isinstance(node.children, list):
            new_children = []
            for child in node.children:
                updated_child = self._inject_heading_ids(child)
                new_children.append(updated_child)

            # Rebuild node with updated children
            if isinstance(node, Document):
                return Document(children=new_children, metadata=node.metadata, source_location=node.source_location)
            elif isinstance(node, Paragraph):
                return node  # Paragraphs can't have Heading children
            else:
                # For other node types, try to update children if they have that attribute
                if hasattr(node, "children"):
                    return replace_node_children(node, new_children)

        return node

    def _generate_toc(self) -> list[Node]:
        """Generate TOC nodes from collected headings.

        Returns
        -------
        list of Node
            List of nodes representing the TOC

        Notes
        -----
        This method handles documents that don't start with level 1 headings
        by calculating the minimum heading level and using that as the base.
        For example, a document starting with H2 will use parent_level=1,
        allowing H2 headings to appear at the top level of the TOC.

        """
        toc_nodes: list[Node] = []

        # Add title heading
        if self.title:
            toc_nodes.append(Heading(level=2, content=[Text(content=self.title)]))

        # Build nested list structure
        if self._headings:
            # Calculate minimum heading level to handle documents not starting at H1
            min_level = min(level for level, _, _ in self._headings)
            # Start with parent_level = min_level - 1 so min_level headings appear at top level
            toc_list, _ = self._build_toc_list(0, min_level - 1)
            if toc_list:
                toc_nodes.append(toc_list)

        return toc_nodes

    def _build_toc_list(self, start_idx: int, parent_level: int) -> tuple[Node | None, int]:
        """Build a nested list for the TOC recursively.

        Parameters
        ----------
        start_idx : int
            Starting index in headings list
        parent_level : int
            Parent heading level

        Returns
        -------
        tuple of (Node or None, int)
            (List node or None if no items, next index to process)

        """
        items: list[ListItem] = []
        idx = start_idx

        while idx < len(self._headings):
            level, text, heading_id = self._headings[idx]

            # If we encounter a heading at or below parent level, stop
            if level <= parent_level:
                break

            # If this is a direct child of parent
            if level == parent_level + 1:
                # Create list item with link
                item_content: list[Node] = []

                # Create paragraph with link or plain text
                para_content: list[Node] = []
                if self.add_links and heading_id:
                    # Create link to heading
                    para_content.append(Link(url=f"#{heading_id}", content=[Text(content=text)]))
                else:
                    para_content.append(Text(content=text))

                item_content.append(Paragraph(content=para_content))

                # Check for nested items
                nested_list, next_idx = self._build_toc_list(idx + 1, level)
                if nested_list:
                    item_content.append(nested_list)
                    idx = next_idx
                else:
                    idx += 1

                items.append(ListItem(children=item_content))
            else:
                # Skip deeper nested items (they'll be handled recursively)
                idx += 1

        result_list = None if not items else List(ordered=False, items=items, tight=False)
        return (result_list, idx)


__all__ = [
    "RemoveImagesTransform",
    "RemoveNodesTransform",
    "HeadingOffsetTransform",
    "LinkRewriterTransform",
    "TextReplacerTransform",
    "AddHeadingIdsTransform",
    "RemoveBoilerplateTextTransform",
    "AddConversionTimestampTransform",
    "CalculateWordCountTransform",
    "AddAttachmentFootnotesTransform",
    "GenerateTocTransform",
]
