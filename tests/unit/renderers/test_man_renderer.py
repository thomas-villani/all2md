#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for the man(7) renderer."""

from io import BytesIO

import pytest

from all2md import to_ast
from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Comment,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    HTMLBlock,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
    MathBlock,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.options.man import ManParserOptions, ManRendererOptions
from all2md.parsers.man import ManParser
from all2md.renderers.man import ManRenderer

pytestmark = pytest.mark.unit


def render(doc: Document, **options: object) -> str:
    return ManRenderer(ManRendererOptions(**options)).render_to_string(doc)  # type: ignore[arg-type]


def render_md(markdown: str, **options: object) -> str:
    return render(to_ast(markdown.encode("utf-8"), source_format="markdown"), **options)


def body(output: str) -> list[str]:
    """The lines after .TH."""
    return output.splitlines()[1:]


def para(*content: object) -> Paragraph:
    return Paragraph(content=[Text(content=c) if isinstance(c, str) else c for c in content])  # type: ignore[misc]


class TestTitle:
    def test_title_heading_with_section(self) -> None:
        doc = Document(children=[Heading(level=1, content=[Text(content="LS(1)")]), para("x")])
        assert render(doc).splitlines()[0] == ".TH LS 1"

    def test_title_heading_is_not_repeated(self) -> None:
        doc = Document(children=[Heading(level=1, content=[Text(content="LS(1)")]), para("x")])
        assert ".SH" not in render(doc)

    def test_title_from_metadata(self) -> None:
        doc = Document(
            children=[para("x")],
            metadata={
                "title": "open(2)",
                "modification_date": "2024-06-15",
                "source": "Linux man-pages 6.9",
                "manual": "System Calls Manual",
            },
        )
        assert render(doc).splitlines()[0] == '.TH open 2 2024-06-15 "Linux man-pages 6.9" "System Calls Manual"'

    def test_options_override_metadata(self) -> None:
        doc = Document(children=[para("x")], metadata={"title": "tool(1)", "modification_date": "2020-01-01"})
        first = render(doc, section="8", date="2026-10-03", manual="Admin").splitlines()[0]
        assert first == '.TH tool 8 2026-10-03 "" Admin'

    def test_title_without_section_defaults_to_1(self) -> None:
        doc = Document(children=[Heading(level=1, content=[Text(content="My Tool")])])
        assert render(doc).splitlines()[0] == '.TH "My Tool" 1'

    def test_section_from_metadata(self) -> None:
        doc = Document(children=[], metadata={"title": "conf", "section": "5"})
        assert render(doc).splitlines()[0] == ".TH conf 5"

    def test_untitled(self) -> None:
        assert render(Document(children=[para("x")])).splitlines()[0] == ".TH UNTITLED 1"

    def test_heading_that_is_not_first_is_not_the_title(self) -> None:
        doc = Document(children=[para("intro"), Heading(level=1, content=[Text(content="Usage")])])
        lines = render(doc).splitlines()
        assert lines[0] == ".TH UNTITLED 1"
        assert ".SH USAGE" in lines


class TestHeadings:
    def test_levels_below_title(self) -> None:
        out = render_md("# X(1)\n\n## Name\n\nx\n\n### Sub\n\ny\n")
        assert body(out) == [".SH NAME", "x", ".SS Sub", "y"]

    def test_shallowest_level_is_section_without_title(self) -> None:
        out = render_md("intro\n\n# One\n\n## Two\n")
        assert ".SH ONE" in out and ".SS Two" in out

    def test_deeper_headings_become_bold_paragraphs(self) -> None:
        out = render_md("# X(1)\n\n## A\n\n### B\n\n#### Deep\n\ntext\n")
        assert body(out) == [".SH A", ".SS B", "\\fBDeep\\fR", ".PP", "text"]

    def test_uppercase_can_be_turned_off(self) -> None:
        out = render_md("# X(1)\n\n## See also\n", uppercase_section_headings=False)
        assert ".SH See also" in out

    def test_uppercase_leaves_font_escapes_alone(self) -> None:
        doc = Document(children=[Heading(level=2, content=[Text(content="the "), Strong(content=[Text(content="x")])])])
        assert ".SH THE \\fBX\\fR" in render(doc)

    def test_quote_in_heading(self) -> None:
        doc = Document(children=[Heading(level=2, content=[Text(content='say "hi"')])])
        assert ".SH SAY \\(dqHI\\(dq" in render(doc)

    def test_no_pp_after_heading(self) -> None:
        out = render_md("## A\n\none\n\ntwo\n")
        assert body(out) == [".SH A", "one", ".PP", "two"]


class TestEscaping:
    def test_backslash(self) -> None:
        assert body(render(Document(children=[para("a\\b")]))) == ["a\\eb"]

    def test_leading_period_and_apostrophe(self) -> None:
        doc = Document(children=[para(".hidden"), para("'quoted")])
        assert body(render(doc)) == ["\\&.hidden", ".PP", "\\&'quoted"]

    def test_leading_period_after_line_break(self) -> None:
        doc = Document(children=[para("a", LineBreak(), ".b")])
        assert body(render(doc)) == ["a", ".br", "\\&.b"]

    def test_option_hyphens_are_minus_signs(self) -> None:
        assert body(render(Document(children=[para("use -l or --all, not x-ray")]))) == [
            "use \\-l or \\-\\-all, not x-ray"
        ]

    def test_non_ascii(self) -> None:
        assert body(render(Document(children=[para("caf\u00e9 \u2014 ok")]))) == ["caf\\[u00E9] \\[u2014] ok"]

    def test_code_escapes(self) -> None:
        doc = Document(children=[para(Code(content="a-b 'c' `d` \\e"))])
        assert body(render(doc)) == ["\\f(CRa\\-b \\(aqc\\(aq \\(gad\\(ga \\ee\\fR"]

    def test_multiline_text_strips_indent_and_blank_lines(self) -> None:
        assert body(render(Document(children=[para("one\n   two\n\n.three")]))) == ["one", "two", "\\&.three"]


class TestInline:
    def test_bold_italic(self) -> None:
        doc = Document(children=[para(Strong(content=[Text(content="b")]), " ", Emphasis(content=[Text(content="i")]))])
        assert body(render(doc)) == ["\\fBb\\fR \\fIi\\fR"]

    def test_nested_fonts_restore_outer(self) -> None:
        inner = Emphasis(content=[Text(content="bi")])
        doc = Document(children=[para(Strong(content=[Text(content="b "), inner, Text(content=" b")]))])
        assert body(render(doc)) == ["\\fBb \\f(BIbi\\fB b\\fR"]

    def test_code_inside_bold(self) -> None:
        doc = Document(children=[para(Strong(content=[Code(content="x")]))])
        assert body(render(doc)) == ["\\fB\\f(CBx\\fB\\fR"]

    def test_underline_is_italic(self) -> None:
        assert body(render(Document(children=[para(Underline(content=[Text(content="u")]))]))) == ["\\fIu\\fR"]

    def test_link(self) -> None:
        link = Link(url="https://example.org", content=[Text(content="site")])
        doc = Document(children=[para("see ", link, ", then")])
        assert body(render(doc)) == ["see", ".UR https://example.org", "site", ".UE ,", "then"]

    def test_autolink_has_no_text(self) -> None:
        link = Link(url="https://example.org", content=[Text(content="https://example.org")])
        assert body(render(Document(children=[para(link)]))) == [".UR https://example.org", ".UE"]

    def test_link_glued_to_text(self) -> None:
        link = Link(url="https://example.org", content=[Text(content="x")])
        assert body(render(Document(children=[para("(", link, ")")]))) == [
            "(\\c",
            ".UR https://example.org",
            "x",
            ".UE )",
        ]

    def test_mail_link(self) -> None:
        link = Link(url="mailto:a@example.org", content=[Text(content="a@example.org")])
        assert body(render(Document(children=[para(link)]))) == [".MT a@example.org", ".ME"]

    def test_link_in_a_tag_line_is_inline(self) -> None:
        term = DefinitionTerm(content=[Link(url="https://e.org", content=[Text(content="e")])])
        doc = Document(children=[DefinitionList(items=[(term, [DefinitionDescription(content=[para("d")])])])])
        assert body(render(doc)) == [".TP", "e <https://e.org>", "d"]

    def test_image_is_alt_text(self) -> None:
        doc = Document(children=[para("a ", Image(url="x.png", alt_text="diagram"), " b")])
        assert body(render(doc)) == ["a diagram b"]

    def test_footnote_reference(self) -> None:
        assert body(render(Document(children=[para("x", FootnoteReference(identifier="1"))]))) == ["x[1]"]


class TestBlocks:
    def test_code_block(self) -> None:
        doc = Document(children=[para("x"), CodeBlock(content="$ ls -l\n.dot\n\nend\n")])
        assert body(render(doc)) == ["x", ".PP", ".EX", "$ ls \\-l", "\\&.dot", "", "end", ".EE"]

    def test_empty_code_block_is_dropped(self) -> None:
        assert body(render(Document(children=[CodeBlock(content="\n")]))) == []

    def test_block_quote(self) -> None:
        doc = Document(children=[para("x"), BlockQuote(children=[para("q")]), para("y")])
        assert body(render(doc)) == ["x", ".RS", ".PP", "q", ".RE", ".PP", "y"]

    def test_bullet_list(self) -> None:
        assert body(render_md("- a\n- b\n")) == [".IP \\(bu 2", "a", ".IP \\(bu 2", "b"]

    def test_ordered_list_start_and_width(self) -> None:
        items = [ListItem(children=[para(str(n))]) for n in range(9, 12)]
        doc = Document(children=[List(ordered=True, start=9, items=items)])
        assert body(render(doc)) == [".IP 9. 5", "9", ".IP 10. 5", "10", ".IP 11. 5", "11"]

    def test_nested_list_and_second_paragraph(self) -> None:
        out = render_md("- a\n\n  more\n\n  - inner\n- b\n")
        assert body(out) == [
            ".IP \\(bu 2",
            "a",
            ".IP",
            "more",
            ".RS",
            ".IP \\(bu 2",
            "inner",
            ".RE",
            ".IP \\(bu 2",
            "b",
        ]

    def test_paragraph_after_list(self) -> None:
        assert body(render_md("- a\n\nafter\n")) == [".IP \\(bu 2", "a", ".PP", "after"]

    def test_task_list(self) -> None:
        item = ListItem(children=[para("done")], task_status="checked")
        assert body(render(Document(children=[List(ordered=False, items=[item])]))) == [".IP \\(bu 2", "[x] done"]

    def test_definition_list(self) -> None:
        out = render_md("-a, --all\n:   show all\n")
        assert body(out) == [".TP", "\\-a, \\-\\-all", "show all"]

    def test_terms_sharing_a_description_use_tq(self) -> None:
        items = [
            (DefinitionTerm(content=[Text(content="-a")]), []),
            (DefinitionTerm(content=[Text(content="--all")]), [DefinitionDescription(content=[para("all")])]),
        ]
        doc = Document(children=[DefinitionList(items=items)])
        assert body(render(doc)) == [".TP", "\\-a", ".TQ", "\\-\\-all", "all"]

    def test_code_in_definition_is_indented(self) -> None:
        description = DefinitionDescription(content=[para("d"), CodeBlock(content="x")])
        doc = Document(children=[DefinitionList(items=[(DefinitionTerm(content=[Text(content="t")]), [description])])])
        assert body(render(doc)) == [".TP", "t", "d", ".RS", ".PP", ".EX", "x", ".EE", ".RE"]

    def test_table(self) -> None:
        out = render_md("| A | B |\n|:--|--:|\n| 1 | 2 |\n")
        assert body(out) == [".TS", "allbox;", "lB rB", "l r.", "A\tB", "1\t2", ".TE"]

    def test_table_without_header(self) -> None:
        doc = Document(children=[Table(rows=[TableRow(cells=[TableCell(content=[Text(content="a")])])])])
        assert body(render(doc)) == [".TS", "allbox;", "l.", "a", ".TE"]

    def test_table_spans(self) -> None:
        header = TableRow(cells=[TableCell(content=[Text(content="wide")], colspan=2)], is_header=True)
        rows = [
            TableRow(
                cells=[TableCell(content=[Text(content="tall")], rowspan=2), TableCell(content=[Text(content="1")])]
            ),
            TableRow(cells=[TableCell(content=[Text(content="2")])]),
        ]
        out = render(Document(children=[Table(header=header, rows=rows)]))
        assert body(out) == [".TS", "allbox;", "lB s", "l l.", "wide", "tall\t1", "\\^\t2", ".TE"]

    def test_table_cell_with_a_link_is_a_text_block(self) -> None:
        out = render_md("| A | B |\n|:--|:--|\n| x | see [docs](https://e.org) now |\n")
        assert body(out)[5:] == ["x\tT{", "see", ".UR https://e.org", "docs", ".UE", "now", "T}", ".TE"]

    def test_text_block_protects_a_closing_marker(self) -> None:
        doc = Document(
            children=[
                Table(
                    header=TableRow(cells=[TableCell(content=[Text(content="h")])], is_header=True),
                    rows=[TableRow(cells=[TableCell(content=[Text(content="a"), LineBreak(), Text(content="T} b")])])],
                )
            ]
        )
        assert body(render(doc))[5:10] == ["T{", "a", ".br", "\\&T} b", "T}"]

    def test_rule_character_cell_mid_row_is_protected(self) -> None:
        out = render_md("| a | b |\n|---|---|\n| x | _ |\n| = | y |\n")
        assert body(out)[5:7] == ["x\t\\&_", "\\&=\ty"]

    def test_table_cells_round_trip(self) -> None:
        markdown = "| Feature | Notes |\n|:--|--:|\n| links | see [docs](https://e.org) now |\n| **b** | x  \ny |\n"
        parsed = ManParser(ManParserOptions(title_heading=False)).parse(render_md(markdown).encode())
        assert parsed.children == to_ast(markdown.encode(), source_format="markdown").children

    def test_table_cell_safety(self) -> None:
        header = TableRow(cells=[TableCell(content=[Text(content=".x\ty")])], is_header=True)
        rows = [TableRow(cells=[TableCell(content=[Text(content="_")])])]
        out = render(Document(children=[Table(header=header, rows=rows)]))
        assert body(out)[4:6] == ["\\&.x y", "\\&_"]

    def test_thematic_break(self) -> None:
        assert body(render(Document(children=[para("a"), ThematicBreak()]))) == ["a", ".PP", "* * *"]

    def test_html_is_dropped(self) -> None:
        assert body(render(Document(children=[HTMLBlock(content="<div>x</div>")]))) == []

    def test_comment(self) -> None:
        assert body(render(Document(children=[Comment(content="note\nmore")]))) == ['.\\" note', '.\\" more']

    def test_footnote_definition(self) -> None:
        doc = Document(children=[FootnoteDefinition(identifier="1", content=[para("note")])])
        assert body(render(doc)) == [".TP", "[1]", "note"]

    def test_math_block(self) -> None:
        assert body(render(Document(children=[MathBlock(content="x^2")]))) == [".EX", "x^2", ".EE"]


class TestRoundTrip:
    PAGE = (
        '.TH LS 1 2024-01-01 "GNU coreutils 9.4" "User Commands"\n'
        ".SH NAME\n"
        "ls \\- list directory contents\n"
        ".SH SYNOPSIS\n"
        ".B ls\n"
        "[\\fIOPTION\\fR]... [\\fIFILE\\fR]...\n"
        ".SH DESCRIPTION\n"
        "List information about the FILEs.\n"
        ".TP\n"
        "\\fB\\-a\\fR, \\fB\\-\\-all\\fR\n"
        "do not ignore entries starting with .\n"
        ".IP \\(bu 2\n"
        "bullet\n"
        ".SS Exit status\n"
        ".EX\n"
        "$ ls \\-l\n"
        ".EE\n"
        "See\n"
        ".UR https://www.gnu.org/software/coreutils/\n"
        "the manual\n"
        ".UE .\n"
    )

    def test_metadata_survives(self) -> None:
        out = ManRenderer().render_to_string(ManParser().parse(self.PAGE.encode()))
        assert out.splitlines()[0] == '.TH LS 1 2024-01-01 "GNU coreutils 9.4" "User Commands"'

    def test_parse_render_parse_is_stable(self) -> None:
        first = ManParser().parse(self.PAGE.encode())
        rendered = ManRenderer().render_to_string(first)
        second = ManParser().parse(rendered.encode())
        assert second.children == first.children
        assert ManRenderer().render_to_string(second) == rendered

    def test_markdown_round_trip(self) -> None:
        markdown = "# X(1)\n\n## NAME\n\nx - do things\n\n## OPTIONS\n\n-v\n: verbose output\n"
        rendered = render_md(markdown)
        parsed = ManParser().parse(rendered.encode())
        assert parsed.children == to_ast(markdown.encode(), source_format="markdown").children

    @pytest.mark.parametrize(
        "markdown",
        [
            "**bold with *italic* inside** and *italic with **bold** inside*.\n",
            "***both***, **bold `code` bold**, *it `c`*.\n",
        ],
    )
    def test_nested_inline_formatting_round_trips(self, markdown: str) -> None:
        parsed = ManParser(ManParserOptions(title_heading=False)).parse(render_md(markdown).encode())
        assert parsed.children == to_ast(markdown.encode(), source_format="markdown").children


class TestOutput:
    def test_render_to_bytes_stream(self) -> None:
        stream = BytesIO()
        ManRenderer().render(Document(children=[para("x")]), stream)
        assert stream.getvalue().decode("utf-8") == ".TH UNTITLED 1\nx\n"

    def test_wrong_options_type(self) -> None:
        from all2md.options.markdown import MarkdownRendererOptions

        with pytest.raises(Exception):
            ManRenderer(MarkdownRendererOptions())  # type: ignore[arg-type]
