"""PyMuPDF's layout advisory must not land in the converted document.

PyMuPDF prints::

    Consider using the pymupdf_layout package for a greatly improved page layout analysis.

with a bare ``print()`` the first time ``find_tables()`` runs in a process where
``pymupdf.layout`` is not installed. all2md writes documents to stdout, so it
arrived as line one of the markdown -- ``all2md report.pdf > report.md`` produced
a corrupt file. See #284.

``pymupdf-layout`` is excluded from the ``all`` extra over its license, so the
plain and ``[all]`` installs are both affected; this is the common case, not an
exotic one.
"""

import importlib.util

import pymupdf
import pytest

from all2md import to_markdown
from all2md.parsers import pdf as pdf_module

ADVISORY = "pymupdf_layout package"


def _one_page_pdf(tmp_path) -> str:
    """A page carrying ruling lines, so ``find_tables()`` actually runs.

    The default table mode gates ``find_tables()`` behind a cheap drawings scan,
    so a prose-only page never reaches the call that emits the advisory. Drawing
    a grid is what arms it.
    """
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Peregrine falcons nest nearby.")
    for offset in (0, 20, 40):
        page.draw_line(pymupdf.Point(72, 120 + offset), pymupdf.Point(300, 120 + offset))
    for offset in (0, 114, 228):
        page.draw_line(pymupdf.Point(72 + offset, 120), pymupdf.Point(72 + offset, 160))
    path = tmp_path / "advisory.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def pymupdf_without_layout(monkeypatch):
    """Make PyMuPDF believe ``pymupdf.layout`` is absent, as a plain install is.

    Also rearms the once-per-process latch, so the advisory is genuinely due to
    fire during the test rather than having been spent by an earlier one.
    """
    import pymupdf

    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name, package=None):
        if name == "pymupdf.layout":
            return None
        return real_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    monkeypatch.setattr(pymupdf, "_get_layout", None, raising=False)
    monkeypatch.setattr(pymupdf, "_recommend_layout", True, raising=False)


@pytest.mark.unit
@pytest.mark.pdf
class TestLayoutAdvisoryStaysOutOfStdout:
    """The advisory is suppressed, and the suppression is what does it."""

    def test_advisory_does_not_reach_stdout(self, tmp_path, capsys, pymupdf_without_layout):
        to_markdown(_one_page_pdf(tmp_path))
        assert ADVISORY not in capsys.readouterr().out

    def test_the_harness_can_actually_catch_it(self, tmp_path, capsys, monkeypatch, pymupdf_without_layout):
        """Control: with the suppression disabled, the advisory does print.

        Without this, the test above would pass just as happily on a fixture that
        never arms the advisory in the first place.
        """
        monkeypatch.setattr(pdf_module, "_silence_pymupdf_layout_advisory", lambda: None)
        to_markdown(_one_page_pdf(tmp_path))
        assert ADVISORY in capsys.readouterr().out

    def test_document_text_is_unaffected(self, tmp_path, capsys, pymupdf_without_layout):
        markdown = to_markdown(_one_page_pdf(tmp_path))
        assert "Peregrine falcons nest nearby." in markdown
        assert ADVISORY not in markdown


@pytest.mark.unit
@pytest.mark.pdf
class TestSuppressionIsNotLoadBearing:
    """A PyMuPDF without the entry point must convert, not crash."""

    def test_missing_entry_point_is_tolerated(self, tmp_path, monkeypatch):
        monkeypatch.delattr(pymupdf, "no_recommend_layout", raising=False)
        assert "Peregrine" in to_markdown(_one_page_pdf(tmp_path))
