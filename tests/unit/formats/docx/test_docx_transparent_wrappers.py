"""Wrappers that change how runs are shown or tagged, never what they say.

``w:dir`` and ``w:bdo`` set the direction of the runs inside them (Word writes them
around Arabic and Hebrew text), ``w:smartTag`` marks a recognised name, place or date,
and ``w:customXml`` binds content to a custom schema. Like a content control, each puts
its runs one level below where every reader looks, so a paragraph read its runs past
them as if they were not there. LibreOffice's Writer regression corpus lost all 71
words of one Arabic file (tdf119143) this way, and words in files with smart tags.
"""

from io import BytesIO

import docx
import pytest
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from all2md import to_markdown
from all2md.parsers.docx_sdt import document_has_transparent_wrappers, unwrap_transparent_wrappers

pytestmark = [pytest.mark.unit, pytest.mark.docx]


def run(text: str, bold: bool = False):
    element = OxmlElement("w:r")
    if bold:
        properties = OxmlElement("w:rPr")
        properties.append(OxmlElement("w:b"))
        element.append(properties)
    text_element = OxmlElement("w:t")
    text_element.text = text
    text_element.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    element.append(text_element)
    return element


def wrapper(tag: str, *content, **attributes):
    """A ``w:<tag>`` around ``content``, with the properties child Word writes for it."""
    element = OxmlElement(f"w:{tag}")
    for name, value in attributes.items():
        element.set(qn(f"w:{name}"), value)
    if tag in ("smartTag", "customXml"):
        properties = OxmlElement(f"w:{tag}Pr")
        attribute = OxmlElement("w:attr")
        attribute.set(qn("w:name"), "hidden")
        attribute.set(qn("w:val"), "PROPERTY TEXT")
        properties.append(attribute)
        element.append(properties)
    for child in content:
        element.append(child)
    return element


def markdown_of(document) -> str:
    buffer = BytesIO()
    document.save(buffer)
    return to_markdown(buffer.getvalue(), source_format="docx")


def sentence_around(element) -> str:
    document = docx.Document()
    paragraph = document.add_paragraph()
    paragraph.add_run("Before ")
    paragraph.add_run(" after.")._r.addprevious(element)
    return markdown_of(document)


@pytest.mark.parametrize(
    ("tag", "attributes"),
    [
        ("dir", {"val": "rtl"}),
        ("bdo", {"val": "rtl"}),
        ("smartTag", {"uri": "urn:schemas-microsoft-com:office:smarttags", "element": "place"}),
        ("customXml", {"element": "clause"}),
    ],
)
def test_wrapped_runs_keep_their_place_in_the_sentence(tag, attributes):
    markdown = sentence_around(wrapper(tag, run("WRAPPED"), **attributes))

    assert "Before WRAPPED after." in markdown
    assert "PROPERTY TEXT" not in markdown


def test_right_to_left_text_is_written_in_reading_order():
    arabic = "مرحبا بك"
    markdown = sentence_around(wrapper("dir", run(arabic), val="rtl"))

    assert f"Before {arabic} after." in markdown


def test_nested_wrappers_and_their_formatting_are_kept():
    inner = wrapper("smartTag", run("Bold place", bold=True), element="place")
    markdown = sentence_around(wrapper("dir", run("Plain "), inner, val="rtl"))

    assert "Before Plain **Bold place** after." in markdown


def test_a_hyperlink_inside_a_wrapper_is_still_a_link():
    document = docx.Document()
    paragraph = document.add_paragraph()
    paragraph.add_run("See ")
    relationship = document.part.relate_to(
        "https://example.com/", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", True
    )
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), relationship)
    link.append(run("the site"))
    paragraph.add_run(".")._r.addprevious(wrapper("smartTag", link, element="place"))

    assert "See [the site](https://example.com/)." in markdown_of(document)


def test_block_level_custom_xml_does_not_swallow_its_paragraph_or_table():
    document = docx.Document()
    document.add_paragraph("Intro.")
    wrapped = document.add_paragraph("Bound paragraph.")._p
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Bound cell."
    body = document.element.body
    for element in (wrapped, table._tbl):
        index = body.index(element)
        body.remove(element)
        body.insert(index, wrapper("customXml", element, element="block"))

    markdown = markdown_of(document)

    assert "Bound paragraph." in markdown
    assert "Bound cell." in markdown


def test_unwrapping_reports_what_it_removed_and_leaves_plain_documents_alone():
    document = docx.Document()
    paragraph = document.add_paragraph("Plain.")
    root = document.element
    assert not document_has_transparent_wrappers(root)
    assert unwrap_transparent_wrappers(root) == 0

    paragraph._p.append(wrapper("dir", wrapper("bdo", run("x"), val="ltr"), val="rtl"))
    assert document_has_transparent_wrappers(root)
    assert unwrap_transparent_wrappers(root) == 2
    assert not document_has_transparent_wrappers(root)
    assert [child.tag for child in paragraph._p] == [qn("w:r"), qn("w:r")]
