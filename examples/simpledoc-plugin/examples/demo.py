#!/usr/bin/env python
"""Demo script showing SimpleDoc plugin usage.

This script demonstrates how to use the SimpleDoc plugin to parse
and render documents.
"""

from pathlib import Path

from all2md_simpledoc import SimpleDocParser, SimpleDocRenderer, SimpleDocOptions


def demo_parsing():
    """Demonstrate parsing SimpleDoc format."""
    print("=" * 60)
    print("DEMO: Parsing SimpleDoc")
    print("=" * 60)

    # Sample SimpleDoc content
    simpledoc_content = """---
title: Demo Document
author: Example User
---

@@ Welcome

This is a demo of the SimpleDoc format.

@@ Features

- Simple syntax
- Easy to read
- Easy to write

@@ Code Example

```python
def greet(name):
    return f"Hello, {name}!"
```
"""

    # Parse the content
    parser = SimpleDocParser()
    ast_doc = parser.parse(simpledoc_content.encode())

    print("\nParsed AST structure:")
    print(f"  Document with {len(ast_doc.children)} children")
    print(f"  Metadata: {ast_doc.metadata}")

    for i, child in enumerate(ast_doc.children):
        print(f"  [{i}] {type(child).__name__}")

    print("\nMetadata extracted:")
    print(f"  Title: {ast_doc.metadata.get('title')}")
    print(f"  Author: {ast_doc.metadata.get('author')}")


def demo_rendering():
    """Demonstrate rendering to SimpleDoc format."""
    print("\n" + "=" * 60)
    print("DEMO: Rendering to SimpleDoc")
    print("=" * 60)

    from all2md.ast import CodeBlock, Document, Heading, List, ListItem, Paragraph, Text

    # Create AST manually
    doc = Document(
        children=[
            Heading(level=1, content=[Text(content="Generated Document")]),
            Paragraph(content=[Text(content="This document was created programmatically.")]),
            List(
                ordered=False,
                items=[
                    ListItem(children=[Paragraph(content=[Text(content="First item")])]),
                    ListItem(children=[Paragraph(content=[Text(content="Second item")])]),
                ],
            ),
            CodeBlock(language="python", content='print("Hello from AST!")'),
        ],
        metadata={"title": "Generated Example", "author": "Demo Script"},
    )

    # Render to SimpleDoc
    renderer = SimpleDocRenderer()
    output = renderer.render_to_string(doc)

    print("\nRendered SimpleDoc output:")
    print("-" * 60)
    print(output)
    print("-" * 60)


def demo_round_trip():
    """Demonstrate round-trip conversion."""
    print("\n" + "=" * 60)
    print("DEMO: Round-trip Conversion")
    print("=" * 60)

    original = """@@ Test Document

This is a paragraph.

- Item A
- Item B
"""

    # Parse
    parser = SimpleDocParser()
    ast = parser.parse(original.encode())
    print(f"\nOriginal parsed to {len(ast.children)} AST nodes")

    # Render
    renderer = SimpleDocRenderer()
    rendered = renderer.render_to_string(ast)
    print("\nRendered back to SimpleDoc:")
    print("-" * 60)
    print(rendered)
    print("-" * 60)

    # Parse again to verify
    ast2 = parser.parse(rendered.encode())
    print(f"\nRe-parsed to {len(ast2.children)} AST nodes")
    print("Round-trip successful!" if len(ast.children) == len(ast2.children) else "Structure changed!")


def demo_file_operations(output_dir: Path):
    """Demonstrate file operations."""
    print("\n" + "=" * 60)
    print("DEMO: File Operations")
    print("=" * 60)

    # Create output directory
    output_dir.mkdir(exist_ok=True)

    from all2md.ast import Document, Heading, Paragraph, Text

    # Create a document
    doc = Document(
        children=[
            Heading(level=1, content=[Text(content="File Demo")]),
            Paragraph(content=[Text(content="This was written to a file.")]),
        ],
        metadata={"title": "File Example"},
    )

    # Write to file
    output_file = output_dir / "demo_output.sdoc"
    renderer = SimpleDocRenderer()
    renderer.render(doc, output_file)
    print(f"\nWrote document to: {output_file}")

    # Read it back
    parser = SimpleDocParser()
    doc_read = parser.parse(output_file)
    print(f"Read back: {len(doc_read.children)} nodes")
    print(f"Title: {doc_read.metadata.get('title')}")


if __name__ == "__main__":
    # Run all demos
    demo_parsing()
    demo_rendering()
    demo_round_trip()

    # File operations demo (optional)
    output_dir = Path(__file__).parent / "output"
    demo_file_operations(output_dir)

    print("\n" + "=" * 60)
    print("All demos completed!")
    print("=" * 60)
