#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/markdown.py
"""Markdown to AST converter.

This module provides conversion from Markdown documents to AST representation
using the mistune parser. It enables bidirectional transformation by parsing
markdown into the same AST structure used for other formats.

"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found,unused-ignore]
from typing import IO, Any, Literal, Optional, Union

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Comment,
    CommentInline,
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
from all2md.constants import DEPS_MARKDOWN
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
        self, options: MarkdownParserOptions | None = None, progress_callback: Optional[ProgressCallback] = None
    ):
        """Initialize the Markdown parser with options and progress callback."""
        BaseParser._validate_options_type(options, MarkdownParserOptions, "markdown")
        options = options or MarkdownParserOptions()
        super().__init__(options, progress_callback)
        self.options: MarkdownParserOptions = options
        self._footnote_definitions: dict[str, list[Node]] = {}

    @requires_dependencies("markdown", DEPS_MARKDOWN)
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
        markdown_content = self._load_text_content(input_data)

        # Reset parser state to prevent leakage across parse calls
        self._footnote_definitions = {}

        # Extract and parse frontmatter before parsing content
        # This also strips frontmatter from the content
        markdown_content, frontmatter_metadata = self._extract_frontmatter(markdown_content)

        import mistune

        # Configure mistune plugins based on options
        plugins = []
        if self.options.parse_strikethrough:
            plugins.append("strikethrough")
        if self.options.parse_tables:
            plugins.append("table")
        if self.options.parse_footnotes:
            plugins.append("footnotes")
        if self.options.parse_task_lists:
            plugins.append("task_lists")
        if self.options.parse_math:
            plugins.append("math")

        # Create markdown parser with plugins
        markdown = mistune.create_markdown(plugins=plugins, renderer=None)  # We'll process tokens ourselves

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
                children.append(FootnoteDefinition(identifier=identifier, content=content))

        # Use frontmatter metadata as document metadata
        return Document(children=children, metadata=frontmatter_metadata.to_dict())

    def _try_extract_yaml_frontmatter(self, content: str) -> tuple[str, DocumentMetadata] | None:
        """Try to extract YAML frontmatter (--- ... ---).

        Parameters
        ----------
        content : str
            Markdown content

        Returns
        -------
        tuple[str, DocumentMetadata] or None
            (remaining_content, metadata) if YAML found, None otherwise

        """
        if not (content.startswith("---\n") or content.startswith("---\r\n")):
            return None

        lines = content.splitlines(keepends=True)
        end_index = -1

        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_index = i
                break

        if end_index <= 0:
            return None

        yaml_content = "".join(lines[1:end_index])
        remaining_content = "".join(lines[end_index + 1 :])

        try:
            import yaml

            data = yaml.safe_load(yaml_content)
            if isinstance(data, dict):
                metadata = self._dict_to_metadata(data)
                return remaining_content, metadata
        except ImportError:
            pass
        except Exception:
            pass

        return remaining_content, DocumentMetadata()

    def _try_extract_toml_frontmatter(self, content: str) -> tuple[str, DocumentMetadata] | None:
        """Try to extract TOML frontmatter (+++ ... +++).

        Parameters
        ----------
        content : str
            Markdown content

        Returns
        -------
        tuple[str, DocumentMetadata] or None
            (remaining_content, metadata) if TOML found, None otherwise

        """
        if not (content.startswith("+++\n") or content.startswith("+++\r\n")):
            return None

        lines = content.splitlines(keepends=True)
        end_index = -1

        for i in range(1, len(lines)):
            if lines[i].strip() == "+++":
                end_index = i
                break

        if end_index <= 0:
            return None

        toml_content = "".join(lines[1:end_index])
        remaining_content = "".join(lines[end_index + 1 :])

        try:
            data = tomllib.loads(toml_content)
            if isinstance(data, dict):
                metadata = self._dict_to_metadata(data)
                return remaining_content, metadata
        except Exception:
            pass

        return remaining_content, DocumentMetadata()

    def _try_extract_json_frontmatter(self, content: str) -> tuple[str, DocumentMetadata] | None:
        """Try to extract JSON frontmatter ({ ... }).

        Parameters
        ----------
        content : str
            Markdown content

        Returns
        -------
        tuple[str, DocumentMetadata] or None
            (remaining_content, metadata) if JSON found, None otherwise

        """
        if not content.startswith("{"):
            return None

        try:

            # Find the end of JSON object
            brace_count = 0
            end_pos = 0
            for i, char in enumerate(content):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i + 1
                        break

            if end_pos > 0:
                json_content = content[:end_pos]
                remaining_content = content[end_pos:].lstrip()

                data = json.loads(json_content)
                if isinstance(data, dict):
                    metadata = self._dict_to_metadata(data)
                    return remaining_content, metadata
        except Exception:
            pass

        return None

    def _extract_frontmatter(self, content: str) -> tuple[str, DocumentMetadata]:
        """Extract and parse frontmatter from markdown content.

        Supports YAML (---), TOML (+++), and JSON frontmatter formats.

        Parameters
        ----------
        content : str
            Markdown content that may contain frontmatter

        Returns
        -------
        tuple[str, DocumentMetadata]
            Content with frontmatter removed and parsed metadata

        """
        if not self.options.parse_frontmatter:
            return content, DocumentMetadata()

        # Try each frontmatter format
        result = self._try_extract_yaml_frontmatter(content)
        if result:
            return result

        result = self._try_extract_toml_frontmatter(content)
        if result:
            return result

        result = self._try_extract_json_frontmatter(content)
        if result:
            return result

        return content, DocumentMetadata()

    def _dict_to_metadata(self, data: dict) -> DocumentMetadata:
        """Convert frontmatter dictionary to DocumentMetadata.

        Parameters
        ----------
        data : dict
            Parsed frontmatter dictionary

        Returns
        -------
        DocumentMetadata
            Document metadata object

        """
        metadata = DocumentMetadata()

        # Map standard fields
        if "title" in data:
            metadata.title = str(data["title"])
        if "author" in data:
            metadata.author = str(data["author"])
        if "description" in data:
            metadata.subject = str(data["description"])
        if "keywords" in data:
            if isinstance(data["keywords"], list):
                metadata.keywords = [str(k) for k in data["keywords"]]
            else:
                metadata.keywords = [str(data["keywords"])]
        if "language" in data or "lang" in data:
            metadata.language = str(data.get("language") or data.get("lang"))
        if "date" in data:
            metadata.creation_date = str(data["date"])

        # Store all other fields in custom
        standard_fields = {"title", "author", "description", "keywords", "language", "lang", "date"}
        for key, value in data.items():
            if key not in standard_fields:
                metadata.custom[key] = value

        return metadata

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
        token_type = token.get("type", "")

        # Block-level tokens
        if token_type == "heading":
            return self._process_heading(token)
        elif token_type == "paragraph":
            return self._process_paragraph(token)
        elif token_type == "block_text":
            # block_text is used for tight list items - treat like paragraph
            return self._process_paragraph(token)
        elif token_type == "block_code":
            return self._process_code_block(token)
        elif token_type == "block_quote":
            return self._process_block_quote(token)
        elif token_type == "list":
            return self._process_list(token)
        elif token_type == "table":
            return self._process_table(token)
        elif token_type == "thematic_break":
            return ThematicBreak()
        elif token_type == "block_html":
            return self._process_html_block(token)
        elif token_type == "block_math":
            return self._process_math_block(token)
        elif token_type == "footnote_def":
            self._process_footnote_def(token)
            return None
        elif token_type == "def_list":
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
        attrs = token.get("attrs", {})
        level = attrs.get("level", 1) if isinstance(attrs, dict) else 1

        # Ensure level is valid (1-6)
        if not isinstance(level, int) or level < 1 or level > 6:
            level = 1

        children = token.get("children", [])
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
        children = token.get("children", [])
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
        code_content = token.get("raw", "")
        attrs = token.get("attrs", {})
        info_string = attrs.get("info", None)

        # Initialize metadata for code block
        metadata: dict[str, Any] = {}
        language = None

        # Parse language and metadata from info string
        if info_string:
            info_string = info_string.strip()
            # Preserve full info string for renderers that support metadata
            metadata["info_string"] = info_string

            # Extract language (first word) and additional attributes
            parts = info_string.split(maxsplit=1)
            if parts:
                # Sanitize language identifier for security (prevent markdown injection)
                language = sanitize_language_identifier(parts[0])

                # Preserve additional metadata if present
                if len(parts) > 1:
                    metadata["info_attrs"] = parts[1]

        return CodeBlock(content=code_content, language=language if language else None, metadata=metadata)

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
        children = token.get("children", [])
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
        attrs = token.get("attrs", {})
        # Guard against attrs not being a dict
        if not isinstance(attrs, dict):
            attrs = {}

        ordered = attrs.get("ordered", False)
        start = attrs.get("start", 1)
        tight = attrs.get("tight", True)

        children = token.get("children", [])
        # Guard against children not being a list
        if not isinstance(children, list):
            children = []

        items = [self._process_list_item(child) for child in children if isinstance(child, dict)]

        return List(ordered=ordered, items=items, start=start, tight=tight)

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
        children = token.get("children", [])
        content = self._process_tokens(children)

        # Check for task list checkbox
        task_status: Literal["checked", "unchecked"] | None = None
        attrs = token.get("attrs", {})
        if "checked" in attrs:
            task_status = "checked" if attrs["checked"] else "unchecked"

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
        children = token.get("children", [])

        header = None
        rows = []
        alignments = []

        for _i, row_token in enumerate(children):
            row_type = row_token.get("type", "")
            if row_type == "table_head":
                # Process header row - cells are direct children of table_head
                head_children = row_token.get("children", [])
                if head_children:
                    # Process cells directly (no intermediate table_row)
                    cells = []
                    alignments_list = []
                    for cell_token in head_children:
                        if cell_token.get("type") == "table_cell":
                            cell_children = cell_token.get("children", [])
                            content = self._process_inline_tokens(cell_children)

                            # Get alignment if specified
                            align = cell_token.get("attrs", {}).get("align", None)
                            alignments_list.append(align)

                            cells.append(TableCell(content=content, alignment=align))

                    header = TableRow(cells=cells, is_header=True)
                    alignments = alignments_list

            elif row_type == "table_body":
                # Process body rows
                body_children = row_token.get("children", [])
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
        cells_tokens = row_token.get("children", [])
        cells = []

        for cell_token in cells_tokens:
            cell_children = cell_token.get("children", [])
            content = self._process_inline_tokens(cell_children)

            # Get alignment if specified
            attrs = cell_token.get("attrs", {})
            alignment = attrs.get("align", None)

            cells.append(TableCell(content=content, alignment=alignment))

        return cells

    def _process_html_block(self, token: dict[str, Any]) -> HTMLBlock | Comment | None:
        """Process HTML block token.

        Parameters
        ----------
        token : dict
            HTML block token with 'raw'

        Returns
        -------
        HTMLBlock, Comment, or None
            HTML block node, Comment node, or None based on content and options

        """
        content = token.get("raw", "")

        # Check if this is an HTML comment
        if self._is_html_comment(content):
            comment_text = self._extract_comment_text(content)
            return Comment(content=comment_text)

        # preserve_html is True, keep raw content
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
        content = token.get("raw", "")
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
        attrs = token.get("attrs", {})
        identifier = attrs.get("label", "")
        children = token.get("children", [])
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
        children = token.get("children", [])
        items: list[tuple[DefinitionTerm, list[DefinitionDescription]]] = []

        current_term: DefinitionTerm | None = None
        current_descriptions: list[DefinitionDescription] = []

        for child in children:
            child_type = child.get("type", "")
            if child_type == "def_list_head":
                # Save previous term/descriptions if any
                if current_term is not None:
                    items.append((current_term, current_descriptions))

                # Start new term
                term_children = child.get("children", [])
                term_content = self._process_inline_tokens(term_children)
                current_term = DefinitionTerm(content=term_content)
                current_descriptions = []

            elif child_type == "def_list_content":
                # Add description
                desc_children = child.get("children", [])
                desc_content = self._process_tokens(desc_children)
                current_descriptions.append(DefinitionDescription(content=desc_content))

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

    def _handle_text_token(self, token: dict[str, Any]) -> Text:
        """Handle text token."""
        content = token.get("raw", "")
        return Text(content=content)

    def _handle_strong_token(self, token: dict[str, Any]) -> Strong:
        """Handle strong token."""
        children = token.get("children", [])
        content = self._process_inline_tokens(children)
        return Strong(content=content)

    def _handle_emphasis_token(self, token: dict[str, Any]) -> Emphasis:
        """Handle emphasis token."""
        children = token.get("children", [])
        content = self._process_inline_tokens(children)
        return Emphasis(content=content)

    def _handle_codespan_token(self, token: dict[str, Any]) -> Code:
        """Handle codespan token."""
        content = token.get("raw", "")
        return Code(content=content)

    def _handle_link_token(self, token: dict[str, Any]) -> Link:
        """Handle link token."""
        attrs = token.get("attrs", {})
        if not isinstance(attrs, dict):
            attrs = {}
        url = attrs.get("url", "")
        title = attrs.get("title", None)
        children = token.get("children", [])
        if not isinstance(children, list):
            children = []
        content = self._process_inline_tokens(children)
        return Link(url=url, content=content, title=title)

    def _handle_image_token(self, token: dict[str, Any]) -> Image:
        """Handle image token."""
        attrs = token.get("attrs", {})
        if not isinstance(attrs, dict):
            attrs = {}
        url = attrs.get("url", "")
        title = attrs.get("title", None)
        # Alt text is in children, not attrs
        children = token.get("children", [])
        alt_text = ""
        if isinstance(children, list) and children:
            # Extract text from children
            alt_parts = []
            for child in children:
                if isinstance(child, dict) and child.get("type") == "text":
                    alt_parts.append(child.get("raw", ""))
            alt_text = "".join(alt_parts)
        return Image(url=url, alt_text=alt_text, title=title)

    def _handle_linebreak_token(self, token: dict[str, Any]) -> LineBreak:
        """Handle linebreak token."""
        attrs = token.get("attrs", {})
        if not isinstance(attrs, dict):
            attrs = {}
        soft = attrs.get("soft", False)
        return LineBreak(soft=soft)

    def _handle_strikethrough_token(self, token: dict[str, Any]) -> Strikethrough:
        """Handle strikethrough token."""
        children = token.get("children", [])
        content = self._process_inline_tokens(children)
        return Strikethrough(content=content)

    def _handle_inline_html_token(self, token: dict[str, Any]) -> Node | None:
        """Handle inline_html token."""
        content = token.get("raw", "")

        # Check if this is an HTML comment
        if self._is_html_comment(content):
            comment_text = self._extract_comment_text(content)
            return CommentInline(content=comment_text)

        return HTMLInline(content=content)

    def _handle_inline_math_token(self, token: dict[str, Any]) -> MathInline:
        """Handle inline_math token."""
        content = token.get("raw", "")
        return MathInline(content=content)

    def _handle_footnote_ref_token(self, token: dict[str, Any]) -> FootnoteReference:
        """Handle footnote_ref token."""
        attrs = token.get("attrs", {})
        if not isinstance(attrs, dict):
            attrs = {}
        identifier = attrs.get("label", "")
        return FootnoteReference(identifier=identifier)

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
        token_type = token.get("type", "")

        # Dispatch to appropriate handler
        handler_map: dict[str, Any] = {
            "text": self._handle_text_token,
            "strong": self._handle_strong_token,
            "emphasis": self._handle_emphasis_token,
            "codespan": self._handle_codespan_token,
            "link": self._handle_link_token,
            "image": self._handle_image_token,
            "linebreak": self._handle_linebreak_token,
            "strikethrough": self._handle_strikethrough_token,
            "inline_html": self._handle_inline_html_token,
            "inline_math": self._handle_inline_math_token,
            "footnote_ref": self._handle_footnote_ref_token,
        }

        handler = handler_map.get(token_type)
        if handler:
            return handler(token)
        return None

    def _is_html_comment(self, content: str) -> bool:
        """Check if HTML content is a comment.

        Parameters
        ----------
        content : str
            HTML content to check

        Returns
        -------
        bool
            True if content is an HTML comment

        """
        stripped = content.strip()
        return stripped.startswith("<!--") and stripped.endswith("-->")

    def _extract_comment_text(self, content: str) -> str:
        """Extract text from HTML comment.

        Parameters
        ----------
        content : str
            HTML comment content (including <!-- and -->)

        Returns
        -------
        str
            Comment text without HTML comment markers

        """
        stripped = content.strip()
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            # Remove comment markers and strip whitespace
            return stripped[4:-3].strip()
        return content

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


def markdown_to_ast(markdown_content: str, options: MarkdownParserOptions | None = None) -> Document:
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
    renderer_options_class="all2md.options.markdown.MarkdownRendererOptions",
    description="Parse Markdown to AST and render AST to Markdown",
    priority=10,
)
