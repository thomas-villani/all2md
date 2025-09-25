import base64

import docx
import pytest

from all2md import docx2markdown as md


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
    assert md._detect_list_level(para) == (None, 0)


@pytest.mark.unit
def test_detect_list_level_built_in_bullet():
    para = DummyParagraph(style_name="List Bullet 2")
    assert md._detect_list_level(para) == ("bullet", 2)


@pytest.mark.unit
def test_detect_list_level_built_in_number_default():
    para = DummyParagraph(style_name="List Number")
    assert md._detect_list_level(para) == ("number", 1)


@pytest.mark.unit
def test_detect_list_level_indentation_number():
    para = DummyParagraph(style_name="Normal", left_indent=72, text="1) item")
    assert md._detect_list_level(para) == ("number", 2)


@pytest.mark.unit
def test_detect_list_level_indentation_bullet():
    para = DummyParagraph(style_name="Normal", left_indent=36, text="item")
    assert md._detect_list_level(para) == ("bullet", 1)


@pytest.mark.unit
def test_detect_list_level_no_indent():
    para = DummyParagraph(style_name="Normal", left_indent=None, text="item")
    assert md._detect_list_level(para) == (None, 0)


@pytest.mark.unit
def test_format_list_marker():
    assert md._format_list_marker("bullet") == "* "
    assert md._format_list_marker("number", 3) == "3. "


class FakeFont:
    def __init__(self, strike=False, subscript=False, superscript=False):
        self.strike = strike
        self.subscript = subscript
        self.superscript = superscript


class FakeRun:
    def __init__(
        self, text, bold=False, italic=False, underline=False, strike=False, subscript=False, superscript=False
    ):
        self.text = text
        self.bold = bold
        self.italic = italic
        self.underline = underline
        self.font = FakeFont(strike, subscript, superscript)


@pytest.mark.unit
def test_get_run_formatting_key():
    run = FakeRun("test", bold=True, italic=False, underline=True, strike=True, subscript=True, superscript=False)
    key = md._get_run_formatting_key(run)
    assert key == (True, False, True, True, True, False)


@pytest.mark.unit
def test_process_hyperlink(monkeypatch):
    inner = FakeRun("linktext")

    class FakeHyperlink:
        def __init__(self, url, run):
            self.url = url
            self.runs = [run]

    monkeypatch.setattr(md, "Hyperlink", FakeHyperlink)
    link = FakeHyperlink("http://example.com", inner)
    url, run = md._process_hyperlink(link)
    assert url == "http://example.com"
    assert run is inner
    url2, run2 = md._process_hyperlink(inner)
    assert url2 is None and run2 is inner


class RunParagraph:
    def __init__(self, runs):
        self._runs = runs

    def iter_inner_content(self):
        return iter(self._runs)


@pytest.mark.unit
def test_process_paragraph_runs_simple():
    runs = [FakeRun("Hello "), FakeRun("World")]
    para = RunParagraph(runs)
    assert md._process_paragraph_runs(para) == "Hello World"


@pytest.mark.unit
def test_process_paragraph_runs_bold():
    runs = [FakeRun("Bold", bold=True)]
    para = RunParagraph(runs)
    assert md._process_paragraph_runs(para) == "**Bold**"


@pytest.mark.unit
def test_process_paragraph_runs_italic():
    runs = [FakeRun("Ital", italic=True)]
    para = RunParagraph(runs)
    assert md._process_paragraph_runs(para) == "*Ital*"


@pytest.mark.unit
def test_process_paragraph_runs_underline():
    runs = [FakeRun("Under", underline=True)]
    para = RunParagraph(runs)
    assert md._process_paragraph_runs(para) == "__Under__"


@pytest.mark.unit
def test_process_paragraph_runs_strike():
    runs = [FakeRun("Strike", strike=True)]
    para = RunParagraph(runs)
    assert md._process_paragraph_runs(para) == "~~Strike~~"


@pytest.mark.unit
def test_process_paragraph_runs_subscript():
    runs = [FakeRun("Sub", subscript=True)]
    para = RunParagraph(runs)
    assert md._process_paragraph_runs(para) == "~Sub~"


@pytest.mark.unit
def test_process_paragraph_runs_superscript():
    runs = [FakeRun("Sup", superscript=True)]
    para = RunParagraph(runs)
    assert md._process_paragraph_runs(para) == "^Sup^"


@pytest.mark.unit
def test_process_paragraph_runs_multiple_formatting():
    runs = [FakeRun("Test", bold=True, italic=True)]
    para = RunParagraph(runs)
    assert md._process_paragraph_runs(para) == "***Test***"


@pytest.mark.unit
def test_process_paragraph_runs_hyperlink(monkeypatch):
    inner = FakeRun("LinkUpdate")

    class FakeHyperlink:
        def __init__(self):
            self.url = "http://link"
            self.runs = [inner]

    monkeypatch.setattr(md, "Hyperlink", FakeHyperlink)
    runs = [FakeHyperlink()]
    para = RunParagraph(runs)
    assert md._process_paragraph_runs(para) == "[LinkUpdate](http://link)"


@pytest.mark.unit
def test_process_paragraph_runs_whitespace_preserved():
    runs = [FakeRun("  hello  ")]
    para = RunParagraph(runs)
    assert md._process_paragraph_runs(para) == "  hello  "


class FakeCell:
    def __init__(self, texts):
        if isinstance(texts, str):
            texts_list = [texts]
        else:
            texts_list = texts
        self.paragraphs = [RunParagraph([FakeRun(text)]) for text in texts_list]
