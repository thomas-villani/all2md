#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/mediawiki.py
"""MediaWiki rendering from AST.

This module provides the MediaWikiRenderer class which converts AST nodes
to MediaWiki markup text. The renderer supports configurable rendering options
for controlling output format suitable for Wikipedia and other MediaWiki-based wikis.

"""

from __future__ import annotations

from pathlib import Path
from typing import IO, Literal, Union

from all2md.ast.nodes import (
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
from all2md.ast.visitors import NodeVisitor
from all2md.converter_metadata import ConverterMetadata
from all2md.options.mediawiki import MediaWikiOptions
from all2md.renderers.base import BaseRenderer, InlineContentMixin
from all2md.utils.escape import escape_html_entities, escape_mediawiki
from all2md.utils.html_sanitizer import sanitize_html_content


class MediaWikiRenderer(NodeVisitor, InlineContentMixin, BaseRenderer):
    """Render AST nodes to MediaWiki markup text.

    This class implements the visitor pattern to traverse an AST and
    generate MediaWiki output suitable for Wikipedia and other MediaWiki-based wikis.

    Parameters
    ----------
    options : MediaWikiOptions or None, default = None
        MediaWiki rendering options

    Examples
    --------
    Basic usage:

        >>> from all2md.ast import Document, Heading, Text
        >>> from all2md.renderers.mediawiki import MediaWikiRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> renderer = MediaWikiRenderer()
        >>> wiki_text = renderer.render_to_string(doc)
        >>> print(wiki_text)
        = Title =

    """

    def __init__(self, options: MediaWikiOptions | None = None):
        """Initialize the MediaWiki renderer with options."""
        BaseRenderer._validate_options_type(options, MediaWikiOptions, "mediawiki")
        options = options or MediaWikiOptions()
        BaseRenderer.__init__(self, options)
        self.options: MediaWikiOptions = options
        self._output: list[str] = []
        self._list_level: int = 0
        self._list_ordered_stack: list[bool] = []  # Track ordered/unordered at each level

    def render_to_string(self, document: Document) -> str:
        """Render a document AST to MediaWiki markup string.

        Parameters
        ----------
        document : Document
            The document node to render

        Returns
        -------
        str
            MediaWiki markup text

        """
        self._output = []
        self._list_level = 0
        self._list_ordered_stack = []

        document.accept(self)

        result = "".join(self._output)
        return result.rstrip() + "\n"

    def visit_document(self, node: Document) -> None:
        """Render a Document node.

        Parameters
        ----------
        node : Document
            Document to render

        """
        for i, child in enumerate(node.children):
            child.accept(self)
            if i < len(node.children) - 1:
                self._output.append("\n\n")

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node.

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        content = self._render_inline_content(node.content)
        equals = "=" * node.level
        self._output.append(f"{equals} {content} {equals}")

    def visit_paragraph(self, node: Paragraph) -> None:
        """Render a Paragraph node.

        Parameters
        ----------
        node : Paragraph
            Paragraph to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(content)

    def visit_code_block(self, node: CodeBlock) -> None:
        """Render a CodeBlock node.

        Parameters
        ----------
        node : CodeBlock
            Code block to render

        """
        if node.language:
            self._output.append(f'<syntaxhighlight lang="{node.language}">\n')
            self._output.append(node.content)
            if not node.content.endswith("\n"):
                self._output.append("\n")
            self._output.append("</syntaxhighlight>")
        else:
            self._output.append("<pre>\n")
            self._output.append(node.content)
            if not node.content.endswith("\n"):
                self._output.append("\n")
            self._output.append("</pre>")

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render a BlockQuote node.

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        saved_output = self._output
        self._output = []

        for i, child in enumerate(node.children):
            child.accept(self)
            if i < len(node.children) - 1:
                self._output.append("\n\n")

        quoted = "".join(self._output)
        lines = quoted.split("\n")
        quoted_lines = [": " + line for line in lines]

        self._output = saved_output
        self._output.append("\n".join(quoted_lines))

    def visit_list(self, node: List) -> None:
        """Render a List node.

        Parameters
        ----------
        node : List
            List to render

        """
        self._list_level += 1
        self._list_ordered_stack.append(node.ordered)

        for i, item in enumerate(node.items):
            item.accept(self)
            if i < len(node.items) - 1:
                self._output.append("\n")

        self._list_level -= 1
        self._list_ordered_stack.pop()

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        # Determine list marker based on nesting level and ordered/unordered
        # MediaWiki uses * for unordered, # for ordered
        # Multiple chars for nesting: **, ***, etc. or ##, ###, etc.
        is_ordered = self._list_ordered_stack[-1] if self._list_ordered_stack else False
        marker_char = "#" if is_ordered else "*"
        marker = marker_char * self._list_level

        self._output.append(f"{marker} ")

        # Render children
        for i, child in enumerate(node.children):
            if i == 0:
                # First child inline with marker
                if isinstance(child, Paragraph):
                    content = self._render_inline_content(child.content)
                    self._output.append(content)
                else:
                    child.accept(self)
            else:
                # Subsequent children (nested elements)
                self._output.append("\n")
                child.accept(self)

    def visit_table(self, node: Table) -> None:
        """Render a Table node.

        Parameters
        ----------
        node : Table
            Table to render

        """
        self._output.append('{| class="wikitable"\n')

        # Render caption if present
        if node.caption:
            self._output.append(f"|+ {node.caption}\n")

        # Render header
        if node.header:
            first_cell = True
            for cell in node.header.cells:
                # Add colspan/rowspan attributes if needed
                span_attrs = ""
                if cell.colspan > 1:
                    span_attrs += f' colspan="{cell.colspan}"'
                if cell.rowspan > 1:
                    span_attrs += f' rowspan="{cell.rowspan}"'

                if first_cell:
                    self._output.append(f"!{span_attrs} ")
                    first_cell = False
                else:
                    self._output.append(f" !!{span_attrs} ")

                content = self._render_inline_content(cell.content)
                self._output.append(content)
            self._output.append("\n")

        # Render rows
        for row in node.rows:
            self._output.append("|-\n")
            first_cell = True
            for cell in row.cells:
                # Add colspan/rowspan attributes if needed
                span_attrs = ""
                if cell.colspan > 1:
                    span_attrs += f' colspan="{cell.colspan}"'
                if cell.rowspan > 1:
                    span_attrs += f' rowspan="{cell.rowspan}"'

                if first_cell:
                    self._output.append(f"|{span_attrs} ")
                    first_cell = False
                else:
                    self._output.append(f" ||{span_attrs} ")

                content = self._render_inline_content(cell.content)
                self._output.append(content)
            self._output.append("\n")

        self._output.append("|}")

    def visit_table_row(self, node: TableRow) -> None:
        """Render a TableRow node (handled by visit_table).

        Parameters
        ----------
        node : TableRow
            Table row to render

        """
        pass

    def visit_table_cell(self, node: TableCell) -> None:
        """Render a TableCell node (handled by visit_table).

        Parameters
        ----------
        node : TableCell
            Table cell to render

        """
        pass

    def visit_thematic_break(self, node: ThematicBreak) -> None:
        """Render a ThematicBreak node.

        Parameters
        ----------
        node : ThematicBreak
            Thematic break to render

        """
        self._output.append("----")

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Render an HTMLBlock node.

        Parameters
        ----------
        node : HTMLBlock
            HTML block to render

        """
        sanitized = sanitize_html_content(node.content, mode=self.options.html_passthrough_mode)
        if sanitized:
            self._output.append(sanitized)

    def visit_comment(self, node: Comment) -> None:
        """Render a Comment node according to comment_mode option.

        Parameters
        ----------
        node : Comment
            Comment block to render

        Notes
        -----
        Supports multiple rendering modes via comment_mode option:
        - "html": Use HTML comment syntax <!-- --> (default)
        - "visible": Render as visible text
        - "ignore": Skip comment entirely

        """
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            return

        # Format comment with metadata
        comment_text = node.content
        if node.metadata.get("author"):
            author = node.metadata.get("author")
            date = node.metadata.get("date", "")
            label = node.metadata.get("label", "")
            prefix = f"Comment {label}" if label else "Comment"
            if date:
                comment_text = f"{prefix} by {author} ({date}): {comment_text}"
            else:
                comment_text = f"{prefix} by {author}: {comment_text}"

        if comment_mode == "html":
            self._output.append(f"<!-- {comment_text} -->")
        elif comment_mode == "visible":
            # Render as visible text (no special formatting in MediaWiki)
            self._output.append(comment_text)

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        # MediaWiki is fairly lenient with special characters
        # but we apply minimal escaping for safety
        text = escape_mediawiki(node.content)
        self._output.append(text)

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis node.

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"''{content}''")

    def visit_strong(self, node: Strong) -> None:
        """Render a Strong node.

        Parameters
        ----------
        node : Strong
            Strong to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"'''{content}'''")

    def visit_code(self, node: Code) -> None:
        """Render a Code node.

        Parameters
        ----------
        node : Code
            Code to render

        Notes
        -----
        Code content is HTML-escaped to prevent markup injection and ensure
        special characters like <, >, and & display correctly.

        """
        # Escape HTML entities to prevent injection and correctly display special chars
        escaped_content = escape_html_entities(node.content)
        self._output.append(f"<code>{escaped_content}</code>")

    def visit_link(self, node: Link) -> None:
        """Render a Link node.

        Parameters
        ----------
        node : Link
            Link to render

        """
        content = self._render_inline_content(node.content)

        # Determine if this is an internal or external link
        # External links start with http://, https://, ftp://, etc.
        is_external = node.url.startswith(("http://", "https://", "ftp://", "ftps://", "mailto:"))

        if is_external:
            # External link: [URL display text]
            if len(node.content) == 1 and isinstance(node.content[0], Text):
                if node.content[0].content == node.url:
                    # Auto-link - just output the URL
                    self._output.append(node.url)
                    return
            self._output.append(f"[{node.url} {content}]")
        else:
            # Internal link: [[Page Name|Display Text]]
            if len(node.content) == 1 and isinstance(node.content[0], Text):
                if node.content[0].content == node.url:
                    # Simple internal link
                    self._output.append(f"[[{node.url}]]")
                    return
            self._output.append(f"[[{node.url}|{content}]]")

    def visit_image(self, node: Image) -> None:
        """Render an Image node.

        Parameters
        ----------
        node : Image
            Image to render

        Notes
        -----
        MediaWiki image syntax: [[File:filename|options|caption]]
        - When image_thumb=True and caption_mode is configured, renders with caption
        - Caption can be derived from alt_text or title metadata
        - alt= attribute and caption text can be controlled separately via image_caption_mode

        """
        # MediaWiki image syntax: [[File:filename|options|caption]]
        parts = [f"File:{node.url}"]

        if self.options.image_thumb:
            parts.append("thumb")

            # Handle caption rendering based on mode
            caption_text = node.title if hasattr(node, "title") and node.title else node.alt_text

            if self.options.image_caption_mode == "auto" and caption_text:
                # Auto mode: render both alt attribute and caption text
                if node.alt_text:
                    parts.append(f"alt={node.alt_text}")
                parts.append(caption_text)
            elif self.options.image_caption_mode == "alt_only" and node.alt_text:
                # Only render alt attribute, no caption
                parts.append(f"alt={node.alt_text}")
            elif self.options.image_caption_mode == "caption_only" and caption_text:
                # Only render caption, no alt attribute
                parts.append(caption_text)
        else:
            # When not thumbnail, just add alt if available
            if node.alt_text:
                parts.append(f"alt={node.alt_text}")

        self._output.append("[[" + "|".join(parts) + "]]")

    def visit_line_break(self, node: LineBreak) -> None:
        """Render a LineBreak node.

        Parameters
        ----------
        node : LineBreak
            Line break to render

        """
        if node.soft:
            # Soft breaks render as space in MediaWiki
            self._output.append(" ")
        else:
            # Hard break
            self._output.append("<br />")

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Render a Strikethrough node.

        Parameters
        ----------
        node : Strikethrough
            Strikethrough to render

        """
        content = self._render_inline_content(node.content)
        # MediaWiki uses <s> or <del> for strikethrough
        self._output.append(f"<s>{content}</s>")

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node.

        Parameters
        ----------
        node : Underline
            Underline to render

        """
        content = self._render_inline_content(node.content)
        if self.options.use_html_for_unsupported:
            # MediaWiki supports <u> for underline
            self._output.append(f"<u>{content}</u>")
        else:
            # Strip underline formatting
            self._output.append(content)

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node.

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        content = self._render_inline_content(node.content)
        # MediaWiki uses <sup> for superscript
        self._output.append(f"<sup>{content}</sup>")

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node.

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        content = self._render_inline_content(node.content)
        # MediaWiki uses <sub> for subscript
        self._output.append(f"<sub>{content}</sub>")

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Render an HTMLInline node.

        Parameters
        ----------
        node : HTMLInline
            Inline HTML to render

        """
        sanitized = sanitize_html_content(node.content, mode=self.options.html_passthrough_mode)
        if sanitized:
            self._output.append(sanitized)

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Render a CommentInline node according to comment_mode option.

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

        Notes
        -----
        Supports multiple rendering modes via comment_mode option:
        - "html": Use HTML comment syntax <!-- --> (default)
        - "visible": Render as visible text
        - "ignore": Skip comment entirely

        """
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            return

        # Format comment with metadata
        comment_text = node.content
        if node.metadata.get("author"):
            author = node.metadata.get("author")
            date = node.metadata.get("date", "")
            label = node.metadata.get("label", "")
            prefix = f"Comment {label}" if label else "Comment"
            if date:
                comment_text = f"[{prefix} by {author} ({date}): {comment_text}]"
            else:
                comment_text = f"[{prefix} by {author}: {comment_text}]"
        elif node.metadata.get("label"):
            label = node.metadata.get("label")
            comment_text = f"[Comment {label}: {comment_text}]"
        else:
            # Add brackets for inline visible comments without metadata
            if comment_mode == "visible":
                comment_text = f"[{comment_text}]"

        if comment_mode == "html":
            self._output.append(f"<!-- {comment_text} -->")
        elif comment_mode == "visible":
            self._output.append(comment_text)

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render a FootnoteReference node.

        Parameters
        ----------
        node : FootnoteReference
            Footnote reference to render

        """
        # MediaWiki uses <ref> tags for footnotes
        self._output.append(f'<ref name="{node.identifier}" />')

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Render a FootnoteDefinition node.

        Parameters
        ----------
        node : FootnoteDefinition
            Footnote definition to render

        """
        # MediaWiki footnote definitions are inline with <ref> tags
        self._output.append(f'<ref name="{node.identifier}">')
        for child in node.content:
            child.accept(self)
        self._output.append("</ref>")

    def visit_definition_list(self, node: DefinitionList) -> None:
        """Render a DefinitionList node.

        Parameters
        ----------
        node : DefinitionList
            Definition list to render

        """
        for i, (term, descriptions) in enumerate(node.items):
            if i > 0:
                self._output.append("\n")

            # Render term
            term_content = self._render_inline_content(term.content)
            self._output.append(f"; {term_content}")

            # Render descriptions
            for desc in descriptions:
                self._output.append("\n: ")
                for child in desc.content:
                    child.accept(self)

    def visit_definition_term(self, node: DefinitionTerm) -> None:
        """Render a DefinitionTerm node (handled by visit_definition_list).

        Parameters
        ----------
        node : DefinitionTerm
            Definition term to render

        """
        pass

    def visit_definition_description(self, node: DefinitionDescription) -> None:
        """Render a DefinitionDescription node (handled by visit_definition_list).

        Parameters
        ----------
        node : DefinitionDescription
            Definition description to render

        """
        pass

    def visit_math_inline(self, node: MathInline) -> None:
        """Render a MathInline node.

        Parameters
        ----------
        node : MathInline
            Inline math to render

        """
        # MediaWiki uses <math> tags for LaTeX math
        preferred: Literal["latex", "mathml", "html"] = "latex"
        content, notation = node.get_preferred_representation(preferred)
        self._output.append(f"<math>{content}</math>")

    def visit_math_block(self, node: MathBlock) -> None:
        """Render a MathBlock node.

        Parameters
        ----------
        node : MathBlock
            Math block to render

        """
        # MediaWiki uses <math display="block"> for block-level math
        preferred: Literal["latex", "mathml", "html"] = "latex"
        content, notation = node.get_preferred_representation(preferred)
        self._output.append('<math display="block">\n')
        self._output.append(content)
        if not content.endswith("\n"):
            self._output.append("\n")
        self._output.append("</math>")

    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render AST to MediaWiki markup and write to output.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        """
        mediawiki_text = self.render_to_string(doc)
        self.write_text_output(mediawiki_text, output)


# Converter metadata for registry auto-discovery
CONVERTER_METADATA = ConverterMetadata(
    format_name="mediawiki",
    extensions=[".wiki", ".mw"],
    mime_types=["text/x-wiki"],
    magic_bytes=[],
    renderer_class=MediaWikiRenderer,
    renders_as_string=True,
    parser_required_packages=[],
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="",
    renderer_options_class=MediaWikiOptions,
    description="Render AST to MediaWiki markup.",
    priority=5,
)
