#  Copyright (c) 2025 Tom Villani, Ph.D.
"""GitHub alerts: a quote whose first line is ``[!NOTE]`` (or TIP, IMPORTANT, WARNING, CAUTION).

They read as admonitions with the metadata every parser uses, and GFM -- the
default flavor -- writes them back the same way, so a README with alerts round
trips unchanged.
"""

from __future__ import annotations

import pytest

from all2md import to_ast, to_markdown
from all2md.ast import BlockQuote, List, Paragraph, Text
from all2md.options.markdown import MarkdownParserOptions

ALERT = """> [!NOTE]
> Body *here*.
>
> Second paragraph.
"""

ALERT_WITH_LIST = """> [!WARNING]
>
> - one
> - two
"""


def _quote(source: str, **options) -> BlockQuote:
    parser_options = MarkdownParserOptions(**options) if options else None
    doc = to_ast(source.encode(), source_format="markdown", parser_options=parser_options)
    assert len(doc.children) == 1
    quote = doc.children[0]
    assert isinstance(quote, BlockQuote)
    return quote


@pytest.mark.unit
class TestParse:
    @pytest.mark.parametrize("kind", ["NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"])
    def test_each_kind(self, kind):
        quote = _quote(f"> [!{kind}]" + chr(10) + "> Body." + chr(10))
        assert quote.metadata == {"admonition_type": kind.lower(), "source_format": "gfm"}
        assert quote.children == [Paragraph(content=[Text(content="Body.")])]

    def test_marker_is_case_insensitive(self):
        assert _quote("> [!note]" + chr(10) + "> Body." + chr(10)).metadata["admonition_type"] == "note"

    def test_marker_is_not_body_text(self):
        quote = _quote(ALERT)
        assert len(quote.children) == 2
        first = quote.children[0]
        assert isinstance(first, Paragraph)
        assert isinstance(first.content[0], Text) and first.content[0].content == "Body "

    def test_body_opening_with_a_list(self):
        quote = _quote(ALERT_WITH_LIST)
        assert quote.metadata["admonition_type"] == "warning"
        assert [type(child) for child in quote.children] == [List]

    @pytest.mark.parametrize(
        "source",
        [
            "> [!NOTE] on the same line as text" + chr(10),
            "> [!NOTE]" + chr(10),
            "> [!DANGER]" + chr(10) + "> Not one of GitHub's kinds." + chr(10),
            "> Text first." + chr(10) + "> [!NOTE]" + chr(10),
        ],
        ids=["marker-shares-its-line", "marker-alone", "unknown-kind", "marker-not-first"],
    )
    def test_ordinary_quotes_stay_quotes(self, source):
        assert _quote(source).metadata == {}

    def test_parse_admonitions_off(self):
        assert _quote(ALERT, parse_admonitions=False).metadata == {}


@pytest.mark.unit
class TestRender:
    @pytest.mark.parametrize("source", [ALERT, ALERT_WITH_LIST], ids=["paragraph", "list"])
    def test_gfm_round_trip_is_stable(self, source):
        once = to_markdown(source.encode(), source_format="markdown")
        assert once.startswith("> [!")
        assert to_markdown(once.encode(), source_format="markdown") == once

    def test_paragraph_follows_the_marker_directly(self):
        assert to_markdown(ALERT.encode(), source_format="markdown").splitlines()[:2] == [
            "> [!NOTE]",
            "> Body *here*.",
        ]

    def test_other_blocks_are_set_off_by_a_blank_line(self):
        lines = to_markdown(ALERT_WITH_LIST.encode(), source_format="markdown").splitlines()
        assert lines[0] == "> [!WARNING]"
        assert lines[1].strip() == ">"

    def test_flavor_without_alerts_writes_the_label(self):
        output = to_markdown(ALERT.encode(), source_format="markdown", flavor="commonmark")
        assert output.startswith("> **Note:** Body *here*.")
