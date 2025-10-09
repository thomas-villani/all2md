#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/asciidoc.py
"""AsciiDoc to AST converter.

This module provides conversion from AsciiDoc documents to AST representation
using a custom parser implementation. It enables bidirectional transformation
by parsing AsciiDoc into the same AST structure used for other formats.

"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
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
    Heading,
    Image,
    Link,
    List,
    ListItem,
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
from all2md.converter_metadata import ConverterMetadata
from all2md.options.asciidoc import AsciiDocOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.metadata import DocumentMetadata


class TokenType(Enum):
    """Token types for AsciiDoc lexer."""

    # Block delimiters
    HEADING = auto()
    PARAGRAPH = auto()
    CODE_BLOCK_DELIMITER = auto()
    QUOTE_BLOCK_DELIMITER = auto()
    LITERAL_BLOCK_DELIMITER = auto()
    SIDEBAR_BLOCK_DELIMITER = auto()
    EXAMPLE_BLOCK_DELIMITER = auto()
    TABLE_DELIMITER = auto()
    THEMATIC_BREAK = auto()

    # List markers
    UNORDERED_LIST = auto()
    ORDERED_LIST = auto()
    DESCRIPTION_TERM = auto()
    CHECKLIST_ITEM = auto()

    # Attributes and metadata
    ATTRIBUTE = auto()
    BLOCK_ATTRIBUTE = auto()
    ANCHOR = auto()

    # Special
    COMMENT = auto()
    BLANK_LINE = auto()
    TEXT_LINE = auto()
    EOF = auto()


@dataclass
class Token:
    """Represents a token from the lexer.

    Parameters
    ----------
    type : TokenType
        Type of the token
    content : str
        Token content/value
    line_num : int
        Line number in source
    indent : int
        Indentation level
    metadata : dict
        Additional token metadata

    """

    type: TokenType
    content: str
    line_num: int
    indent: int = 0
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Initialize metadata if not provided."""
        if self.metadata is None:
            object.__setattr__(self, 'metadata', {})


class AsciiDocLexer:
    """Tokenizer for AsciiDoc content.

    This lexer performs line-by-line tokenization of AsciiDoc content,
    identifying block delimiters, list markers, attributes, and text.

    Parameters
    ----------
    content : str
        AsciiDoc content to tokenize

    """

    def __init__(self, content: str):
        """Initialize the lexer with content."""
        self.lines = content.splitlines()
        self.current_line = 0
        self.tokens: list[Token] = []

        # Patterns for matching
        self.heading_pattern = re.compile(r'^(={1,6})\s+(.+?)(?:\s+\1)?$')
        self.ul_pattern = re.compile(r'^(\*{1,5})\s+(.*)$')
        self.ol_pattern = re.compile(r'^(\.{1,5})\s+(.*)$')
        self.desc_pattern = re.compile(r'^(.+?)::(?:\s+(.*))?$')
        self.checklist_pattern = re.compile(r'^(\*+)\s+\[([ x*])\]\s+(.*)$')
        self.attribute_pattern = re.compile(r'^:([^:]+):\s*(.*)$')
        self.block_attr_pattern = re.compile(r'^\[([^\]]+)\]$')
        self.anchor_pattern = re.compile(r'^\[\[([^\]]+)\]\]$')

    def tokenize(self) -> list[Token]:
        """Tokenize the content into a list of tokens.

        Returns
        -------
        list[Token]
            List of tokens

        """
        while self.current_line < len(self.lines):
            line = self.lines[self.current_line]
            token = self._tokenize_line(line, self.current_line)
            self.tokens.append(token)
            self.current_line += 1

        # Add EOF token
        self.tokens.append(Token(
            type=TokenType.EOF,
            content='',
            line_num=self.current_line,
            indent=0
        ))

        return self.tokens

    def _tokenize_line(self, line: str, line_num: int) -> Token:
        """Tokenize a single line.

        Parameters
        ----------
        line : str
            Line content
        line_num : int
            Line number

        Returns
        -------
        Token
            Token for this line

        """
        # Calculate indentation
        indent = len(line) - len(line.lstrip())
        stripped = line.lstrip()

        # Blank line
        if not stripped:
            return Token(TokenType.BLANK_LINE, '', line_num, indent)

        # Comment
        if stripped.startswith('//'):
            return Token(TokenType.COMMENT, stripped[2:].strip(), line_num, indent)

        # Table delimiter special case: |===
        if stripped.startswith('|') and len(stripped) >= 4:
            if all(c == '=' for c in stripped[1:]):
                return Token(TokenType.TABLE_DELIMITER, stripped, line_num, indent)

        # Block delimiters (must be at least 4 characters and all same char)
        if len(stripped) >= 4 and all(c == stripped[0] for c in stripped):
            delimiter_char = stripped[0]
            delimiter_map = {
                '-': TokenType.CODE_BLOCK_DELIMITER,
                '_': TokenType.QUOTE_BLOCK_DELIMITER,
                '.': TokenType.LITERAL_BLOCK_DELIMITER,
                '*': TokenType.SIDEBAR_BLOCK_DELIMITER,
                '=': TokenType.EXAMPLE_BLOCK_DELIMITER,
            }

            if delimiter_char in delimiter_map:
                return Token(
                    delimiter_map[delimiter_char],
                    stripped,
                    line_num,
                    indent
                )

        # Thematic break (triple apostrophes, hyphens, or asterisks)
        if stripped in ("'''", "---", "***"):
            return Token(TokenType.THEMATIC_BREAK, stripped, line_num, indent)

        # Heading
        heading_match = self.heading_pattern.match(stripped)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2)
            return Token(
                TokenType.HEADING,
                content,
                line_num,
                indent,
                {'level': level}
            )

        # Anchor
        anchor_match = self.anchor_pattern.match(stripped)
        if anchor_match:
            return Token(
                TokenType.ANCHOR,
                anchor_match.group(1),
                line_num,
                indent
            )

        # Block attribute
        block_attr_match = self.block_attr_pattern.match(stripped)
        if block_attr_match:
            return Token(
                TokenType.BLOCK_ATTRIBUTE,
                block_attr_match.group(1),
                line_num,
                indent
            )

        # Document attribute
        attr_match = self.attribute_pattern.match(stripped)
        if attr_match:
            return Token(
                TokenType.ATTRIBUTE,
                attr_match.group(1),
                line_num,
                indent,
                {'value': attr_match.group(2)}
            )

        # Checklist item
        checklist_match = self.checklist_pattern.match(stripped)
        if checklist_match:
            level = len(checklist_match.group(1))
            checked = checklist_match.group(2) in ('x', '*')
            content = checklist_match.group(3)
            return Token(
                TokenType.CHECKLIST_ITEM,
                content,
                line_num,
                indent,
                {'level': level, 'checked': checked}
            )

        # Unordered list
        ul_match = self.ul_pattern.match(stripped)
        if ul_match:
            level = len(ul_match.group(1))
            content = ul_match.group(2)
            return Token(
                TokenType.UNORDERED_LIST,
                content,
                line_num,
                indent,
                {'level': level}
            )

        # Ordered list
        ol_match = self.ol_pattern.match(stripped)
        if ol_match:
            level = len(ol_match.group(1))
            content = ol_match.group(2)
            return Token(
                TokenType.ORDERED_LIST,
                content,
                line_num,
                indent,
                {'level': level}
            )

        # Description list
        desc_match = self.desc_pattern.match(stripped)
        if desc_match:
            term = desc_match.group(1)
            description = desc_match.group(2) or ''
            return Token(
                TokenType.DESCRIPTION_TERM,
                term,
                line_num,
                indent,
                {'description': description}
            )

        # Default: text line
        return Token(TokenType.TEXT_LINE, stripped, line_num, indent)


class AsciiDocParser(BaseParser):
    r"""Convert AsciiDoc to AST representation.

    This parser implements a custom AsciiDoc parser that converts AsciiDoc
    documents into the all2md AST format. It uses a two-stage process:
    lexing (tokenization) and parsing.

    Parameters
    ----------
    options : AsciiDocParserOptions or None, default = None
        Parser configuration options
    progress_callback : ProgressCallback or None, default = None
        Optional callback for progress updates

    Examples
    --------
    Basic parsing:

        >>> parser = AsciiDocParser()
        >>> doc = parser.parse("= Title\n\nThis is *bold*.")

    With options:

        >>> options = AsciiDocOptions(parse_attributes=True)
        >>> parser = AsciiDocParser(options)
        >>> doc = parser.parse(asciidoc_text)

    """

    def __init__(
        self,
        options: AsciiDocOptions | None = None,
        progress_callback: Optional[ProgressCallback] = None
    ):
        """Initialize the AsciiDoc parser."""
        options = options or AsciiDocOptions()
        super().__init__(options, progress_callback)
        self.options: AsciiDocOptions = options

        # Parser state
        self.tokens: list[Token] = []
        self.current_token_index = 0
        self.attributes: dict[str, str] = {}

        # Inline patterns
        self._setup_inline_patterns()

    def _setup_inline_patterns(self) -> None:
        """Set up regex patterns for inline formatting."""
        # Inline formatting patterns (non-greedy)
        self.bold_pattern = re.compile(r'\*([^\*]+?)\*')
        self.italic_pattern = re.compile(r'_([^_]+?)_')
        self.mono_pattern = re.compile(r'`([^`]+?)`')
        self.subscript_pattern = re.compile(r'~([^~]+?)~')
        self.superscript_pattern = re.compile(r'\^([^\^]+?)\^')

        # Links and images
        self.link_pattern = re.compile(r'link:([^\[]+)\[([^\]]*)\]')
        self.auto_link_pattern = re.compile(r'(https?://[^\s\[\]]+)')
        self.image_block_pattern = re.compile(r'image::([^\[]+)\[([^\]]*)\]')
        self.image_inline_pattern = re.compile(r'image:([^\[]+)\[([^\]]*)\]')

        # Cross-references
        self.xref_pattern = re.compile(r'<<([^,\>]+)(?:,([^\>]+))?>>')

        # Attribute references
        self.attr_ref_pattern = re.compile(r'\{([^\}]+)\}')

        # Passthrough
        self.passthrough_pattern = re.compile(r'(?:\+\+([^\+]+)\+\+|\+([^\+]+)\+|pass:\[([^\]]+)\])')

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse AsciiDoc input into AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            AsciiDoc input to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw AsciiDoc bytes
            - AsciiDoc string

        Returns
        -------
        Document
            AST document node

        Raises
        ------
        ParsingError
            If parsing fails

        """
        # Load content
        content = self._load_content(input_data)

        # Emit progress event
        self._emit_progress("started", "Parsing AsciiDoc", current=0, total=100)

        # Tokenize
        lexer = AsciiDocLexer(content)
        self.tokens = lexer.tokenize()
        self.current_token_index = 0

        self._emit_progress("tokenization_done", "Tokenization complete", current=30, total=100)

        # Parse tokens into AST
        children = self._parse_document()

        # Extract metadata
        metadata = self.extract_metadata(content)

        self._emit_progress("finished", "Parsing complete", current=100, total=100)

        return Document(children=children, metadata=metadata.to_dict())

    @staticmethod
    def _load_content(input_data: Union[str, Path, IO[bytes], bytes]) -> str:
        """Load AsciiDoc content from various input types.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Input data to load

        Returns
        -------
        str
            AsciiDoc content as string

        """
        if isinstance(input_data, bytes):
            return input_data.decode("utf-8", errors="replace")
        elif isinstance(input_data, Path):
            return input_data.read_text(encoding="utf-8")
        elif isinstance(input_data, str):
            # Could be file path or content
            path = Path(input_data)
            if path.exists() and path.is_file():
                return path.read_text(encoding="utf-8")
            else:
                # Assume it's content
                return input_data
        else:
            # File-like object
            input_data.seek(0)
            content_bytes = input_data.read()
            return content_bytes.decode("utf-8", errors="replace")

    def _current_token(self) -> Token:
        """Get the current token.

        Returns
        -------
        Token
            Current token

        """
        if self.current_token_index < len(self.tokens):
            return self.tokens[self.current_token_index]
        return self.tokens[-1]  # EOF

    def _peek_token(self, offset: int = 1) -> Token:
        """Peek at a token ahead.

        Parameters
        ----------
        offset : int, default = 1
            How many tokens to look ahead

        Returns
        -------
        Token
            Token at offset

        """
        index = self.current_token_index + offset
        if index < len(self.tokens):
            return self.tokens[index]
        return self.tokens[-1]  # EOF

    def _advance(self) -> Token:
        """Advance to the next token and return the previous one.

        Returns
        -------
        Token
            Token before advancing

        """
        token = self._current_token()
        if token.type != TokenType.EOF:
            self.current_token_index += 1
        return token

    def _skip_blank_lines(self) -> None:
        """Skip over blank lines and comments."""
        while self._current_token().type in (TokenType.BLANK_LINE, TokenType.COMMENT):
            self._advance()

    def _parse_document(self) -> list[Node]:
        """Parse the document into a list of block nodes.

        Returns
        -------
        list[Node]
            List of block-level AST nodes

        """
        nodes: list[Node] = []

        # First pass: collect document attributes
        if self.options.parse_attributes:
            self._collect_attributes()

        # Reset to beginning for main parsing
        self.current_token_index = 0

        # Parse blocks
        while self._current_token().type != TokenType.EOF:
            # Skip blank lines and comments at document level
            self._skip_blank_lines()

            if self._current_token().type == TokenType.EOF:
                break

            # Parse next block
            node = self._parse_block()
            if node is not None:
                if isinstance(node, list):
                    nodes.extend(node)
                else:
                    nodes.append(node)

        return nodes

    def _collect_attributes(self) -> None:
        """Collect document-level attributes on first pass."""
        saved_index = self.current_token_index
        self.current_token_index = 0

        while self._current_token().type != TokenType.EOF:
            token = self._current_token()

            if token.type == TokenType.ATTRIBUTE:
                attr_name = token.content
                attr_value = token.metadata.get('value', '') if token.metadata else ''
                self.attributes[attr_name] = attr_value

            self._advance()

        self.current_token_index = saved_index

    def _parse_block(self) -> Node | list[Node] | None:
        """Parse a single block-level element.

        Returns
        -------
        Node, list[Node], or None
            Parsed block node(s)

        """
        token = self._current_token()

        # Skip attributes (already collected)
        if token.type == TokenType.ATTRIBUTE:
            self._advance()
            return None

        # Heading
        if token.type == TokenType.HEADING:
            return self._parse_heading()

        # Lists
        if token.type in (TokenType.UNORDERED_LIST, TokenType.ORDERED_LIST, TokenType.CHECKLIST_ITEM):
            return self._parse_list()

        # Description list
        if token.type == TokenType.DESCRIPTION_TERM:
            return self._parse_description_list()

        # Delimited blocks
        if token.type == TokenType.CODE_BLOCK_DELIMITER:
            return self._parse_code_block()

        if token.type == TokenType.QUOTE_BLOCK_DELIMITER:
            return self._parse_quote_block()

        if token.type == TokenType.TABLE_DELIMITER:
            return self._parse_table()

        # Thematic break
        if token.type == TokenType.THEMATIC_BREAK:
            self._advance()
            return ThematicBreak()

        # Block attribute or anchor (preceding next block)
        if token.type in (TokenType.BLOCK_ATTRIBUTE, TokenType.ANCHOR):
            # TODO: Store for next block
            self._advance()
            return None

        # Text line - start of paragraph
        if token.type == TokenType.TEXT_LINE:
            return self._parse_paragraph()

        # Unknown - skip
        self._advance()
        return None

    def _parse_heading(self) -> Heading:
        """Parse a heading.

        Returns
        -------
        Heading
            Heading node

        """
        token = self._advance()
        level = token.metadata.get('level', 1) if token.metadata else 1
        content = self._parse_inline(token.content)

        return Heading(level=level, content=content)

    def _parse_paragraph(self) -> Paragraph:
        """Parse a paragraph (consecutive text lines).

        Returns
        -------
        Paragraph
            Paragraph node

        """
        lines = []

        # Collect consecutive text lines
        while self._current_token().type == TokenType.TEXT_LINE:
            token = self._advance()
            lines.append(token.content)

            # Check if next is still text (not separated by blank line)
            if self._current_token().type == TokenType.BLANK_LINE:
                break

        # Join lines with spaces
        text = ' '.join(lines)
        content = self._parse_inline(text)

        return Paragraph(content=content)

    def _parse_inline(self, text: str) -> list[Node]:
        """Parse inline formatting in text.

        Parameters
        ----------
        text : str
            Text to parse

        Returns
        -------
        list[Node]
            List of inline nodes

        """
        nodes: list[Node] = []

        if not text:
            return nodes

        # Process inline formatting using a state-based approach
        # This handles nested and overlapping formats correctly
        nodes = self._parse_inline_recursive(text)

        return nodes

    def _parse_inline_recursive(self, text: str) -> list[Node]:
        """Recursively parse inline formatting.

        Parameters
        ----------
        text : str
            Text to parse

        Returns
        -------
        list[Node]
            List of inline nodes

        """
        nodes: list[Node] = []
        remaining = text
        pos = 0

        while pos < len(remaining):
            # Try to match each pattern at current position
            matched = False

            # Check for passthrough first (highest priority)
            match = self.passthrough_pattern.match(remaining[pos:])
            if match:
                # Extract passthrough content (don't process further)
                passthrough_content = match.group(1) or match.group(2) or match.group(3)
                nodes.append(Text(content=passthrough_content))
                pos += match.end()
                matched = True
                continue

            # Check for images (block and inline)
            match = self.image_block_pattern.match(remaining[pos:])
            if not match:
                match = self.image_inline_pattern.match(remaining[pos:])

            if match:
                url = match.group(1)
                alt_text = match.group(2) if len(match.groups()) >= 2 else ''
                nodes.append(Image(url=url, alt_text=alt_text))
                pos += match.end()
                matched = True
                continue

            # Check for links (explicit)
            match = self.link_pattern.match(remaining[pos:])
            if match:
                url = match.group(1)
                link_text = match.group(2)
                content = self._parse_inline_recursive(link_text) if link_text else [Text(content=url)]
                nodes.append(Link(url=url, content=content))
                pos += match.end()
                matched = True
                continue

            # Check for auto-links
            match = self.auto_link_pattern.match(remaining[pos:])
            if match:
                url = match.group(1)
                nodes.append(Link(url=url, content=[Text(content=url)]))
                pos += match.end()
                matched = True
                continue

            # Check for cross-references
            match = self.xref_pattern.match(remaining[pos:])
            if match:
                ref_id = match.group(1)
                ref_text = match.group(2) if len(match.groups()) >= 2 and match.group(2) else ref_id
                # Cross-references are rendered as links with # prefix
                nodes.append(Link(url=f"#{ref_id}", content=[Text(content=ref_text)]))
                pos += match.end()
                matched = True
                continue

            # Check for attribute references
            if self.options.resolve_attribute_refs:
                match = self.attr_ref_pattern.match(remaining[pos:])
                if match:
                    attr_name = match.group(1)
                    attr_value = self.attributes.get(attr_name, f"{{{attr_name}}}")
                    nodes.append(Text(content=attr_value))
                    pos += match.end()
                    matched = True
                    continue

            # Check for bold
            match = self.bold_pattern.match(remaining[pos:])
            if match:
                inner_text = match.group(1)
                inner_nodes = self._parse_inline_recursive(inner_text)
                nodes.append(Strong(content=inner_nodes))
                pos += match.end()
                matched = True
                continue

            # Check for italic
            match = self.italic_pattern.match(remaining[pos:])
            if match:
                inner_text = match.group(1)
                inner_nodes = self._parse_inline_recursive(inner_text)
                nodes.append(Emphasis(content=inner_nodes))
                pos += match.end()
                matched = True
                continue

            # Check for monospace
            match = self.mono_pattern.match(remaining[pos:])
            if match:
                code_text = match.group(1)
                nodes.append(Code(content=code_text))
                pos += match.end()
                matched = True
                continue

            # Check for superscript
            match = self.superscript_pattern.match(remaining[pos:])
            if match:
                inner_text = match.group(1)
                inner_nodes = self._parse_inline_recursive(inner_text)
                nodes.append(Superscript(content=inner_nodes))
                pos += match.end()
                matched = True
                continue

            # Check for subscript
            match = self.subscript_pattern.match(remaining[pos:])
            if match:
                inner_text = match.group(1)
                inner_nodes = self._parse_inline_recursive(inner_text)
                nodes.append(Subscript(content=inner_nodes))
                pos += match.end()
                matched = True
                continue

            # No pattern matched - consume one character as text
            if not matched:
                # Find the next special character or end of string
                next_special = len(remaining)
                for pattern in [
                    self.bold_pattern,
                    self.italic_pattern,
                    self.mono_pattern,
                    self.subscript_pattern,
                    self.superscript_pattern,
                    self.link_pattern,
                    self.auto_link_pattern,
                    self.image_block_pattern,
                    self.image_inline_pattern,
                    self.xref_pattern,
                    self.attr_ref_pattern,
                    self.passthrough_pattern,
                ]:
                    match = pattern.search(remaining[pos:])
                    if match:
                        next_special = min(next_special, pos + match.start())

                # Extract text up to next special character
                text_content = remaining[pos:next_special]
                if text_content:
                    # Merge with previous text node if possible
                    if nodes and isinstance(nodes[-1], Text):
                        nodes[-1] = Text(content=nodes[-1].content + text_content)
                    else:
                        nodes.append(Text(content=text_content))

                pos = next_special

        return nodes

    def _parse_list(self) -> List:
        """Parse an ordered or unordered list.

        Returns
        -------
        List
            List node

        """
        # Determine list type from first item
        first_token = self._current_token()
        ordered = first_token.type == TokenType.ORDERED_LIST

        items: list[ListItem] = []

        # Parse list items at the same level
        while True:
            token = self._current_token()

            # Check if this is a list item at our level
            if token.type not in (TokenType.UNORDERED_LIST, TokenType.ORDERED_LIST, TokenType.CHECKLIST_ITEM):
                break

            # Parse the item
            item = self._parse_list_item()
            items.append(item)

            # Skip blank line after item if present
            if self._current_token().type == TokenType.BLANK_LINE:
                self._advance()

        return List(ordered=ordered, items=items, tight=True)

    def _parse_list_item(self) -> ListItem:
        """Parse a single list item.

        Returns
        -------
        ListItem
            List item node

        """
        token = self._advance()
        content_text = token.content

        # Parse inline content
        content_nodes = self._parse_inline(content_text)

        # Wrap in paragraph
        children: list[Node] = [Paragraph(content=content_nodes)]

        # Check for task status
        task_status: Literal['checked', 'unchecked'] | None = None
        if token.type == TokenType.CHECKLIST_ITEM:
            is_checked = token.metadata.get('checked') if token.metadata else False
            task_status = 'checked' if is_checked else 'unchecked'

        return ListItem(children=children, task_status=task_status)

    def _parse_description_list(self) -> DefinitionList:
        """Parse a description list.

        Returns
        -------
        DefinitionList
            Definition list node

        """
        items: list[tuple[DefinitionTerm, list[DefinitionDescription]]] = []

        while self._current_token().type == TokenType.DESCRIPTION_TERM:
            token = self._advance()

            # Parse term
            term_content = self._parse_inline(token.content)
            term = DefinitionTerm(content=term_content)

            # Parse description(s)
            descriptions: list[DefinitionDescription] = []
            description_text = (token.metadata.get('description', '') if token.metadata else '').strip()

            if description_text:
                desc_content = self._parse_inline(description_text)
                descriptions.append(DefinitionDescription(content=[Paragraph(content=desc_content)]))

            items.append((term, descriptions))

            # Skip blank line
            if self._current_token().type == TokenType.BLANK_LINE:
                self._advance()

        return DefinitionList(items=items)

    def _parse_code_block(self) -> CodeBlock:
        """Parse a code block.

        Returns
        -------
        CodeBlock
            Code block node

        """
        # Skip opening delimiter
        self._advance()

        # Check if previous token was a block attribute with language
        # TODO: Implement block attribute handling
        language: Optional[str] = None

        # Collect content until closing delimiter
        lines = []
        while self._current_token().type != TokenType.CODE_BLOCK_DELIMITER:
            if self._current_token().type == TokenType.EOF:
                break

            token = self._advance()
            if token.type == TokenType.TEXT_LINE:
                lines.append(token.content)
            elif token.type == TokenType.BLANK_LINE:
                lines.append('')

        # Skip closing delimiter
        if self._current_token().type == TokenType.CODE_BLOCK_DELIMITER:
            self._advance()

        content = '\n'.join(lines)
        return CodeBlock(content=content, language=language)

    def _parse_quote_block(self) -> BlockQuote:
        """Parse a block quote.

        Returns
        -------
        BlockQuote
            Block quote node

        """
        # Skip opening delimiter
        self._advance()

        # Collect content until closing delimiter
        children: list[Node] = []

        while self._current_token().type != TokenType.QUOTE_BLOCK_DELIMITER:
            if self._current_token().type == TokenType.EOF:
                break

            # Parse blocks inside quote
            node = self._parse_block()
            if node is not None:
                if isinstance(node, list):
                    children.extend(node)
                else:
                    children.append(node)

        # Skip closing delimiter
        if self._current_token().type == TokenType.QUOTE_BLOCK_DELIMITER:
            self._advance()

        return BlockQuote(children=children)

    def _parse_table(self) -> Table:
        """Parse a table.

        Returns
        -------
        Table
            Table node

        """
        # Skip opening delimiter
        self._advance()

        rows: list[TableRow] = []
        header: Optional[TableRow] = None

        # Collect table rows
        while self._current_token().type != TokenType.TABLE_DELIMITER:
            if self._current_token().type == TokenType.EOF:
                break

            token = self._current_token()

            if token.type == TokenType.TEXT_LINE and '|' in token.content:
                row = self._parse_table_row(token.content)
                if header is None:
                    header = row
                    header.is_header = True
                else:
                    rows.append(row)

            self._advance()

        # Skip closing delimiter
        if self._current_token().type == TokenType.TABLE_DELIMITER:
            self._advance()

        return Table(header=header, rows=rows)

    def _parse_table_row(self, line: str) -> TableRow:
        """Parse a table row from a line.

        Parameters
        ----------
        line : str
            Table row line

        Returns
        -------
        TableRow
            Table row node

        """
        # Split by | and create cells
        parts = line.split('|')
        cells: list[TableCell] = []

        for part in parts:
            part = part.strip()
            if part:
                content = self._parse_inline(part)
                cells.append(TableCell(content=content))

        return TableRow(cells=cells)

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from AsciiDoc document.

        Parameters
        ----------
        document : Any
            Document content or AST

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Extract standard fields
        if 'title' in self.attributes:
            metadata.title = self.attributes['title']
        if 'author' in self.attributes:
            metadata.author = self.attributes['author']
        if 'description' in self.attributes:
            metadata.subject = self.attributes['description']  # subject maps to description in to_dict()
        if 'keywords' in self.attributes:
            # Parse keywords (comma or space separated)
            keywords_str = self.attributes['keywords']
            if isinstance(keywords_str, str):
                metadata.keywords = [k.strip() for k in keywords_str.replace(',', ' ').split() if k.strip()]
        if 'lang' in self.attributes or 'language' in self.attributes:
            metadata.language = self.attributes.get('lang') or self.attributes.get('language')

        # Store all other AsciiDoc attributes in custom field
        for key, value in self.attributes.items():
            if key not in ('title', 'author', 'description', 'keywords', 'lang', 'language'):
                metadata.custom[key] = value

        return metadata


# Converter metadata for registry auto-discovery
CONVERTER_METADATA = ConverterMetadata(
    format_name="asciidoc",
    extensions=[".adoc", ".asciidoc", ".asc"],
    mime_types=["text/asciidoc", "text/x-asciidoc"],
    magic_bytes=[],  # AsciiDoc is plain text, no magic bytes
    parser_class="AsciiDocParser",
    renderer_class="all2md.renderers.asciidoc.AsciiDocRenderer",
    renders_as_string=True,
    parser_required_packages=[],  # No external dependencies
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="",
    parser_options_class="AsciiDocOptions",
    renderer_options_class="AsciiDocRendererOptions",
    description="Parse and render AsciiDoc format",
    priority=10
)
