"""Inline formatting tags must survive a Markdown round trip (#140).

mistune hands raw inline HTML through as ``inline_html`` tokens, so the Markdown
parser produced loose ``HTMLInline`` nodes rather than the AST node that already
exists for the meaning. On the way back out the default
``html_passthrough_mode="escape"`` -- a deliberate security posture -- escaped
them, so ``a <del>x</del> b`` came back as ``a &lt;del&gt;x&lt;/del&gt; b``.

#113 fixed this for ``<u>``/``<ins>``; these cover the rest of the family, plus
the ``<mark>`` gap on the HTML side that the same audit predicted.
"""

import pytest

from all2md import to_markdown
from all2md.ast import Mark, Strikethrough, Subscript, Superscript, Underline
from all2md.ast.transforms import NodeCollector
from all2md.parsers.markdown import MarkdownToAstConverter

#: tag -> the node it must fold into, and the markdown it should render as.
FOLDED = [
    ("del", Strikethrough, "a ~~x~~ b"),
    ("s", Strikethrough, "a ~~x~~ b"),
    ("sup", Superscript, "a ^x^ b"),
    ("sub", Subscript, "a ~x~ b"),
    ("mark", Mark, "a ==x== b"),
    ("u", Underline, "a <u>x</u> b"),
    ("ins", Underline, "a ^^x^^ b"),
]


def _nodes_of(document, node_type):
    collector = NodeCollector(lambda n: isinstance(n, node_type))
    document.accept(collector)
    return collector.collected


@pytest.mark.unit
@pytest.mark.formatting
class TestTagsFoldIntoTheirNode:
    """Each tag becomes the AST node that already carries its meaning."""

    @pytest.mark.parametrize("tag,node_type,_expected", FOLDED)
    def test_tag_produces_its_node(self, tag, node_type, _expected):
        doc = MarkdownToAstConverter().parse(f"a <{tag}>x</{tag}> b")
        assert _nodes_of(doc, node_type), f"<{tag}> did not fold into {node_type.__name__}"

    @pytest.mark.parametrize("tag,_node_type,expected", FOLDED)
    def test_tag_is_not_escaped_on_the_way_out(self, tag, _node_type, expected):
        assert to_markdown(f"a <{tag}>x</{tag}> b", source_format="markdown").strip() == expected

    def test_u_and_ins_keep_their_distinction(self):
        """Both are Underline; ``semantic`` is what tells them apart."""
        underline = _nodes_of(MarkdownToAstConverter().parse("<u>x</u>"), Underline)[0]
        insert = _nodes_of(MarkdownToAstConverter().parse("<ins>x</ins>"), Underline)[0]
        assert (underline.semantic, insert.semantic) == ("underline", "insert")


@pytest.mark.unit
@pytest.mark.formatting
class TestOutputIsStable:
    """A second pass must not change the first pass's output."""

    @pytest.mark.parametrize("tag,_node_type,_expected", FOLDED)
    def test_round_trip_is_idempotent(self, tag, _node_type, _expected):
        once = to_markdown(f"a <{tag}>x</{tag}> b", source_format="markdown").strip()
        assert to_markdown(once, source_format="markdown").strip() == once


@pytest.mark.unit
@pytest.mark.formatting
class TestWhatMustNotFold:
    """The #113 constraints carry over: never guess, never silently drop."""

    def test_tag_with_attributes_stays_raw(self):
        # The attributes hold information the node cannot, so folding would lose them.
        out = to_markdown('a <del class="z">x</del> b', source_format="markdown")
        assert "class=" in out
        assert not _nodes_of(MarkdownToAstConverter().parse('a <del class="z">x</del> b'), Strikethrough)

    def test_unmatched_opener_stays_raw(self):
        assert not _nodes_of(MarkdownToAstConverter().parse("a <del>x b"), Strikethrough)

    def test_stray_closer_stays_raw(self):
        assert not _nodes_of(MarkdownToAstConverter().parse("a x</del> b"), Strikethrough)

    def test_nothing_is_dropped_when_a_tag_stays_raw(self):
        # The failure mode worth guarding is silent loss, not escaping.
        assert "x" in to_markdown("a <del>x b", source_format="markdown")


@pytest.mark.unit
@pytest.mark.formatting
class TestNesting:
    """Folding is applied to a stack, so nested spans must both survive."""

    def test_nested_tags(self):
        assert to_markdown("a <sup><sub>x</sub></sup> b", source_format="markdown").strip() == "a ^~x~^ b"

    def test_mixed_nesting_keeps_both(self):
        doc = MarkdownToAstConverter().parse("a <del>x <sup>y</sup> z</del> b")
        assert _nodes_of(doc, Strikethrough)
        assert _nodes_of(doc, Superscript)

    def test_the_shorter_tag_name_does_not_win_the_alternation(self):
        """``<sub>`` must not match the ``s`` branch of the tag pattern."""
        doc = MarkdownToAstConverter().parse("a <sub>x</sub> b")
        assert _nodes_of(doc, Subscript)
        assert not _nodes_of(doc, Strikethrough)


@pytest.mark.unit
@pytest.mark.html
class TestHtmlParserHasNoGap:
    """``<mark>`` was listed as inline but had no handler, so it was dropped.

    Not an escaping bug like the Markdown side -- the highlight was gone from the
    output entirely, which no round-trip text comparison would notice.
    """

    def test_mark_survives_html(self):
        assert to_markdown("<p>a <mark>x</mark> b</p>", source_format="html").strip() == "a ==x== b"

    @pytest.mark.parametrize(
        "tag,expected",
        [
            ("del", "a ~~x~~ b"),
            ("s", "a ~~x~~ b"),
            ("strike", "a ~~x~~ b"),
            ("sup", "a ^x^ b"),
            ("sub", "a ~x~ b"),
            ("mark", "a ==x== b"),
            ("u", "a <u>x</u> b"),
            ("ins", "a ^^x^^ b"),
        ],
    )
    def test_html_inline_formatting_family(self, tag, expected):
        assert to_markdown(f"<p>a <{tag}>x</{tag}> b</p>", source_format="html").strip() == expected
