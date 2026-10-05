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

#: The same warning in every syntax that has one: name -> (source format, text).
WARNINGS = {
    "rst": (
        "rst",
        """.. warning::

   Mind the gap.
""",
    ),
    "mkdocs": (
        "markdown",
        """!!! warning
    Mind the gap.
""",
    ),
    "github-alert": (
        "markdown",
        """> [!WARNING]
> Mind the gap.
""",
    ),
    "asciidoc": (
        "asciidoc",
        """WARNING: Mind the gap.
""",
    ),
}

#: The same titled warning (GitHub alerts have no titles).
TITLED = {
    "rst": (
        "rst",
        """.. admonition:: Careful

   Mind the gap.
""",
    ),
    "mkdocs": (
        "markdown",
        """!!! warning "Careful"
    Mind the gap.
""",
    ),
    "asciidoc": (
        "asciidoc",
        """.Careful
[WARNING]
Mind the gap.
""",
    ),
}


def _only_quote(source: str, source_format: str) -> BlockQuote:
    doc = to_ast(source.encode(), source_format=source_format)
    assert len(doc.children) == 1
    quote = doc.children[0]
    assert isinstance(quote, BlockQuote)
    return quote


def _markdown(case: tuple[str, str], flavor: str) -> str:
    source_format, source = case
    return to_markdown(source.encode(), source_format=source_format, flavor=flavor).strip()


@pytest.mark.unit
class TestOneRepresentation:
    @pytest.mark.parametrize("name", list(WARNINGS))
    def test_type(self, name):
        source_format, source = WARNINGS[name]
        quote = _only_quote(source, source_format)
        assert quote.metadata["admonition_type"] == "warning"
        assert "role" not in quote.metadata

    @pytest.mark.parametrize("name", list(TITLED))
    def test_title(self, name):
        source_format, source = TITLED[name]
        assert _only_quote(source, source_format).metadata["admonition_title"] == "Careful"


@pytest.mark.unit
class TestMarkdownRendersAnyAdmonition:
    """The Markdown renderer used to label only RST and MkDocs admonitions."""

    @pytest.mark.parametrize("name", list(WARNINGS))
    def test_labeled_quote_on_a_plain_flavor(self, name):
        assert _markdown(WARNINGS[name], "commonmark") == "> **Warning:** Mind the gap."

    @pytest.mark.parametrize("name", list(WARNINGS))
    def test_github_alert_on_gfm(self, name):
        assert _markdown(WARNINGS[name], "gfm").splitlines() == ["> [!WARNING]", "> Mind the gap."]

    @pytest.mark.parametrize("name", list(WARNINGS))
    def test_native_block_where_the_flavor_has_one(self, name):
        assert _markdown(WARNINGS[name], "markdown_plus").splitlines() == ["!!! warning", "    Mind the gap."]

    @pytest.mark.parametrize("name", list(TITLED))
    def test_a_titled_admonition_keeps_its_title_on_gfm(self, name):
        """A GitHub alert has no title, so a titled admonition stays a labeled quote."""
        assert _markdown(TITLED[name], "gfm") == "> **Careful:** Mind the gap."

    def test_asciidoc_note_survives_markdown_plus_and_back(self):
        markdown = to_markdown(b"NOTE: Kept.", source_format="asciidoc", flavor="markdown_plus")
        assert _only_quote(markdown, "markdown").metadata["admonition_type"] == "note"
