#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for HTML template functionality.

Tests cover:
- Replace template mode
- Inject template mode
- Jinja template mode
- CSS class mapping
- Template validation

"""

import pytest

from all2md.ast import (
    CodeBlock,
    Document,
    Heading,
    Paragraph,
    Text,
)
from all2md.options import HtmlRendererOptions
from all2md.renderers.html import HtmlRenderer


@pytest.mark.unit
class TestReplaceTemplateMode:
    """Tests for replace template mode."""

    def test_basic_replacement(self, tmp_path):
        """Test basic content placeholder replacement."""
        # Create template file
        template = tmp_path / "template.html"
        template.write_text("<!DOCTYPE html><html><body>{CONTENT}</body></html>", encoding="utf-8")

        # Create document
        doc = Document(children=[Paragraph(content=[Text(content="Hello World")])])

        # Render with replace mode
        options = HtmlRendererOptions(template_mode="replace", template_file=str(template))
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "<!DOCTYPE html>" in result
        assert "<p>Hello World</p>" in result
        assert "{CONTENT}" not in result

    def test_multiple_placeholders(self, tmp_path):
        """Test replacing multiple placeholders."""
        # Create template file
        template = tmp_path / "template.html"
        template.write_text(
            "<!DOCTYPE html><html><head><title>{TITLE}</title></head>"
            "<body><h1>{TITLE}</h1><p>By {AUTHOR}</p>{CONTENT}</body></html>",
            encoding="utf-8",
        )

        # Create document with metadata
        doc = Document(
            metadata={"title": "My Article", "author": "John Doe"},
            children=[Paragraph(content=[Text(content="Content here")])],
        )

        # Render
        options = HtmlRendererOptions(template_mode="replace", template_file=str(template))
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "<title>My Article</title>" in result
        assert "<h1>My Article</h1>" in result
        assert "<p>By John Doe</p>" in result
        assert "<p>Content here</p>" in result

    def test_custom_placeholder(self, tmp_path):
        """Test custom content placeholder."""
        template = tmp_path / "template.html"
        template.write_text("<html><body>{{MAIN_CONTENT}}</body></html>", encoding="utf-8")

        doc = Document(children=[Paragraph(content=[Text(content="Test")])])

        options = HtmlRendererOptions(
            template_mode="replace", template_file=str(template), content_placeholder="{{MAIN_CONTENT}}"
        )
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "<p>Test</p>" in result
        assert "{{MAIN_CONTENT}}" not in result

    def test_toc_placeholder(self, tmp_path):
        """Test TOC placeholder replacement."""
        template = tmp_path / "template.html"
        template.write_text("<html><body><nav>{TOC}</nav>{CONTENT}</body></html>", encoding="utf-8")

        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter 1")]),
                Paragraph(content=[Text(content="Content")]),
            ]
        )

        options = HtmlRendererOptions(template_mode="replace", template_file=str(template), include_toc=True)
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert '<nav id="table-of-contents">' in result
        assert "<ul>" in result
        assert "Chapter 1" in result
        assert "{TOC}" not in result


@pytest.mark.unit
class TestInjectTemplateMode:
    """Tests for inject template mode."""

    def test_inject_replace(self, tmp_path):
        """Test injecting with replace mode."""
        template = tmp_path / "layout.html"
        template.write_text("<html><body><div id='content'><p>Old content</p></div></body></html>", encoding="utf-8")

        doc = Document(children=[Paragraph(content=[Text(content="New content")])])

        options = HtmlRendererOptions(
            template_mode="inject", template_file=str(template), template_selector="#content", injection_mode="replace"
        )
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert '<div id="content">' in result
        assert "<p>New content</p>" in result
        assert "Old content" not in result

    def test_inject_append(self, tmp_path):
        """Test injecting with append mode."""
        template = tmp_path / "layout.html"
        template.write_text("<html><body><div id='main'><p>Existing</p></div></body></html>", encoding="utf-8")

        doc = Document(children=[Paragraph(content=[Text(content="Appended")])])

        options = HtmlRendererOptions(
            template_mode="inject", template_file=str(template), template_selector="#main", injection_mode="append"
        )
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "<p>Existing</p>" in result
        assert "<p>Appended</p>" in result
        # Existing should come before Appended
        assert result.index("Existing") < result.index("Appended")

    def test_inject_prepend(self, tmp_path):
        """Test injecting with prepend mode."""
        template = tmp_path / "layout.html"
        template.write_text("<html><body><div class='container'><p>Last</p></div></body></html>", encoding="utf-8")

        doc = Document(children=[Paragraph(content=[Text(content="First")])])

        options = HtmlRendererOptions(
            template_mode="inject",
            template_file=str(template),
            template_selector=".container",
            injection_mode="prepend",
        )
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "<p>First</p>" in result
        assert "<p>Last</p>" in result
        # First should come before Last
        assert result.index("First") < result.index("Last")

    def test_inject_selector_not_found(self, tmp_path):
        """Test error when selector not found."""
        template = tmp_path / "layout.html"
        template.write_text("<html><body><div id='content'></div></body></html>", encoding="utf-8")

        doc = Document(children=[Paragraph(content=[Text(content="Content")])])

        options = HtmlRendererOptions(
            template_mode="inject", template_file=str(template), template_selector="#nonexistent"
        )
        renderer = HtmlRenderer(options)

        with pytest.raises(ValueError, match="Selector '#nonexistent' not found"):
            renderer.render_to_string(doc)


@pytest.mark.unit
class TestJinjaTemplateMode:
    """Tests for Jinja template mode."""

    def test_jinja_basic(self, tmp_path):
        """Test basic Jinja template rendering."""
        pytest.importorskip("jinja2")

        template = tmp_path / "template.html"
        template.write_text("<html><body><h1>{{ title }}</h1>{{ content }}</body></html>", encoding="utf-8")

        doc = Document(metadata={"title": "Test Page"}, children=[Paragraph(content=[Text(content="Content")])])

        options = HtmlRendererOptions(template_mode="jinja", template_file=str(template))
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "<h1>Test Page</h1>" in result
        assert "<p>Content</p>" in result

    def test_jinja_with_headings(self, tmp_path):
        """Test Jinja template with headings context."""
        pytest.importorskip("jinja2")

        template = tmp_path / "template.html"
        template.write_text(
            "<html><body>"
            "{% for h in headings %}<p>Level {{ h.level }}: {{ h.text }}</p>{% endfor %}"
            "{{ content }}</body></html>",
            encoding="utf-8",
        )

        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter 1")]),
                Heading(level=2, content=[Text(content="Section 1.1")]),
            ]
        )

        options = HtmlRendererOptions(template_mode="jinja", template_file=str(template))
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "Level 1: Chapter 1" in result
        assert "Level 2: Section 1.1" in result

    def test_jinja_with_metadata(self, tmp_path):
        """Test Jinja template with custom metadata."""
        pytest.importorskip("jinja2")

        template = tmp_path / "template.html"
        template.write_text(
            "<html><head><meta name='author' content='{{ metadata.author }}'></head>"
            "<body>{{ content }}</body></html>",
            encoding="utf-8",
        )

        doc = Document(
            metadata={"author": "Jane Smith", "custom": "value"}, children=[Paragraph(content=[Text(content="Text")])]
        )

        options = HtmlRendererOptions(template_mode="jinja", template_file=str(template))
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert "content='Jane Smith'" in result or 'content="Jane Smith"' in result


@pytest.mark.unit
class TestCssClassMapping:
    """Tests for CSS class mapping."""

    def test_heading_custom_class(self):
        """Test custom CSS class on headings."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])

        options = HtmlRendererOptions(standalone=False, css_class_map={"Heading": "custom-heading"})
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert 'class="custom-heading"' in result

    def test_paragraph_multiple_classes(self):
        """Test multiple CSS classes on paragraph."""
        doc = Document(children=[Paragraph(content=[Text(content="Text")])])

        options = HtmlRendererOptions(standalone=False, css_class_map={"Paragraph": ["prose", "text-lg"]})
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert 'class="prose text-lg"' in result

    def test_code_block_with_language_and_custom_class(self):
        """Test code block with both language class and custom class."""
        doc = Document(children=[CodeBlock(content="print('hello')", language="python")])

        options = HtmlRendererOptions(
            standalone=False, syntax_highlighting=True, css_class_map={"CodeBlock": "code-snippet"}
        )
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        # Should have both language class and custom class
        assert 'class="language-python code-snippet"' in result

    def test_table_custom_class(self):
        """Test custom CSS class on table."""
        from all2md.ast import Table, TableCell, TableRow

        doc = Document(children=[Table(header=TableRow(cells=[TableCell(content=[Text(content="Header")])]), rows=[])])

        options = HtmlRendererOptions(standalone=False, css_class_map={"Table": "data-table"})
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert '<table class="data-table">' in result

    def test_blockquote_custom_class(self):
        """Test custom CSS class on blockquote."""
        from all2md.ast import BlockQuote

        doc = Document(children=[BlockQuote(children=[Paragraph(content=[Text(content="Quote")])])])

        options = HtmlRendererOptions(standalone=False, css_class_map={"BlockQuote": "quote"})
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        assert '<blockquote class="quote">' in result


@pytest.mark.unit
class TestTemplateValidation:
    """Tests for template validation and error handling."""

    def test_template_mode_requires_file(self):
        """Test that template_mode requires template_file."""
        with pytest.raises(ValueError, match="template_mode='replace' requires template_file to be set"):
            HtmlRendererOptions(template_mode="replace", template_file=None)  # Missing template file

    def test_standalone_ignored_with_template_mode(self, tmp_path):
        """Test that standalone is ignored when template_mode is set."""
        template = tmp_path / "template.html"
        template.write_text("<html>{CONTENT}</html>", encoding="utf-8")

        doc = Document(children=[Paragraph(content=[Text(content="Content")])])

        options = HtmlRendererOptions(
            standalone=True,
            template_mode="replace",
            template_file=str(template),  # Should be ignored
        )
        renderer = HtmlRenderer(options)
        result = renderer.render_to_string(doc)

        # Should use template, not standalone wrapping
        assert result.count("<html>") == 1  # Only from template
        assert "<!DOCTYPE html>" not in result  # Not from standalone mode
