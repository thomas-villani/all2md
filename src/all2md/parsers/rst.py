#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/rst.py
"""reStructuredText to AST converter.

This module provides conversion from reStructuredText documents to AST representation
using the docutils parser. It enables bidirectional transformation by parsing RST
into the same AST structure used for other formats.

"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import IO, Any, Literal, Optional, Union

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Comment,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    HTMLBlock,
    HTMLInline,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
    Node,
    Paragraph,
    Strong,
    Subscript,
    Superscript,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
)
from all2md.constants import DEPS_RST
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.rst import RstParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


class RestructuredTextParser(BaseParser):
    r"""Convert reStructuredText to AST representation.

    This converter uses docutils to parse RST and builds an AST that
    matches the structure used throughout all2md, enabling bidirectional
    conversion and transformation pipelines.

    Parameters
    ----------
    options : RstParserOptions or None, default = None
        Parser configuration options

    Examples
    --------
    Basic parsing:

        >>> parser = RestructuredTextParser()
        >>> doc = parser.parse("Title\\n=====\\n\\nThis is **bold**.")

    With options:

        >>> options = RstParserOptions(parse_directives=True, strict_mode=False)
        >>> parser = RestructuredTextParser(options)
        >>> doc = parser.parse(rst_text)

    """

    def __init__(self, options: RstParserOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the RST parser with options and progress callback."""
        BaseParser._validate_options_type(options, RstParserOptions, "rst")
        options = options or RstParserOptions()
        super().__init__(options, progress_callback)
        self.options: RstParserOptions = options

    @requires_dependencies("rst", DEPS_RST)
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse RST input into AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            RST input to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw RST bytes
            - RST string

        Returns
        -------
        Document
            AST document node

        Raises
        ------
        DependencyError
            If docutils is not installed
        ParsingError
            If parsing fails

        """
        # Load RST content from various input types
        rst_content = self._load_text_content(input_data)

        from docutils.core import publish_doctree

        # Parse RST to docutils document tree
        try:
            settings_overrides = {
                "report_level": 5 if not self.options.strict_mode else 2,
                "halt_level": 5 if not self.options.strict_mode else 3,
                "warning_stream": None,
            }
            doctree = publish_doctree(rst_content, settings_overrides=settings_overrides)
        except Exception as e:
            raise ParsingError(f"Failed to parse RST: {e}") from e

        # Extract metadata
        metadata = self.extract_metadata(doctree)

        # Convert docutils tree to AST
        children = []
        for node in doctree.children:
            ast_node = self._process_node(node)
            if ast_node is not None:
                if isinstance(ast_node, list):
                    children.extend(ast_node)
                else:
                    children.append(ast_node)

        return Document(children=children, metadata=metadata.to_dict())

    def _process_node(self, node: Any) -> Node | list[Node] | None:  # noqa: C901
        """Process a docutils node into an AST node.

        Parameters
        ----------
        node : Any
            Docutils node to process

        Returns
        -------
        Node, list[Node], or None
            Resulting AST node(s)

        """
        from docutils import nodes as docutils_nodes

        node_type = type(node).__name__

        # Block-level nodes
        if isinstance(node, docutils_nodes.section):
            return self._process_section(node)
        elif isinstance(node, docutils_nodes.paragraph):
            return self._process_paragraph(node)
        elif isinstance(node, docutils_nodes.literal_block):
            return self._process_literal_block(node)
        elif isinstance(node, docutils_nodes.block_quote):
            return self._process_block_quote(node)
        elif isinstance(node, docutils_nodes.Admonition):
            # Handle admonitions (note, warning, tip, etc.)
            if self.options.parse_admonitions:
                return self._process_admonition(node)
            else:
                # Skip admonitions if parsing is disabled
                return None
        elif isinstance(node, docutils_nodes.bullet_list):
            return self._process_bullet_list(node)
        elif isinstance(node, docutils_nodes.enumerated_list):
            return self._process_enumerated_list(node)
        elif isinstance(node, docutils_nodes.definition_list):
            return self._process_definition_list(node)
        elif isinstance(node, docutils_nodes.table):
            return self._process_table(node)
        elif isinstance(node, docutils_nodes.transition):
            return ThematicBreak()
        elif isinstance(node, docutils_nodes.title):
            # Standalone title (not within a section) - treat as level 1 heading
            content = self._process_inline_nodes(node.children)
            return Heading(level=1, content=content)
        elif isinstance(node, docutils_nodes.subtitle):
            # Subtitle - treat as level 2 heading
            content = self._process_inline_nodes(node.children)
            return Heading(level=2, content=content)
        elif isinstance(node, docutils_nodes.system_message):
            # Skip system messages (warnings/errors)
            return None
        elif isinstance(node, docutils_nodes.comment):
            # Handle RST comments - either skip or preserve as Comment nodes
            if self.options.strip_comments:
                return None
            # Extract comment content and create Comment node
            comment_content = node.astext()
            return Comment(content=comment_content, metadata={"comment_type": "rst"})
        elif isinstance(node, docutils_nodes.docinfo):
            # Docinfo is handled by metadata extraction
            return None
        elif isinstance(node, docutils_nodes.footnote):
            # Footnote definition
            return self._process_footnote(node)
        elif isinstance(node, docutils_nodes.math_block):
            # Math block (displayed equation)
            return self._process_math_block(node)
        elif isinstance(node, docutils_nodes.raw):
            # Raw content (could be HTML or other formats)
            return self._process_raw_block(node)
        else:
            # Unknown node type - log and skip
            logger.debug(f"Skipping unknown docutils node type: {node_type}")
            return None

    def _process_section(self, node: Any) -> list[Node]:
        """Process a section node (heading + content).

        Parameters
        ----------
        node : docutils.nodes.section
            Section node to process

        Returns
        -------
        list[Node]
            List containing heading and section content

        """
        from docutils import nodes as docutils_nodes

        result: list[Node] = []

        # Find title and determine heading level
        level = 1

        # Calculate level by counting parent sections
        parent = node.parent
        while parent is not None:
            if isinstance(parent, docutils_nodes.section):
                level += 1
            parent = parent.parent

        # Process children
        for child in node.children:
            if isinstance(child, docutils_nodes.title):
                # Process title as heading
                content = self._process_inline_nodes(child.children)
                result.append(Heading(level=level, content=content))
            else:
                # Process other section content
                ast_node = self._process_node(child)
                if ast_node is not None:
                    if isinstance(ast_node, list):
                        result.extend(ast_node)
                    else:
                        result.append(ast_node)

        return result

    def _process_paragraph(self, node: Any) -> Paragraph:
        """Process a paragraph node.

        Parameters
        ----------
        node : docutils.nodes.paragraph
            Paragraph node to process

        Returns
        -------
        Paragraph
            Paragraph AST node

        """
        content = self._process_inline_nodes(node.children)
        return Paragraph(content=content)

    def _process_literal_block(self, node: Any) -> CodeBlock:
        """Process a literal block (code block).

        Parameters
        ----------
        node : docutils.nodes.literal_block
            Literal block node to process

        Returns
        -------
        CodeBlock
            Code block AST node

        """
        content = node.astext()

        # Try to extract language from classes or attributes
        language = None

        # Check attributes dict - for code-block directives, classes = ['code', 'language']
        if hasattr(node, "get"):
            classes = node.get("classes", [])
            if classes:
                # If first class is 'code', use second class as language
                if classes[0] == "code" and len(classes) > 1:
                    language = classes[1]
                else:
                    # Otherwise first class is the language
                    language = classes[0]
                    # Remove 'code-' prefix if present
                    if language and language.startswith("code-"):
                        language = language[5:]

        # Fallback: check attributes dict
        if not language and hasattr(node, "attributes") and "classes" in node.attributes:
            classes = node.attributes["classes"]
            if classes:
                if classes[0] == "code" and len(classes) > 1:
                    language = classes[1]
                else:
                    language = classes[0]
                    if language and language.startswith("code-"):
                        language = language[5:]

        # Check 'language' attribute directly
        if not language and hasattr(node, "get"):
            language = node.get("language", None)

        return CodeBlock(content=content, language=language)

    def _process_block_quote(self, node: Any) -> BlockQuote:
        """Process a block quote node.

        Parameters
        ----------
        node : docutils.nodes.block_quote
            Block quote node to process

        Returns
        -------
        BlockQuote
            Block quote AST node

        """
        children = []
        for child in node.children:
            ast_node = self._process_node(child)
            if ast_node is not None:
                if isinstance(ast_node, list):
                    children.extend(ast_node)
                else:
                    children.append(ast_node)

        return BlockQuote(children=children)

    def _process_admonition(self, node: Any) -> BlockQuote:
        """Process an admonition node (note, warning, tip, etc.) as a BlockQuote with metadata.

        Admonitions in RST include: note, warning, tip, important, caution, danger, error,
        hint, attention, and custom admonitions with titles.

        Parameters
        ----------
        node : docutils.nodes.Admonition
            Admonition node to process

        Returns
        -------
        BlockQuote
            Block quote AST node with admonition type in metadata

        """
        from docutils import nodes as docutils_nodes

        admonition_type = node.tagname  # 'note', 'warning', 'tip', etc.
        children = []

        # Check if this is a custom admonition with a title
        custom_title = None
        for child in node.children:
            if isinstance(child, docutils_nodes.title):
                # Custom admonition - extract title and store in metadata
                custom_title = child.astext()
            else:
                # Process content nodes
                ast_node = self._process_node(child)
                if ast_node is not None:
                    if isinstance(ast_node, list):
                        children.extend(ast_node)
                    else:
                        children.append(ast_node)

        # Create BlockQuote with metadata indicating admonition type
        metadata = {
            "admonition_type": admonition_type,
            "source_format": "rst",
        }

        # Add custom title to metadata if present
        if custom_title:
            metadata["admonition_title"] = custom_title

        return BlockQuote(children=children, metadata=metadata)

    def _process_bullet_list(self, node: Any) -> List:
        """Process a bullet list node.

        Parameters
        ----------
        node : docutils.nodes.bullet_list
            Bullet list node to process

        Returns
        -------
        List
            List AST node (unordered)

        """
        from docutils import nodes as docutils_nodes

        items = []
        for child in node.children:
            if isinstance(child, docutils_nodes.list_item):
                items.append(self._process_list_item(child))

        return List(ordered=False, items=items, start=1, tight=True)

    def _process_enumerated_list(self, node: Any) -> List:
        """Process an enumerated list node.

        Parameters
        ----------
        node : docutils.nodes.enumerated_list
            Enumerated list node to process

        Returns
        -------
        List
            List AST node (ordered)

        """
        from docutils import nodes as docutils_nodes

        items = []
        start = 1

        # Try to get start number from attributes
        if hasattr(node, "attributes"):
            if "start" in node.attributes:
                start = int(node.attributes["start"])

        for child in node.children:
            if isinstance(child, docutils_nodes.list_item):
                items.append(self._process_list_item(child))

        return List(ordered=True, items=items, start=start, tight=True)

    def _process_list_item(self, node: Any) -> ListItem:
        """Process a list item node.

        Parameters
        ----------
        node : docutils.nodes.list_item
            List item node to process

        Returns
        -------
        ListItem
            List item AST node

        """
        children = []
        for child in node.children:
            ast_node = self._process_node(child)
            if ast_node is not None:
                if isinstance(ast_node, list):
                    children.extend(ast_node)
                else:
                    children.append(ast_node)

        return ListItem(children=children)

    def _process_definition_list(self, node: Any) -> DefinitionList:
        """Process a definition list node.

        Parameters
        ----------
        node : docutils.nodes.definition_list
            Definition list node to process

        Returns
        -------
        DefinitionList
            Definition list AST node

        """
        from docutils import nodes as docutils_nodes

        items = []

        for child in node.children:
            if isinstance(child, docutils_nodes.definition_list_item):
                # Extract term and definitions
                term = None
                descriptions = []

                for subchild in child.children:
                    if isinstance(subchild, docutils_nodes.term):
                        content = self._process_inline_nodes(subchild.children)
                        term = DefinitionTerm(content=content)
                    elif isinstance(subchild, docutils_nodes.definition):
                        # Process definition content
                        def_children = []
                        for def_node in subchild.children:
                            ast_node = self._process_node(def_node)
                            if ast_node is not None:
                                if isinstance(ast_node, list):
                                    def_children.extend(ast_node)
                                else:
                                    def_children.append(ast_node)
                        descriptions.append(DefinitionDescription(content=def_children))

                if term is not None:
                    items.append((term, descriptions))

        return DefinitionList(items=items)

    def _process_table(self, node: Any) -> Table:
        """Process a table node.

        Parameters
        ----------
        node : docutils.nodes.table
            Table node to process

        Returns
        -------
        Table
            Table AST node

        """
        from docutils import nodes as docutils_nodes

        header = None
        rows = []
        alignments: list[Literal["left", "center", "right"] | None] = []

        # Find tgroup which contains table structure
        tgroup = None
        for child in node.children:
            if isinstance(child, docutils_nodes.tgroup):
                tgroup = child
                break

        if tgroup is None:
            return Table(header=None, rows=[], alignments=[])

        # Process thead (header) and tbody (body)
        for child in tgroup.children:
            if isinstance(child, docutils_nodes.thead):
                # Process header row
                for row_node in child.children:
                    if isinstance(row_node, docutils_nodes.row):
                        cells = self._process_table_row_cells(row_node)
                        header = TableRow(cells=cells, is_header=True)
                        break
            elif isinstance(child, docutils_nodes.tbody):
                # Process body rows
                for row_node in child.children:
                    if isinstance(row_node, docutils_nodes.row):
                        cells = self._process_table_row_cells(row_node)
                        rows.append(TableRow(cells=cells, is_header=False))

        return Table(header=header, rows=rows, alignments=alignments)

    def _process_table_row_cells(self, row_node: Any) -> list[TableCell]:
        """Process table row cells.

        Parameters
        ----------
        row_node : docutils.nodes.row
            Table row node

        Returns
        -------
        list[TableCell]
            List of table cell nodes

        """
        from docutils import nodes as docutils_nodes

        cells = []

        for cell_node in row_node.children:
            if isinstance(cell_node, docutils_nodes.entry):
                # Process cell content
                content = []
                for child in cell_node.children:
                    if isinstance(child, docutils_nodes.paragraph):
                        # For table cells, extract inline content from paragraphs
                        content.extend(self._process_inline_nodes(child.children))
                    else:
                        # Text nodes directly in cell
                        inline_nodes = self._process_inline_nodes([child])
                        content.extend(inline_nodes)

                cells.append(TableCell(content=content))

        return cells

    def _process_inline_nodes(self, nodes: list[Any]) -> list[Node]:
        """Process a list of inline docutils nodes.

        Parameters
        ----------
        nodes : list[Any]
            List of docutils inline nodes

        Returns
        -------
        list[Node]
            List of AST inline nodes

        """
        result = []

        for node in nodes:
            inline_node = self._process_inline_node(node)
            if inline_node is not None:
                if isinstance(inline_node, list):
                    result.extend(inline_node)
                else:
                    result.append(inline_node)

        return result

    def _process_inline_node(self, node: Any) -> Node | list[Node] | None:
        """Process a single inline docutils node.

        Parameters
        ----------
        node : Any
            Docutils inline node

        Returns
        -------
        Node, list[Node], or None
            AST inline node(s)

        """
        from docutils import nodes as docutils_nodes

        if isinstance(node, docutils_nodes.Text):
            return Text(content=str(node))
        elif isinstance(node, docutils_nodes.emphasis):
            content = self._process_inline_nodes(node.children)
            return Emphasis(content=content)
        elif isinstance(node, docutils_nodes.strong):
            content = self._process_inline_nodes(node.children)
            return Strong(content=content)
        elif isinstance(node, docutils_nodes.literal):
            return Code(content=node.astext())
        elif isinstance(node, docutils_nodes.reference):
            # Link node
            url = node.get("refuri", "")
            content = self._process_inline_nodes(node.children)
            return Link(url=url, content=content)
        elif isinstance(node, docutils_nodes.image):
            # Image node
            url = node.get("uri", "")
            alt_text = node.get("alt", "")
            return Image(url=url, alt_text=alt_text)
        elif hasattr(docutils_nodes, "line_break") and isinstance(node, docutils_nodes.line_break):
            return LineBreak(soft=False)
        elif isinstance(node, docutils_nodes.footnote_reference):
            # Footnote reference
            return self._process_footnote_reference(node)
        elif isinstance(node, docutils_nodes.math):
            # Inline math
            return self._process_math_inline(node)
        elif isinstance(node, docutils_nodes.raw):
            # Raw inline content (could be HTML)
            return self._process_raw_inline(node)
        elif isinstance(node, docutils_nodes.superscript):
            # Superscript
            content = self._process_inline_nodes(node.children)
            return Superscript(content=content)
        elif isinstance(node, docutils_nodes.subscript):
            # Subscript
            content = self._process_inline_nodes(node.children)
            return Subscript(content=content)
        else:
            # Unknown inline node - extract text if possible
            if hasattr(node, "astext"):
                text = node.astext()
                if text:
                    return Text(content=text)
            return None

    def _process_footnote(self, node: Any) -> FootnoteDefinition | None:
        """Process a footnote definition.

        Parameters
        ----------
        node : docutils.nodes.footnote
            Footnote node to process

        Returns
        -------
        FootnoteDefinition or None
            Footnote definition AST node

        """
        # Extract footnote identifier
        identifier = None
        if hasattr(node, "get"):
            # Try to get footnote IDs
            ids = node.get("ids", [])
            if ids:
                identifier = ids[0]
            # Also check names attribute
            if not identifier:
                names = node.get("names", [])
                if names:
                    identifier = names[0]

        if not identifier:
            # Fallback to auto-numbering
            identifier = "footnote"

        # Process footnote content
        content = []
        for child in node.children:
            # Skip the label node (first child)
            if hasattr(child, "tagname") and child.tagname == "label":
                continue

            ast_node = self._process_node(child)
            if ast_node is not None:
                if isinstance(ast_node, list):
                    content.extend(ast_node)
                else:
                    content.append(ast_node)

        return FootnoteDefinition(identifier=identifier, content=content)

    def _process_footnote_reference(self, node: Any) -> FootnoteReference:
        """Process a footnote reference.

        Parameters
        ----------
        node : docutils.nodes.footnote_reference
            Footnote reference node

        Returns
        -------
        FootnoteReference
            Footnote reference AST node

        """
        # Extract identifier from refid or refname
        identifier = node.get("refid") or node.get("refname") or "footnote"
        return FootnoteReference(identifier=identifier)

    def _process_math_block(self, node: Any) -> MathBlock:
        """Process a math block (displayed equation).

        Parameters
        ----------
        node : docutils.nodes.math_block
            Math block node

        Returns
        -------
        MathBlock
            Math block AST node

        """
        content = node.astext()
        # RST math is typically LaTeX
        return MathBlock(content=content, notation="latex")

    def _process_math_inline(self, node: Any) -> MathInline:
        """Process inline math.

        Parameters
        ----------
        node : docutils.nodes.math
            Inline math node

        Returns
        -------
        MathInline
            Inline math AST node

        """
        content = node.astext()
        # RST math is typically LaTeX
        return MathInline(content=content, notation="latex")

    def _process_raw_block(self, node: Any) -> HTMLBlock | None:
        """Process raw block content.

        Parameters
        ----------
        node : docutils.nodes.raw
            Raw block node

        Returns
        -------
        HTMLBlock or None
            HTML block if format is html, None otherwise

        """
        # Check format attribute
        format_attr = node.get("format", "").lower()

        # Only process HTML raw blocks
        if "html" in format_attr:
            content = node.astext()
            return HTMLBlock(content=content)

        # For other formats, skip
        return None

    def _process_raw_inline(self, node: Any) -> HTMLInline | None:
        """Process raw inline content.

        Parameters
        ----------
        node : docutils.nodes.raw
            Raw inline node

        Returns
        -------
        HTMLInline or None
            HTML inline if format is html, None otherwise

        """
        # Check format attribute
        format_attr = node.get("format", "").lower()

        # Only process HTML raw content
        if "html" in format_attr:
            content = node.astext()
            return HTMLInline(content=content)

        # For other formats, skip
        return None

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from docutils document.

        Parameters
        ----------
        document : docutils.nodes.document
            Parsed docutils document

        Returns
        -------
        DocumentMetadata
            Extracted metadata from docinfo if present

        Notes
        -----
        RST documents can have docinfo blocks that contain metadata fields.
        This method extracts those fields into DocumentMetadata.

        """
        from docutils import nodes as docutils_nodes

        metadata = DocumentMetadata()

        # Look for docinfo node in document children
        for child in document.children:
            if isinstance(child, docutils_nodes.docinfo):
                # Process docinfo fields
                for field in child.children:
                    if isinstance(field, docutils_nodes.author):
                        metadata.author = field.astext()
                    elif isinstance(field, docutils_nodes.date):
                        metadata.creation_date = field.astext()
                    elif isinstance(field, docutils_nodes.version):
                        metadata.custom["version"] = field.astext()
                    elif isinstance(field, docutils_nodes.field):
                        # Custom field
                        field_name = None
                        field_body = None
                        for subfield in field.children:
                            if isinstance(subfield, docutils_nodes.field_name):
                                field_name = subfield.astext()
                            elif isinstance(subfield, docutils_nodes.field_body):
                                field_body = subfield.astext()
                        if field_name and field_body:
                            metadata.custom[field_name.lower()] = field_body

        # Try to extract title from first section or standalone title
        for child in document.children:
            if isinstance(child, docutils_nodes.section):
                for subchild in child.children:
                    if isinstance(subchild, docutils_nodes.title):
                        metadata.title = subchild.astext()
                        break
                break
            elif isinstance(child, docutils_nodes.title):
                # Standalone title
                metadata.title = child.astext()
                break

        return metadata


# Converter metadata for registry auto-discovery
CONVERTER_METADATA = ConverterMetadata(
    format_name="rst",
    extensions=[".rst", ".rest"],
    mime_types=["text/x-rst", "text/prs.fallenstein.rst"],
    magic_bytes=[],
    parser_class=RestructuredTextParser,
    renderer_class="all2md.renderers.rst.RestructuredTextRenderer",
    renders_as_string=True,
    parser_required_packages=[("docutils", "docutils", ">=0.18")],
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="RST parsing requires 'docutils'. Install with: pip install 'all2md[rst]'",
    parser_options_class=RstParserOptions,
    renderer_options_class="all2md.options.rst.RstRendererOptions",
    description="Parse reStructuredText to AST and render AST to reStructuredText",
    priority=10,
)
