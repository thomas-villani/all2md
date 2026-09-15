#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_docx_ast.py
"""Unit tests for DOCX to AST converter.

Tests cover:
- DOCX paragraph to AST node conversion
- Heading detection and conversion
- Text formatting (bold, italic, underline, etc.)
- Hyperlink processing
- List detection and conversion
- Table structure conversion
- Image markdown parsing
- Run grouping and formatting preservation

"""

import io
from typing import Any

import docx
import pytest
from docx.oxml import parse_xml
from fixtures import FIXTURES_PATH

from all2md.ast import (
    BlockQuote,
    Code,
    CommentInline,
    Document,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    List,
    MathBlock,
    MathInline,
    Paragraph,
    Strikethrough,
    Strong,
    Subscript,
    Superscript,
    Table,
    Text,
    Underline,
)
from all2md.ast.transforms import extract_nodes
from all2md.options import DocxOptions
from all2md.parsers.docx import DocxToAstConverter
from all2md.renderers.markdown import MarkdownRenderer

FIXTURE_FOOTNOTES_DOC = FIXTURES_PATH / "documents" / "footnotes-endnotes-comments.docx"
FIXTURE_MATH_DOC = FIXTURES_PATH / "documents" / "math-basic.docx"


def _inline_text(nodes: list, comment_mode: str = "blockquote") -> str:
    """Extract text from AST nodes, simulating markdown rendering.

    Parameters
    ----------
    nodes : list
        List of AST nodes
    comment_mode : str, default "blockquote"
        How to render comment nodes (matches renderer option)

    """
    parts: list[str] = []
    for node in nodes:
        if isinstance(node, Text):
            parts.append(node.content)
        elif isinstance(node, CommentInline):
            # Handle inline comments similar to markdown renderer
            if comment_mode == "ignore":
                continue
            elif comment_mode == "blockquote":
                comment_text = node.content
                if node.metadata.get("author"):
                    author = node.metadata.get("author")
                    label = node.metadata.get("label", "")
                    prefix = f"[Comment {label}" if label else "[Comment"
                    comment_text = f"{prefix} by {author}: {comment_text}]"
                else:
                    comment_text = f"[{comment_text}]"
                parts.append(comment_text)
            else:  # html
                # For html mode, just include the content
                parts.append(node.content)
        elif hasattr(node, "content"):
            child = node.content
            if isinstance(child, list):
                parts.append(_inline_text(child, comment_mode=comment_mode))
    return "".join(parts)


@pytest.mark.unit
class TestBasicElements:
    """Tests for basic DOCX element conversion."""

    def test_simple_paragraph(self) -> None:
        """Test converting a simple paragraph."""
        doc = docx.Document()
        doc.add_paragraph("Hello world")

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        assert isinstance(ast_doc, Document)
        assert len(ast_doc.children) == 1
        assert isinstance(ast_doc.children[0], Paragraph)
        para = ast_doc.children[0]
        assert len(para.content) == 1
        assert isinstance(para.content[0], Text)
        assert para.content[0].content == "Hello world"

    def test_multiple_paragraphs(self) -> None:
        """Test converting multiple paragraphs."""
        doc = docx.Document()
        doc.add_paragraph("First")
        doc.add_paragraph("Second")
        doc.add_paragraph("Third")

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        assert len(ast_doc.children) == 3
        assert all(isinstance(child, Paragraph) for child in ast_doc.children)

    def test_headings_1_to_6(self) -> None:
        """Test converting all heading levels."""
        doc = docx.Document()
        doc.add_heading("Heading 1", level=1)
        doc.add_heading("Heading 2", level=2)
        doc.add_heading("Heading 3", level=3)
        doc.add_heading("Heading 4", level=4)
        doc.add_heading("Heading 5", level=5)
        doc.add_heading("Heading 6", level=6)

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        assert len(ast_doc.children) == 6
        for i, child in enumerate(ast_doc.children):
            assert isinstance(child, Heading)
            assert child.level == i + 1
            assert isinstance(child.content[0], Text)
            assert child.content[0].content == f"Heading {i + 1}"

    def test_empty_paragraphs_skipped(self) -> None:
        """Test that empty paragraphs are skipped."""
        doc = docx.Document()
        doc.add_paragraph("First")
        doc.add_paragraph("")  # Empty
        doc.add_paragraph("   ")  # Whitespace only
        doc.add_paragraph("Second")

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        # Only 2 paragraphs should be in AST (empty ones skipped)
        assert len(ast_doc.children) == 2
        assert ast_doc.children[0].content[0].content == "First"
        assert ast_doc.children[1].content[0].content == "Second"

    def test_empty_list_styled_paragraph_skipped(self) -> None:
        """An empty paragraph carrying a list style must not emit a blank bullet.

        Regression: a stray empty leading paragraph styled ``List Bullet`` (a
        common DOCX template artifact) previously slipped past the empty-paragraph
        filter and produced a leading blank list item / blank line.
        """
        doc = docx.Document()
        empty = doc.add_paragraph("")
        try:
            empty.style = doc.styles["List Bullet"]
        except KeyError:  # pragma: no cover - style always present in default template
            pytest.skip("List Bullet style unavailable")
        doc.add_paragraph("Hello world")

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        assert len(ast_doc.children) == 1
        assert isinstance(ast_doc.children[0], Paragraph)
        assert ast_doc.children[0].content[0].content == "Hello world"

    def test_leading_empty_paragraph_no_blank_line(self) -> None:
        """The rendered markdown must not open with a blank line."""
        doc = docx.Document()
        doc.add_paragraph("")  # stray leading empty paragraph (template artifact)
        doc.add_paragraph("Title text")

        md = MarkdownRenderer().render_to_string(DocxToAstConverter().convert_to_ast(doc))
        assert md.startswith("Title text")

    def test_heading_level_above_six_clamped(self) -> None:
        """Heading 7/8/9 styles must clamp to Heading level 6 without ValueError."""
        doc = docx.Document()
        doc.add_paragraph("Deep Heading", style="Heading 7")

        ast_doc = DocxToAstConverter().convert_to_ast(doc)

        assert len(ast_doc.children) == 1
        heading = ast_doc.children[0]
        assert isinstance(heading, Heading)
        assert heading.level == 6
        assert heading.content[0].content == "Deep Heading"

    def test_inline_math_extraction(self) -> None:
        """Inline OMML equations should become MathInline nodes."""
        doc = docx.Document()
        paragraph = doc.add_paragraph()
        paragraph.add_run("Inline ")
        math_run = paragraph.add_run()
        math_element = parse_xml(
            '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            "<m:r><m:t>x</m:t></m:r>"
            "</m:oMath>"
        )
        math_run._element.append(math_element)
        paragraph.add_run(" equals three")

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        assert isinstance(ast_doc.children[0], Paragraph)
        para = ast_doc.children[0]
        assert any(isinstance(node, MathInline) for node in para.content)

        texts = [node for node in para.content if isinstance(node, Text)]
        assert texts[0].content == "Inline "
        math_nodes = [node for node in para.content if isinstance(node, MathInline)]
        assert math_nodes[0].content == "x"
        assert math_nodes[0].notation == "latex"
        assert math_nodes[0].representations["latex"] == "x"


@pytest.mark.unit
class TestTextFormatting:
    """Tests for text formatting conversion."""

    def test_bold_text(self) -> None:
        """Test bold text conversion."""
        doc = docx.Document()
        para = doc.add_paragraph()
        run = para.add_run("Bold text")
        run.bold = True

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        assert isinstance(para_node.content[0], Strong)
        assert isinstance(para_node.content[0].content[0], Text)
        assert para_node.content[0].content[0].content == "Bold text"

    def test_italic_text(self) -> None:
        """Test italic text conversion."""
        doc = docx.Document()
        para = doc.add_paragraph()
        run = para.add_run("Italic text")
        run.italic = True

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        assert isinstance(para_node.content[0], Emphasis)
        assert isinstance(para_node.content[0].content[0], Text)
        assert para_node.content[0].content[0].content == "Italic text"

    def test_underline_text(self) -> None:
        """Test underline text conversion."""
        doc = docx.Document()
        para = doc.add_paragraph()
        run = para.add_run("Underlined text")
        run.underline = True

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        assert isinstance(para_node.content[0], Underline)
        assert isinstance(para_node.content[0].content[0], Text)
        assert para_node.content[0].content[0].content == "Underlined text"

    def test_strikethrough_text(self) -> None:
        """Test strikethrough text conversion."""
        doc = docx.Document()
        para = doc.add_paragraph()
        run = para.add_run("Strikethrough text")
        run.font.strike = True

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        assert isinstance(para_node.content[0], Strikethrough)
        assert isinstance(para_node.content[0].content[0], Text)
        assert para_node.content[0].content[0].content == "Strikethrough text"

    def test_subscript_text(self) -> None:
        """Test subscript text conversion."""
        doc = docx.Document()
        para = doc.add_paragraph()
        run = para.add_run("H2O")
        run.font.subscript = True

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        assert isinstance(para_node.content[0], Subscript)

    def test_superscript_text(self) -> None:
        """Test superscript text conversion."""
        doc = docx.Document()
        para = doc.add_paragraph()
        run = para.add_run("E=mc^2")
        run.font.superscript = True

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        assert isinstance(para_node.content[0], Superscript)

    def test_multiple_formatting(self) -> None:
        """Test text with multiple formatting applied."""
        doc = docx.Document()
        para = doc.add_paragraph()
        run = para.add_run("Bold and italic")
        run.bold = True
        run.italic = True

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        # Should be nested: Emphasis -> Strong -> Text (italic applied after bold)
        assert isinstance(para_node.content[0], Emphasis)
        assert isinstance(para_node.content[0].content[0], Strong)
        assert isinstance(para_node.content[0].content[0].content[0], Text)
        assert para_node.content[0].content[0].content[0].content == "Bold and italic"

    def test_mixed_formatting_runs(self) -> None:
        """Test paragraph with multiple runs having different formatting."""
        doc = docx.Document()
        para = doc.add_paragraph()
        para.add_run("Normal ")
        bold_run = para.add_run("bold ")
        bold_run.bold = True
        para.add_run("normal ")
        italic_run = para.add_run("italic")
        italic_run.italic = True

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        # Should have 4 inline nodes
        assert len(para_node.content) == 4
        assert isinstance(para_node.content[0], Text)
        assert isinstance(para_node.content[1], Strong)
        assert isinstance(para_node.content[2], Text)
        assert isinstance(para_node.content[3], Emphasis)


class TestRunCharacterStyle:
    """Tests for run-level named character style capture (round-trip fidelity)."""

    def test_named_character_style_stashed_on_inline_node(self) -> None:
        """A run's named character style rides on the built inline node's metadata."""
        doc = docx.Document()
        para = doc.add_paragraph()
        run = para.add_run("quoted")
        run.style = doc.styles["Intense Emphasis"]

        ast_doc = DocxToAstConverter().convert_to_ast(doc)

        node = ast_doc.children[0].content[0]
        assert isinstance(node, Text)
        assert node.metadata.get("source_style") == "Intense Emphasis"

    def test_default_run_style_not_stashed(self) -> None:
        """The default 'Default Paragraph Font' style carries no metadata."""
        doc = docx.Document()
        para = doc.add_paragraph()
        para.add_run("plain")

        ast_doc = DocxToAstConverter().convert_to_ast(doc)

        node = ast_doc.children[0].content[0]
        assert isinstance(node, Text)
        assert "source_style" not in node.metadata

    def test_character_style_stashed_on_outermost_formatted_node(self) -> None:
        """A styled *and* bold run stashes the style on the wrapping Strong node."""
        doc = docx.Document()
        para = doc.add_paragraph()
        run = para.add_run("strong-styled")
        run.bold = True
        run.style = doc.styles["Intense Reference"]

        ast_doc = DocxToAstConverter().convert_to_ast(doc)

        strong = ast_doc.children[0].content[0]
        assert isinstance(strong, Strong)
        assert strong.metadata.get("source_style") == "Intense Reference"
        # The inner Text is unstyled — the style lives on the outermost node only.
        assert "source_style" not in strong.content[0].metadata

    def test_style_change_splits_run_group(self) -> None:
        """Adjacent runs with the same formatting but different styles do not merge."""
        doc = docx.Document()
        para = doc.add_paragraph()
        first = para.add_run("alpha")
        first.style = doc.styles["Intense Emphasis"]
        second = para.add_run("beta")
        second.style = doc.styles["Intense Reference"]

        ast_doc = DocxToAstConverter().convert_to_ast(doc)

        content = ast_doc.children[0].content
        assert len(content) == 2
        assert content[0].content == "alpha"
        assert content[0].metadata.get("source_style") == "Intense Emphasis"
        assert content[1].content == "beta"
        assert content[1].metadata.get("source_style") == "Intense Reference"


@pytest.mark.unit
class TestLists:
    """Tests for list conversion."""

    def test_bullet_list(self) -> None:
        """Test bullet list conversion."""
        doc = docx.Document()
        doc.add_paragraph("Item 1", style="List Bullet")
        doc.add_paragraph("Item 2", style="List Bullet")
        doc.add_paragraph("Item 3", style="List Bullet")

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        # Should have one List node
        assert len(ast_doc.children) == 1
        assert isinstance(ast_doc.children[0], List)
        list_node = ast_doc.children[0]
        assert not list_node.ordered
        assert len(list_node.items) == 3

    def test_numbered_list(self) -> None:
        """Test numbered list conversion."""
        doc = docx.Document()
        doc.add_paragraph("First", style="List Number")
        doc.add_paragraph("Second", style="List Number")
        doc.add_paragraph("Third", style="List Number")

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        # Should have one List node
        assert len(ast_doc.children) == 1
        assert isinstance(ast_doc.children[0], List)
        list_node = ast_doc.children[0]
        assert list_node.ordered
        assert len(list_node.items) == 3

    def test_list_followed_by_paragraph(self) -> None:
        """Test list properly closed when followed by regular paragraph."""
        doc = docx.Document()
        doc.add_paragraph("Item 1", style="List Bullet")
        doc.add_paragraph("Item 2", style="List Bullet")
        doc.add_paragraph("Regular paragraph")

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        # Should have 2 nodes: List and Paragraph
        assert len(ast_doc.children) == 2
        assert isinstance(ast_doc.children[0], List)
        assert isinstance(ast_doc.children[1], Paragraph)

    def test_multiple_separate_lists(self) -> None:
        """Test multiple lists separated by paragraphs."""
        doc = docx.Document()
        doc.add_paragraph("List 1 Item 1", style="List Bullet")
        doc.add_paragraph("List 1 Item 2", style="List Bullet")
        doc.add_paragraph("Separator")
        doc.add_paragraph("List 2 Item 1", style="List Number")
        doc.add_paragraph("List 2 Item 2", style="List Number")

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        # Should have 3 nodes: List, Paragraph, List
        assert len(ast_doc.children) == 3
        assert isinstance(ast_doc.children[0], List)
        assert not ast_doc.children[0].ordered  # Bullet
        assert isinstance(ast_doc.children[1], Paragraph)
        assert isinstance(ast_doc.children[2], List)
        assert ast_doc.children[2].ordered  # Numbered


@pytest.mark.unit
class TestTables:
    """Tests for table conversion."""

    def test_simple_table(self) -> None:
        """Test simple table conversion."""
        doc = docx.Document()
        table = doc.add_table(rows=2, cols=2)
        table.rows[0].cells[0].text = "H1"
        table.rows[0].cells[1].text = "H2"
        table.rows[1].cells[0].text = "R1C1"
        table.rows[1].cells[1].text = "R1C2"

        converter = DocxToAstConverter(options=DocxOptions(preserve_tables=True))
        ast_doc = converter.convert_to_ast(doc)

        # Should have one Table node
        assert len(ast_doc.children) == 1
        assert isinstance(ast_doc.children[0], Table)
        table_node = ast_doc.children[0]

        # Check header
        assert table_node.header is not None
        assert len(table_node.header.cells) == 2

        # Check data rows
        assert len(table_node.rows) == 1
        assert len(table_node.rows[0].cells) == 2

    def test_table_with_formatted_cells(self) -> None:
        """Test table with formatted cell content."""
        doc = docx.Document()
        table = doc.add_table(rows=2, cols=2)

        # Add bold text to header
        para = table.rows[0].cells[0].paragraphs[0]
        run = para.add_run("Bold Header")
        run.bold = True

        # Add normal text to data cell
        table.rows[1].cells[0].text = "Normal text"

        converter = DocxToAstConverter(options=DocxOptions(preserve_tables=True))
        ast_doc = converter.convert_to_ast(doc)

        table_node = ast_doc.children[0]
        # Check that formatting is preserved
        header_cell = table_node.header.cells[0]
        assert isinstance(header_cell.content[0], Strong)

    def test_table_flattening(self) -> None:
        """Test table flattening when preserve_tables=False."""
        doc = docx.Document()
        table = doc.add_table(rows=2, cols=2)
        table.rows[0].cells[0].text = "H1"
        table.rows[0].cells[1].text = "H2"
        table.rows[1].cells[0].text = "R1C1"
        table.rows[1].cells[1].text = "R1C2"

        converter = DocxToAstConverter(options=DocxOptions(preserve_tables=False))
        ast_doc = converter.convert_to_ast(doc)

        # Should have multiple Paragraph nodes (flattened)
        assert all(isinstance(child, Paragraph) for child in ast_doc.children)
        assert len(ast_doc.children) >= 4  # At least 4 cells

    @staticmethod
    def _grid(rows: int, cols: int) -> tuple[docx.document.Document, docx.table.Table]:
        doc = docx.Document()
        table = doc.add_table(rows=rows, cols=cols)
        for r, row in enumerate(table.rows):
            for c, cell in enumerate(row.cells):
                cell.text = f"r{r}c{c}"
        return doc, table

    @staticmethod
    def _cell_texts(table_node: Table) -> list[list[tuple[str, int, int]]]:
        rows = [table_node.header, *table_node.rows]
        return [
            [
                ("".join(getattr(n, "content", "") for n in cell.content), cell.colspan, cell.rowspan)
                for cell in row.cells
            ]
            for row in rows
        ]

    def test_horizontal_merge_is_one_cell_with_a_colspan(self) -> None:
        """A gridSpan cell is read once, not once per grid column it covers."""
        doc, table = self._grid(2, 3)
        table.cell(1, 0).merge(table.cell(1, 1)).text = "wide"

        ast_doc = DocxToAstConverter(options=DocxOptions(preserve_tables=True)).convert_to_ast(doc)

        assert self._cell_texts(ast_doc.children[0])[1] == [("wide", 2, 1), ("r1c2", 1, 1)]

    def test_vertical_merge_is_one_cell_with_a_rowspan(self) -> None:
        """A vMerge continuation extends the cell above instead of repeating it."""
        doc, table = self._grid(3, 3)
        table.cell(1, 0).merge(table.cell(2, 0)).text = "tall"

        rows = self._cell_texts(DocxToAstConverter().convert_to_ast(doc).children[0])

        assert rows[1] == [("tall", 1, 2), ("r1c1", 1, 1), ("r1c2", 1, 1)]
        assert rows[2] == [("r2c1", 1, 1), ("r2c2", 1, 1)]

    def test_block_merge_spans_both_ways(self) -> None:
        """A merge over a 2x2 block is one cell spanning two rows and two columns."""
        doc, table = self._grid(3, 3)
        table.cell(1, 0).merge(table.cell(2, 1)).text = "block"

        rows = self._cell_texts(DocxToAstConverter().convert_to_ast(doc).children[0])

        assert rows[1] == [("block", 2, 2), ("r1c2", 1, 1)]
        assert rows[2] == [("r2c2", 1, 1)]

    def test_header_merged_down_into_the_data_rows(self) -> None:
        """A merge that starts in the header row still extends into the row below."""
        doc, table = self._grid(3, 2)
        table.cell(0, 0).merge(table.cell(1, 0)).text = "head"

        rows = self._cell_texts(DocxToAstConverter().convert_to_ast(doc).children[0])

        assert rows[0][0] == ("head", 1, 2)
        assert rows[1] == [("r1c1", 1, 1)]

    def test_grid_before_keeps_cells_in_their_columns(self) -> None:
        """Columns a row skips with w:gridBefore get an empty stand-in cell."""
        from docx.oxml.ns import nsdecls

        doc, table = self._grid(2, 3)
        tr = table.rows[1]._tr
        tr.remove(tr.tc_lst[0])
        tr.insert(0, parse_xml(f'<w:trPr {nsdecls("w")}><w:gridBefore w:val="1"/></w:trPr>'))

        rows = self._cell_texts(DocxToAstConverter().convert_to_ast(doc).children[0])

        assert rows[1] == [("", 1, 1), ("r1c1", 1, 1), ("r1c2", 1, 1)]

    def test_flattened_table_writes_a_merged_cell_once(self) -> None:
        """Flattening reads the same real cells, so merged text is not repeated."""
        doc, table = self._grid(3, 3)
        table.cell(1, 0).merge(table.cell(2, 1)).text = "block"

        ast_doc = DocxToAstConverter(options=DocxOptions(preserve_tables=False)).convert_to_ast(doc)
        texts = ["".join(getattr(n, "content", "") for n in p.content) for p in ast_doc.children]

        assert texts.count("block") == 1
        assert texts == ["r0c0", "r0c1", "r0c2", "block", "r1c2", "r2c2"]


@pytest.mark.unit
class TestHyperlinks:
    """Tests for hyperlink conversion."""

    def test_hyperlink_parsing(self) -> None:
        """Test hyperlink detection and URL extraction."""
        # Note: Creating actual hyperlinks in python-docx is complex,
        # so we test the conversion logic with mocked data
        converter = DocxToAstConverter()

        # Test URL extraction
        result = converter._process_hyperlink(None)
        assert result == (None, None)


@pytest.mark.unit
class TestFormattingKey:
    """Tests for run formatting key generation."""

    def test_formatting_key_plain_text(self) -> None:
        """Test formatting key for plain text."""
        doc = docx.Document()
        para = doc.add_paragraph()
        run = para.add_run("Plain text")

        converter = DocxToAstConverter()
        key = converter._get_run_formatting_key(run, False)

        # All False except is_hyperlink
        assert key == (False, False, False, False, False, False, False)

    def test_formatting_key_bold(self) -> None:
        """Test formatting key for bold text."""
        doc = docx.Document()
        para = doc.add_paragraph()
        run = para.add_run("Bold")
        run.bold = True

        converter = DocxToAstConverter()
        key = converter._get_run_formatting_key(run, False)

        assert key[0] is True  # bold
        assert key[1] is False  # italic

    def test_formatting_key_all_formatting(self) -> None:
        """Test formatting key with all formatting applied."""
        doc = docx.Document()
        para = doc.add_paragraph()
        run = para.add_run("Formatted")
        run.bold = True
        run.italic = True
        run.underline = True
        run.font.strike = True
        run.font.subscript = True

        converter = DocxToAstConverter()
        key = converter._get_run_formatting_key(run, True)

        assert key == (True, True, True, True, True, False, True)


@pytest.mark.unit
class TestListFinalization:
    """Tests for list finalization logic."""

    def test_list_at_end_of_document(self) -> None:
        """Test that list at end of document is properly finalized."""
        doc = docx.Document()
        doc.add_paragraph("Item 1", style="List Bullet")
        doc.add_paragraph("Item 2", style="List Bullet")
        # No paragraph after list

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        # List should still be in the document
        assert len(ast_doc.children) == 1
        assert isinstance(ast_doc.children[0], List)
        assert len(ast_doc.children[0].items) == 2

    def test_empty_list_stack(self) -> None:
        """Test finalization with empty list stack."""
        converter = DocxToAstConverter()
        result = converter._finalize_current_list()
        assert result is None


@pytest.mark.unit
class TestRunGrouping:
    """Tests for run grouping optimization."""

    def test_runs_with_same_formatting_grouped(self) -> None:
        """Test that consecutive runs with same formatting are grouped."""
        doc = docx.Document()
        para = doc.add_paragraph()
        run1 = para.add_run("Bold ")
        run1.bold = True
        run2 = para.add_run("text")
        run2.bold = True

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        # Should be grouped into single Strong node
        assert len(para_node.content) == 1
        assert isinstance(para_node.content[0], Strong)
        # Check text is combined
        text_content = para_node.content[0].content[0].content
        assert text_content == "Bold text"

    def test_runs_with_different_formatting_separate(self) -> None:
        """Test that runs with different formatting are kept separate."""
        doc = docx.Document()
        para = doc.add_paragraph()
        run1 = para.add_run("Bold")
        run1.bold = True
        run2 = para.add_run("Italic")
        run2.italic = True

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        para_node = ast_doc.children[0]
        # Should have 2 separate inline nodes
        assert len(para_node.content) == 2
        assert isinstance(para_node.content[0], Strong)
        assert isinstance(para_node.content[1], Emphasis)


@pytest.mark.unit
class TestComplexStructures:
    """Tests for complex document structures."""

    def test_mixed_content_document(self) -> None:
        """Test document with mixed content types."""
        doc = docx.Document()
        doc.add_heading("Title", level=1)
        doc.add_paragraph("Introduction paragraph")
        doc.add_paragraph("Item 1", style="List Bullet")
        doc.add_paragraph("Item 2", style="List Bullet")
        doc.add_paragraph("Conclusion paragraph")

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        # Should have: Heading, Paragraph, List, Paragraph
        assert len(ast_doc.children) == 4
        assert isinstance(ast_doc.children[0], Heading)
        assert isinstance(ast_doc.children[1], Paragraph)
        assert isinstance(ast_doc.children[2], List)
        assert isinstance(ast_doc.children[3], Paragraph)

    def test_heading_with_formatting(self) -> None:
        """Test heading with formatted text."""
        doc = docx.Document()
        heading = doc.add_heading(level=1)
        run = heading.add_run("Bold Title")
        run.bold = True

        converter = DocxToAstConverter()
        ast_doc = converter.convert_to_ast(doc)

        heading_node = ast_doc.children[0]
        assert isinstance(heading_node, Heading)
        assert heading_node.level == 1
        # Check formatting is preserved
        assert isinstance(heading_node.content[0], Strong)


@pytest.mark.unit
class TestFootnotes:
    """Tests for DOCX footnote and endnote extraction."""

    def test_footnote_reference_and_definition(self) -> None:
        """Parser should emit references and collect matching definitions."""
        ast_doc = self._convert_with_fixture()
        references, definitions = self._extract_notes(ast_doc)

        footnote_refs = [ref for ref in references if not ref.identifier.startswith("end")]
        footnote_defs = [definition for definition in definitions if definition.metadata.get("note_type") == "footnote"]

        assert footnote_refs, "Expected at least one footnote reference"
        assert footnote_defs, "Expected at least one captured footnote definition"

        footnote_ids = {definition.identifier for definition in footnote_defs}
        assert {ref.identifier for ref in footnote_refs} <= footnote_ids

        for definition in footnote_defs:
            assert definition.content, "Footnote definition should contain block content"
            assert all(isinstance(block, Paragraph) for block in definition.content)
            assert all(block.content for block in definition.content)

    def test_endnote_reference_and_definition(self) -> None:
        """Endnotes should use prefixed identifiers and be collected."""
        ast_doc = self._convert_with_fixture()
        references, definitions = self._extract_notes(ast_doc)

        endnote_refs = [ref for ref in references if ref.identifier.startswith("end")]
        endnote_defs = [definition for definition in definitions if definition.metadata.get("note_type") == "endnote"]

        assert endnote_refs, "Expected at least one endnote reference"
        assert endnote_defs, "Expected at least one captured endnote definition"

        endnote_ids = {definition.identifier for definition in endnote_defs}
        assert {ref.identifier for ref in endnote_refs} <= endnote_ids

        for definition in endnote_defs:
            assert definition.content, "Endnote definition should contain block content"
            assert all(isinstance(block, Paragraph) for block in definition.content)
            assert all(block.content for block in definition.content)

    def test_footnotes_can_be_disabled(self) -> None:
        """Footnotes should be omitted entirely when option disabled."""
        ast_doc = self._convert_with_fixture(include_footnotes=False)
        references, definitions = self._extract_notes(ast_doc)

        footnote_refs = [ref for ref in references if not ref.identifier.startswith("end")]
        assert not footnote_refs
        assert all(definition.metadata.get("note_type") != "footnote" for definition in definitions)
        assert any(ref.identifier.startswith("end") for ref in references), "Endnote references should remain"

    def test_endnotes_can_be_disabled(self) -> None:
        """Endnotes should be omitted when include_endnotes is False."""
        ast_doc = self._convert_with_fixture(include_endnotes=False)
        references, definitions = self._extract_notes(ast_doc)

        endnote_refs = [ref for ref in references if ref.identifier.startswith("end")]
        assert not endnote_refs
        assert all(definition.metadata.get("note_type") != "endnote" for definition in definitions)
        assert any(not ref.identifier.startswith("end") for ref in references), "Footnote references should remain"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_with_fixture(
        include_footnotes: bool = True,
        include_endnotes: bool = True,
    ) -> Document:
        options = DocxOptions(
            include_footnotes=include_footnotes,
            include_endnotes=include_endnotes,
            include_comments=False,
        )
        converter = DocxToAstConverter(options=options)
        fixture_doc = docx.Document(FIXTURE_FOOTNOTES_DOC)
        return converter.convert_to_ast(fixture_doc)

    @staticmethod
    def _extract_notes(document: Document) -> tuple[list[FootnoteReference], list[FootnoteDefinition]]:
        references = extract_nodes(document, FootnoteReference)
        definitions = extract_nodes(document, FootnoteDefinition)
        return references, definitions


@pytest.mark.unit
class TestComments:
    """Tests for DOCX comment rendering options."""

    def test_comments_append_when_position_is_footnotes(self) -> None:
        doc = docx.Document(str(FIXTURE_FOOTNOTES_DOC))
        options = DocxOptions(
            include_comments=True,
            comments_position="footnotes",
        )
        converter = DocxToAstConverter(options=options)
        ast_doc = converter.convert_to_ast(doc)

        # Parser creates Comment nodes (not BlockQuote) - renderer decides presentation
        from all2md.ast import Comment

        comments = [node for node in ast_doc.children if isinstance(node, Comment)]
        assert comments, "Expected comments to be appended as Comment nodes"

        # Check comment content and metadata
        assert "I decided not to think of something funny." in comments[0].content
        assert comments[0].metadata["comment_type"] == "docx_review"
        assert comments[0].metadata.get("author") is not None

        # Verify inline comment is NOT in paragraph (since position is "footnotes")
        paragraph = next(
            child
            for child in ast_doc.children
            if isinstance(child, Paragraph) and "However, it will have a comment" in _inline_text(child.content)
        )
        inline_text = _inline_text(paragraph.content)
        assert "comment1" not in inline_text

    def test_comments_inline_when_requested(self) -> None:
        doc = docx.Document(str(FIXTURE_FOOTNOTES_DOC))
        options = DocxOptions(
            include_comments=True,
            comments_position="inline",
        )
        converter = DocxToAstConverter(options=options)
        ast_doc = converter.convert_to_ast(doc)

        paragraph = next(
            child
            for child in ast_doc.children
            if isinstance(child, Paragraph) and "However, it will have a comment" in _inline_text(child.content)
        )
        inline_text = _inline_text(paragraph.content)
        assert "I decided not to think of something funny." in inline_text
        assert "comment1" in inline_text

        blockquotes = [node for node in ast_doc.children if isinstance(node, BlockQuote)]
        assert not blockquotes, "Inline comments should not append trailing blockquotes"


@pytest.mark.unit
class TestCommentThreads:
    """Comment body text, anchored range text, replies and resolved threads."""

    W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
    W15 = "http://schemas.microsoft.com/office/word/2012/wordml"

    @classmethod
    def _threaded_doc(cls, extended: str | None) -> docx.document.Document:
        """Alice comments on "deliver the goods"; Bob comments on "the goods".

        ``extended`` is the commentsExtended.xml body (the commentEx entries), or
        None for a document with no thread part. The two comment bodies carry
        paraIds 00000001 and 00000002.
        """
        from docx.opc.packuri import PackURI
        from docx.opc.part import Part

        doc = docx.Document()
        paragraph = doc.add_paragraph("The Supplier shall ")
        first = paragraph.add_run("deliver ")
        second = paragraph.add_run("the goods")
        paragraph.add_run(" by Friday.")
        alice = doc.add_comment([first, second], text="Recon", author="Alice")
        alice.paragraphs[0].add_run("sider ")
        alice.paragraphs[0].add_run("this")
        alice.add_paragraph("Second paragraph.")
        bob = doc.add_comment(second, text="Agreed.", author="Bob")
        for number, comment in enumerate((alice, bob), start=1):
            comment._comment_elm.xpath("./w:p")[-1].set(f"{{{cls.W14}}}paraId", f"0000000{number}")

        if extended is not None:
            blob = f'<w15:commentsEx xmlns:w15="{cls.W15}">{extended}</w15:commentsEx>'.encode()
            part = Part(
                PackURI("/word/commentsExtended.xml"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml",
                blob,
                doc.part.package,
            )
            doc.part.relate_to(part, "http://schemas.microsoft.com/office/2011/relationships/commentsExtended")

        buffer = io.BytesIO()
        doc.save(buffer)
        return docx.Document(io.BytesIO(buffer.getvalue()))

    @staticmethod
    def _comments(doc: docx.document.Document) -> dict[str, Any]:
        from all2md.ast import Comment

        options = DocxOptions(include_comments=True, comments_position="footnotes")
        ast_doc = DocxToAstConverter(options=options).convert_to_ast(doc)
        return {node.metadata["label"]: node for node in ast_doc.children if isinstance(node, Comment)}

    def test_runs_join_without_spaces_and_paragraphs_break(self) -> None:
        comments = self._comments(self._threaded_doc(None))
        assert comments["comment1"].content == "Reconsider this\nSecond paragraph."

    def test_anchored_text_is_the_commented_range(self) -> None:
        comments = self._comments(self._threaded_doc(None))
        assert comments["comment1"].metadata["anchored_text"] == "deliver the goods"
        assert comments["comment2"].metadata["anchored_text"] == "the goods"

    def test_no_thread_part_means_unresolved_roots(self) -> None:
        comments = self._comments(self._threaded_doc(None))
        for node in comments.values():
            assert "parent_label" not in node.metadata
            assert "resolved" not in node.metadata

    def test_reply_names_parent_and_follows_resolved_root(self) -> None:
        extended = (
            '<w15:commentEx w15:paraId="00000001" w15:done="1"/>'
            '<w15:commentEx w15:paraId="00000002" w15:paraIdParent="00000001" w15:done="0"/>'
        )
        comments = self._comments(self._threaded_doc(extended))
        assert "parent_label" not in comments["comment1"].metadata
        assert comments["comment1"].metadata["resolved"] is True
        assert comments["comment2"].metadata["parent_label"] == "comment1"
        assert comments["comment2"].metadata["resolved"] is True

    def test_dangling_parent_leaves_a_root(self) -> None:
        extended = '<w15:commentEx w15:paraId="00000002" w15:paraIdParent="DEADBEEF" w15:done="0"/>'
        comments = self._comments(self._threaded_doc(extended))
        assert "parent_label" not in comments["comment2"].metadata

    def test_range_across_paragraphs_reads_as_one_line(self) -> None:
        doc = docx.Document()
        first = doc.add_paragraph("End of one.")
        doc.add_paragraph("Start of two.")
        doc.add_comment(first.runs[0], text="Spans both.", author="A")
        # Move the range end (and its reference run) into the second paragraph.
        body = doc.element.body
        end = body.xpath(".//w:commentRangeEnd")[0]
        reference_run = end.getnext()
        second_paragraph = body.xpath("./w:p")[1]
        second_paragraph.append(end)
        if reference_run is not None:
            second_paragraph.append(reference_run)

        comments = self._comments(doc)
        assert comments["comment1"].metadata["anchored_text"] == "End of one. Start of two."


@pytest.mark.unit
class TestMathExtraction:
    """Tests for DOCX math conversion."""

    def test_math_block_from_fixture(self) -> None:
        """Math blocks should convert to MathBlock nodes with LaTeX content."""
        converter = DocxToAstConverter()
        ast_doc = converter.parse(FIXTURE_MATH_DOC)

        math_nodes = extract_nodes(ast_doc, MathBlock)
        assert math_nodes, "Expected at least one MathBlock from math fixture"

        content = math_nodes[0].content.replace(" ", "")
        assert content.startswith("e^{πi}")
        assert "=-1" in content
        assert math_nodes[0].notation == "latex"
        assert math_nodes[0].representations["latex"].replace(" ", "") == content


@pytest.mark.unit
class TestCodeAndBlockquoteRoundTrip:
    """Tests for inline code and blockquote DOCX round-trip fidelity (issue #71)."""

    def test_quote_style_paragraph_becomes_blockquote(self) -> None:
        """A Word 'Quote' paragraph parses to a BlockQuote, not a list item."""
        doc = docx.Document()
        doc.add_paragraph("a quoted line", style="Quote")

        ast_doc = DocxToAstConverter().convert_to_ast(doc)

        blockquotes = extract_nodes(ast_doc, BlockQuote)
        assert len(blockquotes) == 1
        assert not extract_nodes(ast_doc, List), "Quote paragraph must not be read as a list"
        assert _inline_text(blockquotes[0].children[0].content) == "a quoted line"

    def test_consecutive_quote_paragraphs_coalesce(self) -> None:
        """Adjacent 'Quote' paragraphs merge into a single multi-paragraph BlockQuote."""
        doc = docx.Document()
        doc.add_paragraph("line one", style="Quote")
        doc.add_paragraph("line two", style="Quote")

        ast_doc = DocxToAstConverter().convert_to_ast(doc)

        blockquotes = extract_nodes(ast_doc, BlockQuote)
        assert len(blockquotes) == 1
        assert len(blockquotes[0].children) == 2

    def test_inline_code_char_style_becomes_code_node(self) -> None:
        """A run wearing the inline-code character style parses to a Code node."""
        from docx.enum.style import WD_STYLE_TYPE

        doc = docx.Document()
        doc.styles.add_style("Verbatim Char", WD_STYLE_TYPE.CHARACTER)
        para = doc.add_paragraph("Use ")
        code_run = para.add_run("f(x)")
        code_run.style = "Verbatim Char"
        para.add_run(" here")

        ast_doc = DocxToAstConverter().convert_to_ast(doc)

        code_nodes = extract_nodes(ast_doc, Code)
        assert len(code_nodes) == 1
        assert code_nodes[0].content == "f(x)"

    def test_markdown_docx_markdown_preserves_inline_code_and_quote(self) -> None:
        """Md -> docx -> md keeps inline code as code and a quote as a quote (#71)."""
        from all2md import from_ast, to_ast

        source = "Body with `inline code`.\n\n> a quoted line\n"
        ast = to_ast(source.encode(), source_format="markdown")
        docx_bytes = from_ast(ast, target_format="docx")
        back = to_ast(docx_bytes, source_format="docx")

        assert len(extract_nodes(back, Code)) == 1
        assert len(extract_nodes(back, BlockQuote)) == 1
        assert not extract_nodes(back, List), "Quote must not decay into a bullet list"

        rendered = from_ast(back, target_format="markdown")
        assert "`inline code`" in rendered
        assert "> a quoted line" in rendered
        assert "* a quoted line" not in rendered


class TestTitleRoundTrip:
    """Tests for the Word 'Title' style inverse (issue #70)."""

    def test_title_style_becomes_title_heading(self) -> None:
        """A 'Title' paragraph maps back to a level-1 heading marked is_title."""
        doc = docx.Document()
        doc.add_paragraph("My Title", style="Title")

        ast_doc = DocxToAstConverter().convert_to_ast(doc)

        assert isinstance(ast_doc.children[0], Heading)
        title = ast_doc.children[0]
        assert title.level == 1
        assert title.metadata.get("is_title") is True
        assert _inline_text(title.content) == "My Title"

    def test_headings_after_title_are_demoted(self) -> None:
        """Headings following a leading title shift down one level to undo promotion."""
        doc = docx.Document()
        doc.add_paragraph("My Title", style="Title")
        doc.add_heading("Section", level=1)
        doc.add_heading("Subsection", level=2)

        ast_doc = DocxToAstConverter().convert_to_ast(doc)
        headings = [c for c in ast_doc.children if isinstance(c, Heading)]

        # Title stays at 1; "Heading 1"/"Heading 2" become level 2/3.
        assert [h.level for h in headings] == [1, 2, 3]
        assert headings[0].metadata.get("is_title") is True

    def test_demotion_after_title_is_clamped_at_level_6(self) -> None:
        """An H6 after a title must stay an H6, not become an out-of-spec level 7.

        ``Heading`` enforces a 1-6 level; the demotion mutates ``.level`` directly,
        which would otherwise leave an invalid node that serialization and the
        round-trip scorer see even though the Markdown renderer hides it.
        """
        doc = docx.Document()
        doc.add_paragraph("My Title", style="Title")
        doc.add_heading("Deep", level=6)

        ast_doc = DocxToAstConverter().convert_to_ast(doc)
        headings = [c for c in ast_doc.children if isinstance(c, Heading)]

        assert [h.level for h in headings] == [1, 6]
        assert all(1 <= h.level <= 6 for h in headings), "demotion produced an out-of-range heading level"

    def test_non_leading_title_does_not_shift_headings(self) -> None:
        """A title that is not the first content leaves following headings untouched."""
        doc = docx.Document()
        doc.add_paragraph("Intro paragraph.")
        doc.add_paragraph("Mid Title", style="Title")
        doc.add_heading("Section", level=1)

        ast_doc = DocxToAstConverter().convert_to_ast(doc)
        headings = [c for c in ast_doc.children if isinstance(c, Heading)]

        # The non-leading title still becomes a heading, but no promotion was applied
        # by the renderer in this shape, so the "Heading 1" must stay at level 1.
        assert headings[0].metadata.get("is_title") is True
        assert headings[0].level == 1
        assert headings[1].level == 1

    def test_markdown_docx_markdown_round_trip_preserves_outline(self) -> None:
        """Md -> docx -> md keeps the title a heading and the outline intact (#70)."""
        from all2md import from_ast, to_ast

        source = "# Title\n\n## Section\n\nBody.\n"
        ast = to_ast(source.encode(), source_format="markdown")
        docx_bytes = from_ast(ast, target_format="docx")
        back = to_ast(docx_bytes, source_format="docx")
        rendered = from_ast(back, target_format="markdown")

        assert "# Title" in rendered
        assert "## Section" in rendered
        # The title must not have decayed into body text, nor Section into an H1.
        assert "\nTitle\n" not in rendered
        assert "\n# Section" not in rendered


@pytest.mark.unit
class TestTableCellLists:
    """Numbered and bulleted paragraphs inside a table cell."""

    @staticmethod
    def _doc_with_numbering() -> docx.document.Document:
        from docx.oxml.ns import nsdecls

        w = nsdecls("w")
        doc = docx.Document()
        numbering = doc.part.numbering_part.element
        numbering.insert(
            0,
            parse_xml(
                f'<w:abstractNum {w} w:abstractNumId="90">'
                '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl>'
                '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="lowerLetter"/><w:lvlText w:val="(%2)"/></w:lvl>'
                "</w:abstractNum>"
            ),
        )
        numbering.insert(
            1,
            parse_xml(
                f'<w:abstractNum {w} w:abstractNumId="91">'
                '<w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/></w:lvl>'
                "</w:abstractNum>"
            ),
        )
        numbering.append(parse_xml(f'<w:num {w} w:numId="90"><w:abstractNumId w:val="90"/></w:num>'))
        numbering.append(parse_xml(f'<w:num {w} w:numId="91"><w:abstractNumId w:val="91"/></w:num>'))
        return doc

    @staticmethod
    def _list_paragraph(container, text: str, num_id: int = 90, ilvl: int = 0) -> None:
        from docx.oxml.ns import nsdecls

        paragraph = container.add_paragraph(text)
        paragraph._p.get_or_add_pPr().insert(
            0,
            parse_xml(f'<w:numPr {nsdecls("w")}><w:ilvl w:val="{ilvl}"/><w:numId w:val="{num_id}"/></w:numPr>'),
        )

    def _cell(self) -> tuple[docx.document.Document, "docx.table._Cell"]:
        doc = self._doc_with_numbering()
        table = doc.add_table(rows=2, cols=1)
        table.cell(0, 0).text = "Obligation"
        return doc, table.cell(1, 0)

    @staticmethod
    def _markdown(doc: docx.document.Document, **options: bool) -> str:
        ast_doc = DocxToAstConverter(options=DocxOptions(**options)).convert_to_ast(doc)
        return MarkdownRenderer().render_to_string(ast_doc)

    def test_cell_paragraphs_are_separate_lines(self) -> None:
        """Paragraphs of one cell are joined by a line break, not run together."""
        doc, cell = self._cell()
        cell.paragraphs[0].text = "first"
        cell.add_paragraph("second")

        assert "| first<br>second |" in self._markdown(doc)

    def test_numbered_paragraphs_in_a_cell_keep_their_numbers(self) -> None:
        """A numbered clause inside a cell keeps its number on its own line."""
        doc, cell = self._cell()
        cell.paragraphs[0].text = "The Supplier shall:"
        self._list_paragraph(cell, "deliver the goods")
        self._list_paragraph(cell, "invoice monthly")

        assert "| The Supplier shall:<br>1. deliver the goods<br>2. invoice monthly |" in self._markdown(doc)

    def test_nested_level_counts_from_one_under_each_parent(self) -> None:
        """A deeper level restarts its count whenever a shallower item intervenes."""
        doc, cell = self._cell()
        cell.paragraphs[0].text = ""
        self._list_paragraph(cell, "a")
        self._list_paragraph(cell, "b", ilvl=1)
        self._list_paragraph(cell, "c", ilvl=1)
        self._list_paragraph(cell, "d")
        self._list_paragraph(cell, "e", ilvl=1)

        assert "| 1. a<br>(a) b<br>(b) c<br>2. d<br>(a) e |" in self._markdown(doc)

    def test_bulleted_paragraph_in_a_cell_keeps_a_bullet(self) -> None:
        """A bullet paragraph inside a cell is marked with the bullet Word prints."""
        doc, cell = self._cell()
        cell.paragraphs[0].text = "Notes:"
        self._list_paragraph(cell, "one", num_id=91)

        assert "| Notes:<br>• one |" in self._markdown(doc)

    def test_flattened_cell_list_is_a_list_closed_by_the_cell(self) -> None:
        """With tables flattened, a cell's numbered paragraphs form a list that ends with the cell."""
        doc = self._doc_with_numbering()
        table = doc.add_table(rows=1, cols=2)
        first, second = table.cell(0, 0), table.cell(0, 1)
        first.paragraphs[0].text = "The Supplier shall:"
        self._list_paragraph(first, "deliver the goods")
        self._list_paragraph(first, "invoice monthly")
        second.text = "next cell"

        ast_doc = DocxToAstConverter(options=DocxOptions(preserve_tables=False)).convert_to_ast(doc)

        assert [type(child) for child in ast_doc.children] == [Paragraph, List, Paragraph]
        assert len(ast_doc.children[1].items) == 2

    def test_body_list_before_a_table_stays_ahead_of_it(self) -> None:
        """A list that runs up to a table is emitted before the table, not after it."""
        doc = self._doc_with_numbering()
        self._list_paragraph(doc, "body item one")
        self._list_paragraph(doc, "body item two")
        doc.add_table(rows=1, cols=1).cell(0, 0).text = "cell"
        doc.add_paragraph("After the table.")

        ast_doc = DocxToAstConverter().convert_to_ast(doc)

        assert [type(child) for child in ast_doc.children] == [List, Table, Paragraph]


class TestListStartAndRestart:
    """The number a Word list starts at, and where Word restarts or continues the count."""

    _cells = TestTableCellLists

    @classmethod
    def _doc(cls, *extra_xml: str) -> docx.document.Document:
        """Build a document with abstractNum 90 (decimal, lowerLetter), 91 (bullet), and ``extra_xml``."""
        from docx.oxml.ns import nsdecls

        doc = cls._cells._doc_with_numbering()
        numbering = doc.part.numbering_part.element
        w = nsdecls("w")
        for xml in extra_xml:
            element = parse_xml(
                xml.replace("<w:abstractNum ", f"<w:abstractNum {w} ").replace("<w:num ", f"<w:num {w} ")
            )
            if element.tag.endswith("abstractNum"):
                numbering.insert(0, element)
            else:
                numbering.append(element)
        return doc

    @staticmethod
    def _lists(doc: docx.document.Document) -> list[List]:
        return [child for child in DocxToAstConverter().convert_to_ast(doc).children if isinstance(child, List)]

    def test_list_interrupted_by_a_paragraph_carries_on_counting(self) -> None:
        """Prose between two runs of one numbered list does not restart it at 1."""
        doc = self._doc()
        self._cells._list_paragraph(doc, "one")
        self._cells._list_paragraph(doc, "two")
        doc.add_paragraph("An interruption.")
        self._cells._list_paragraph(doc, "three")

        assert [lst.start for lst in self._lists(doc)] == [1, 3]
        assert "3. three" in self._cells._markdown(doc)

    def test_level_start_value_is_honoured(self) -> None:
        """A level defined to start at 5 prints 5 first."""
        doc = self._doc(
            '<w:abstractNum w:abstractNumId="92"><w:lvl w:ilvl="0"><w:start w:val="5"/>'
            '<w:numFmt w:val="decimal"/></w:lvl></w:abstractNum>',
            '<w:num w:numId="92"><w:abstractNumId w:val="92"/></w:num>',
        )
        self._cells._list_paragraph(doc, "five", num_id=92)
        self._cells._list_paragraph(doc, "six", num_id=92)

        assert "5. five\n6. six" in self._cells._markdown(doc)

    def test_start_override_restarts_a_list_written_straight_after_another(self) -> None:
        """Word's Restart Numbering splits two back-to-back lists instead of fusing them 1..4."""
        doc = self._doc(
            '<w:num w:numId="93"><w:abstractNumId w:val="90"/>'
            '<w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>'
        )
        self._cells._list_paragraph(doc, "a")
        self._cells._list_paragraph(doc, "b")
        self._cells._list_paragraph(doc, "c", num_id=93)
        self._cells._list_paragraph(doc, "d", num_id=93)

        lists = self._lists(doc)
        assert [(lst.start, len(lst.items)) for lst in lists] == [(1, 2), (1, 2)]

    def test_second_instance_without_override_continues_the_same_list(self) -> None:
        """Two w:num instances of one abstract number count as one list."""
        doc = self._doc('<w:num w:numId="94"><w:abstractNumId w:val="90"/></w:num>')
        self._cells._list_paragraph(doc, "a")
        self._cells._list_paragraph(doc, "b")
        self._cells._list_paragraph(doc, "c", num_id=94)

        lists = self._lists(doc)
        assert [(lst.start, len(lst.items)) for lst in lists] == [(1, 3)]

    def test_numbering_in_a_table_cell_continues_from_the_body(self) -> None:
        """Word's counter runs through table cells in document order."""
        doc = self._doc()
        self._cells._list_paragraph(doc, "one")
        self._cells._list_paragraph(doc, "two")
        cell = doc.add_table(rows=1, cols=1).cell(0, 0)
        cell.paragraphs[0].text = "Also:"
        self._cells._list_paragraph(cell, "three")
        doc.add_paragraph("After.")
        self._cells._list_paragraph(doc, "four")

        markdown = self._cells._markdown(doc)
        assert "| Also:<br>3. three |" in markdown
        assert "4. four" in markdown

    def test_level_restart_zero_keeps_counting_across_parents(self) -> None:
        """``w:lvlRestart`` 0 means a shallower item never resets the deeper count."""
        doc = self._doc(
            '<w:abstractNum w:abstractNumId="95">'
            '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/></w:lvl>'
            '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:lvlRestart w:val="0"/><w:numFmt w:val="decimal"/></w:lvl>'
            "</w:abstractNum>",
            '<w:num w:numId="95"><w:abstractNumId w:val="95"/></w:num>',
        )
        cell = doc.add_table(rows=1, cols=1).cell(0, 0)
        cell.paragraphs[0].text = ""
        for text, ilvl in (("a", 0), ("b", 1), ("c", 0), ("d", 1)):
            self._cells._list_paragraph(cell, text, num_id=95, ilvl=ilvl)

        assert "| 1. a<br>1. b<br>2. c<br>2. d |" in self._cells._markdown(doc)

    def test_numbered_heading_restarts_the_level_below_it(self) -> None:
        """A heading numbered by the same definition resets the clauses under it."""
        from docx.oxml.ns import nsdecls

        doc = self._doc()
        for heading in ("Article one", "Article two"):
            paragraph = doc.add_paragraph(heading, style="Heading 1")
            paragraph._p.get_or_add_pPr().insert(
                0, parse_xml(f'<w:numPr {nsdecls("w")}><w:ilvl w:val="0"/><w:numId w:val="90"/></w:numPr>')
            )
            self._cells._list_paragraph(doc, f"{heading} clause a", ilvl=1)
            self._cells._list_paragraph(doc, f"{heading} clause b", ilvl=1)

        markdown = self._cells._markdown(doc)
        assert "# 2. Article two" in markdown
        assert "(a) Article two clause a" in markdown
        assert "(b) Article two clause b" in markdown

    def test_list_opening_deeper_than_what_follows_keeps_its_items(self) -> None:
        """A list whose first items sit at level 2 is not discarded when level 1 arrives."""
        doc = self._doc(
            '<w:abstractNum w:abstractNumId="97">'
            '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl>'
            '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%2."/></w:lvl>'
            "</w:abstractNum>",
            '<w:num w:numId="97"><w:abstractNumId w:val="97"/></w:num>',
        )
        self._cells._list_paragraph(doc, "deep a", num_id=97, ilvl=1)
        self._cells._list_paragraph(doc, "deep b", num_id=97, ilvl=1)
        self._cells._list_paragraph(doc, "top c", num_id=97)

        markdown = self._cells._markdown(doc)
        assert "deep a" in markdown
        assert "deep b" in markdown
        assert "top c" in markdown


class TestNumberedLabels:
    """Labels Word prints that a Markdown list cannot: ``Article I``, ``1.1``, ``(a)``."""

    _cells = TestTableCellLists
    _LEGAL = (
        '<w:abstractNum w:abstractNumId="98">'
        '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="upperRoman"/><w:lvlText w:val="Article %1"/></w:lvl>'
        '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:isLgl/><w:numFmt w:val="lowerRoman"/>'
        '<w:lvlText w:val="%1.%2"/></w:lvl>'
        "</w:abstractNum>",
        '<w:num w:numId="98"><w:abstractNumId w:val="98"/></w:num>',
    )

    @staticmethod
    def _numbered(doc: docx.document.Document, text: str, style: str, num_id: int, ilvl: int) -> None:
        from docx.oxml.ns import nsdecls

        paragraph = doc.add_paragraph(text, style=style)
        paragraph._p.get_or_add_pPr().insert(
            0, parse_xml(f'<w:numPr {nsdecls("w")}><w:ilvl w:val="{ilvl}"/><w:numId w:val="{num_id}"/></w:numPr>')
        )

    def test_numbered_headings_carry_their_labels(self) -> None:
        """``Article I`` in upper Roman, and a legal ``1.1`` that prints every level in decimal."""
        doc = TestListStartAndRestart._doc(*self._LEGAL)
        self._numbered(doc, "Definitions", "Heading 1", 98, 0)
        self._numbered(doc, "Scope", "Heading 2", 98, 1)
        self._numbered(doc, "Terms", "Heading 2", 98, 1)
        self._numbered(doc, "Payment", "Heading 1", 98, 0)
        self._numbered(doc, "Invoices", "Heading 2", 98, 1)

        markdown = self._cells._markdown(doc)
        assert "# Article I Definitions" in markdown
        assert "## 1.1 Scope" in markdown
        assert "## 1.2 Terms" in markdown
        assert "# Article II Payment" in markdown
        assert "## 2.1 Invoices" in markdown

    def test_lettered_clauses_are_paragraphs_between_plain_list_items(self) -> None:
        """``(a)`` is printed as text; the plain ``1.`` items around it stay a list and keep counting."""
        doc = TestListStartAndRestart._doc()
        self._cells._list_paragraph(doc, "The Supplier shall:")
        self._cells._list_paragraph(doc, "deliver the goods;", ilvl=1)
        self._cells._list_paragraph(doc, "invoice monthly.", ilvl=1)
        self._cells._list_paragraph(doc, "Payment is due in 30 days.")

        children = DocxToAstConverter().convert_to_ast(doc).children
        assert [type(child) for child in children] == [List, Paragraph, Paragraph, List]
        assert children[3].start == 2
        markdown = self._cells._markdown(doc)
        assert "(a) deliver the goods;" in markdown
        assert "(b) invoice monthly." in markdown
        assert "2. Payment is due in 30 days." in markdown

    def test_heading_ends_a_list_open_before_it(self) -> None:
        """A list running up to a heading is emitted ahead of the heading, not after it."""
        doc = docx.Document()
        doc.add_paragraph("item", style="List Number")
        doc.add_heading("After the list", level=1)
        doc.add_paragraph("body")

        children = DocxToAstConverter().convert_to_ast(doc).children
        assert [type(child) for child in children] == [List, Heading, Paragraph]

    @pytest.mark.parametrize(
        ("value", "fmt", "expected"),
        [
            (3, "decimalZero", "03"),
            (12, "decimalZero", "12"),
            (1, "lowerLetter", "a"),
            (27, "lowerLetter", "aa"),
            (28, "upperLetter", "BB"),
            (14, "lowerRoman", "xiv"),
            (1994, "upperRoman", "MCMXCIV"),
            (11, "ordinal", "11th"),
            (22, "ordinal", "22nd"),
            (7, "chineseCounting", "7"),
        ],
    )
    def test_number_formats(self, value: int, fmt: str, expected: str) -> None:
        """Each counter value is written in its level's ``w:numFmt``; an unknown format prints decimal."""
        from all2md.parsers.docx import _format_list_number

        assert _format_list_number(value, fmt) == expected
