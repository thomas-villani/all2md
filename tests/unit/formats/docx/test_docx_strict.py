"""Strict Open XML packages, read by renaming their namespaces to the Transitional ones.

A Strict package ("Strict Open XML Document" in Word's Save As) holds the same elements
as a Transitional one, under ``http://purl.oclc.org/ooxml/...`` names in place of
``http://schemas.openxmlformats.org/...``. ``python-docx`` finds no main document under
the Strict relationship type and refuses the package; Word opens it. LibreOffice's
Writer regression corpus holds seven such files that Word opens and the parser refused.

The tests make their Strict packages by renaming a ``python-docx`` document the other
way, the change Word's Save As makes to the names.
"""

import io
import re
import zipfile

import docx
import pytest
from docx.oxml import parse_xml

from all2md import to_markdown
from all2md.exceptions import MalformedFileError
from all2md.parsers.docx_package import strict_to_transitional

pytestmark = [pytest.mark.unit, pytest.mark.docx]

_TRANSITIONAL_URI = re.compile(
    rb"http://schemas\.openxmlformats\.org/(wordprocessingml|officeDocument|drawingml)/2006/([A-Za-z/\-]+)"
)


def _strict_uri(match: re.Match[bytes]) -> bytes:
    area, name = match.group(1), match.group(2)
    name = name.replace(b"extended-properties", b"extendedProperties")
    return b"http://purl.oclc.org/ooxml/" + area + b"/" + name


def strict(data: bytes) -> bytes:
    """``data`` with every Transitional namespace and relationship type in its Strict name."""
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(output, "w") as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename.endswith((".xml", ".rels")):
                content = _TRANSITIONAL_URI.sub(_strict_uri, content)
            target.writestr(item, content)
    return output.getvalue()


def saved(document) -> bytes:
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def strict_document() -> bytes:
    document = docx.Document()
    document.add_heading("Strict heading", level=1)
    paragraph = document.add_paragraph("Plain and ")
    paragraph.add_run("bold").bold = True
    paragraph.add_run(" text.")
    table = document.add_table(rows=2, cols=2)
    for row, cells in enumerate(table.rows):
        for column, cell in enumerate(cells.cells):
            cell.text = f"r{row}c{column}"
    return strict(saved(document))


def test_python_docx_refuses_a_strict_package():
    with pytest.raises(KeyError):
        docx.Document(io.BytesIO(strict_document()))


def test_a_strict_package_reads_its_headings_formatting_and_tables():
    markdown = to_markdown(strict_document(), source_format="docx")

    assert "# Strict heading" in markdown
    assert "Plain and **bold** text." in markdown
    assert "| r0c0 | r0c1 |" in markdown
    assert "| r1c0 | r1c1 |" in markdown


def test_a_strict_hyperlink_and_equation_are_read():
    document = docx.Document()
    paragraph = document.add_paragraph("See ")
    relationship = document.part.relate_to(
        "https://example.com/", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", True
    )
    paragraph._p.append(
        parse_xml(
            '<w:hyperlink xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            f'r:id="{relationship}"><w:r><w:t>the site</w:t></w:r></w:hyperlink>'
        )
    )
    document.add_paragraph()._p.append(
        parse_xml(
            '<m:oMathPara xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><m:oMath>'
            "<m:r><m:t>x=1</m:t></m:r></m:oMath></m:oMathPara>"
        )
    )

    markdown = to_markdown(strict(saved(document)), source_format="docx")

    assert "See [the site](https://example.com/)" in markdown
    assert "x=1" in markdown


def test_a_strict_package_from_a_path_and_with_a_missing_part(tmp_path):
    document = docx.Document()
    document.add_paragraph("Body text survives.")
    document.sections[0].footer.paragraphs[0].text = "Footer text."
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(saved(document))) as source, zipfile.ZipFile(output, "w") as target:
        for item in source.infolist():
            if item.filename != "word/footer1.xml":
                target.writestr(item, source.read(item.filename))
    path = tmp_path / "strict-missing-footer.docx"
    path.write_bytes(strict(output.getvalue()))

    assert "Body text survives." in to_markdown(path)


def test_the_translation_renames_every_strict_name_and_leaves_transitional_alone():
    transitional = saved(docx.Document())
    assert strict_to_transitional(transitional) is None

    translated = strict_to_transitional(strict(transitional))

    assert translated is not None
    with zipfile.ZipFile(io.BytesIO(translated)) as archive:
        for name in archive.namelist():
            assert b"purl.oclc.org" not in archive.read(name), name
        package_rels = archive.read("_rels/.rels")
    assert b"officeDocument/2006/relationships/officeDocument" in package_rels
    assert b"officeDocument/2006/relationships/extended-properties" in package_rels
    docx.Document(io.BytesIO(translated))


def test_a_name_the_translation_does_not_know_is_kept():
    data = strict(saved(docx.Document()))
    unknown = b"http://purl.oclc.org/ooxml/futureml/main"
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(output, "w") as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "word/document.xml":
                content = content.replace(b"<w:body>", b'<w:body xmlns:f="' + unknown + b'">', 1)
            target.writestr(item, content)

    translated = strict_to_transitional(output.getvalue())

    with zipfile.ZipFile(io.BytesIO(translated)) as archive:
        assert unknown in archive.read("word/document.xml")


def test_a_strict_package_without_its_main_document_reports_the_original_error():
    data = strict(saved(docx.Document()))
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(output, "w") as target:
        for item in source.infolist():
            if item.filename != "word/document.xml":
                target.writestr(item, source.read(item.filename))

    with pytest.raises(MalformedFileError, match="Failed to open DOCX document"):
        to_markdown(output.getvalue(), source_format="docx")
