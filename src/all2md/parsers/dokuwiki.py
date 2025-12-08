#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/dokuwiki.py
"""DokuWiki markup to AST converter.

This module provides conversion from DokuWiki markup to AST representation
using custom regex-based parsing. It enables bidirectional transformation by parsing
DokuWiki markup into the same AST structure used for other formats.

"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import IO, Optional, Union, cast

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
    HTMLBlock,
    HTMLInline,
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
from all2md.ast.utils import extract_text
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.dokuwiki import DokuWikiParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
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

# HTML tags (for html_passthrough_mode handling)
HTML_TAG_PATTERN = re.compile(r"<([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>.*?</\1>|<[a-zA-Z][a-zA-Z0-9]*\b[^>]*/>", re.DOTALL)


class DokuWikiParser(BaseParser):
    r"""Convert DokuWiki markup to AST representation.

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
        BaseParser._validate_options_type(options, DokuWikiParserOptions, "dokuwiki")
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
        dokuwiki_content = self._load_text_content(input_data)

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

    def _flush_inline_buffer(self, inline_buffer: list[Node], result: list[Node]) -> None:
        """Flush inline buffer to result as paragraph.

        Parameters
        ----------
        inline_buffer : list[Node]
            Buffer of inline nodes to flush
        result : list[Node]
            Result list to append paragraph to

        """
        if inline_buffer:
            result.append(Paragraph(content=list(inline_buffer)))
            inline_buffer.clear()

    def _try_parse_comment_block(self, line: str, inline_buffer: list[Node], result: list[Node]) -> tuple[bool, int]:
        """Try to parse block-level comments.

        Parameters
        ----------
        line : str
            Line to check
        inline_buffer : list[Node]
            Current inline buffer
        result : list[Node]
            Result list

        Returns
        -------
        tuple[bool, int]
            (matched, lines_consumed) - matched is True if comment was found

        """
        # Check for C-style block comment
        c_comment_match = C_COMMENT_PATTERN.match(line.strip())
        if c_comment_match and c_comment_match.group(0) == line.strip():
            if self.options.strip_comments:
                return True, 1
            else:
                self._flush_inline_buffer(inline_buffer, result)
                comment_text = line.strip()[2:-2].strip()
                result.append(Comment(content=comment_text, metadata={"comment_type": "wiki"}))
                return True, 1

        # Check for HTML block comment
        html_comment_match = HTML_COMMENT_PATTERN.match(line.strip())
        if html_comment_match and html_comment_match.group(0) == line.strip():
            if self.options.strip_comments:
                return True, 1
            else:
                self._flush_inline_buffer(inline_buffer, result)
                comment_text = line.strip()[4:-3].strip()
                result.append(Comment(content=comment_text, metadata={"comment_type": "wiki"}))
                return True, 1

        return False, 0

    def _try_parse_heading(self, line: str, inline_buffer: list[Node], result: list[Node]) -> tuple[bool, int]:
        """Try to parse heading.

        Parameters
        ----------
        line : str
            Line to check
        inline_buffer : list[Node]
            Current inline buffer
        result : list[Node]
            Result list

        Returns
        -------
        tuple[bool, int]
            (matched, lines_consumed)

        """
        heading_match = HEADING_PATTERN.match(line)
        if heading_match:
            self._flush_inline_buffer(inline_buffer, result)
            equals_count = len(heading_match.group(1))
            level = 7 - equals_count
            heading_text = heading_match.group(2).strip()
            heading_content = self._process_inline(heading_text)
            result.append(Heading(level=level, content=heading_content))
            return True, 1
        return False, 0

    def _try_parse_horizontal_rule(self, line: str, inline_buffer: list[Node], result: list[Node]) -> tuple[bool, int]:
        """Try to parse horizontal rule.

        Parameters
        ----------
        line : str
            Line to check
        inline_buffer : list[Node]
            Current inline buffer
        result : list[Node]
            Result list

        Returns
        -------
        tuple[bool, int]
            (matched, lines_consumed)

        """
        if HORIZONTAL_RULE_PATTERN.match(line):
            self._flush_inline_buffer(inline_buffer, result)
            result.append(ThematicBreak())
            return True, 1
        return False, 0

    def _try_parse_code_block(
        self, lines: list[str], i: int, inline_buffer: list[Node], result: list[Node]
    ) -> tuple[bool, int]:
        """Try to parse code block.

        Parameters
        ----------
        lines : list[str]
            All lines
        i : int
            Current line index
        inline_buffer : list[Node]
            Current inline buffer
        result : list[Node]
            Result list

        Returns
        -------
        tuple[bool, int]
            (matched, new_index)

        """
        line = lines[i]
        code_start_match = CODE_BLOCK_START_PATTERN.match(line)
        if code_start_match:
            self._flush_inline_buffer(inline_buffer, result)
            code_block, new_i = self._parse_code_block(lines, i)
            if code_block:
                result.append(code_block)
            return True, new_i
        return False, i

    def _try_parse_list(
        self, lines: list[str], i: int, inline_buffer: list[Node], result: list[Node]
    ) -> tuple[bool, int]:
        """Try to parse list.

        Parameters
        ----------
        lines : list[str]
            All lines
        i : int
            Current line index
        inline_buffer : list[Node]
            Current inline buffer
        result : list[Node]
            Result list

        Returns
        -------
        tuple[bool, int]
            (matched, new_index)

        """
        line = lines[i]
        list_match = LIST_ITEM_PATTERN.match(line)
        if list_match:
            self._flush_inline_buffer(inline_buffer, result)
            list_node, new_i = self._parse_list(lines, i)
            if list_node:
                result.append(list_node)
            return True, new_i
        return False, i

    def _try_parse_table(
        self, lines: list[str], i: int, inline_buffer: list[Node], result: list[Node]
    ) -> tuple[bool, int]:
        """Try to parse table.

        Parameters
        ----------
        lines : list[str]
            All lines
        i : int
            Current line index
        inline_buffer : list[Node]
            Current inline buffer
        result : list[Node]
            Result list

        Returns
        -------
        tuple[bool, int]
            (matched, new_index)

        """
        line = lines[i]
        if TABLE_ROW_PATTERN.match(line):
            self._flush_inline_buffer(inline_buffer, result)
            table_node, new_i = self._parse_table(lines, i)
            if table_node:
                result.append(table_node)
            return True, new_i
        return False, i

    def _try_parse_blockquote(
        self, lines: list[str], i: int, inline_buffer: list[Node], result: list[Node]
    ) -> tuple[bool, int]:
        """Try to parse blockquote.

        Parameters
        ----------
        lines : list[str]
            All lines
        i : int
            Current line index
        inline_buffer : list[Node]
            Current inline buffer
        result : list[Node]
            Result list

        Returns
        -------
        tuple[bool, int]
            (matched, new_index)

        """
        line = lines[i]
        blockquote_match = BLOCKQUOTE_PATTERN.match(line)
        if blockquote_match:
            self._flush_inline_buffer(inline_buffer, result)
            blockquote_node, new_i = self._parse_blockquote(lines, i)
            if blockquote_node:
                result.append(blockquote_node)
            return True, new_i
        return False, i

    def _try_parse_plugin_block(self, line: str, inline_buffer: list[Node], result: list[Node]) -> tuple[bool, int]:
        """Try to parse plugin syntax as block-level element.

        Parameters
        ----------
        line : str
            Line to check
        inline_buffer : list[Node]
            Current inline buffer
        result : list[Node]
            Result list

        Returns
        -------
        tuple[bool, int]
            (matched, lines_consumed)

        """
        plugin_match = PLUGIN_PATTERN.match(line.strip())
        if plugin_match and plugin_match.group(0) == line.strip():
            self._flush_inline_buffer(inline_buffer, result)
            if self.options.parse_plugins:
                # Convert plugin syntax to HTMLBlock node
                result.append(HTMLBlock(content=plugin_match.group(0)))
            # else: strip the plugin (do nothing)
            return True, 1
        return False, 0

    def _try_parse_html_block(self, line: str, inline_buffer: list[Node], result: list[Node]) -> tuple[bool, int]:
        """Try to parse HTML tag as block-level element based on html_passthrough_mode.

        Parameters
        ----------
        line : str
            Line to check
        inline_buffer : list[Node]
            Current inline buffer
        result : list[Node]
            Result list

        Returns
        -------
        tuple[bool, int]
            (matched, lines_consumed)

        """
        html_match = HTML_TAG_PATTERN.match(line.strip())
        if html_match and html_match.group(0) == line.strip():
            self._flush_inline_buffer(inline_buffer, result)
            html_content = html_match.group(0)
            mode = self.options.html_passthrough_mode

            if mode == "pass-through":
                result.append(HTMLBlock(content=html_content))
            elif mode == "escape":
                import html

                result.append(Paragraph(content=[Text(content=html.escape(html_content))]))
            elif mode == "drop":
                pass  # Don't add anything
            elif mode == "sanitize":
                from all2md.utils.html_sanitizer import sanitize_html_string

                safe_html = sanitize_html_string(html_content)
                if safe_html:
                    result.append(HTMLBlock(content=safe_html))
                # If empty after sanitization, don't add anything

            return True, 1
        return False, 0

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
                self._flush_inline_buffer(inline_buffer, result)
                i += 1
                continue

            # Try to match block-level elements using pattern matchers
            matched, consumed = self._try_parse_comment_block(line, inline_buffer, result)
            if matched:
                i += consumed
                continue

            matched, consumed = self._try_parse_heading(line, inline_buffer, result)
            if matched:
                i += consumed
                continue

            matched, consumed = self._try_parse_horizontal_rule(line, inline_buffer, result)
            if matched:
                i += consumed
                continue

            matched, new_i = self._try_parse_code_block(lines, i, inline_buffer, result)
            if matched:
                i = new_i
                continue

            matched, new_i = self._try_parse_list(lines, i, inline_buffer, result)
            if matched:
                i = new_i
                continue

            matched, new_i = self._try_parse_table(lines, i, inline_buffer, result)
            if matched:
                i = new_i
                continue

            matched, new_i = self._try_parse_blockquote(lines, i, inline_buffer, result)
            if matched:
                i = new_i
                continue

            matched, consumed = self._try_parse_plugin_block(line, inline_buffer, result)
            if matched:
                i += consumed
                continue

            matched, consumed = self._try_parse_html_block(line, inline_buffer, result)
            if matched:
                i += consumed
                continue

            # Regular text line - add to inline buffer
            inline_nodes = self._process_inline(line)
            inline_buffer.extend(inline_nodes)
            # Add soft line break between lines in same paragraph
            if i + 1 < len(lines) and lines[i + 1].strip():
                inline_buffer.append(LineBreak(soft=True))
            i += 1

        # Flush remaining inline buffer
        self._flush_inline_buffer(inline_buffer, result)

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
            result.append(FootnoteDefinition(identifier=identifier, content=cast(list[Node], content_nodes)))

    def _handle_image_pattern(self, match: re.Match) -> Node:
        """Handle image pattern match.

        Parameters
        ----------
        match : Match
            Regex match object

        Returns
        -------
        Node
            Image node

        """
        url = match.group(1).strip()
        alt_text = match.group(2).strip() if match.group(2) else ""
        url = sanitize_url(url)
        return Image(url=url, alt_text=alt_text)

    def _handle_link_pattern(self, match: re.Match) -> Node:
        """Handle link pattern match.

        Parameters
        ----------
        match : Match
            Regex match object

        Returns
        -------
        Node
            Link node

        """
        url = match.group(1).strip()
        link_text = match.group(2)

        # Handle interwiki links if enabled
        if self.options.parse_interwiki and ">" in url:
            pass  # Keep as-is in URL

        url = sanitize_url(url)

        if link_text:
            link_content = self._process_inline(link_text.strip())
        else:
            link_content = [Text(content=url)]

        return Link(url=url, content=link_content)

    def _handle_footnote_pattern(self, match: re.Match) -> Node:
        """Handle footnote pattern match.

        Parameters
        ----------
        match : Match
            Regex match object

        Returns
        -------
        Node
            FootnoteReference node

        """
        footnote_text = match.group(1).strip()
        identifier = hashlib.md5(footnote_text.encode(), usedforsecurity=False).hexdigest()[:8]

        if identifier not in self._footnote_definitions:
            self._footnote_definitions[identifier] = footnote_text

        return FootnoteReference(identifier=identifier)

    def _handle_formatting_pattern(self, match: re.Match, node_type: str) -> Node:
        """Handle formatting pattern match (bold, italic, underline, etc.).

        Parameters
        ----------
        match : Match
            Regex match object
        node_type : str
            Type of formatting node to create

        Returns
        -------
        Node
            Formatted node

        """
        inner_text = match.group(1)
        inner_nodes = self._process_inline(inner_text)

        if node_type == "bold":
            return Strong(content=inner_nodes)
        elif node_type == "italic":
            return Emphasis(content=inner_nodes)
        elif node_type == "underline":
            return Underline(content=inner_nodes)
        elif node_type == "monospace":
            return Code(content=inner_text)  # Don't process nested
        elif node_type == "strikethrough":
            return Strikethrough(content=inner_nodes)
        elif node_type == "subscript":
            return Subscript(content=inner_nodes)
        elif node_type == "superscript":
            return Superscript(content=inner_nodes)
        else:
            return Text(content=inner_text)

    def _handle_comment_pattern(self, match: re.Match, comment_style: str) -> Node:
        """Handle comment pattern match.

        Parameters
        ----------
        match : Match
            Regex match object
        comment_style : str
            'c-style' or 'html'

        Returns
        -------
        Node
            CommentInline node

        """
        if comment_style == "c-style":
            comment_text = match.group(0)[2:-2].strip()
        else:  # html
            comment_text = match.group(0)[4:-3].strip()
        return CommentInline(content=comment_text, metadata={"comment_type": "wiki"})

    def _handle_html_tag_pattern(self, match: re.Match) -> Node:
        """Handle HTML tag pattern based on html_passthrough_mode.

        Parameters
        ----------
        match : Match
            Regex match object

        Returns
        -------
        Node
            Appropriate node based on passthrough mode

        """
        html_content = match.group(0)
        mode = self.options.html_passthrough_mode

        if mode == "pass-through":
            return HTMLInline(content=html_content)
        elif mode == "escape":
            import html

            return Text(content=html.escape(html_content))
        elif mode == "drop":
            return Text(content="")
        else:  # mode == "sanitize"
            from all2md.utils.html_sanitizer import sanitize_html_string

            safe_html = sanitize_html_string(html_content)
            if safe_html:
                return HTMLInline(content=safe_html)
            return Text(content="")

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

        # Define patterns in order of precedence
        patterns = [
            ("image", IMAGE_PATTERN),
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

        # Add plugin pattern if enabled
        if self.options.parse_plugins:
            patterns.append(("plugin", PLUGIN_PATTERN))

        # Add HTML tag pattern after specific formatting patterns to avoid intercepting known tags
        patterns.append(("html_tag", HTML_TAG_PATTERN))

        if not self.options.strip_comments:
            patterns.extend([("c_comment", C_COMMENT_PATTERN), ("html_comment", HTML_COMMENT_PATTERN)])

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

        if not earliest_match:
            return [Text(content=text)] if text else []

        # At this point, earliest_match and earliest_type are both set
        assert earliest_type is not None, "earliest_type must be set when earliest_match is found"

        # Split into before, match, and after
        before = text[: earliest_match.start()]
        after = text[earliest_match.end() :]
        result: list[Node] = []

        if before:
            result.append(Text(content=before))

        # Dispatch to appropriate handler
        if earliest_type == "image":
            result.append(self._handle_image_pattern(earliest_match))
        elif earliest_type == "link":
            result.append(self._handle_link_pattern(earliest_match))
        elif earliest_type == "footnote":
            result.append(self._handle_footnote_pattern(earliest_match))
        elif earliest_type == "html_tag":
            result.append(self._handle_html_tag_pattern(earliest_match))
        elif earliest_type == "linebreak":
            result.append(LineBreak(soft=False))
        elif earliest_type == "plugin":
            # Convert plugin syntax to HTMLInline node
            result.append(HTMLInline(content=earliest_match.group(0)))
        elif earliest_type in ("c_comment", "html_comment"):
            comment_type = "c-style" if earliest_type == "c_comment" else "html"
            result.append(self._handle_comment_pattern(earliest_match, comment_type))
        else:
            # Formatting patterns (bold, italic, underline, etc.)
            result.append(self._handle_formatting_pattern(earliest_match, earliest_type))

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

            # Calculate word count from document text
            all_text = extract_text(content, joiner=" ")
            word_count = len(all_text.split()) if all_text else 0

            return DocumentMetadata(
                title=title,
                word_count=word_count,
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
