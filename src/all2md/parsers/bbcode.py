#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/bbcode.py
"""BBCode to AST converter.

This module provides conversion from BBCode (Bulletin Board Code) markup to AST
representation. It enables parsing legacy bulletin board and forum content into
the unified all2md AST structure for archival and conversion purposes.

BBCode is a lightweight markup language used by many bulletin board systems and
forums in the early web. This parser supports comprehensive BBCode tags including
vendor-specific extensions commonly found in popular forum software.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast import (
    BlockQuote,
    CodeBlock,
    Document,
    Emphasis,
    Heading,
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
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.bbcode import BBCodeParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.html_sanitizer import sanitize_html_content, sanitize_url
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


@dataclass
class BBCodeTag:
    """Represents a parsed BBCode tag.

    Parameters
    ----------
    name : str
        Tag name (e.g., 'b', 'url', 'quote')
    is_closing : bool
        Whether this is a closing tag
    value : str or None
        Tag attribute value (e.g., URL in [url=http://example.com])
    position : int
        Character position in source text

    """

    name: str
    is_closing: bool
    value: Optional[str]
    position: int


class BBCodeParser(BaseParser):
    """Convert BBCode markup to AST representation.

    This parser handles comprehensive BBCode tags including core formatting,
    links, images, lists, tables, quotes, code blocks, and vendor-specific
    extensions commonly found in bulletin board systems.

    Supported BBCode tags include:
    - Formatting: [b], [i], [u], [s], [sup], [sub]
    - Links: [url], [url=...], [email], [email=...]
    - Images: [img], [img=WIDTHxHEIGHT]
    - Quotes: [quote], [quote=author]
    - Code: [code], [code=language]
    - Lists: [list], [list=1], [*]
    - Tables: [table], [tr], [td], [th]
    - Styling: [color=...], [size=...], [font=...]
    - Alignment: [center], [left], [right]
    - Media: [youtube], [video]
    - Special: [spoiler], [hr]

    Parameters
    ----------
    options : BBCodeParserOptions or None, default = None
        Parser configuration options
    progress_callback : ProgressCallback or None, default = None
        Optional callback for progress updates

    Examples
    --------
    Basic parsing:

        >>> parser = BBCodeParser()
        >>> doc = parser.parse("[b]Bold[/b] and [i]italic[/i] text")

    With options:

        >>> options = BBCodeParserOptions(strict_mode=True)
        >>> parser = BBCodeParser(options)
        >>> doc = parser.parse(bbcode_text)

    """

    # Regex pattern for BBCode tags
    TAG_PATTERN = re.compile(r"\[(/?)(\w+)(?:=([^\]]+))?\]", re.IGNORECASE)

    # Block-level tags that should create new blocks
    BLOCK_TAGS = {"quote", "code", "list", "table", "center", "left", "right", "hr", "spoiler", "youtube", "video"}

    # Tags that should be treated as headings
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    # Self-closing tags
    SELF_CLOSING_TAGS = {"hr", "*", "br"}

    def __init__(
        self, options: BBCodeParserOptions | None = None, progress_callback: Optional[ProgressCallback] = None
    ):
        """Initialize the BBCode parser with options and progress callback."""
        BaseParser._validate_options_type(options, BBCodeParserOptions, "bbcode")
        options = options or BBCodeParserOptions()
        super().__init__(options, progress_callback)
        self.options: BBCodeParserOptions = options

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse BBCode input into AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            BBCode input to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw BBCode bytes
            - BBCode string

        Returns
        -------
        Document
            AST document node

        Raises
        ------
        ParsingError
            If parsing fails in strict mode

        """
        self._emit_progress("started", "Parsing BBCode", current=0, total=100)

        # Load BBCode content from various input types
        bbcode_content = self._load_text_content(input_data)

        self._emit_progress("item_done", "Loaded BBCode content", current=20, total=100, item_type="loading")

        # Parse BBCode to AST
        try:
            children = self._parse_content(bbcode_content)
        except Exception as e:
            if self.options.strict_mode:
                raise ParsingError(f"Failed to parse BBCode markup: {e}") from e
            else:
                logger.warning(f"BBCode parsing encountered error, attempting recovery: {e}", stacklevel=2)
                # Fallback: treat as plain text
                children = [Paragraph(content=[Text(content=bbcode_content)])]

        self._emit_progress("item_done", "Parsed BBCode to AST", current=90, total=100, item_type="parsing")

        # Extract metadata
        metadata = self.extract_metadata(bbcode_content)

        # Create document
        doc = Document(children=children, metadata=metadata.to_dict() if metadata else {})

        self._emit_progress("finished", "Parsing complete", current=100, total=100)

        return doc

    def _parse_content(self, bbcode: str) -> list[Node]:
        """Parse BBCode content into AST nodes.

        Parameters
        ----------
        bbcode : str
            BBCode content to parse

        Returns
        -------
        list of Node
            Parsed AST nodes

        """
        # Normalize line endings
        bbcode = bbcode.replace("\r\n", "\n").replace("\r", "\n")

        # Parse into blocks and inline content
        return self._parse_blocks(bbcode)

    def _parse_blocks(self, bbcode: str) -> list[Node]:
        """Parse BBCode into block-level nodes.

        Parameters
        ----------
        bbcode : str
            BBCode content

        Returns
        -------
        list of Node
            Block-level AST nodes

        """
        result: list[Node] = []
        inline_buffer: list[str] = []
        pos = 0

        while pos < len(bbcode):
            # Check for block-level tags
            match = self.TAG_PATTERN.search(bbcode, pos)

            if not match:
                # No more tags, add remaining text to buffer
                remaining = bbcode[pos:]
                if remaining.strip():
                    inline_buffer.append(remaining)
                break

            # Add text before tag to buffer
            if match.start() > pos:
                text_before = bbcode[pos : match.start()]
                inline_buffer.append(text_before)

            is_closing = match.group(1) == "/"
            tag_name = match.group(2).lower()
            tag_value = match.group(3)

            # Check for horizontal rule first (self-closing block tag)
            if tag_name == "hr" and not is_closing:
                # Horizontal rule (self-closing)
                if inline_buffer:
                    inline_content = "".join(inline_buffer)
                    if inline_content.strip():
                        result.extend(self._split_paragraphs(inline_content))
                    inline_buffer = []

                result.append(ThematicBreak())
                pos = match.end()

            # Check if this is a block-level tag
            elif tag_name in self.BLOCK_TAGS and not is_closing:
                # Flush inline buffer
                if inline_buffer:
                    inline_content = "".join(inline_buffer)
                    if inline_content.strip():
                        result.extend(self._split_paragraphs(inline_content))
                    inline_buffer = []

                # Parse block-level element
                block_node, new_pos = self._parse_block_tag(bbcode, match, tag_name, tag_value)
                if block_node:
                    result.append(block_node)
                pos = new_pos

            elif tag_name in self.HEADING_TAGS and not is_closing:
                # Flush inline buffer
                if inline_buffer:
                    inline_content = "".join(inline_buffer)
                    if inline_content.strip():
                        result.extend(self._split_paragraphs(inline_content))
                    inline_buffer = []

                # Parse heading
                heading_node, new_pos = self._parse_heading(bbcode, match, tag_name)
                if heading_node:
                    result.append(heading_node)
                pos = new_pos

            else:
                # Inline tag or closing tag - include in buffer
                inline_buffer.append(bbcode[match.start() : match.end()])
                pos = match.end()

        # Flush remaining inline buffer
        if inline_buffer:
            inline_content = "".join(inline_buffer)
            if inline_content.strip():
                result.extend(self._split_paragraphs(inline_content))

        return result

    def _split_paragraphs(self, content: str) -> list[Node]:
        """Split content by double newlines into paragraphs.

        Parameters
        ----------
        content : str
            Content to split

        Returns
        -------
        list of Node
            Paragraph nodes

        """
        paragraphs: list[Node] = []
        parts = re.split(r"\n\s*\n", content)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Check for thematic break
            if re.match(r"^-{3,}$", part):
                paragraphs.append(ThematicBreak())
            else:
                # Parse inline content
                inline_nodes = self._parse_inline(part)
                if inline_nodes:
                    paragraphs.append(Paragraph(content=inline_nodes))

        return paragraphs

    def _parse_block_tag(
        self, bbcode: str, match: re.Match[str], tag_name: str, tag_value: Optional[str]
    ) -> tuple[Node | None, int]:
        """Parse a block-level BBCode tag.

        Parameters
        ----------
        bbcode : str
            Full BBCode content
        match : re.Match
            Regex match for opening tag
        tag_name : str
            Tag name
        tag_value : str or None
            Tag value/attribute

        Returns
        -------
        tuple of (Node or None, int)
            Parsed node and new position

        """
        # Find closing tag
        closing_pattern = re.compile(rf"\[/{tag_name}\]", re.IGNORECASE)
        closing_match = closing_pattern.search(bbcode, match.end())

        if not closing_match:
            if self.options.strict_mode:
                raise ParsingError(f"Unclosed [{tag_name}] tag at position {match.start()}")
            else:
                # No closing tag - treat as text
                return None, match.end()

        # Extract content between tags
        content = bbcode[match.end() : closing_match.start()]

        # Parse based on tag type
        if tag_name == "quote":
            return self._create_quote(content, tag_value), closing_match.end()
        elif tag_name == "code":
            return self._create_code_block(content, tag_value), closing_match.end()
        elif tag_name == "list":
            return self._create_list(content, tag_value), closing_match.end()
        elif tag_name == "table":
            return self._create_table(content), closing_match.end()
        elif tag_name in ("center", "left", "right"):
            return self._create_aligned_paragraph(content, tag_name), closing_match.end()
        elif tag_name == "spoiler":
            return self._create_spoiler(content), closing_match.end()
        elif tag_name in ("youtube", "video"):
            return self._create_media_block(content, tag_name), closing_match.end()
        else:
            # Unknown block tag - handle based on option
            return self._handle_unknown_block(content, tag_name, tag_value), closing_match.end()

    def _parse_heading(self, bbcode: str, match: re.Match[str], tag_name: str) -> tuple[Node | None, int]:
        """Parse a heading tag.

        Parameters
        ----------
        bbcode : str
            Full BBCode content
        match : re.Match
            Regex match for opening tag
        tag_name : str
            Tag name (h1-h6)

        Returns
        -------
        tuple of (Node or None, int)
            Parsed heading node and new position

        """
        # Extract level from tag name
        level = int(tag_name[1])

        # Find closing tag
        closing_pattern = re.compile(rf"\[/{tag_name}\]", re.IGNORECASE)
        closing_match = closing_pattern.search(bbcode, match.end())

        if not closing_match:
            if self.options.strict_mode:
                raise ParsingError(f"Unclosed [{tag_name}] tag at position {match.start()}")
            else:
                return None, match.end()

        # Extract and parse content
        content = bbcode[match.end() : closing_match.start()]
        inline_nodes = self._parse_inline(content)

        return Heading(level=level, content=inline_nodes), closing_match.end()

    def _parse_inline(self, content: str) -> list[Node]:
        """Parse inline BBCode content into AST nodes.

        Parameters
        ----------
        content : str
            Inline content to parse

        Returns
        -------
        list of Node
            Inline AST nodes

        """
        result: list[Node] = []
        pos = 0

        while pos < len(content):
            match = self.TAG_PATTERN.search(content, pos)

            if not match:
                # No more tags, add remaining text
                remaining = content[pos:]
                if remaining:
                    result.append(Text(content=remaining))
                break

            # Add text before tag
            if match.start() > pos:
                text_before = content[pos : match.start()]
                result.append(Text(content=text_before))

            is_closing = match.group(1) == "/"
            tag_name = match.group(2).lower()
            tag_value = match.group(3)

            if is_closing:
                # Unmatched closing tag - treat as text
                if self.options.strict_mode:
                    raise ParsingError(f"Unmatched closing tag [/{tag_name}] in inline content")
                else:
                    result.append(Text(content=match.group(0)))
                    pos = match.end()
            else:
                # Opening tag
                if tag_name in self.SELF_CLOSING_TAGS:
                    # Self-closing tag
                    node = self._create_self_closing_node(tag_name, tag_value)
                    if node:
                        result.append(node)
                    pos = match.end()
                elif tag_name in ("img",):
                    # Special handling for img tag
                    node = self._parse_img_tag(content, match, tag_value)
                    if node:
                        result.append(node)
                        closing_img_pos = self._find_closing_tag_position(content, match.end(), tag_name)
                        if closing_img_pos is not None:
                            pos = closing_img_pos + len(f"[/{tag_name}]")
                        else:
                            pos = match.end()
                    else:
                        pos = match.end()
                else:
                    # Find matching closing tag and extract content
                    closing_pos = self._find_closing_tag_position(content, match.end(), tag_name)
                    if closing_pos is None:
                        # No closing tag - treat as text
                        if self.options.strict_mode:
                            raise ParsingError(f"Unclosed [{tag_name}] tag in inline content")
                        else:
                            result.append(Text(content=match.group(0)))
                            pos = match.end()
                    else:
                        # Extract content and create node
                        inner_content = content[match.end() : closing_pos]
                        node = self._create_inline_formatted_node(tag_name, tag_value, inner_content)
                        if node:
                            result.append(node)
                        # Move past closing tag
                        closing_tag_end = closing_pos + len(f"[/{tag_name}]")
                        pos = closing_tag_end

        return result if result else [Text(content="")]

    def _find_closing_tag_position(self, content: str, start_pos: int, tag_name: str) -> Optional[int]:
        """Find the position of a closing tag, accounting for nesting.

        Parameters
        ----------
        content : str
            Content to search
        start_pos : int
            Position to start searching from
        tag_name : str
            Tag name to find closing tag for

        Returns
        -------
        int or None
            Position of closing tag start, or None if not found

        """
        depth = 1
        pos = start_pos

        while pos < len(content):
            match = self.TAG_PATTERN.search(content, pos)
            if not match:
                break

            is_closing = match.group(1) == "/"
            current_tag = match.group(2).lower()

            if current_tag == tag_name:
                if is_closing:
                    depth -= 1
                    if depth == 0:
                        return match.start()
                else:
                    depth += 1

            pos = match.end()

        return None

    def _create_inline_formatted_node(self, tag_name: str, tag_value: Optional[str], inner_content: str) -> Node | None:
        """Create a formatted inline AST node.

        Parameters
        ----------
        tag_name : str
            Tag name
        tag_value : str or None
            Tag attribute value
        inner_content : str
            Content between opening and closing tags

        Returns
        -------
        Node or None
            Created AST node

        """
        # Recursively parse inner content
        inner_nodes = self._parse_inline(inner_content) if inner_content else [Text(content="")]

        # Create appropriate node based on tag
        if tag_name == "b":
            return Strong(content=inner_nodes)
        elif tag_name == "i":
            return Emphasis(content=inner_nodes)
        elif tag_name == "u":
            return Underline(content=inner_nodes)
        elif tag_name == "s":
            return Strikethrough(content=inner_nodes)
        elif tag_name == "sup":
            return Superscript(content=inner_nodes)
        elif tag_name == "sub":
            return Subscript(content=inner_nodes)
        elif tag_name == "url":
            # If tag_value is set, use it as URL; otherwise use inner content
            if tag_value:
                url = sanitize_url(tag_value)
            else:
                # Extract URL from inner text
                url_text = inner_content.strip()
                url = sanitize_url(url_text)
                # Use URL as both link target and content if no text provided
                if not inner_content.strip():
                    inner_nodes = [Text(content=url_text)]

            return Link(url=url, content=inner_nodes)
        elif tag_name == "email":
            # If tag_value is set, use it as email; otherwise use inner content
            if tag_value:
                email = tag_value
            else:
                email = inner_content.strip()

            url = f"mailto:{email}"
            return Link(url=url, content=inner_nodes)
        elif tag_name in ("color", "size", "font"):
            # Styled text - wrap in a container with metadata if option is set
            if self.options.parse_color_size and tag_value:
                # For styled text, we can't use metadata on Text nodes effectively
                # Instead, wrap in HTMLInline to preserve the styling
                tag_str = f"[{tag_name}={tag_value}]{inner_content}[/{tag_name}]"
                sanitized = sanitize_html_content(tag_str, mode=self.options.html_passthrough_mode)
                return HTMLInline(content=sanitized)
            else:
                # Just return the inner nodes without styling
                return inner_nodes[0] if len(inner_nodes) == 1 else Text(content=inner_content)
        else:
            # Unknown inline tag
            return self._handle_unknown_inline(tag_name, tag_value, inner_content)

    def _parse_img_tag(self, content: str, match: re.Match[str], tag_value: Optional[str]) -> Image | None:
        """Parse an image tag.

        Parameters
        ----------
        content : str
            Full content string
        match : re.Match
            Regex match for opening [img] tag
        tag_value : str or None
            Optional size specification (WIDTHxHEIGHT)

        Returns
        -------
        Image or None
            Image AST node

        """
        # Find closing [/img] tag
        closing_pos = self._find_closing_tag_position(content, match.end(), "img")
        if closing_pos is None:
            if self.options.strict_mode:
                raise ParsingError(f"Unclosed [img] tag at position {match.start()}")
            else:
                return None

        # Extract image URL
        url = content[match.end() : closing_pos].strip()
        url = sanitize_url(url)

        # Parse size if provided
        metadata: dict[str, Any] = {}
        if tag_value and "x" in tag_value.lower():
            try:
                width, height = tag_value.lower().split("x")
                metadata["width"] = width.strip()
                metadata["height"] = height.strip()
            except ValueError:
                pass

        return Image(url=url, alt_text="", metadata=metadata if metadata else {})

    def _create_self_closing_node(self, tag_name: str, tag_value: Optional[str]) -> Node | None:
        """Create a self-closing inline node.

        Parameters
        ----------
        tag_name : str
            Tag name
        tag_value : str or None
            Tag value

        Returns
        -------
        Node or None
            Created node

        """
        if tag_name == "br":
            return LineBreak(soft=False)
        elif tag_name == "*":
            # List item marker - should not appear in inline context
            return None
        else:
            return None

    def _create_quote(self, content: str, author: Optional[str]) -> BlockQuote:
        """Create a quote block.

        Parameters
        ----------
        content : str
            Quote content
        author : str or None
            Quote author attribution

        Returns
        -------
        BlockQuote
            Quote AST node

        """
        # Parse content recursively
        children = self._parse_blocks(content) if content.strip() else [Paragraph(content=[Text(content="")])]

        # Add author attribution if present
        if author:
            # Add author as metadata
            metadata = {"author": author}
            return BlockQuote(children=children, metadata=metadata)

        return BlockQuote(children=children)

    def _create_code_block(self, content: str, language: Optional[str]) -> CodeBlock:
        """Create a code block.

        Parameters
        ----------
        content : str
            Code content
        language : str or None
            Programming language

        Returns
        -------
        CodeBlock
            Code block AST node

        """
        return CodeBlock(content=content, language=language)

    def _create_list(self, content: str, list_type: Optional[str]) -> List:
        """Create a list.

        Parameters
        ----------
        content : str
            List content with [*] markers
        list_type : str or None
            List type ('1' for ordered, None for unordered)

        Returns
        -------
        List
            List AST node

        """
        ordered = list_type == "1"
        items: list[ListItem] = []

        # Split by [*] markers
        parts = re.split(r"\[\*\]", content)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Parse item content as inline
            item_inline = self._parse_inline(part)
            items.append(ListItem(children=[Paragraph(content=item_inline)]))

        return List(ordered=ordered, items=items)

    def _create_table(self, content: str) -> Table:
        """Create a table.

        Parameters
        ----------
        content : str
            Table content with [tr], [td], [th] tags

        Returns
        -------
        Table
            Table AST node

        """
        rows: list[TableRow] = []
        header: Optional[TableRow] = None

        # Find all [tr]...[/tr] pairs
        tr_pattern = re.compile(r"\[tr\](.*?)\[/tr\]", re.IGNORECASE | re.DOTALL)
        tr_matches = tr_pattern.findall(content)

        for row_content in tr_matches:
            cells: list[TableCell] = []
            is_header = False

            # Find all [td] or [th] cells
            td_pattern = re.compile(r"\[(td|th)\](.*?)\[/\1\]", re.IGNORECASE | re.DOTALL)
            cell_matches = td_pattern.findall(row_content)

            for cell_type, cell_content in cell_matches:
                if cell_type.lower() == "th":
                    is_header = True

                # Parse cell content as inline
                cell_inline = self._parse_inline(cell_content.strip())
                cells.append(TableCell(content=cell_inline))

            if cells:
                row = TableRow(cells=cells, is_header=is_header)
                if is_header and header is None:
                    header = row
                else:
                    rows.append(row)

        return Table(header=header, rows=rows)

    def _create_aligned_paragraph(self, content: str, alignment: str) -> Paragraph:
        """Create an aligned paragraph.

        Parameters
        ----------
        content : str
            Paragraph content
        alignment : str
            Alignment type (center, left, right)

        Returns
        -------
        Paragraph
            Paragraph with alignment metadata

        """
        inline_nodes = self._parse_inline(content)
        metadata: dict[str, Any] = {}

        if self.options.parse_alignment:
            metadata["alignment"] = alignment

        return Paragraph(content=inline_nodes, metadata=metadata if metadata else {})

    def _create_spoiler(self, content: str) -> BlockQuote:
        """Create a spoiler block (rendered as blockquote with metadata).

        Parameters
        ----------
        content : str
            Spoiler content

        Returns
        -------
        BlockQuote
            Blockquote representing spoiler

        """
        children = self._parse_blocks(content) if content.strip() else [Paragraph(content=[Text(content="")])]
        return BlockQuote(children=children, metadata={"spoiler": True})

    def _create_media_block(self, content: str, media_type: str) -> Paragraph:
        """Create a media embed block (YouTube, video).

        Parameters
        ----------
        content : str
            Media ID or URL
        media_type : str
            Media type (youtube, video)

        Returns
        -------
        Paragraph
            Paragraph with media link

        """
        content = content.strip()

        if media_type == "youtube":
            # Convert YouTube ID to URL
            url = f"https://www.youtube.com/watch?v={content}"
        else:
            url = content

        url = sanitize_url(url)
        link = Link(url=url, content=[Text(content=f"[{media_type.upper()}]")])
        return Paragraph(content=[link])

    def _handle_unknown_block(self, content: str, tag_name: str, tag_value: Optional[str]) -> Node:
        """Handle unknown block-level tags.

        Parameters
        ----------
        content : str
            Tag content
        tag_name : str
            Tag name
        tag_value : str or None
            Tag value

        Returns
        -------
        Node
            Node based on unknown_tag_mode option

        """
        if self.options.unknown_tag_mode == "preserve":
            # Preserve as HTMLInline in a paragraph
            tag_open = f"[{tag_name}]" if tag_value is None else f"[{tag_name}={tag_value}]"
            tag_close = f"[/{tag_name}]"
            preserved = f"{tag_open}{content}{tag_close}"
            return Paragraph(content=[HTMLInline(content=preserved)])
        elif self.options.unknown_tag_mode == "strip":
            # Strip tags, keep content
            children = self._parse_blocks(content) if content.strip() else []
            if children:
                return children[0] if len(children) == 1 else Paragraph(content=[Text(content=content)])
            else:
                return Paragraph(content=[Text(content="")])
        else:  # "escape"
            # Escape brackets
            tag_open = f"[{tag_name}]" if tag_value is None else f"[{tag_name}={tag_value}]"
            tag_close = f"[/{tag_name}]"
            escaped = html.escape(f"{tag_open}{content}{tag_close}")
            return Paragraph(content=[Text(content=escaped)])

    def _handle_unknown_inline(self, tag_name: str, tag_value: Optional[str], inner_content: str = "") -> Node:
        """Handle unknown inline tags.

        Parameters
        ----------
        tag_name : str
            Tag name
        tag_value : str or None
            Tag value
        inner_content : str
            Content between tags (for strip mode)

        Returns
        -------
        Node
            Node based on unknown_tag_mode option

        """
        if self.options.unknown_tag_mode == "preserve":
            # Preserve as HTMLInline
            tag_open = f"[{tag_name}]" if tag_value is None else f"[{tag_name}={tag_value}]"
            tag_close = f"[/{tag_name}]"
            tag_str = f"{tag_open}{inner_content}{tag_close}"
            return HTMLInline(content=tag_str)
        elif self.options.unknown_tag_mode == "strip":
            # Strip tag, return content as text
            return Text(content=inner_content)
        else:  # "escape"
            # Escape brackets
            tag_open = f"[{tag_name}]" if tag_value is None else f"[{tag_name}={tag_value}]"
            tag_close = f"[/{tag_name}]"
            escaped = html.escape(f"{tag_open}{inner_content}{tag_close}")
            return Text(content=escaped)

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from BBCode document.

        BBCode doesn't have standard metadata fields, but we can try to extract
        basic information like title from the first heading if present.

        Parameters
        ----------
        document : Any
            Document content (BBCode string)

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        if isinstance(document, str):
            # Try to find first heading
            for i in range(1, 7):
                pattern = rf"\[h{i}\](.*?)\[/h{i}\]"
                match = re.search(pattern, document, re.IGNORECASE)
                if match:
                    metadata.title = match.group(1).strip()
                    break

        return metadata


# Converter metadata for registry auto-discovery
CONVERTER_METADATA = ConverterMetadata(
    format_name="bbcode",
    extensions=[".bbcode", ".bb"],
    mime_types=["text/x-bbcode"],
    magic_bytes=[],  # BBCode is plain text, no magic bytes
    parser_class=BBCodeParser,
    renderer_class=None,  # No renderer for BBCode (parser only)
    renders_as_string=False,
    parser_required_packages=[],  # No external dependencies
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="",
    parser_options_class="all2md.options.bbcode.BBCodeParserOptions",
    renderer_options_class=None,
    description="Parse BBCode bulletin board markup to AST",
    priority=10,
)
