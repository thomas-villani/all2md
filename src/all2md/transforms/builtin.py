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

"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

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


class RemoveImagesTransform(NodeTransformer):
    """Remove all Image nodes from the AST.

    This transform removes every Image node it encounters, useful for
    creating text-only versions of documents or reducing document size.

    Examples
    --------
    >>> transform = RemoveImagesTransform()
    >>> doc_without_images = transform.transform(document)

    """

    def visit_image(self, node: Image) -> None:
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

    # Mapping of node type strings to node classes
    NODE_TYPE_MAP = {
        'document': Document,
        'heading': Heading,
        'paragraph': Paragraph,
        'image': Image,
        'link': Link,
        'text': Text,
        # Add more as needed
    }

    def __init__(self, node_types: list[str]):
        """Initialize with list of node types to remove.

        Parameters
        ----------
        node_types : list[str]
            Node type names to remove

        """
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
        # Get node type string
        node_type = self._get_node_type_string(node)

        # Remove if it matches
        if node_type in self.node_types:
            return None

        # Otherwise continue normal traversal
        return super().transform(node)

    def _get_node_type_string(self, node: Node) -> str:
        """Get the type string for a node.

        Parameters
        ----------
        node : Node
            Node to get type for

        Returns
        -------
        str
            Node type string (e.g., 'image', 'heading')

        """
        # Reverse lookup in NODE_TYPE_MAP
        for type_str, node_class in self.NODE_TYPE_MAP.items():
            if isinstance(node, node_class):
                return type_str

        # Fallback: use class name in snake_case
        class_name = type(node).__name__
        return self._camel_to_snake(class_name)

    @staticmethod
    def _camel_to_snake(name: str) -> str:
        """Convert CamelCase to snake_case.

        Parameters
        ----------
        name : str
            CamelCase string

        Returns
        -------
        str
            snake_case string

        """
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


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
    """Rewrite link URLs using regex pattern matching.

    This transform allows flexible URL rewriting using regular expressions.
    Useful for converting relative links to absolute, updating base URLs,
    or modifying link schemes.

    Parameters
    ----------
    pattern : str
        Regex pattern to match in URLs
    replacement : str
        Replacement string (can include regex groups like \\1, \\2)

    Examples
    --------
    Convert relative links to absolute:

        >>> transform = LinkRewriterTransform(
        ...     pattern=r'^/docs/',
        ...     replacement='https://example.com/docs/'
        ... )
        >>> new_doc = transform.transform(document)

    """

    def __init__(self, pattern: str, replacement: str):
        """Initialize with pattern and replacement.

        Parameters
        ----------
        pattern : str
            Regex pattern
        replacement : str
            Replacement string

        """
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
        # Apply regex substitution
        new_url = self.pattern.sub(self.replacement, node.url)

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
        # Extract text from heading content
        text = self._extract_text_from_nodes(node.content)

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

    def _extract_text_from_nodes(self, nodes: list[Node]) -> str:
        """Extract plain text from a list of nodes.

        Parameters
        ----------
        nodes : list[Node]
            Nodes to extract text from

        Returns
        -------
        str
            Concatenated text

        """
        text_parts = []
        for node in nodes:
            if isinstance(node, Text):
                text_parts.append(node.content)
            elif hasattr(node, 'content') and isinstance(node.content, list):
                # Recursive for nested content (e.g., emphasis in heading)
                text_parts.append(self._extract_text_from_nodes(node.content))
        return ''.join(text_parts)

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

    """

    DEFAULT_PATTERNS = [
        r"^CONFIDENTIAL$",
        r"^Page \d+ of \d+$",
        r"^Internal Use Only$",
        r"^\[DRAFT\]$",
        r"^Copyright \d{4}",
        r"^Printed on \d{4}-\d{2}-\d{2}$"
    ]

    def __init__(self, patterns: list[str] | None = None):
        """Initialize with patterns.

        Parameters
        ----------
        patterns : list[str] or None
            Regex patterns to match (None uses defaults)

        """
        self.patterns = patterns if patterns is not None else self.DEFAULT_PATTERNS
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.patterns]

    def visit_paragraph(self, node: Paragraph) -> Paragraph | None:
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
        # Extract text from paragraph
        text = self._extract_text_from_nodes(node.content)

        # Check against patterns
        text_stripped = text.strip()
        for pattern in self._compiled:
            if pattern.match(text_stripped):
                return None  # Remove

        # Keep paragraph
        return super().visit_paragraph(node)

    def _extract_text_from_nodes(self, nodes: list[Node]) -> str:
        """Extract plain text from nodes.

        Parameters
        ----------
        nodes : list[Node]
            Nodes to extract from

        Returns
        -------
        str
            Concatenated text

        """
        text_parts = []
        for node in nodes:
            if isinstance(node, Text):
                text_parts.append(node.content)
            elif hasattr(node, 'content') and isinstance(node.content, list):
                text_parts.append(self._extract_text_from_nodes(node.content))
        return ''.join(text_parts)


class AddConversionTimestampTransform(NodeTransformer):
    """Add conversion timestamp to document metadata.

    This transform adds a timestamp to the document metadata indicating
    when the conversion occurred. Useful for tracking document versions
    and conversion history.

    Parameters
    ----------
    field_name : str, default = "conversion_timestamp"
        Metadata field name for the timestamp
    format : str, default = "iso"
        Timestamp format: "iso", "unix", or strftime format string

    Examples
    --------
    Add ISO timestamp:

        >>> transform = AddConversionTimestampTransform()
        >>> new_doc = transform.transform(document)
        >>> # metadata['conversion_timestamp'] = "2025-01-01T12:00:00.123456"

    Custom format:

        >>> transform = AddConversionTimestampTransform(
        ...     field_name="converted_at",
        ...     format="%Y-%m-%d %H:%M:%S"
        ... )
        >>> new_doc = transform.transform(document)

    """

    def __init__(self, field_name: str = "conversion_timestamp", format: str = "iso"):
        """Initialize with field name and format.

        Parameters
        ----------
        field_name : str
            Metadata field name
        format : str
            Timestamp format

        """
        self.field_name = field_name
        self.format = format

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
        # Generate timestamp
        now = datetime.now()

        if self.format == "iso":
            timestamp = now.isoformat()
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
        # Extract all text
        all_text = self._extract_all_text(node)

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

    def _extract_all_text(self, node: Node) -> str:
        """Recursively extract all text from a node.

        Parameters
        ----------
        node : Node
            Node to extract from

        Returns
        -------
        str
            All text concatenated

        """
        text_parts = []

        # If node is Text, get its content
        if isinstance(node, Text):
            text_parts.append(node.content)

        # If node has children list, recurse
        if hasattr(node, 'children') and isinstance(node.children, list):
            for child in node.children:
                text_parts.append(self._extract_all_text(child))

        # If node has content list (inline nodes), recurse
        if hasattr(node, 'content') and isinstance(node.content, list):
            for child in node.content:
                text_parts.append(self._extract_all_text(child))

        return ' '.join(text_parts)


class AddAttachmentFootnotesTransform(NodeTransformer):
    """Add footnote definitions for attachment references.

    When attachments are processed with alt_text_mode="footnote", they generate
    footnote-style references like ![image][^label] but no corresponding definitions.
    This transform scans the rendered markdown for such references and adds
    FootnoteDefinition nodes with source information.

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
    3. Creating FootnoteDefinition nodes with source information
    4. Appending definitions to the end of the document

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
            children=new_children,
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
            # Extract footnote label from rendered markdown
            # The label is derived from alt_text or filename
            label = self._extract_label(node.alt_text or "attachment")
            if label:
                self._footnote_refs[label] = node.alt_text or "Unknown source"

        if self.add_definitions_for_links and isinstance(node, Link) and not node.url:
            # Extract label from link content
            label = self._extract_label(self._get_link_text(node))
            if label:
                self._footnote_refs[label] = self._get_link_text(node) or "Unknown source"

        # Recurse into children
        if hasattr(node, 'children') and isinstance(node.children, list):
            for child in node.children:
                self._collect_footnote_refs(child)

        # Recurse into content
        if hasattr(node, 'content') and isinstance(node.content, list):
            for child in node.content:
                self._collect_footnote_refs(child)

    def _extract_label(self, text: str) -> str:
        """Extract footnote label from attachment name.

        Mimics the logic in utils.attachments._sanitize_footnote_label.

        Parameters
        ----------
        text : str
            Source text (filename or alt text)

        Returns
        -------
        str
            Sanitized label

        """
        if not text:
            return "attachment"

        # Remove file extension
        if '.' in text:
            base_name = text.rsplit('.', 1)[0]
        else:
            base_name = text

        # Sanitize: replace non-alphanumeric with underscore
        label = re.sub(r'[^a-zA-Z0-9_-]', '_', base_name.lower().strip())

        # Remove multiple underscores
        label = re.sub(r'_+', '_', label)

        # Remove leading/trailing underscores
        label = label.strip('_')

        return label or "attachment"

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
]
