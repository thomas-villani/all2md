#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Every parser describes an admonition with the same metadata.

A renderer reads ``admonition_type`` (and ``admonition_title``) off a
``BlockQuote`` without caring which syntax it came from. The AsciiDoc parser
used to write ``role`` instead, so its notes and warnings reached every other
format as plain quotes.
"""

from __future__ import annotations

import pytest

from all2md import to_ast, to_markdown
from all2md.ast import BlockQuote

WARNINGS = {
    "rst": """.. warning::

   Mind the gap.
""",
    "markdown": """!!! warning
    Mind the gap.
""",
    "asciidoc": """WARNING: Mind the gap.
""",
}

TITLED = {
    "rst": """.. admonition:: Careful

   Mind the gap.
""",
    "markdown": """!!! warning "Careful"
    Mind the gap.
""",
    "asciidoc": """.Careful
[WARNING]
Mind the gap.
""",
}


def _only_quote(source: str, source_format: str) -> BlockQuote:
    doc = to_ast(source.encode(), source_format=source_format)
    assert len(doc.children) == 1
    quote = doc.children[0]
    assert isinstance(quote, BlockQuote)
    return quote


@pytest.mark.unit
class TestOneRepresentation:
    @pytest.mark.parametrize("source_format", list(WARNINGS))
    def test_type(self, source_format):
        quote = _only_quote(WARNINGS[source_format], source_format)
        assert quote.metadata["admonition_type"] == "warning"
        assert "role" not in quote.metadata

    @pytest.mark.parametrize("source_format", list(TITLED))
    def test_title(self, source_format):
        assert _only_quote(TITLED[source_format], source_format).metadata["admonition_title"] == "Careful"


@pytest.mark.unit
class TestMarkdownRendersAnyAdmonition:
    """The Markdown renderer used to label only RST and MkDocs admonitions."""

    @pytest.mark.parametrize("source_format", list(WARNINGS))
    def test_labeled_quote_on_a_plain_flavor(self, source_format):
        output = to_markdown(WARNINGS[source_format].encode(), source_format=source_format, flavor="gfm")
        assert output.strip() == "> **Warning:** Mind the gap."

    @pytest.mark.parametrize("source_format", list(WARNINGS))
    def test_native_block_where_the_flavor_has_one(self, source_format):
        output = to_markdown(WARNINGS[source_format].encode(), source_format=source_format, flavor="markdown_plus")
        assert output.strip().splitlines() == ["!!! warning", "    Mind the gap."]

    def test_asciidoc_note_survives_markdown_plus_and_back(self):
        markdown = to_markdown(b"NOTE: Kept.", source_format="asciidoc", flavor="markdown_plus")
        assert _only_quote(markdown, "markdown").metadata["admonition_type"] == "note"
