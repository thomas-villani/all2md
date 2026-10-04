"""Tests for the Word read-back instrument (`benchmarks.pmc.docx_word`).

Word itself is only reachable on Windows with Office installed, so these tests hand the
instrument synthetic `WordReading`s -- the shape `WordReader` returns -- and check what it
makes of them. As with the re-parse instrument, several exist to show a known loss is
reported: a zero is only evidence if the instrument can produce a non-zero.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

import pytest

from all2md.ast.nodes import (
    Document,
    Heading,
    Link,
    List,
    ListItem,
    Paragraph,
    Table,
    TableCell,
    TableRow,
    Text,
)
from benchmarks.pmc import docx_word
from benchmarks.pmc.docx_word import WordHyperlink, WordListItem, WordParagraph, WordReading

pytestmark = pytest.mark.unit


def _items(*texts: str) -> list[ListItem]:
    return [ListItem(children=[Paragraph(content=[Text(text)])]) for text in texts]


def _table(rows: int) -> Table:
    return Table(rows=[TableRow(cells=[TableCell(content=[Text(f"r{index}")])]) for index in range(rows)])


def _document(*children: Any) -> Document:
    return Document(children=list(children))


def _reading(*paragraphs: tuple[str, int, str], **facts: Any) -> WordReading:
    return WordReading(
        paragraphs=tuple(WordParagraph(style=style, outline=outline, text=text) for style, outline, text in paragraphs),
        **facts,
    )


def test_the_module_does_not_import_win32com() -> None:
    """Everything but `WordReader` must run where Word cannot -- CI included."""
    probe = "import sys, benchmarks.pmc.docx_word; print('win32com' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "False"


def test_headings_are_what_the_navigation_pane_shows() -> None:
    word, promoted = docx_word.word_inventory(
        _reading(("Heading 1", 1, "Intro\r"), ("Normal", 10, "Body\r"), ("Heading 2", 2, "Detail\r"))
    )
    assert not promoted
    assert word.inventory.headings == {(1, "Intro"): 1, (2, "Detail"): 1}


def test_the_title_promotion_is_undone_as_the_parser_undoes_it() -> None:
    word, promoted = docx_word.word_inventory(
        _reading(("Normal", 10, "\r"), ("Title", 10, "Paper\r"), ("Heading 1", 1, "Methods\r"))
    )
    assert promoted
    assert word.inventory.headings == {(1, "Paper"): 1, (2, "Methods"): 1}


def test_a_heading_word_reads_as_body_text_is_lost_in_word_only() -> None:
    document = _document(Heading(level=1, content=[Text("Intro")]), Heading(level=2, content=[Text("Detail")]))
    direct = docx_word.ast_reading(document)
    word, _ = docx_word.word_inventory(_reading(("Heading 1", 1, "Intro\r"), ("Heading 2", 10, "Detail\r")))
    split = docx_word.blame(direct, direct, word)
    assert split["headings"]["word_only"] == 1
    assert split["headings"]["word_only_examples"] == [[2, "Detail"]]
    assert split["heading_text"]["word_only"] == 1


def test_lists_sharing_a_word_identity_are_one_list_to_word() -> None:
    document = _document(
        List(ordered=False, items=_items("a")),
        Paragraph(content=[Text("between")]),
        List(ordered=False, items=_items("b")),
    )
    direct = docx_word.ast_reading(document)
    word, _ = docx_word.word_inventory(
        _reading(list_items=(WordListItem(list_id=0, marker="\uf0b7"), WordListItem(list_id=0, marker="\uf0b7")))
    )
    compared = docx_word.compare_readings(direct, word)
    assert compared["lists"]["lost"] == 2
    assert compared["lists"]["gained_examples"] == [[False, 2]]
    # Every item still carries its bullet: the grouping changed, not what a reader sees.
    assert compared["list_items"]["lost"] == 0


def test_list_items_are_paired_by_the_number_word_displays() -> None:
    document = _document(List(ordered=True, start=3, items=_items("c", "d")))
    direct = docx_word.ast_reading(document)
    continued, _ = docx_word.word_inventory(
        _reading(list_items=(WordListItem(list_id=7, marker="1."), WordListItem(list_id=7, marker="2.")))
    )
    compared = docx_word.compare_readings(direct, continued)
    assert compared["lists"]["lost"] == 0
    assert compared["list_items"]["lost"] == 2
    assert compared["list_items"]["lost_examples"] == [[True, 3], [True, 4]]


def test_adjacent_tables_word_joins_are_lost_in_word_only() -> None:
    document = _document(_table(2), _table(3))
    direct = docx_word.ast_reading(document)
    word, _ = docx_word.word_inventory(_reading(tables=((5, 1),)))
    split = docx_word.blame(direct, direct, word)
    assert split["tables"] == {
        "word_only": 2,
        "parser_only": 0,
        "both": 0,
        "word_only_examples": [[2, 1], [3, 1]],
        "parser_only_examples": [],
    }


def test_a_loss_word_does_not_share_is_the_parsers() -> None:
    document = _document(_table(2))
    direct = docx_word.ast_reading(document)
    parser = docx_word.ast_reading(_document())
    word, _ = docx_word.word_inventory(_reading(tables=((2, 1),)))
    split = docx_word.blame(direct, parser, word)
    assert split["tables"]["parser_only"] == 1
    assert split["tables"]["word_only"] == 0


def test_a_bare_host_reads_back_with_its_root_path() -> None:
    document = _document(Paragraph(content=[Link(url="https://example.org", content=[Text("site")])]))
    direct = docx_word.ast_reading(document)
    word, _ = docx_word.word_inventory(_reading(hyperlinks=(WordHyperlink(url="https://example.org/"),)))
    assert docx_word.compare_readings(direct, word)["links"]["lost"] == 0
    assert docx_word.url_key("https://example.org/a?b") == "https://example.org/a?b"
    assert docx_word.url_key("http://CRAN.R-project.org/a%20b") == docx_word.url_key("http://cran.r-project.org/a b")
    assert docx_word.url_key("mailto:a@example.org") == "mailto:a@example.org"


def test_hyperlinks_joined_by_whitespace_are_one_span() -> None:
    word, _ = docx_word.word_inventory(
        _reading(
            hyperlinks=(
                WordHyperlink(url="https://example.org/a"),
                WordHyperlink(url="https://example.org/a", joins_previous=True),
                WordHyperlink(url="https://example.org/a"),
            )
        )
    )
    assert word.inventory.links == {"https://example.org/a": 2}


def test_captions_are_paragraphs_in_the_caption_style() -> None:
    word, _ = docx_word.word_inventory(
        _reading(("Caption", 10, "Figure 1.\x0bA cat\r"), ("Normal", 10, "Figure 2. Not one\r"))
    )
    assert word.inventory.captions == {"Figure 1. A cat": 1}


def test_clean_text_drops_control_characters_and_collapses_space() -> None:
    assert docx_word.clean_text("a\x07 b\x0b\x0bc\r") == "a b c"


def test_a_failed_stage_is_listed_and_kept_out_of_the_totals() -> None:
    document = _document(Heading(level=1, content=[Text("Intro")]))
    direct = docx_word.ast_reading(document)
    word, _ = docx_word.word_inventory(_reading(("Heading 1", 1, "Intro\r")))
    raw = _reading(("Heading 1", 1, "Intro\r"), compatibility_mode=14)
    readings = [
        docx_word.ArticleWordReading("A", {"direct": direct, "parser": direct, "word": word}, raw),
        docx_word.ArticleWordReading("B", {"direct": direct, "parser": direct}, errors={"word": "boom"}),
    ]
    payload = docx_word.summarize(readings)
    assert payload["articles"] == 2
    assert payload["articles_read"] == 1
    assert payload["failures"]["word"] == ["B"]
    assert payload["structure"]["headings"]["direct_vs_word"]["before"] == 1
    assert payload["word"]["compatibility_modes"] == {"14": 1}
    assert payload["word"]["styles"] == {"Heading 1": 1}
