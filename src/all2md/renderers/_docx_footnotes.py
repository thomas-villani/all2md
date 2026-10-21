#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/_docx_footnotes.py
"""Word footnotes for the DOCX renderer: the footnotes part, its styles and its ids.

python-docx has no footnotes part. A document it creates has none, and one it opens from a
template gets a bare ``Part`` holding the XML as bytes, which nothing can add a note to.
This module gives the renderer a footnotes part it can write into: a ``StoryPart``, so a
paragraph inside a note resolves hyperlinks and images against the footnotes part's own
relationships, as Word requires, rather than the main document's.

Imported only from inside the renderer's render path, after python-docx is known to be
installed.
"""

from __future__ import annotations

from typing import Any

from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.oxml import OxmlElement
from docx.oxml.ns import nsdecls, qn
from docx.oxml.parser import parse_xml
from docx.parts.story import StoryPart
from docx.shared import Pt

# Word's built-in style ids for the two styles a note uses. Word matches built-in styles by
# name ("footnote text", "footnote reference"), but a paragraph refers to them by id.
FOOTNOTE_TEXT_STYLE_ID = "FootnoteText"
FOOTNOTE_REFERENCE_STYLE_ID = "FootnoteReference"
_FOOTNOTE_TEXT_NAME = "footnote text"
_FOOTNOTE_REFERENCE_NAME = "footnote reference"
_FOOTNOTES_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"

# The separator lines Word draws above the notes, as Word itself writes them. Every
# footnotes part Word saves carries both, with these ids, and settings.xml names them.
_FOOTNOTES_XML = (
    f"<w:footnotes {nsdecls('w', 'r')}>"
    '<w:footnote w:type="separator" w:id="-1"><w:p><w:pPr>'
    '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
    "<w:r><w:separator/></w:r></w:p></w:footnote>"
    '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:pPr>'
    '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
    "<w:r><w:continuationSeparator/></w:r></w:p></w:footnote>"
    "</w:footnotes>"
)

# The w:settings children the schema puts after w:footnotePr.
_FOOTNOTE_PR_SUCCESSORS = (
    "w:endnotePr",
    "w:compat",
    "w:docVars",
    "w:rsids",
    "m:mathPr",
    "w:attachedSchema",
    "w:themeFontLang",
    "w:clrSchemeMapping",
    "w:doNotIncludeSubdocsInStats",
    "w:doNotAutoCompressPictures",
    "w:forceUpgrade",
    "w:captions",
    "w:readModeInkLockDown",
    "w:smartTagType",
    "sl:schemaLibrary",
    "w:shapeDefaults",
    "w:doNotEmbedSmartTags",
    "w:decimalSymbol",
    "w:listSeparator",
)


class FootnotesPart(StoryPart):
    """The ``word/footnotes.xml`` part, as a story python-docx paragraphs can live in."""


class PartHolder:
    """Parent for a block container whose paragraphs belong to ``part``.

    python-docx resolves a paragraph's part by asking its parent, up to the first object
    that knows; a ``_Body`` parented here answers with the footnotes part.
    """

    def __init__(self, part: FootnotesPart) -> None:
        self.part = part


def get_or_add_footnotes_part(document: Any) -> FootnotesPart:
    """Return the document's footnotes part, creating or adopting it as needed.

    A template's own footnotes part arrives as a bare ``Part``; it is replaced by a
    ``FootnotesPart`` built from the same XML, under the same name, relationship id and
    relationships, so the template's separators and any notes it carries survive.
    """
    document_part = document.part
    for r_id, rel in document_part.rels.items():
        if rel.reltype != RT.FOOTNOTES or rel.is_external:
            continue
        existing = rel.target_part
        if isinstance(existing, FootnotesPart):
            return existing
        element = getattr(existing, "element", None)
        if element is None:
            element = parse_xml(existing.blob)
        part = FootnotesPart(existing.partname, existing.content_type, element, existing.package)
        for old_id, old_rel in existing.rels.items():
            part.rels.add_relationship(old_rel.reltype, old_rel._target, old_id, old_rel.is_external)
        rel._target = part
        document_part.rels._target_parts_by_rId[r_id] = part
        _ensure_footnote_settings(document)
        return part

    part = FootnotesPart(
        PackURI("/word/footnotes.xml"),
        _FOOTNOTES_CONTENT_TYPE,
        parse_xml(_FOOTNOTES_XML),
        document_part.package,
    )
    document_part.relate_to(part, RT.FOOTNOTES)
    _ensure_footnote_settings(document)
    return part


def _ensure_footnote_settings(document: Any) -> None:
    """Name the separator notes in settings.xml, as Word does, unless already named."""
    settings = document.settings.element
    if settings.find(qn("w:footnotePr")) is not None:
        return
    footnote_pr = OxmlElement("w:footnotePr")
    for note_id in ("-1", "0"):
        reference = OxmlElement("w:footnote")
        reference.set(qn("w:id"), note_id)
        footnote_pr.append(reference)
    settings.insert_element_before(footnote_pr, *_FOOTNOTE_PR_SUCCESSORS)


def next_footnote_id(part: FootnotesPart) -> int:
    """Return the id after the highest note id in the part; separators use -1 and 0."""
    values = (note.get(qn("w:id"), "") for note in part.element.findall(qn("w:footnote")))
    ids = [int(value) for value in values if value.lstrip("-").isdigit()]
    return max([0, *ids]) + 1


def add_footnote(part: FootnotesPart, note_id: int) -> Any:
    """Append an empty ``w:footnote`` with ``note_id`` to the part and return it."""
    footnote = OxmlElement("w:footnote")
    footnote.set(qn("w:id"), str(note_id))
    part.element.append(footnote)
    return footnote


def ensure_footnote_styles(document: Any) -> tuple[str, str]:
    """Return the style ids of the footnote text and reference styles, adding any missing.

    A template's own styles of those names are used as they are. Missing ones are added as
    Word's built-ins: text at 10 pt with no space after, the reference mark superscript.
    """
    from docx.enum.style import WD_STYLE_TYPE

    styles = document.styles
    by_name = {style.name.lower(): style for style in styles if style.name}

    text_style = by_name.get(_FOOTNOTE_TEXT_NAME)
    if text_style is None:
        text_style = styles.add_style(_FOOTNOTE_TEXT_NAME, WD_STYLE_TYPE.PARAGRAPH, builtin=True)
        text_style.style_id = FOOTNOTE_TEXT_STYLE_ID
        text_style.base_style = styles["Normal"]
        text_style.font.size = Pt(10)
        text_style.paragraph_format.space_after = Pt(0)
        text_style.paragraph_format.line_spacing = 1.0

    reference_style = by_name.get(_FOOTNOTE_REFERENCE_NAME)
    if reference_style is None:
        reference_style = styles.add_style(_FOOTNOTE_REFERENCE_NAME, WD_STYLE_TYPE.CHARACTER, builtin=True)
        reference_style.style_id = FOOTNOTE_REFERENCE_STYLE_ID
        reference_style.font.superscript = True

    return text_style.style_id, reference_style.style_id


def styled_run(style_id: str, mark_tag: str, note_id: int | None = None) -> Any:
    """Build ``<w:r><w:rPr><w:rStyle/></w:rPr><mark/></w:r>`` for a note mark.

    ``mark_tag`` is ``w:footnoteReference`` (in the body, with the note's id) or
    ``w:footnoteRef`` (opening the note itself, where Word prints the number).
    """
    run = OxmlElement("w:r")
    run_pr = OxmlElement("w:rPr")
    run_style = OxmlElement("w:rStyle")
    run_style.set(qn("w:val"), style_id)
    run_pr.append(run_style)
    run.append(run_pr)
    mark = OxmlElement(mark_tag)
    if note_id is not None:
        mark.set(qn("w:id"), str(note_id))
    run.append(mark)
    return run
