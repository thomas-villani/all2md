"""Dehyphenation on the *native* (non-OCR) PDF text path.

The parser used to delegate this entirely to PyMuPDF's ``TEXT_DEHYPHENATE``
extraction flag, which is inert (it does not change ``get_text()`` output in any
mode on PyMuPDF 1.28 / MuPDF 1.29). ``merge_hyphenated_words`` — a default-on
option — therefore did nothing at all for any PDF that did not go through OCR.

It went unnoticed because every existing test either called ``dehyphenate_text()``
as a pure function or drove the OCR path; none ran a real text PDF through the
parser and asserted the word came back joined. These do.
"""

import fitz
import pytest

from all2md import to_markdown
from all2md.options.pdf import PdfOptions
from all2md.parsers._pdf_ocr import dehyphenate_blocks


def _pdf_with_lines(tmp_path, text: str, name: str = "h.pdf") -> str:
    """Render ``text`` into one text block, honouring its explicit line breaks.

    The hyphen must fall at the end of a line *inside a single block* — that is the
    only place line-break hyphenation can occur. Separate ``insert_text`` calls put
    each line in its own block, where no dehyphenator (ours or PyMuPDF's) can join
    them; that is a property of the fixture, not of the parser.
    """
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 400, 300), text, fontsize=10)
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.mark.unit
@pytest.mark.pdf
class TestNativePdfDehyphenation:
    """End-to-end: a text PDF, through the parser, with no OCR involved."""

    def test_merges_line_break_hyphenation_by_default(self, tmp_path):
        """The regression: merge_hyphenated_words defaults on and must actually merge."""
        path = _pdf_with_lines(tmp_path, "This paragraph demonstrates hyphen-\nation across a break.")

        markdown = to_markdown(path)

        assert "hyphenation across a break." in markdown
        assert "hyphen- ation" not in markdown

    def test_preserves_hyphenation_when_disabled(self, tmp_path):
        """Turning the option off has to be observable, or it is not a real knob."""
        path = _pdf_with_lines(tmp_path, "This paragraph demonstrates hyphen-\nation across a break.")

        markdown = to_markdown(path, parser_options=PdfOptions(merge_hyphenated_words=False))

        assert "hyphenation" not in markdown
        assert "hyphen- ation" in markdown

    def test_uppercase_continuation_keeps_the_hyphen(self, tmp_path):
        """A genuine compound survives: "Anglo-\\nSaxon" is a hyphenated word, not a split one."""
        path = _pdf_with_lines(tmp_path, "The Anglo-\nSaxon and the be-\nwusst cases.")

        markdown = to_markdown(path)

        assert "Anglo-Saxon" in markdown
        assert "bewusst" in markdown
        assert "AngloSaxon" not in markdown

    def test_numeric_continuation_is_left_alone(self, tmp_path):
        """A number range is not hyphenation: "10-\\n20" must stay "10- 20", not "1020"."""
        path = _pdf_with_lines(tmp_path, "Values in the range 10-\n20 are valid.")

        markdown = to_markdown(path)

        assert "1020" not in markdown


@pytest.mark.unit
@pytest.mark.pdf
class TestDehyphenateBlocks:
    """Span-level behaviour of the block rewriter."""

    @staticmethod
    def _block(*lines: list[str]) -> dict:
        return {"type": 0, "lines": [{"spans": [{"text": t} for t in line]} for line in lines]}

    def test_moves_continuation_word_into_the_previous_line(self):
        """The continuation must MOVE, not just lose its hyphen.

        Callers join a block's lines with a space, so merely stripping the hyphen
        would still render "hyphen ation". The word has to migrate up a line.
        """
        blocks = [self._block(["demonstrates hyphen-"], ["ation across a break."])]

        dehyphenate_blocks(blocks)

        lines = blocks[0]["lines"]
        assert lines[0]["spans"][0]["text"] == "demonstrates hyphenation"
        assert lines[1]["spans"][0]["text"] == "across a break."

    def test_drops_a_line_the_continuation_emptied(self):
        """When the continuation was the whole line, the now-empty line goes away."""
        blocks = [self._block(["spanning hyphen-"], ["ation"], ["and more text"])]

        dehyphenate_blocks(blocks)

        lines = blocks[0]["lines"]
        assert len(lines) == 2
        assert lines[0]["spans"][0]["text"] == "spanning hyphenation"
        assert lines[1]["spans"][0]["text"] == "and more text"

    def test_leaves_ordinary_line_breaks_untouched(self):
        blocks = [self._block(["no hyphen here"], ["second line"])]

        dehyphenate_blocks(blocks)

        lines = blocks[0]["lines"]
        assert lines[0]["spans"][0]["text"] == "no hyphen here"
        assert lines[1]["spans"][0]["text"] == "second line"

    def test_ignores_non_text_blocks(self):
        """Image blocks (type 1) have no "lines" and must not raise."""
        blocks = [{"type": 1, "bbox": (0, 0, 1, 1)}]

        dehyphenate_blocks(blocks)  # must not raise

        assert blocks == [{"type": 1, "bbox": (0, 0, 1, 1)}]

    def test_hyphen_at_end_of_the_final_line_is_kept(self):
        """Nothing follows, so there is nothing to join it to."""
        blocks = [self._block(["a trailing hyphen-"])]

        dehyphenate_blocks(blocks)

        assert blocks[0]["lines"][0]["spans"][0]["text"] == "a trailing hyphen-"
