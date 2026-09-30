"""Text boxes: ``w:txbxContent`` anchored in a run.

A text box holds block content -- paragraphs, tables, even another text box -- inside
a drawing anchored to a run of an ordinary paragraph. Word keeps it in a separate shape
story; the parser reads it as ordinary blocks placed right after the paragraph that
anchors it (mammoth's convention). A modern box is written twice, as a DrawingML shape
under ``mc:Choice`` and as a VML copy under ``mc:Fallback``, and must be read once.

LibreOffice's Writer regression corpus lost 2,359 words across 111 files to unread
text boxes before this was read at all.
"""

from io import BytesIO

import docx
import pytest
from docx.oxml.parser import parse_xml
from PIL import Image as PILImage

from all2md import to_markdown
from all2md.ast.nodes import Image, Table, get_node_children
from all2md.options import DocxOptions
from all2md.parsers.docx import DocxToAstConverter

pytestmark = [pytest.mark.unit, pytest.mark.docx]

NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" '
    'xmlns:v="urn:schemas-microsoft-com:vml"'
)
WPS_URI = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
WPG_URI = "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"


def para(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def shape(blocks: str) -> str:
    return f"<wps:wsp><wps:txbx><w:txbxContent>{blocks}</w:txbxContent></wps:txbx></wps:wsp>"


def drawing(graphic: str, uri: str = WPS_URI) -> str:
    return (
        '<w:drawing><wp:anchor><wp:docPr id="1" name="Text Box 1"/>'
        f'<a:graphic><a:graphicData uri="{uri}">{graphic}</a:graphicData></a:graphic>'
        "</wp:anchor></w:drawing>"
    )


def vml(blocks: str) -> str:
    return f"<w:pict><v:rect><v:textbox><w:txbxContent>{blocks}</w:txbxContent></v:textbox></v:rect></w:pict>"


def dml_box(blocks: str) -> str:
    """A text box as Word writes it: DrawingML under mc:Choice, a VML copy under mc:Fallback."""
    return (
        f'<mc:AlternateContent><mc:Choice Requires="wps">{drawing(shape(blocks))}</mc:Choice>'
        f"<mc:Fallback>{vml(blocks)}</mc:Fallback></mc:AlternateContent>"
    )


def anchor_paragraph(document, before: str, box: str) -> None:
    """Append a paragraph whose text is ``before`` followed by a run anchoring ``box``."""
    paragraph = document.add_paragraph(before)
    paragraph._p.append(parse_xml(f"<w:r {NS}>{box}</w:r>"))


def build(box: str):
    document = docx.Document()
    document.add_paragraph("Opening paragraph.")
    anchor_paragraph(document, "Anchor text.", box)
    document.add_paragraph("Closing paragraph.")
    return document


def save(document) -> bytes:
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def markdown_of(document) -> str:
    return to_markdown(save(document), source_format="docx")


def nodes_of_type(node, kind) -> list:
    found = [node] if isinstance(node, kind) else []
    for child in get_node_children(node):
        found.extend(nodes_of_type(child, kind))
    return found


def test_a_word_text_box_is_read_once_after_its_anchor():
    markdown = markdown_of(build(dml_box(para("Boxed words."))))

    assert markdown.count("Boxed words.") == 1
    assert markdown.index("Anchor text.") < markdown.index("Boxed words.") < markdown.index("Closing paragraph.")


def test_a_vml_only_text_box_is_read():
    markdown = markdown_of(build(vml(para("Legacy box words."))))

    assert markdown.count("Legacy box words.") == 1


def test_a_drawingml_only_text_box_is_read():
    markdown = markdown_of(build(drawing(shape(para("Shape-only words.")))))

    assert markdown.count("Shape-only words.") == 1


def test_every_paragraph_and_table_in_a_box_is_read_in_order():
    table = (
        "<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/></w:tblGrid>"
        f"<w:tr><w:tc>{para('Left cell')}</w:tc><w:tc>{para('Right cell')}</w:tc></w:tr></w:tbl>"
    )
    document = build(dml_box(para("First boxed.") + table + para("Last boxed.")))

    markdown = markdown_of(document)
    assert markdown.index("First boxed.") < markdown.index("Left cell") < markdown.index("Last boxed.")
    assert markdown.count("Right cell") == 1
    ast = DocxToAstConverter().parse(BytesIO(save(document)))
    assert len(nodes_of_type(ast, Table)) == 1


def test_every_box_in_a_group_shape_is_read():
    group = f"<wpg:wgp>{shape(para('Grouped one.'))}{shape(para('Grouped two.'))}</wpg:wgp>"
    box = (
        f'<mc:AlternateContent><mc:Choice Requires="wpg">{drawing(group, WPG_URI)}</mc:Choice>'
        f"<mc:Fallback>{vml(para('Grouped one.'))}{vml(para('Grouped two.'))}</mc:Fallback></mc:AlternateContent>"
    )

    markdown = markdown_of(build(box))

    assert markdown.count("Grouped one.") == 1
    assert markdown.count("Grouped two.") == 1


def test_a_box_inside_a_box_is_read_once_after_its_own_anchor():
    inner_anchor = f"<w:p><w:r><w:t>Outer words.</w:t></w:r><w:r>{dml_box(para('Inner words.'))}</w:r></w:p>"

    markdown = markdown_of(build(dml_box(inner_anchor)))

    assert markdown.count("Outer words.") == 1
    assert markdown.count("Inner words.") == 1
    assert markdown.index("Outer words.") < markdown.index("Inner words.")


def test_a_fallback_is_read_when_its_choice_holds_no_text_box():
    # A linked text box continues another box's story: its DrawingML half carries no
    # txbxContent of its own, so the fallback is the only copy there is.
    box = (
        f'<mc:AlternateContent><mc:Choice Requires="wps">{drawing("<wps:wsp/>")}</mc:Choice>'
        f"<mc:Fallback>{vml(para('Fallback-only words.'))}</mc:Fallback></mc:AlternateContent>"
    )

    assert markdown_of(build(box)).count("Fallback-only words.") == 1


def test_a_picture_inside_a_box_is_read_once(tmp_path):
    picture = tmp_path / "dot.png"
    PILImage.new("RGB", (4, 4), "red").save(picture)
    document = docx.Document()
    document.add_paragraph("Opening paragraph.")
    document.add_picture(str(picture))
    picture_paragraph = document.paragraphs[-1]._p
    anchor_paragraph(document, "Anchor text.", drawing(shape(para("Caption in box."))))
    # Move the picture's paragraph into the text box, after the box's own paragraph.
    txbx = document.paragraphs[-1]._p.xpath(".//w:txbxContent")[0]
    txbx.append(picture_paragraph)

    ast = DocxToAstConverter(options=DocxOptions(attachment_mode="base64")).parse(BytesIO(save(document)))

    assert len(nodes_of_type(ast, Image)) == 1


def test_a_document_without_boxes_is_unchanged():
    document = docx.Document()
    document.add_paragraph("Only prose.")

    assert markdown_of(document).strip() == "Only prose."
