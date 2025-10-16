"""Unit tests for the RtfRenderer."""

import pytest

try:
    from pyth.plugins.rtf15 import writer  # noqa: F401
    RTF_AVAILABLE = True
except Exception:  # pragma: no cover - dependency guard
    RTF_AVAILABLE = False

from all2md.ast import Document, Emphasis, Paragraph, Strong, Text
from all2md.options import RtfRendererOptions

if RTF_AVAILABLE:
    from all2md.renderers.rtf import RtfRenderer


pytestmark = pytest.mark.skipif(not RTF_AVAILABLE, reason="pyth3 with six not installed")


@pytest.mark.unit
class TestRtfRendererBasic:
    """Smoke tests for the RTF renderer."""

    def test_render_empty_document_to_string(self) -> None:
        """Render an empty document and ensure RTF header is present."""
        renderer = RtfRenderer()
        output = renderer.render_to_string(Document())
        assert "\\rtf1" in output

    def test_render_formatted_paragraph(self) -> None:
        """Ensure formatted inline nodes appear in the output payload."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Hello "),
                Strong(content=[Text(content="world")]),
                Emphasis(content=[Text(content="!")])
            ])
        ])
        renderer = RtfRenderer(RtfRendererOptions(font_family="swiss"))
        rtf_output = renderer.render_to_string(doc)
        assert "Hello" in rtf_output
        assert "world" in rtf_output
        assert "!" in rtf_output
