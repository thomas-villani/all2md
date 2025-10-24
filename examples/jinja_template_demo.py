#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Demonstration of Jinja2 template-based rendering in all2md.

This script shows how to use the generic Jinja2 template renderer to convert
documents to various custom formats using templates.
"""

import sys

# Fix Windows console encoding for Unicode box characters
if sys.platform == "win32":
    import codecs

    sys.stdout.reconfigure(encoding="utf-8")

from all2md.ast import (
    BlockQuote,
    CodeBlock,
    Document,
    Heading,
    Image,
    Link,
    Paragraph,
    Text,
)
from all2md.options.jinja import JinjaRendererOptions
from all2md.renderers.jinja import JinjaRenderer


def create_sample_document() -> Document:
    """Create a sample document for demonstration.

    Returns
    -------
    Document
        Sample document with various node types

    """
    return Document(
        metadata={
            "title": "Sample Technical Document",
            "author": "John Doe",
            "date": "2025-01-15",
        },
        children=[
            Heading(level=1, content=[Text(content="Introduction")]),
            Paragraph(
                content=[
                    Text(content="This is a "),
                    Link(url="https://example.com", content=[Text(content="sample document")], title="Example"),
                    Text(content=" demonstrating the Jinja2 template renderer."),
                ]
            ),
            Heading(level=2, content=[Text(content="Features")]),
            Paragraph(content=[Text(content="The template renderer supports:")]),
            CodeBlock(
                content="def hello():\n    print('Hello, World!')", language="python", fence_char="`", fence_length=3
            ),
            Heading(level=2, content=[Text(content="Images")]),
            Paragraph(
                content=[
                    Text(content="Here's an example image: "),
                    Image(
                        url="diagram.png",
                        alt_text="Architecture Diagram",
                        title="System Architecture",
                        width=800,
                        height=600,
                    ),
                ]
            ),
            BlockQuote(children=[Paragraph(content=[Text(content="This is a quote demonstrating block content.")])]),
        ],
    )


def demo_docbook_xml():
    """Demonstrate DocBook XML generation."""
    print("=" * 70)
    print("1. DocBook XML Template Demo")
    print("=" * 70)

    doc = create_sample_document()

    options = JinjaRendererOptions(
        template_file="examples/jinja-templates/docbook.xml.jinja2",
        escape_strategy="xml",
        enable_escape_filters=True,
        enable_traversal_helpers=True,
    )

    renderer = JinjaRenderer(options)
    output = renderer.render_to_string(doc)

    print(output)
    print()


def demo_yaml_metadata():
    """Demonstrate YAML metadata extraction."""
    print("=" * 70)
    print("2. YAML Metadata Template Demo")
    print("=" * 70)

    doc = create_sample_document()

    options = JinjaRendererOptions(
        template_file="examples/jinja-templates/metadata.yaml.jinja2",
        escape_strategy="yaml",
        enable_escape_filters=True,
        enable_traversal_helpers=True,
    )

    renderer = JinjaRenderer(options)
    output = renderer.render_to_string(doc)

    print(output)
    print()


def demo_custom_outline():
    """Demonstrate custom text outline."""
    print("=" * 70)
    print("3. Custom Outline Template Demo")
    print("=" * 70)

    doc = create_sample_document()

    options = JinjaRendererOptions(
        template_file="examples/jinja-templates/custom-outline.txt.jinja2",
        enable_traversal_helpers=True,
    )

    renderer = JinjaRenderer(options)
    output = renderer.render_to_string(doc)

    print(output)
    print()


def demo_inline_template():
    """Demonstrate using an inline template string."""
    print("=" * 70)
    print("4. Inline Template String Demo")
    print("=" * 70)

    doc = create_sample_document()

    template = """
# {{ title }}

{% if metadata.author -%}
By: {{ metadata.author }}
{% endif %}

## Table of Contents
{%- for h in headings %}
{{ "  " * (h.level - 1) }}- {{ h.text }}
{%- endfor %}

## Statistics
- Headings: {{ headings|length }}
- Links: {{ links|length }}
- Images: {{ images|length }}
"""

    options = JinjaRendererOptions(
        template_string=template,
        enable_traversal_helpers=True,
    )

    renderer = JinjaRenderer(options)
    output = renderer.render_to_string(doc)

    print(output)
    print()


def demo_ansi_terminal():
    """Demonstrate ANSI colored terminal output."""
    print("=" * 70)
    print("5. ANSI Terminal Output Demo")
    print("=" * 70)

    doc = create_sample_document()

    options = JinjaRendererOptions(
        template_file="examples/jinja-templates/ansi-terminal.txt.jinja2",
        enable_traversal_helpers=True,
    )

    renderer = JinjaRenderer(options)
    output = renderer.render_to_string(doc)

    print(output)
    print()


def demo_custom_context():
    """Demonstrate providing extra context variables."""
    print("=" * 70)
    print("6. Custom Context Variables Demo")
    print("=" * 70)

    doc = create_sample_document()

    template = """
Document: {{ title }}
Version: {{ version }}
Generated by: {{ tool_name }}

Prepared for: {{ client_name }}
Project: {{ project_code }}
"""

    options = JinjaRendererOptions(
        template_string=template,
        extra_context={
            "version": "1.0.0",
            "tool_name": "all2md Jinja2 Renderer",
            "client_name": "Acme Corp",
            "project_code": "PROJ-2025-001",
        },
    )

    renderer = JinjaRenderer(options)
    output = renderer.render_to_string(doc)

    print(output)
    print()


def main():
    """Run all demonstrations."""
    print("\n")
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + "  Jinja2 Template Renderer Demonstration".center(68) + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    print("\n")

    demo_docbook_xml()
    demo_yaml_metadata()
    demo_custom_outline()
    demo_inline_template()
    demo_ansi_terminal()
    demo_custom_context()

    print("=" * 70)
    print("All demonstrations completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
