#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/transforms/footnote_to_citation.py
"""Transform footnotes to citations for academic document processing.

This transformer scans FootnoteDefinition nodes for bibliographic content,
parses bibliographic information, and replaces FootnoteReference nodes
with Citation nodes while building a Bibliography.
"""

from __future__ import annotations

from typing import Any

from all2md.ast.nodes import (
    Bibliography,
    BibliographyEntry,
    Citation,
    Document,
    FootnoteDefinition,
    FootnoteReference,
    Node,
    Text,
    get_node_children,
    replace_node_children,
)
from all2md.ast.transforms import NodeTransformer
from all2md.utils.bibliography import (
    generate_citation_key,
    is_bibliographic_footnote,
    parse_bibliographic_text,
)


def _extract_text_from_nodes(nodes: list[Node]) -> str:
    """Extract plain text content from a list of nodes.

    Parameters
    ----------
    nodes : list of Node
        Nodes to extract text from

    Returns
    -------
    str
        Plain text content

    """
    parts: list[str] = []

    def visit(node: Node) -> None:
        if isinstance(node, Text):
            parts.append(node.content)
        for child in get_node_children(node):
            visit(child)

    for node in nodes:
        visit(node)

    return " ".join(parts)


class FootnoteToCitationTransformer(NodeTransformer):
    """Transform bibliographic footnotes to proper citations.

    This transformer analyzes footnote definitions to detect bibliographic
    content and converts matching footnotes to citation references with
    a proper bibliography.

    Parameters
    ----------
    confidence_threshold : float, default 0.3
        Minimum confidence score to treat footnote as bibliographic.
        Lower values are more inclusive, higher values more selective.
    preserve_non_bibliographic : bool, default True
        Keep non-bibliographic footnotes as-is. If False, all footnotes
        are converted to citations.
    bibliography_style : str, default "plain"
        BibTeX bibliography style to use.

    Examples
    --------
    >>> from all2md import to_ast
    >>> from all2md.transforms.footnote_to_citation import FootnoteToCitationTransformer
    >>> doc = to_ast("paper.docx")
    >>> transformer = FootnoteToCitationTransformer()
    >>> doc = transformer.transform(doc)

    """

    def __init__(
        self,
        confidence_threshold: float = 0.3,
        preserve_non_bibliographic: bool = True,
        bibliography_style: str = "plain",
    ) -> None:
        """Initialize the transformer.

        Parameters
        ----------
        confidence_threshold : float
            Minimum confidence to treat footnote as bibliographic
        preserve_non_bibliographic : bool
            Keep non-bibliographic footnotes as-is
        bibliography_style : str
            BibTeX style for the bibliography

        """
        super().__init__()
        self.confidence_threshold = confidence_threshold
        self.preserve_non_bibliographic = preserve_non_bibliographic
        self.bibliography_style = bibliography_style

        # Internal state
        self._footnote_map: dict[str, FootnoteDefinition] = {}
        self._citation_map: dict[str, BibliographyEntry] = {}
        self._existing_keys: set[str] = set()

    def transform(self, node: Node) -> Node:
        """Transform document, returning new document with citations.

        Parameters
        ----------
        node : Node
            Node to transform (must be a Document)

        Returns
        -------
        Node
            New document with citations and bibliography

        """
        if not isinstance(node, Document):
            return node
        document = node
        # Reset state
        self._footnote_map = {}
        self._citation_map = {}
        self._existing_keys = set()

        # Phase 1: Collect all footnote definitions
        self._collect_footnotes(document)

        # Phase 2: Analyze and convert bibliographic footnotes
        self._generate_bibliography_entries()

        # Phase 3: Transform document tree
        new_children = self._transform_children(list(document.children))

        # Phase 4: Remove converted footnote definitions from children
        new_children = [
            child
            for child in new_children
            if not (isinstance(child, FootnoteDefinition) and child.identifier in self._citation_map)
        ]

        # Phase 5: Add bibliography if entries exist
        if self._citation_map:
            bibliography = Bibliography(
                entries=list(self._citation_map.values()),
                style=self.bibliography_style,
            )
            new_children.append(bibliography)

        return Document(
            children=new_children,
            metadata=document.metadata,
            source_location=document.source_location,
        )

    def _collect_footnotes(self, document: Document) -> None:
        """Collect all FootnoteDefinition nodes from document.

        Parameters
        ----------
        document : Document
            Document to scan

        """
        for child in document.children:
            if isinstance(child, FootnoteDefinition):
                self._footnote_map[child.identifier] = child

    def _generate_bibliography_entries(self) -> None:
        """Analyze footnotes and generate bibliography entries."""
        for identifier, footnote in self._footnote_map.items():
            # Extract text from footnote content
            text = _extract_text_from_nodes(footnote.content)

            # Check if bibliographic
            if not is_bibliographic_footnote(text):
                if self.preserve_non_bibliographic:
                    continue
                # If not preserving, treat as misc citation

            # Parse the bibliographic text
            ref = parse_bibliographic_text(text)

            # Check confidence threshold
            if ref.confidence < self.confidence_threshold:
                if self.preserve_non_bibliographic:
                    continue

            # Generate citation key
            key = generate_citation_key(ref, self._existing_keys)
            self._existing_keys.add(key)

            # Create bibliography entry
            entry = BibliographyEntry(
                key=key,
                entry_type=ref.entry_type,
                fields={
                    k: v
                    for k, v in [
                        ("author", " and ".join(ref.authors) if ref.authors else None),
                        ("title", ref.title if ref.title else None),
                        ("year", ref.year),
                        ("journal", ref.journal),
                        ("volume", ref.volume),
                        ("number", ref.issue),
                        ("pages", ref.pages),
                        ("publisher", ref.publisher),
                        ("doi", ref.doi),
                        ("url", ref.url),
                    ]
                    if v
                },
                raw_text=text,
                source_location=footnote.source_location,
            )

            self._citation_map[identifier] = entry

    def _transform_children(self, children: list[Node]) -> list[Node]:
        """Transform a list of child nodes.

        Parameters
        ----------
        children : list of Node
            Children to transform

        Returns
        -------
        list of Node
            Transformed children

        """
        return [self._transform_node(child) for child in children]

    def _transform_node(self, node: Node) -> Node:
        """Transform a single node, replacing footnote refs with citations.

        Parameters
        ----------
        node : Node
            Node to transform

        Returns
        -------
        Node
            Transformed node

        """
        if isinstance(node, FootnoteReference):
            if node.identifier in self._citation_map:
                entry = self._citation_map[node.identifier]
                return Citation(
                    keys=[entry.key],
                    metadata=node.metadata,
                    source_location=node.source_location,
                )
            # Keep as footnote reference if not converted
            return node

        # Recursively transform children
        children = get_node_children(node)
        if children:
            new_children = self._transform_children(children)
            return replace_node_children(node, new_children)

        return node

    def visit_document(self, node: Document) -> Any:
        """Visit Document node - use transform() instead."""
        return self.transform(node)
