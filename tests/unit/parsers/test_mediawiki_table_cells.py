#  Copyright (c) 2025 Tom Villani, Ph.D.
"""MediaWiki table cell attribute stripping."""

from all2md.ast import Table, Text
from all2md.parsers.mediawiki import MediaWikiParser


class TestMediaWikiTableCellPipes:
    def test_literal_pipe_in_cell_text_preserved(self) -> None:
        wiki = "{|\n|-\n| pipe: a|b\n|}"
        doc = MediaWikiParser().parse(wiki)
        table = doc.children[0]
        assert isinstance(table, Table)
        cell = table.rows[0].cells[0]
        assert isinstance(cell.content[0], Text)
        assert cell.content[0].content == "pipe: a|b"

    def test_style_attribute_still_stripped(self) -> None:
        wiki = '{|\n|-\n| style="color:red"| red cell\n|}'
        doc = MediaWikiParser().parse(wiki)
        table = doc.children[0]
        assert isinstance(table, Table)
        cell = table.rows[0].cells[0]
        assert isinstance(cell.content[0], Text)
        assert cell.content[0].content == "red cell"

    def test_wikilink_pipe_in_cell_preserved(self) -> None:
        wiki = "{|\n|-\n| [[Target|label]]\n|}"
        doc = MediaWikiParser().parse(wiki)
        table = doc.children[0]
        assert isinstance(table, Table)
        cell = table.rows[0].cells[0]
        assert isinstance(cell.content[0], Text)
        assert cell.content[0].content == "[[Target|label]]"
