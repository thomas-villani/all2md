#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/renderers/test_pdf_conversion.py
"""Integration tests for PDF renderer.

Tests cover:
- End-to-end PDF rendering workflows
- Different page sizes
- Custom font settings
- Complete document conversion

"""


import pytest

try:
    from reportlab.platypus import SimpleDocTemplate  # noqa: F401
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from all2md.ast import (
    BlockQuote,
    CodeBlock,
    Document,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.options import PdfRendererOptions
from all2md.options.common import NetworkFetchOptions

if REPORTLAB_AVAILABLE:
    from all2md.renderers.pdf import PdfRenderer


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


@pytest.mark.integration
@pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="reportlab not installed")
@pytest.mark.pdf
class TestPdfRendering:
    """Integration tests for PDF rendering."""

    def test_full_document_to_pdf(self, tmp_path):
        """Test rendering complete document to PDF."""
        doc = create_sample_document()
        renderer = PdfRenderer()
        output_file = tmp_path / "full_document.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_pdf_page_sizes(self, tmp_path):
        """Test PDF rendering with different page sizes."""
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])

        # Letter
        letter_renderer = PdfRenderer(PdfRendererOptions(page_size="letter"))
        letter_file = tmp_path / "letter.pdf"
        letter_renderer.render(doc, letter_file)
        assert letter_file.exists()

        # A4
        a4_renderer = PdfRenderer(PdfRendererOptions(page_size="a4"))
        a4_file = tmp_path / "a4.pdf"
        a4_renderer.render(doc, a4_file)
        assert a4_file.exists()

        # Legal
        legal_renderer = PdfRenderer(PdfRendererOptions(page_size="legal"))
        legal_file = tmp_path / "legal.pdf"
        legal_renderer.render(doc, legal_file)
        assert legal_file.exists()

    def test_pdf_with_custom_fonts(self, tmp_path):
        """Test PDF with custom font settings."""
        doc = create_sample_document()
        options = PdfRendererOptions(
            font_name="Times-Roman",
            font_size=12,
            code_font="Courier"
        )
        renderer = PdfRenderer(options)
        output_file = tmp_path / "custom_fonts.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.integration
@pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="reportlab not installed")
@pytest.mark.pdf
class TestPdfRemoteImageFetching:
    """Integration tests for PDF remote image fetching."""

    def test_remote_image_disabled_by_default(self, tmp_path):
        """Test that remote images are skipped by default (secure-by-default)."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Image test:")]),
            Paragraph(content=[
                Image(
                    url="https://example.com/test-image.png",
                    alt_text="Remote image"
                )
            ])
        ])
        # Default options should have allow_remote_fetch=False
        renderer = PdfRenderer()
        output_file = tmp_path / "no_remote.pdf"
        renderer.render(doc, output_file)

        # Should complete without error, but image is skipped
        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_remote_image_explicit_disabled(self, tmp_path):
        """Test that remote images are skipped when explicitly disabled."""
        doc = Document(children=[
            Paragraph(content=[
                Image(
                    url="https://httpbin.org/image/png",
                    alt_text="Remote image"
                )
            ])
        ])
        options = PdfRendererOptions(
            network=NetworkFetchOptions(allow_remote_fetch=False)
        )
        renderer = PdfRenderer(options)
        output_file = tmp_path / "remote_disabled.pdf"
        renderer.render(doc, output_file)

        # Should complete without error, but image is skipped
        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_local_image_not_affected(self, tmp_path):
        """Test that local images work regardless of network settings."""
        # This is a unit test verifying local images aren't affected
        doc = Document(children=[
            Paragraph(content=[
                Image(
                    url="/path/to/local/image.png",
                    alt_text="Local image"
                )
            ])
        ])
        # Even with remote fetching disabled, local images should be attempted
        options = PdfRendererOptions(
            network=NetworkFetchOptions(allow_remote_fetch=False),
            fail_on_resource_errors=False
        )
        renderer = PdfRenderer(options)
        output_file = tmp_path / "local_image.pdf"
        renderer.render(doc, output_file)

        # Should complete (though image won't be found)
        assert output_file.exists()

    def test_base64_image_not_affected(self, tmp_path):
        """Test that base64 images work regardless of network settings."""
        # Small 1x1 red pixel PNG
        base64_image = (
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z"
            "8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        doc = Document(children=[
            Paragraph(content=[
                Image(url=base64_image, alt_text="Base64 image")
            ])
        ])
        # Base64 images should work even with remote fetching disabled
        options = PdfRendererOptions(
            network=NetworkFetchOptions(allow_remote_fetch=False)
        )
        renderer = PdfRenderer(options)
        output_file = tmp_path / "base64_image.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_network_options_respected(self, tmp_path):
        """Test that network security options are properly configured."""
        options = PdfRendererOptions(
            network=NetworkFetchOptions(
                allow_remote_fetch=True,
                require_https=True,
                network_timeout=10.0,
                allowed_hosts=["example.com"]
            )
        )
        renderer = PdfRenderer(options)

        # Verify options are set correctly
        assert renderer.options.network.allow_remote_fetch is True
        assert renderer.options.network.require_https is True
        assert renderer.options.network.network_timeout == 10.0
        assert renderer.options.network.allowed_hosts == ["example.com"]

    def test_mixed_image_sources(self, tmp_path):
        """Test document with mixed image sources (local, remote, base64)."""
        base64_image = (
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z"
            "8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Mixed Images Test")]),
            Paragraph(content=[Text(content="Base64 image:")]),
            Paragraph(content=[Image(url=base64_image, alt_text="Base64")]),
            Paragraph(content=[Text(content="Remote image (skipped):")]),
            Paragraph(content=[
                Image(url="https://example.com/image.png", alt_text="Remote")
            ]),
            Paragraph(content=[Text(content="Local image (attempted):")]),
            Paragraph(content=[Image(url="local.png", alt_text="Local")])
        ])
        options = PdfRendererOptions(
            network=NetworkFetchOptions(allow_remote_fetch=False),
            fail_on_resource_errors=False
        )
        renderer = PdfRenderer(options)
        output_file = tmp_path / "mixed_images.pdf"
        renderer.render(doc, output_file)

        # Should complete successfully
        assert output_file.exists()
        assert output_file.stat().st_size > 0
