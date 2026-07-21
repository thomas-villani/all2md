#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for MediaWiki parser."""

from all2md.ast import Table
from all2md.parsers.mediawiki import MediaWikiParser
from all2md.renderers.mediawiki import MediaWikiRenderer


class TestMediaWikiParserTables:
    """Tests for MediaWiki table parsing."""

    def test_parse_table_caption(self) -> None:
        """Test that |+ caption lines populate Table.caption."""
        wiki = """{|
|+ Cap
! Header
|-
| Cell
|}"""
        parser = MediaWikiParser()
        doc = parser.parse(wiki)

        assert len(doc.children) == 1
        table = doc.children[0]
        assert isinstance(table, Table)
        assert table.caption == "Cap"

        rendered = MediaWikiRenderer().render_to_string(doc)
        assert "|+ Cap" in rendered
        roundtrip = parser.parse(rendered)
        assert isinstance(roundtrip.children[0], Table)
        assert roundtrip.children[0].caption == "Cap"
