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

import re
from datetime import datetime, timezone

from all2md.ast.nodes import (
    Document,
    FootnoteDefinition,
    Heading,
    Image,
    Link,
    Node,
    Paragraph,
    Text,
)
from all2md.ast.transforms import NodeTransformer
from all2md.ast.utils import extract_text
from all2md.constants import DEFAULT_BOILERPLATE_PATTERNS
from all2md.transforms.hooks import HookManager
from all2md.utils.attachments import sanitize_footnote_label


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
            If 'document' is in node_types (cannot remove root node)

        """
        # Validate that 'document' is not in node_types
        if 'document' in node_types:
            raise ValueError(
                "Cannot remove 'document' node type - this would break the pipeline. "
                "Consider using specific child node types instead (e.g., 'heading', 'paragraph')."
            )

        self.node_types = set(node_types)
        # Use centralized node type mapping from HookManager
        self._hook_manager = HookManager()

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
        # Get node type string using centralized mapping
        node_type = self._hook_manager.get_node_type(node)

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
            source_location=node.source_location
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
        from all2md.utils.security import validate_user_regex_pattern

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
        from all2md.constants import MAX_URL_LENGTH

        # Limit URL length to prevent excessive processing
        url_to_process = node.url[:MAX_URL_LENGTH] if len(node.url) > MAX_URL_LENGTH else node.url

        # Apply regex substitution
        new_url = self.pattern.sub(self.replacement, url_to_process)

        return Link(
            url=new_url,
            content=self._transform_children(node.content),
            title=node.title,
            metadata=node.metadata.copy(),
            source_location=node.source_location
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

        return Text(
            content=new_content,
            metadata=node.metadata.copy(),
            source_location=node.source_location
        )


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

        # Generate slug
        slug = self._slugify(text)

        # Handle duplicates
        if slug in self._id_counts:
            self._id_counts[slug] += 1
            slug = f"{slug}{self.separator}{self._id_counts[slug]}"
        else:
            self._id_counts[slug] = 1

        # Add prefix
        final_id = f"{self.id_prefix}{slug}" if self.id_prefix else slug

        # Add to metadata
        new_metadata = node.metadata.copy()
        new_metadata['id'] = final_id

        return Heading(
            level=node.level,
            content=self._transform_children(node.content),
            metadata=new_metadata,
            source_location=node.source_location
        )

    def _slugify(self, text: str) -> str:
        """Convert text to URL-safe slug.

        Parameters
        ----------
        text : str
            Text to slugify

        Returns
        -------
        str
            Slugified text

        """
        # Lowercase
        text = text.lower()

        # Replace spaces and special chars with separator
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_]+', self.separator, text)

        # Remove leading/trailing separators
        text = text.strip(self.separator)

        return text or 'heading'  # Fallback if empty


class RemoveBoilerplateTextTransform(NodeTransformer):
    """Remove paragraphs matching common boilerplate patterns.

    This transform removes paragraphs whose text matches predefined
    patterns like "CONFIDENTIAL", "Page X of Y", etc. Useful for
    cleaning up corporate documents and reports.

    Parameters
    ----------
    patterns : list[str], optional
        List of regex patterns to match (default: common boilerplate)

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

    Custom patterns:

        >>> transform = RemoveBoilerplateTextTransform(
        ...     patterns=[r"^DRAFT$", r"^INTERNAL$"]
        ... )
        >>> cleaned_doc = transform.transform(document)

    Notes
    -----
    For security reasons, this transform validates user-supplied regex patterns
    to prevent ReDoS attacks. Default patterns are pre-validated and trusted.
    Patterns with nested quantifiers or excessive backtracking potential are
    rejected. See `validate_user_regex_pattern()` for details.

    """

    def __init__(self, patterns: list[str] | None = None):
        """Initialize with patterns.

        Parameters
        ----------
        patterns : list[str] or None
            Regex patterns to match (None uses defaults)

        Raises
        ------
        SecurityError
            If any user-supplied pattern contains dangerous constructs

        """
        from all2md.utils.security import validate_user_regex_pattern

        self.patterns = patterns if patterns is not None else DEFAULT_BOILERPLATE_PATTERNS

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
        from all2md.constants import MAX_TEXT_LENGTH_FOR_REGEX

        # Extract text from paragraph (no joiner to match exact text)
        text = extract_text(node.content, joiner="")

        # Limit text length to prevent excessive regex processing
        text_stripped = text.strip()
        if len(text_stripped) > MAX_TEXT_LENGTH_FOR_REGEX:
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
    format : str, default = "iso"
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
        Only applies when format="iso". Ignored for other formats.

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

        >>> transform = AddConversionTimestampTransform(format="unix")
        >>> new_doc = transform.transform(document)
        >>> # metadata['conversion_timestamp'] = "1735732800"

    Custom strftime format:

        >>> transform = AddConversionTimestampTransform(
        ...     field_name="converted_at",
        ...     format="%Y-%m-%d %H:%M:%S UTC"
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
        self,
        field_name: str = "conversion_timestamp",
        format: str = "iso",
        timespec: str = "seconds"
    ):
        """Initialize with field name, format, and time precision.

        Parameters
        ----------
        field_name : str
            Metadata field name
        format : str
            Timestamp format
        timespec : str
            Time precision for ISO format (default: "seconds")

        """
        self.field_name = field_name
        self.format = format
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

        if self.format == "iso":
            timestamp = now.isoformat(timespec=self.timespec)
        elif self.format == "unix":
            timestamp = str(int(now.timestamp()))
        else:
            # Custom strftime format
            timestamp = now.strftime(self.format)

        # Add to metadata
        new_metadata = node.metadata.copy()
        new_metadata[self.field_name] = timestamp

        return Document(
            children=self._transform_children(node.children),
            metadata=new_metadata,
            source_location=node.source_location
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
            source_location=node.source_location
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
        add_definitions_for_links: bool = True
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

        # If no footnotes found, return unchanged
        if not self._footnote_refs:
            return node

        # Create footnote definitions
        new_children = list(node.children)

        # Add section heading if specified
        if self.section_title:
            new_children.append(Heading(
                level=2,
                content=[Text(content=self.section_title)]
            ))

        # Add footnote definitions
        for label, source_info in sorted(self._footnote_refs.items()):
            definition = FootnoteDefinition(
                identifier=label,
                content=[Paragraph(content=[Text(content=f"Source: {source_info}")])]
            )
            new_children.append(definition)

        return Document(
            children=self._transform_children(new_children),
            metadata=node.metadata,
            source_location=node.source_location
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
            source_text = node.alt_text or node.metadata.get('original_filename') or "attachment"
            base_label = sanitize_footnote_label(source_text)

            if base_label:
                # Handle duplicate labels with numeric suffix
                if base_label in self._label_counts:
                    self._label_counts[base_label] += 1
                    label = f"{base_label}-{self._label_counts[base_label]}"
                else:
                    self._label_counts[base_label] = 1
                    label = base_label

                self._footnote_refs[label] = source_text

        if self.add_definitions_for_links and isinstance(node, Link) and not node.url:
            # Extract label from link content or metadata
            link_text = self._get_link_text(node)
            source_text = link_text or node.metadata.get('original_filename') or "attachment"
            base_label = sanitize_footnote_label(source_text)

            if base_label:
                # Handle duplicate labels with numeric suffix
                if base_label in self._label_counts:
                    self._label_counts[base_label] += 1
                    label = f"{base_label}-{self._label_counts[base_label]}"
                else:
                    self._label_counts[base_label] = 1
                    label = base_label

                self._footnote_refs[label] = source_text

        # Recurse into children
        if hasattr(node, 'children') and isinstance(node.children, list):
            for child in node.children:
                self._collect_footnote_refs(child)

        # Recurse into content
        if hasattr(node, 'content') and isinstance(node.content, list):
            for child in node.content:
                self._collect_footnote_refs(child)

    def _get_link_text(self, node: Link) -> str:
        """Extract text content from link node.

        Parameters
        ----------
        node : Link
            Link node

        Returns
        -------
        str
            Text content of link

        """
        text_parts = []
        if node.content:
            for child in node.content:
                if isinstance(child, Text):
                    text_parts.append(child.content)
        return ' '.join(text_parts)


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

    Notes
    -----
    This transform works best when combined with AddHeadingIdsTransform,
    which generates unique IDs for headings that can be used for navigation.
    If headings don't have IDs, the transform will generate slugified IDs
    on-the-fly for link targets.

    """

    def __init__(
        self,
        title: str = "Table of Contents",
        max_depth: int = 3,
        position: str = "top",
        add_links: bool = True,
        separator: str = "-"
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
        self._headings: list[tuple[int, str, str | None]] = []  # (level, text, id)
        self._id_counts: dict[str, int] = {}

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

        # Collect headings from document
        self._collect_headings(node)

        # If no headings found, return unchanged
        if not self._headings:
            return node

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
            source_location=node.source_location
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
            heading_id = node.metadata.get('id')
            if not heading_id and self.add_links:
                heading_id = self._generate_id(text)

            self._headings.append((node.level, text, heading_id))

        # Recurse into children
        if hasattr(node, 'children') and isinstance(node.children, list):
            for child in node.children:
                self._collect_headings(child)

        # Recurse into content
        if hasattr(node, 'content') and isinstance(node.content, list):
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
        # Lowercase
        slug = text.lower()

        # Replace spaces and special chars with separator
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', self.separator, slug)

        # Remove leading/trailing separators
        slug = slug.strip(self.separator)

        # Handle empty slugs
        if not slug:
            slug = 'heading'

        # Handle duplicates
        if slug in self._id_counts:
            self._id_counts[slug] += 1
            slug = f"{slug}{self.separator}{self._id_counts[slug]}"
        else:
            self._id_counts[slug] = 1

        return slug

    def _generate_toc(self) -> list[Node]:
        """Generate TOC nodes from collected headings.

        Returns
        -------
        list of Node
            List of nodes representing the TOC

        """
        toc_nodes: list[Node] = []

        # Add title heading
        if self.title:
            toc_nodes.append(Heading(
                level=2,
                content=[Text(content=self.title)]
            ))

        # Build nested list structure
        if self._headings:
            toc_list, _ = self._build_toc_list(0, 0)
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
        from all2md.ast.nodes import List as ListNode, ListItem as ListItemNode

        items: list[ListItemNode] = []
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
                    para_content.append(Link(
                        url=f"#{heading_id}",
                        content=[Text(content=text)]
                    ))
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

                items.append(ListItemNode(children=item_content))
            else:
                # Skip deeper nested items (they'll be handled recursively)
                idx += 1

        result_list = None if not items else ListNode(
            ordered=False,
            items=items,
            tight=False
        )
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
