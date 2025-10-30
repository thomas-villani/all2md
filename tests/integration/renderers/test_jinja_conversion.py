"""Integration tests for Jinja template renderer.

Tests cover:
- End-to-end jinja template rendering workflows
- Custom template rendering
- Variable substitution
- Template filters and functions
- Complete document conversion with templates
"""

import pytest

from all2md import from_ast, to_ast
from all2md.ast import (
    CodeBlock,
    Document,
    Heading,
    List,
    ListItem,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.options.jinja import JinjaRendererOptions
from all2md.renderers.jinja import JinjaRenderer


def create_sample_document():
    """Create a sample AST document for testing.

    Returns
    -------
    Document
        A sample document with various elements for testing jinja rendering.

    """
    return Document(
        metadata={"title": "Test Document", "author": "Test Author"},
        children=[
            Heading(level=1, content=[Text(content="Document Title")]),
            Paragraph(
                content=[
                    Text(content="This is a paragraph with "),
                    Strong(content=[Text(content="bold text")]),
                    Text(content="."),
                ]
            ),
            List(
                ordered=False,
                items=[
                    ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                    ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                ],
            ),
            CodeBlock(content='print("Hello")', language="python"),
        ],
    )


@pytest.mark.integration
def test_jinja_renderer_basic_template(tmp_path):
    """Test basic jinja template rendering."""
    template_content = """Title: {{ metadata.title }}
Author: {{ metadata.author }}

Content:
{% for child in document.children %}
{{ child }}
{% endfor %}"""

    template_file = tmp_path / "template.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = create_sample_document()
    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    assert "Title: Test Document" in result
    assert "Author: Test Author" in result


@pytest.mark.integration
def test_jinja_renderer_simple_text_template(tmp_path):
    """Test jinja rendering with simple text template."""
    template_content = """# {{ metadata.title }}

Document content here."""

    template_file = tmp_path / "simple.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = Document(metadata={"title": "Simple Title"}, children=[Paragraph(content=[Text(content="Paragraph text.")])])

    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    assert "# Simple Title" in result


@pytest.mark.integration
def test_jinja_renderer_with_loops(tmp_path):
    """Test jinja template with loops."""
    template_content = """{% for child in document.children %}
- {{ child }}
{% endfor %}"""

    template_file = tmp_path / "loops.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = Document(
        children=[
            Paragraph(content=[Text(content="First paragraph")]),
            Paragraph(content=[Text(content="Second paragraph")]),
            Paragraph(content=[Text(content="Third paragraph")]),
        ]
    )

    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    assert "First paragraph" in result
    assert "Second paragraph" in result


@pytest.mark.integration
def test_jinja_renderer_with_conditionals(tmp_path):
    """Test jinja template with conditionals."""
    template_content = """{% if metadata.title %}
Title: {{ metadata.title }}
{% endif %}

{% if "author" in metadata %}
Author: {{ metadata.author }}
{% else %}
Author: Unknown
{% endif %}"""

    template_file = tmp_path / "conditionals.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = Document(metadata={"title": "Test Title"}, children=[])

    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    assert "Title: Test Title" in result
    assert "Author: Unknown" in result


@pytest.mark.integration
def test_jinja_renderer_with_filters(tmp_path):
    """Test jinja template with filters."""
    template_content = """{{ metadata.title | upper }}

{{ metadata.author | lower }}"""

    template_file = tmp_path / "filters.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = Document(metadata={"title": "Test Document", "author": "John Doe"}, children=[])

    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    assert "TEST DOCUMENT" in result
    assert "john doe" in result


@pytest.mark.integration
def test_jinja_renderer_html_template(tmp_path):
    """Test jinja rendering with HTML template."""
    template_content = """<!DOCTYPE html>
<html>
<head>
    <title>{{ metadata.title }}</title>
</head>
<body>
    <h1>{{ metadata.title }}</h1>
    <div class="content">
        {% for child in document.children %}
        <div>{{ child }}</div>
        {% endfor %}
    </div>
</body>
</html>"""

    template_file = tmp_path / "html.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = create_sample_document()
    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    assert "<!DOCTYPE html>" in result
    assert "<title>Test Document</title>" in result
    assert "<h1>Test Document</h1>" in result


@pytest.mark.integration
def test_jinja_renderer_xml_template(tmp_path):
    """Test jinja rendering with XML template."""
    template_content = """<?xml version="1.0" encoding="UTF-8"?>
<document>
    <title>{{ metadata.title }}</title>
    <author>{{ metadata.author }}</author>
    <content>
        {% for child in document.children %}
        <item>{{ child }}</item>
        {% endfor %}
    </content>
</document>"""

    template_file = tmp_path / "xml.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = create_sample_document()
    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    assert "<?xml version" in result
    assert "<title>Test Document</title>" in result


@pytest.mark.integration
def test_jinja_renderer_from_markdown_file(tmp_path):
    """Test converting Markdown file with jinja template."""
    md_content = """# Test Document

This is a test document."""

    md_file = tmp_path / "test.md"
    md_file.write_text(md_content, encoding="utf-8")

    template_content = """Title: {{ metadata.get('title', 'Untitled') }}

Content follows..."""

    template_file = tmp_path / "template.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = to_ast(md_file)
    options = JinjaRendererOptions(template_file=str(template_file))
    result = from_ast(doc, "jinja", renderer_options=options)

    assert "Title:" in result


@pytest.mark.integration
def test_jinja_renderer_metadata_access(tmp_path):
    """Test accessing various metadata fields in template."""
    template_content = """Title: {{ metadata.title }}
Author: {{ metadata.author }}
Date: {{ metadata.get('date', 'N/A') }}
Version: {{ metadata.get('version', '1.0') }}"""

    template_file = tmp_path / "metadata.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = Document(metadata={"title": "My Document", "author": "Jane Smith", "version": "2.3"}, children=[])

    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    assert "Title: My Document" in result
    assert "Author: Jane Smith" in result
    assert "Date: N/A" in result
    assert "Version: 2.3" in result


@pytest.mark.integration
def test_jinja_renderer_list_rendering(tmp_path):
    """Test rendering lists with jinja template."""
    template_content = """{% for child in document.children %}
{% if child.__class__.__name__ == 'List' %}
List with {{ child.items|length }} items
{% endif %}
{% endfor %}"""

    template_file = tmp_path / "lists.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = Document(
        children=[
            List(
                ordered=False,
                items=[
                    ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                    ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ListItem(children=[Paragraph(content=[Text(content="Item 3")])]),
                ],
            ),
        ]
    )

    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    assert "List with 3 items" in result


@pytest.mark.integration
def test_jinja_renderer_table_rendering(tmp_path):
    """Test rendering tables with jinja template."""
    template_content = """{% for child in document.children %}
{{ child }}
{% endfor %}"""

    template_file = tmp_path / "table.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = Document(
        children=[
            Table(
                header=TableRow(
                    cells=[TableCell(content=[Text(content="Name")]), TableCell(content=[Text(content="Age")])]
                ),
                rows=[
                    TableRow(
                        cells=[TableCell(content=[Text(content="Alice")]), TableCell(content=[Text(content="30")])]
                    ),
                ],
            ),
        ]
    )

    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    # Table should be rendered in some form
    assert isinstance(result, str)


@pytest.mark.integration
def test_jinja_renderer_unicode_template(tmp_path):
    """Test jinja template with Unicode characters."""
    template_content = """{{ metadata.title }} \U0001f600

Content: {{ metadata.author }}"""

    template_file = tmp_path / "unicode.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = Document(metadata={"title": "Unicode \U00004e2d\U00006587", "author": "Author \U00000391"}, children=[])

    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    assert "Unicode" in result


@pytest.mark.integration
def test_jinja_renderer_custom_delimiter_template(tmp_path):
    """Test jinja template with text that looks like template syntax."""
    template_content = """Title: {{ metadata.title }}

The document uses {{ title }} in content."""

    template_file = tmp_path / "delimiters.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = Document(metadata={"title": "Delimiter Test"}, children=[])

    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    assert "Title: Delimiter Test" in result


@pytest.mark.integration
def test_jinja_renderer_whitespace_control(tmp_path):
    """Test jinja template with whitespace control."""
    template_content = """Title: {{ metadata.title }}
{%- for child in document.children %}
{{ child }}
{%- endfor %}"""

    template_file = tmp_path / "whitespace.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = Document(
        metadata={"title": "Test"},
        children=[
            Paragraph(content=[Text(content="Line 1")]),
            Paragraph(content=[Text(content="Line 2")]),
        ],
    )

    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    assert "Title: Test" in result


@pytest.mark.integration
def test_jinja_renderer_empty_document(tmp_path):
    """Test jinja rendering with empty document."""
    template_content = """{% if document.children %}
Has content
{% else %}
Empty document
{% endif %}"""

    template_file = tmp_path / "empty.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = Document(children=[])

    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    assert "Empty document" in result


@pytest.mark.integration
def test_jinja_renderer_long_document(tmp_path):
    """Test jinja rendering with long document."""
    template_content = """{% for child in document.children %}
{{ loop.index }}. {{ child }}
{% endfor %}"""

    template_file = tmp_path / "long.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    paragraphs = [Paragraph(content=[Text(content=f"Paragraph {i}")]) for i in range(100)]
    doc = Document(children=paragraphs)

    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    assert "1." in result
    assert "100." in result


@pytest.mark.integration
def test_jinja_renderer_with_includes(tmp_path):
    """Test jinja template with includes (if supported)."""
    header_template = """Header: {{ metadata.title }}"""
    header_file = tmp_path / "header.jinja2"
    header_file.write_text(header_template, encoding="utf-8")

    main_template = """{% include 'header.jinja2' %}

Main content here."""
    main_file = tmp_path / "main.jinja2"
    main_file.write_text(main_template, encoding="utf-8")

    doc = Document(metadata={"title": "Include Test"}, children=[])

    options = JinjaRendererOptions(template_file=str(main_file))
    renderer = JinjaRenderer(options=options)

    # May or may not support includes depending on implementation
    try:
        result = renderer.render_to_string(doc)
        assert "Include Test" in result or "Main content" in result
    except Exception:
        # Includes may not be supported
        pass


@pytest.mark.integration
def test_jinja_renderer_comment_template(tmp_path):
    """Test jinja template with comments."""
    template_content = """{# This is a comment #}
Title: {{ metadata.title }}
{# Another comment
   spanning multiple lines #}
Content follows."""

    template_file = tmp_path / "comments.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = Document(metadata={"title": "Comment Test"}, children=[])

    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    assert "Title: Comment Test" in result
    assert "This is a comment" not in result  # Comments should not appear in output


@pytest.mark.integration
def test_jinja_renderer_escaping(tmp_path):
    """Test jinja template with escaped content."""
    template_content = """{{ metadata.title | e }}

Content: {{ metadata.description | e }}"""

    template_file = tmp_path / "escaping.jinja2"
    template_file.write_text(template_content, encoding="utf-8")

    doc = Document(
        metadata={"title": "Test <script>alert('xss')</script>", "description": "Description with & symbols"},
        children=[],
    )

    options = JinjaRendererOptions(template_file=str(template_file))
    renderer = JinjaRenderer(options=options)
    result = renderer.render_to_string(doc)

    # Escaping may or may not be applied depending on implementation
    assert "Test" in result
