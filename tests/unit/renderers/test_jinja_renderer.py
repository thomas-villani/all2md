#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for Jinja2 template-based renderer."""

from __future__ import annotations

import pytest

from all2md.ast import Document, Heading, Image, Link, Paragraph, Text
from all2md.options.jinja import JinjaRendererOptions
from all2md.renderers.jinja import (
    JinjaRenderer,
    escape_html,
    escape_latex,
    escape_markdown,
    escape_xml,
    escape_yaml,
    get_all_headings,
    get_all_images,
    get_all_links,
)


class TestJinjaRendererOptions:
    """Test JinjaRendererOptions validation."""

    def test_options_requires_template(self):
        """Test that options require either template_file or template_string."""
        with pytest.raises(ValueError, match="Either template_file or template_string must be provided"):
            JinjaRendererOptions()

    def test_options_with_template_file(self):
        """Test options with template_file."""
        options = JinjaRendererOptions(template_file="template.jinja2")
        assert options.template_file == "template.jinja2"
        assert options.template_string is None

    def test_options_with_template_string(self):
        """Test options with template_string."""
        options = JinjaRendererOptions(template_string="Hello {{ title }}")
        assert options.template_string == "Hello {{ title }}"
        assert options.template_file is None

    def test_custom_escape_strategy_requires_function(self):
        """Test that custom escape strategy requires custom_escape_function."""
        with pytest.raises(ValueError, match="custom_escape_function must be provided"):
            JinjaRendererOptions(template_string="test", escape_strategy="custom")

    def test_custom_escape_function_requires_custom_strategy(self):
        """Test that custom_escape_function requires custom strategy."""

        def my_escape(text: str) -> str:
            return text

        with pytest.raises(ValueError, match="custom_escape_function can only be used"):
            JinjaRendererOptions(template_string="test", custom_escape_function=my_escape, escape_strategy="xml")


class TestEscapeFunctions:
    """Test escape functions."""

    def test_escape_xml(self):
        """Test XML escaping."""
        assert escape_xml("<script>alert('XSS')</script>") == "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;"
        assert escape_xml("Hello & World") == "Hello &amp; World"
        assert escape_xml('Test "quotes"') == "Test &quot;quotes&quot;"

    def test_escape_html(self):
        """Test HTML escaping (should be same as XML)."""
        assert escape_html("<div>test</div>") == "&lt;div&gt;test&lt;/div&gt;"

    def test_escape_latex(self):
        """Test LaTeX escaping."""
        result = escape_latex("$100 & 50% profit")
        assert "\\$" in result
        assert "\\&" in result
        assert "\\%" in result

    def test_escape_yaml(self):
        """Test YAML escaping."""
        # Simple string without special chars - no quotes needed
        assert escape_yaml("simple") == "simple"
        # String with colon needs quotes
        assert escape_yaml("key: value") == '"key: value"'
        # String with quotes needs escaping
        assert escape_yaml('say "hello"') == '"say \\"hello\\""'

    def test_escape_markdown(self):
        """Test Markdown escaping."""
        result = escape_markdown("Text with *asterisks* and [brackets]")
        assert "\\*" in result
        assert "\\[" in result

    def test_escape_empty_strings(self):
        """Test that empty strings are handled correctly."""
        assert escape_xml("") == ""
        assert escape_latex("") == ""
        assert escape_markdown("") == ""


class TestTraversalHelpers:
    """Test AST traversal helper functions."""

    def test_get_all_headings(self):
        """Test extracting all headings from document."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(content=[Text(content="Some text")]),
                Heading(level=2, content=[Text(content="Subtitle")]),
            ]
        )

        headings = get_all_headings(doc)
        assert len(headings) == 2
        assert headings[0]["level"] == 1
        assert headings[0]["text"] == "Title"
        assert headings[1]["level"] == 2
        assert headings[1]["text"] == "Subtitle"

    def test_get_all_links(self):
        """Test extracting all links from document."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Link(url="https://example.com", content=[Text(content="Example")], title="Example Site"),
                        Text(content=" and "),
                        Link(url="https://test.com", content=[Text(content="Test")], title=None),
                    ]
                )
            ]
        )

        links = get_all_links(doc)
        assert len(links) == 2
        assert links[0]["url"] == "https://example.com"
        assert links[0]["text"] == "Example"
        assert links[0]["title"] == "Example Site"
        assert links[1]["url"] == "https://test.com"
        assert links[1]["text"] == "Test"

    def test_get_all_images(self):
        """Test extracting all images from document."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Image(url="image1.png", alt_text="Image 1", title="First", width=100, height=200),
                        Image(url="image2.jpg", alt_text="Image 2", title=None, width=None, height=None),
                    ]
                )
            ]
        )

        images = get_all_images(doc)
        assert len(images) == 2
        assert images[0]["url"] == "image1.png"
        assert images[0]["alt_text"] == "Image 1"
        assert images[0]["width"] == 100
        assert images[0]["height"] == 200
        assert images[1]["url"] == "image2.jpg"


class TestJinjaRenderer:
    """Test JinjaRenderer functionality."""

    def test_basic_rendering(self):
        """Test basic template rendering."""
        doc = Document(metadata={"title": "Test Document"}, children=[Paragraph(content=[Text(content="Hello world")])])

        template = "Title: {{ title }}"
        options = JinjaRendererOptions(template_string=template)
        renderer = JinjaRenderer(options)

        result = renderer.render_to_string(doc)
        assert result == "Title: Test Document"

    def test_access_document_metadata(self):
        """Test accessing document metadata in template."""
        doc = Document(metadata={"title": "My Doc", "author": "Test Author"}, children=[])

        template = "{{ metadata.title }} by {{ metadata.author }}"
        options = JinjaRendererOptions(template_string=template)
        renderer = JinjaRenderer(options)

        result = renderer.render_to_string(doc)
        assert result == "My Doc by Test Author"

    def test_escape_filter_xml(self):
        """Test using escape_xml filter in template."""
        doc = Document(metadata={"title": "Test & <Demo>"}, children=[])

        template = "{{ metadata.title|escape_xml }}"
        options = JinjaRendererOptions(template_string=template, enable_escape_filters=True)
        renderer = JinjaRenderer(options)

        result = renderer.render_to_string(doc)
        assert result == "Test &amp; &lt;Demo&gt;"

    def test_traversal_helper_headings(self):
        """Test using get_headings helper in template."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Heading(level=2, content=[Text(content="Subtitle")]),
            ]
        )

        template = """
{%- for h in headings -%}
H{{ h.level }}: {{ h.text }}
{% endfor -%}
"""
        options = JinjaRendererOptions(template_string=template, enable_traversal_helpers=True)
        renderer = JinjaRenderer(options)

        result = renderer.render_to_string(doc)
        assert "H1: Title" in result
        assert "H2: Subtitle" in result

    def test_extra_context(self):
        """Test providing extra context variables."""
        doc = Document(children=[])

        template = "Version: {{ version }}, Author: {{ author }}"
        options = JinjaRendererOptions(
            template_string=template, extra_context={"version": "1.0.0", "author": "Developer"}
        )
        renderer = JinjaRenderer(options)

        result = renderer.render_to_string(doc)
        assert result == "Version: 1.0.0, Author: Developer"

    def test_node_type_filter(self):
        """Test node_type filter."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])

        template = """
{%- for child in document.children -%}
{{ child|node_type }}
{% endfor -%}
"""
        options = JinjaRendererOptions(template_string=template)
        renderer = JinjaRenderer(options)

        result = renderer.render_to_string(doc)
        assert "Heading" in result

    def test_custom_escape_function(self):
        """Test using custom escape function."""

        def rot13_escape(text: str) -> str:
            # Simple ROT13 for testing
            return text.translate(str.maketrans("abcdefghijklmnopqrstuvwxyz", "nopqrstuvwxyzabcdefghijklm"))

        doc = Document(metadata={"title": "hello"}, children=[])

        template = "{{ metadata.title }}"
        options = JinjaRendererOptions(
            template_string=template, escape_strategy="custom", custom_escape_function=rot13_escape
        )
        renderer = JinjaRenderer(options)

        result = renderer.render_to_string(doc)
        assert result == "hello"  # Without autoescape, no transformation

    def test_strict_undefined_enabled(self):
        """Test that strict_undefined raises errors for missing variables."""
        doc = Document(children=[])

        template = "{{ missing_variable }}"
        options = JinjaRendererOptions(template_string=template, strict_undefined=True)
        renderer = JinjaRenderer(options)

        with pytest.raises(Exception):  # Jinja2 UndefinedError
            renderer.render_to_string(doc)

    def test_strict_undefined_disabled(self):
        """Test that disabling strict_undefined renders undefined as empty."""
        doc = Document(children=[])

        template = "Value: {{ missing_variable }}"
        options = JinjaRendererOptions(template_string=template, strict_undefined=False)
        renderer = JinjaRenderer(options)

        result = renderer.render_to_string(doc)
        assert result == "Value: "

    def test_xml_template_example(self):
        """Test rendering a simple XML document."""
        doc = Document(
            metadata={"title": "Test Document"},
            children=[
                Heading(level=1, content=[Text(content="Chapter 1")]),
                Paragraph(content=[Text(content="Some text here.")]),
            ],
        )

        template = """<?xml version="1.0"?>
<document>
  <title>{{ metadata.title|escape_xml }}</title>
  <body>
    {%- for heading in headings %}
    <heading level="{{ heading.level }}">{{ heading.text|escape_xml }}</heading>
    {%- endfor %}
  </body>
</document>"""

        options = JinjaRendererOptions(
            template_string=template, escape_strategy="xml", enable_escape_filters=True, enable_traversal_helpers=True
        )
        renderer = JinjaRenderer(options)

        result = renderer.render_to_string(doc)
        assert '<?xml version="1.0"?>' in result
        assert "<title>Test Document</title>" in result
        assert '<heading level="1">Chapter 1</heading>' in result

    def test_yaml_template_example(self):
        """Test rendering a simple YAML document."""
        doc = Document(
            metadata={"title": "My Document", "author": "John Doe"},
            children=[Heading(level=1, content=[Text(content="Introduction")])],
        )

        template = """title: {{ metadata.title|escape_yaml }}
author: {{ metadata.author|escape_yaml }}
headings:
{%- for h in headings %}
  - level: {{ h.level }}
    text: {{ h.text|escape_yaml }}
{%- endfor %}"""

        options = JinjaRendererOptions(
            template_string=template, escape_strategy="yaml", enable_escape_filters=True, enable_traversal_helpers=True
        )
        renderer = JinjaRenderer(options)

        result = renderer.render_to_string(doc)
        assert "title: My Document" in result
        assert "author: John Doe" in result
        assert "level: 1" in result
        assert "text: Introduction" in result

    def test_ast_dict_access(self):
        """Test accessing AST as dictionary in template."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])

        template = "Node type: {{ ast.node_type }}, Children: {{ ast.children|length }}"
        options = JinjaRendererOptions(template_string=template)
        renderer = JinjaRenderer(options)

        result = renderer.render_to_string(doc)
        assert "Node type: Document" in result
        assert "Children: 1" in result
