#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/renderers/test_epub_conversion.py
"""Integration tests for EPUB renderer.

Tests cover:
- End-to-end EPUB rendering workflows
- Chapter splitting strategies
- Table of contents generation
- Metadata handling
- Complex content structures

"""


import pytest

try:
    from ebooklib import epub
    EBOOKLIB_AVAILABLE = True
except ImportError:
    EBOOKLIB_AVAILABLE = False

from all2md.ast import (
    BlockQuote,
    CodeBlock,
    Document,
    Heading,
    Link,
    List,
    ListItem,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
)
from all2md.options import EpubRendererOptions

if EBOOKLIB_AVAILABLE:
    from all2md.renderers.epub import EpubRenderer


def create_sample_document():
    """Create a sample AST document for testing.

    Returns
    -------
    Document
        A sample document with various elements for testing.

    """
    return Document(
        metadata={"title": "Sample Document", "author": "Test Author"},
        children=[
            Heading(level=1, content=[Text(content="Document Title")]),
            Paragraph(content=[
                Text(content="This is a paragraph with "),
                Strong(content=[Text(content="bold text")]),
                Text(content=" and a "),
                Link(url="https://example.com", content=[Text(content="link")]),
                Text(content=".")
            ]),
            Heading(level=2, content=[Text(content="Lists")]),
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="First item")])]),
                ListItem(children=[Paragraph(content=[Text(content="Second item")])]),
                ListItem(children=[Paragraph(content=[Text(content="Third item")])])
            ]),
            Heading(level=2, content=[Text(content="Code Example")]),
            CodeBlock(content='def hello():\n    print("Hello, world!")', language="python"),
            Heading(level=2, content=[Text(content="Table")]),
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Name")]),
                    TableCell(content=[Text(content="Value")])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="Alpha")]),
                        TableCell(content=[Text(content="1")])
                    ]),
                    TableRow(cells=[
                        TableCell(content=[Text(content="Beta")]),
                        TableCell(content=[Text(content="2")])
                    ])
                ]
            ),
            Heading(level=2, content=[Text(content="Quote")]),
            BlockQuote(children=[
                Paragraph(content=[Text(content="This is a blockquote.")])
            ])
        ]
    )


@pytest.mark.skipif(not EBOOKLIB_AVAILABLE, reason="ebooklib not installed")
@pytest.mark.integration
class TestEpubRendering:
    """Integration tests for EPUB rendering."""

    def test_full_document_to_epub(self, tmp_path):
        """Test rendering complete document to EPUB."""
        doc = create_sample_document()
        renderer = EpubRenderer(EpubRendererOptions(
            title="Sample Book",
            author="Test Author"
        ))
        output_file = tmp_path / "sample.epub"
        renderer.render(doc, output_file)

        # Verify file created and is valid EPUB
        assert output_file.exists()
        book = epub.read_epub(str(output_file))
        assert book.get_metadata('DC', 'title')[0][0] == "Sample Book"
        assert book.get_metadata('DC', 'creator')[0][0] == "Test Author"

    def test_epub_chapter_splitting_strategies(self, tmp_path):
        """Test different chapter splitting strategies."""
        # Document with both separators and headings
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Chapter 1")]),
            Paragraph(content=[Text(content="Content 1")]),
            ThematicBreak(),
            Heading(level=1, content=[Text(content="Chapter 2")]),
            Paragraph(content=[Text(content="Content 2")])
        ])

        # Test separator mode
        sep_renderer = EpubRenderer(EpubRendererOptions(chapter_split_mode="separator"))
        sep_file = tmp_path / "separator.epub"
        sep_renderer.render(doc, sep_file)
        assert sep_file.exists()

        # Test heading mode
        heading_renderer = EpubRenderer(EpubRendererOptions(chapter_split_mode="heading"))
        heading_file = tmp_path / "heading.epub"
        heading_renderer.render(doc, heading_file)
        assert heading_file.exists()

        # Test auto mode
        auto_renderer = EpubRenderer(EpubRendererOptions(chapter_split_mode="auto"))
        auto_file = tmp_path / "auto.epub"
        auto_renderer.render(doc, auto_file)
        assert auto_file.exists()

    def test_epub_with_toc(self, tmp_path):
        """Test EPUB with table of contents."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Introduction")]),
            Paragraph(content=[Text(content="Intro content")]),
            Heading(level=1, content=[Text(content="Main Content")]),
            Paragraph(content=[Text(content="Main content")]),
            Heading(level=1, content=[Text(content="Conclusion")]),
            Paragraph(content=[Text(content="Conclusion")])
        ])

        renderer = EpubRenderer(EpubRendererOptions(
            chapter_split_mode="heading",
            generate_toc=True
        ))
        output_file = tmp_path / "with_toc.epub"
        renderer.render(doc, output_file)

        # Verify TOC was created
        book = epub.read_epub(str(output_file))
        assert len(book.toc) > 0

    def test_epub_metadata_from_document(self, tmp_path):
        """Test EPUB metadata extraction from document."""
        doc = Document(
            metadata={
                "title": "My Document",
                "author": "Jane Smith",
                "subject": "Testing",
                "date": "2025-01-01"
            },
            children=[
                Paragraph(content=[Text(content="Content")])
            ]
        )

        renderer = EpubRenderer()
        output_file = tmp_path / "metadata.epub"
        renderer.render(doc, output_file)

        # Verify metadata
        book = epub.read_epub(str(output_file))
        assert book.get_metadata('DC', 'title')[0][0] == "My Document"
        assert book.get_metadata('DC', 'creator')[0][0] == "Jane Smith"

    def test_epub_complex_content(self, tmp_path):
        """Test EPUB with complex content structures."""
        doc = Document(
            metadata={"title": "Complex EPUB"},
            children=[
                Heading(level=1, content=[Text(content="Chapter 1: Introduction")]),
                Paragraph(content=[
                    Text(content="This is "),
                    Strong(content=[Text(content="important")]),
                    Text(content=".")
                ]),
                List(ordered=True, items=[
                    ListItem(children=[Paragraph(content=[Text(content="First point")])]),
                    ListItem(children=[Paragraph(content=[Text(content="Second point")])])
                ]),
                ThematicBreak(),
                Heading(level=1, content=[Text(content="Chapter 2: Code")]),
                CodeBlock(content='def example():\n    return 42', language="python"),
                ThematicBreak(),
                Heading(level=1, content=[Text(content="Chapter 3: Data")]),
                Table(
                    header=TableRow(cells=[
                        TableCell(content=[Text(content="Name")]),
                        TableCell(content=[Text(content="Value")])
                    ]),
                    rows=[
                        TableRow(cells=[
                            TableCell(content=[Text(content="X")]),
                            TableCell(content=[Text(content="10")])
                        ])
                    ]
                )
            ]
        )

        renderer = EpubRenderer()
        output_file = tmp_path / "complex.epub"
        renderer.render(doc, output_file)

        # Verify EPUB is valid
        book = epub.read_epub(str(output_file))
        assert book is not None
