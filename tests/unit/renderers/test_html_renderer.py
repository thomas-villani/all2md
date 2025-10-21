#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_html_renderer.py
"""Unit tests for HtmlRenderer.

Tests cover:
- Rendering all node types to HTML
- Standalone vs fragment modes
- CSS styling options
- Table of contents generation
- Math rendering options
- Edge cases and nested structures

"""

from io import BytesIO

import pytest

from all2md.ast import (
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
from all2md.options import HtmlRendererOptions
from all2md.renderers.html import HtmlRenderer


@pytest.mark.unit
class TestBasicRendering:
    """Tests for basic HTML rendering."""

    def test_render_empty_document(self):
        """Test rendering an empty document."""
        doc = Document()
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert result == ""

    def test_render_text_only(self):
        """Test rendering plain text."""
        doc = Document(children=[Paragraph(content=[Text(content="Hello world")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<p>Hello world</p>" in result

    def test_render_multiple_paragraphs(self):
        """Test rendering multiple paragraphs."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="First paragraph")]),
                Paragraph(content=[Text(content="Second paragraph")]),
            ]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<p>First paragraph</p>" in result
        assert "<p>Second paragraph</p>" in result

    def test_render_standalone_document(self):
        """Test rendering standalone HTML document."""
        doc = Document(children=[Paragraph(content=[Text(content="Content")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=True))
        result = renderer.render_to_string(doc)
        assert "<!DOCTYPE html>" in result
        assert "<html" in result
        assert "<head>" in result
        assert "<body>" in result
        assert "</html>" in result


@pytest.mark.unit
class TestHeadingRendering:
    """Tests for heading rendering."""

    def test_heading_level_1(self):
        """Test rendering h1."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert '<h1 id="heading-0">Title</h1>' in result

    def test_heading_level_2(self):
        """Test rendering h2."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Subtitle")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert '<h2 id="heading-0">Subtitle</h2>' in result

    def test_heading_level_6(self):
        """Test rendering h6."""
        doc = Document(children=[Heading(level=6, content=[Text(content="Small heading")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert '<h6 id="heading-0">Small heading</h6>' in result

    def test_heading_with_formatting(self):
        """Test heading with inline formatting."""
        doc = Document(
            children=[Heading(level=1, content=[Text(content="Bold "), Strong(content=[Text(content="title")])])]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "Bold <strong>title</strong>" in result


@pytest.mark.unit
class TestInlineFormatting:
    """Tests for inline formatting."""

    def test_strong(self):
        """Test bold text rendering."""
        doc = Document(children=[Paragraph(content=[Strong(content=[Text(content="bold")])])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<strong>bold</strong>" in result

    def test_emphasis(self):
        """Test italic text rendering."""
        doc = Document(children=[Paragraph(content=[Emphasis(content=[Text(content="italic")])])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<em>italic</em>" in result

    def test_code(self):
        """Test inline code rendering."""
        doc = Document(children=[Paragraph(content=[Code(content="code")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<code>code</code>" in result

    def test_strikethrough(self):
        """Test strikethrough rendering."""
        doc = Document(children=[Paragraph(content=[Strikethrough(content=[Text(content="deleted")])])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<del>deleted</del>" in result

    def test_underline(self):
        """Test underline rendering."""
        doc = Document(children=[Paragraph(content=[Underline(content=[Text(content="underlined")])])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<u>underlined</u>" in result

    def test_superscript(self):
        """Test superscript rendering."""
        doc = Document(children=[Paragraph(content=[Superscript(content=[Text(content="2")])])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<sup>2</sup>" in result

    def test_subscript(self):
        """Test subscript rendering."""
        doc = Document(children=[Paragraph(content=[Subscript(content=[Text(content="2")])])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<sub>2</sub>" in result

    def test_nested_formatting(self):
        """Test nested inline formatting."""
        doc = Document(
            children=[Paragraph(content=[Strong(content=[Emphasis(content=[Text(content="bold italic")])])])]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<strong><em>bold italic</em></strong>" in result


@pytest.mark.unit
class TestLinkAndImageRendering:
    """Tests for link and image rendering."""

    def test_simple_link(self):
        """Test basic link rendering."""
        doc = Document(
            children=[Paragraph(content=[Link(url="https://example.com", content=[Text(content="Example")])])]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert '<a href="https://example.com">Example</a>' in result

    def test_link_with_title(self):
        """Test link with title attribute."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Link(url="https://example.com", title="Example Site", content=[Text(content="Example")])]
                )
            ]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert 'title="Example Site"' in result

    def test_image(self):
        """Test image rendering."""
        doc = Document(children=[Paragraph(content=[Image(url="image.png", alt_text="Description")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert '<img src="image.png" alt="Description">' in result

    def test_image_with_dimensions(self):
        """Test image with width and height."""
        doc = Document(
            children=[Paragraph(content=[Image(url="image.png", alt_text="Description", width=100, height=200)])]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert 'width="100"' in result
        assert 'height="200"' in result


@pytest.mark.unit
class TestListRendering:
    """Tests for list rendering."""

    def test_unordered_list(self):
        """Test unordered list rendering."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                )
            ]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<ul>" in result
        assert "<li>" in result
        assert "Item 1" in result
        assert "Item 2" in result
        assert "</ul>" in result

    def test_ordered_list(self):
        """Test ordered list rendering."""
        doc = Document(
            children=[
                List(
                    ordered=True,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="First")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Second")])]),
                    ],
                )
            ]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<ol>" in result
        assert "<li>" in result
        assert "</ol>" in result

    def test_ordered_list_with_start(self):
        """Test ordered list with custom start number."""
        doc = Document(
            children=[
                List(
                    ordered=True,
                    start=5,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Five")])]),
                    ],
                )
            ]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert 'start="5"' in result

    def test_task_list(self):
        """Test task list rendering."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(task_status="checked", children=[Paragraph(content=[Text(content="Done")])]),
                        ListItem(task_status="unchecked", children=[Paragraph(content=[Text(content="Todo")])]),
                    ],
                )
            ]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert '<input type="checkbox" checked disabled>' in result
        assert '<input type="checkbox" disabled>' in result


@pytest.mark.unit
class TestTableRendering:
    """Tests for table rendering."""

    def test_simple_table(self):
        """Test basic table rendering."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[TableCell(content=[Text(content="Name")]), TableCell(content=[Text(content="Age")])]
                    ),
                    rows=[
                        TableRow(
                            cells=[TableCell(content=[Text(content="Alice")]), TableCell(content=[Text(content="30")])]
                        )
                    ],
                )
            ]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<table>" in result
        assert "<thead>" in result
        assert "<th>Name</th>" in result
        assert "<tbody>" in result
        assert "<td>Alice</td>" in result
        assert "</table>" in result

    def test_table_with_alignment(self):
        """Test table with column alignment."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[TableCell(content=[Text(content="Left")]), TableCell(content=[Text(content="Right")])]
                    ),
                    alignments=["left", "right"],
                    rows=[
                        TableRow(cells=[TableCell(content=[Text(content="A")]), TableCell(content=[Text(content="B")])])
                    ],
                )
            ]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert 'style="text-align: left"' in result
        assert 'style="text-align: right"' in result

    def test_table_with_caption(self):
        """Test table with caption."""
        doc = Document(
            children=[
                Table(caption="Data Table", header=TableRow(cells=[TableCell(content=[Text(content="Col")])]), rows=[])
            ]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<caption>Data Table</caption>" in result


@pytest.mark.unit
class TestBlockElements:
    """Tests for block-level elements."""

    def test_code_block(self):
        """Test code block rendering."""
        doc = Document(children=[CodeBlock(content="def hello():\n    print('world')", language="python")])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False, syntax_highlighting=True))
        result = renderer.render_to_string(doc)
        assert "<pre><code" in result
        assert 'class="language-python"' in result
        assert "def hello()" in result

    def test_code_block_no_language(self):
        """Test code block without language."""
        doc = Document(children=[CodeBlock(content="plain code")])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<pre><code>" in result

    def test_blockquote(self):
        """Test blockquote rendering."""
        doc = Document(children=[BlockQuote(children=[Paragraph(content=[Text(content="Quoted text")])])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<blockquote>" in result
        assert "Quoted text" in result
        assert "</blockquote>" in result

    def test_thematic_break(self):
        """Test horizontal rule rendering."""
        doc = Document(children=[ThematicBreak()])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<hr>" in result

    def test_html_block(self):
        """Test HTML block passthrough."""
        doc = Document(children=[HTMLBlock(content="<div>Custom HTML</div>")])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False, html_passthrough_mode="pass-through"))
        result = renderer.render_to_string(doc)
        assert "<div>Custom HTML</div>" in result


@pytest.mark.unit
class TestMathRendering:
    """Tests for math rendering."""

    def test_inline_math_mathjax(self):
        """Test inline math with MathJax."""
        doc = Document(children=[Paragraph(content=[MathInline(content="x^2", notation="latex")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False, math_renderer="mathjax"))
        result = renderer.render_to_string(doc)
        assert '<span class="math math-inline" data-notation="latex">$x^2$</span>' in result

    def test_block_math_mathjax(self):
        """Test block math with MathJax."""
        doc = Document(children=[MathBlock(content="E = mc^2", notation="latex")])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False, math_renderer="mathjax"))
        result = renderer.render_to_string(doc)
        assert '<div class="math math-block" data-notation="latex">' in result
        assert "E = mc^2" in result

    def test_math_none_mode(self):
        """Test math rendering with none mode."""
        doc = Document(children=[Paragraph(content=[MathInline(content="x^2", notation="latex")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False, math_renderer="none"))
        result = renderer.render_to_string(doc)
        assert '<span class="math math-inline" data-notation="latex">$x^2$</span>' in result


@pytest.mark.unit
class TestFootnotes:
    """Tests for footnote rendering."""

    def test_footnote_reference(self):
        """Test footnote reference rendering."""
        doc = Document(children=[Paragraph(content=[Text(content="Text"), FootnoteReference(identifier="1")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert '<sup id="fnref-1">' in result
        assert '<a href="#fn-1">[1]</a>' in result

    def test_footnote_definition_in_standalone(self):
        """Test footnote definition in standalone mode."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Text"), FootnoteReference(identifier="1")]),
                FootnoteDefinition(identifier="1", content=[Text(content="Footnote text")]),
            ]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=True))
        result = renderer.render_to_string(doc)
        assert '<section id="footnotes">' in result
        assert '<li id="fn-1">' in result
        assert "Footnote text" in result


@pytest.mark.unit
class TestDefinitionLists:
    """Tests for definition list rendering."""

    def test_definition_list(self):
        """Test definition list rendering."""
        doc = Document(
            children=[
                DefinitionList(
                    items=[
                        (
                            DefinitionTerm(content=[Text(content="Term")]),
                            [DefinitionDescription(content=[Text(content="Description")])],
                        )
                    ]
                )
            ]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "<dl>" in result
        assert "<dt>Term</dt>" in result
        assert "<dd>" in result
        assert "Description" in result
        assert "</dl>" in result


@pytest.mark.unit
class TestHtmlEscaping:
    """Tests for HTML escaping."""

    def test_escape_special_characters(self):
        """Test HTML special character escaping."""
        doc = Document(children=[Paragraph(content=[Text(content="<script>alert('xss')</script>")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False, escape_html=True))
        result = renderer.render_to_string(doc)
        assert "&lt;script&gt;" in result
        assert "<script>" not in result

    def test_no_escape_when_disabled(self):
        """Test no escaping when disabled."""
        doc = Document(children=[Paragraph(content=[Text(content="<b>bold</b>")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False, escape_html=False))
        result = renderer.render_to_string(doc)
        assert "<b>bold</b>" in result


@pytest.mark.unit
class TestTableOfContents:
    """Tests for table of contents generation."""

    def test_toc_generation(self):
        """Test TOC is generated when enabled."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter 1")]),
                Paragraph(content=[Text(content="Content")]),
                Heading(level=2, content=[Text(content="Section 1.1")]),
            ]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=True, include_toc=True))
        result = renderer.render_to_string(doc)
        assert '<nav id="table-of-contents">' in result
        assert "Table of Contents" in result
        assert "Chapter 1" in result
        assert "Section 1.1" in result

    def test_no_toc_when_disabled(self):
        """Test no TOC when disabled."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=True, include_toc=False))
        result = renderer.render_to_string(doc)
        assert '<nav id="table-of-contents">' not in result


@pytest.mark.unit
class TestCssStyling:
    """Tests for CSS styling options."""

    def test_embedded_css(self):
        """Test embedded CSS in standalone mode."""
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=True, css_style="embedded"))
        result = renderer.render_to_string(doc)
        assert "<style>" in result
        assert "</style>" in result
        assert "font-family" in result

    def test_external_css(self):
        """Test external CSS reference."""
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=True, css_style="external", css_file="styles.css"))
        result = renderer.render_to_string(doc)
        assert '<link rel="stylesheet" href="styles.css">' in result
        assert "<style>" not in result

    def test_no_css(self):
        """Test no CSS when set to none."""
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=True, css_style="none"))
        result = renderer.render_to_string(doc)
        assert "<style>" not in result
        assert '<link rel="stylesheet"' not in result


@pytest.mark.unit
class TestLineBreaks:
    """Tests for line break rendering."""

    def test_hard_line_break(self):
        """Test hard line break rendering."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Line 1"), LineBreak(soft=False), Text(content="Line 2")])]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "Line 1<br>" in result
        assert "Line 2" in result

    def test_soft_line_break(self):
        """Test soft line break renders as space."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Line 1"), LineBreak(soft=True), Text(content="Line 2")])]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        # Soft breaks should render as space in HTML
        assert "Line 1 Line 2" in result


@pytest.mark.unit
class TestOutputMethods:
    """Tests for different output methods."""

    def test_render_to_file_path(self, tmp_path):
        """Test rendering to file path."""
        doc = Document(children=[Paragraph(content=[Text(content="Test content")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        output_file = tmp_path / "output.html"
        renderer.render(doc, output_file)

        assert output_file.exists()
        content = output_file.read_text()
        assert "Test content" in content

    def test_render_to_string_io(self):
        """Test rendering to StringIO."""
        doc = Document(children=[Paragraph(content=[Text(content="Test content")])])
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        output = BytesIO()
        renderer.render(doc, output)

        result = output.getvalue()
        assert b"Test content" in result


@pytest.mark.unit
class TestSecurityFeatures:
    """Tests for HTML renderer security features."""

    def test_allow_remote_scripts_default_false(self):
        """Test that allow_remote_scripts defaults to False (secure-by-default)."""
        options = HtmlRendererOptions(standalone=True)
        assert options.allow_remote_scripts is False

    def test_csp_enabled_default_false(self):
        """Test that csp_enabled defaults to False."""
        options = HtmlRendererOptions(standalone=True)
        assert options.csp_enabled is False

    def test_remote_scripts_disabled_no_mathjax_script(self):
        """Test that MathJax script is NOT included when allow_remote_scripts=False."""
        doc = Document(children=[Paragraph(content=[MathInline(content="x^2", notation="latex")])])
        options = HtmlRendererOptions(standalone=True, math_renderer="mathjax", allow_remote_scripts=False)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)
        # MathJax CDN script should NOT be included
        assert "cdn.jsdelivr.net/npm/mathjax" not in result
        assert "mathjax" not in result.lower() or "data-notation" in result

    def test_remote_scripts_enabled_includes_mathjax_script(self):
        """Test that MathJax script IS included when allow_remote_scripts=True."""
        doc = Document(children=[Paragraph(content=[MathInline(content="x^2", notation="latex")])])
        options = HtmlRendererOptions(standalone=True, math_renderer="mathjax", allow_remote_scripts=True)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)
        # MathJax CDN script SHOULD be included
        assert "cdn.jsdelivr.net/npm/mathjax" in result or "mathjax" in result.lower()

    def test_remote_scripts_disabled_no_katex_script(self):
        """Test that KaTeX script is NOT included when allow_remote_scripts=False."""
        doc = Document(children=[Paragraph(content=[MathInline(content="x^2", notation="latex")])])
        options = HtmlRendererOptions(standalone=True, math_renderer="katex", allow_remote_scripts=False)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)
        # KaTeX CDN script should NOT be included
        assert "cdn.jsdelivr.net/npm/katex" not in result
        assert "katex" not in result.lower() or "data-notation" in result

    def test_remote_scripts_enabled_includes_katex_script(self):
        """Test that KaTeX script IS included when allow_remote_scripts=True."""
        doc = Document(children=[Paragraph(content=[MathInline(content="x^2", notation="latex")])])
        options = HtmlRendererOptions(standalone=True, math_renderer="katex", allow_remote_scripts=True)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)
        # KaTeX CDN script SHOULD be included
        assert "cdn.jsdelivr.net/npm/katex" in result or "katex" in result.lower()

    def test_math_renderer_none_no_warning(self):
        """Test that math_renderer='none' doesn't trigger warning."""
        doc = Document(children=[Paragraph(content=[MathInline(content="x^2", notation="latex")])])
        options = HtmlRendererOptions(standalone=True, math_renderer="none", allow_remote_scripts=False)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)
        # Should render without requiring remote scripts
        assert "x^2" in result

    def test_csp_meta_tag_when_enabled(self):
        """Test that CSP meta tag is included when csp_enabled=True."""
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        options = HtmlRendererOptions(standalone=True, csp_enabled=True)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)
        # Should include CSP meta tag
        assert "Content-Security-Policy" in result
        assert '<meta http-equiv="Content-Security-Policy"' in result

    def test_csp_meta_tag_not_included_when_disabled(self):
        """Test that CSP meta tag is NOT included when csp_enabled=False."""
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        options = HtmlRendererOptions(standalone=True, csp_enabled=False)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)
        # Should NOT include CSP meta tag
        assert "Content-Security-Policy" not in result

    def test_csp_meta_tag_only_in_standalone_mode(self):
        """Test that CSP meta tag is only included in standalone mode."""
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        options = HtmlRendererOptions(standalone=False, csp_enabled=True)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)
        # Should NOT include CSP meta tag in fragment mode
        assert "Content-Security-Policy" not in result
        assert "<head>" not in result

    def test_csp_default_policy(self):
        """Test that default CSP policy is secure."""
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        options = HtmlRendererOptions(standalone=True, csp_enabled=True)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)
        # Should include default secure policy (quotes are HTML-escaped)
        assert "default-src &#x27;self&#x27;" in result or "default-src 'self'" in result
        assert "script-src &#x27;self&#x27;" in result or "script-src 'self'" in result
        assert (
            "style-src &#x27;self&#x27; &#x27;unsafe-inline&#x27;" in result
            or "style-src 'self' 'unsafe-inline'" in result
        )

    def test_csp_custom_policy(self):
        """Test that custom CSP policy is used when specified."""
        custom_policy = "default-src 'none'; script-src 'self' https://trusted.cdn.com;"
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        options = HtmlRendererOptions(standalone=True, csp_enabled=True, csp_policy=custom_policy)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)
        # Should include custom policy (quotes are HTML-escaped)
        assert "default-src &#x27;none&#x27;" in result or "default-src 'none'" in result
        assert "https://trusted.cdn.com" in result

    def test_csp_policy_properly_escaped(self):
        """Test that CSP policy is properly HTML-escaped."""
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        options = HtmlRendererOptions(standalone=True, csp_enabled=True, escape_html=True)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)
        # CSP meta tag should be present and properly formatted
        assert '<meta http-equiv="Content-Security-Policy"' in result
        # Should not have unescaped quotes in attribute
        assert 'content="' in result

    def test_combined_security_features(self):
        """Test that multiple security features work together."""
        doc = Document(children=[Paragraph(content=[Text(content="Secure content")])])
        options = HtmlRendererOptions(
            standalone=True, allow_remote_scripts=False, csp_enabled=True, escape_html=True, math_renderer="mathjax"
        )
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)
        # Should include CSP
        assert "Content-Security-Policy" in result
        # Should NOT include remote scripts
        assert "cdn.jsdelivr.net" not in result
        # Should be valid HTML
        assert "<!DOCTYPE html>" in result
        assert "<html" in result
