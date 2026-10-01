"""A package whose relationships name parts the archive does not contain.

``python-docx`` loads every part the relationships reach when it opens a package, so
one relationship to a missing footer, font table, numbering part or image -- or an
internal bookmark written as if it were a file -- failed the whole document. Word opens
these files and shows what is there; so does the parser now, by reopening the package
without the dangling relationships. Fifteen files in LibreOffice's Writer regression
corpus that Word opens failed this way.
"""

import io
import logging
import zipfile

import docx
import pytest
from PIL import Image as PILImage

from all2md import to_markdown
from all2md.exceptions import MalformedFileError
from all2md.parsers.docx_package import drop_dangling_relationships

pytestmark = [pytest.mark.unit, pytest.mark.docx]


def saved(document) -> bytes:
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def without(data: bytes, *missing: str, rels_edit=None) -> bytes:
    """``data`` with the named archive members removed, and optionally one .rels rewritten."""
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(output, "w") as target:
        for item in source.infolist():
            if item.filename in missing:
                continue
            content = source.read(item.filename)
            if rels_edit is not None and item.filename == rels_edit[0]:
                content = rels_edit[1](content.decode("utf8")).encode("utf8")
            target.writestr(item, content)
    return output.getvalue()


def document_with_footer() -> bytes:
    document = docx.Document()
    document.add_paragraph("Body text survives.")
    document.sections[0].footer.paragraphs[0].text = "Footer text."
    return saved(document)


def test_a_missing_footer_part_reads_the_body():
    data = without(document_with_footer(), "word/footer1.xml")
    with pytest.raises(KeyError):
        docx.Document(io.BytesIO(data))

    assert "Body text survives." in to_markdown(data, source_format="docx")


def test_a_missing_numbering_part_reads_the_list_items_as_text():
    document = docx.Document()
    document.add_paragraph("First item.", style="List Number")
    document.add_paragraph("Second item.", style="List Number")
    data = without(saved(document), "word/numbering.xml")

    markdown = to_markdown(data, source_format="docx")

    assert "First item." in markdown
    assert "Second item." in markdown


def test_a_missing_image_reads_the_text_around_it(tmp_path):
    picture = tmp_path / "dot.png"
    PILImage.new("RGB", (4, 4), "red").save(picture)
    document = docx.Document()
    document.add_paragraph("Before the picture.")
    document.add_picture(str(picture))
    document.add_paragraph("After the picture.")
    data = saved(document)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        media = [name for name in archive.namelist() if name.startswith("word/media/")]

    markdown = to_markdown(without(data, *media), source_format="docx")

    assert "Before the picture." in markdown
    assert "After the picture." in markdown


def test_a_missing_font_table_and_an_internal_bookmark_target_are_ignored():
    def add_bookmark_relationship(rels: str) -> str:
        bookmark = (
            '<Relationship Id="rIdBookmark" Target="#bookmark" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/hyperlink"/>'
        )
        return rels.replace("</Relationships>", bookmark + "</Relationships>")

    document = docx.Document()
    document.add_paragraph("Still here.")
    data = without(
        saved(document),
        "word/fontTable.xml",
        rels_edit=("word/_rels/document.xml.rels", add_bookmark_relationship),
    )

    assert "Still here." in to_markdown(data, source_format="docx")


def test_a_path_and_a_stream_are_repaired_alike(tmp_path):
    data = without(document_with_footer(), "word/footer1.xml")
    path = tmp_path / "missing-footer.docx"
    path.write_bytes(data)

    assert "Body text survives." in to_markdown(path)
    assert "Body text survives." in to_markdown(io.BytesIO(data), source_format="docx")


def test_the_repair_drops_only_relationships_to_missing_parts(caplog):
    data = without(document_with_footer(), "word/footer1.xml")

    with caplog.at_level(logging.WARNING, logger="all2md.parsers.docx_package"):
        repaired, dropped = drop_dangling_relationships(data)

    assert dropped == ["word/footer1.xml"]
    assert "word/footer1.xml" in caplog.text
    with zipfile.ZipFile(io.BytesIO(repaired)) as archive:
        rels = archive.read("word/_rels/document.xml.rels").decode("utf8")
    assert "footer1.xml" not in rels
    assert "styles.xml" in rels
    assert drop_dangling_relationships(document_with_footer()) is None


def test_a_package_the_repair_cannot_help_reports_the_original_error():
    data = without(document_with_footer(), "word/document.xml")

    with pytest.raises(MalformedFileError, match="Failed to open DOCX document"):
        to_markdown(data, source_format="docx")
