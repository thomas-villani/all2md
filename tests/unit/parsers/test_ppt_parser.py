#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for the PowerPoint 97-2003 (.ppt) parser.

Two kinds of input: ``basic.ppt``, which PowerPoint itself saved from the
``basic.pptx`` beside it, and presentations laid out record by record by
:func:`build_ppt`, for the layouts PowerPoint does not produce on request
(outline text, edit chains, a missing Current User stream) and for broken files.
"""

from __future__ import annotations

import re
import struct
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from all2md import to_markdown
from all2md.ast import Comment, Heading, LineBreak, Link, List, Paragraph, Text, ThematicBreak
from all2md.converter_registry import registry
from all2md.exceptions import All2MdError, FormatError, MalformedFileError, PasswordProtectedError
from all2md.options.ppt import PptOptions
from all2md.options.pptx import PptxOptions
from all2md.parsers.ppt import PptParser

from ..utils.cfb_builder import build

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "documents"

CR = chr(13)
VT = chr(11)

TITLE, BODY, NOTES, OTHER, CENTER_BODY, CENTER_TITLE = 0, 1, 2, 4, 5, 6


def record(record_type: int, body: bytes = b"", instance: int = 0) -> bytes:
    return struct.pack("<HHI", instance << 4, record_type, len(body)) + body


def container(record_type: int, *children: bytes, instance: int = 0) -> bytes:
    body = b"".join(children)
    return struct.pack("<HHI", (instance << 4) | 0xF, record_type, len(body)) + body


def text_records(
    text_type: int,
    text: str,
    *,
    unicode: bool = True,
    runs: list[tuple[int, int, int | None]] | None = None,
    extra: tuple[bytes, ...] = (),
) -> list[bytes]:
    """Return the records of one text: header, characters, paragraph runs, then ``extra``.

    ``runs`` are (characters, indent level, bullet flag or None) per paragraph.
    """
    records = [record(0x0F9F, struct.pack("<I", text_type))]
    records.append(record(0x0FA0, text.encode("utf-16-le")) if unicode else record(0x0FA8, text.encode("latin-1")))
    if runs is not None:
        style = b""
        for count, level, bullet in runs:
            if bullet is None:
                style += struct.pack("<IHI", count, level, 0)
            else:
                style += struct.pack("<IHIH", count, level, 0x0001, int(bullet))
        records.append(record(0x0FA1, style))
    records.extend(extra)
    return records


def text_box(*records: bytes) -> bytes:
    """A shape whose client textbox holds ``records``."""
    return container(0xF004, record(0xF00A, bytes(8)), container(0xF00D, *records))


def outline_ref(index: int) -> bytes:
    return text_box(record(0x0F9E, struct.pack("<I", index)))


def hyperlink(link_id: int, start: int, end: int) -> tuple[bytes, ...]:
    info = container(0x0FF2, record(0x0FF3, struct.pack("<IIBBBB", 0, link_id, 4, 0, 0, 0) + bytes(4)))
    return info, record(0x0FDF, struct.pack("<II", start, end))


def comment(author: str, text: str, initials: str = "") -> bytes:
    def cstring(value: str, instance: int) -> bytes:
        return record(0x0FBA, value.encode("utf-16-le"), instance)

    item = container(0x2EE0, cstring(author, 0), cstring(text, 1), cstring(initials, 2), record(0x2EE1, bytes(28)))
    blob = record(0x138B, item)
    tag = container(0x138A, record(0x0FBA, "___PPT10".encode("utf-16-le")), blob)
    return container(0x1388, tag)


@dataclass
class Slide:
    shapes: list[bytes] = field(default_factory=list)
    outline: list[bytes] = field(default_factory=list)
    notes: list[bytes] | None = None
    tail: list[bytes] = field(default_factory=list)


def _drawing(shapes: list[bytes]) -> bytes:
    group = container(0xF003, container(0xF004, record(0xF009, bytes(16)), record(0xF00A, bytes(8))), *shapes)
    return container(0x040C, container(0xF002, record(0xF008, bytes(8)), group))


def build_ppt(
    slides: list[Slide],
    *,
    hyperlinks: dict[int, str] | None = None,
    current_user: bool = True,
    token: int = 0xE391C05F,
    encrypt_ref: int | None = None,
    later_edit: dict[int, Slide] | None = None,
    streams: dict[str, bytes] | None = None,
) -> bytes:
    """Lay out a presentation: document, slides and notes, persist directory, edit atom.

    ``later_edit`` replaces the slides at the given indexes in a second save
    appended to the stream, as an incremental save does.
    """
    # Persist ids: 1 document, then for slide i: 2 + 2i the slide, 3 + 2i its notes.
    slide_list = b""
    notes_list = b""
    for index, slide in enumerate(slides):
        slide_list += record(0x03F3, struct.pack("<IIIII", 2 + 2 * index, 0, len(slide.outline), 256 + index, 0))
        slide_list += b"".join(slide.outline)
        if slide.notes is not None:
            notes_list += record(0x03F3, struct.pack("<IIIII", 3 + 2 * index, 0, 0, 512 + index, 0))
    links = b""
    for link_id, target in (hyperlinks or {}).items():
        links += container(
            0x0FD7,
            record(0x0FD3, struct.pack("<I", link_id)),
            record(0x0FBA, target.encode("utf-16-le"), 0),
            record(0x0FBA, target.encode("utf-16-le"), 1),
        )
    document = container(
        0x03E8,
        record(0x03E9, bytes(40)),
        container(0x0409, record(0x040A, bytes(4)), links) if links else b"",
        container(0x0FF0, slide_list, instance=0),
        container(0x0FF0, notes_list, instance=2) if notes_list else b"",
        record(0x03EA),
    )
    stream = bytearray(document)
    offsets = {1: 0}

    def add_slide(index: int, slide: Slide) -> None:
        notes_id = 512 + index if slide.notes is not None else 0
        atom = record(0x03EF, struct.pack("<I8BIIHH", 0, *([0] * 8), 0, notes_id, 0, 0))
        offsets[2 + 2 * index] = len(stream)
        stream.extend(container(0x03EE, atom, _drawing(slide.shapes), *slide.tail))
        if slide.notes is not None:
            offsets[3 + 2 * index] = len(stream)
            stream.extend(container(0x03F0, record(0x03F1, bytes(8)), _drawing(slide.notes)))

    for index, slide in enumerate(slides):
        add_slide(index, slide)

    def add_edit(entries: dict[int, int], last_edit: int) -> int:
        directory = b""
        for persist_id in sorted(entries):
            directory += struct.pack("<II", persist_id | (1 << 20), entries[persist_id])
        directory_offset = len(stream)
        stream.extend(record(0x1772, directory))
        edit_offset = len(stream)
        body = struct.pack("<IHBBIIIIHH", 0, 0, 0, 3, last_edit, directory_offset, 1, 1 + 2 * len(slides), 1, 0)
        if encrypt_ref is not None:
            body += struct.pack("<I", encrypt_ref)
        stream.extend(record(0x0FF5, body))
        return edit_offset

    edit = add_edit(dict(offsets), 0)
    if later_edit:
        offsets.clear()
        for index, slide in later_edit.items():
            add_slide(index, slide)
        edit = add_edit(dict(offsets), edit)

    all_streams = {"PowerPoint Document": bytes(stream)}
    if current_user:
        user = struct.pack("<IIIHHBBH", 20, token, edit, 0, 0x03F4, 3, 0, 0)
        all_streams["Current User"] = record(0x0FF6, user)
    all_streams.update(streams or {})
    return build(all_streams).data


def _parse(data: bytes, **options) -> list:
    return PptParser(PptOptions(**options)).parse(data).children


def _texts(nodes) -> str:
    out = []
    for node in nodes:
        if isinstance(node, Text):
            out.append(node.content)
        elif isinstance(node, LineBreak):
            out.append("|")
        elif hasattr(node, "content") and isinstance(node.content, list):
            out.append(_texts(node.content))
    return "".join(out)


def _words(markdown: str) -> Counter:
    """Words of the text alone: link targets, HTML tags and ordered-list numbers are syntax."""
    markdown = re.sub(r"\]\([^)]*\)", "]", markdown)
    markdown = re.sub(r"<[^>]+>", " ", markdown)
    markdown = re.sub(r"(?m)^\s*\d+\.\s", " ", markdown)
    return Counter(re.findall(r"\w+", markdown.lower()))


def _slide(title: str = "Title", body: str = "One") -> Slide:
    return Slide(shapes=[text_box(*text_records(TITLE, title)), text_box(*text_records(BODY, body))])


@pytest.mark.unit
class TestPowerPointFixture:
    """A presentation PowerPoint saved as .ppt reads with the same text as its .pptx."""

    def test_same_words_as_the_pptx(self):
        ppt = to_markdown(FIXTURES / "basic.ppt")
        pptx = to_markdown(FIXTURES / "basic.pptx", parser_options=PptxOptions(attachment_mode="skip"))
        assert _words(ppt) == _words(pptx)

    def test_slides_are_separated_and_titled(self):
        children = PptParser().parse(FIXTURES / "basic.ppt").children
        assert sum(isinstance(node, ThematicBreak) for node in children) == 5
        assert any(isinstance(node, Heading) and node.level == 2 for node in children)

    def test_metadata(self):
        metadata = PptParser().parse(FIXTURES / "basic.ppt").metadata
        assert metadata["slide_count"] == 5

    def test_detected_by_streams(self):
        assert registry.detect_format((FIXTURES / "basic.ppt").read_bytes()) == "ppt"

    @pytest.mark.parametrize("suffix", [".ppt", ".pps", ".pot"])
    def test_detected_by_extension(self, tmp_path, suffix):
        path = tmp_path / f"deck{suffix}"
        path.write_bytes(build_ppt([_slide()]))
        assert registry.detect_format(str(path)) == "ppt"


@pytest.mark.unit
class TestSlides:
    """Titles, body text, lists and text boxes."""

    def test_title_and_bulleted_body(self):
        children = _parse(build_ppt([_slide("Agenda", f"First{CR}Second")]))
        assert isinstance(children[0], Heading) and _texts(children[0].content) == "Agenda"
        assert isinstance(children[1], List)
        assert [_texts(item.children) for item in children[1].items] == ["First", "Second"]
        assert isinstance(children[2], ThematicBreak)

    def test_indent_levels_nest(self):
        runs = [(4, 0, None), (4, 1, None), (4, 1, None), (4, 0, None)]
        body = text_records(BODY, f"One{CR}Two{CR}Thr{CR}Fou", runs=runs)
        children = _parse(build_ppt([Slide(shapes=[text_box(*body)])]))
        outer = children[0]
        assert [_texts(item.children[:1]) for item in outer.items] == ["One", "Fou"]
        inner = outer.items[0].children[1]
        assert isinstance(inner, List) and [_texts(item.children) for item in inner.items] == ["Two", "Thr"]

    def test_one_run_covers_several_paragraphs(self):
        runs = [(8, 0, None), (8, 1, None), (4, 0, None)]
        body = text_records(BODY, f"One{CR}Two{CR}Thr{CR}Fou{CR}Fiv", runs=runs)
        outer = _parse(build_ppt([Slide(shapes=[text_box(*body)])]))[0]
        assert [_texts(item.children[:1]) for item in outer.items] == ["One", "Two", "Fiv"]
        inner = outer.items[1].children[1]
        assert [_texts(item.children) for item in inner.items] == ["Thr", "Fou"]

    def test_nested_list_in_the_fixture(self):
        children = PptParser().parse(FIXTURES / "basic.ppt").children
        lists = [node for node in children if isinstance(node, List)]
        nested = [item for item in lists[1].items if any(isinstance(child, List) for child in item.children)]
        assert len(nested) == 1
        assert _texts(nested[0].children[:1]) == "And we’ll do a nested list"

    def test_explicit_bullet_flags_override_the_text_type(self):
        body = text_records(BODY, f"Plain{CR}Dot", runs=[(6, 0, False), (4, 0, True)])
        box = text_records(OTHER, f"Box{CR}Item", runs=[(4, 0, None), (4, 0, True)])
        children = _parse(build_ppt([Slide(shapes=[text_box(*body), text_box(*box)])]))
        kinds = [(type(node).__name__, _texts([node]) if isinstance(node, Paragraph) else None) for node in children]
        assert kinds[:4] == [("Paragraph", "Plain"), ("List", None), ("Paragraph", "Box"), ("List", None)]

    def test_text_box_and_subtitle_are_paragraphs(self):
        shapes = [
            text_box(*text_records(CENTER_TITLE, "Deck")),
            text_box(*text_records(CENTER_BODY, "Subtitle")),
            text_box(*text_records(OTHER, "Loose text")),
        ]
        children = _parse(build_ppt([Slide(shapes=shapes)]))
        assert isinstance(children[0], Heading)
        assert [_texts([node]) for node in children[1:3]] == ["Subtitle", "Loose text"]

    def test_bytes_and_unicode_text(self):
        shapes = [text_box(*text_records(OTHER, "Café", unicode=False)), text_box(*text_records(OTHER, "Ωμέγα ✓"))]
        children = _parse(build_ppt([Slide(shapes=shapes)]))
        assert [_texts([node]) for node in children[:2]] == ["Café", "Ωμέγα ✓"]

    def test_vertical_tab_is_a_line_break(self):
        children = _parse(build_ppt([Slide(shapes=[text_box(*text_records(OTHER, f"Line one{VT}line two"))])]))
        assert _texts([children[0]]) == "Line one|line two"

    def test_empty_paragraphs_dropped(self):
        children = _parse(build_ppt([Slide(shapes=[text_box(*text_records(OTHER, f"{CR}A{CR}{CR}  {CR}B{CR}"))])]))
        assert [_texts([node]) for node in children if isinstance(node, Paragraph)] == ["A", "B"]

    def test_slide_number_field(self):
        meta = record(0x0FD8, struct.pack("<I", 6))
        box = text_box(*text_records(OTHER, "Slide *", extra=(meta,)))
        children = _parse(build_ppt([_slide(), Slide(shapes=[box])]))
        assert _texts([node for node in children if isinstance(node, Paragraph)][-1:]) == "Slide 2"

    def test_slide_number_placeholder_skipped(self):
        """A box that is only a field is page furniture, as the PPTX parser treats it."""
        meta = record(0x0FD8, struct.pack("<I", 0))
        children = _parse(build_ppt([Slide(shapes=[text_box(*text_records(OTHER, "*", extra=(meta,)))])]))
        assert children == []

    def test_other_fields_dropped(self):
        meta = record(0x0FF7, struct.pack("<I", 0))
        children = _parse(build_ppt([Slide(shapes=[text_box(*text_records(OTHER, "*Today", extra=(meta,)))])]))
        assert _texts([children[0]]) == "Today"

    def test_hyperlink(self):
        box = text_box(*text_records(OTHER, "See the site now", extra=hyperlink(7, 4, 12)))
        children = _parse(build_ppt([Slide(shapes=[box])], hyperlinks={7: "https://example.com/"}))
        content = children[0].content
        assert _texts(content[:1]) == "See "
        assert isinstance(content[1], Link) and content[1].url == "https://example.com/"
        assert _texts(content[1].content) == "the site"

    def test_unknown_hyperlink_is_plain_text(self):
        box = text_box(*text_records(OTHER, "See the site", extra=hyperlink(9, 4, 12)))
        children = _parse(build_ppt([Slide(shapes=[box])]))
        assert not any(isinstance(node, Link) for node in children[0].content)

    def test_comments(self):
        slide = _slide()
        slide.tail = [comment("Ada Lovelace", "Check this", "AL")]
        children = _parse(build_ppt([slide]))
        comments = [node for node in children if isinstance(node, Comment)]
        assert len(comments) == 1
        assert comments[0].content == "Check this"
        assert comments[0].metadata["author"] == "Ada Lovelace"
        assert comments[0].metadata["slide_number"] == 1

    def test_empty_slide_leaves_no_separator(self):
        children = _parse(build_ppt([Slide(), _slide()]))
        assert sum(isinstance(node, ThematicBreak) for node in children) == 1


@pytest.mark.unit
class TestOutlineText:
    """Older PowerPoint keeps placeholder text in the slide list; the drawing refers to it."""

    def test_reference_resolved_in_drawing_order(self):
        outline = [*text_records(TITLE, "Outline title"), *text_records(BODY, "Outline body")]
        slide = Slide(shapes=[outline_ref(0), text_box(*text_records(OTHER, "Box")), outline_ref(1)], outline=outline)
        children = _parse(build_ppt([slide]))
        assert isinstance(children[0], Heading) and _texts(children[0].content) == "Outline title"
        assert _texts([children[1]]) == "Box"
        assert isinstance(children[2], List)

    def test_unreferenced_outline_text_kept(self):
        slide = Slide(outline=[*text_records(TITLE, "Only here")])
        children = _parse(build_ppt([slide]))
        assert _texts(children[0].content) == "Only here"

    def test_reference_out_of_range_ignored(self):
        children = _parse(build_ppt([Slide(shapes=[outline_ref(5), text_box(*text_records(OTHER, "Kept"))])]))
        assert _texts([children[0]]) == "Kept"


@pytest.mark.unit
class TestNotes:
    """Speaker notes, as the PPTX parser reads them."""

    def _deck(self):
        slide = _slide()
        slide.notes = [text_box(*text_records(NOTES, f"Say this{CR}Then that"))]
        return build_ppt([slide])

    def test_notes_under_a_heading(self):
        children = _parse(self._deck())
        index = next(i for i, node in enumerate(children) if isinstance(node, Heading) and node.level == 3)
        assert _texts(children[index].content) == "Speaker Notes"
        assert [_texts([node]) for node in children[index + 1 : index + 3]] == ["Say this", "Then that"]

    def test_notes_as_comment(self):
        children = _parse(self._deck(), comment_mode="comment")
        notes = [node for node in children if isinstance(node, Comment)]
        assert notes[0].content == "Say this\nThen that"
        assert notes[0].metadata["comment_type"] == "ppt_speaker_notes"

    @pytest.mark.parametrize("options", [{"include_notes": False}, {"comment_mode": "ignore"}])
    def test_notes_left_out(self, options):
        children = _parse(self._deck(), **options)
        assert "Say this" not in "".join(_texts([node]) for node in children)

    def test_only_the_notes_text_is_read(self):
        """A notes page also shows the slide's image and may carry other boxes."""
        slide = _slide()
        slide.notes = [text_box(*text_records(OTHER, "Header text")), text_box(*text_records(NOTES, "Note"))]
        markdown = to_markdown(build_ppt([slide]), source_format="ppt")
        assert "Note" in markdown and "Header text" not in markdown


@pytest.mark.unit
class TestOptions:
    def test_slide_selection(self):
        children = _parse(build_ppt([_slide("A"), _slide("B"), _slide("C")]), slides="1,3")
        assert [_texts(node.content) for node in children if isinstance(node, Heading)] == ["A", "C"]

    def test_slide_numbers(self):
        children = _parse(build_ppt([_slide("A"), _slide("B")]), include_slide_numbers=True)
        assert [_texts(node.content) for node in children if isinstance(node, Heading)] == ["Slide 1: A", "Slide 2: B"]

    def test_titles_as_paragraphs(self):
        children = _parse(build_ppt([_slide("A")]), include_titles_as_h2=False)
        assert not any(isinstance(node, Heading) for node in children)
        assert _texts([children[0]]) == "A"


@pytest.mark.unit
class TestEdits:
    """The live records are found through the edit chain, newest first."""

    def test_incremental_save_replaces_a_slide(self):
        data = build_ppt([_slide("Old A"), _slide("B")], later_edit={0: _slide("New A")})
        titles = [_texts(node.content) for node in _parse(data) if isinstance(node, Heading)]
        assert titles == ["New A", "B"]

    def test_missing_current_user_falls_back_to_the_last_edit(self):
        data = build_ppt([_slide("Old A")], later_edit={0: _slide("New A")}, current_user=False)
        assert [_texts(node.content) for node in _parse(data) if isinstance(node, Heading)] == ["New A"]


@pytest.mark.unit
class TestRejected:
    def test_encrypted_by_current_user_token(self):
        with pytest.raises(PasswordProtectedError):
            _parse(build_ppt([_slide()], token=0xF3D1C4DF))

    def test_encrypted_by_edit_atom(self):
        with pytest.raises(PasswordProtectedError):
            _parse(build_ppt([_slide()], encrypt_ref=9))

    def test_another_container(self):
        data = build({"WordDocument": bytes(64), "1Table": bytes(64)}).data
        with pytest.raises(FormatError, match="Word 97-2003 document"):
            _parse(data)

    def test_not_a_container(self):
        with pytest.raises(FormatError):
            _parse(b"plain text")

    def test_no_edit_record(self):
        data = build({"PowerPoint Document": record(0x03E8)}).data
        with pytest.raises(MalformedFileError, match="edit record"):
            _parse(data)

    @settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(st.data())
    def test_mutations_raise_only_all2md_errors(self, draw):
        slide = _slide("Título", f"Uno{CR}Dos")
        slide.notes = [text_box(*text_records(NOTES, "Notes"))]
        slide.tail = [comment("A", "B")]
        data = bytearray(build_ppt([slide, _slide()], hyperlinks={1: "https://example.com/"}))
        if draw.draw(st.booleans()):
            data = data[: draw.draw(st.integers(0, len(data)))]
        else:
            for _ in range(draw.draw(st.integers(1, 6))):
                data[draw.draw(st.integers(0, len(data) - 1))] = draw.draw(st.integers(0, 255))
        try:
            _parse(bytes(data))
        except All2MdError:
            pass
