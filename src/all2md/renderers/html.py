#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/html.py
"""HTML rendering from AST.

This module provides the HtmlRenderer class which converts AST nodes
to HTML format. The renderer supports standalone documents with CSS
styling, as well as HTML fragments for embedding in other documents.

The rendering process uses the visitor pattern to traverse the AST and
generate HTML output with appropriate semantic markup.

"""

from __future__ import annotations

from pathlib import Path
from typing import IO, TYPE_CHECKING, Union

from all2md.utils.html_utils import escape_html, render_math_html

if TYPE_CHECKING:
    try:
        from jinja2 import Environment, FileSystemLoader, Template
    except ImportError:
        pass

from all2md.ast.nodes import (
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
from all2md.options import HtmlRendererOptions
from all2md.renderers.base import BaseRenderer


class HtmlRenderer(NodeVisitor, BaseRenderer):
    """Render AST nodes to HTML format.

    This class implements the visitor pattern to traverse an AST and
    generate HTML output. It supports both standalone HTML documents
    with CSS styling and HTML fragments for embedding.

    Parameters
    ----------
    options : HtmlRendererOptions or None, default = None
        HTML rendering options

    Examples
    --------
    Basic usage:

        >>> from all2md.ast import Document, Heading, Text
        >>> from all2md.options import HtmlRendererOptions
        >>> from all2md.renderers.html import HtmlRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> options = HtmlRendererOptions()
        >>> renderer = HtmlRenderer(options)
        >>> html = renderer.render_to_string(doc)

    """

    def __init__(self, options: HtmlRendererOptions | None = None):
        options = options or HtmlRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: HtmlRendererOptions = options
        self._output: list[str] = []
        self._headings: list[tuple[int, str, str]] = []  # (level, id, text)
        self._heading_id_counter: int = 0
        self._footnote_definitions: list[FootnoteDefinition] = []

    def render_to_string(self, document: Document) -> str:
        """Render a document AST to HTML string.

        Parameters
        ----------
        document : Document
            The document node to render

        Returns
        -------
        str
            HTML text

        """
        self._output = []
        self._headings = []
        self._heading_id_counter = 0
        self._footnote_definitions = []

        # Render content
        document.accept(self)

        content = ''.join(self._output)

        # Wrap in HTML document if standalone
        if self.options.standalone:
            return self._wrap_in_document(document, content)

        return content

    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render the AST to HTML and write to output.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        """
        html_text = self.render_to_string(doc)

        if isinstance(output, (str, Path)):
            Path(output).write_text(html_text, encoding="utf-8")
        else:
            if hasattr(output, 'mode') and 'b' in output.mode:
                output.write(html_text.encode('utf-8'))
            else:
                output.write(html_text)

    def _wrap_in_document(self, doc: Document, content: str) -> str:
        """Wrap content in a complete HTML document.

        Parameters
        ----------
        doc : Document
            Document node with metadata
        content : str
            Rendered HTML content

        Returns
        -------
        str
            Complete HTML document

        """
        # Extract title from metadata or first heading
        title = doc.metadata.get('title', 'Document') if doc.metadata else 'Document'

        # Build HTML document
        parts = ['<!DOCTYPE html>', '<html lang="en">', '<head>']
        parts.append('<meta charset="UTF-8">')
        parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
        parts.append(f'<title>{escape_html(str(title), enabled=self.options.escape_html)}</title>')

        # Add CSS
        if self.options.css_style == 'embedded':
            parts.append('<style>')
            parts.append(self._generate_default_css())
            parts.append('</style>')
        elif self.options.css_style == 'external' and self.options.css_file:
            parts.append(f'<link rel="stylesheet" href="{self.options.css_file}">')

        # Add math renderer scripts
        if self.options.math_renderer == 'mathjax':
            parts.append('<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>')
        elif self.options.math_renderer == 'katex':
            parts.append('<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">')
            parts.append('<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>')
            parts.append('<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>')

        parts.append('</head>')
        parts.append('<body>')

        # Add TOC if requested
        if self.options.include_toc and self._headings:
            parts.append('<nav id="table-of-contents">')
            parts.append('<h2>Table of Contents</h2>')
            parts.append(self._generate_toc())
            parts.append('</nav>')

        parts.append('<main>')
        parts.append(content)
        parts.append('</main>')

        # Add footnotes section if any
        if self._footnote_definitions:
            parts.append('<section id="footnotes">')
            parts.append('<h2>Footnotes</h2>')
            parts.append('<ol>')
            for footnote in self._footnote_definitions:
                parts.append(f'<li id="fn-{footnote.identifier}">')
                for child in footnote.content:
                    saved_output = self._output
                    self._output = []
                    child.accept(self)
                    parts.append(''.join(self._output))
                    self._output = saved_output
                parts.append(f' <a href="#fnref-{footnote.identifier}">↩</a></li>')
            parts.append('</ol>')
            parts.append('</section>')

        parts.append('</body>')
        parts.append('</html>')

        return '\n'.join(parts)

    def _generate_default_css(self) -> str:
        """Generate default CSS styles.

        Returns
        -------
        str
            CSS stylesheet

        """
        return """
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    line-height: 1.6;
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem;
    color: #333;
}

h1, h2, h3, h4, h5, h6 {
    margin-top: 1.5rem;
    margin-bottom: 0.5rem;
    font-weight: 600;
    line-height: 1.25;
}

h1 { font-size: 2rem; border-bottom: 1px solid #eee; padding-bottom: 0.3rem; }
h2 { font-size: 1.5rem; }
h3 { font-size: 1.25rem; }
h4 { font-size: 1rem; }
h5 { font-size: 0.875rem; }
h6 { font-size: 0.85rem; color: #666; }

p { margin: 1rem 0; }

code {
    background-color: #f5f5f5;
    padding: 0.2em 0.4em;
    border-radius: 3px;
    font-family: "Courier New", Courier, monospace;
    font-size: 0.9em;
}

pre {
    background-color: #f5f5f5;
    padding: 1rem;
    border-radius: 5px;
    overflow-x: auto;
}

pre code {
    background-color: transparent;
    padding: 0;
}

blockquote {
    border-left: 4px solid #ddd;
    padding-left: 1rem;
    margin-left: 0;
    color: #666;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 1rem 0;
}

th, td {
    border: 1px solid #ddd;
    padding: 0.5rem;
    text-align: left;
}

th {
    background-color: #f5f5f5;
    font-weight: 600;
}

img {
    max-width: 100%;
    height: auto;
}

a {
    color: #0066cc;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

ul, ol {
    padding-left: 2rem;
    margin: 1rem 0;
}

hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 2rem 0;
}

#table-of-contents {
    background-color: #f9f9f9;
    border: 1px solid #ddd;
    border-radius: 5px;
    padding: 1rem;
    margin-bottom: 2rem;
}

#table-of-contents h2 {
    margin-top: 0;
    font-size: 1.2rem;
}

#footnotes {
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid #ddd;
    font-size: 0.9em;
}
"""

    def _generate_toc(self) -> str:
        """Generate table of contents HTML from collected headings.

        Returns
        -------
        str
            TOC HTML

        """
        if not self._headings:
            return ''

        parts = ['<ul>']
        for level, heading_id, text in self._headings:
            indent = '  ' * (level - 1)
            parts.append(
                f'{indent}<li><a href="#{heading_id}">{escape_html(text, enabled=self.options.escape_html)}</a></li>'
            )
        parts.append('</ul>')

        return '\n'.join(parts)

    def _render_inline_content(self, content: list[Node]) -> str:
        """Render a list of inline nodes to HTML.

        Parameters
        ----------
        content : list of Node
            Inline nodes to render

        Returns
        -------
        str
            Rendered HTML

        """
        saved_output = self._output
        self._output = []

        for node in content:
            node.accept(self)

        result = ''.join(self._output)
        self._output = saved_output
        return result

    def visit_document(self, node: Document) -> None:
        """Render a Document node.

        Parameters
        ----------
        node : Document
            Document to render

        """
        for child in node.children:
            child.accept(self)

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node.

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        level = min(6, max(1, node.level))
        content = self._render_inline_content(node.content)

        # Generate heading ID for TOC
        heading_id = f'heading-{self._heading_id_counter}'
        self._heading_id_counter += 1

        # Store for TOC
        self._headings.append((level, heading_id, content))

        self._output.append(f'<h{level} id="{heading_id}">{content}</h{level}>\n')

    def visit_paragraph(self, node: Paragraph) -> None:
        """Render a Paragraph node.

        Parameters
        ----------
        node : Paragraph
            Paragraph to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f'<p>{content}</p>\n')

    def visit_code_block(self, node: CodeBlock) -> None:
        """Render a CodeBlock node.

        Parameters
        ----------
        node : CodeBlock
            Code block to render

        """
        lang_class = ''
        if self.options.syntax_highlighting and node.language:
            lang_class = f' class="language-{node.language}"'

        escaped_content = escape_html(node.content, enabled=self.options.escape_html)
        self._output.append(f'<pre><code{lang_class}>{escaped_content}</code></pre>\n')

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render a BlockQuote node.

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        self._output.append('<blockquote>\n')

        for child in node.children:
            child.accept(self)

        self._output.append('</blockquote>\n')

    def visit_list(self, node: List) -> None:
        """Render a List node.

        Parameters
        ----------
        node : List
            List to render

        """
        tag = 'ol' if node.ordered else 'ul'
        start_attr = f' start="{node.start}"' if node.ordered and node.start != 1 else ''

        self._output.append(f'<{tag}{start_attr}>\n')

        for item in node.items:
            item.accept(self)

        self._output.append(f'</{tag}>\n')

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        self._output.append('<li>')

        # Handle task lists
        if node.task_status:
            checked = ' checked' if node.task_status == 'checked' else ''
            self._output.append(f'<input type="checkbox"{checked} disabled> ')

        for child in node.children:
            child.accept(self)

        self._output.append('</li>\n')

    def visit_table(self, node: Table) -> None:
        """Render a Table node.

        Parameters
        ----------
        node : Table
            Table to render

        """
        self._output.append('<table>\n')

        # Render caption if present
        if node.caption:
            caption = escape_html(node.caption, enabled=self.options.escape_html)
            self._output.append(f'<caption>{caption}</caption>\n')

        # Render header
        if node.header:
            self._output.append('<thead>\n<tr>')
            for i, cell in enumerate(node.header.cells):
                align = ''
                if node.alignments and i < len(node.alignments) and node.alignments[i]:
                    align = f' style="text-align: {node.alignments[i]}"'
                content = self._render_inline_content(cell.content)
                self._output.append(f'<th{align}>{content}</th>')
            self._output.append('</tr>\n</thead>\n')

        # Render body
        if node.rows:
            self._output.append('<tbody>\n')
            for row in node.rows:
                self._output.append('<tr>')
                for i, cell in enumerate(row.cells):
                    align = ''
                    if node.alignments and i < len(node.alignments) and node.alignments[i]:
                        align = f' style="text-align: {node.alignments[i]}"'
                    content = self._render_inline_content(cell.content)
                    self._output.append(f'<td{align}>{content}</td>')
                self._output.append('</tr>\n')
            self._output.append('</tbody>\n')

        self._output.append('</table>\n')

    def visit_table_row(self, node: TableRow) -> None:
        """Render a TableRow node.

        Parameters
        ----------
        node : TableRow
            Table row to render

        """
        pass  # Handled by visit_table

    def visit_table_cell(self, node: TableCell) -> None:
        """Render a TableCell node.

        Parameters
        ----------
        node : TableCell
            Table cell to render

        """
        pass  # Handled by visit_table

    def visit_thematic_break(self, node: ThematicBreak) -> None:
        """Render a ThematicBreak node.

        Parameters
        ----------
        node : ThematicBreak
            Thematic break to render

        """
        self._output.append('<hr>\n')

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Render an HTMLBlock node.

        Parameters
        ----------
        node : HTMLBlock
            HTML block to render

        """
        self._output.append(node.content)
        self._output.append('\n')

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        self._output.append(escape_html(node.content, enabled=self.options.escape_html))

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis node.

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f'<em>{content}</em>')

    def visit_strong(self, node: Strong) -> None:
        """Render a Strong node.

        Parameters
        ----------
        node : Strong
            Strong to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f'<strong>{content}</strong>')

    def visit_code(self, node: Code) -> None:
        """Render a Code node.

        Parameters
        ----------
        node : Code
            Code to render

        """
        escaped = escape_html(node.content, enabled=self.options.escape_html)
        self._output.append(f'<code>{escaped}</code>')

    def visit_link(self, node: Link) -> None:
        """Render a Link node.

        Parameters
        ----------
        node : Link
            Link to render

        """
        content = self._render_inline_content(node.content)
        title_attr = (
            f' title="{escape_html(node.title, enabled=self.options.escape_html)}"'
            if node.title else ''
        )
        href = escape_html(node.url, enabled=self.options.escape_html)
        self._output.append(f'<a href="{href}"{title_attr}>{content}</a>')

    def visit_image(self, node: Image) -> None:
        """Render an Image node.

        Parameters
        ----------
        node : Image
            Image to render

        """
        alt = escape_html(node.alt_text, enabled=self.options.escape_html)
        title_attr = (
            f' title="{escape_html(node.title, enabled=self.options.escape_html)}"'
            if node.title else ''
        )
        width_attr = f' width="{node.width}"' if node.width else ''
        height_attr = f' height="{node.height}"' if node.height else ''
        src = escape_html(node.url, enabled=self.options.escape_html)
        self._output.append(f'<img src="{src}" alt="{alt}"{title_attr}{width_attr}{height_attr}>')

    def visit_line_break(self, node: LineBreak) -> None:
        """Render a LineBreak node.

        Parameters
        ----------
        node : LineBreak
            Line break to render

        """
        if node.soft:
            self._output.append('\n')
        else:
            self._output.append('<br>\n')

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Render a Strikethrough node.

        Parameters
        ----------
        node : Strikethrough
            Strikethrough to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f'<del>{content}</del>')

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node.

        Parameters
        ----------
        node : Underline
            Underline to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f'<u>{content}</u>')

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node.

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f'<sup>{content}</sup>')

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node.

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f'<sub>{content}</sub>')

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Render an HTMLInline node.

        Parameters
        ----------
        node : HTMLInline
            Inline HTML to render

        """
        self._output.append(node.content)

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render a FootnoteReference node.

        Parameters
        ----------
        node : FootnoteReference
            Footnote reference to render

        """
        self._output.append(f'<sup id="fnref-{node.identifier}">')
        self._output.append(f'<a href="#fn-{node.identifier}">[{node.identifier}]</a>')
        self._output.append('</sup>')

    def visit_math_inline(self, node: MathInline) -> None:
        """Render a MathInline node.

        Parameters
        ----------
        node : MathInline
            Inline math to render

        """
        preferred = 'latex' if self.options.math_renderer != 'none' else 'mathml'
        content, notation = node.get_preferred_representation(preferred)
        markup = render_math_html(
            content,
            notation,
            inline=True,
            escape_enabled=self.options.escape_html,
        )
        self._output.append(markup)

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Render a FootnoteDefinition node.

        Parameters
        ----------
        node : FootnoteDefinition
            Footnote definition to render

        """
        # Collect footnotes for rendering at the end
        self._footnote_definitions.append(node)

    def visit_definition_list(self, node: DefinitionList) -> None:
        """Render a DefinitionList node.

        Parameters
        ----------
        node : DefinitionList
            Definition list to render

        """
        self._output.append('<dl>\n')

        for term, descriptions in node.items:
            term_content = self._render_inline_content(term.content)
            self._output.append(f'<dt>{term_content}</dt>\n')

            for desc in descriptions:
                self._output.append('<dd>')
                for child in desc.content:
                    child.accept(self)
                self._output.append('</dd>\n')

        self._output.append('</dl>\n')

    def visit_definition_term(self, node: DefinitionTerm) -> None:
        """Render a DefinitionTerm node.

        Parameters
        ----------
        node : DefinitionTerm
            Definition term to render

        """
        pass  # Handled by visit_definition_list

    def visit_definition_description(self, node: DefinitionDescription) -> None:
        """Render a DefinitionDescription node.

        Parameters
        ----------
        node : DefinitionDescription
            Definition description to render

        """
        pass  # Handled by visit_definition_list

    def visit_math_block(self, node: MathBlock) -> None:
        """Render a MathBlock node.

        Parameters
        ----------
        node : MathBlock
            Math block to render

        """
        preferred = 'latex' if self.options.math_renderer != 'none' else 'mathml'
        content, notation = node.get_preferred_representation(preferred)
        markup = render_math_html(
            content,
            notation,
            inline=False,
            escape_enabled=self.options.escape_html,
        )
        if not markup.endswith('\n'):
            markup += '\n'
        self._output.append(markup)
