"""Footnotes and task-list boxes survive a round trip through DOCX (#621).

The renderer used to write a footnote reference as superscript ``[1]`` text and its
definition as a ``[1]: `` paragraph, and dropped a task item's box altogether, so
Markdown -> DOCX -> Markdown lost both. Footnotes are now Word footnotes, which the
parser already read, and task items open with the box Word's own check box shows.
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from all2md.ast import Document, List, ListItem, Paragraph, Text
from all2md.ast.nodes import FootnoteDefinition, FootnoteReference, Link, Strong
from all2md.options.docx import DocxRendererOptions
from all2md.parsers.docx import DocxToAstConverter
from all2md.renderers.docx import DocxRenderer

docx = pytest.importorskip("docx")

pytestmark = [pytest.mark.unit, pytest.mark.docx]

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "documents"
UNCHECKED, CHECKED = chr(0x2610), chr(0x2612)


def _render(document: Document, options: DocxRendererOptions | None = None) -> bytes:
    buffer = BytesIO()
    DocxRenderer(options).render(document, buffer)
    return buffer.getvalue()


def _parse(data: bytes) -> Document:
    return DocxToAstConverter().parse(BytesIO(data))


def _part(data: bytes, name: str) -> str:
    with zipfile.ZipFile(BytesIO(data)) as package:
        return package.read(name).decode("utf-8")


def _footnotes(data: bytes) -> dict[str, str]:
    """Note id -> its visible text, for every real (non-separator) note."""
    from lxml import etree

    root = etree.fromstring(_part(data, "word/footnotes.xml").encode())
    return {
        note.get(f"{_W}id"): "".join(node.text or "" for node in note.iter(f"{_W}t"))
        for note in root.iter(f"{_W}footnote")
        if note.get(f"{_W}type") is None
    }


def _note(identifier: str, *content) -> FootnoteDefinition:
    return FootnoteDefinition(identifier=identifier, content=[Paragraph(content=list(content))])


def _collect(node, kind) -> list:
    from all2md.ast.nodes import get_node_children

    found, pending = [], [node]
    while pending:
        current = pending.pop(0)
        if isinstance(current, kind):
            found.append(current)
        pending[0:0] = get_node_children(current)
    return found


# ---------------------------------------------------------------------------
# Footnotes
# ---------------------------------------------------------------------------


def test_a_footnote_is_a_word_footnote() -> None:
    data = _render(
        Document(
            children=[
                Paragraph(content=[Text(content="Text with a note."), FootnoteReference(identifier="1")]),
                _note("1", Text(content="The note.")),
            ]
        )
    )

    document_xml = _part(data, "word/document.xml")
    assert '<w:footnoteReference w:id="1"/>' in document_xml
    assert "[1]" not in document_xml
    assert _footnotes(data) == {"1": " The note."}
    # Word names its separator notes in settings, and the content types declare the part.
    assert '<w:footnote w:id="-1"/>' in _part(data, "word/settings.xml")
    assert "footnotes+xml" in _part(data, "[Content_Types].xml")


def test_footnotes_round_trip_with_their_formatting() -> None:
    data = _render(
        Document(
            children=[
                Paragraph(content=[Text(content="Body."), FootnoteReference(identifier="a")]),
                _note("a", Text(content="Has "), Strong(content=[Text(content="bold")]), Text(content=".")),
            ]
        )
    )

    parsed = _parse(data)
    references = _collect(parsed, FootnoteReference)
    definitions = _collect(parsed, FootnoteDefinition)
    assert len(references) == 1
    assert [definition.identifier for definition in definitions] == [references[0].identifier]
    assert _collect(definitions[0], Strong)


def test_a_link_inside_a_note_is_related_from_the_footnotes_part() -> None:
    """Word resolves a note's r:id against footnotes.xml's rels, not document.xml's."""
    data = _render(
        Document(
            children=[
                Paragraph(content=[Text(content="Body."), FootnoteReference(identifier="1")]),
                _note("1", Link(url="https://example.com/", content=[Text(content="example")])),
            ]
        )
    )

    assert "https://example.com/" in _part(data, "word/_rels/footnotes.xml.rels")
    assert "https://example.com/" not in _part(data, "word/_rels/document.xml.rels")
    links = _collect(_collect(_parse(data), FootnoteDefinition)[0], Link)
    assert [link.url for link in links] == ["https://example.com/"]


def test_a_note_of_several_blocks_keeps_them_and_opens_with_the_number_mark() -> None:
    definition = FootnoteDefinition(
        identifier="1",
        content=[
            Paragraph(content=[Text(content="First.")]),
            List(ordered=False, items=[ListItem(children=[Paragraph(content=[Text(content="item")])])]),
            Paragraph(content=[Text(content="Last.")]),
        ],
    )
    data = _render(
        Document(children=[Paragraph(content=[Text(content="Body"), FootnoteReference(identifier="1")]), definition])
    )

    footnotes = _part(data, "word/footnotes.xml")
    note = footnotes[footnotes.index('<w:footnote w:id="1">') :]
    assert note.index("<w:footnoteRef/>") < note.index("First.") < note.index("item") < note.index("Last.")
    assert note.count("<w:footnoteRef/>") == 1
    # The list keeps its own style; the other paragraphs take the note style.
    assert note.count('w:val="FootnoteText"') == 2
    # Nothing of the note leaked into the body.
    assert "First." not in _part(data, "word/document.xml")


def test_a_label_referred_to_twice_gets_a_note_at_each_reference() -> None:
    data = _render(
        Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="One"),
                        FootnoteReference(identifier="x"),
                        Text(content=" two"),
                        FootnoteReference(identifier="x"),
                    ]
                ),
                _note("x", Text(content="Shared.")),
            ]
        )
    )

    assert _footnotes(data) == {"1": " Shared.", "2": " Shared."}


def test_an_undefined_reference_and_an_unreferenced_definition_stay_text() -> None:
    data = _render(
        Document(
            children=[
                Paragraph(content=[Text(content="Dangling"), FootnoteReference(identifier="missing")]),
                _note("orphan", Text(content="Nobody refers to me.")),
            ]
        )
    )

    document_xml = _part(data, "word/document.xml")
    assert "[missing]" in document_xml
    assert "Nobody refers to me." in document_xml
    with zipfile.ZipFile(BytesIO(data)) as package:
        assert "word/footnotes.xml" not in package.namelist()


def test_a_reference_inside_a_note_stays_text() -> None:
    """Word has no notes within notes."""
    data = _render(
        Document(
            children=[
                Paragraph(content=[Text(content="Body"), FootnoteReference(identifier="outer")]),
                _note("outer", Text(content="See"), FootnoteReference(identifier="inner")),
                _note("inner", Text(content="Inner.")),
            ]
        )
    )

    notes = _footnotes(data)
    assert list(notes.values()) == [" See[inner]"]


def test_a_template_with_its_own_footnotes_keeps_them_and_numbers_after_them() -> None:
    """A Word-made template brings footnotes.xml (here with notes 1 and 2) as a bare part."""
    template = _FIXTURES / "footnotes-endnotes-comments.docx"
    data = _render(
        Document(
            children=[
                Paragraph(content=[Text(content="New body"), FootnoteReference(identifier="1")]),
                _note("1", Text(content="A new note.")),
            ]
        ),
        DocxRendererOptions(template_path=str(template)),
    )

    notes = _footnotes(data)
    assert {"1", "2"} <= set(notes)
    assert notes["3"] == " A new note."
    assert '<w:footnoteReference w:id="3"/>' in _part(data, "word/document.xml")
    with zipfile.ZipFile(BytesIO(data)) as package:
        assert package.namelist().count("word/footnotes.xml") == 1


# ---------------------------------------------------------------------------
# Task lists
# ---------------------------------------------------------------------------


def _task_list() -> Document:
    return Document(
        children=[
            List(
                ordered=False,
                items=[
                    ListItem(children=[Paragraph(content=[Text(content="todo")])], task_status="unchecked"),
                    ListItem(children=[Paragraph(content=[Text(content="done")])], task_status="checked"),
                    ListItem(children=[Paragraph(content=[Text(content="plain")])]),
                ],
            )
        ]
    )


def test_task_items_open_with_a_box() -> None:
    texts = [paragraph.text for paragraph in docx.Document(BytesIO(_render(_task_list()))).paragraphs]
    assert texts == [f"{UNCHECKED} todo", f"{CHECKED} done", "plain"]


def test_task_items_round_trip() -> None:
    items = _collect(_parse(_render(_task_list())), ListItem)
    assert [(item.task_status, _collect(item, Text)[0].content) for item in items] == [
        ("unchecked", "todo"),
        ("checked", "done"),
        (None, "plain"),
    ]


@pytest.mark.parametrize(
    ("text", "status", "rest"),
    [
        (f"{UNCHECKED} open", "unchecked", "open"),
        (f"{chr(0x2611)} ticked", "checked", "ticked"),
        (f"{CHECKED}", "checked", None),
        (f"{UNCHECKED}glued", None, f"{UNCHECKED}glued"),
        (f"a {UNCHECKED} later", None, f"a {UNCHECKED} later"),
    ],
)
def test_the_parser_reads_only_a_leading_freestanding_box(text: str, status: str | None, rest: str | None) -> None:
    document = docx.Document()
    document.add_paragraph(text, style="List Bullet")
    if rest is None:
        # A box alone still makes an item: an empty task.
        document.add_paragraph("x", style="List Bullet")
    buffer = BytesIO()
    document.save(buffer)

    item = _collect(_parse(buffer.getvalue()), ListItem)[0]
    assert item.task_status == status
    texts = [node.content for node in _collect(item, Text)]
    assert texts == ([] if rest is None else [rest])
