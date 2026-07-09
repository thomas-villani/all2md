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


# A *custom* character style name (not a python-docx built-in) so assertions can
# tell "renderer applied the source style from the template" apart from "the
# default skeleton happened to define it too" — same rationale as
# CUSTOM_STYLE_NAME for paragraphs.
CUSTOM_RUN_STYLE_NAME = "RunQuote_Roundtrip"


def _make_docx_with_run_styles(path: Path) -> None:
    """Build a docx whose paragraph mixes plain and character-styled runs."""
    doc = DocxDocument()
    if CUSTOM_RUN_STYLE_NAME not in {s.name for s in doc.styles}:
        char_style = doc.styles.add_style(CUSTOM_RUN_STYLE_NAME, WD_STYLE_TYPE.CHARACTER)
        char_style.font.small_caps = True

    para = doc.add_paragraph()
    para.add_run("plain ")
    quoted = para.add_run("quoted")
    quoted.style = doc.styles[CUSTOM_RUN_STYLE_NAME]
    para.add_run(" and ")
    strong = para.add_run("strong-styled")
    strong.bold = True
    strong.style = doc.styles[CUSTOM_RUN_STYLE_NAME]
    doc.save(str(path))


@pytest.fixture
def docx_with_run_styles(tmp_path: Path) -> Path:
    path = tmp_path / "run-styles-source.docx"
    _make_docx_with_run_styles(path)
    return path


@pytest.mark.integration
@pytest.mark.docx
def test_run_character_style_captured_on_ast(docx_with_run_styles: Path) -> None:
    """The parser stashes the run character style on the inline node metadata."""
    doc = to_ast(str(docx_with_run_styles))
    captured = [
        node.metadata.get("source_style")
        for para in doc.children
        for node in getattr(para, "content", [])
        if node.metadata.get("source_style")
    ]
    # Both the plain styled run and the bold+styled run carry the style name.
    assert captured.count(CUSTOM_RUN_STYLE_NAME) == 2


@pytest.mark.integration
@pytest.mark.docx
def test_run_character_style_round_trips_through_template(docx_with_run_styles: Path, tmp_path: Path) -> None:
    """A named character style on a run survives docx → AST → docx with a template."""
    doc = to_ast(str(docx_with_run_styles))
    out_path = tmp_path / "out.docx"
    from_ast(
        doc,
        "docx",
        output=out_path,
        template_path=str(docx_with_run_styles),
        clear_template_body=True,
    )

    rendered = DocxDocument(str(out_path))
    runs = {run.text: run for para in rendered.paragraphs for run in para.runs}
    assert runs["quoted"].style is not None and runs["quoted"].style.name == CUSTOM_RUN_STYLE_NAME
    # The bold-and-styled run keeps *both* the character style and direct bold.
    assert runs["strong-styled"].style is not None and runs["strong-styled"].style.name == CUSTOM_RUN_STYLE_NAME
    assert runs["strong-styled"].bold is True
    # Unstyled runs stay on the default run style.
    assert runs["plain "].style.name == "Default Paragraph Font"


@pytest.mark.integration
@pytest.mark.docx
def test_run_character_style_no_op_without_template(docx_with_run_styles: Path, tmp_path: Path) -> None:
    """Without a template the custom run style falls through silently."""
    doc = to_ast(str(docx_with_run_styles))
    out_path = tmp_path / "out.docx"
    from_ast(doc, "docx", output=out_path)

    rendered = DocxDocument(str(out_path))
    # The custom character style only exists in the source; the default skeleton
    # has no such style, so the source_style application falls through.
    styled = [
        run
        for para in rendered.paragraphs
        for run in para.runs
        if run.style and run.style.name == CUSTOM_RUN_STYLE_NAME
    ]
    assert not styled, "Custom character style must not appear without a template that defines it"
