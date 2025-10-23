#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/dokuwiki.py
"""DokuWiki markup to AST converter.

This module provides conversion from DokuWiki markup to AST representation
using custom regex-based parsing. It enables bidirectional transformation by parsing
DokuWiki markup into the same AST structure used for other formats.

"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import IO, Optional, Union

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Comment,
    CommentInline,
    Document,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
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
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.dokuwiki import DokuWikiParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.encoding import read_text_with_encoding_detection
from all2md.utils.html_sanitizer import sanitize_url
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


# =============================================================================
# Regex Patterns for DokuWiki Syntax
# =============================================================================

# Heading: ====== Level 1 ====== (6 equals), ===== Level 2 ===== (5 equals), etc.
# Level calculation: 7 - equals_count
HEADING_PATTERN = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$")

# Horizontal rule: ---- (4 or more dashes)
HORIZONTAL_RULE_PATTERN = re.compile(r"^-{4,}\s*$")

# List patterns: ordered (- ) and unordered (* )
# Lists can be nested with multiple spaces (2 spaces per level)
LIST_ITEM_PATTERN = re.compile(r"^(\s*)([\*\-])\s+(.+)$")

# Table row patterns: ^ for headers, | for regular cells
TABLE_ROW_PATTERN = re.compile(r"^[\|\^].+[\|\^]\s*$")

# Code block: <code> or <code language>
CODE_BLOCK_START_PATTERN = re.compile(r"^<code(?:\s+(\w+))?>\s*$", re.IGNORECASE)
CODE_BLOCK_END_PATTERN = re.compile(r"^</code>\s*$", re.IGNORECASE)

# Block quote: > at start of line
BLOCKQUOTE_PATTERN = re.compile(r"^>\s*(.*)$")

# Comment patterns: C-style /* */ and HTML <!-- -->
C_COMMENT_PATTERN = re.compile(r"/\*.*?\*/", re.DOTALL)
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)

# Plugin syntax pattern (for stripping or converting to HTML)
PLUGIN_PATTERN = re.compile(r"<(\w+)(?:\s+[^>]*)?>.*?</\1>", re.DOTALL | re.IGNORECASE)

# Inline patterns (processed in text content)
# Bold: **text**
BOLD_PATTERN = re.compile(r"\*\*(.*?)\*\*")
# Italic: //text//
ITALIC_PATTERN = re.compile(r"//(.*?)//")
# Underline: __text__
UNDERLINE_PATTERN = re.compile(r"__(.*?)__")
# Monospace: ''text'' (two single quotes)
MONOSPACE_PATTERN = re.compile(r"''(.*?)''")
# Strikethrough: <del>text</del>
STRIKETHROUGH_PATTERN = re.compile(r"<del>(.*?)</del>", re.IGNORECASE)
# Subscript: <sub>text</sub>
SUBSCRIPT_PATTERN = re.compile(r"<sub>(.*?)</sub>", re.IGNORECASE)
# Superscript: <sup>text</sup>
SUPERSCRIPT_PATTERN = re.compile(r"<sup>(.*?)</sup>", re.IGNORECASE)

# Links: [[url]] or [[url|text]] or [[wp>Article]] (interwiki)
LINK_PATTERN = re.compile(r"\[\[([^\|\]]+)(?:\|([^\]]+))?\]\]")
# Images: {{image.png}} or {{image.png|alt text}}
IMAGE_PATTERN = re.compile(r"\{\{([^\|\}]+)(?:\|([^\}]+))?\}\}")

# Line break: \\ (two backslashes)
LINE_BREAK_PATTERN = re.compile(r"\\\\")

# Footnote: ((footnote text))
FOOTNOTE_PATTERN = re.compile(r"\(\(([^\)]+)\)\)")


class DokuWikiParser(BaseParser):
    """Convert DokuWiki markup to AST representation.

    This converter uses custom regex-based parsing to process DokuWiki markup
    and builds an AST that matches the structure used throughout all2md, enabling
    bidirectional conversion and transformation pipelines.

    Parameters
    ----------
    options : DokuWikiParserOptions or None, default = None
        Parser configuration options
    progress_callback : ProgressCallback or None, default = None
        Optional callback for progress updates

    Examples
    --------
    Basic parsing:

        >>> parser = DokuWikiParser()
        >>> doc = parser.parse("====== Heading ======\\n\\nThis is **bold**.")

    With options:

        >>> options = DokuWikiParserOptions(parse_plugins=True)
        >>> parser = DokuWikiParser(options)
        >>> doc = parser.parse(dokuwiki_text)

    """

    def __init__(
        self,
        options: DokuWikiParserOptions | None = None,
        progress_callback: Optional[ProgressCallback] = None,
    ):
        """Initialize the DokuWiki parser with options and progress callback."""
        options = options or DokuWikiParserOptions()
        super().__init__(options, progress_callback)
        self.options: DokuWikiParserOptions = options
        self._footnote_definitions: dict[str, str] = {}  # identifier -> footnote content

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse DokuWiki input into AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            DokuWiki markup input to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw DokuWiki bytes
            - DokuWiki string

        Returns
        -------
        Document
            AST document node

        Raises
        ------
        ParsingError
            If parsing fails

        """
        # Load DokuWiki content from various input types
        dokuwiki_content = self._load_dokuwiki_content(input_data)

        # Reset parser state to prevent leakage across parse calls
        self._footnote_definitions = {}

        # Extract metadata before processing (do this before stripping comments)
        metadata = self.extract_metadata(dokuwiki_content)

        # Convert DokuWiki to AST
        try:
            children = self._process_content(dokuwiki_content)
        except Exception as e:
            raise ParsingError(f"Failed to parse DokuWiki markup: {e}") from e

        return Document(children=children, metadata=metadata.to_dict())

    @staticmethod
    def _load_dokuwiki_content(input_data: Union[str, Path, IO[bytes], bytes]) -> str:
        """Load DokuWiki content from various input types with encoding detection.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Input data to load

        Returns
        -------
        str
            DokuWiki content as string

        """
        if isinstance(input_data, bytes):
            return read_text_with_encoding_detection(input_data)

        if isinstance(input_data, str):
            # Check if it's a file path
            path = Path(input_data)
            if path.exists() and path.is_file():
                with open(path, "rb") as f:
                    return read_text_with_encoding_detection(f.read())
            # Otherwise treat as literal content
            return input_data

        if isinstance(input_data, Path):
            with open(input_data, "rb") as f:
                return read_text_with_encoding_detection(f.read())

        # File-like object
        if hasattr(input_data, "read"):
            content = input_data.read()
            if isinstance(content, bytes):
                return read_text_with_encoding_detection(content)
            return content

        raise ValueError(f"Unsupported input type: {type(input_data)}")

    def _extract_comments_from_text(self, text: str) -> list[tuple[str, int, int, str]]:
        """Extract comments from text, returning comment info with positions.

        Parameters
        ----------
        text : str
            Text content to extract comments from

        Returns
        -------
        list[tuple[str, int, int, str]]
            List of tuples: (comment_content, start_pos, end_pos, comment_style)
            where comment_style is 'c-style' or 'html'

        """
        comments: list[tuple[str, int, int, str]] = []

        # Find C-style comments /* ... */
        for match in C_COMMENT_PATTERN.finditer(text):
            # Extract content without delimiters
            full_match = match.group(0)
            content = full_match[2:-2].strip()  # Remove /* and */
            comments.append((content, match.start(), match.end(), "c-style"))

        # Find HTML comments <!-- ... -->
        for match in HTML_COMMENT_PATTERN.finditer(text):
            # Extract content without delimiters
            full_match = match.group(0)
            content = full_match[4:-3].strip()  # Remove <!-- and -->
            comments.append((content, match.start(), match.end(), "html"))

        # Sort by position
        comments.sort(key=lambda x: x[1])
        return comments

    def _process_content(self, content: str) -> list[Node]:
        """Process DokuWiki content into AST nodes.

        This is the main parsing method that processes the content line by line,
        using an inline buffer pattern to group inline elements into paragraphs.

        Parameters
        ----------
        content : str
            DokuWiki markup content

        Returns
        -------
        list[Node]
            List of block-level AST nodes

        """
        lines = content.split("\n")
        result: list[Node] = []
        inline_buffer: list[Node] = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # Skip empty lines - they separate blocks
            if not line.strip():
                # Flush inline buffer as paragraph
                if inline_buffer:
                    result.append(Paragraph(content=inline_buffer))
                    inline_buffer = []
                i += 1
                continue

            # Try to match block-level elements

            # Block-level comments (C-style or HTML comments on their own line)
            # Check if the line contains ONLY a comment (possibly with surrounding whitespace)
            # Check for C-style block comment
            c_comment_match = C_COMMENT_PATTERN.match(line.strip())
            if c_comment_match and c_comment_match.group(0) == line.strip():
                # Entire line is a comment
                if self.options.strip_comments:
                    # Skip the line entirely
                    i += 1
                    continue
                else:
                    # Treat as block comment node
                    if inline_buffer:
                        result.append(Paragraph(content=inline_buffer))
                        inline_buffer = []
                    comment_text = line.strip()[2:-2].strip()  # Remove /* and */
                    result.append(Comment(content=comment_text, metadata={"comment_type": "wiki"}))
                    i += 1
                    continue

            # Check for HTML block comment
            html_comment_match = HTML_COMMENT_PATTERN.match(line.strip())
            if html_comment_match and html_comment_match.group(0) == line.strip():
                # Entire line is a comment
                if self.options.strip_comments:
                    # Skip the line entirely
                    i += 1
                    continue
                else:
                    # Treat as block comment node
                    if inline_buffer:
                        result.append(Paragraph(content=inline_buffer))
                        inline_buffer = []
                    comment_text = line.strip()[4:-3].strip()  # Remove <!-- and -->
                    result.append(Comment(content=comment_text, metadata={"comment_type": "wiki"}))
                    i += 1
                    continue

            # Heading
            heading_match = HEADING_PATTERN.match(line)
            if heading_match:
                # Flush inline buffer first
                if inline_buffer:
                    result.append(Paragraph(content=inline_buffer))
                    inline_buffer = []

                equals_count = len(heading_match.group(1))
                level = 7 - equals_count  # DokuWiki: 6 equals = level 1
                heading_text = heading_match.group(2).strip()
                heading_content = self._process_inline(heading_text)
                result.append(Heading(level=level, content=heading_content))
                i += 1
                continue

            # Horizontal rule
            if HORIZONTAL_RULE_PATTERN.match(line):
                # Flush inline buffer first
                if inline_buffer:
                    result.append(Paragraph(content=inline_buffer))
                    inline_buffer = []

                result.append(ThematicBreak())
                i += 1
                continue

            # Code block
            code_start_match = CODE_BLOCK_START_PATTERN.match(line)
            if code_start_match:
                # Flush inline buffer first
                if inline_buffer:
                    result.append(Paragraph(content=inline_buffer))
                    inline_buffer = []

                code_block, new_i = self._parse_code_block(lines, i)
                if code_block:
                    result.append(code_block)
                i = new_i
                continue

            # List
            list_match = LIST_ITEM_PATTERN.match(line)
            if list_match:
                # Flush inline buffer first
                if inline_buffer:
                    result.append(Paragraph(content=inline_buffer))
                    inline_buffer = []

                list_node, new_i = self._parse_list(lines, i)
                if list_node:
                    result.append(list_node)
                i = new_i
                continue

            # Table
            if TABLE_ROW_PATTERN.match(line):
                # Flush inline buffer first
                if inline_buffer:
                    result.append(Paragraph(content=inline_buffer))
                    inline_buffer = []

                table_node, new_i = self._parse_table(lines, i)
                if table_node:
                    result.append(table_node)
                i = new_i
                continue

            # Block quote
            blockquote_match = BLOCKQUOTE_PATTERN.match(line)
            if blockquote_match:
                # Flush inline buffer first
                if inline_buffer:
                    result.append(Paragraph(content=inline_buffer))
                    inline_buffer = []

                blockquote_node, new_i = self._parse_blockquote(lines, i)
                if blockquote_node:
                    result.append(blockquote_node)
                i = new_i
                continue

            # Regular text line - add to inline buffer
            inline_nodes = self._process_inline(line)
            inline_buffer.extend(inline_nodes)
            # Add soft line break between lines in same paragraph
            if i + 1 < len(lines) and lines[i + 1].strip():
                inline_buffer.append(LineBreak(soft=True))
            i += 1

        # Flush remaining inline buffer
        if inline_buffer:
            result.append(Paragraph(content=inline_buffer))

        # Append footnote definitions at the end of the document
        self._append_footnote_definitions(result)

        return result

    def _append_footnote_definitions(self, result: list[Node]) -> None:
        """Append collected footnote definitions to the end of the document.

        Parameters
        ----------
        result : list[Node]
            List of AST nodes to append footnote definitions to

        Notes
        -----
        This method processes the collected footnote definitions and appends
        FootnoteDefinition nodes at the end of the document for proper AST
        representation.

        """
        if not self._footnote_definitions:
            return

        # Append each footnote definition
        for identifier, footnote_text in self._footnote_definitions.items():
            # Parse the footnote content as inline text
            footnote_content = self._process_inline(footnote_text)
            # Wrap in a paragraph
            content_nodes = [Paragraph(content=footnote_content)]
            # Create and append the footnote definition
            result.append(FootnoteDefinition(identifier=identifier, content=content_nodes))

    def _process_inline(self, text: str) -> list[Node]:
        """Process inline formatting in text.

        This method handles all inline formatting like bold, italic, links, images, etc.
        It processes patterns in a specific order to handle nesting correctly.

        Parameters
        ----------
        text : str
            Text content to process

        Returns
        -------
        list[Node]
            List of inline AST nodes

        """
        if not text:
            return []

        # Strip comments from text if option is enabled
        if self.options.strip_comments:
            text = C_COMMENT_PATTERN.sub("", text)
            text = HTML_COMMENT_PATTERN.sub("", text)
            if not text:
                return []

        # Process inline elements by finding the earliest match of any pattern
        # This handles overlapping and nested patterns correctly

        # Define patterns in order of precedence
        patterns = [
            ("image", IMAGE_PATTERN),  # Images before links to avoid confusion
            ("link", LINK_PATTERN),
            ("footnote", FOOTNOTE_PATTERN),
            ("bold", BOLD_PATTERN),
            ("italic", ITALIC_PATTERN),
            ("underline", UNDERLINE_PATTERN),
            ("monospace", MONOSPACE_PATTERN),
            ("strikethrough", STRIKETHROUGH_PATTERN),
            ("subscript", SUBSCRIPT_PATTERN),
            ("superscript", SUPERSCRIPT_PATTERN),
            ("linebreak", LINE_BREAK_PATTERN),
        ]

        # Add comment patterns if not stripping comments
        if not self.options.strip_comments:
            patterns.extend([
                ("c_comment", C_COMMENT_PATTERN),
                ("html_comment", HTML_COMMENT_PATTERN),
            ])

        # Find earliest match
        earliest_match = None
        earliest_pos = len(text)
        earliest_type = None

        for pattern_type, pattern in patterns:
            match = pattern.search(text)
            if match and match.start() < earliest_pos:
                earliest_match = match
                earliest_pos = match.start()
                earliest_type = pattern_type

        # If no match found, return plain text
        if not earliest_match:
            return [Text(content=text)] if text else []

        # Split into before, match, and after
        before = text[:earliest_match.start()]
        after = text[earliest_match.end() :]

        result: list[Node] = []

        # Add text before match
        if before:
            result.append(Text(content=before))

        # Process the matched pattern
        if earliest_type == "image":
            url = earliest_match.group(1).strip()
            alt_text = earliest_match.group(2).strip() if earliest_match.group(2) else ""
            # Sanitize URL
            url = sanitize_url(url)
            result.append(Image(url=url, alt_text=alt_text))

        elif earliest_type == "link":
            url = earliest_match.group(1).strip()
            link_text = earliest_match.group(2)

            # Handle interwiki links if enabled
            if self.options.parse_interwiki and ">" in url:
                # Interwiki link like [[wp>Article]]
                # Keep as-is in URL
                pass

            # Sanitize URL
            url = sanitize_url(url)

            if link_text:
                # Link with custom text
                link_content = self._process_inline(link_text.strip())
            else:
                # Link without text - use URL as text
                link_content = [Text(content=url)]

            result.append(Link(url=url, content=link_content))

        elif earliest_type == "footnote":
            # Footnote: ((text)) - create a reference with inline content
            footnote_text = earliest_match.group(1).strip()
            # For DokuWiki, footnotes are inline - generate a unique identifier
            import hashlib

            identifier = hashlib.md5(footnote_text.encode()).hexdigest()[:8]

            # Collect footnote definition for later appending to document
            if identifier not in self._footnote_definitions:
                self._footnote_definitions[identifier] = footnote_text

            result.append(FootnoteReference(identifier=identifier))

        elif earliest_type == "bold":
            inner_text = earliest_match.group(1)
            # Recursively process inner content for nested formatting
            inner_nodes = self._process_inline(inner_text)
            result.append(Strong(content=inner_nodes))

        elif earliest_type == "italic":
            inner_text = earliest_match.group(1)
            inner_nodes = self._process_inline(inner_text)
            result.append(Emphasis(content=inner_nodes))

        elif earliest_type == "underline":
            inner_text = earliest_match.group(1)
            inner_nodes = self._process_inline(inner_text)
            result.append(Underline(content=inner_nodes))

        elif earliest_type == "monospace":
            inner_text = earliest_match.group(1)
            # Monospace is typically not nested
            result.append(Code(content=inner_text))

        elif earliest_type == "strikethrough":
            inner_text = earliest_match.group(1)
            inner_nodes = self._process_inline(inner_text)
            result.append(Strikethrough(content=inner_nodes))

        elif earliest_type == "subscript":
            inner_text = earliest_match.group(1)
            inner_nodes = self._process_inline(inner_text)
            result.append(Subscript(content=inner_nodes))

        elif earliest_type == "superscript":
            inner_text = earliest_match.group(1)
            inner_nodes = self._process_inline(inner_text)
            result.append(Superscript(content=inner_nodes))

        elif earliest_type == "linebreak":
            # Hard line break
            result.append(LineBreak(soft=False))

        elif earliest_type == "c_comment":
            # C-style comment /* ... */
            comment_text = earliest_match.group(0)[2:-2].strip()  # Remove /* and */
            result.append(CommentInline(content=comment_text, metadata={"comment_type": "wiki"}))

        elif earliest_type == "html_comment":
            # HTML comment <!-- ... -->
            comment_text = earliest_match.group(0)[4:-3].strip()  # Remove <!-- and -->
            result.append(CommentInline(content=comment_text, metadata={"comment_type": "wiki"}))

        # Recursively process the text after the match
        if after:
            result.extend(self._process_inline(after))

        return result

    def _parse_code_block(self, lines: list[str], start_idx: int) -> tuple[CodeBlock | None, int]:
        """Parse a code block starting at the given line.

        Parameters
        ----------
        lines : list[str]
            All lines in the document
        start_idx : int
            Index of the <code> line

        Returns
        -------
        tuple[CodeBlock | None, int]
            Parsed code block node and the index after the </code> line

        """
        start_line = lines[start_idx]
        code_start_match = CODE_BLOCK_START_PATTERN.match(start_line)
        if not code_start_match:
            return None, start_idx + 1

        language = code_start_match.group(1) or None
        code_lines: list[str] = []

        # Find the closing </code>
        i = start_idx + 1
        while i < len(lines):
            if CODE_BLOCK_END_PATTERN.match(lines[i]):
                # Found closing tag
                code_content = "\n".join(code_lines)
                return CodeBlock(content=code_content, language=language), i + 1
            code_lines.append(lines[i])
            i += 1

        # No closing tag found - treat accumulated lines as code block anyway
        code_content = "\n".join(code_lines)
        return CodeBlock(content=code_content, language=language), i

    def _parse_list(self, lines: list[str], start_idx: int) -> tuple[List | None, int]:
        """Parse a list starting at the given line.

        Supports nested lists with indentation (2 spaces per level).
        DokuWiki uses * for unordered lists and - for ordered lists.

        Parameters
        ----------
        lines : list[str]
            All lines in the document
        start_idx : int
            Index of the first list item line

        Returns
        -------
        tuple[List | None, int]
            Parsed list node and the index after the last list item

        """
        first_line = lines[start_idx]
        first_match = LIST_ITEM_PATTERN.match(first_line)
        if not first_match:
            return None, start_idx + 1

        # Determine list type from first item
        first_indent = len(first_match.group(1))
        first_marker = first_match.group(2)
        ordered = first_marker == "-"

        items: list[ListItem] = []
        i = start_idx

        while i < len(lines):
            line = lines[i]
            list_match = LIST_ITEM_PATTERN.match(line)

            if not list_match:
                # Not a list item - end of list
                break

            indent = len(list_match.group(1))
            marker = list_match.group(2)
            item_text = list_match.group(3)

            # Check if this item belongs to current list level
            if indent < first_indent:
                # Less indented - end of this list
                break

            if indent == first_indent:
                # Same level - check if same list type
                current_ordered = marker == "-"
                if current_ordered != ordered:
                    # Different list type at same level - end of this list
                    break

                # Parse item content
                item_content = self._process_inline(item_text)
                # Check if next lines are nested lists
                child_nodes: list[Node] = [Paragraph(content=item_content)]

                # Look ahead for nested lists
                if i + 1 < len(lines):
                    next_match = LIST_ITEM_PATTERN.match(lines[i + 1])
                    if next_match and len(next_match.group(1)) > indent:
                        # Nested list follows
                        nested_list, next_i = self._parse_list(lines, i + 1)
                        if nested_list:
                            child_nodes.append(nested_list)
                            i = next_i - 1  # Will be incremented at end of loop

                items.append(ListItem(children=child_nodes))
                i += 1
            else:
                # More indented than current level - shouldn't happen here
                # as nested lists are handled above
                break

        return List(ordered=ordered, items=items, tight=True), i

    def _parse_table(self, lines: list[str], start_idx: int) -> tuple[Table | None, int]:
        """Parse a table starting at the given line.

        DokuWiki tables use:
        - ^ for header cells
        - | for regular cells
        Rows start and end with | or ^.

        Parameters
        ----------
        lines : list[str]
            All lines in the document
        start_idx : int
            Index of the first table row line

        Returns
        -------
        tuple[Table | None, int]
            Parsed table node and the index after the last table row

        """
        rows: list[TableRow] = []
        header: TableRow | None = None
        i = start_idx

        while i < len(lines):
            line = lines[i].strip()

            if not TABLE_ROW_PATTERN.match(line):
                # Not a table row - end of table
                break

            # Determine if this is a header row (starts with ^)
            is_header_row = line.startswith("^")

            # Split cells by | or ^
            # Remove leading/trailing delimiters
            delimiter = "^" if is_header_row else "|"
            line = line.strip(delimiter)

            # Split by delimiter
            cell_texts = line.split(delimiter)

            # Parse each cell
            cells: list[TableCell] = []
            for cell_text in cell_texts:
                cell_text = cell_text.strip()
                cell_content = self._process_inline(cell_text) if cell_text else []
                cells.append(TableCell(content=cell_content))

            # Create table row
            table_row = TableRow(cells=cells, is_header=is_header_row)

            if is_header_row and header is None:
                # First header row becomes the table header
                header = table_row
            else:
                # All other rows go to body
                rows.append(table_row)

            i += 1

        if not rows and not header:
            return None, start_idx + 1

        return Table(header=header, rows=rows), i

    def _parse_blockquote(self, lines: list[str], start_idx: int) -> tuple[BlockQuote | None, int]:
        """Parse a block quote starting at the given line.

        DokuWiki blockquotes use > at the start of each line.
        Multiple consecutive > lines are combined into one blockquote.

        Parameters
        ----------
        lines : list[str]
            All lines in the document
        start_idx : int
            Index of the first blockquote line

        Returns
        -------
        tuple[BlockQuote | None, int]
            Parsed blockquote node and the index after the last blockquote line

        """
        blockquote_lines: list[str] = []
        i = start_idx

        while i < len(lines):
            blockquote_match = BLOCKQUOTE_PATTERN.match(lines[i])
            if not blockquote_match:
                # No longer a blockquote line
                break

            quote_text = blockquote_match.group(1)
            blockquote_lines.append(quote_text)
            i += 1

        if not blockquote_lines:
            return None, start_idx + 1

        # Combine lines into paragraphs
        # Empty lines separate paragraphs within the blockquote
        paragraphs: list[Node] = []
        current_paragraph_lines: list[str] = []

        for line in blockquote_lines:
            if line.strip():
                current_paragraph_lines.append(line)
            elif current_paragraph_lines:
                # Empty line - end current paragraph
                para_text = " ".join(current_paragraph_lines)
                para_content = self._process_inline(para_text)
                paragraphs.append(Paragraph(content=para_content))
                current_paragraph_lines = []

        # Add final paragraph if any
        if current_paragraph_lines:
            para_text = " ".join(current_paragraph_lines)
            para_content = self._process_inline(para_text)
            paragraphs.append(Paragraph(content=para_content))

        return BlockQuote(children=paragraphs), i

    def extract_metadata(self, content: str | Document) -> DocumentMetadata:
        """Extract metadata from DokuWiki content.

        Parameters
        ----------
        content : str or Document
            DokuWiki markup content or parsed document

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        if isinstance(content, Document):
            # Already parsed - extract from document
            title = None
            # Try to find first heading
            for child in content.children:
                if isinstance(child, Heading):
                    # Extract text from heading content
                    title_parts = []
                    for node in child.content:
                        if isinstance(node, Text):
                            title_parts.append(node.content)
                    title = "".join(title_parts)
                    break
            return DocumentMetadata(
                title=title,
                word_count=0,  # TODO: Implement word count
            )

        # String content - try to find first heading
        lines = content.split("\n")
        title = None
        for line in lines:
            heading_match = HEADING_PATTERN.match(line)
            if heading_match:
                title = heading_match.group(2).strip()
                break

        return DocumentMetadata(
            title=title,
            word_count=len(content.split()) if content else 0,
        )


# =============================================================================
# Converter Metadata Registration
# =============================================================================

CONVERTER_METADATA = ConverterMetadata(
    format_name="dokuwiki",
    extensions=[".doku", ".dokuwiki"],
    mime_types=["text/plain"],
    magic_bytes=[],  # No magic bytes for DokuWiki - it's plain text
    parser_class=DokuWikiParser,
    renderer_class="all2md.renderers.dokuwiki.DokuWikiRenderer",
    renders_as_string=True,
    parser_required_packages=[],  # Pure Python implementation
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="",  # No dependencies needed
    parser_options_class=DokuWikiParserOptions,
    renderer_options_class="all2md.options.dokuwiki.DokuWikiOptions",
    description="Parse and render DokuWiki markup",
    priority=10,
)
