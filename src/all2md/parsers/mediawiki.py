#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/mediawiki.py
"""MediaWiki/WikiText to AST converter.

This module provides conversion from MediaWiki markup (WikiText) to AST representation
using the mwparserfromhell parser. It enables bidirectional transformation by parsing
wiki markup into the same AST structure used for other formats.

"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import IO, Any, Optional, Union, cast

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    CommentInline,
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
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.constants import DEPS_MEDIAWIKI
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.mediawiki import MediaWikiParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.html_sanitizer import sanitize_html_content, sanitize_url
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


class MediaWikiParser(BaseParser):
    r"""Convert MediaWiki/WikiText to AST representation.

    This converter uses mwparserfromhell to parse WikiText and builds an AST that
    matches the structure used throughout all2md, enabling bidirectional
    conversion and transformation pipelines.

    Parameters
    ----------
    options : MediaWikiParserOptions or None, default = None
        Parser configuration options

    Examples
    --------
    Basic parsing:

        >>> parser = MediaWikiParser()
        >>> doc = parser.parse("== Heading ==\\n\\nThis is '''bold'''.")

    With options:

        >>> options = MediaWikiParserOptions(parse_templates=True)
        >>> parser = MediaWikiParser(options)
        >>> doc = parser.parse(wikitext)

    """

    def __init__(
        self, options: MediaWikiParserOptions | None = None, progress_callback: Optional[ProgressCallback] = None
    ):
        """Initialize the MediaWiki parser with options and progress callback."""
        BaseParser._validate_options_type(options, MediaWikiParserOptions, "mediawiki")
        options = options or MediaWikiParserOptions()
        super().__init__(options, progress_callback)
        self.options: MediaWikiParserOptions = options

    @requires_dependencies("mediawiki", DEPS_MEDIAWIKI)
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse MediaWiki input into AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            MediaWiki/WikiText input to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw WikiText bytes
            - WikiText string

        Returns
        -------
        Document
            AST document node

        Raises
        ------
        DependencyError
            If mwparserfromhell is not installed
        ParsingError
            If parsing fails

        """
        # Load WikiText content from various input types
        wikitext_content = self._load_text_content(input_data)

        import mwparserfromhell

        # Parse WikiText to mwparserfromhell Wikicode
        try:
            wikicode = mwparserfromhell.parse(wikitext_content)
        except Exception as e:
            raise ParsingError(f"Failed to parse MediaWiki markup: {e}") from e

        # Extract metadata before processing
        metadata = self.extract_metadata(wikicode)

        # Convert wikicode to AST
        children = self._process_wikicode(wikicode)

        return Document(children=children, metadata=metadata.to_dict())

    def _flush_inline_buffer(self, inline_buffer: list[Node], result: list[Node]) -> None:
        """Flush inline buffer to result as a paragraph.

        Parameters
        ----------
        inline_buffer : list of Node
            Buffer of inline nodes to flush
        result : list of Node
            Result list to append paragraph to

        """
        if inline_buffer:
            result.append(Paragraph(content=inline_buffer.copy()))
            inline_buffer.clear()

    def _handle_heading_node(self, node: Any, inline_buffer: list[Node], result: list[Node]) -> int:
        """Handle a Heading node.

        Parameters
        ----------
        node : Any
            The heading node
        inline_buffer : list of Node
            Current inline buffer
        result : list of Node
            Result list

        Returns
        -------
        int
            Number of nodes consumed (always 1 for headings)

        """
        self._flush_inline_buffer(inline_buffer, result)
        heading = self._process_heading(node)
        if heading:
            result.append(heading)
        return 1

    def _handle_tag_node(
        self, node: Any, inline_buffer: list[Node], result: list[Node], nodes_list: list[Any], i: int
    ) -> int:
        """Handle a Tag node (block-level or inline).

        Parameters
        ----------
        node : Any
            The tag node
        inline_buffer : list of Node
            Current inline buffer
        result : list of Node
            Result list
        nodes_list : list of Any
            Full list of nodes being processed
        i : int
            Current index

        Returns
        -------
        int
            Number of nodes consumed

        """
        tag_name = str(node.tag).lower()

        # Block-level code blocks
        if tag_name in ("pre", "syntaxhighlight", "source"):
            self._flush_inline_buffer(inline_buffer, result)
            code_block = self._process_inline_tag(node)
            if isinstance(code_block, CodeBlock):
                result.append(code_block)
            return 1

        # Wiki markup tags
        if hasattr(node, "wiki_markup") and node.wiki_markup:
            if node.wiki_markup in ("*", "#"):
                self._flush_inline_buffer(inline_buffer, result)
                list_node, consumed = self._parse_list_from_position(nodes_list, i)
                if list_node:
                    result.append(list_node)
                return consumed

            elif node.wiki_markup == "{|":
                self._flush_inline_buffer(inline_buffer, result)
                table = self._process_table(node)
                if table:
                    result.append(table)
                return 1

            elif node.wiki_markup == "----":
                self._flush_inline_buffer(inline_buffer, result)
                result.append(ThematicBreak())
                return 1

            elif node.wiki_markup == ":":
                self._flush_inline_buffer(inline_buffer, result)
                quote, consumed = self._parse_blockquote_from_position(nodes_list, i)
                if quote:
                    result.append(quote)
                return consumed

        # Inline formatting tag
        inline_node = self._process_inline_tag(node)
        if inline_node:
            inline_buffer.append(inline_node)
        return 1

    def _handle_wikilink_node(self, node: Any, inline_buffer: list[Node]) -> int:
        """Handle a Wikilink node.

        Parameters
        ----------
        node : Any
            The wikilink node
        inline_buffer : list of Node
            Current inline buffer

        Returns
        -------
        int
            Number of nodes consumed (always 1)

        """
        inline_node = self._process_wikilink(node)
        if inline_node:
            inline_buffer.append(inline_node)
        return 1

    def _handle_external_link_node(self, node: Any, inline_buffer: list[Node]) -> int:
        """Handle an ExternalLink node.

        Parameters
        ----------
        node : Any
            The external link node
        inline_buffer : list of Node
            Current inline buffer

        Returns
        -------
        int
            Number of nodes consumed (always 1)

        """
        inline_node = self._process_external_link(node)
        if inline_node:
            inline_buffer.append(inline_node)
        return 1

    def _handle_template_node(self, node: Any, inline_buffer: list[Node]) -> int:
        """Handle a Template node.

        Parameters
        ----------
        node : Any
            The template node
        inline_buffer : list of Node
            Current inline buffer

        Returns
        -------
        int
            Number of nodes consumed (always 1)

        """
        if self.options.parse_templates:
            inline_node = self._process_template(node)
            if inline_node:
                inline_buffer.append(inline_node)
        return 1

    def _handle_comment_node(self, node: Any, inline_buffer: list[Node]) -> int:
        """Handle a Comment node.

        Parameters
        ----------
        node : Any
            The comment node
        inline_buffer : list of Node
            Current inline buffer

        Returns
        -------
        int
            Number of nodes consumed (always 1)

        """
        if not self.options.strip_comments:
            inline_buffer.append(CommentInline(content=str(node), metadata={"comment_type": "wiki"}))
        return 1

    def _handle_text_node(self, node: Any, inline_buffer: list[Node], result: list[Node]) -> int:
        """Handle a Text node.

        Parameters
        ----------
        node : Any
            The text node
        inline_buffer : list of Node
            Current inline buffer
        result : list of Node
            Result list

        Returns
        -------
        int
            Number of nodes consumed (always 1)

        """
        text_content = str(node)

        # Handle text with paragraph breaks
        if "\n\n" in text_content:
            parts = text_content.split("\n\n")
            for idx, part in enumerate(parts):
                part = part.strip()

                if re.match(r"^-{4,}$", part):
                    self._flush_inline_buffer(inline_buffer, result)
                    result.append(ThematicBreak())
                elif part:
                    if self._is_block_quote(part):
                        self._flush_inline_buffer(inline_buffer, result)
                        quote = self._process_block_quote(part)
                        if quote:
                            result.append(quote)
                    else:
                        inline_buffer.append(Text(content=part))

                # Flush after each part except the last
                if idx < len(parts) - 1:
                    self._flush_inline_buffer(inline_buffer, result)
        else:
            # Single line text
            text_content = text_content.strip()
            if text_content:
                if re.match(r"^-{4,}$", text_content):
                    self._flush_inline_buffer(inline_buffer, result)
                    result.append(ThematicBreak())
                elif self._is_block_quote(text_content):
                    self._flush_inline_buffer(inline_buffer, result)
                    quote = self._process_block_quote(text_content)
                    if quote:
                        result.append(quote)
                else:
                    inline_buffer.append(Text(content=text_content))

        return 1

    def _process_wikicode(self, wikicode: Any) -> list[Node]:
        """Process mwparserfromhell Wikicode into AST nodes.

        Parameters
        ----------
        wikicode : mwparserfromhell.Wikicode
            Parsed WikiText

        Returns
        -------
        list of Node
            AST nodes

        """
        result: list[Node] = []
        inline_buffer: list[Node] = []

        nodes_list = list(wikicode.nodes)
        i = 0

        while i < len(nodes_list):
            node = nodes_list[i]
            node_type = type(node).__name__

            # Dispatch to appropriate handler based on node type
            if node_type == "Heading":
                consumed = self._handle_heading_node(node, inline_buffer, result)
            elif node_type == "Tag":
                consumed = self._handle_tag_node(node, inline_buffer, result, nodes_list, i)
            elif node_type == "Wikilink":
                consumed = self._handle_wikilink_node(node, inline_buffer)
            elif node_type == "ExternalLink":
                consumed = self._handle_external_link_node(node, inline_buffer)
            elif node_type == "Template":
                consumed = self._handle_template_node(node, inline_buffer)
            elif node_type == "Comment":
                consumed = self._handle_comment_node(node, inline_buffer)
            elif node_type == "Text":
                consumed = self._handle_text_node(node, inline_buffer, result)
            else:
                # Unknown node type - treat as text
                inline_buffer.append(Text(content=str(node)))
                consumed = 1

            i += consumed

        # Flush remaining inline buffer
        self._flush_inline_buffer(inline_buffer, result)

        return result

    def _process_heading(self, heading: Any) -> Heading | None:
        """Process a MediaWiki heading.

        Parameters
        ----------
        heading : mwparserfromhell.nodes.Heading
            Heading node

        Returns
        -------
        Heading or None
            Heading AST node

        """
        level = heading.level
        if level < 1:
            level = 1
        elif level > 6:
            level = 6

        # Get heading title and process inline content
        title_wikicode = heading.title
        content = self._process_inline_wikicode(title_wikicode)

        return Heading(level=level, content=content)

    def _process_inline_wikicode(self, wikicode: Any) -> list[Node]:
        """Process inline wikicode content into AST nodes.

        Parameters
        ----------
        wikicode : mwparserfromhell.Wikicode
            Inline wikicode to process

        Returns
        -------
        list of Node
            Inline AST nodes

        """
        result: list[Node] = []

        for node in wikicode.nodes:
            node_type = type(node).__name__

            if node_type == "Tag":
                inline_node = self._process_inline_tag(node)
                if inline_node:
                    result.append(inline_node)

            elif node_type == "Wikilink":
                inline_node = self._process_wikilink(node)
                if inline_node:
                    result.append(inline_node)

            elif node_type == "ExternalLink":
                inline_node = self._process_external_link(node)
                if inline_node:
                    result.append(inline_node)

            elif node_type == "Template":
                if self.options.parse_templates:
                    inline_node = self._process_template(node)
                    if inline_node:
                        result.append(inline_node)

            elif node_type == "Text":
                text = str(node).strip()
                if text:
                    result.append(Text(content=text))

            else:
                # Unknown - treat as text
                text = str(node).strip()
                if text:
                    result.append(Text(content=text))

        return result if result else [Text(content="")]

    def _process_inline_tag(self, tag: Any) -> Node | None:
        """Process an inline Tag node.

        Parameters
        ----------
        tag : mwparserfromhell.nodes.Tag
            Tag node

        Returns
        -------
        Node or None
            Inline AST node

        """
        tag_name = str(tag.tag).lower()

        # Check wiki markup for bold/italic
        if hasattr(tag, "wiki_markup") and tag.wiki_markup:
            if tag.wiki_markup == "'''":
                # Bold
                content = self._process_inline_wikicode(tag.contents)
                return Strong(content=content)
            elif tag.wiki_markup == "''":
                # Italic
                content = self._process_inline_wikicode(tag.contents)
                return Emphasis(content=content)

        # HTML-style tags
        if tag_name == "b" or tag_name == "strong":
            content = self._process_inline_wikicode(tag.contents)
            return Strong(content=content)
        elif tag_name == "i" or tag_name == "em":
            content = self._process_inline_wikicode(tag.contents)
            return Emphasis(content=content)
        elif tag_name == "code" or tag_name == "tt":
            return Code(content=str(tag.contents).strip())
        elif tag_name == "u":
            content = self._process_inline_wikicode(tag.contents)
            return Underline(content=content)
        elif tag_name == "s" or tag_name == "del" or tag_name == "strike":
            content = self._process_inline_wikicode(tag.contents)
            return Strikethrough(content=content)
        elif tag_name == "br":
            return LineBreak(soft=False)
        elif tag_name == "nowiki":
            # Preserve as code
            return Code(content=str(tag.contents))
        elif tag_name == "pre":
            # Block code
            return CodeBlock(content=str(tag.contents))
        elif tag_name == "syntaxhighlight" or tag_name == "source":
            # Code block with language
            language = None
            if self.options.parse_tags and tag.attributes:
                for attr in tag.attributes:
                    if str(attr.name).lower() == "lang":
                        language = str(attr.value).strip().strip("\"'")
                        break
            return CodeBlock(content=str(tag.contents), language=language)
        else:
            # Generic HTML tag - sanitize
            tag_str = str(tag)
            sanitized = sanitize_html_content(tag_str, mode=self.options.html_passthrough_mode)
            if sanitized:
                return HTMLInline(content=sanitized)

        return None

    def _process_wikilink(self, wikilink: Any) -> Node | None:
        """Process a MediaWiki internal link [[...]].

        Parameters
        ----------
        wikilink : mwparserfromhell.nodes.Wikilink
            Wikilink node

        Returns
        -------
        Node or None
            Link or Image AST node

        """
        title = str(wikilink.title).strip()
        text = str(wikilink.text).strip() if wikilink.text else title

        # Check if this is a file/image link
        if title.startswith("File:") or title.startswith("Image:"):
            # Remove the prefix
            image_url = title.split(":", 1)[1] if ":" in title else title
            # Sanitize URL
            image_url = sanitize_url(image_url)
            return Image(url=image_url, alt_text=text)

        # Regular internal link
        # Sanitize URL
        url = sanitize_url(title)
        content = [Text(content=text)]
        return Link(url=url, content=cast(list[Node], content))

    def _process_external_link(self, extlink: Any) -> Link | None:
        """Process a MediaWiki external link [http://...].

        Parameters
        ----------
        extlink : mwparserfromhell.nodes.ExternalLink
            External link node

        Returns
        -------
        Link or None
            Link AST node

        """
        url = str(extlink.url).strip()
        title = str(extlink.title).strip() if extlink.title else url

        # Sanitize URL
        url = sanitize_url(url)
        content = [Text(content=title)]
        return Link(url=url, content=cast(list[Node], content))

    def _process_template(self, template: Any) -> HTMLInline | None:
        """Process a MediaWiki template {{...}}.

        Parameters
        ----------
        template : mwparserfromhell.nodes.Template
            Template node

        Returns
        -------
        HTMLInline or None
            HTMLInline node with template content

        """
        # Convert template to string representation
        template_str = str(template)

        # Apply HTML sanitization based on passthrough mode
        sanitized = sanitize_html_content(template_str, mode=self.options.html_passthrough_mode)

        if sanitized:
            return HTMLInline(content=sanitized)
        return None

    def _parse_list_from_position(self, nodes_list: list[Any], start_idx: int) -> tuple[List | None, int]:
        """Parse a list starting from a position in the nodes list.

        Parameters
        ----------
        nodes_list : list
            List of all nodes
        start_idx : int
            Starting index

        Returns
        -------
        tuple of (List or None, int)
            Parsed list and number of nodes consumed

        """
        items: list[ListItem] = []
        ordered = False
        i = start_idx

        # Determine if ordered or unordered from first marker
        first_node = nodes_list[i]
        if hasattr(first_node, "wiki_markup"):
            ordered = first_node.wiki_markup == "#"

        # Determine expected marker character based on list type
        expected_marker = "#" if ordered else "*"

        # Collect list items
        while i < len(nodes_list):
            node = nodes_list[i]
            node_type = type(node).__name__

            # Check if this is a list marker of the same type as the first one
            # Stop collecting if we encounter a different marker type
            if node_type == "Tag" and hasattr(node, "wiki_markup") and node.wiki_markup == expected_marker:
                # This is a list marker of the correct type
                # Next node should be the item text
                i += 1
                if i < len(nodes_list):
                    text_node = nodes_list[i]
                    text_content = str(text_node).strip()

                    # Extract just the first line (items are one per line)
                    if "\n" in text_content:
                        text_content = text_content.split("\n")[0].strip()

                    if text_content:
                        item_content = [Text(content=text_content)]
                        items.append(ListItem(children=[Paragraph(content=cast(list[Node], item_content))]))

                    i += 1
                else:
                    break
            else:
                # Not a list marker of the expected type - end of list
                break

        if not items:
            return None, 1

        consumed = i - start_idx
        return List(ordered=ordered, items=items), consumed

    def _parse_blockquote_from_position(self, nodes_list: list[Any], start_idx: int) -> tuple[BlockQuote | None, int]:
        """Parse a block quote starting from a position in the nodes list.

        Parameters
        ----------
        nodes_list : list
            List of all nodes
        start_idx : int
            Starting index

        Returns
        -------
        tuple of (BlockQuote or None, int)
            Parsed block quote and number of nodes consumed

        """
        text_parts: list[str] = []
        i = start_idx

        # Collect block quote lines
        while i < len(nodes_list):
            node = nodes_list[i]
            node_type = type(node).__name__

            # Check if this is a block quote marker (:)
            if node_type == "Tag" and hasattr(node, "wiki_markup") and node.wiki_markup == ":":
                # This is a quote marker
                # Next node should be the quoted text
                i += 1
                if i < len(nodes_list):
                    text_node = nodes_list[i]
                    text_content = str(text_node).strip()

                    # Extract just the first line (quote lines are one per line)
                    if "\n" in text_content:
                        text_content = text_content.split("\n")[0].strip()

                    if text_content:
                        text_parts.append(text_content)

                    i += 1
                else:
                    break
            else:
                # Not a block quote marker - end of quote
                break

        if not text_parts:
            return None, 1

        quote_text = " ".join(text_parts)
        content = [Text(content=quote_text)]
        consumed = i - start_idx
        return BlockQuote(children=[Paragraph(content=cast(list[Node], content))]), consumed

    def _process_table(self, table_tag: Any) -> Table | None:
        """Parse a MediaWiki table.

        Parameters
        ----------
        table_tag : mwparserfromhell.nodes.Tag
            Table tag node

        Returns
        -------
        Table or None
            Table AST node

        """
        # Get table contents
        contents = str(table_tag.contents)
        lines = contents.split("\n")

        rows: list[TableRow] = []
        header: Optional[TableRow] = None
        current_row_cells: list[TableCell] = []
        in_header = False

        for line in lines:
            line = line.strip()

            if not line or line.startswith("|-"):
                # Row separator
                if current_row_cells:
                    if in_header:
                        header = TableRow(cells=current_row_cells, is_header=True)
                        in_header = False
                    else:
                        rows.append(TableRow(cells=current_row_cells, is_header=False))
                    current_row_cells = []
                continue

            elif line.startswith("|+"):
                # Caption - skip for now
                continue

            elif line.startswith("!"):
                # Header cell
                in_header = True
                cell_text = line[1:].strip()
                # Handle multiple cells on one line (!! separator)
                cell_texts = cell_text.split("!!")
                for ct in cell_texts:
                    # Remove cell attributes (e.g., style="...")
                    ct = re.sub(r"^\s*[^|]*\|\s*", "", ct).strip()
                    content = [Text(content=ct)]
                    current_row_cells.append(TableCell(content=cast(list[Node], content)))

            elif line.startswith("|"):
                # Data cell
                cell_text = line[1:].strip()
                # Handle multiple cells on one line (|| separator)
                cell_texts = cell_text.split("||")
                for ct in cell_texts:
                    # Remove cell attributes
                    ct = re.sub(r"^\s*[^|]*\|\s*", "", ct).strip()
                    content = [Text(content=ct)]
                    current_row_cells.append(TableCell(content=cast(list[Node], content)))

        # Add last row if any
        if current_row_cells:
            if in_header:
                header = TableRow(cells=current_row_cells, is_header=True)
            else:
                rows.append(TableRow(cells=current_row_cells, is_header=False))

        if not rows and not header:
            return None

        return Table(header=header, rows=rows)

    def _is_block_quote(self, text: str) -> bool:
        """Check if text is a block quote.

        Parameters
        ----------
        text : str
            Text to check

        Returns
        -------
        bool
            True if text is a block quote

        """
        lines = text.split("\n")
        return all(line.strip().startswith(":") or not line.strip() for line in lines)

    def _process_block_quote(self, text: str) -> BlockQuote:
        """Parse a block quote.

        Parameters
        ----------
        text : str
            Block quote text

        Returns
        -------
        BlockQuote
            Block quote AST node

        """
        lines = text.split("\n")
        # Remove leading : from each line
        clean_lines = []
        for line in lines:
            if line.strip().startswith(":"):
                clean_lines.append(line.strip()[1:].strip())
            else:
                clean_lines.append(line)

        quote_text = " ".join(clean_lines).strip()
        content = [Text(content=quote_text)]
        return BlockQuote(children=[Paragraph(content=cast(list[Node], content))])

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from MediaWiki document.

        Parameters
        ----------
        document : mwparserfromhell.Wikicode
            Parsed MediaWiki document

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        Notes
        -----
        MediaWiki documents may have metadata in templates or special syntax.
        This implementation extracts basic information where available.

        """
        metadata = DocumentMetadata()

        # Try to extract title from first heading
        try:
            headings = document.filter_headings()
            if headings:
                first_heading = headings[0]
                metadata.title = str(first_heading.title).strip()
        except Exception:
            pass

        return metadata


# Converter metadata for registry auto-discovery
CONVERTER_METADATA = ConverterMetadata(
    format_name="mediawiki",
    extensions=[".wiki", ".mw"],
    mime_types=["text/x-wiki"],
    magic_bytes=[],
    parser_class=MediaWikiParser,
    renderer_class="all2md.renderers.mediawiki.MediaWikiRenderer",
    renders_as_string=True,
    parser_required_packages=[("mwparserfromhell", "mwparserfromhell", "")],
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="MediaWiki parsing requires 'mwparserfromhell'. Install with: pip install 'all2md[mediawiki]'",
    parser_options_class=MediaWikiParserOptions,
    renderer_options_class="all2md.options.mediawiki.MediaWikiOptions",
    description="Parse MediaWiki/WikiText to AST and render AST to MediaWiki",
    priority=10,
)
