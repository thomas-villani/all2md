"""Integration tests for the RTF renderer."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from pyth.plugins.rtf15 import writer  # noqa: F401
    RTF_AVAILABLE = True
except Exception:  # pragma: no cover - dependency guard
    RTF_AVAILABLE = False

from all2md.ast import Document, Heading, Paragraph, Strong, Text
from all2md.options import RtfRendererOptions

if RTF_AVAILABLE:
    from all2md.renderers.rtf import RtfRenderer


pytestmark = pytest.mark.skipif(not RTF_AVAILABLE, reason="pyth3 with six not installed")


def _build_basic_document() -> Document:
    """Create a basic document with headings and inline formatting."""
    return Document(
        metadata={"title": "RTF Sample", "author": "Integration Bot"},
        children=[
            Heading(level=1, content=[Text(content="Integration Heading")]),
            Paragraph(content=[
                Text(content="Hello "),
                Strong(content=[Text(content="World")]),
                Text(content="!"),
            ]),
        ],
    )


@pytest.mark.integration
@pytest.mark.rtf
class TestRtfRenderingIntegration:
    """End-to-end checks for generating RTF output."""

    def test_render_to_string_contains_expected_segments(self) -> None:
        """Ensure rendered string contains header, metadata, and body text."""
        doc = _build_basic_document()
        renderer = RtfRenderer()
        output = renderer.render_to_string(doc)

        assert "\\rtf1" in output
        assert "Integration Heading" in output
        assert "Hello" in output
        assert "World" in output

    def test_render_to_file_round_trip(self, tmp_path: Path) -> None:
        """Render to disk and verify persisted RTF payload."""
        doc = _build_basic_document()
        renderer = RtfRenderer(RtfRendererOptions(font_family="swiss"))
        target = tmp_path / "sample.rtf"
        renderer.render(doc, target)

        assert target.exists()
        content = target.read_text(encoding="utf-8")
        assert "\\rtf1" in content
        assert "Integration Heading" in content
        # ensure font family switch applied (Calibri == swiss)
        assert "Calibri" in content or "\\f1\\fswiss" in content
