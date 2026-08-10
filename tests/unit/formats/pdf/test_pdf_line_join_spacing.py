"""Spacing at the join between two lines of one paragraph.

Lines of a paragraph are joined with an explicit separator space, unless the text already
ends with whitespace there. Deciding "already ends with whitespace" means finding the last
Text leaf, which may sit inside a Strong/Emphasis/Link wrapper.

The walk used to conflate two different answers from a wrapper — "its text does not end in
whitespace" and "it holds no text at all" — and treat both as "keep looking". So a line
ending in a bold run fell through to whatever came *before* the bold run, and if that ended
with a space the separator was suppressed: `negotiating Roang on` + `Lamotrek Atoll` came
back as `Roang onLamotrek`.

Found on the PMC born-digital corpus, where it cost whole reference-list entries: a wrapped
bibliography title loses several n-grams to one such join, which is enough to fail a recall
threshold that a long paragraph would have absorbed.
"""

import re

import fitz
import pytest

from all2md import to_markdown
from all2md.ast.nodes import Code, Emphasis, Link, Strong, Text
from all2md.parsers.pdf import _trailing_text_is_whitespace


@pytest.mark.unit
@pytest.mark.pdf
class TestTrailingWhitespaceDetection:
    """The predicate that decides whether a line join needs a separator space."""

    def test_bold_run_not_ending_in_space_after_spaced_text(self) -> None:
        """The bold run is the join point, so the space before it is irrelevant.

        This is the regression: answering about `'167. Metzgar E: '` instead of about the
        bold run that actually ends the line suppressed the separator.
        """
        nodes = [Text(content="167. Metzgar E: "), Strong(content=[Text(content="Roang on")])]
        assert _trailing_text_is_whitespace(nodes) is False

    def test_bold_run_ending_in_space(self) -> None:
        """A wrapper whose own text ends in whitespace still answers True."""
        nodes = [Text(content="a "), Strong(content=[Text(content="bold ")])]
        assert _trailing_text_is_whitespace(nodes) is True

    def test_plain_text(self) -> None:
        """Unwrapped text is judged directly."""
        assert _trailing_text_is_whitespace([Text(content="hello ")]) is True
        assert _trailing_text_is_whitespace([Text(content="hello")]) is False

    def test_empty_wrapper_falls_through(self) -> None:
        """A wrapper holding no text really does mean "keep looking"."""
        nodes = [Text(content="a "), Strong(content=[])]
        assert _trailing_text_is_whitespace(nodes) is True

    def test_nested_wrapper_is_judged_by_its_innermost_text(self) -> None:
        """Bold-inside-italic answers about the text, not about the nesting."""
        nodes = [Text(content="a "), Strong(content=[Emphasis(content=[Text(content="x")])])]
        assert _trailing_text_is_whitespace(nodes) is False

    def test_link_is_walked_like_other_wrappers(self) -> None:
        """A link ending a line is a join point too."""
        nodes = [Text(content="a "), Link(content=[Text(content="here")], url="https://example.com")]
        assert _trailing_text_is_whitespace(nodes) is False

    def test_code_stops_the_walk(self) -> None:
        """Code is text-bearing, so it answers rather than deferring."""
        assert _trailing_text_is_whitespace([Text(content="a "), Code(content="x")]) is False

    def test_no_nodes(self) -> None:
        """Nothing to judge is not whitespace."""
        assert _trailing_text_is_whitespace([]) is False


@pytest.mark.unit
@pytest.mark.pdf
class TestBoldRunAcrossLineBreak:
    """The same defect through the parser, on a real PDF."""

    @staticmethod
    def _prose(markdown: str) -> str:
        """Drop emphasis markers, so the assertion is about words rather than markup.

        The two halves render as separate runs (`**...on** **Lamotrek...**`), which is
        correct — what matters is that a space separates them in the text.
        """
        return re.sub(r"\*+", "", markdown)

    @staticmethod
    def _reference_entry(tmp_path, name: str, first_line: list[tuple[str, bool]], second_line: str) -> str:
        """Write one numbered reference entry whose bold title wraps onto a second line.

        Shaped after the real thing rather than invented: the spans reproduce a PMC
        reference line (`'167.'`, `' '`, `'Metzgar E: '`, then the bold title), laid out
        contiguously so PyMuPDF reports them as spans of one line. The leading ordinal
        matters — it marks the block as a list item, which is what keeps both lines in a
        single paragraph and therefore makes the inter-line join happen at all.
        """
        size = 8.0
        doc = fitz.open()
        page = doc.new_page()
        writer = fitz.TextWriter(page.rect)
        fonts = {False: fitz.Font("helv"), True: fitz.Font("hebo")}

        x = 60.0
        for text, is_bold in first_line:
            writer.append((x, 100), text, font=fonts[is_bold], fontsize=size)
            x += fonts[is_bold].text_length(text, size)
        writer.append((60, 109), second_line, font=fonts[True], fontsize=size)
        writer.write_text(page)

        path = tmp_path / name
        doc.save(str(path))
        doc.close()
        return str(path)

    def test_space_survives_the_join(self, tmp_path) -> None:
        """`on` and `Lamotrek` are separate words and must stay separate."""
        path = self._reference_entry(
            tmp_path,
            "wrapped_bold.pdf",
            [("167.", False), (" ", False), ("Metzgar E: ", False), ("negotiating Roang on", True)],
            "Lamotrek Atoll, Micronesia.",
        )
        result = self._prose(to_markdown(path))
        assert "onLamotrek" not in result, "the inter-line separator was dropped after a bold run"
        assert "on Lamotrek" in result

    def test_no_doubled_space_where_one_already_exists(self, tmp_path) -> None:
        """A line whose bold run already ends in a space must not gain a second one."""
        path = self._reference_entry(
            tmp_path,
            "already_spaced.pdf",
            [("167.", False), (" ", False), ("Metzgar E: ", False), ("negotiating Roang on ", True)],
            "Lamotrek Atoll, Micronesia.",
        )
        result = self._prose(to_markdown(path))
        assert "on  Lamotrek" not in result
        assert "on Lamotrek" in result
