import fitz

from all2md import pdf2markdown as mod


class FakePageIdent:
    def __init__(self):
        spans = [{"text": "a" * 100, "size": 12.0}, {"text": "b" * 10, "size": 20.0}]
        line = {"dir": (1, 0), "spans": spans}
        block = {"lines": [line]}
        self.blocks = [block]

    def get_text(self, mode, **kwargs):
        return {"blocks": self.blocks}


class FakeDocIdent:
    def __init__(self):
        self.page_count = 1

    def __getitem__(self, i):
        assert i == 0
        return FakePageIdent()


def test_identify_headers_empty_doc():
    class EmptyDoc:
        page_count = 0

        def __getitem__(self, i):
            raise IndexError

    hdr = mod.IdentifyHeaders(EmptyDoc())
    assert hdr.header_id == {}
    assert hdr.get_header_id({"size": 15}) == ""
    assert hdr.get_header_id({"size": 100}) == ""


def test_identify_headers_mapping():
    doc = FakeDocIdent()
    hdr = mod.IdentifyHeaders(doc)
    assert hdr.header_id.get(20) == "# "
    assert hdr.get_header_id({"size": 20.0}) == "# "
    assert hdr.get_header_id({"size": 12.0}) == ""


def test_resolve_links_no_overlap():
    span = {"bbox": (0, 0, 10, 10), "text": "X"}
    link = {"from": fitz.Rect(5, 5, 6, 6), "uri": "u"}
    assert mod.resolve_links([link], span) is None


def test_resolve_links_overlap():
    span = {"bbox": (0, 0, 10, 10), "text": " click "}
    link = {"from": fitz.Rect(0, 0, 10, 10), "uri": "http://test"}
    res = mod.resolve_links([link], span)
    assert res == "[click](http://test)"


def test_page_to_markdown_simple():
    span = {"bbox": (0, 0, 5, 10), "size": 12.0, "text": "hello", "flags": 0}
    line = {"bbox": (0, 0, 5, 10), "dir": (1, 0), "spans": [span]}
    block = {"bbox": (0, 0, 100, 100), "lines": [line]}

    class FakePage:
        def get_links(self):
            return []

        def get_text(self, mode, **kwargs):
            return {"blocks": [block]}

    hdr_prefix = mod.IdentifyHeaders(type("D", (), {"page_count": 0, "__getitem__": lambda *a: None})())
    out = mod.page_to_markdown(FakePage(), clip=None, hdr_prefix=hdr_prefix)
    assert out == "\nhello\n\n"


def test_parse_page_no_tables():
    class FakeTables:
        def __init__(self, tables):
            self.tables = tables

    class FakePage:
        rect = fitz.Rect(0, 0, 10, 20)

        def find_tables(self):
            return FakeTables([])

    lst = mod.parse_page(FakePage())
    assert lst == [("text", fitz.Rect(0, 0, 10, 20), 0)]


def test_parse_page_one_table():
    class FakeTable:
        def __init__(self, bbox, header_bbox):
            self.bbox = bbox
            self.header = type("H", (), {"bbox": header_bbox})

    class FakeTables:
        def __init__(self, tables):
            self.tables = tables

    page_rect = fitz.Rect(0, 0, 100, 200)

    class FakePage:
        def __init__(self):
            self.rect = page_rect

        def find_tables(self):
            tbl = FakeTable((10, 10, 30, 30), (10, 10, 30, 30))
            return FakeTables([tbl])

    lst = mod.parse_page(FakePage())
    assert lst[0][0] == "text"
    assert lst[1][0] == "table"
    rect = lst[1][1]
    assert rect == fitz.Rect(10, 10, 30, 30)
    assert lst[1][2] == 0


def test_pdf_to_markdown_no_tables(monkeypatch):
    class DummyHdr:
        def __init__(self, doc, pages=None, body_limit=None):
            pass

        def get_header_id(self, span):
            return ""

    monkeypatch.setattr(mod, "IdentifyHeaders", DummyHdr)
    monkeypatch.setattr(mod, "page_to_markdown", lambda page, clip, hdr, opts: "A")

    class FakeTables:
        def __init__(self, tables):
            self.tables = tables

    class FakePage:
        def __init__(self):
            self.rect = fitz.Rect(0, 0, 10, 10)

        def find_tables(self):
            return FakeTables([])

    class FakeDoc:
        page_count = 1

        def __getitem__(self, i):
            return FakePage()

    res = mod.pdf_to_markdown(FakeDoc())
    assert res == "A\n\n-----\n\n"


def test_pdf_to_markdown_with_tables(monkeypatch):
    class DummyHdr:
        def __init__(self, doc, pages=None, body_limit=None):
            pass

        def get_header_id(self, span):
            return ""

    monkeypatch.setattr(mod, "IdentifyHeaders", DummyHdr)
    monkeypatch.setattr(mod, "page_to_markdown", lambda page, clip, hdr: "X")

    class FakeTable:
        def __init__(self, bbox, header_bbox):
            self.bbox = bbox
            self.header = type("H", (), {"bbox": header_bbox})

        def to_markdown(self, clean=False):
            return "Y"

    class FakeTables:
        def __init__(self, tables):
            self.tables = tables

        def __getitem__(self, item):
            return self.tables[item]

    page_rect = fitz.Rect(0, 0, 100, 200)

    class FakePage:
        def __init__(self):
            self.rect = page_rect

        def find_tables(self):
            tbl = FakeTable((0, 10, 100, 20), (0, 10, 100, 20))
            return FakeTables([tbl])

    class FakeDoc:
        page_count = 1

        def __getitem__(self, i):
            return FakePage()

    res = mod.pdf_to_markdown(FakeDoc())
    assert res == "X\nY\n-----\n\n"
