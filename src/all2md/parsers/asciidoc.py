#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/asciidoc.py
"""AsciiDoc to AST converter.

This module provides conversion from AsciiDoc documents to AST representation
using a custom parser implementation. It enables bidirectional transformation
by parsing AsciiDoc into the same AST structure used for other formats.

"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import IO, Any, Literal, Optional, Union, cast

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
    MathBlock,
    MathInline,
    Node,
    Paragraph,
    Strikethrough,
    Strong,
    Subscript,
    Superscript,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.ast.builder import ListBuilder
from all2md.converter_metadata import ConverterMetadata
from all2md.options.asciidoc import AsciiDocOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.html_sanitizer import sanitize_url
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.parser_helpers import parse_delimited_block

logger = logging.getLogger(__name__)


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
            object.__setattr__(self, "metadata", {})


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
        self.heading_pattern = re.compile(r"^(={1,6})\s+(.+?)(?:\s+\1)?$")
        self.ul_pattern = re.compile(r"^(\*{1,5})\s+(.*)$")
        self.ol_pattern = re.compile(r"^(\.{1,5})\s+(.*)$")
        # Description list: supports both :: and ; delimiters
        self.desc_pattern_double_colon = re.compile(r"^(.+?)::(?:\s+(.*))?$")
        self.desc_pattern_semicolon = re.compile(r"^(.+?);(?:\s+(.*))?$")
        self.checklist_pattern = re.compile(r"^(\*+)\s+\[([ x*])\]\s+(.*)$")
        self.attribute_pattern = re.compile(r"^:([^:!]+)(!)?:\s*(.*)$")
        self.block_attr_pattern = re.compile(r"^\[([^\]]+)\]$")
        self.anchor_pattern = re.compile(r"^\[\[([^\]]+)\]\]$")

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
        self.tokens.append(Token(type=TokenType.EOF, content="", line_num=self.current_line, indent=0))

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
            return Token(TokenType.BLANK_LINE, "", line_num, indent)

        # Comment
        if stripped.startswith("//"):
            return Token(TokenType.COMMENT, stripped[2:].strip(), line_num, indent)

        # Table delimiter special case: |===
        if stripped.startswith("|") and len(stripped) >= 4:
            if all(c == "=" for c in stripped[1:]):
                return Token(TokenType.TABLE_DELIMITER, stripped, line_num, indent)

        # Block delimiters (must be at least 4 characters and all same char)
        if len(stripped) >= 4 and all(c == stripped[0] for c in stripped):
            delimiter_char = stripped[0]
            delimiter_map = {
                "-": TokenType.CODE_BLOCK_DELIMITER,
                "_": TokenType.QUOTE_BLOCK_DELIMITER,
                ".": TokenType.LITERAL_BLOCK_DELIMITER,
                "*": TokenType.SIDEBAR_BLOCK_DELIMITER,
                "=": TokenType.EXAMPLE_BLOCK_DELIMITER,
            }

            if delimiter_char in delimiter_map:
                return Token(delimiter_map[delimiter_char], stripped, line_num, indent)

        # Thematic break (3+ identical chars of ', -, *, _)
        # Note: 4+ of -, _, * are caught earlier as block delimiters
        if len(stripped) >= 3 and all(c == stripped[0] for c in stripped) and stripped[0] in ("'", "-", "*", "_"):
            return Token(TokenType.THEMATIC_BREAK, stripped, line_num, indent)

        # Heading
        heading_match = self.heading_pattern.match(stripped)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2)
            return Token(TokenType.HEADING, content, line_num, indent, {"level": level})

        # Anchor
        anchor_match = self.anchor_pattern.match(stripped)
        if anchor_match:
            return Token(TokenType.ANCHOR, anchor_match.group(1), line_num, indent)

        # Block attribute
        block_attr_match = self.block_attr_pattern.match(stripped)
        if block_attr_match:
            return Token(TokenType.BLOCK_ATTRIBUTE, block_attr_match.group(1), line_num, indent)

        # Document attribute (with continuation support)
        attr_match = self.attribute_pattern.match(stripped)
        if attr_match:
            attr_name = attr_match.group(1)
            is_unset = attr_match.group(2) is not None  # Check for ! marker
            attr_value = attr_match.group(3) if not is_unset else None

            # Check for continuation (value ending with ' +')
            if attr_value and attr_value.endswith(" +"):
                # Collect continuation lines
                value_parts = [attr_value[:-2]]  # Remove ' +' from current line

                # Look ahead for continuation lines
                continuation_line_num = line_num + 1
                while continuation_line_num < len(self.lines):
                    cont_line = self.lines[continuation_line_num]
                    cont_stripped = cont_line.strip()

                    # Empty line ends continuation
                    if not cont_stripped:
                        break

                    # Check if this line ends with ' +' (more continuation)
                    if cont_stripped.endswith(" +"):
                        value_parts.append(cont_stripped[:-2])
                        continuation_line_num += 1
                    else:
                        # Last continuation line
                        value_parts.append(cont_stripped)
                        continuation_line_num += 1
                        break

                # Join all parts with space
                attr_value = " ".join(value_parts)

                # Skip the continuation lines we consumed
                # (they'll be tokenized as blank or skipped)
                for _ in range(line_num + 1, continuation_line_num):
                    self.current_line += 1

            return Token(TokenType.ATTRIBUTE, attr_name, line_num, indent, {"value": attr_value, "unset": is_unset})

        # Checklist item
        checklist_match = self.checklist_pattern.match(stripped)
        if checklist_match:
            level = len(checklist_match.group(1))
            checked = checklist_match.group(2) in ("x", "*")
            content = checklist_match.group(3)
            return Token(TokenType.CHECKLIST_ITEM, content, line_num, indent, {"level": level, "checked": checked})

        # Unordered list
        ul_match = self.ul_pattern.match(stripped)
        if ul_match:
            level = len(ul_match.group(1))
            content = ul_match.group(2)
            return Token(TokenType.UNORDERED_LIST, content, line_num, indent, {"level": level})

        # Ordered list
        ol_match = self.ol_pattern.match(stripped)
        if ol_match:
            level = len(ol_match.group(1))
            content = ol_match.group(2)
            return Token(TokenType.ORDERED_LIST, content, line_num, indent, {"level": level})

        # Description list (try double-colon first, then semicolon)
        desc_match = self.desc_pattern_double_colon.match(stripped)
        if not desc_match:
            # Try semicolon syntax
            desc_match = self.desc_pattern_semicolon.match(stripped)

        if desc_match:
            term = desc_match.group(1)
            description = desc_match.group(2) or ""
            return Token(TokenType.DESCRIPTION_TERM, term, line_num, indent, {"description": description})

        # Default: text line
        return Token(TokenType.TEXT_LINE, stripped, line_num, indent)


class AsciiDocParser(BaseParser):
    r"""Convert AsciiDoc to AST representation.

    This parser implements a custom AsciiDoc parser that converts AsciiDoc
    documents into the all2md AST format. It uses a two-stage process:
    lexing (tokenization) and parsing.

    Supported Features
    ------------------
    - Headings (= through ======)
    - Paragraphs with hard line breaks (trailing `` +``)
    - Inline formatting:
      - Bold: \*text\* (constrained), \*\*text\*\* (unconstrained)
      - Italic: \_text\_ (constrained), \__text\__ (unconstrained)
      - Monospace: \`code\`
      - Superscript: ^text^
      - Subscript: ~text~
      - Escape sequences: \\\*, \_, \\{, \\+, \\#, \\!, \\:, etc.
    - Lists with nesting:
      - Unordered (\* through \*****)
      - Ordered (. through .....)
      - Checklists (\* [x] or \* [ ])
      - Description lists (term:: or term;)
    - Code blocks (----) with language support via [source,lang]
    - Literal blocks (....) for preformatted text
    - Block quotes (____)
    - Sidebar blocks (\****) rendered as block quotes with role='sidebar'
    - Example blocks (====) rendered as block quotes with role='example'
    - Tables (\|===) with:
      - Attribute-based header detection
      - Escaped pipes (\\|) in cells
      - Basic cell formatting
    - Links: link:url[text] and auto-links (http://...)
    - Images: image::url[alt] and image:url[alt]
    - Cross-references: <<id>> and <<id,text>>
    - Attribute references in braces
    - Block attributes: [#id], [.role], [source,python], [options="header"]
    - Anchors: [[anchor-id]]
    - Thematic breaks (''', ---, \***, ___, or 3+ of same char)
    - Passthrough: ++text++, +text+, pass:[text]
    - Document attributes (:name: value, :name!: to unset, multi-line with +)
    - Admonitions: [NOTE], [TIP], [IMPORTANT], [WARNING], [CAUTION]
    - Comments: // single-line comments (preserved as Comment nodes unless strip_comments=True)

    Limitations
    -----------
    - No support for: includes, conditionals, complex macros
    - Tables: no multi-line cells or nested tables (cell spanning is supported)
    - Some advanced inline formatting edge cases

    Parameters
    ----------
    options : AsciiDocOptions or None, default = None
        Parser configuration options
    progress_callback : ProgressCallback or None, default = None
        Optional callback for progress updates

    Examples
    --------
    Basic parsing:

        >>> parser = AsciiDocParser()
        >>> doc = parser.parse("= Title\n\nThis is *bold*.")

    With options:

        >>> options = AsciiDocOptions(
        ...     support_unconstrained_formatting=True,
        ...     table_header_detection="attribute-based"
        ... )
        >>> parser = AsciiDocParser(options)
        >>> doc = parser.parse(asciidoc_text)

    """

    def __init__(self, options: AsciiDocOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the AsciiDoc parser."""
        BaseParser._validate_options_type(options, AsciiDocOptions, "asciidoc")
        options = options or AsciiDocOptions()
        super().__init__(options, progress_callback)
        self.options: AsciiDocOptions = options

        # Parser state
        self.tokens: list[Token] = []
        self.current_token_index = 0
        self.attributes: dict[str, str] = {}
        self.pending_block_attrs: dict[str, Any] = {}

        # Footnote collection for tracking footnote definitions
        self._footnote_definitions: dict[str, str] = {}  # identifier -> footnote content
        self._footnote_counter = 0  # Counter for auto-generated footnote IDs

        # Inline patterns
        self._setup_inline_patterns()

        # Escape sequence placeholder (unlikely to appear in normal text)
        self._escape_placeholder = "\x00ESC\x00"

    def _setup_inline_patterns(self) -> None:
        """Set up regex patterns for inline formatting.

        Supports both constrained (single delimiter, word boundaries) and
        unconstrained (double delimiter, anywhere) formatting.
        """
        # Unconstrained formatting (double delimiters, higher priority)
        self.bold_unconstrained_pattern: Optional[re.Pattern[str]]
        self.italic_unconstrained_pattern: Optional[re.Pattern[str]]

        if self.options.support_unconstrained_formatting:
            self.bold_unconstrained_pattern = re.compile(r"\*\*([^\*]+?)\*\*")
            self.italic_unconstrained_pattern = re.compile(r"__([^_]+?)__")
        else:
            self.bold_unconstrained_pattern = None
            self.italic_unconstrained_pattern = None

        # Constrained formatting (single delimiters with word boundaries)
        # Modified to not match if preceded/followed by same character
        self.bold_pattern = re.compile(r"(?<!\*)\*([^\*\s][^\*]*?)\*(?!\*)")
        self.italic_pattern = re.compile(r"(?<!_)_([^_\s][^_]*?)_(?!_)")
        self.mono_pattern = re.compile(r"`([^`]+?)`")
        self.subscript_pattern = re.compile(r"~([^~]+?)~")
        self.superscript_pattern = re.compile(r"\^([^\^]+?)\^")

        # Links and images
        self.link_pattern = re.compile(r"link:([^\[]+)\[([^\]]*)\]")
        self.auto_link_pattern = re.compile(r"(https?://[^\s\[\]]+)")
        self.image_block_pattern = re.compile(r"image::([^\[]+)\[([^\]]*)\]")
        self.image_inline_pattern = re.compile(r"image:([^\[]+)\[([^\]]*)\]")

        # Cross-references
        self.xref_pattern = re.compile(r"<<([^,\>]+)(?:,([^\>]+))?>>")

        # Attribute references (will check for escaping separately)
        self.attr_ref_pattern = re.compile(r"\{([^\}]+)\}")

        # Passthrough
        self.passthrough_pattern = re.compile(r"(?:\+\+([^\+]+)\+\+|\+([^\+]+)\+|pass:\[([^\]]+)\])")

        # Footnotes
        # footnote:[text] - inline footnote with content
        # footnoteref:[id,text] - footnote reference with optional text (first occurrence defines, rest reference)
        # footnoteref:[id] - footnote reference without text (must be defined elsewhere)
        self.footnote_pattern = re.compile(r"footnote:\[([^\]]+)\]")
        self.footnoteref_pattern = re.compile(r"footnoteref:\[([^\],]+)(?:,([^\]]+))?\]")

        # Math
        # latexmath:[$...$] or latexmath:[...] - inline LaTeX math
        # stem:[$...$] or stem:[...] - inline STEM math (default is LaTeX)
        self.latexmath_inline_pattern = re.compile(r"latexmath:\[(?:\$([^\$]+)\$|([^\]]+))\]")
        self.stem_inline_pattern = re.compile(r"stem:\[(?:\$([^\$]+)\$|([^\]]+))\]")

        # Roles for special formatting
        # [line-through]#text# - strikethrough
        # [underline]#text# - underline
        self.role_pattern = re.compile(r"\[([^\]]+)\]#([^#]+)#")

        # Combined pattern for efficient scanning (finds ANY special construct)
        self._compile_combined_inline_pattern()

    def _compile_combined_inline_pattern(self) -> None:
        """Compile a combined regex pattern for efficient inline scanning.

        This single pattern matches ANY inline construct, allowing us to find
        the next special element in one search instead of trying all patterns.
        """
        patterns = []

        # Add unconstrained patterns first (higher priority)
        if self.options.support_unconstrained_formatting:
            patterns.append(r"\*\*([^\*]+?)\*\*")  # Unconstrained bold
            patterns.append(r"__([^_]+?)__")  # Unconstrained italic

        # Standard patterns
        patterns.extend(
            [
                r"(?<!\*)\*([^\*\s][^\*]*?)\*(?!\*)",  # Constrained bold
                r"(?<!_)_([^_\s][^_]*?)_(?!_)",  # Constrained italic
                r"`([^`]+?)`",  # Monospace
                r"~([^~]+?)~",  # Subscript
                r"\^([^\^]+?)\^",  # Superscript
                r"link:([^\[]+)\[([^\]]*)\]",  # Explicit link
                r"(https?://[^\s\[\]]+)",  # Auto-link
                r"image::([^\[]+)\[([^\]]*)\]",  # Block image
                r"image:([^\[]+)\[([^\]]*)\]",  # Inline image
                r"<<([^,\>]+)(?:,([^\>]+))?>>",  # Cross-reference
                r"\{([^\}]+)\}",  # Attribute reference
                r"(?:\+\+([^\+]+)\+\+|\+([^\+]+)\+|pass:\[([^\]]+)\])",  # Passthrough
                r"footnote:\[([^\]]+)\]",  # Footnote with inline content
                r"footnoteref:\[([^\],]+)(?:,([^\]]+))?\]",  # Footnote reference
                r"latexmath:\[(?:\$([^\$]+)\$|([^\]]+))\]",  # LaTeX math inline
                r"stem:\[(?:\$([^\$]+)\$|([^\]]+))\]",  # STEM math inline
                r"\[([^\]]+)\]#([^#]+)#",  # Role (strikethrough, underline, etc.)
            ]
        )

        # Combine all patterns with alternation
        combined = "|".join(f"({p})" for p in patterns)
        self.combined_inline_pattern = re.compile(combined)

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
        content = self._load_text_content(input_data)

        # Reset parser state to prevent leakage across parse calls
        self.attributes = {}
        self.tokens = []
        self.current_token_index = 0
        self.pending_block_attrs = {}
        self._footnote_definitions = {}
        self._footnote_counter = 0

        # Emit progress event
        self._emit_progress("started", "Parsing AsciiDoc", current=0, total=100)

        # Tokenize
        lexer = AsciiDocLexer(content)
        self.tokens = lexer.tokenize()
        self.current_token_index = 0

        self._emit_progress("item_done", "Tokenization complete", current=30, total=100, item_type="tokenization")

        # Parse tokens into AST
        children = self._parse_document()

        # Append footnote definitions at the end of the document
        self._append_footnote_definitions(children)

        # Extract metadata
        metadata = self.extract_metadata(content)

        self._emit_progress("finished", "Parsing complete", current=100, total=100)

        return Document(children=children, metadata=metadata.to_dict())

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
        """Skip over blank lines and optionally comments.

        Comments are only skipped if strip_comments option is True.
        Otherwise, comments are preserved for conversion to Comment nodes.
        """
        while True:
            token_type = self._current_token().type
            if token_type == TokenType.BLANK_LINE:
                self._advance()
            elif token_type == TokenType.COMMENT and self.options.strip_comments:
                self._advance()
            else:
                break

    def _parse_block_attribute(self, attr_content: str) -> None:
        """Parse a block attribute and store in pending attributes.

        Parses AsciiDoc block attributes like:
        - [source,python] -> language: python
        - [#anchor-id] -> id: anchor-id
        - [.role-name] -> role: role-name
        - [options="header"] -> options: ["header"]
        - [NOTE], [TIP], etc. -> admonition: note/tip/etc.

        Parameters
        ----------
        attr_content : str
            Content inside the brackets

        """
        attr_content = attr_content.strip()

        # Check for anchor ID (#id)
        if attr_content.startswith("#"):
            self.pending_block_attrs["id"] = attr_content[1:]
            return

        # Check for role (.role)
        if attr_content.startswith("."):
            self.pending_block_attrs["role"] = attr_content[1:]
            return

        # Check for admonitions
        admonition_types = {"NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"}
        attr_upper = attr_content.upper()
        if attr_upper in admonition_types and self.options.parse_admonitions:
            # Mark this as an admonition
            self.pending_block_attrs["admonition"] = attr_upper.lower()
            return

        # Parse positional and named attributes
        # Simple parser: split by comma, handle key=value pairs
        parts = [p.strip() for p in attr_content.split(",")]

        for i, part in enumerate(parts):
            if "=" in part:
                # Named attribute: key="value" or key=value
                key, value = part.split("=", 1)
                key = key.strip()
                value = value.strip().strip("\"'")
                self.pending_block_attrs[key] = value
            elif i == 0:
                # First positional: often block type (e.g., "source")
                self.pending_block_attrs["type"] = part
            elif i == 1 and parts[0] in ("source", "listing"):
                # Second positional after "source": language
                self.pending_block_attrs["language"] = part
            else:
                # Other positional attributes
                if "positional" not in self.pending_block_attrs:
                    self.pending_block_attrs["positional"] = []
                self.pending_block_attrs["positional"].append(part)

    def _consume_pending_attrs(self) -> dict[str, Any]:
        """Consume and clear pending block attributes.

        Returns
        -------
        dict[str, Any]
            Pending attributes (now cleared)

        """
        attrs = self.pending_block_attrs.copy()
        self.pending_block_attrs = {}
        return attrs

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
                is_unset = token.metadata.get("unset", False) if token.metadata else False

                if is_unset:
                    # Remove attribute if it exists
                    self.attributes.pop(attr_name, None)
                else:
                    # Set attribute value
                    attr_value = token.metadata.get("value", "") if token.metadata else ""
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

        # Comment (block-level)
        if token.type == TokenType.COMMENT:
            return self._parse_comment()

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

        if token.type == TokenType.LITERAL_BLOCK_DELIMITER:
            return self._parse_literal_block()

        if token.type == TokenType.SIDEBAR_BLOCK_DELIMITER:
            return self._parse_sidebar_block()

        if token.type == TokenType.EXAMPLE_BLOCK_DELIMITER:
            return self._parse_example_block()

        if token.type == TokenType.TABLE_DELIMITER:
            return self._parse_table()

        # Thematic break
        if token.type == TokenType.THEMATIC_BREAK:
            self._advance()
            return ThematicBreak()

        # Block attribute (preceding next block)
        if token.type == TokenType.BLOCK_ATTRIBUTE:
            self._parse_block_attribute(token.content)
            self._advance()
            return None

        # Anchor (preceding next block)
        if token.type == TokenType.ANCHOR:
            self.pending_block_attrs["id"] = token.content
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
        # Consume pending attributes
        attrs = self._consume_pending_attrs()

        token = self._advance()
        level = token.metadata.get("level", 1) if token.metadata else 1
        content = self._parse_inline(token.content)

        # Apply anchor ID if present
        metadata = {}
        if "id" in attrs:
            metadata["id"] = attrs["id"]

        if metadata:
            return Heading(level=level, content=content, metadata=metadata)
        else:
            return Heading(level=level, content=content)

    def _parse_comment(self) -> Comment:
        """Parse a comment block.

        Returns
        -------
        Comment
            Comment node with comment_type='asciidoc'

        """
        token = self._advance()
        content = token.content
        metadata = {"comment_type": "asciidoc"}
        return Comment(content=content, metadata=metadata)

    def _parse_paragraph(self) -> Paragraph | BlockQuote:
        """Parse a paragraph (consecutive text lines).

        Supports hard line breaks via trailing space+plus (` +`).
        If an admonition attribute is pending, wraps the paragraph in BlockQuote.

        Returns
        -------
        Paragraph or BlockQuote
            Paragraph node, or BlockQuote if admonition

        """
        # Consume pending attributes
        attrs = self._consume_pending_attrs()

        lines = []

        # Collect consecutive text lines
        while self._current_token().type == TokenType.TEXT_LINE:
            token = self._advance()
            lines.append(token.content)

            # Check if next is still text (not separated by blank line)
            if self._current_token().type == TokenType.BLANK_LINE:
                break

        # Process lines with hard break support
        if self.options.honor_hard_breaks:
            content: list[Node] = []

            for i, line in enumerate(lines):
                # Check for hard line break marker (trailing space + plus)
                has_hard_break = line.endswith(" +")

                # Strip the hard break marker if present
                if has_hard_break:
                    line = line[:-2].rstrip()  # Remove ' +' and any additional trailing spaces

                # Parse inline content for this line
                if line:  # Only parse non-empty lines
                    line_nodes = self._parse_inline(line)
                    content.extend(line_nodes)

                # Add line break if needed
                if has_hard_break:
                    content.append(LineBreak())
                elif i < len(lines) - 1:
                    # Add space between lines (unless it's the last line or has hard break)
                    if content and not isinstance(content[-1], LineBreak):
                        # Merge space into previous text node if possible
                        if content and isinstance(content[-1], Text):
                            content[-1] = Text(content=content[-1].content + " ")
                        else:
                            content.append(Text(content=" "))

        else:
            # Original behavior: join all lines with spaces
            text = " ".join(lines)
            content = self._parse_inline(text)

        # Apply metadata if present
        metadata = {}
        if "id" in attrs:
            metadata["id"] = attrs["id"]
        if "role" in attrs:
            metadata["role"] = attrs["role"]

        # Create paragraph
        if metadata:
            paragraph = Paragraph(content=content, metadata=metadata)
        else:
            paragraph = Paragraph(content=content)

        # If this is an admonition, wrap in BlockQuote with role
        if "admonition" in attrs:
            admonition_type = attrs["admonition"]
            admonition_metadata = {"role": admonition_type}
            return BlockQuote(children=[paragraph], metadata=admonition_metadata)

        return paragraph

    def _preprocess_escapes(self, text: str) -> tuple[str, dict[str, str]]:
        """Preprocess text to handle escape sequences.

        Parameters
        ----------
        text : str
            Text to preprocess

        Returns
        -------
        tuple[str, dict[str, str]]
            Preprocessed text and escape mapping

        """
        escape_map: dict[str, str] = {}
        counter = 0

        # Find all escaped characters: \* \_ \{ \+ \# \! \: etc.
        escaped_chars_pattern = re.compile(r"\\([\*_`~\^\{\}\[\]\\+#!:])")

        def replace_escape(match: re.Match[str]) -> str:
            nonlocal counter
            placeholder = f"{self._escape_placeholder}{counter}{self._escape_placeholder}"
            escape_map[placeholder] = match.group(1)  # Store the escaped character
            counter += 1
            return placeholder

        preprocessed = escaped_chars_pattern.sub(replace_escape, text)
        return preprocessed, escape_map

    def _postprocess_escapes(self, text: str, escape_map: dict[str, str]) -> str:
        """Restore escaped characters after processing.

        Parameters
        ----------
        text : str
            Text to postprocess
        escape_map : dict[str, str]
            Escape mapping from preprocessing

        Returns
        -------
        str
            Text with escapes restored

        """
        result = text
        for placeholder, char in escape_map.items():
            result = result.replace(placeholder, char)
        return result

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

        # Preprocess escapes
        preprocessed, escape_map = self._preprocess_escapes(text)

        # Process inline formatting using a state-based approach
        # This handles nested and overlapping formats correctly
        nodes = self._parse_inline_recursive(preprocessed, escape_map)

        return nodes

    def _try_parse_passthrough(self, text: str, escape_map: dict[str, str]) -> tuple[list[Node], int] | None:
        """Try to parse passthrough pattern at start of text.

        Parameters
        ----------
        text : str
            Text to parse
        escape_map : dict[str, str]
            Escape mapping

        Returns
        -------
        tuple[list[Node], int] or None
            (nodes, pos_advance) if matched, None otherwise

        """
        match = self.passthrough_pattern.match(text)
        if match:
            passthrough_content = match.group(1) or match.group(2) or match.group(3)
            passthrough_content = self._postprocess_escapes(passthrough_content, escape_map)
            return [HTMLInline(content=passthrough_content)], match.end()
        return None

    def _try_parse_image(self, text: str, escape_map: dict[str, str]) -> tuple[list[Node], int] | None:
        """Try to parse image pattern at start of text.

        Parameters
        ----------
        text : str
            Text to parse
        escape_map : dict[str, str]
            Escape mapping

        Returns
        -------
        tuple[list[Node], int] or None
            (nodes, pos_advance) if matched, None otherwise

        """
        match = self.image_block_pattern.match(text)
        if not match:
            match = self.image_inline_pattern.match(text)
        if match:
            url = match.group(1)
            alt_text = match.group(2) if len(match.groups()) >= 2 else ""
            url = self._postprocess_escapes(url, escape_map)
            alt_text = self._postprocess_escapes(alt_text, escape_map)
            url = sanitize_url(url)
            return [Image(url=url, alt_text=alt_text)], match.end()
        return None

    def _try_parse_links(self, text: str, escape_map: dict[str, str]) -> tuple[list[Node], int] | None:
        """Try to parse link patterns at start of text.

        Parameters
        ----------
        text : str
            Text to parse
        escape_map : dict[str, str]
            Escape mapping

        Returns
        -------
        tuple[list[Node], int] or None
            (nodes, pos_advance) if matched, None otherwise

        """
        match = self.link_pattern.match(text)
        if match:
            url = match.group(1)
            link_text = match.group(2)
            url = self._postprocess_escapes(url, escape_map)
            url = sanitize_url(url)
            content = self._parse_inline_recursive(link_text, escape_map) if link_text else [Text(content=url)]
            return [Link(url=url, content=content)], match.end()

        match = self.auto_link_pattern.match(text)
        if match:
            url = match.group(1)
            url = sanitize_url(url)
            return [Link(url=url, content=[Text(content=url)])], match.end()

        match = self.xref_pattern.match(text)
        if match:
            ref_id = match.group(1)
            ref_text = match.group(2) if len(match.groups()) >= 2 and match.group(2) else ref_id
            url = sanitize_url(f"#{ref_id}")
            return [Link(url=url, content=[Text(content=ref_text)])], match.end()

        return None

    def _try_parse_attribute_ref(self, text: str, escape_map: dict[str, str]) -> tuple[list[Node], int] | None:
        """Try to parse attribute reference at start of text.

        Parameters
        ----------
        text : str
            Text to parse
        escape_map : dict[str, str]
            Escape mapping

        Returns
        -------
        tuple[list[Node], int] or None
            (nodes, pos_advance) if matched, None otherwise

        """
        if not self.options.resolve_attribute_refs:
            return None

        match = self.attr_ref_pattern.match(text)
        if match:
            attr_name = match.group(1)
            if self._escape_placeholder not in attr_name:
                if attr_name in self.attributes:
                    attr_value = self.attributes[attr_name]
                elif self.options.attribute_missing_policy == "blank":
                    attr_value = ""
                elif self.options.attribute_missing_policy == "warn":
                    logger.warning(f"Undefined attribute reference: {{{attr_name}}}", stacklevel=2)
                    attr_value = f"{{{attr_name}}}"
                else:  # keep
                    attr_value = f"{{{attr_name}}}"
                return [Text(content=attr_value)], match.end()
        return None

    def _try_parse_formatting(self, text: str, escape_map: dict[str, str]) -> tuple[list[Node], int] | None:
        """Try to parse formatting patterns at start of text.

        Parameters
        ----------
        text : str
            Text to parse
        escape_map : dict[str, str]
            Escape mapping

        Returns
        -------
        tuple[list[Node], int] or None
            (nodes, pos_advance) if matched, None otherwise

        """
        if self.bold_unconstrained_pattern:
            match = self.bold_unconstrained_pattern.match(text)
            if match:
                inner_nodes = self._parse_inline_recursive(match.group(1), escape_map)
                return [Strong(content=inner_nodes)], match.end()

        match = self.bold_pattern.match(text)
        if match:
            inner_nodes = self._parse_inline_recursive(match.group(1), escape_map)
            return [Strong(content=inner_nodes)], match.end()

        if self.italic_unconstrained_pattern:
            match = self.italic_unconstrained_pattern.match(text)
            if match:
                inner_nodes = self._parse_inline_recursive(match.group(1), escape_map)
                return [Emphasis(content=inner_nodes)], match.end()

        match = self.italic_pattern.match(text)
        if match:
            inner_nodes = self._parse_inline_recursive(match.group(1), escape_map)
            return [Emphasis(content=inner_nodes)], match.end()

        match = self.mono_pattern.match(text)
        if match:
            code_text = self._postprocess_escapes(match.group(1), escape_map)
            return [Code(content=code_text)], match.end()

        match = self.superscript_pattern.match(text)
        if match:
            inner_nodes = self._parse_inline_recursive(match.group(1), escape_map)
            return [Superscript(content=inner_nodes)], match.end()

        match = self.subscript_pattern.match(text)
        if match:
            inner_nodes = self._parse_inline_recursive(match.group(1), escape_map)
            return [Subscript(content=inner_nodes)], match.end()

        return None

    def _try_parse_footnotes(self, text: str, escape_map: dict[str, str]) -> tuple[list[Node], int] | None:
        """Try to parse footnote patterns at start of text.

        Parameters
        ----------
        text : str
            Text to parse
        escape_map : dict[str, str]
            Escape mapping

        Returns
        -------
        tuple[list[Node], int] or None
            (nodes, pos_advance) if matched, None otherwise

        """
        match = self.footnote_pattern.match(text)
        if match:
            footnote_text = self._postprocess_escapes(match.group(1), escape_map)
            self._footnote_counter += 1
            identifier = str(self._footnote_counter)
            self._footnote_definitions[identifier] = footnote_text
            return [FootnoteReference(identifier=identifier)], match.end()

        match = self.footnoteref_pattern.match(text)
        if match:
            identifier = match.group(1).strip()
            footnote_ref_text: str | None = match.group(2) if len(match.groups()) >= 2 and match.group(2) else None
            if footnote_ref_text:
                processed_text = self._postprocess_escapes(footnote_ref_text, escape_map)
                if identifier not in self._footnote_definitions:
                    self._footnote_definitions[identifier] = processed_text
            return [FootnoteReference(identifier=identifier)], match.end()

        return None

    def _try_parse_math(self, text: str, escape_map: dict[str, str]) -> tuple[list[Node], int] | None:
        """Try to parse math patterns at start of text.

        Parameters
        ----------
        text : str
            Text to parse
        escape_map : dict[str, str]
            Escape mapping

        Returns
        -------
        tuple[list[Node], int] or None
            (nodes, pos_advance) if matched, None otherwise

        """
        match = self.latexmath_inline_pattern.match(text)
        if match:
            math_content = match.group(1) if match.group(1) else match.group(2)
            math_content = self._postprocess_escapes(math_content, escape_map)
            return [MathInline(content=math_content, notation="latex")], match.end()

        match = self.stem_inline_pattern.match(text)
        if match:
            math_content = match.group(1) if match.group(1) else match.group(2)
            math_content = self._postprocess_escapes(math_content, escape_map)
            return [MathInline(content=math_content, notation="latex")], match.end()

        return None

    def _try_parse_role(self, text: str, escape_map: dict[str, str]) -> tuple[list[Node], int] | None:
        """Try to parse role pattern at start of text.

        Parameters
        ----------
        text : str
            Text to parse
        escape_map : dict[str, str]
            Escape mapping

        Returns
        -------
        tuple[list[Node], int] or None
            (nodes, pos_advance) if matched, None otherwise

        """
        match = self.role_pattern.match(text)
        if match:
            role = match.group(1).lower().strip()
            role_text = match.group(2)
            inner_nodes = self._parse_inline_recursive(role_text, escape_map)

            if role == "line-through":
                return [Strikethrough(content=inner_nodes)], match.end()
            elif role == "underline":
                return [Underline(content=inner_nodes)], match.end()
            else:
                return inner_nodes, match.end()

        return None

    def _parse_inline_recursive(self, text: str, escape_map: dict[str, str]) -> list[Node]:
        """Recursively parse inline formatting.

        Parameters
        ----------
        text : str
            Text to parse (preprocessed)
        escape_map : dict[str, str]
            Escape mapping for postprocessing

        Returns
        -------
        list[Node]
            List of inline nodes

        """
        nodes: list[Node] = []
        pos = 0

        while pos < len(text):
            remaining = text[pos:]

            # Try each pattern handler in order
            result = (
                self._try_parse_passthrough(remaining, escape_map)
                or self._try_parse_image(remaining, escape_map)
                or self._try_parse_links(remaining, escape_map)
                or self._try_parse_attribute_ref(remaining, escape_map)
                or self._try_parse_formatting(remaining, escape_map)
                or self._try_parse_footnotes(remaining, escape_map)
                or self._try_parse_math(remaining, escape_map)
                or self._try_parse_role(remaining, escape_map)
            )

            if result:
                parsed_nodes, advance = result
                nodes.extend(parsed_nodes)
                pos += advance
            else:
                # No pattern matched - consume text until next special construct
                next_match = self.combined_inline_pattern.search(remaining)
                next_special = next_match.start() if next_match else len(remaining)

                text_content = remaining[:next_special]
                if text_content:
                    text_content = self._postprocess_escapes(text_content, escape_map)
                    if nodes and isinstance(nodes[-1], Text):
                        nodes[-1] = Text(content=nodes[-1].content + text_content)
                    else:
                        nodes.append(Text(content=text_content))

                pos += next_special

        return nodes

    def _append_footnote_definitions(self, children: list[Node]) -> None:
        """Append collected footnote definitions to the end of the document.

        Parameters
        ----------
        children : list[Node]
            List of AST nodes to append footnote definitions to

        Notes
        -----
        This method processes the collected footnote definitions and appends
        FootnoteDefinition nodes at the end of the document for proper AST
        representation. Footnote content is parsed as inline text.

        """
        if not self._footnote_definitions:
            return

        # Append each footnote definition
        for identifier, footnote_text in self._footnote_definitions.items():
            # Parse the footnote content as inline text
            footnote_content = self._parse_inline(footnote_text)
            # Wrap in a paragraph
            content_nodes = [Paragraph(content=footnote_content)]
            # Create and append the footnote definition
            children.append(FootnoteDefinition(identifier=identifier, content=cast(list[Node], content_nodes)))

    def _parse_list(self) -> List | list[Node]:
        """Parse an ordered or unordered list with nesting support.

        Uses ListBuilder to handle proper nesting based on level metadata.

        Returns
        -------
        List or list[Node]
            Single list node or list of top-level lists if multiple roots

        """
        # Create a ListBuilder for managing nesting
        list_builder = ListBuilder()

        # Parse consecutive list items
        while True:
            token = self._current_token()

            # Check if this is a list item
            if token.type not in (TokenType.UNORDERED_LIST, TokenType.ORDERED_LIST, TokenType.CHECKLIST_ITEM):
                break

            # Extract level and ordered flag
            level = token.metadata.get("level", 1) if token.metadata else 1
            ordered = token.type == TokenType.ORDERED_LIST

            # Get task status for checklist items
            task_status: Literal["checked", "unchecked"] | None = None
            if token.type == TokenType.CHECKLIST_ITEM:
                is_checked = token.metadata.get("checked") if token.metadata else False
                task_status = "checked" if is_checked else "unchecked"

            # Parse the list item content
            content_text = token.content
            self._advance()  # Consume the list item token

            # Parse inline content and wrap in paragraph
            content_nodes = self._parse_inline(content_text)
            item_content: list[Node] = [Paragraph(content=content_nodes)]

            # Add to builder with proper level
            list_builder.add_item(level=level, ordered=ordered, content=item_content, task_status=task_status)

            # Skip blank line after item if present
            if self._current_token().type == TokenType.BLANK_LINE:
                self._advance()

        # Get the built document and extract the lists
        built_doc = list_builder.get_document()

        # Return single list if there's only one, otherwise return all
        if len(built_doc.children) == 1:
            return cast(List, built_doc.children[0])
        else:
            return cast(list[Node], built_doc.children)

    def _parse_description_list(self) -> DefinitionList:
        """Parse a description list with multi-line support.

        Supports multi-line descriptions and nested blocks within descriptions.
        Continuation lines must be indented or preceded by an explicit continuation (+).

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
            description_text = (token.metadata.get("description", "") if token.metadata else "").strip()

            # Collect description content nodes
            desc_nodes: list[Node] = []

            # Add first-line description if present
            if description_text:
                desc_content = self._parse_inline(description_text)
                desc_nodes.append(Paragraph(content=desc_content))

            # Check for continuation lines (indented text or explicit blocks)
            # Continue while we have text lines that are indented or continuation markers
            while self._current_token().type in (TokenType.TEXT_LINE, TokenType.BLANK_LINE):
                next_token = self._current_token()

                # If it's a blank line, check if the next non-blank is still part of description
                if next_token.type == TokenType.BLANK_LINE:
                    # Peek ahead to see if there's more indented content
                    saved_index = self.current_token_index
                    self._advance()  # Skip blank line

                    peek_token = self._current_token()
                    # If next is indented text, it's part of description
                    if peek_token.type == TokenType.TEXT_LINE and peek_token.indent > 0:
                        # Continue collecting description
                        continue
                    else:
                        # End of description, restore position
                        self.current_token_index = saved_index
                        break

                # Check if this line is indented (continuation)
                if next_token.type == TokenType.TEXT_LINE and next_token.indent > 0:
                    self._advance()
                    # Add continuation line to description
                    line_content = self._parse_inline(next_token.content)
                    desc_nodes.append(Paragraph(content=line_content))
                else:
                    # Not indented, end of description
                    break

            # Create description from collected nodes
            if desc_nodes:
                descriptions.append(DefinitionDescription(content=desc_nodes))

            items.append((term, descriptions))

            # Skip trailing blank line
            if self._current_token().type == TokenType.BLANK_LINE:
                self._advance()

        return DefinitionList(items=items)

    def _parse_code_block(self) -> CodeBlock | MathBlock:
        """Parse a code block or math block.

        Returns
        -------
        CodeBlock | MathBlock
            Code block or math block node

        """
        # Consume pending attributes (may contain language info or math type)
        attrs = self._consume_pending_attrs()

        # Skip opening delimiter
        self._advance()

        # Check if this is a math block
        block_type = attrs.get("type", "").lower()
        is_math_block = block_type in ("latexmath", "stem")

        # Extract language from block attributes if present
        language: Optional[str] = attrs.get("language")

        # Collect content until closing delimiter
        lines, _closed = parse_delimited_block(
            current_token_fn=self._current_token,
            advance_fn=self._advance,
            opening_delimiter_type=TokenType.CODE_BLOCK_DELIMITER,
            closing_delimiter_type=TokenType.CODE_BLOCK_DELIMITER,
            eof_type=TokenType.EOF,
            collect_mode="lines",
        )

        content = "\n".join(lines)

        # Apply metadata if present
        metadata = {}
        if "id" in attrs:
            metadata["id"] = attrs["id"]

        # Return MathBlock for latexmath or stem blocks
        if is_math_block:
            if metadata:
                return MathBlock(content=content, notation="latex", metadata=metadata)
            else:
                return MathBlock(content=content, notation="latex")

        # Return CodeBlock for regular code blocks
        if metadata:
            return CodeBlock(content=content, language=language, metadata=metadata)
        else:
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
        children, _closed = parse_delimited_block(
            current_token_fn=self._current_token,
            advance_fn=self._advance,
            opening_delimiter_type=TokenType.QUOTE_BLOCK_DELIMITER,
            closing_delimiter_type=TokenType.QUOTE_BLOCK_DELIMITER,
            eof_type=TokenType.EOF,
            collect_mode="blocks",
            parse_block_fn=self._parse_block,
        )

        return BlockQuote(children=cast(list[Node], children))

    def _parse_literal_block(self) -> CodeBlock:
        """Parse a literal block.

        Literal blocks (....) render content as-is without syntax highlighting.

        Returns
        -------
        CodeBlock
            Code block node without language

        """
        # Consume pending attributes
        attrs = self._consume_pending_attrs()

        # Skip opening delimiter
        self._advance()

        # Collect content until closing delimiter
        lines, _closed = parse_delimited_block(
            current_token_fn=self._current_token,
            advance_fn=self._advance,
            opening_delimiter_type=TokenType.LITERAL_BLOCK_DELIMITER,
            closing_delimiter_type=TokenType.LITERAL_BLOCK_DELIMITER,
            eof_type=TokenType.EOF,
            collect_mode="lines",
        )

        content = "\n".join(lines)

        # Apply metadata if present
        metadata = {}
        if "id" in attrs:
            metadata["id"] = attrs["id"]

        if metadata:
            return CodeBlock(content=content, language=None, metadata=metadata)
        else:
            return CodeBlock(content=content, language=None)

    def _parse_sidebar_block(self) -> BlockQuote:
        """Parse a sidebar block.

        Sidebar blocks (****) are rendered as block quotes with role='sidebar'.

        Returns
        -------
        BlockQuote
            Block quote with sidebar role

        """
        # Consume pending attributes
        attrs = self._consume_pending_attrs()

        # Skip opening delimiter
        self._advance()

        # Collect content until closing delimiter
        children, _closed = parse_delimited_block(
            current_token_fn=self._current_token,
            advance_fn=self._advance,
            opening_delimiter_type=TokenType.SIDEBAR_BLOCK_DELIMITER,
            closing_delimiter_type=TokenType.SIDEBAR_BLOCK_DELIMITER,
            eof_type=TokenType.EOF,
            collect_mode="blocks",
            parse_block_fn=self._parse_block,
        )

        # Apply metadata with sidebar role
        metadata = {"role": "sidebar"}
        if "id" in attrs:
            metadata["id"] = attrs["id"]

        return BlockQuote(children=cast(list[Node], children), metadata=metadata)

    def _parse_example_block(self) -> BlockQuote | HTMLBlock:
        """Parse an example block or HTML passthrough block.

        Example blocks (====) are rendered as block quotes with role='example'.
        If the block has a "pass" or "passthrough" role/type, it's rendered as HTMLBlock.

        WARNING: HTML passthrough blocks should be sanitized by the renderer to
        prevent XSS attacks.

        Returns
        -------
        BlockQuote | HTMLBlock
            Block quote with example role, or HTMLBlock for passthrough

        """
        # Consume pending attributes
        attrs = self._consume_pending_attrs()

        # Skip opening delimiter
        self._advance()

        # Check if this is a passthrough block (HTML block)
        block_type = attrs.get("type", "").lower()
        block_role = attrs.get("role", "").lower()
        is_passthrough = block_type in ("pass", "passthrough") or block_role in ("pass", "passthrough")

        if is_passthrough:
            # Collect content as lines (raw HTML)
            lines, _closed = parse_delimited_block(
                current_token_fn=self._current_token,
                advance_fn=self._advance,
                opening_delimiter_type=TokenType.EXAMPLE_BLOCK_DELIMITER,
                closing_delimiter_type=TokenType.EXAMPLE_BLOCK_DELIMITER,
                eof_type=TokenType.EOF,
                collect_mode="lines",
            )
            content = "\n".join(lines)

            # Apply metadata if present
            metadata = {}
            if "id" in attrs:
                metadata["id"] = attrs["id"]

            if metadata:
                return HTMLBlock(content=content, metadata=metadata)
            else:
                return HTMLBlock(content=content)

        # Regular example block - collect as blocks
        children, _closed = parse_delimited_block(
            current_token_fn=self._current_token,
            advance_fn=self._advance,
            opening_delimiter_type=TokenType.EXAMPLE_BLOCK_DELIMITER,
            closing_delimiter_type=TokenType.EXAMPLE_BLOCK_DELIMITER,
            eof_type=TokenType.EOF,
            collect_mode="blocks",
            parse_block_fn=self._parse_block,
        )

        # Apply metadata with example role
        metadata = {"role": "example"}
        if "id" in attrs:
            metadata["id"] = attrs["id"]

        return BlockQuote(children=cast(list[Node], children), metadata=metadata)

    def _parse_table(self) -> Table:
        """Parse a table.

        Returns
        -------
        Table
            Table node

        """
        # Consume pending attributes
        attrs = self._consume_pending_attrs()

        # Skip opening delimiter
        self._advance()

        rows: list[TableRow] = []
        header: Optional[TableRow] = None

        # Determine header detection mode
        header_mode = self.options.table_header_detection
        has_header = True  # Default assumption

        # Check block attributes for header options
        if header_mode == "attribute-based":
            options_str = attrs.get("options", "")
            # Support both explicit "header" and "noheader" options
            # Check noheader first to avoid substring match issues
            if "noheader" in options_str:
                has_header = False
            elif "header" in options_str:
                has_header = True
            # If neither is specified, use default (has_header = True)
        elif header_mode == "first-row":
            has_header = True
        # "auto" mode: could implement heuristics, for now treat as first-row

        # Collect table rows
        row_index = 0
        while self._current_token().type != TokenType.TABLE_DELIMITER:
            if self._current_token().type == TokenType.EOF:
                break

            token = self._current_token()

            if token.type == TokenType.TEXT_LINE and "|" in token.content:
                row = self._parse_table_row(token.content)

                # First row handling based on header detection
                if row_index == 0 and has_header:
                    header = row
                    header.is_header = True
                else:
                    rows.append(row)

                row_index += 1

            self._advance()

        # Skip closing delimiter
        if self._current_token().type == TokenType.TABLE_DELIMITER:
            self._advance()

        return Table(header=header, rows=rows)

    def _parse_table_row(self, line: str) -> TableRow:
        r"""Parse a table row from a line.

        Handles escaped pipes (\|) within cells and preserves empty cells.
        Optionally parses colspan/rowspan syntax like 2+|cell or .3+|cell.

        This uses a single-pass approach:
        1. Replace escaped pipes with placeholder
        2. Split on literal '|'
        3. Parse span specifications (if enabled)
        4. Restore placeholder in cell content

        Parameters
        ----------
        line : str
            Table row line

        Returns
        -------
        TableRow
            Table row node

        """
        # Placeholder for escaped pipes (unlikely to appear in normal content)
        escaped_pipe_placeholder = "\x00PIPE\x00"

        # Single-pass optimization: replace escaped pipes, then split on literal pipes
        line = line.replace(r"\|", escaped_pipe_placeholder)
        parts = line.split("|")

        # Remove leading empty part caused by starting | delimiter
        # AsciiDoc rows always start with |, which creates a leading empty string
        # For example: |cell1|cell2| produces ['', 'cell1', 'cell2', '']
        if parts and parts[0].strip() == "":
            parts = parts[1:]

        # Keep trailing empty parts as they represent intentional empty cells
        # For example: |A|B| should produce cells [A, B, empty]

        cells: list[TableCell] = []

        # Track pending span specs from previous parts
        pending_colspan: int | None = None
        pending_rowspan: int | None = None

        for part in parts:
            # Restore escaped pipes
            part = part.replace(escaped_pipe_placeholder, "|")

            # Parse colspan/rowspan if enabled
            colspan = pending_colspan  # Use pending span from previous part
            rowspan = pending_rowspan
            pending_colspan = None  # Reset pending
            pending_rowspan = None

            if self.options.parse_table_spans:
                # Pattern: [colspan].[rowspan]+
                # Examples: 2+, .3+, 2.3+
                # Also supports: 2* for duplication (treated as colspan)

                span_pattern = r"^(\d+)?\.?(\d+)?([+*])\s*"
                match = re.match(span_pattern, part.strip())

                if match:
                    col_spec = match.group(1)
                    row_spec = match.group(2)
                    operator = match.group(3)

                    if operator == "+":
                        # Standard span syntax
                        if col_spec and not row_spec:
                            # Just colspan: 2+
                            colspan = int(col_spec)
                        elif row_spec and not col_spec:
                            # Just rowspan: .3+
                            rowspan = int(row_spec)
                        elif col_spec and row_spec:
                            # Both: 2.3+
                            colspan = int(col_spec)
                            rowspan = int(row_spec)
                    elif operator == "*":
                        # Duplication syntax (treat as colspan for simplicity)
                        if col_spec:
                            colspan = int(col_spec)

                    # Remove the span specification from content
                    part = part[match.end() :]

            # Strip whitespace but preserve empty cells
            content_text = part.strip()

            # If content is empty and we have a span, this is likely a standalone
            # span spec (like |2+| where the content is in the next part)
            # Save the span for the next cell and skip this part
            if not content_text and (colspan is not None or rowspan is not None):
                pending_colspan = colspan
                pending_rowspan = rowspan
                continue

            content = self._parse_inline(content_text)

            # Create cell with colspan/rowspan if present
            # TableCell expects colspan/rowspan as direct attributes, not in metadata
            cell_kwargs: dict[str, Any] = {"content": content}
            if colspan is not None:
                cell_kwargs["colspan"] = colspan
            if rowspan is not None:
                cell_kwargs["rowspan"] = rowspan

            cells.append(TableCell(**cell_kwargs))

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
        if "title" in self.attributes:
            metadata.title = self.attributes["title"]
        if "author" in self.attributes:
            metadata.author = self.attributes["author"]
        if "description" in self.attributes:
            metadata.subject = self.attributes["description"]  # subject maps to description in to_dict()
        if "keywords" in self.attributes:
            # Parse keywords (comma or space separated)
            keywords_str = self.attributes["keywords"]
            if isinstance(keywords_str, str):
                metadata.keywords = [k.strip() for k in keywords_str.replace(",", " ").split() if k.strip()]
        if "lang" in self.attributes or "language" in self.attributes:
            metadata.language = self.attributes.get("lang") or self.attributes.get("language")

        # Revision metadata
        if "revnumber" in self.attributes:
            metadata.version = self.attributes["revnumber"]
        if "revdate" in self.attributes:
            metadata.custom["revdate"] = self.attributes["revdate"]

        # Store all other AsciiDoc attributes in custom field
        standard_fields = {"title", "author", "description", "keywords", "lang", "language", "revnumber", "revdate"}
        for key, value in self.attributes.items():
            if key not in standard_fields:
                metadata.custom[key] = value

        return metadata


# Converter metadata for registry auto-discovery
CONVERTER_METADATA = ConverterMetadata(
    format_name="asciidoc",
    extensions=[".adoc", ".asciidoc", ".asc"],
    mime_types=["text/asciidoc", "text/x-asciidoc"],
    magic_bytes=[],  # AsciiDoc is plain text, no magic bytes
    parser_class=AsciiDocParser,
    renderer_class="all2md.renderers.asciidoc.AsciiDocRenderer",
    renders_as_string=True,
    parser_required_packages=[],  # No external dependencies
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="",
    parser_options_class=AsciiDocOptions,
    renderer_options_class="all2md.options.asciidoc.AsciiDocRendererOptions",
    description="Parse and render AsciiDoc format",
    priority=10,
)
