"""Unit tests for ODT parser."""

import pytest
from odf import opendocument, text

from all2md.ast import Heading
from all2md.parsers.odt import OdtToAstConverter


@pytest.mark.unit
def test_odt_heading_level_above_six_clamped() -> None:
    """ODT heading elements with outlinelevel >= 7 must clamp to Heading level 6."""
    doc = opendocument.OpenDocumentText()
    h = text.H(outlinelevel="7", text="Deep ODT Heading")
    doc.text.addElement(h)

    converter = OdtToAstConverter()
    ast_doc = converter.convert_to_ast(doc)

    assert len(ast_doc.children) == 1
    heading = ast_doc.children[0]
    assert isinstance(heading, Heading)
    assert heading.level == 6
    assert heading.content[0].content == "Deep ODT Heading"
