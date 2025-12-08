"""RTF rendering from AST using the pyth3 toolkit."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import IO, Any, Iterable, Union, cast

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
from all2md.constants import DEPS_RTF_RENDER
from all2md.exceptions import RenderingError
from all2md.options.rtf import RtfRendererOptions
from all2md.renderers.base import BaseRenderer
from all2md.utils.decorators import requires_dependencies

logger = logging.getLogger(__name__)


class RtfRenderer(NodeVisitor, BaseRenderer):
    """Render AST nodes into Rich Text Format documents."""

    def __init__(self, options: RtfRendererOptions | None = None) -> None:
        """Initialize the renderer with format-specific options."""
        BaseRenderer._validate_options_type(options, RtfRendererOptions, "rtf")
        options = options or RtfRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: RtfRendererOptions = options

        self._pyth_loaded: bool = False
        self._Document: Any | None = None
        self._Paragraph: Any | None = None
        self._Text: Any | None = None
        self._List: Any | None = None
        self._ListEntry: Any | None = None
        self._writer_cls: Any | None = None

    def _ensure_dependencies(self) -> None:
        """Import pyth classes lazily to honour optional dependency semantics."""
        if self._pyth_loaded:
            return

        from pyth.document import Document as PythDocument
        from pyth.document import List as PythList
        from pyth.document import ListEntry as PythListEntry
        from pyth.document import Paragraph as PythParagraph
        from pyth.document import Text as PythText
        from pyth.plugins.rtf15.writer import Rtf15Writer

        self._Document = PythDocument
        self._Paragraph = PythParagraph
        self._Text = PythText
        self._List = PythList
        self._ListEntry = PythListEntry
        self._writer_cls = Rtf15Writer
        self._pyth_loaded = True

    def _assert_dependencies_loaded(self) -> None:
        """Assert that all pyth dependencies have been loaded (for type narrowing)."""
        assert self._Document is not None
        assert self._Paragraph is not None
        assert self._Text is not None
        assert self._List is not None
        assert self._ListEntry is not None
        assert self._writer_cls is not None

    def _normalize_blocks(self, value: Any) -> list[Any]:
        """Flatten renderer results into a list of paragraph-like objects."""
        if value is None:
            return []
        if isinstance(value, list):
            result: list[Any] = []
            for item in value:
                result.extend(self._normalize_blocks(item))
            return result
        return [value]

    def _normalize_inline(self, value: Any) -> list[Any]:
        """Flatten inline renderer results into text runs."""
        if value is None:
            return []
        if isinstance(value, list):
            result: list[Any] = []
            for item in value:
                result.extend(self._normalize_inline(item))
            return result
        return [value]

    def _create_text_run(self, text: str) -> Any:
        """Create a pyth Text run with the supplied content."""
        return cast(Any, self._Text)(content=[text])

    def _render_inline(self, nodes: Iterable[Any]) -> list[Any]:
        """Render inline nodes to a list of pyth Text runs."""
        runs: list[Any] = []
        for child in nodes:
            rendered = child.accept(self)
            runs.extend(self._normalize_inline(rendered))
        return runs

    def _render_plain_text(self, nodes: Iterable[Any]) -> str:
        """Render inline nodes to plain text for fallback scenarios."""
        parts: list[str] = []
        for child in nodes:
            if isinstance(child, Text):
                parts.append(child.content)
            elif isinstance(child, (Strong, Emphasis, Underline, Strikethrough, Subscript, Superscript)):
                parts.append(self._render_plain_text(child.content))
            elif isinstance(child, Link):
                parts.append(self._render_plain_text(child.content))
            elif isinstance(child, Image):
                parts.append(child.alt_text or "Image")
            elif isinstance(child, Code):
                parts.append(child.content)
            elif isinstance(child, LineBreak):
                parts.append("\n")
            elif isinstance(child, MathInline):
                content, _ = child.get_preferred_representation("latex")
                parts.append(content)
        return "".join(parts)

    def _prefix_paragraph(self, paragraph: Any, prefix: str) -> Any:
        """Return a copy of a paragraph with prefix text prepended."""
        runs = [self._create_text_run(prefix)]
        runs.extend(paragraph.content)
        return cast(Any, self._Paragraph)(content=runs)

    def _render_table_row(self, row: TableRow, header: bool = False) -> str:
        """Render a table row to a pipe-delimited fallback string.

        Note: Rowspan is not supported in this fallback format.
        Colspan is approximated by repeating the cell content.

        """
        cell_texts: list[str] = []
        for cell in row.cells:
            cell_text = self._render_plain_text(cell.content)
            cell_text_stripped = cell_text.strip()

            # Add cell text
            cell_texts.append(cell_text_stripped)

            # Handle colspan by repeating the cell
            if cell.colspan > 1:
                for _ in range(cell.colspan - 1):
                    cell_texts.append(cell_text_stripped)

        line = " | ".join(cell_texts)
        if header:
            underline = "-+-".join("-" * len(text) if text else "-" for text in cell_texts)
            return f"{line}\n{underline}"
        return line

    @requires_dependencies("rtf_render", DEPS_RTF_RENDER)
    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render a document to an RTF stream or file."""
        self._ensure_dependencies()
        self._assert_dependencies_loaded()
        try:
            pyth_doc = doc.accept(self)
            buffer = cast(Any, self._writer_cls).write(pyth_doc, fontFamily=self.options.font_family)
            text = buffer.getvalue() if hasattr(buffer, "getvalue") else buffer
            if isinstance(text, bytes):
                text = text.decode("utf-8")
            self.write_text_output(text, output)
        except Exception as exc:  # pragma: no cover - safety net
            raise RenderingError(
                f"Failed to render RTF: {exc!r}",
                rendering_stage="rendering",
                original_error=exc,
            ) from exc

    @requires_dependencies("rtf_render", DEPS_RTF_RENDER)
    def render_to_string(self, doc: Document) -> str:
        """Render a document to an in-memory RTF string."""
        self._ensure_dependencies()
        self._assert_dependencies_loaded()
        pyth_doc = doc.accept(self)
        buffer = cast(Any, self._writer_cls).write(pyth_doc, fontFamily=self.options.font_family)
        text = buffer.getvalue() if hasattr(buffer, "getvalue") else buffer
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        return text

    def visit_document(self, node: Document) -> Any:
        """Convert the root document node to a pyth document."""
        self._ensure_dependencies()
        self._assert_dependencies_loaded()
        properties: dict[str, str] = {}
        for key in ("title", "author", "subject"):
            value = (node.metadata or {}).get(key)
            if value:
                properties[key] = value
        content: list[Any] = []
        for child in node.children:
            content.extend(self._normalize_blocks(child.accept(self)))
        return cast(Any, self._Document)(properties=properties, content=content)

    def visit_heading(self, node: Heading) -> Any:
        """Render a heading node with optional bold styling."""
        runs = self._render_inline(node.content)
        if not runs:
            return None
        if self.options.bold_headings:
            for run in runs:
                run["bold"] = True
        return cast(Any, self._Paragraph)(content=runs)

    def visit_paragraph(self, node: Paragraph) -> Any:
        """Render a paragraph node to a pyth paragraph."""
        runs = self._render_inline(node.content)
        if not runs:
            return None
        return cast(Any, self._Paragraph)(content=runs)

    def visit_code_block(self, node: CodeBlock) -> Any:
        """Render a fenced or indented code block as indented text paragraphs."""
        lines = node.content.splitlines() or [""]
        paragraphs: list[Any] = []
        for line in lines:
            run = self._create_text_run(line)
            paragraphs.append(cast(Any, self._Paragraph)(content=[run]))
        return paragraphs

    def visit_block_quote(self, node: BlockQuote) -> Any:
        """Render a block quote by prefixing contained paragraphs."""
        paragraphs: list[Any] = []
        Paragraph_cls = cast(Any, self._Paragraph)
        for child in node.children:
            for block in self._normalize_blocks(child.accept(self)):
                if isinstance(block, Paragraph_cls):
                    paragraphs.append(self._prefix_paragraph(block, "> "))
                else:
                    paragraphs.append(block)
        return paragraphs

    def visit_list(self, node: List) -> Any:
        """Render a list node to a pyth bullet list."""
        entries: list[Any] = []
        for item in node.items:
            entries.extend(self._normalize_blocks(item.accept(self)))
        normalized_entries: list[Any] = []
        ListEntry_cls = cast(Any, self._ListEntry)
        Paragraph_cls = cast(Any, self._Paragraph)
        List_cls = cast(Any, self._List)
        for entry in entries:
            if isinstance(entry, ListEntry_cls):
                normalized_entries.append(entry)
            elif isinstance(entry, Paragraph_cls):
                normalized_entries.append(ListEntry_cls(content=[entry]))
            elif isinstance(entry, List_cls):
                normalized_entries.append(ListEntry_cls(content=[entry]))
        return List_cls(content=normalized_entries)

    def visit_list_item(self, node: ListItem) -> Any:
        """Render a list item, preserving task status when present."""
        paragraphs: list[Any] = []
        for child in node.children:
            paragraphs.extend(self._normalize_blocks(child.accept(self)))
        Paragraph_cls = cast(Any, self._Paragraph)
        if node.task_status in {"checked", "unchecked"}:
            marker = "[x] " if node.task_status == "checked" else "[ ] "
            if paragraphs:
                first = paragraphs[0]
                if isinstance(first, Paragraph_cls):
                    first.content.insert(0, self._create_text_run(marker))
            else:
                paragraphs.append(Paragraph_cls(content=[self._create_text_run(marker)]))
        if not paragraphs:
            paragraphs.append(Paragraph_cls(content=[self._create_text_run("")]))
        return cast(Any, self._ListEntry)(content=paragraphs)

    def visit_table(self, node: Table) -> Any:
        """Render a table as a series of plain-text paragraphs."""
        paragraphs: list[Any] = []
        Paragraph_cls = cast(Any, self._Paragraph)
        if node.header:
            header = self._render_table_row(node.header, header=True)
            paragraphs.append(Paragraph_cls(content=[self._create_text_run(header)]))
        for row in node.rows:
            line = self._render_table_row(row)
            paragraphs.append(Paragraph_cls(content=[self._create_text_run(line)]))
        if node.caption:
            paragraphs.append(Paragraph_cls(content=[self._create_text_run(node.caption)]))
        return paragraphs

    def visit_table_row(self, node: TableRow) -> Any:
        """Render a table row to a fallback string (used internally)."""
        return self._render_table_row(node)

    def visit_table_cell(self, node: TableCell) -> Any:
        """Render a table cell to plain text."""
        return self._render_plain_text(node.content)

    def visit_definition_list(self, node: DefinitionList) -> Any:
        """Render a definition list as paragraphs with indented descriptions."""
        paragraphs: list[Any] = []
        Paragraph_cls = cast(Any, self._Paragraph)
        for term, descriptions in node.items:
            term_runs = self._render_inline(term.content)
            if term_runs:
                paragraphs.append(Paragraph_cls(content=term_runs))
            for desc in descriptions:
                for block in self._normalize_blocks(desc.accept(self)):
                    if isinstance(block, Paragraph_cls):
                        paragraphs.append(self._prefix_paragraph(block, "    "))
                    else:
                        paragraphs.append(block)
        return paragraphs

    def visit_definition_term(self, node: DefinitionTerm) -> Any:
        """Render a definition term to a paragraph."""
        runs = self._render_inline(node.content)
        return cast(Any, self._Paragraph)(content=runs) if runs else None

    def visit_definition_description(self, node: DefinitionDescription) -> Any:
        """Render a definition description's block content."""
        paragraphs: list[Any] = []
        for child in node.content:
            paragraphs.extend(self._normalize_blocks(child.accept(self)))
        return paragraphs

    def visit_thematic_break(self, node: ThematicBreak) -> Any:  # noqa: ARG002
        """Render a thematic break as an em-dash divider."""
        return cast(Any, self._Paragraph)(content=[self._create_text_run("—" * 10)])

    def visit_html_block(self, node: HTMLBlock) -> Any:
        """Render raw HTML blocks as literal text with a debug hint."""
        logger.debug("Rendering HTML block as plain text for RTF output")
        return cast(Any, self._Paragraph)(content=[self._create_text_run(node.content)])

    def visit_footnote_definition(self, node: FootnoteDefinition) -> Any:
        """Render a footnote definition with indentation."""
        Paragraph_cls = cast(Any, self._Paragraph)
        intro = Paragraph_cls(content=[self._create_text_run(f"[^{node.identifier}]:")])
        content: list[Any] = [intro]
        for child in node.content:
            for block in self._normalize_blocks(child.accept(self)):
                if isinstance(block, Paragraph_cls):
                    content.append(self._prefix_paragraph(block, "    "))
                else:
                    content.append(block)
        return content

    def visit_math_block(self, node: MathBlock) -> Any:
        """Render a display math block using its preferred representation."""
        content, _ = node.get_preferred_representation("latex")
        lines = content.splitlines() or [content]
        Paragraph_cls = cast(Any, self._Paragraph)
        paragraphs = [Paragraph_cls(content=[self._create_text_run(line)]) for line in lines]
        return paragraphs

    def visit_math_inline(self, node: MathInline) -> Any:
        """Render inline math using its preferred representation."""
        content, _ = node.get_preferred_representation("latex")
        return [self._create_text_run(content)]

    def visit_link(self, node: Link) -> Any:
        """Render a hyperlink, preserving URL metadata."""
        runs = self._render_inline(node.content)
        for run in runs:
            run["url"] = node.url
        return runs

    def visit_image(self, node: Image) -> Any:
        """Render an image as descriptive text with optional target URL."""
        alt = node.alt_text or "Image"
        description = f"[{alt}]"
        if node.url:
            description += f" ({node.url})"
        return [self._create_text_run(description)]

    def visit_text(self, node: Text) -> Any:
        """Render a plain text leaf node."""
        return [self._create_text_run(node.content)]

    def visit_emphasis(self, node: Emphasis) -> Any:
        """Render emphasized content with italic styling."""
        runs = self._render_inline(node.content)
        for run in runs:
            run["italic"] = True
        return runs

    def visit_strong(self, node: Strong) -> Any:
        """Render strong content with bold styling."""
        runs = self._render_inline(node.content)
        for run in runs:
            run["bold"] = True
        return runs

    def visit_code(self, node: Code) -> Any:
        """Render inline code as a literal text run."""
        return [self._create_text_run(node.content)]

    def visit_line_break(self, node: LineBreak) -> Any:  # noqa: ARG002
        """Render a soft or hard line break as a newline character."""
        return [self._create_text_run("\n")]

    def visit_strikethrough(self, node: Strikethrough) -> Any:
        """Render strikethrough content with the strike property."""
        runs = self._render_inline(node.content)
        for run in runs:
            run["strike"] = True
        return runs

    def visit_subscript(self, node: Subscript) -> Any:
        """Render subscript content using the subscript style."""
        runs = self._render_inline(node.content)
        for run in runs:
            run["sub"] = True
        return runs

    def visit_superscript(self, node: Superscript) -> Any:
        """Render superscript content using the superscript style."""
        runs = self._render_inline(node.content)
        for run in runs:
            run["super"] = True
        return runs

    def visit_underline(self, node: Underline) -> Any:
        """Render underlined content using the underline style."""
        runs = self._render_inline(node.content)
        for run in runs:
            run["underline"] = True
        return runs

    def visit_html_inline(self, node: HTMLInline) -> Any:
        """Render raw inline HTML as literal text."""
        logger.debug("Rendering inline HTML as literal text in RTF output")
        return [self._create_text_run(node.content)]

    def visit_footnote_reference(self, node: FootnoteReference) -> Any:
        """Render a footnote reference marker."""
        return [self._create_text_run(f"[^{node.identifier}]")]

    def visit_comment(self, node: Comment) -> Any:
        r"""Render a block-level comment node according to comment_mode option.

        RTF supports native annotations via the \annotation control word, but the pyth3
        library does not expose direct support for annotations. We use bracketed text
        as a fallback.

        Parameters
        ----------
        node : Comment
            Comment block to render

        Returns
        -------
        Any
            Pyth paragraph object with comment content, or None if ignoring

        Notes
        -----
        Supports multiple rendering modes via comment_mode option:
        - "bracketed": Render as [bracketed text] (default)
        - "ignore": Skip comment entirely

        """
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            return None

        # Build comment text with metadata
        comment_text = node.content

        # Add author/date info if available
        author = node.metadata.get("author")
        date = node.metadata.get("date")
        label = node.metadata.get("label")

        if author or date or label:
            prefix_parts = []
            if label:
                prefix_parts.append(f"Comment {label}")
            else:
                prefix_parts.append("Comment")

            if author:
                prefix_parts.append(f"by {author}")

            if date:
                prefix_parts.append(f"({date})")

            prefix = " ".join(prefix_parts)
            comment_text = f"{prefix}: {comment_text}"

        # Render as bracketed text paragraph
        Paragraph_cls = cast(Any, self._Paragraph)
        return Paragraph_cls(content=[self._create_text_run(f"[{comment_text}]")])

    def visit_comment_inline(self, node: CommentInline) -> Any:
        r"""Render an inline comment node according to comment_mode option.

        RTF supports native annotations via the \annotation control word, but the pyth3
        library does not expose direct support for annotations. We use bracketed inline
        text as a fallback.

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

        Returns
        -------
        Any
            List containing pyth text run with comment content, or empty list if ignoring

        Notes
        -----
        Supports multiple rendering modes via comment_mode option:
        - "bracketed": Render as [bracketed text] (default)
        - "ignore": Skip comment entirely

        """
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            return []

        # Build comment text with metadata
        comment_text = node.content

        # Add author/date info if available
        author = node.metadata.get("author")
        date = node.metadata.get("date")
        label = node.metadata.get("label")

        if author or date or label:
            prefix_parts = []
            if label:
                prefix_parts.append(f"Comment {label}")
            else:
                prefix_parts.append("Comment")

            if author:
                prefix_parts.append(f"by {author}")

            if date:
                prefix_parts.append(f"({date})")

            prefix = " ".join(prefix_parts)
            comment_text = f"{prefix}: {comment_text}"

        # Render as bracketed inline text
        return [self._create_text_run(f"[{comment_text}]")]
