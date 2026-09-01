"""Word field codes, which store an instruction beside the result Word computed.

Nothing here evaluates a field. The cached result is already in the document -- it is
what the page prints -- so the job is to read the half Word displays and drop the half
it does not, and to keep whatever the instruction still means.
"""

import docx
import pytest
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from all2md import to_markdown
from all2md.parsers.docx_fields import (
    document_has_fields,
    field_target,
    hyperlink_target,
    resolve_fields,
    split_instruction,
)

pytestmark = [pytest.mark.unit, pytest.mark.docx]

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def body(inner: str):
    """Parse a one-paragraph document from raw run markup."""
    return etree.fromstring(f'<w:document xmlns:w="{W}"><w:body><w:p>{inner}</w:p></w:body></w:document>'.encode())


def visible(root) -> str:
    return "".join(node.text or "" for node in root.iter(f"{{{W}}}t"))


def marker(kind: str) -> str:
    return f'<w:r><w:fldChar w:fldCharType="{kind}"/></w:r>'


def instruction(text: str) -> str:
    return f'<w:r><w:instrText xml:space="preserve">{text}</w:instrText></w:r>'


def run(text: str) -> str:
    return f"<w:r><w:t>{text}</w:t></w:r>"


def targets(root) -> set:
    return {field_target(r) for r in root.iter(f"{{{W}}}r")} - {None}


# ------------------------------------------------------------------ reading instructions
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (' HYPERLINK "https://example.com/a" ', "https://example.com/a"),
        # Word quotes any argument with a space in it, and a URL routinely has one.
        (' HYPERLINK "https://example.com/a b" ', "https://example.com/a b"),
        (" HYPERLINK https://bare.example ", "https://bare.example"),
        (r' HYPERLINK "https://example.com/a" \* MERGEFORMAT ', "https://example.com/a"),
        # `\l` targets a bookmark inside the document, not a URL.
        (r' HYPERLINK \l "bookmark" ', None),
        (r" REF Target \h ", None),
        (r' TOC \o "1-3" ', None),
        ("", None),
    ],
)
def test_hyperlink_target_reads_the_instruction(text, expected):
    assert hyperlink_target(text) == expected


def test_a_quoted_argument_stays_one_token():
    assert split_instruction(' HYPERLINK "a b" \\* X ') == ["HYPERLINK", "a b", "\\*", "X"]


# ------------------------------------------------------------------------ the fldChar form
def test_the_instruction_goes_and_the_result_stays():
    root = body(run("A") + marker("begin") + instruction(" PAGE ") + marker("separate") + run("7") + marker("end"))

    assert resolve_fields(root) == 1
    assert visible(root) == "A7"


def test_a_field_that_was_never_computed_shows_nothing():
    # No `separate`, so there is no cached result -- only an instruction, which is
    # not text the page ever printed.
    root = body(run("A") + marker("begin") + instruction(" PAGE ") + marker("end") + run("B"))

    assert resolve_fields(root) == 1
    assert visible(root) == "AB"


def test_a_hyperlink_field_marks_the_runs_it_displayed():
    root = body(
        marker("begin")
        + instruction(' HYPERLINK "https://example.com/t" ')
        + marker("separate")
        + run("click here")
        + marker("end")
    )

    resolve_fields(root)
    assert visible(root) == "click here"
    assert targets(root) == {"https://example.com/t"}


def test_a_field_inside_another_field_s_instruction_does_not_leak():
    # The inner field computes part of the outer instruction; its result was never
    # on the page. The outer instruction is still assembled across it.
    root = body(
        marker("begin")
        + instruction(" HYPERLINK ")
        + marker("begin")
        + instruction(" MERGEFIELD X ")
        + marker("separate")
        + run("INNER")
        + marker("end")
        + instruction(' "https://example.com/n" ')
        + marker("separate")
        + run("shown")
        + marker("end")
    )

    assert resolve_fields(root) == 2
    assert visible(root) == "shown"
    assert targets(root) == {"https://example.com/n"}


def test_an_end_with_no_begin_leaves_the_text_alone():
    # Word writes this whenever a field spans a paragraph boundary and the tree is
    # read from part-way through; it must never eat surrounding prose.
    root = body(run("A") + marker("end") + run("B"))

    assert resolve_fields(root) == 0
    assert visible(root) == "AB"


def test_a_begin_that_is_never_closed_still_shows_its_result():
    root = body(run("A") + marker("begin") + instruction(" TOC ") + marker("separate") + run("entry"))

    resolve_fields(root)
    assert visible(root) == "Aentry"


def test_a_field_spanning_paragraphs_is_resolved_as_one():
    xml = (
        f'<w:document xmlns:w="{W}"><w:body>'
        f"<w:p>{marker('begin')}{instruction(' REF Target ')}{marker('separate')}{run('resolved text')}</w:p>"
        f"<w:p>{marker('end')}{run('after')}</w:p>"
        f"</w:body></w:document>"
    )
    root = etree.fromstring(xml.encode())

    assert resolve_fields(root) == 1
    assert visible(root) == "resolved textafter"


# ----------------------------------------------------------------------- the fldSimple form
def test_a_simple_field_gives_up_the_result_it_wraps():
    # The result is a *child* run, so python-docx never saw it -- the same grandchild
    # problem a content control has.
    root = body(run("Figure ") + '<w:fldSimple w:instr=" SEQ Figure "><w:r><w:t>1</w:t></w:r></w:fldSimple>')

    assert resolve_fields(root) == 1
    assert visible(root) == "Figure 1"


def test_a_simple_hyperlink_field_marks_its_runs_too():
    root = body("<w:fldSimple w:instr=' HYPERLINK \"https://example.com/s\" '><w:r><w:t>go</w:t></w:r></w:fldSimple>")

    resolve_fields(root)
    assert visible(root) == "go"
    assert targets(root) == {"https://example.com/s"}


# --------------------------------------------------------------------------------- gating
def test_a_document_without_fields_is_left_alone():
    document = docx.Document()
    document.add_paragraph("Ordinary text.")

    assert document_has_fields(document.element) is False
    assert resolve_fields(document.element) == 0


def test_a_document_with_a_field_is_recognised():
    document = docx.Document()
    paragraph = document.add_paragraph()
    simple = OxmlElement("w:fldSimple")
    simple.set(qn("w:instr"), " PAGE ")
    paragraph._p.append(simple)

    assert document_has_fields(document.element) is True


# ------------------------------------------------------------------------------ end to end
def test_a_hyperlink_field_becomes_a_link_in_the_markdown(tmp_path):
    document = docx.Document()
    paragraph = document.add_paragraph()
    for fragment in (
        marker("begin"),
        instruction(' HYPERLINK "https://example.com/target" '),
        marker("separate"),
        run("the link text"),
        marker("end"),
    ):
        paragraph._p.append(etree.fromstring(f'<root xmlns:w="{W}">{fragment}</root>'.encode())[0])

    path = tmp_path / "field.docx"
    document.save(str(path))

    assert "[the link text](https://example.com/target)" in to_markdown(str(path))
