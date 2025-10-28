#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/latex.py
"""LaTeX rendering from AST.

This module provides the LatexRenderer class which converts AST nodes
to LaTeX text. The renderer supports configurable rendering options
for controlling output format and can generate complete documents or fragments.

"""

from __future__ import annotations

from pathlib import Path
from typing import IO, Any, Dict, Union

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
from all2md.options.latex import LatexRendererOptions
from all2md.renderers.base import BaseRenderer, InlineContentMixin


class LatexRenderer(NodeVisitor, InlineContentMixin, BaseRenderer):
    r"""Render AST nodes to LaTeX text.

    This class implements the visitor pattern to traverse an AST and
    generate LaTeX output. It supports configurable rendering options
    and can generate complete documents or fragments for inclusion.

    Parameters
    ----------
    options : LatexRendererOptions or None, default = None
        LaTeX rendering options

    Examples
    --------
    Basic usage:

        >>> from all2md.ast import Document, Heading, Text
        >>> from all2md.renderers.latex import LatexRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> renderer = LatexRenderer()
        >>> latex = renderer.render_to_string(doc)
        >>> print(latex)
        \documentclass{article}
        ...
        \section{Title}
        ...

    """

    # LaTeX special characters that need escaping
    SPECIAL_CHARS = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
        "%": r"\%",
        "&": r"\&",
        "#": r"\#",
        "_": r"\_",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }

    def __init__(self, options: LatexRendererOptions | None = None):
        """Initialize the LaTeX renderer with options."""
        BaseRenderer._validate_options_type(options, LatexRendererOptions, "latex")
        options = options or LatexRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: LatexRendererOptions = options
        self._output: list[str] = []
        self._in_table: bool = False

    def render_to_string(self, document: Document) -> str:
        """Render a document AST to LaTeX string.

        Parameters
        ----------
        document : Document
            The document node to render

        Returns
        -------
        str
            LaTeX text

        """
        self._output = []
        self._in_table = False

        metadata_block = self._prepare_metadata(document.metadata)

        # Generate preamble if requested
        if self.options.include_preamble:
            self._render_preamble(metadata_block)

        # Render document body
        if self.options.include_preamble:
            self._output.append("\\begin{document}\n\n")

            # Render title if present in metadata
            if metadata_block.get("title"):
                self._output.append("\\maketitle\n\n")

        for i, child in enumerate(document.children):
            child.accept(self)
            # Add spacing between blocks
            if i < len(document.children) - 1:
                self._output.append("\n\n")

        if self.options.include_preamble:
            self._output.append("\n\n\\end{document}\n")

        return "".join(self._output)

    def _render_preamble(self, metadata: Dict[str, Any]) -> None:
        """Render LaTeX document preamble.

        Parameters
        ----------
        metadata : dict[str, Any]
            Document metadata dictionary

        """
        self._output.append(f"\\documentclass{{{self.options.document_class}}}\n\n")

        # Add packages
        for package in self.options.packages:
            self._output.append(f"\\usepackage{{{package}}}\n")

        self._output.append("\n")

        # Add metadata commands
        if metadata.get("title"):
            self._output.append(f"\\title{{{self._escape(metadata['title'])}}}\n")
        if metadata.get("author"):
            self._output.append(f"\\author{{{self._escape(metadata['author'])}}}\n")

        date_value = metadata.get("creation_date") or metadata.get("date")
        if date_value:
            self._output.append(f"\\date{{{self._escape(str(date_value))}}}\n")
        else:
            self._output.append("\\date{\\today}\n")

        self._output.append("\n")

    def _escape(self, text: str) -> str:
        """Escape special LaTeX characters.

        Parameters
        ----------
        text : str
            Text to escape

        Returns
        -------
        str
            Escaped text

        """
        if not self.options.escape_special:
            return text

        # Replace special characters
        result = text
        for char, replacement in self.SPECIAL_CHARS.items():
            result = result.replace(char, replacement)

        return result

    def visit_document(self, node: Document) -> None:
        """Render a Document node.

        This method is not called directly as rendering is handled
        by render_to_string.

        Parameters
        ----------
        node : Document
            Document to render

        """
        pass

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node.

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        # Map heading levels to LaTeX commands
        commands = {
            1: "section",
            2: "subsection",
            3: "subsubsection",
            4: "paragraph",
            5: "subparagraph",
            6: "subparagraph",  # LaTeX doesn't have level 6
        }

        command = commands.get(node.level, "section")
        content = self._render_inline_content(node.content)
        self._output.append(f"\\{command}{{{content}}}")

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
        # Use verbatim environment for code blocks
        self._output.append("\\begin{verbatim}\n")
        self._output.append(node.content)
        if not node.content.endswith("\n"):
            self._output.append("\n")
        self._output.append("\\end{verbatim}")

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render a BlockQuote node.

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        self._output.append("\\begin{quote}\n")

        for i, child in enumerate(node.children):
            child.accept(self)
            if i < len(node.children) - 1:
                self._output.append("\n\n")

        self._output.append("\n\\end{quote}")

    def visit_list(self, node: List) -> None:
        """Render a List node.

        Parameters
        ----------
        node : List
            List to render

        """
        env_name = "enumerate" if node.ordered else "itemize"

        self._output.append(f"\\begin{{{env_name}}}\n")

        for item in node.items:
            self._output.append("\\item ")
            item.accept(self)
            self._output.append("\n")

        self._output.append(f"\\end{{{env_name}}}")

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        # Render children (first is typically a paragraph)
        for i, child in enumerate(node.children):
            if i == 0 and isinstance(child, Paragraph):
                # For first paragraph, render inline content directly
                content = self._render_inline_content(child.content)
                self._output.append(content)
            else:
                # Subsequent children get new paragraphs
                self._output.append("\n\n")
                child.accept(self)

    def visit_table(self, node: Table) -> None:
        """Render a Table node.

        Parameters
        ----------
        node : Table
            Table to render

        """
        self._in_table = True

        # Collect all rows
        all_rows = []
        if node.header:
            all_rows.append(node.header)
        all_rows.extend(node.rows)

        if not all_rows:
            self._in_table = False
            return

        # Compute grid dimensions accounting for colspan/rowspan
        num_rows = len(all_rows)
        num_cols = self._compute_table_columns(all_rows)

        # Generate column specification (all left-aligned for simplicity)
        col_spec = "|" + "l|" * num_cols

        self._output.append(f"\\begin{{tabular}}{{{col_spec}}}\n")
        self._output.append("\\hline\n")

        # Track which grid cells are occupied by spanning cells
        occupied = [[False] * num_cols for _ in range(num_rows)]

        # Render all rows
        for row_idx, ast_row in enumerate(all_rows):
            col_idx = 0
            first_cell = True

            for ast_cell in ast_row.cells:
                # Skip occupied cells
                while col_idx < num_cols and occupied[row_idx][col_idx]:
                    col_idx += 1

                if col_idx >= num_cols:
                    break

                if not first_cell:
                    self._output.append(" & ")
                first_cell = False

                # Render cell content
                content = self._render_inline_content(ast_cell.content)

                # Handle cell spanning
                colspan = ast_cell.colspan
                rowspan = ast_cell.rowspan

                # Mark occupied cells
                for r in range(row_idx, min(row_idx + rowspan, num_rows)):
                    for c in range(col_idx, min(col_idx + colspan, num_cols)):
                        occupied[r][c] = True

                # Emit cell with appropriate span commands
                if colspan > 1 and rowspan > 1:
                    # Both colspan and rowspan - use multirow inside multicolumn
                    self._output.append(
                        f"\\multicolumn{{{colspan}}}{{|l|}}{{\\multirow{{{rowspan}}}{{*}}{{{content}}}}}"
                    )
                elif colspan > 1:
                    # Just colspan
                    self._output.append(f"\\multicolumn{{{colspan}}}{{|l|}}{{{content}}}")
                elif rowspan > 1:
                    # Just rowspan
                    self._output.append(f"\\multirow{{{rowspan}}}{{*}}{{{content}}}")
                else:
                    # No spanning
                    self._output.append(content)

                col_idx += colspan

            # End row
            self._output.append(" \\\\\n")

            # Add \hline after header or last row
            if row_idx == 0 and node.header:
                self._output.append("\\hline\n")
            elif row_idx == len(all_rows) - 1:
                self._output.append("\\hline\n")

        self._output.append("\\end{tabular}")

        self._in_table = False

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
        self._output.append("\\hrulefill")

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Render an HTMLBlock node.

        Parameters
        ----------
        node : HTMLBlock
            HTML block to render

        """
        # LaTeX doesn't directly support HTML
        # Wrap in comment
        self._output.append(f"% HTML block: {node.content[:50]}...")

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        escaped = self._escape(node.content)
        self._output.append(escaped)

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis node.

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"\\emph{{{content}}}")

    def visit_strong(self, node: Strong) -> None:
        """Render a Strong node.

        Parameters
        ----------
        node : Strong
            Strong to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"\\textbf{{{content}}}")

    def visit_code(self, node: Code) -> None:
        """Render a Code node.

        Parameters
        ----------
        node : Code
            Code to render

        """
        # Use texttt for inline code
        escaped = self._escape(node.content)
        self._output.append(f"\\texttt{{{escaped}}}")

    def visit_link(self, node: Link) -> None:
        """Render a Link node.

        Parameters
        ----------
        node : Link
            Link to render

        """
        content = self._render_inline_content(node.content)
        url = node.url

        # Use href command (requires hyperref package)
        self._output.append(f"\\href{{{url}}}{{{content}}}")

    def visit_image(self, node: Image) -> None:
        """Render an Image node.

        Parameters
        ----------
        node : Image
            Image to render

        """
        # Use includegraphics (requires graphicx package)
        options = []
        if node.width:
            options.append(f"width={node.width}pt")
        if node.height:
            options.append(f"height={node.height}pt")

        opt_str = ",".join(options)
        if opt_str:
            self._output.append(f"\\includegraphics[{opt_str}]{{{node.url}}}")
        else:
            self._output.append(f"\\includegraphics{{{node.url}}}")

    def visit_line_break(self, node: LineBreak) -> None:
        """Render a LineBreak node.

        Parameters
        ----------
        node : LineBreak
            Line break to render

        """
        if node.soft:
            # Soft breaks render as space in LaTeX
            self._output.append(" ")
        else:
            self._output.append("\\\\")

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node.

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"\\textsuperscript{{{content}}}")

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node.

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"\\textsubscript{{{content}}}")

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node.

        Parameters
        ----------
        node : Underline
            Underline to render

        """
        content = self._render_inline_content(node.content)
        self._output.append(f"\\underline{{{content}}}")

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Render a Strikethrough node.

        Parameters
        ----------
        node : Strikethrough
            Strikethrough to render

        """
        # Requires soul or ulem package
        content = self._render_inline_content(node.content)
        self._output.append(f"\\sout{{{content}}}")

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Render an HTMLInline node.

        Parameters
        ----------
        node : HTMLInline
            Inline HTML to render

        """
        # LaTeX doesn't support HTML - comment it out
        self._output.append(f"% HTML: {node.content}")

    def visit_comment(self, node: Comment) -> None:
        """Render a Comment node (block-level).

        Parameters
        ----------
        node : Comment
            Comment block to render

        """
        # Check comment_mode option
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            # Skip rendering comment entirely
            return

        # Extract metadata
        author = node.metadata.get("author", "")
        date = node.metadata.get("date", "")
        label = node.metadata.get("label", "")
        comment_type = node.metadata.get("comment_type", "")

        # Build attribution prefix
        prefix_parts = []
        if comment_type:
            prefix_parts.append(comment_type.upper())
        if label:
            prefix_parts.append(f"#{label}")
        prefix = " ".join(prefix_parts) if prefix_parts else "Comment"

        if comment_mode == "todonotes":
            # Render using \todo{} from todonotes package
            # Format: \todo[author=Name]{Comment text}
            todo_text = node.content.replace("}", "\\}")  # Escape closing braces

            if author:
                # Add author as option
                escaped_author = author.replace("]", "\\]")  # Escape closing brackets
                if date:
                    self._output.append(f"\\todo[author={escaped_author}]{{{prefix} ({date}): {todo_text}}}")
                else:
                    self._output.append(f"\\todo[author={escaped_author}]{{{prefix}: {todo_text}}}")
            else:
                self._output.append(f"\\todo{{{todo_text}}}")

        elif comment_mode == "marginnote":
            # Render using \marginpar{} for margin notes
            margin_text = node.content.replace("}", "\\}")  # Escape closing braces

            # Build full text with attribution
            if author:
                if date:
                    full_text = f"\\textbf{{{prefix} by {author} ({date}):}} {margin_text}"
                else:
                    full_text = f"\\textbf{{{prefix} by {author}:}} {margin_text}"
            else:
                full_text = margin_text

            self._output.append(f"\\marginpar{{{full_text}}}")

        else:  # "percent" mode
            # Build comment text with metadata if available
            comment_lines = []

            # Add metadata header if present
            if author or date:
                header_parts = [prefix]
                header_parts.append(f"by {author}" if author else "")
                if date:
                    header_parts.append(f"({date})")

                comment_lines.append("% " + " ".join(p for p in header_parts if p))

            # Add content - split multiline content and prefix each line
            content_lines = node.content.split("\n")
            for line in content_lines:
                comment_lines.append(f"% {line}")

            self._output.append("\n".join(comment_lines))

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Render a CommentInline node (inline).

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

        """
        # Check comment_mode option
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            # Skip rendering comment entirely
            return

        # Extract metadata
        author = node.metadata.get("author", "")
        date = node.metadata.get("date", "")
        label = node.metadata.get("label", "")
        comment_type = node.metadata.get("comment_type", "")

        # Build attribution prefix
        prefix_parts = []
        if comment_type:
            prefix_parts.append(comment_type.upper())
        if label:
            prefix_parts.append(f"#{label}")
        prefix = " ".join(prefix_parts) if prefix_parts else "Comment"

        if comment_mode == "todonotes":
            # Render using \todo{} inline
            todo_text = node.content.replace("}", "\\}")

            if author:
                escaped_author = author.replace("]", "\\]")
                if date:
                    self._output.append(f"\\todo[inline,author={escaped_author}]{{{prefix} ({date}): {todo_text}}}")
                else:
                    self._output.append(f"\\todo[inline,author={escaped_author}]{{{prefix}: {todo_text}}}")
            else:
                self._output.append(f"\\todo[inline]{{{todo_text}}}")

        elif comment_mode == "marginnote":
            # Render using \marginpar{} for inline margin notes
            margin_text = node.content.replace("}", "\\}")

            if author:
                if date:
                    full_text = f"\\textbf{{{prefix} by {author} ({date}):}} {margin_text}"
                else:
                    full_text = f"\\textbf{{{prefix} by {author}:}} {margin_text}"
            else:
                full_text = margin_text

            self._output.append(f"\\marginpar{{{full_text}}}")

        else:  # "percent" mode
            # Build comment text with metadata if available
            comment_text = node.content

            if author:
                prefix_text_parts = [prefix]
                prefix_text_parts.append(f"by {author}")
                if date:
                    prefix_text_parts.append(f"({date})")

                comment_text = " ".join(prefix_text_parts) + f": {comment_text}"

            # Render as inline LaTeX comment
            self._output.append(f"% {comment_text}")

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render a FootnoteReference node.

        Parameters
        ----------
        node : FootnoteReference
            Footnote reference to render

        """
        # Use footnote command
        self._output.append(f"\\footnotemark[{node.identifier}]")

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Render a FootnoteDefinition node.

        Parameters
        ----------
        node : FootnoteDefinition
            Footnote definition to render

        """
        # Render as footnotetext
        content_nodes = []
        for child in node.content:
            if isinstance(child, Paragraph):
                content_nodes.extend(child.content)
            else:
                # Convert block to text
                content_nodes.append(Text(content=str(child)))

        content = self._render_inline_content(content_nodes)
        self._output.append(f"\\footnotetext[{node.identifier}]{{{content}}}")

    def visit_math_inline(self, node: MathInline) -> None:
        """Render a MathInline node.

        Parameters
        ----------
        node : MathInline
            Inline math to render

        """
        # Get LaTeX representation
        content, notation = node.get_preferred_representation("latex")

        # Render as inline math
        self._output.append(f"${content}$")

    def visit_math_block(self, node: MathBlock) -> None:
        """Render a MathBlock node.

        Parameters
        ----------
        node : MathBlock
            Math block to render

        """
        # Get LaTeX representation
        content, notation = node.get_preferred_representation("latex")

        # Render as display math using equation environment
        self._output.append("\\begin{equation}\n")
        self._output.append(content)
        if not content.endswith("\n"):
            self._output.append("\n")
        self._output.append("\\end{equation}")

    def visit_definition_list(self, node: DefinitionList) -> None:
        """Render a DefinitionList node.

        Parameters
        ----------
        node : DefinitionList
            Definition list to render

        """
        # Use description environment
        self._output.append("\\begin{description}\n")

        for term, descriptions in node.items:
            term_content = self._render_inline_content(term.content)
            self._output.append(f"\\item[{term_content}] ")

            for i, desc in enumerate(descriptions):
                for child in desc.content:
                    child.accept(self)
                    if i < len(descriptions) - 1:
                        self._output.append("\n")

            self._output.append("\n")

        self._output.append("\\end{description}")

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

    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render AST to LaTeX and write to output.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        """
        latex_text = self.render_to_string(doc)
        self.write_text_output(latex_text, output)
