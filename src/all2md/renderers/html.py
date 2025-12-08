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

import logging
from pathlib import Path
from typing import IO, Union

from all2md.ast import ast_to_dict
from all2md.constants import DEPS_HTML, DEPS_JINJA
from all2md.utils.decorators import requires_dependencies
from all2md.utils.text import slugify

logger = logging.getLogger(__name__)

from all2md.ast.nodes import (  # noqa: E402
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
    MathNotation,
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
from all2md.ast.visitors import NodeVisitor  # noqa: E402
from all2md.options.html import HtmlRendererOptions  # noqa: E402
from all2md.renderers.base import BaseRenderer, InlineContentMixin  # noqa: E402
from all2md.utils.html_sanitizer import sanitize_html_content, strip_html_tags  # noqa: E402
from all2md.utils.html_utils import escape_html, render_math_html  # noqa: E402


class HtmlRenderer(NodeVisitor, InlineContentMixin, BaseRenderer):
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
        """Initialize the HTML renderer with options."""
        BaseRenderer._validate_options_type(options, HtmlRendererOptions, "html")
        options = options or HtmlRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: HtmlRendererOptions = options
        self._output: list[str] = []
        self._headings: list[tuple[int, str, str]] = []  # (level, id, text)
        self._heading_id_counter: int = 0
        self._footnote_definitions: list[FootnoteDefinition] = []
        self._toc_insert_position: int | None = None  # Position to insert TOC in inject mode

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
        self._toc_insert_position = None

        # Render content (TOC position will be tracked during heading rendering)
        document.accept(self)

        # Determine whether to insert TOC into content or handle separately
        # For inject mode with toc_selector, TOC is handled separately in template application
        # For replace mode with {TOC} placeholder, TOC is replaced in template
        if (
            self.options.include_toc
            and self._headings
            and self._toc_insert_position is not None
            and self._should_insert_toc_in_content()  # type: ignore[unreachable]
        ):
            toc_html = '<nav id="table-of-contents">\n'  # type: ignore[unreachable]
            toc_html += "<h2>Table of Contents</h2>\n"
            toc_html += self._generate_toc()
            toc_html += "\n</nav>\n"
            # Insert TOC at the tracked position
            self._output.insert(self._toc_insert_position, toc_html)

        content = "".join(self._output)

        # Apply template if template_mode is set
        if self.options.template_mode is not None:
            return self._apply_template(document, content)

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
        self.write_text_output(html_text, output)

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
        title = doc.metadata.get("title", "Document") if doc.metadata else "Document"

        # Get language from metadata or options
        language = doc.metadata.get("language", self.options.language) if doc.metadata else self.options.language

        # Build HTML document
        parts = [
            "<!DOCTYPE html>",
            f'<html lang="{escape_html(language, enabled=self.options.escape_html)}">',
            "<head>",
        ]
        parts.append('<meta charset="UTF-8">')
        parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')

        # Add Content-Security-Policy meta tag if enabled
        if self.options.csp_enabled:
            csp_policy = self.options.csp_policy or (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';"
            )
            escaped_csp = escape_html(csp_policy, enabled=self.options.escape_html)
            parts.append(f'<meta http-equiv="Content-Security-Policy" content="{escaped_csp}">')

        parts.append(f"<title>{escape_html(str(title), enabled=self.options.escape_html)}</title>")

        # Add CSS
        if self.options.css_style == "embedded":
            parts.append("<style>")
            parts.append(self._generate_default_css())
            parts.append("</style>")
        elif self.options.css_style == "external" and self.options.css_file:
            parts.append(f'<link rel="stylesheet" href="{self.options.css_file}">')

        # Add math renderer scripts (with security check)
        if self.options.math_renderer != "none":
            if not self.options.allow_remote_scripts:
                logger.warning(
                    f"Math renderer '{self.options.math_renderer}' requires remote CDN scripts, "
                    f"but allow_remote_scripts=False. Math rendering may not work. "
                    f"Set allow_remote_scripts=True to enable CDN script loading."
                )
            else:
                # Load remote scripts only if explicitly allowed
                if self.options.math_renderer == "mathjax":
                    parts.append('<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>')
                elif self.options.math_renderer == "katex":
                    parts.append(
                        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">'
                    )
                    parts.append('<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>')
                    parts.append(
                        '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>'
                    )

        parts.append("</head>")
        parts.append("<body>")

        # Add TOC if requested
        if self.options.include_toc and self._headings:
            parts.append('<nav id="table-of-contents">')
            parts.append("<h2>Table of Contents</h2>")
            parts.append(self._generate_toc())
            parts.append("</nav>")

        parts.append("<main>")
        parts.append(content)
        parts.append("</main>")

        # Add footnotes section if any
        if self._footnote_definitions:
            parts.append('<section id="footnotes">')
            parts.append("<h2>Footnotes</h2>")
            parts.append("<ol>")
            for footnote in self._footnote_definitions:
                parts.append(f'<li id="fn-{footnote.identifier}">')
                for child in footnote.content:
                    saved_output = self._output
                    self._output = []
                    child.accept(self)
                    parts.append("".join(self._output))
                    self._output = saved_output
                parts.append(f' <a href="#fnref-{footnote.identifier}">↩</a></li>')
            parts.append("</ol>")
            parts.append("</section>")

        parts.append("</body>")
        parts.append("</html>")

        return "\n".join(parts)

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

    def _should_insert_toc_in_content(self) -> bool:
        """Determine if TOC should be inserted in content.

        Returns
        -------
        bool
            True if TOC should be inserted in content, False otherwise

        """
        if self.options.template_mode == "inject" and not self.options.toc_selector:
            # Inject mode without separate toc_selector: insert in content
            return True
        if self.options.template_mode == "replace" and self.options.template_file:
            # Replace mode: check if template has {TOC} placeholder
            template_path = Path(self.options.template_file)
            template_content = template_path.read_text(encoding="utf-8")
            # If no {TOC} placeholder, insert in content (fallback behavior)
            return "{TOC}" not in template_content
        return False

    def _generate_toc(self) -> str:
        """Generate table of contents HTML from collected headings.

        Returns
        -------
        str
            TOC HTML

        """
        if not self._headings:
            return ""

        parts = ["<ul>"]
        for level, heading_id, text in self._headings:
            indent = "  " * (level - 1)
            parts.append(
                f'{indent}<li><a href="#{heading_id}">{escape_html(text, enabled=self.options.escape_html)}</a></li>'
            )
        parts.append("</ul>")

        return "\n".join(parts)

    def _apply_template(self, document: Document, content: str) -> str:
        """Apply template based on template_mode.

        Parameters
        ----------
        document : Document
            Document with metadata
        content : str
            Rendered HTML content

        Returns
        -------
        str
            Final HTML with template applied

        Raises
        ------
        ValueError
            If template_file is not specified or template_mode is invalid
        FileNotFoundError
            If template_file does not exist

        """
        if not self.options.template_file:
            raise ValueError("template_file must be specified when template_mode is set")

        # Validate template file exists
        template_path = Path(self.options.template_file)
        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {self.options.template_file}")

        if self.options.template_mode == "replace":
            return self._apply_replace_template(document, content)
        elif self.options.template_mode == "inject":
            return self._apply_inject_template(document, content)
        elif self.options.template_mode == "jinja":
            return self._apply_jinja_template(document, content)
        else:
            raise ValueError(f"Invalid template_mode: {self.options.template_mode}")

    def _apply_replace_template(self, document: Document, content: str) -> str:
        """Apply replace template mode - replace placeholders in template.

        Parameters
        ----------
        document : Document
            Document with metadata
        content : str
            Rendered HTML content

        Returns
        -------
        str
            HTML with placeholders replaced

        """
        # Read template file (already validated in _apply_template)
        assert self.options.template_file is not None  # for type checker
        template_path = Path(self.options.template_file)
        template = template_path.read_text(encoding="utf-8")

        # Build TOC HTML if needed
        toc_html = ""
        if self.options.include_toc and self._headings:
            toc_html = '<nav id="table-of-contents">\n'
            toc_html += "<h2>Table of Contents</h2>\n"
            toc_html += self._generate_toc()
            toc_html += "\n</nav>\n"

        # Build replacement map
        replacements = {
            self.options.content_placeholder: content,
            "{TITLE}": escape_html(str(document.metadata.get("title", "Document")), enabled=self.options.escape_html),
            "{AUTHOR}": escape_html(str(document.metadata.get("author", "")), enabled=self.options.escape_html),
            "{DATE}": escape_html(str(document.metadata.get("date", "")), enabled=self.options.escape_html),
            "{DESCRIPTION}": escape_html(
                str(document.metadata.get("description", "")), enabled=self.options.escape_html
            ),
            "{TOC}": toc_html,
        }

        # Replace all placeholders
        result = template
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)

        return result

    @requires_dependencies("html", DEPS_HTML)
    def _apply_inject_template(self, document: Document, content: str) -> str:
        """Apply inject template mode - inject content into HTML at selector.

        Parameters
        ----------
        document : Document
            Document with metadata
        content : str
            Rendered HTML content

        Returns
        -------
        str
            HTML with content injected

        Raises
        ------
        DependencyError
            If BeautifulSoup is not available
        ValueError
            If selector not found in template

        """
        from bs4 import BeautifulSoup

        # Read template file (already validated in _apply_template)
        assert self.options.template_file is not None  # for type checker
        template_path = Path(self.options.template_file)
        template_html = template_path.read_text(encoding="utf-8")

        # Parse with BeautifulSoup
        soup = BeautifulSoup(template_html, "html.parser")

        # Find target element for content
        target = soup.select_one(self.options.template_selector)
        if not target:
            raise ValueError(
                f"Selector '{self.options.template_selector}' not found in template {self.options.template_file}"
            )

        # Create content soup
        content_soup = BeautifulSoup(content, "html.parser")

        # Inject content based on injection_mode
        if self.options.injection_mode == "replace":
            target.clear()
            for child in content_soup.children:
                target.append(child)
        elif self.options.injection_mode == "append":
            for child in content_soup.children:
                target.append(child)
        elif self.options.injection_mode == "prepend":
            for child in reversed(list(content_soup.children)):
                target.insert(0, child)

        # Handle separate TOC injection if toc_selector is specified
        if self.options.toc_selector and self.options.include_toc and self._headings:
            toc_target = soup.select_one(self.options.toc_selector)
            if not toc_target:
                logger.warning(
                    f"TOC selector '{self.options.toc_selector}' not found in template {self.options.template_file}. "
                    "TOC will not be included."
                )
            else:
                # Generate TOC HTML
                toc_html = '<nav id="table-of-contents">\n'
                toc_html += "<h2>Table of Contents</h2>\n"
                toc_html += self._generate_toc()
                toc_html += "\n</nav>\n"

                # Inject TOC at toc_selector (always use replace mode for TOC)
                toc_soup = BeautifulSoup(toc_html, "html.parser")
                toc_target.clear()
                for child in toc_soup.children:
                    toc_target.append(child)

        return str(soup)

    @requires_dependencies("html", DEPS_JINJA)
    def _apply_jinja_template(self, document: Document, content: str) -> str:
        """Apply jinja template mode - render with Jinja2 template engine.

        Parameters
        ----------
        document : Document
            Document with metadata
        content : str
            Rendered HTML content

        Returns
        -------
        str
            HTML rendered through Jinja2 template

        Raises
        ------
        DependencyError
            If Jinja2 is not available

        """
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        # Set up Jinja environment (already validated in _apply_template)
        assert self.options.template_file is not None  # for type checker
        template_path = Path(self.options.template_file)
        template_dir = template_path.parent
        template_name = template_path.name

        # Enable autoescape for security
        # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
        env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=select_autoescape(["html", "xml"]))
        template = env.get_template(template_name)

        # Build context
        # Mark HTML content as safe (already rendered by us)
        try:
            from markupsafe import Markup  # Jinja2 3.x
        except ImportError:
            from jinja2 import Markup  # type: ignore[attr-defined,no-redef]  # Jinja2 2.x fallback

        context = {
            "content": Markup(content),  # Already rendered HTML from our renderer
            "title": document.metadata.get("title", "Document"),
            "metadata": document.metadata,
            "headings": [{"level": level, "id": hid, "text": text} for level, hid, text in self._headings],
            "toc_html": Markup(self._generate_toc()) if self._headings else "",  # Also safe HTML
            "footnotes": [{"identifier": fn.identifier} for fn in self._footnote_definitions],
            "ast_dict": ast_to_dict(document),
        }

        # Render template
        # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
        return template.render(**context)

    def _get_custom_css_class(self, node_type: str) -> str:
        """Get custom CSS class(es) for a node type from css_class_map.

        Parameters
        ----------
        node_type : str
            Name of the node type (e.g., 'Heading', 'CodeBlock')

        Returns
        -------
        str
            Class attribute string (e.g., ' class="custom-class"') or empty string

        """
        if not self.options.css_class_map:
            return ""

        classes = self.options.css_class_map.get(node_type)
        if not classes:
            return ""

        # Handle both string and list of strings
        if isinstance(classes, str):
            class_str = classes
        else:
            class_str = " ".join(classes)

        return f' class="{class_str}"' if class_str else ""

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

        # Store for TOC (extract plain text to avoid HTML tags in TOC entries)
        plain_text_content = strip_html_tags(content)

        # Generate semantic heading ID from content with counter for uniqueness
        slug = slugify(plain_text_content, max_length=50)
        self._heading_id_counter += 1
        heading_id = f"{slug}-{self._heading_id_counter}"

        self._headings.append((level, heading_id, plain_text_content))

        # Add custom CSS class if configured
        css_class = self._get_custom_css_class("Heading")
        self._output.append(f'<h{level} id="{heading_id}"{css_class}>{content}</h{level}>\n')

        # Track position for TOC insertion in inject and replace modes (after first h1)
        # (jinja mode handles TOC through template variables)
        if (
            self.options.template_mode in ("inject", "replace")
            and self.options.include_toc
            and self._toc_insert_position is None
            and level == 1
        ):
            # Mark position after this heading for TOC insertion
            self._toc_insert_position = len(self._output)

    def visit_paragraph(self, node: Paragraph) -> None:
        """Render a Paragraph node.

        Parameters
        ----------
        node : Paragraph
            Paragraph to render

        """
        content = self._render_inline_content(node.content)
        css_class = self._get_custom_css_class("Paragraph")
        self._output.append(f"<p{css_class}>{content}</p>\n")

    def visit_code_block(self, node: CodeBlock) -> None:
        """Render a CodeBlock node.

        Parameters
        ----------
        node : CodeBlock
            Code block to render

        """
        # Build class attribute
        classes = []
        if self.options.syntax_highlighting and node.language:
            classes.append(f"language-{node.language}")

        # Add custom CSS class if configured
        custom_class = self.options.css_class_map.get("CodeBlock") if self.options.css_class_map else None
        if custom_class:
            if isinstance(custom_class, str):
                classes.append(custom_class)
            else:
                classes.extend(custom_class)

        class_attr = f' class="{" ".join(classes)}"' if classes else ""

        escaped_content = escape_html(node.content, enabled=self.options.escape_html)
        pre_class = self._get_custom_css_class("CodeBlock_pre")
        self._output.append(f"<pre{pre_class}><code{class_attr}>{escaped_content}</code></pre>\n")

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render a BlockQuote node.

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        css_class = self._get_custom_css_class("BlockQuote")
        self._output.append(f"<blockquote{css_class}>\n")

        for child in node.children:
            child.accept(self)

        self._output.append("</blockquote>\n")

    def visit_list(self, node: List) -> None:
        """Render a List node.

        Parameters
        ----------
        node : List
            List to render

        """
        tag = "ol" if node.ordered else "ul"
        start_attr = f' start="{node.start}"' if node.ordered and node.start != 1 else ""
        css_class = self._get_custom_css_class("List")

        self._output.append(f"<{tag}{start_attr}{css_class}>\n")

        for item in node.items:
            item.accept(self)

        self._output.append(f"</{tag}>\n")

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        css_class = self._get_custom_css_class("ListItem")
        self._output.append(f"<li{css_class}>")

        # Handle task lists - insert checkbox into first paragraph
        if node.task_status:
            checkbox = "&#9745; " if node.task_status == "checked" else "&#9744; "

            # If first child is a Paragraph, insert checkbox at the beginning
            if node.children and isinstance(node.children[0], Paragraph):
                first_para = node.children[0]
                para_css_class = self._get_custom_css_class("Paragraph")
                self._output.append(f"<p{para_css_class}>{checkbox}")

                # Render paragraph content
                for content_node in first_para.content:
                    content_node.accept(self)

                self._output.append("</p>\n")

                # Render remaining children
                for child in node.children[1:]:
                    child.accept(self)
            else:
                # Fallback: just prepend checkbox
                self._output.append(checkbox)
                for child in node.children:
                    child.accept(self)
        else:
            # Non-task list item
            for child in node.children:
                child.accept(self)

        self._output.append("</li>\n")

    def visit_table(self, node: Table) -> None:
        """Render a Table node.

        Parameters
        ----------
        node : Table
            Table to render

        """
        css_class = self._get_custom_css_class("Table")
        self._output.append(f"<table{css_class}>\n")

        # Render caption if present
        if node.caption:
            caption = escape_html(node.caption, enabled=self.options.escape_html)
            self._output.append(f"<caption>{caption}</caption>\n")

        # Render header
        if node.header:
            self._output.append("<thead>\n<tr>")
            for i, cell in enumerate(node.header.cells):
                align = ""
                if node.alignments and i < len(node.alignments) and node.alignments[i]:
                    align = f' style="text-align: {node.alignments[i]}"'

                # Add colspan/rowspan attributes if needed
                span_attrs = ""
                if cell.colspan > 1:
                    span_attrs += f' colspan="{cell.colspan}"'
                if cell.rowspan > 1:
                    span_attrs += f' rowspan="{cell.rowspan}"'

                content = self._render_inline_content(cell.content)
                self._output.append(f"<th{align}{span_attrs}>{content}</th>")
            self._output.append("</tr>\n</thead>\n")

        # Render body
        if node.rows:
            self._output.append("<tbody>\n")
            for row in node.rows:
                self._output.append("<tr>")
                for i, cell in enumerate(row.cells):
                    align = ""
                    if node.alignments and i < len(node.alignments) and node.alignments[i]:
                        align = f' style="text-align: {node.alignments[i]}"'

                    # Add colspan/rowspan attributes if needed
                    span_attrs = ""
                    if cell.colspan > 1:
                        span_attrs += f' colspan="{cell.colspan}"'
                    if cell.rowspan > 1:
                        span_attrs += f' rowspan="{cell.rowspan}"'

                    content = self._render_inline_content(cell.content)
                    self._output.append(f"<td{align}{span_attrs}>{content}</td>")
                self._output.append("</tr>\n")
            self._output.append("</tbody>\n")

        self._output.append("</table>\n")

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
        css_class = self._get_custom_css_class("ThematicBreak")
        self._output.append(f"<hr{css_class}>\n")

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
            if not sanitized.endswith("\n"):
                self._output.append("\n")

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
        self._output.append(f"<em>{content}</em>")

    def visit_strong(self, node: Strong) -> None:
        """Render a Strong node.

        Parameters
        ----------
        node : Strong
            Strong to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"<strong>{content}</strong>")

    def visit_code(self, node: Code) -> None:
        """Render a Code node.

        Parameters
        ----------
        node : Code
            Code to render

        """
        escaped = escape_html(node.content, enabled=self.options.escape_html)
        self._output.append(f"<code>{escaped}</code>")

    def visit_link(self, node: Link) -> None:
        """Render a Link node.

        Parameters
        ----------
        node : Link
            Link to render

        """
        content = self._render_inline_content(node.content)
        title_attr = f' title="{escape_html(node.title, enabled=self.options.escape_html)}"' if node.title else ""
        css_class = self._get_custom_css_class("Link")
        href = escape_html(node.url, enabled=self.options.escape_html)
        self._output.append(f'<a href="{href}"{title_attr}{css_class}>{content}</a>')

    def visit_image(self, node: Image) -> None:
        """Render an Image node.

        Parameters
        ----------
        node : Image
            Image to render

        """
        alt = escape_html(node.alt_text, enabled=self.options.escape_html)
        title_attr = f' title="{escape_html(node.title, enabled=self.options.escape_html)}"' if node.title else ""
        width_attr = f' width="{node.width}"' if node.width else ""
        height_attr = f' height="{node.height}"' if node.height else ""
        css_class = self._get_custom_css_class("Image")
        src = escape_html(node.url, enabled=self.options.escape_html)
        self._output.append(f'<img src="{src}" alt="{alt}"{title_attr}{width_attr}{height_attr}{css_class}>')

    def visit_line_break(self, node: LineBreak) -> None:
        """Render a LineBreak node.

        Parameters
        ----------
        node : LineBreak
            Line break to render

        """
        if node.soft:
            # Soft breaks render as space in HTML (whitespace is collapsed)
            self._output.append(" ")
        else:
            self._output.append("<br>\n")

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Render a Strikethrough node.

        Parameters
        ----------
        node : Strikethrough
            Strikethrough to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"<del>{content}</del>")

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node.

        Parameters
        ----------
        node : Underline
            Underline to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"<u>{content}</u>")

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node.

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"<sup>{content}</sup>")

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node.

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        content = self._render_inline_content(node.content)
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
        """Render a CommentInline node (inline).

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

        """
        # Check renderer's comment_mode option
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            # Skip rendering comment entirely
            return

        # Build comment text with metadata if available
        comment_text = node.content

        # Add metadata information if available
        author = node.metadata.get("author")
        date = node.metadata.get("date", "")
        label = node.metadata.get("label", "")
        comment_type = node.metadata.get("comment_type", "")

        if comment_mode == "native":
            # Render as HTML comment
            if author:
                # Build metadata prefix
                prefix_parts = []
                if comment_type:
                    prefix_parts.append(comment_type.upper())
                if label:
                    prefix_parts.append(f"#{label}")

                prefix = " ".join(prefix_parts) if prefix_parts else "Comment"

                # Build full comment text
                if date:
                    comment_text = f"{prefix} by {author} ({date}): {comment_text}"
                else:
                    comment_text = f"{prefix} by {author}: {comment_text}"

            # Escape any -- sequences in comment to avoid breaking HTML comment syntax
            safe_text = comment_text.replace("--", "- -")
            self._output.append(f"<!-- {safe_text} -->")

        elif comment_mode == "visible":
            # Render as visible <span> element with data attributes (inline)
            self._output.append('<span class="comment"')
            if author:
                self._output.append(f' data-author="{escape_html(author)}"')
            if date:
                self._output.append(f' data-date="{escape_html(date)}"')
            if label:
                self._output.append(f' data-label="{escape_html(label)}"')
            if comment_type:
                self._output.append(f' data-type="{escape_html(comment_type)}"')
            self._output.append(f">{escape_html(comment_text)}</span>")

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render a FootnoteReference node.

        Parameters
        ----------
        node : FootnoteReference
            Footnote reference to render

        """
        self._output.append(f'<sup id="fnref-{node.identifier}">')
        self._output.append(f'<a href="#fn-{node.identifier}">[{node.identifier}]</a>')
        self._output.append("</sup>")

    def visit_math_inline(self, node: MathInline) -> None:
        """Render a MathInline node.

        Parameters
        ----------
        node : MathInline
            Inline math to render

        """
        preferred: MathNotation = "latex" if self.options.math_renderer != "none" else "mathml"
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
        css_class = self._get_custom_css_class("DefinitionList")
        self._output.append(f"<dl{css_class}>\n")

        for term, descriptions in node.items:
            term_content = self._render_inline_content(term.content)
            dt_class = self._get_custom_css_class("DefinitionTerm")
            self._output.append(f"<dt{dt_class}>{term_content}</dt>\n")

            for desc in descriptions:
                dd_class = self._get_custom_css_class("DefinitionDescription")
                self._output.append(f"<dd{dd_class}>")
                for child in desc.content:
                    child.accept(self)
                self._output.append("</dd>\n")

        self._output.append("</dl>\n")

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
        preferred: MathNotation = "latex" if self.options.math_renderer != "none" else "mathml"
        content, notation = node.get_preferred_representation(preferred)
        markup = render_math_html(
            content,
            notation,
            inline=False,
            escape_enabled=self.options.escape_html,
        )
        if not markup.endswith("\n"):
            markup += "\n"
        self._output.append(markup)

    def visit_comment(self, node: Comment) -> None:
        """Render a Comment node (block-level).

        Parameters
        ----------
        node : Comment
            Comment block to render

        """
        # Check renderer's comment_mode option
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            # Skip rendering comment entirely
            return

        # Build comment text with metadata if available
        comment_text = node.content

        # Add metadata information if available
        author = node.metadata.get("author")
        date = node.metadata.get("date", "")
        label = node.metadata.get("label", "")
        comment_type = node.metadata.get("comment_type", "")

        if comment_mode == "native":
            # Render as HTML comment
            if author:
                # Build metadata prefix
                prefix_parts = []
                if comment_type:
                    prefix_parts.append(comment_type.upper())
                if label:
                    prefix_parts.append(f"#{label}")

                prefix = " ".join(prefix_parts) if prefix_parts else "Comment"

                # Build full comment text
                if date:
                    comment_text = f"{prefix} by {author} ({date}): {comment_text}"
                else:
                    comment_text = f"{prefix} by {author}: {comment_text}"

            # Escape any -- sequences in comment to avoid breaking HTML comment syntax
            safe_text = comment_text.replace("--", "- -")
            self._output.append(f"<!-- {safe_text} -->\n")

        elif comment_mode == "visible":
            # Render as visible <div> element with data attributes
            self._output.append('<div class="comment"')
            if author:
                self._output.append(f' data-author="{escape_html(author)}"')
            if date:
                self._output.append(f' data-date="{escape_html(date)}"')
            if label:
                self._output.append(f' data-label="{escape_html(label)}"')
            if comment_type:
                self._output.append(f' data-type="{escape_html(comment_type)}"')
            self._output.append(f">{escape_html(comment_text)}</div>\n")
