#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/markdown.py
"""Markdown to AST converter.

This module provides conversion from Markdown documents to AST representation
using the mistune parser. It enables bidirectional transformation by parsing
markdown into the same AST structure used for other formats.

"""

from __future__ import annotations

from pathlib import Path
from typing import IO, Any, Literal, Optional, Union

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
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
    Strikethrough,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.options.markdown import MarkdownParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.security import sanitize_language_identifier


class MarkdownToAstConverter(BaseParser):
    r"""Convert Markdown to AST representation.

    This converter uses mistune to parse Markdown and builds an AST that
    matches the structure used throughout all2md, enabling bidirectional
    conversion and transformation pipelines.

    Parameters
    ----------
    options : MarkdownParserOptions or None, default = None
        Parser configuration options

    Examples
    --------
    Basic parsing:

        >>> converter = MarkdownToAstConverter()
        >>> doc = converter.parse("# Hello\\n\\nThis is **bold**.")

    With options:

        >>> options = MarkdownParserOptions(flavor="gfm", parse_tables=True)
        >>> converter = MarkdownToAstConverter(options)
        >>> doc = converter.parse(markdown_text)

    """

    def __init__(
        self,
        options: MarkdownParserOptions | None = None,
        progress_callback: Optional[ProgressCallback] = None
    ):
        """Initialize the Markdown parser with options and progress callback."""
        options = options or MarkdownParserOptions()
        super().__init__(options, progress_callback)
        self.options: MarkdownParserOptions = options
        self._footnote_definitions: dict[str, list[Node]] = {}

    @requires_dependencies("markdown", [("mistune", "mistune", ">=3.0.0")])
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse Markdown input into AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Markdown input to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw markdown bytes
            - Markdown string

        Returns
        -------
        Document
            AST document node

        """
        # Load markdown content from various input types
        markdown_content = self._load_markdown_content(input_data)

        # Reset parser state to prevent leakage across parse calls
        self._footnote_definitions = {}

        import mistune

        # Configure mistune plugins based on options
        plugins = []
        if self.options.parse_strikethrough:
            plugins.append('strikethrough')
        if self.options.parse_tables:
            plugins.append('table')
        if self.options.parse_footnotes:
            plugins.append('footnotes')
        if self.options.parse_task_lists:
            plugins.append('task_lists')
        if self.options.parse_math:
            plugins.append('math')

        # Create markdown parser with plugins
        markdown = mistune.create_markdown(
            plugins=plugins,
            renderer=None  # We'll process tokens ourselves
        )

        # Parse to tokens
        tokens, state = markdown.parse(markdown_content)

        # Convert tokens to AST (tokens should always be a list for our configuration)
        if isinstance(tokens, list):
            children = self._process_tokens(tokens)
        else:
            # Fallback for unexpected token format
            children = []

        # Add footnote definitions at end if present
        if self._footnote_definitions:
            for identifier, content in self._footnote_definitions.items():
                children.append(FootnoteDefinition(
                    identifier=identifier,
                    content=content
                ))

        # Extract and attach metadata
        metadata = self.extract_metadata(markdown_content)
        return Document(children=children, metadata=metadata.to_dict())

    @staticmethod
    def _load_markdown_content(input_data: Union[str, Path, IO[bytes], bytes]) -> str:
        """Load markdown content from various input types.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Input data to load

        Returns
        -------
        str
            Markdown content as string

        """
        if isinstance(input_data, bytes):
            return input_data.decode("utf-8", errors="replace")
        elif isinstance(input_data, Path):
            return input_data.read_text(encoding="utf-8")
        elif isinstance(input_data, str):
            # Could be file path or markdown content
            path = Path(input_data)
            if path.exists() and path.is_file():
                return path.read_text(encoding="utf-8")
            else:
                # Assume it's markdown content
                return input_data
        else:
            # File-like object (IO[bytes])
            input_data.seek(0)
            content_bytes = input_data.read()
            return content_bytes.decode("utf-8", errors="replace")

    def _process_tokens(self, tokens: list[dict[str, Any]]) -> list[Node]:
        """Process a list of mistune tokens into AST nodes.

        Parameters
        ----------
        tokens : list of dict
            Mistune token dictionaries

        Returns
        -------
        list of Node
            AST nodes

        """
        nodes: list[Node] = []

        for token in tokens:
            node = self._process_token(token)
            if node is not None:
                if isinstance(node, list):
                    nodes.extend(node)
                else:
                    nodes.append(node)

        return nodes

    def _process_token(self, token: dict[str, Any]) -> Node | list[Node] | None:
        """Process a single mistune token into an AST node.

        Parameters
        ----------
        token : dict
            Mistune token dictionary with 'type' and other fields

        Returns
        -------
        Node, list of Node, or None
            Resulting AST node(s)

        """
        token_type = token.get('type', '')

        # Block-level tokens
        if token_type == 'heading':
            return self._process_heading(token)
        elif token_type == 'paragraph':
            return self._process_paragraph(token)
        elif token_type == 'block_code':
            return self._process_code_block(token)
        elif token_type == 'block_quote':
            return self._process_block_quote(token)
        elif token_type == 'list':
            return self._process_list(token)
        elif token_type == 'table':
            return self._process_table(token)
        elif token_type == 'thematic_break':
            return ThematicBreak()
        elif token_type == 'block_html':
            return self._process_html_block(token)
        elif token_type == 'block_math':
            return self._process_math_block(token)
        elif token_type == 'footnote_def':
            self._process_footnote_def(token)
            return None
        elif token_type == 'def_list':
            return self._process_definition_list(token)

        # If we get here, it might be inline content or unknown
        return None

    def _process_heading(self, token: dict[str, Any]) -> Heading:
        """Process heading token.

        Parameters
        ----------
        token : dict
            Heading token with 'level' and 'children'

        Returns
        -------
        Heading
            Heading AST node

        """
        # Safely extract level with fallback to 1 if attrs or level missing
        attrs = token.get('attrs', {})
        level = attrs.get('level', 1) if isinstance(attrs, dict) else 1

        # Ensure level is valid (1-6)
        if not isinstance(level, int) or level < 1 or level > 6:
            level = 1

        children = token.get('children', [])
        content = self._process_inline_tokens(children) if isinstance(children, list) else []

        return Heading(level=level, content=content)

    def _process_paragraph(self, token: dict[str, Any]) -> Paragraph:
        """Process paragraph token.

        Parameters
        ----------
        token : dict
            Paragraph token with 'children'

        Returns
        -------
        Paragraph
            Paragraph AST node

        """
        children = token.get('children', [])
        content = self._process_inline_tokens(children)

        return Paragraph(content=content)

    def _process_code_block(self, token: dict[str, Any]) -> CodeBlock:
        """Process code block token.

        Parameters
        ----------
        token : dict
            Code block token with 'raw' and optional 'attrs'

        Returns
        -------
        CodeBlock
            Code block AST node

        """
        code_content = token.get('raw', '')
        attrs = token.get('attrs', {})
        info_string = attrs.get('info', None)

        # Initialize metadata for code block
        metadata: dict[str, Any] = {}
        language = None

        # Parse language and metadata from info string
        if info_string:
            info_string = info_string.strip()
            # Preserve full info string for renderers that support metadata
            metadata['info_string'] = info_string

            # Extract language (first word) and additional attributes
            parts = info_string.split(maxsplit=1)
            if parts:
                # Sanitize language identifier for security (prevent markdown injection)
                language = sanitize_language_identifier(parts[0])

                # Preserve additional metadata if present
                if len(parts) > 1:
                    metadata['info_attrs'] = parts[1]

        return CodeBlock(
            content=code_content,
            language=language if language else None,
            metadata=metadata
        )

    def _process_block_quote(self, token: dict[str, Any]) -> BlockQuote:
        """Process block quote token.

        Parameters
        ----------
        token : dict
            Block quote token with 'children'

        Returns
        -------
        BlockQuote
            Block quote AST node

        """
        children = token.get('children', [])
        content = self._process_tokens(children)

        return BlockQuote(children=content)

    def _process_list(self, token: dict[str, Any]) -> List:
        """Process list token.

        Parameters
        ----------
        token : dict
            List token with 'children', 'attrs' (ordered, start)

        Returns
        -------
        List
            List AST node

        """
        attrs = token.get('attrs', {})
        # Guard against attrs not being a dict
        if not isinstance(attrs, dict):
            attrs = {}

        ordered = attrs.get('ordered', False)
        start = attrs.get('start', 1)
        tight = attrs.get('tight', True)

        children = token.get('children', [])
        # Guard against children not being a list
        if not isinstance(children, list):
            children = []

        items = [self._process_list_item(child) for child in children if isinstance(child, dict)]

        return List(
            ordered=ordered,
            items=items,
            start=start,
            tight=tight
        )

    def _process_list_item(self, token: dict[str, Any]) -> ListItem:
        """Process list item token.

        Parameters
        ----------
        token : dict
            List item token with 'children'

        Returns
        -------
        ListItem
            List item AST node

        """
        children = token.get('children', [])
        content = self._process_tokens(children)

        # Check for task list checkbox
        task_status: Literal['checked', 'unchecked'] | None = None
        attrs = token.get('attrs', {})
        if 'checked' in attrs:
            task_status = 'checked' if attrs['checked'] else 'unchecked'

        return ListItem(children=content, task_status=task_status)

    def _process_table(self, token: dict[str, Any]) -> Table:
        """Process table token.

        Parameters
        ----------
        token : dict
            Table token with 'children' (rows)

        Returns
        -------
        Table
            Table AST node

        """
        children = token.get('children', [])

        header = None
        rows = []
        alignments = []

        for _i, row_token in enumerate(children):
            row_type = row_token.get('type', '')
            if row_type == 'table_head':
                # Process header row - cells are direct children of table_head
                head_children = row_token.get('children', [])
                if head_children:
                    # Process cells directly (no intermediate table_row)
                    cells = []
                    alignments_list = []
                    for cell_token in head_children:
                        if cell_token.get('type') == 'table_cell':
                            cell_children = cell_token.get('children', [])
                            content = self._process_inline_tokens(cell_children)

                            # Get alignment if specified
                            align = cell_token.get('attrs', {}).get('align', None)
                            alignments_list.append(align)

                            cells.append(TableCell(content=content, alignment=align))

                    header = TableRow(cells=cells, is_header=True)
                    alignments = alignments_list

            elif row_type == 'table_body':
                # Process body rows
                body_children = row_token.get('children', [])
                for body_row_token in body_children:
                    cells = self._process_table_row_cells(body_row_token)
                    rows.append(TableRow(cells=cells, is_header=False))

        return Table(header=header, rows=rows, alignments=alignments)

    def _process_table_row_cells(self, row_token: dict[str, Any]) -> list[TableCell]:
        """Process table row cells.

        Parameters
        ----------
        row_token : dict
            Table row token with 'children' (cells)

        Returns
        -------
        list of TableCell
            Table cell nodes

        """
        cells_tokens = row_token.get('children', [])
        cells = []

        for cell_token in cells_tokens:
            cell_children = cell_token.get('children', [])
            content = self._process_inline_tokens(cell_children)

            # Get alignment if specified
            attrs = cell_token.get('attrs', {})
            alignment = attrs.get('align', None)

            cells.append(TableCell(content=content, alignment=alignment))

        return cells

    def _process_html_block(self, token: dict[str, Any]) -> HTMLBlock | None:
        """Process HTML block token.

        Parameters
        ----------
        token : dict
            HTML block token with 'raw'

        Returns
        -------
        HTMLBlock or None
            HTML block node if preserve_html is True, None otherwise

        """
        if not self.options.preserve_html:
            return None

        content = token.get('raw', '')
        return HTMLBlock(content=content)

    def _process_math_block(self, token: dict[str, Any]) -> MathBlock:
        """Process math block token.

        Parameters
        ----------
        token : dict
            Math block token with 'raw'

        Returns
        -------
        MathBlock
            Math block AST node

        """
        content = token.get('raw', '')
        return MathBlock(content=content)

    def _process_footnote_def(self, token: dict[str, Any]) -> None:
        """Process footnote definition token.

        Stores definition for later addition to document.

        Parameters
        ----------
        token : dict
            Footnote definition token with 'attrs' (label) and 'children'

        Returns
        -------
        None

        """
        attrs = token.get('attrs', {})
        identifier = attrs.get('label', '')
        children = token.get('children', [])
        content = self._process_tokens(children)

        self._footnote_definitions[identifier] = content
        return None

    def _process_definition_list(self, token: dict[str, Any]) -> DefinitionList:
        """Process definition list token.

        Parameters
        ----------
        token : dict
            Definition list token with 'children'

        Returns
        -------
        DefinitionList
            Definition list AST node

        """
        children = token.get('children', [])
        items: list[tuple[DefinitionTerm, list[DefinitionDescription]]] = []

        current_term: DefinitionTerm | None = None
        current_descriptions: list[DefinitionDescription] = []

        for child in children:
            child_type = child.get('type', '')
            if child_type == 'def_list_head':
                # Save previous term/descriptions if any
                if current_term is not None:
                    items.append((current_term, current_descriptions))

                # Start new term
                term_children = child.get('children', [])
                term_content = self._process_inline_tokens(term_children)
                current_term = DefinitionTerm(content=term_content)
                current_descriptions = []

            elif child_type == 'def_list_content':
                # Add description
                desc_children = child.get('children', [])
                desc_content = self._process_tokens(desc_children)
                current_descriptions.append(
                    DefinitionDescription(content=desc_content)
                )

        # Add last term/descriptions
        if current_term is not None:
            items.append((current_term, current_descriptions))

        return DefinitionList(items=items)

    def _process_inline_tokens(self, tokens: list[dict[str, Any]]) -> list[Node]:
        """Process inline tokens.

        Parameters
        ----------
        tokens : list of dict
            Inline token dictionaries

        Returns
        -------
        list of Node
            Inline AST nodes

        """
        nodes: list[Node] = []

        for token in tokens:
            node = self._process_inline_token(token)
            if node is not None:
                if isinstance(node, list):
                    nodes.extend(node)
                else:
                    nodes.append(node)

        return nodes

    def _process_inline_token(self, token: dict[str, Any]) -> Node | list[Node] | None:
        """Process a single inline token.

        Parameters
        ----------
        token : dict
            Inline token dictionary

        Returns
        -------
        Node, list of Node, or None
            Inline AST node(s)

        """
        token_type = token.get('type', '')

        if token_type == 'text':
            content = token.get('raw', '')
            return Text(content=content)

        elif token_type == 'strong':
            children = token.get('children', [])
            content = self._process_inline_tokens(children)
            return Strong(content=content)

        elif token_type == 'emphasis':
            children = token.get('children', [])
            content = self._process_inline_tokens(children)
            return Emphasis(content=content)

        elif token_type == 'codespan':
            content = token.get('raw', '')
            return Code(content=content)

        elif token_type == 'link':
            attrs = token.get('attrs', {})
            if not isinstance(attrs, dict):
                attrs = {}
            url = attrs.get('url', '')
            title = attrs.get('title', None)
            children = token.get('children', [])
            if not isinstance(children, list):
                children = []
            content = self._process_inline_tokens(children)
            return Link(url=url, content=content, title=title)

        elif token_type == 'image':
            attrs = token.get('attrs', {})
            if not isinstance(attrs, dict):
                attrs = {}
            url = attrs.get('url', '')
            title = attrs.get('title', None)
            # Alt text is in children, not attrs
            children = token.get('children', [])
            alt_text = ''
            if isinstance(children, list) and children:
                # Extract text from children
                alt_parts = []
                for child in children:
                    if isinstance(child, dict) and child.get('type') == 'text':
                        alt_parts.append(child.get('raw', ''))
                alt_text = ''.join(alt_parts)
            return Image(url=url, alt_text=alt_text, title=title)

        elif token_type == 'linebreak':
            attrs = token.get('attrs', {})
            if not isinstance(attrs, dict):
                attrs = {}
            soft = attrs.get('soft', False)
            return LineBreak(soft=soft)

        elif token_type == 'strikethrough':
            children = token.get('children', [])
            content = self._process_inline_tokens(children)
            return Strikethrough(content=content)

        elif token_type == 'inline_html':
            if not self.options.preserve_html:
                return None
            content = token.get('raw', '')
            return HTMLInline(content=content)

        elif token_type == 'inline_math':
            content = token.get('raw', '')
            return MathInline(content=content)

        elif token_type == 'footnote_ref':
            attrs = token.get('attrs', {})
            if not isinstance(attrs, dict):
                attrs = {}
            identifier = attrs.get('label', '')
            return FootnoteReference(identifier=identifier)

        return None

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from Markdown document.

        Parameters
        ----------
        document : Any
            Parsed Markdown document (AST or raw text)

        Returns
        -------
        DocumentMetadata
            Empty metadata (Markdown doesn't have standard metadata)

        Notes
        -----
        Markdown files do not have a standardized metadata format in the
        core specification. Some flavors support YAML frontmatter, but that
        is handled separately in the parsing pipeline, not here.

        """
        return DocumentMetadata()


def markdown_to_ast(
    markdown_content: str,
    options: MarkdownParserOptions | None = None
) -> Document:
    r"""Convert Markdown string to AST.

    This is a convenience function that creates a converter and parses
    the markdown in one step.

    Parameters
    ----------
    markdown_content : str
        Markdown text to parse
    options : MarkdownParserOptions or None, default = None
        Parser configuration

    Returns
    -------
    Document
        AST document node

    Examples
    --------
    >>> from all2md.parsers.markdown import markdown_to_ast
    >>> doc = markdown_to_ast("# Hello\\n\\nWorld")
    >>> len(doc.children)
    2

    """
    converter = MarkdownToAstConverter(options)
    return converter.parse(markdown_content)


# Converter metadata for registry auto-discovery
CONVERTER_METADATA = ConverterMetadata(
    format_name="markdown",
    extensions=[".md", ".markdown", ".mdown", ".mkd", ".mkdn"],
    mime_types=["text/markdown", "text/x-markdown"],
    magic_bytes=[],
    parser_class=MarkdownToAstConverter,
    renderer_class="all2md.renderers.markdown.MarkdownRenderer",
    renders_as_string=True,
    parser_required_packages=[("mistune", "mistune", ">=3.0.0")],
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="Markdown parsing requires 'mistune'. Install with: pip install 'all2md[markdown]'",
    parser_options_class=MarkdownParserOptions,
    renderer_options_class="all2md.options.markdown.MarkdownOptions",
    description="Parse Markdown to AST and render AST to Markdown",
    priority=10
)
