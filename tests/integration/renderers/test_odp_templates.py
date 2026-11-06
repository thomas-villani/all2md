"""Exercise ODP templates through Markdown conversion and the real CLI."""

import subprocess
import sys
from io import BytesIO, StringIO
from zipfile import BadZipFile

import pytest

pytest.importorskip("odf")

from odf.draw import Frame, Page, TextBox
from odf.opendocument import OpenDocumentPresentation, load
from odf.style import HandoutMaster, MasterPage, PageLayout, PageLayoutProperties, Style, TextProperties
from odf.text import P

from all2md import convert
from all2md.ast import Document, Paragraph, Text
from all2md.exceptions import RenderingError
from all2md.options import OdpRendererOptions
from all2md.renderers.odp import OdpRenderer

pytestmark = [pytest.mark.integration, pytest.mark.odf]


@pytest.fixture
def odp_template(tmp_path):
    """Build a synthetic template with two slides, two masters and custom styles."""
    template = OpenDocumentPresentation()
    layout = PageLayout(name="TemplateLayout")
    layout.addElement(PageLayoutProperties(pagewidth="28cm", pageheight="21cm", printorientation="landscape"))
    template.automaticstyles.addElement(layout)
    text_style = Style(name="TemplateText", family="paragraph")
    text_style.addElement(TextProperties(color="#123456", fontsize="18pt"))
    template.styles.addElement(text_style)

    # A non-master-page child must be skipped when selecting the first master.
    template.masterstyles.addElement(HandoutMaster(pagelayoutname=layout))
    for index in range(2):
        master = MasterPage(name=f"TemplateMaster{index}", pagelayoutname=layout)
        template.masterstyles.addElement(master)
        page = Page(name=f"TemplateSlide{index}", masterpagename=master)
        frame = Frame(width="20cm", height="3cm", x="1cm", y="1cm")
        textbox = TextBox()
        textbox.addElement(P(text=f"Retained template content {index}", stylename=text_style))
        frame.addElement(textbox)
        page.addElement(frame)
        template.presentation.addElement(page)

    path = tmp_path / "template.odp"
    template.save(str(path))
    return path


def _xml(element):
    """Serialize a reloaded ODF element to compare retained template structures."""
    buffer = StringIO()
    element.toXml(0, buffer)
    return buffer.getvalue()


@pytest.mark.parametrize("output_mode", ["file", "stream", "bytes", pytest.param("cli", marks=pytest.mark.e2e)])
def test_template_retains_content_and_styles_when_appending(odp_template, tmp_path, output_mode):
    """Keep template content and master/layout/style definitions while adding slides."""
    original_bytes = odp_template.read_bytes()
    original = load(str(odp_template))
    source = tmp_path / "input.md"
    source.write_text(
        "## Appended title\n\nAppended body.\n\n---\n\n## Another title\n\nAnother body.\n", encoding="utf-8"
    )
    output = tmp_path / "result.odp"
    options = OdpRendererOptions(template_path=str(odp_template))

    if output_mode == "cli":
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "all2md",
                str(source),
                "--out",
                str(output),
                "--odp-renderer-template-path",
                str(odp_template),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        presentation = load(str(output))
    else:
        destination = output if output_mode == "file" else BytesIO() if output_mode == "stream" else None
        result = convert(source, destination, target_format="odp", renderer_options=options)
        if output_mode == "file":
            presentation = load(str(output))
        elif output_mode == "stream":
            destination.seek(0)
            presentation = load(destination)
        else:
            assert isinstance(result, bytes)
            presentation = load(BytesIO(result))

    pages = presentation.getElementsByType(Page)
    original_pages = original.getElementsByType(Page)
    assert len(pages) == 4
    assert [_xml(page) for page in pages[:2]] == [_xml(page) for page in original_pages]
    assert [str(page) for page in pages[2:]] == ["Appended titleAppended body.", "Another titleAnother body."]
    assert [page.getAttribute("masterpagename") for page in pages[2:]] == ["TemplateMaster0", "TemplateMaster0"]
    assert _xml(presentation.masterstyles) == _xml(original.masterstyles)
    assert _xml(presentation.styles) == _xml(original.styles)
    assert [_xml(layout) for layout in presentation.getElementsByType(PageLayout)] == [
        _xml(layout) for layout in original.getElementsByType(PageLayout)
    ]
    assert odp_template.read_bytes() == original_bytes


@pytest.mark.parametrize("invalid_template", ["missing", "corrupt"])
def test_invalid_template_preserves_rendering_error(invalid_template, tmp_path):
    """Expose the actual load failure through the renderer's existing error contract."""
    template = tmp_path / "invalid.odp"
    if invalid_template == "corrupt":
        template.write_bytes(b"not an ODP ZIP archive")
    output = tmp_path / "result.odp"
    renderer = OdpRenderer(OdpRendererOptions(template_path=str(template)))

    with pytest.raises(RenderingError, match="Failed to write ODP file") as exc_info:
        renderer.render(Document(children=[Paragraph(content=[Text(content="Content")])]), output)

    expected = FileNotFoundError if invalid_template == "missing" else BadZipFile
    assert isinstance(exc_info.value.original_error, expected)
    assert exc_info.value.__cause__ is exc_info.value.original_error
    assert exc_info.value.rendering_stage == "rendering"
    assert not output.exists()


def test_without_template_creates_default_master_and_content(tmp_path):
    """Keep the default presentation path working when no template is supplied."""
    source = tmp_path / "input.md"
    source.write_text("## Fresh title\n\nFresh content.\n", encoding="utf-8")
    output = tmp_path / "result.odp"
    convert(source, output, target_format="odp")

    presentation = load(str(output))
    pages = presentation.getElementsByType(Page)
    assert len(pages) == 1
    assert str(pages[0]) == "Fresh titleFresh content."
    assert pages[0].getAttribute("masterpagename") == "Standard"
    masters = presentation.getElementsByType(MasterPage)
    assert len(masters) == 1
    assert masters[0].getAttribute("pagelayoutname") == "StandardLayout"
    assert len(presentation.getElementsByType(PageLayout)) == 1
