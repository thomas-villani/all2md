import pytest

import all2md.converters.docx2ast
from all2md.converters import docx2markdown as md


class FakeIndent:
    def __init__(self, pt):
        self.pt = pt


class FakeFormat:
    def __init__(self, left_indent=None):
        self.left_indent = left_indent


class FakeStyle:
    def __init__(self, name):
        self.name = name


class DummyParagraph:
    def __init__(self, style_name=None, left_indent=None, text=""):
        self.style = FakeStyle(style_name)
        self.paragraph_format = FakeFormat(left_indent=FakeIndent(left_indent) if left_indent is not None else None)
        self.text = text

    def iter_inner_content(self):
        return iter([])


@pytest.mark.unit
def test_detect_list_level_no_style():
    para = DummyParagraph(style_name=None)
    assert all2md.converters.docx2ast._detect_list_level(para) == (None, 0)


@pytest.mark.unit
def test_detect_list_level_built_in_bullet():
    para = DummyParagraph(style_name="List Bullet 2")
    assert all2md.converters.docx2ast._detect_list_level(para) == ("bullet", 2)


@pytest.mark.unit
def test_detect_list_level_built_in_number_default():
    para = DummyParagraph(style_name="List Number")
    assert all2md.converters.docx2ast._detect_list_level(para) == ("number", 1)


@pytest.mark.unit
def test_detect_list_level_indentation_number():
    para = DummyParagraph(style_name="Normal", left_indent=72, text="1) item")
    assert all2md.converters.docx2ast._detect_list_level(para) == ("number", 2)


@pytest.mark.unit
def test_detect_list_level_indentation_bullet():
    para = DummyParagraph(style_name="Normal", left_indent=36, text="item")
    assert all2md.converters.docx2ast._detect_list_level(para) == ("bullet", 1)


@pytest.mark.unit
def test_detect_list_level_no_indent():
    para = DummyParagraph(style_name="Normal", left_indent=None, text="item")
    assert all2md.converters.docx2ast._detect_list_level(para) == (None, 0)
