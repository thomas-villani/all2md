"""Tests for the PDF -> DOCX re-parse instrument (`benchmarks.pmc.docx_reparse`).

The instrument reports deltas, and a delta of zero is only evidence if the instrument can
produce a non-zero. Several tests below exist to show that it can: each hands it a known
loss and checks the loss is reported.
"""

from __future__ import annotations

from typing import Any

import pytest

from all2md.ast.nodes import (
    Document,
    Heading,
    LineBreak,
    Link,
    List,
    ListItem,
    Paragraph,
    Table,
    TableCell,
    TableRow,
    Text,
)
from benchmarks.pmc import docx_reparse

pytestmark = pytest.mark.unit

PROSE = "the quick brown fox jumps over the lazy dog while the cat watches from the warm windowsill"


def _table() -> Table:
    return Table(
        header=TableRow(cells=[TableCell(content=[Text("Group")]), TableCell(content=[Text("Count")])], is_header=True),
        rows=[TableRow(cells=[TableCell(content=[Text("Control")]), TableCell(content=[Text("15")])])],
    )


def _document(*, with_table: bool = True) -> Document:
    children: list[Any] = [
        Heading(level=1, content=[Text("Methods")]),
        Paragraph(content=[Text(PROSE + " "), Link(url="https://example.org/a", content=[Text("a link")])]),
        List(
            ordered=False,
            items=[
                ListItem(children=[Paragraph(content=[Text("first item")])]),
                ListItem(children=[Paragraph(content=[Text("second item")])]),
            ],
        ),
    ]
    if with_table:
        children.append(_table())
    return Document(children=children)


def test_an_unchanged_reading_reports_nothing_lost() -> None:
    same = docx_reparse.inventory(_document())
    compared = docx_reparse.compare_inventories(same, same)
    for name in ("headings", "tables", "lists", "links"):
        assert compared[name]["lost"] == 0
        assert compared[name]["gained"] == 0
    assert compared["node_counts_moved"] == {}


def test_a_dropped_table_is_reported_lost() -> None:
    """The control: the pairing must be able to fail, or its zeros mean nothing."""
    compared = docx_reparse.compare_inventories(
        docx_reparse.inventory(_document()), docx_reparse.inventory(_document(with_table=False))
    )
    assert compared["tables"]["lost"] == 1
    assert compared["tables"]["lost_examples"] == [[2, 2]]
    assert compared["node_counts_moved"]["Table"] == {"before": 1, "after": 0}


def test_a_heading_at_the_wrong_level_is_told_apart_from_a_lost_one() -> None:
    before = docx_reparse.inventory(Document(children=[Heading(level=1, content=[Text("Methods")])]))
    after = docx_reparse.inventory(Document(children=[Heading(level=2, content=[Text("Methods")])]))
    compared = docx_reparse.compare_inventories(before, after)
    assert compared["headings"]["lost"] == 1
    assert compared["heading_text"]["lost"] == 0


def test_text_survival_sees_duplication_that_a_set_would_not() -> None:
    unchanged = docx_reparse.text_survival(PROSE, PROSE)
    assert unchanged["lost"] == 0.0
    assert unchanged["added"] == 0.0

    doubled = docx_reparse.text_survival(PROSE, f"{PROSE} {PROSE}")
    assert doubled["lost"] == 0.0
    assert doubled["added"] > 0.4

    halved = docx_reparse.text_survival(PROSE, " ".join(PROSE.split()[:8]))
    assert halved["lost"] > 0.4


def test_lost_blocks_names_only_blocks_the_direct_reading_had() -> None:
    kept = "alpha bravo charlie delta echo foxtrot golf hotel india juliet"
    dropped = "kilo lima mike november oscar papa quebec romeo sierra tango"
    never = "uniform victor whiskey xray yankee zulu one two three four"
    truth = [("text_block", kept), ("text_block", dropped), ("text_block", never)]
    pdf_text = f"{kept} {dropped} {never}"
    lost = docx_reparse.lost_blocks(truth, f"{kept} {dropped}", kept, pdf_text)
    assert lost == [{"kind": "text_block", "text": dropped}]


def test_the_instrument_does_not_render_the_lanes_numbered_page_separators() -> None:
    """Numbered separators would reach the Word document as one review comment per page."""
    from all2md.options.pdf import PdfOptions
    from benchmarks.pmc.convert import PAGE_SEPARATOR_TEMPLATE

    options = docx_reparse.reparse_options()
    assert options.page_separator_template != PAGE_SEPARATOR_TEMPLATE
    assert options.page_separator_template == PdfOptions().page_separator_template
    assert options.include_page_numbers == PdfOptions().include_page_numbers
    # The rest of the lane's policy is kept.
    assert options.layout_analysis_mode == "enabled"
    assert options.attachment_mode == "base64"


@pytest.mark.docx
def test_the_docx_route_round_trips_basic_structure() -> None:
    """Headings, a table, a list and a link survive; this is the floor the ledger reads above."""
    pytest.importorskip("docx")
    document = _document()
    reading = docx_reparse.via_docx(document)
    compared = docx_reparse.compare_inventories(docx_reparse.inventory(document), docx_reparse.inventory(reading))
    for name in ("headings", "tables", "lists", "links"):
        assert compared[name]["lost"] == 0, (name, compared[name])


def _reading(article_id: str, *, docx_error: str | None = None) -> docx_reparse.ArticleReading:
    document = _document()
    projected = f"Methods {PROSE} a link first item second item Group Count Control 15"
    routes = ["direct", "markdown"] if docx_error else ["direct", "docx", "markdown"]
    return docx_reparse.ArticleReading(
        article_id=article_id,
        truth=(("text_block", PROSE),),
        pdf_text=projected,
        texts=dict.fromkeys(routes, projected),
        inventories={route: docx_reparse.inventory(document) for route in routes},
        errors={"docx": docx_error} if docx_error else {},
    )


def test_a_failed_route_is_listed_and_kept_out_of_the_shared_denominator() -> None:
    payload = docx_reparse.summarize_readings([_reading("A"), _reading("B", docx_error="ValueError: boom")])
    assert payload["articles"] == 2
    assert payload["articles_all_routes"] == 1
    assert payload["routes"]["docx"]["failures"] == ["B"]
    assert payload["routes"]["markdown"]["failures"] == []
    # Truth is compared over the articles every route completed, so the routes share a denominator.
    assert payload["direct"]["articles"] == 1
    assert payload["routes"]["docx"]["truth"]["attainable_recall_delta"] == 0.0
    assert payload["per_article"][1]["errors"] == {"docx": "ValueError: boom"}


def test_a_link_split_across_lines_is_one_span() -> None:
    def fragments(*parts: Any) -> Paragraph:
        return Paragraph(content=list(parts))

    doi = "https://doi.org/10.1/x"
    one = Link(url=doi, content=[Text("Cancer incidence")])
    two = Link(url=doi, content=[Text("worldwide. 2015.")])
    split = Document(children=[fragments(one, LineBreak(), Text(" "), two)])
    merged = Document(children=[fragments(Link(url=doi, content=[Text("Cancer incidence worldwide. 2015.")]))])
    assert docx_reparse.link_spans(split) == docx_reparse.link_spans(merged) == {doi: 1}

    cited_twice = Document(children=[fragments(one, Text(" and again "), two)])
    assert docx_reparse.link_spans(cited_twice) == {doi: 2}
