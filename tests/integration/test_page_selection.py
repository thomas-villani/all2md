"""End-to-end tests that a requested page is the page you actually get.

The page-range unit tests only ever exercised ``validate_page_range`` with *lists*, which
took a correct code path. The *string* path double-converted 1-based to 0-based -- once in
``parse_page_ranges``, then again in ``validate_page_range`` -- so ``pages="1-3"`` raised
and ``pages="2-3"`` silently returned the pages either side of the ones asked for. Nothing
caught it, because no test ever asked "does the text of the page I requested come back?"

These tests do exactly that: each page carries a unique marker word, so a conversion either
contains the marker of the requested page or it does not. Every way of expressing a
selection -- string range, list, and the CLI flag -- is checked against the same document.
"""

import fitz
import pytest

from all2md import to_markdown
from all2md.exceptions import ValidationError
from all2md.options.pdf import PdfOptions

# One unmistakable marker per page. Distinct enough that no marker can be mistaken for
# another, and no marker appears anywhere else in the document.
MARKERS = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]


@pytest.fixture(scope="module")
def marked_pdf(tmp_path_factory) -> str:
    """A five-page PDF whose page N contains the marker word MARKERS[N-1] and nothing else."""
    doc = fitz.open()
    for marker in MARKERS:
        page = doc.new_page()
        page.insert_text((72, 100), marker, fontsize=14)

    path = tmp_path_factory.mktemp("pages") / "marked.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _markers_in(markdown: str) -> list[str]:
    """Which page markers survived into the converted output, in page order."""
    return [m for m in MARKERS if m in markdown]


@pytest.mark.integration
@pytest.mark.pdf
class TestStringPageRanges:
    """The string form documented on PdfOptions.pages: '1-3,5,10-'."""

    @pytest.mark.parametrize(
        "spec,expected",
        [
            ("1", ["Alpha"]),
            ("2", ["Beta"]),
            ("1-3", ["Alpha", "Beta", "Gamma"]),
            ("2-3", ["Beta", "Gamma"]),
            ("2,4", ["Beta", "Delta"]),
            ("4-", ["Delta", "Epsilon"]),
            ("1-2,5", ["Alpha", "Beta", "Epsilon"]),
        ],
    )
    def test_string_range_returns_exactly_those_pages(self, marked_pdf, spec, expected):
        result = to_markdown(marked_pdf, parser_options=PdfOptions(pages=spec))
        assert _markers_in(result) == expected

    def test_range_including_page_one_does_not_raise(self, marked_pdf):
        """'1-3' used to raise PageRangeError: Invalid page number: 0."""
        result = to_markdown(marked_pdf, parser_options=PdfOptions(pages="1-3"))
        assert "Alpha" in result

    def test_out_of_range_selection_raises_rather_than_converting_everything(self, marked_pdf):
        """A spec that selects no pages must fail loudly, not silently convert the whole document."""
        with pytest.raises(ValidationError):
            to_markdown(marked_pdf, parser_options=PdfOptions(pages="99"))


@pytest.mark.integration
@pytest.mark.pdf
class TestListPageRanges:
    """The list form, which always worked -- kept so a fix to one path cannot regress the other."""

    @pytest.mark.parametrize(
        "pages,expected",
        [
            ([1], ["Alpha"]),
            ([2], ["Beta"]),
            ([1, 2, 3], ["Alpha", "Beta", "Gamma"]),
            ([2, 4], ["Beta", "Delta"]),
        ],
    )
    def test_list_returns_exactly_those_pages(self, marked_pdf, pages, expected):
        result = to_markdown(marked_pdf, parser_options=PdfOptions(pages=pages))
        assert _markers_in(result) == expected

    def test_string_and_list_forms_agree(self, marked_pdf):
        """The two spellings of one selection must convert to the same Markdown."""
        from_string = to_markdown(marked_pdf, parser_options=PdfOptions(pages="2-3"))
        from_list = to_markdown(marked_pdf, parser_options=PdfOptions(pages=[2, 3]))
        assert from_string == from_list


@pytest.mark.integration
@pytest.mark.pdf
class TestCliPageFlag:
    """--pdf-pages must accept every form the option documents."""

    @pytest.mark.parametrize(
        "flag,expected",
        [
            ("2", ["Beta"]),
            ("1-3", ["Alpha", "Beta", "Gamma"]),
            ("2,4", ["Beta", "Delta"]),
            ("4-", ["Delta", "Epsilon"]),
        ],
    )
    def test_cli_page_flag(self, marked_pdf, capsys, flag, expected):
        from all2md.cli import main

        exit_code = main([marked_pdf, "--pdf-pages", flag])

        assert exit_code == 0
        assert _markers_in(capsys.readouterr().out) == expected
