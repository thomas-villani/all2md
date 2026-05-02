"""Round-trip tests for the docx → markdown → docx preservation workflow.

These tests verify that the template-as-source pathway (``template_path`` +
``clear_template_body``) and the ``preserve_formatting`` ergonomic kwarg
restore page setup, theme, and custom paragraph styles when round-tripping
a docx through the markdown AST.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

pytest.importorskip("docx")

from docx import Document as DocxDocument
from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Pt

from all2md.api import from_ast, to_ast
from all2md.options.docx import DocxRendererOptions
from all2md.renderers.docx import DocxRenderer

CUSTOM_STYLE_NAME = "QuoteCustom_Roundtrip"


def _make_docx_with_custom_style(path: Path) -> None:
    """Build a small docx that exercises both built-in and custom styles.

    The custom ``QuoteCustom_Roundtrip`` style is the load-bearing piece — we
    use a name that is *not* a python-docx built-in so the assertions can
    distinguish "renderer applied the source style from a template" from
    "renderer happened to find the style in the default template too".
    """
    doc = DocxDocument()

    if CUSTOM_STYLE_NAME not in {s.name for s in doc.styles}:
        custom_style = doc.styles.add_style(CUSTOM_STYLE_NAME, WD_STYLE_TYPE.PARAGRAPH)
        custom_style.base_style = doc.styles["Normal"]
        custom_style.font.italic = True
        custom_style.font.size = Pt(9)

    doc.add_heading("Chapter One", level=1)
    para = doc.add_paragraph("A wandering caption beneath the heading.")
    para.style = CUSTOM_STYLE_NAME
    doc.add_paragraph("Body text in the default style.")
    doc.save(str(path))


@pytest.fixture
def docx_with_caption(tmp_path: Path) -> Path:
    path = tmp_path / "caption-source.docx"
    _make_docx_with_custom_style(path)
    return path


@pytest.mark.integration
@pytest.mark.docx
def test_source_path_stashed_for_file_input(docx_with_caption: Path) -> None:
    """to_ast on a file path stashes the resolved absolute path on the AST."""
    doc = to_ast(str(docx_with_caption))
    assert doc.metadata.get("source_path") == str(docx_with_caption.resolve())


@pytest.mark.integration
@pytest.mark.docx
def test_source_path_not_stashed_for_stream_input(docx_with_caption: Path) -> None:
    """Streams have no path on disk, so source_path stays unset."""
    payload = docx_with_caption.read_bytes()
    doc = to_ast(io.BytesIO(payload), source_format="docx")
    assert "source_path" not in doc.metadata


@pytest.mark.integration
@pytest.mark.docx
def test_source_style_metadata_captured_for_custom_paragraph_style(docx_with_caption: Path) -> None:
    """The parser stashes the originating style name on AST paragraphs."""
    doc = to_ast(str(docx_with_caption))

    captured: list[str] = []
    for child in doc.children:
        style = child.metadata.get("source_style") if child.metadata else None
        if style:
            captured.append(style)

    assert "Heading 1" in captured, "Heading should retain source_style"
    assert CUSTOM_STYLE_NAME in captured, "Custom paragraph style should be preserved on the AST"


@pytest.mark.integration
@pytest.mark.docx
def test_clear_template_body_replaces_body_but_keeps_section_properties(
    docx_with_caption: Path, tmp_path: Path
) -> None:
    """clear_template_body=True wipes paragraphs/tables from the template."""
    doc = to_ast(str(docx_with_caption))
    out_path = tmp_path / "out.docx"

    from_ast(
        doc,
        "docx",
        output=out_path,
        template_path=str(docx_with_caption),
        clear_template_body=True,
    )

    rendered = DocxDocument(str(out_path))
    paragraph_texts = [p.text for p in rendered.paragraphs]
    # The original template had 3 body paragraphs; the AST also produces 3,
    # so duplication would yield 6. Replacement should yield 3.
    assert len(paragraph_texts) == 3
    assert paragraph_texts[0] == "Chapter One"
    assert paragraph_texts[1].startswith("A wandering caption")


@pytest.mark.integration
@pytest.mark.docx
def test_letterhead_append_mode_preserves_template_body(docx_with_caption: Path, tmp_path: Path) -> None:
    """Default (clear_template_body=False) keeps existing template body."""
    doc = to_ast(str(docx_with_caption))
    out_path = tmp_path / "out.docx"

    from_ast(
        doc,
        "docx",
        output=out_path,
        template_path=str(docx_with_caption),
    )

    rendered = DocxDocument(str(out_path))
    paragraph_texts = [p.text for p in rendered.paragraphs]
    # Template had 3 paragraphs + AST appends 3 → 6 total.
    assert len(paragraph_texts) == 6


@pytest.mark.integration
@pytest.mark.docx
def test_custom_style_applied_in_rendered_output(docx_with_caption: Path, tmp_path: Path) -> None:
    """Round-trip preserves the custom 'Caption' style application."""
    doc = to_ast(str(docx_with_caption))
    out_path = tmp_path / "out.docx"

    from_ast(
        doc,
        "docx",
        output=out_path,
        template_path=str(docx_with_caption),
        clear_template_body=True,
    )

    rendered = DocxDocument(str(out_path))
    custom = [p for p in rendered.paragraphs if p.style and p.style.name == CUSTOM_STYLE_NAME]
    assert custom, f"Expected at least one paragraph rendered with the '{CUSTOM_STYLE_NAME}' style"
    assert custom[0].text.startswith("A wandering caption")


@pytest.mark.integration
@pytest.mark.docx
def test_preserve_formatting_kwarg_matches_explicit_options(docx_with_caption: Path, tmp_path: Path) -> None:
    """preserve_formatting=True is equivalent to passing template_path + clear_template_body=True."""
    doc_a = to_ast(str(docx_with_caption))
    out_a = tmp_path / "a.docx"
    from_ast(doc_a, "docx", output=out_a, preserve_formatting=True)

    doc_b = to_ast(str(docx_with_caption))
    out_b = tmp_path / "b.docx"
    from_ast(
        doc_b,
        "docx",
        output=out_b,
        template_path=str(docx_with_caption),
        clear_template_body=True,
    )

    rendered_a = DocxDocument(str(out_a))
    rendered_b = DocxDocument(str(out_b))
    texts_a = [(p.text, p.style.name if p.style else None) for p in rendered_a.paragraphs]
    texts_b = [(p.text, p.style.name if p.style else None) for p in rendered_b.paragraphs]
    assert texts_a == texts_b


@pytest.mark.integration
@pytest.mark.docx
def test_preserve_formatting_no_op_without_source_path(tmp_path: Path) -> None:
    """preserve_formatting=True is a no-op when no source_path was stashed."""
    payload = tmp_path / "src.docx"
    _make_docx_with_custom_style(payload)
    # Use a stream to skip auto-stashing.
    doc = to_ast(io.BytesIO(payload.read_bytes()), source_format="docx")
    assert "source_path" not in doc.metadata

    out = tmp_path / "out.docx"
    # Should not raise, should not pull a template, just renders generically.
    from_ast(doc, "docx", output=out, preserve_formatting=True)
    assert out.exists()


@pytest.mark.integration
@pytest.mark.docx
def test_default_render_unchanged_without_template_path(docx_with_caption: Path, tmp_path: Path) -> None:
    """No template_path means no behavioral change from previous releases."""
    doc = to_ast(str(docx_with_caption))
    out_path = tmp_path / "out.docx"
    from_ast(doc, "docx", output=out_path)

    rendered = DocxDocument(str(out_path))
    # The custom style only exists in the original document; without
    # template_path the default python-docx skeleton has no such style,
    # so the source_style application falls through silently.
    custom = [p for p in rendered.paragraphs if p.style and p.style.name == CUSTOM_STYLE_NAME]
    assert not custom


@pytest.mark.integration
@pytest.mark.docx
def test_clear_template_body_helper_preserves_sectpr(docx_with_caption: Path) -> None:
    """The body-clearing helper must keep the trailing sectPr intact."""
    options = DocxRendererOptions(template_path=str(docx_with_caption), clear_template_body=True)
    renderer = DocxRenderer(options=options)
    # Drive only the document load + clear path by mimicking render() preamble.
    from docx import Document as _Document
    from docx.oxml.ns import qn

    renderer.document = _Document(str(docx_with_caption))
    renderer._qn = qn  # type: ignore[attr-defined]
    renderer._clear_template_body()

    body = renderer.document.element.body
    assert body.find(qn("w:sectPr")) is not None, "sectPr (page setup) must be preserved"
    # No paragraphs or tables should remain in the body.
    assert body.find(qn("w:p")) is None
    assert body.find(qn("w:tbl")) is None
