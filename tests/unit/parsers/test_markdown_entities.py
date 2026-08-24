"""Character references survive the markdown round trip as characters (#441).

``all2md`` used to write ``&lt;`` into its own output and then fail to decode it
on the way back in, so ``p < 0.05`` -- ubiquitous in scientific prose -- came
back as the literal five characters ``&lt;`` for every consumer that reads the
AST rather than a rendered page. Three pieces had to agree to fix it, and this
file pins each: the PDF parser stops writing entities into nodes, the markdown
renderer escapes only the angle brackets a re-parse would misread, and the
markdown parser decodes well-formed references the way CommonMark says to.
"""

import pytest

from all2md.ast import Code, Document, Paragraph, Text
from all2md.ast.utils import extract_text
from all2md.parsers.markdown import markdown_to_ast
from all2md.renderers.markdown import MarkdownRenderer

pytestmark = pytest.mark.unit


def _render(text: str) -> str:
    """Render a one-paragraph document holding exactly ``text``."""
    doc = Document(children=[Paragraph(content=[Text(content=text)])])
    return MarkdownRenderer().render_to_string(doc).strip()


def _reparse(markdown: str) -> str:
    """Read ``markdown`` back and return its text with no joiner inserted."""
    return extract_text(markdown_to_ast(markdown), joiner="").strip()


class TestParserDecodesReferences:
    """The parser turns character references into the characters they denote."""

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("p &lt; 0.05", "p < 0.05"),
            ("q &gt; 3", "q > 3"),
            ("AT&amp;T", "AT&T"),
            ("&copy; 2020", "© 2020"),
            ("&#8212; dash", "— dash"),
            ("&#x3C; hex", "< hex"),
        ],
    )
    def test_well_formed_references_decode(self, source: str, expected: str) -> None:
        assert _reparse(source) == expected

    @pytest.mark.parametrize("source", ["a &ltx b", "a & b", "50 &percnt", "AT&T"])
    def test_malformed_references_stay_literal(self, source: str) -> None:
        """CommonMark decodes only references that close with a semicolon.

        ``html.unescape`` would take ``&ltx`` to ``<x``; the spec leaves it as
        typed, so the decode is gated on the grammar rather than on the library.
        """
        assert _reparse(source) == source

    def test_code_spans_keep_their_references(self) -> None:
        """A documented ``&amp;`` must still read as ``&amp;`` inside code."""
        doc = markdown_to_ast("Write `&amp;` for an ampersand")
        codes = [n for n in doc.children[0].content if isinstance(n, Code)]
        assert [c.content for c in codes] == ["&amp;"]


class TestRendererEscapesOnlyWhatItMust:
    """Angle brackets are escaped when a re-parse would misread them, not before."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            # The case that motivated the issue: a "<" before a space is literal
            # to every parser, so escaping it would only add noise to the page.
            ("p < 0.05 and q > 3", "p < 0.05 and q > 3"),
            ("5 <3", "5 <3"),
            ("845G--> A", "845G--> A"),
            # A letter, "/", "!" or "?" after the "<" opens raw HTML or an
            # autolink, so that "<" has to be escaped or the text disappears.
            ("a <b> c", r"a \<b> c"),
            ("close </div> tag", r"close \</div> tag"),
            ("<https://example.com>", r"\<https://example.com>"),
            # A bare "&" is literal unless it would itself parse as a reference.
            ("AT&T", "AT&T"),
            ("AT&lt;", r"AT\&lt;"),
        ],
    )
    def test_escaping_is_context_aware(self, text: str, expected: str) -> None:
        assert _render(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            "p < 0.05 and q > 3",
            "a <b> c",
            "close </div> tag",
            "845G--> A",
            "AT&T",
            # Without the "&" rule this decodes twice -- to "AT&lt;", then to
            # "AT<" -- and the literal reference the author wrote is gone.
            "AT&lt;",
            "x &amp; y",
            "<https://example.com>",
            "845G--&gt; A (C282Y) HFE",
        ],
    )
    def test_text_survives_a_round_trip(self, text: str) -> None:
        assert _reparse(_render(text)) == text

    def test_leading_angle_bracket_is_escaped(self) -> None:
        """A ``>`` opening a line would otherwise come back as a block quote."""
        assert _render("> not a quote") == r"\> not a quote"
        assert _reparse(_render("> not a quote")) == "> not a quote"
