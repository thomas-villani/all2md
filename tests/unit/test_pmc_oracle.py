"""Tests for the PMC born-digital oracle: JATS projection, page assignment, and its controls.

Several of these pin findings rather than code. Where a test's name states a measured fact,
the fact was measured first and the behaviour written to match it -- not the other way round.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pytest

from benchmarks.pmc import alignment, article, benchmark, convert, oracles, pages

pytestmark = pytest.mark.unit


def _jats(body: str) -> Any:
    return ElementTree.fromstring(f"<article><body>{body}</body></article>")


# ---------------------------------------------------------------------------
# Ground-truth projection
# ---------------------------------------------------------------------------


def test_a_table_nested_in_a_paragraph_is_its_own_block() -> None:
    """JATS nests floats inside prose, and swallowing them corrupted three things at once.

    Taking a ``<p>``'s full text fused the paragraph, the caption and every cell into one
    string: the table vanished from the ground truth, the caption stopped being its own
    page object, and the fused block straddled the paragraph's page and the table's page so
    it was placed on the wrong one.
    """
    root = _jats(
        "<p>Results appear in <xref>Table 1</xref>."
        "<table-wrap><label>Table 1</label><caption><p>Characteristics</p></caption>"
        "<table><tr><th>Group</th><th>N</th></tr><tr><td>Control</td><td>15</td></tr></table>"
        "</table-wrap></p>"
    )
    blocks, projection = oracles.project_jats(root)

    prose = [block for block in blocks if block.kind == "text_block"]
    tables = [block for block in blocks if block.kind == "table"]
    assert len(tables) == 1
    assert tables[0].table is not None
    assert tables[0].table.rows == 2
    # The paragraph keeps its own words and the cross-reference, and none of the table's.
    assert prose[0].text == "Results appear in Table 1 ."
    assert "Characteristics" not in prose[0].text
    assert "Control" not in prose[0].text
    # Caption and cell text reach the text stream as separate page objects.
    assert "Table 1 Characteristics" in projection.text_blocks
    assert any("Control" in block for block in projection.text_blocks)


def test_cross_reference_text_is_kept_because_the_page_prints_it() -> None:
    blocks, _ = oracles.project_jats(_jats("<p>See <xref ref-type='table'>Table 3</xref> for detail.</p>"))
    assert blocks[0].text == "See Table 3 for detail."


def test_unrendered_metadata_never_reaches_the_text_stream() -> None:
    root = ElementTree.fromstring(
        "<article><front><article-meta>"
        "<article-id>10.1000/xyz</article-id><counts><page-count count='9'/></counts>"
        "<title-group><article-title>Real Title</article-title></title-group>"
        "</article-meta></front></article>"
    )
    _, projection = oracles.project_jats(root)
    joined = " ".join(projection.text_blocks)
    assert "Real Title" in joined
    assert "10.1000/xyz" not in joined


def test_jats_and_html_tables_are_counted_identically() -> None:
    """The two lanes must not measure table shape differently, or they are incomparable."""
    from benchmarks.omnidocbench.oracles import _html_table

    markup = (
        "<table><tr><th colspan='2'>Head</th></tr><tr><td rowspan='2'>A</td><td>B</td></tr><tr><td>C</td></tr></table>"
    )
    jats = oracles._jats_table(ElementTree.fromstring(markup))
    html = _html_table(markup)
    assert (jats.rows, jats.columns, jats.cell_slots) == (html.rows, html.columns, html.cell_slots)
    assert jats.text == html.text


def test_a_table_wrap_without_a_table_is_not_scored_as_an_empty_table() -> None:
    """It renders as a graphic and a caption; an empty Table would punish a parser for nothing."""
    blocks, projection = oracles.project_jats(
        _jats("<table-wrap><label>Table 2</label><caption><p>Only an image</p></caption></table-wrap>")
    )
    assert projection.tables == ()
    assert blocks[0].kind == "text_block"
    assert "Only an image" in blocks[0].text


def test_element_text_is_joined_not_concatenated() -> None:
    """Concatenation fused ``<label>Table 2</label>`` onto its caption as one bogus token."""
    blocks, _ = oracles.project_jats(_jats("<p><italic>Table 2</italic>obtained results</p>"))
    assert "2obtained" not in blocks[0].text


def test_coverage_reports_ground_truth_against_the_page_rather_than_assuming_it() -> None:
    _, projection = oracles.project_jats(_jats("<p>one two three four</p>"))
    assert oracles.coverage(projection, pdf_words=4) == pytest.approx(1.0)
    assert oracles.coverage(projection, pdf_words=8) == pytest.approx(0.5)
    assert oracles.coverage(projection, pdf_words=0) == 0.0


# ---------------------------------------------------------------------------
# Page boundaries
# ---------------------------------------------------------------------------


def _document(*children: Any) -> Any:
    from all2md.ast.nodes import Document

    return Document(children=list(children))


def _separator(page_num: int, total: int) -> Any:
    from all2md.ast.nodes import Comment

    return Comment(
        content=convert.PAGE_SEPARATOR_TEMPLATE.format(page_num=page_num, total_pages=total),
        metadata={"comment_type": "page_separator"},
    )


def _paragraph(text: str) -> Any:
    from all2md.ast.nodes import Paragraph, Text

    return Paragraph(content=[Text(content=text)])


def test_pages_are_recovered_from_one_conversion() -> None:
    document = _document(_paragraph("one"), _separator(1, 3), _paragraph("two"), _separator(2, 3), _paragraph("three"))
    recovered = convert.split_pages(document, 3)
    assert [len(page.children) for page in recovered] == [1, 1, 1]


def test_a_dropped_page_is_an_error_rather_than_a_silent_shift() -> None:
    """Without this the parser's missing page would shift every later page's ground truth."""
    document = _document(_paragraph("one"), _separator(1, 3), _paragraph("two"))
    with pytest.raises(convert.PageBoundaryError, match="2 page group"):
        convert.split_pages(document, 3)


def test_out_of_order_separators_are_an_error() -> None:
    document = _document(_paragraph("one"), _separator(2, 3), _paragraph("two"), _separator(1, 3), _paragraph("x"))
    with pytest.raises(convert.PageBoundaryError, match="not consecutive"):
        convert.split_pages(document, 3)


def test_an_unrecognized_separator_is_an_error() -> None:
    from all2md.ast.nodes import Comment

    document = _document(
        _paragraph("one"),
        Comment(content="-----", metadata={"comment_type": "page_separator"}),
        _paragraph("two"),
    )
    with pytest.raises(convert.PageBoundaryError, match="unparsable"):
        convert.split_pages(document, 2)


def test_the_lane_leaves_ocr_enabled_so_a_non_born_digital_corpus_would_say_so() -> None:
    options = convert.pdf_options()
    assert options.ocr.enabled is True
    assert options.ocr.mode == "auto"
    assert options.include_page_numbers is True


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------


def _page(text: str) -> pages.PageText:
    tokens = alignment.normalize(text)
    return pages.PageText(grams=alignment.ngrams(tokens), phrase=" ".join(tokens), tokens=set(tokens))


def test_token_placement_finds_a_block_whose_word_order_the_page_does_not_print() -> None:
    """A structured citation lists its fields in an order the rendered page never uses."""
    citation = "Ferlay J Soerjomataram I Int J Cancer 2015 10.1002/ijc.29210"
    rendered = _page("Ferlay J, Soerjomataram I, et al. Int J Cancer. 2015. doi:10.1002/ijc.29210")
    tokens = alignment.normalize(citation)

    assert alignment.place_block(alignment.ngrams(tokens), [rendered.grams]).verdict == "missing"
    assert alignment.place_by_tokens(tokens, [rendered.tokens]) == 0


def test_token_placement_refuses_a_page_that_holds_too_little() -> None:
    tokens = alignment.normalize("alpha beta gamma delta epsilon zeta eta theta")
    assert alignment.place_by_tokens(tokens, [_page("alpha beta unrelated words here").tokens]) is None


def test_token_placement_refuses_a_block_with_too_few_distinct_words() -> None:
    """Below a handful of words a bag is not distinctive enough to name a page."""
    tokens = alignment.normalize("the the results")
    assert alignment.place_by_tokens(tokens, [_page("the results section follows here").tokens]) is None


def test_token_placement_breaks_ties_toward_the_earliest_page() -> None:
    tokens = alignment.normalize("alpha beta gamma delta epsilon")
    page = _page("alpha beta gamma delta epsilon")
    assert alignment.place_by_tokens(tokens, [page.tokens, page.tokens, page.tokens]) == 0


def test_a_block_crossing_a_page_break_is_split_rather_than_counted_whole_twice() -> None:
    """Counting it whole on both pages would guarantee a mismatch on both."""
    head = "the quick brown fox jumps over the lazy dog and keeps running onward"
    tail = "through the tall wet grass until it reaches the far riverbank at dusk"
    block = oracles.JatsBlock(kind="text_block", text=f"{head} {tail}")
    assigned = pages.assign_pages([block], [_page(head), _page(tail)])

    assert assigned.assignments["spans"] == 1
    first, second = assigned.pages[0][0].block.text, assigned.pages[1][0].block.text
    assert first.startswith("the quick brown fox")
    assert second.endswith("far riverbank at dusk")
    # The whole block appears on neither page on its own.
    assert first != block.text and second != block.text


def test_a_split_that_cannot_be_mapped_back_is_counted_rather_than_applied_wrongly() -> None:
    """De-hyphenation makes one token out of two words, so the raw offset would be wrong."""
    assert pages._split_at_token("run-\nning water", token_index=1) is None


def test_a_short_block_is_placed_by_a_phrase_that_only_one_page_carries() -> None:
    block = oracles.JatsBlock(kind="title", text="Statistical Analysis")
    assigned = pages.assign_pages(
        [block],
        [_page("introduction and background material"), _page("statistical analysis was performed")],
    )
    assert assigned.assignments["phrase"] == 1
    assert assigned.pages[1][0].assignment == "phrase"


def test_a_short_block_on_no_unique_page_takes_the_page_of_what_it_introduces() -> None:
    """A heading is kept with the text it introduces, so its successor's page is its own."""
    heading = oracles.JatsBlock(kind="title", text="Results")
    body = oracles.JatsBlock(
        kind="text_block",
        text="participants completed the protocol without any reported adverse events at all",
    )
    assigned = pages.assign_pages(
        [heading, body],
        [
            # "Results" appears on both pages, so no phrase uniquely identifies one.
            _page("results were mixed across every measured outcome results"),
            _page("results participants completed the protocol without any reported adverse events at all"),
        ],
    )
    assert [placed.assignment for placed in assigned.pages[1]] == ["inherited", "clean"]
    assert assigned.pages[0] == ()


def test_a_pending_short_block_takes_the_phrase_placed_blocks_page_not_a_later_one() -> None:
    """A phrase placement must flush pending short blocks too, or they inherit the wrong page.

    "Results" is ambiguous (both pages print it), so it goes to `pending`. "Statistical
    Analysis" then places by unique phrase on page 1. A later paragraph places cleanly on
    page 2. The heading belongs with the phrase-placed block that follows it, on page 1 --
    not with whatever happens to place after that.
    """
    heading = oracles.JatsBlock(kind="title", text="Results")
    subheading = oracles.JatsBlock(kind="title", text="Statistical Analysis")
    body = oracles.JatsBlock(
        kind="text_block",
        text="participants completed the protocol without any reported adverse events at all",
    )
    assigned = pages.assign_pages(
        [heading, subheading, body],
        [
            # "Results" appears on both pages, so no phrase uniquely identifies one.
            _page("results were mixed across every measured outcome results"),
            _page("results statistical analysis was performed today"),
            _page("participants completed the protocol without any reported adverse events at all"),
        ],
    )
    assert [placed.assignment for placed in assigned.pages[1]] == ["inherited", "phrase"]
    assert [placed.block.text for placed in assigned.pages[1]] == ["Results", "Statistical Analysis"]
    assert assigned.pages[0] == ()
    assert [placed.assignment for placed in assigned.pages[2]] == ["clean"]


def test_a_short_block_with_nothing_after_it_is_excluded_rather_than_guessed() -> None:
    trailing = oracles.JatsBlock(kind="title", text="Results")
    assigned = pages.assign_pages([trailing], [_page("results here"), _page("results there")])
    assert assigned.assignments["excluded"] == 1
    assert assigned.excluded == ("too_short",)


def test_unplaceable_blocks_are_counted_as_an_error_budget_not_dropped() -> None:
    present = oracles.JatsBlock(kind="text_block", text="alpha beta gamma delta epsilon zeta eta theta iota")
    absent = oracles.JatsBlock(kind="text_block", text="wholly unrelated wording nowhere near this document at all")
    assigned = pages.assign_pages([present, absent], [_page("alpha beta gamma delta epsilon zeta eta theta iota")])
    assert assigned.assignments["excluded"] == 1
    assert assigned.error_budget == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Article-level recall
# ---------------------------------------------------------------------------


def test_recall_is_reported_against_what_the_pdf_can_actually_yield() -> None:
    """39% of this corpus's blocks are unreachable for any parser, so raw recall misleads."""
    reachable = "the participants completed every session of the supervised training programme"
    unreachable = "Ferlay J Soerjomataram I Int J Cancer 2015"
    report = article.measure_recall(
        [
            (
                "A",
                [("text_block", reachable), ("text_block", unreachable)],
                reachable,
                reachable,
            ),
        ]
    )
    assert report.scored == 2
    assert report.ceiling == pytest.approx(0.5)
    assert report.recall == pytest.approx(0.5)
    # All of what was available was recovered, even though raw recall reads as half.
    assert report.attainable_recall == pytest.approx(1.0)


def test_recall_falls_when_the_parser_loses_recoverable_text() -> None:
    reachable = "the participants completed every session of the supervised training programme"
    report = article.measure_recall([("A", [("text_block", reachable)], "nothing useful here", reachable)])
    assert report.ceiling == pytest.approx(1.0)
    assert report.attainable_recall == pytest.approx(0.0)


def test_a_single_article_reports_no_control_rather_than_a_flattering_zero() -> None:
    """With nothing to mismatch against, 0.0% would read exactly like a passing control."""
    text = "the participants completed every session of the supervised training programme"
    report = article.measure_recall([("A", [("text_block", text)], text, text)])
    assert report.control_scored == 0
    assert report.control_recall == 0.0


def test_recall_collapses_against_a_different_article() -> None:
    """A recall figure means nothing unless the same method fails on the wrong document."""
    first = "the participants completed every session of the supervised training programme"
    second = "vector drawings were counted on each page of the publisher issued document"
    report = article.measure_recall(
        [("A", [("text_block", first)], first, first), ("B", [("text_block", second)], second, second)]
    )
    assert report.recall == pytest.approx(1.0)
    assert report.control_recall == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Precision: does the output say anything the document does not
# ---------------------------------------------------------------------------

_LAYER = "the participants completed every session of the supervised training programme"
_FOREIGN = "vector drawings were counted on each page of the publisher issued document"


def _precision(emitted: str, layer: str = _LAYER) -> article.PrecisionReport:
    return article.measure_precision([("A", [], emitted, layer)])


def test_reproducing_the_text_layer_is_fully_supported() -> None:
    report = _precision(_LAYER)
    assert report.precision == pytest.approx(1.0)
    assert report.duplication == pytest.approx(0.0)


def test_precision_falls_when_the_output_invents_text() -> None:
    """The proven case here is auto-OCR replacing a good text layer with its own guesses."""
    report = _precision(f"{_LAYER} {_FOREIGN}")
    assert report.precision < 0.55
    assert report.novel_share > 0.4
    # Recall is untouched by the invention, which is the whole reason for the second number.
    recall = article.measure_recall([("A", [("text_block", _LAYER)], f"{_LAYER} {_FOREIGN}", _LAYER)])
    assert recall.attainable_recall == pytest.approx(1.0)


def test_reordering_the_document_is_not_counted_as_inventing_text() -> None:
    """Measured: seam n-grams are 4.8% of emitted against 0.5% genuinely novel.

    all2md orders columns and joins blocks; the text layer comes out in PyMuPDF's order.
    Charging the parser for every disagreement would make the headline nine times worse than
    it deserves, so the two are separated rather than summed.
    """
    first = "the participants completed every session of the supervised training programme"
    second = "vector drawings were counted on each page of the publisher issued document"
    report = _precision(f"{second} {first}", f"{first} {second}")

    assert report.novel == 0
    assert report.resequenced > 0
    # Strict precision registers the seam; the number worth reading does not.
    assert report.precision < 1.0
    assert report.novel_share == pytest.approx(0.0)


def test_duplication_is_visible_where_a_set_based_score_is_blind() -> None:
    """Emitting a block twice barely moves precision, because the multiset is what doubled.

    Precision is not *completely* blind to it: rejoining the text creates a handful of
    n-grams spanning the seam that the layer does not hold. Those are a rounding error in a
    real article and would be the whole signal in a two-sentence one, so the block is
    duplicated inside surrounding text here rather than on its own.
    """
    layer = f"{_LAYER} and afterwards {_FOREIGN} and finally the analysis was repeated twice"
    clean = _precision(layer, layer)
    doubled = _precision(f"{_LAYER} and afterwards {layer}", layer)

    # The comparison is against the same document emitted once, so the threshold is a
    # measured difference rather than a number chosen to pass.
    assert clean.duplication == pytest.approx(0.0)
    assert doubled.duplication > 0.15
    # Precision meanwhile barely moves: only the seam is unsupported.
    assert clean.precision == pytest.approx(1.0)
    assert doubled.precision > 0.85


def test_precision_collapses_against_a_different_article() -> None:
    """Without the control, a high precision may only mean English n-grams are common."""
    report = article.measure_precision(
        [("A", [], _LAYER, _LAYER), ("B", [], _FOREIGN, _FOREIGN)],
    )
    assert report.precision == pytest.approx(1.0)
    assert report.control_precision == pytest.approx(0.0)


def test_a_single_article_reports_no_precision_control_rather_than_a_flattering_zero() -> None:
    report = _precision(_LAYER)
    assert report.control_emitted == 0
    assert report.control_precision == 0.0


def test_an_empty_conversion_scores_zero_precision_rather_than_a_perfect_one() -> None:
    """Emitting nothing says nothing false. It must not therefore look flawless."""
    report = _precision("")
    assert report.emitted == 0
    assert report.precision == 0.0


# ---------------------------------------------------------------------------
# Controls that qualify the scores
# ---------------------------------------------------------------------------


def _projection(*blocks: str) -> Any:
    from benchmarks.omnidocbench.oracles import PageProjection

    return PageProjection(
        text_blocks=tuple(blocks),
        block_kinds=tuple("text_block" for _ in blocks),
        tables=(),
        formulas=(),
    )


def test_every_mutation_actually_damages_the_output_it_is_given() -> None:
    """A control that does not change anything cannot show that a score can fail."""
    original = _projection("alpha", "beta", "gamma", "delta")
    assert benchmark.MUTATIONS["reversed"](original).text_blocks == ("delta", "gamma", "beta", "alpha")
    assert benchmark.MUTATIONS["halved"](original).text_blocks == ("alpha", "gamma")
    assert benchmark.MUTATIONS["shuffled"](original).text_blocks != original.text_blocks


def test_shuffling_is_seeded_so_two_runs_are_comparable() -> None:
    original = _projection(*(f"block {index}" for index in range(12)))
    assert benchmark.MUTATIONS["shuffled"](original) == benchmark.MUTATIONS["shuffled"](original)


def test_block_structure_is_recorded_but_marked_unusable_as_a_gate() -> None:
    """It rises when half the content is deleted, so gating on it would reward dropping blocks."""
    assert "block_structure_similarity" in benchmark.UNGATEABLE


def test_a_dimension_carries_its_control_and_its_mutation_drops() -> None:
    page = benchmark.PageEvaluation(
        article_id="PMC1.1",
        page=0,
        scores={"text_content_similarity": 0.8},
        control_scores={"text_content_similarity": 0.2},
        mutated={name: {"text_content_similarity": 0.3} for name in benchmark.MUTATIONS},
        truth_blocks=3,
        truth_tables=0,
        emitted_blocks=3,
        emitted_tables=0,
    )
    summary = benchmark._dimension([page], "text_content_similarity")
    assert summary is not None
    assert summary["discrimination"] == pytest.approx(0.6)
    assert summary["mutation_drop"]["reversed"] == pytest.approx(0.5)


def test_page_scores_and_the_error_budget_come_from_the_same_run(tmp_path: Path) -> None:
    """The excluded blocks must be reported beside the scores they were excluded from."""
    payload = benchmark.normalize_results(
        snapshot=type(
            "Snapshot",
            (),
            {
                "manifest_sha256": "a" * 64,
                "bucket": "b",
                "complete": True,
                "expected_articles": 1,
                "unavailable": {},
            },
        )(),
        evaluations=[
            benchmark.ArticleEvaluation(
                article_id="PMC1.1",
                pages=(),
                assignments={"clean": 9, "excluded": 1},
                unsplit_spans=0,
                excluded={"missing": 1},
                coverage=1.0,
                ocr_page_fraction=0.0,
                degraded=(),
                duration_seconds=0.1,
                ground_truth_blocks=10,
            )
        ],
        recall=article.measure_recall([]),
        precision=article.measure_precision([]),
        binding=article.measure_binding([]),
        all2md_commit="deadbeef",
        parser_runtime={},
    )
    assert payload["projection"]["error_budget"] == pytest.approx(0.1)
    assert payload["projection"]["excluded_reasons"] == {"missing": 1}
    assert payload["ocr_articles"] == []


def test_recall_and_precision_are_reported_together() -> None:
    """Either number alone rewards a degenerate converter, so the payload carries both."""
    layer = f"{_LAYER} and afterwards {_FOREIGN}"
    scored = [("A", [("text_block", _LAYER)], layer, layer), ("B", [("text_block", _FOREIGN)], _FOREIGN, _FOREIGN)]
    payload = benchmark.normalize_results(
        snapshot=type(
            "Snapshot",
            (),
            {
                "manifest_sha256": "a" * 64,
                "bucket": "b",
                "complete": True,
                "expected_articles": 2,
                "unavailable": {},
            },
        )(),
        evaluations=[],
        recall=article.measure_recall(scored),
        precision=article.measure_precision(scored),
        binding=article.measure_binding([]),
        all2md_commit="deadbeef",
        parser_runtime={},
    )
    assert payload["article_recall"]["attainable_recall"] > 0.0
    assert payload["article_precision"]["precision"] == pytest.approx(1.0)
    assert payload["article_precision"]["control_emitted"] > 0


# ---------------------------------------------------------------------------
# Figure-to-caption binding
# ---------------------------------------------------------------------------

_CAPTION = "Figure 1 mean response amplitude across the four experimental conditions shown"
_OTHER_CAPTION = "Figure 2 electrode placement viewed from above with the reference channel marked"


def test_a_figure_caption_is_ground_truth_separate_from_the_text_stream() -> None:
    """`walk` already yields the caption as prose; binding needs it as a figure of its own."""
    root = _jats(f"<fig><label>Figure 1</label><caption><p>{_CAPTION}</p></caption></fig>")

    figures = tuple(oracles.walk_figures(root))

    assert len(figures) == 1
    assert figures[0].label == "Figure 1"
    assert _CAPTION in figures[0].caption
    # The same figure still reaches the text stream, unchanged: the two instruments read the
    # same article and must not disagree about what it contains.
    assert any(_CAPTION in block.text for block in oracles.walk(root))


def test_unrendered_subtrees_hold_no_figures() -> None:
    """A `<fig>` under a skipped element would be ground truth the page never prints."""
    root = _jats(f"<counts><fig><caption><p>{_CAPTION}</p></caption></fig></counts>")

    assert tuple(oracles.walk_figures(root)) == ()


def test_a_bound_caption_is_recognised() -> None:
    """Verify the judge can pass: the instrument must report a correct binding as correct.

    This lane's binding rate is **zero by construction** until `Image` gains a caption field
    (#338), and a gate whose only observable value is zero is indistinguishable from one
    that cannot fire at all. Every other test here would pass against an instrument that
    always returns zero; this one would not.
    """
    report = article.measure_binding([("A", [_CAPTION], [(_CAPTION, "")], _CAPTION)])

    assert report.scored == 1
    assert report.binding_rate == pytest.approx(1.0)
    assert report.misfiled == 0


def test_a_caption_that_reached_only_the_prose_is_not_counted_as_bound() -> None:
    """The whole point: caption text surviving is not the caption being bound.

    On this corpus caption text recall is close to 100% while nothing is bound at all, and
    an instrument that could not tell those apart would report the parser as already correct.
    """
    report = article.measure_binding([("A", [_CAPTION], [("", "")], f"prose {_CAPTION} prose")])

    assert report.binding_rate == pytest.approx(0.0)
    assert report.caption_recall == pytest.approx(1.0)


def test_a_caption_written_into_alt_text_is_counted_apart() -> None:
    """Detector worked, AST had nowhere to put the result -- a different defect from a miss."""
    report = article.measure_binding([("A", [_CAPTION], [("", _CAPTION)], _CAPTION)])

    assert report.binding_rate == pytest.approx(0.0)
    assert report.misfiled_rate == pytest.approx(1.0)


def test_a_tiled_figure_counts_once_rather_than_once_per_panel() -> None:
    """Measured: 231 ground-truth figures emit 345 rasters, one of them tiled fifteen ways.

    Scoring the emitted side would let a single tiled figure outweigh whole articles.
    """
    panels = [(_CAPTION, "")] * 15
    report = article.measure_binding([("A", [_CAPTION], panels, _CAPTION)])

    assert report.bound == 1
    assert report.scored == 1
    assert report.images_emitted == 15
    assert report.captioned_emitted == 15


def test_binding_collapses_against_a_different_article() -> None:
    """Without the control, a high binding rate might only mean captions look alike."""
    report = article.measure_binding(
        [
            ("A", [_CAPTION], [(_CAPTION, "")], _CAPTION),
            ("B", [_OTHER_CAPTION], [(_OTHER_CAPTION, "")], _OTHER_CAPTION),
        ]
    )

    assert report.binding_rate == pytest.approx(1.0)
    assert report.control_binding_rate == pytest.approx(0.0)
    assert report.control_scored == 2


def test_a_single_article_reports_no_binding_control_rather_than_a_flattering_zero() -> None:
    """With one article there is no other to score against, as for recall and precision."""
    report = article.measure_binding([("A", [_CAPTION], [(_CAPTION, "")], _CAPTION)])

    assert report.control_scored == 0
    assert report.control_binding_rate == pytest.approx(0.0)


def test_a_figure_container_counts_once_with_its_caption() -> None:
    """A three-panel `Figure` is one emitted figure, matching JATS ``<fig>`` granularity.

    The container's caption is the entry's caption, and the panels' alt texts fold into
    ``alt_text`` so the misfiled control keeps seeing a caption that landed there.
    """
    from all2md.ast.nodes import Document, Figure, Image, Paragraph

    doc = Document(
        children=[
            Figure(
                children=[
                    Paragraph(content=[Image(url="p1.png", alt_text="panel A")]),
                    Paragraph(content=[Image(url="p2.png", alt_text="panel B")]),
                ],
                caption="Figure 1. Two panels.",
            )
        ]
    )

    assert convert.collect_figures(doc) == (
        convert.EmittedFigure(alt_text="panel A panel B", caption="Figure 1. Two panels."),
    )


def test_a_bare_captioned_image_reads_exactly_as_it_did_before_the_container() -> None:
    """Parity: widening the oracle to `Figure` must not move the numbers on the old shape."""
    from all2md.ast.nodes import Document, Image, Paragraph

    doc = Document(children=[Paragraph(content=[Image(url="x.png", alt_text="alt", caption="Cap")])])

    assert convert.collect_figures(doc) == (convert.EmittedFigure(alt_text="alt", caption="Cap"),)


def test_an_empty_figure_is_an_emitted_figure_and_a_captionless_one_cannot_bind() -> None:
    """The vector-drawn shape (caption, no raster) is observable; no caption means no bind.

    The second half is the judge failing on purpose: an emitted container with an empty
    caption must not satisfy the binding oracle.
    """
    from all2md.ast.nodes import Document, Figure

    doc = Document(children=[Figure(children=[], caption="Figure 2. Vector only."), Figure(children=[])])
    vector, captionless = convert.collect_figures(doc)

    assert vector == convert.EmittedFigure(alt_text="", caption="Figure 2. Vector only.")
    assert captionless.caption == ""
    report = article.measure_binding([("A", [_CAPTION], [(captionless.alt_text, captionless.caption)], _CAPTION)])
    assert report.bound == 0


def test_the_lane_extracts_images_so_a_figure_defect_is_observable() -> None:
    """Under the default `alt_text` mode the parser emits none, making the oracle vacuous.

    The same argument the lane already makes for leaving OCR enabled: a policy that switches
    the subsystem off makes its own clean result true by construction.
    """
    assert convert.pdf_options().attachment_mode == "base64"


class _FakeEvaluation:
    """Only the field `_degraded_summary` reads. The real one needs a scored corpus."""

    def __init__(self, degraded: tuple[convert.DegradedFact, ...]) -> None:
        self.degraded = degraded


def _fact(kind: str, reason: str | None, occurrences: int) -> convert.DegradedFact:
    return convert.DegradedFact(kind=kind, reason=reason, occurrences=occurrences)


def test_degraded_events_count_occurrences_rather_than_coalesced_events() -> None:
    """The parser coalesces repeats and sums their `count`; reading the event alone loses it.

    Twelve regions rejected in one article is a different fact from one region rejected, and
    under the old shape the two were identical.
    """
    evaluations = [_FakeEvaluation((_fact("table_rejected", "text_grid_splits_words", 12),))]

    summary = benchmark._degraded_summary(evaluations)

    assert summary["table_rejected"]["occurrences"] == 12
    assert summary["table_rejected"]["by_reason"]["text_grid_splits_words"]["occurrences"] == 12


def test_degraded_events_separate_a_pathological_article_from_a_corpus_wide_failure() -> None:
    """`articles` is why the corpus total cannot be misread.

    Twenty-nine rejections spread over nine articles is a detection gap; the same total from
    one article is one bad document, and the work those two imply is not the same.
    """
    concentrated = [_FakeEvaluation((_fact("table_rejected", "text_grid_splits_words", 29),))]
    spread = [_FakeEvaluation((_fact("table_rejected", "text_grid_splits_words", 1),)) for _ in range(29)]

    one = benchmark._degraded_summary(concentrated)["table_rejected"]
    many = benchmark._degraded_summary(spread)["table_rejected"]

    assert one["occurrences"] == many["occurrences"] == 29, "the totals are deliberately identical"
    assert one["articles"] == 1
    assert many["articles"] == 29, "which is the only thing that tells them apart"


def test_degraded_events_keep_the_reasons_apart() -> None:
    """Nine guards reject a table region, and some of those rejections are correct.

    Collapsing them into one number cannot distinguish the parser refusing to grid a page of
    prose -- which is the behaviour we want -- from a real table lost.
    """
    evaluations = [
        _FakeEvaluation(
            (
                _fact("table_rejected", "text_grid_splits_words", 6),
                _fact("table_rejected", "mostly_empty", 6),
            )
        ),
        _FakeEvaluation((_fact("table_rejected", "degenerate_grid", 1),)),
    ]

    entry = benchmark._degraded_summary(evaluations)["table_rejected"]

    assert entry["occurrences"] == 13
    assert entry["articles"] == 2
    assert list(entry["by_reason"]) == [
        "mostly_empty",
        "text_grid_splits_words",
        "degenerate_grid",
    ], "ordered by occurrences, so the dominant cause leads"
    assert entry["by_reason"]["degenerate_grid"] == {"occurrences": 1, "articles": 1}


def test_an_event_with_no_reason_still_totals() -> None:
    """Not every degraded event carries a detail; those must not vanish from the total."""
    summary = benchmark._degraded_summary([_FakeEvaluation((_fact("ocr_failed", None, 3),))])

    assert summary["ocr_failed"] == {"occurrences": 3, "articles": 1}


# ---------------------------------------------------------------------------
# The published payload must be checkable from its own fields
# ---------------------------------------------------------------------------


def test_attainable_recall_is_reproducible_from_the_published_counts() -> None:
    """The share's numerator ships beside it, per kind and overall.

    ``attainable_recall`` is ``recovered_attainable / attainable``, and those are
    different blocks from ``recovered``: a block can be recovered from the output
    while the PDF's own text layer does not reproduce it, so it counts in
    ``recovered`` and in neither side of the share. While the numerator was not
    published, dividing the two counts that *were* gave a plausible wrong answer
    -- 92/110 reads as 83.6% where the artifact says 82.7% -- and nothing in the
    payload could settle which was right. A published figure nobody can check
    against the artifact is the failure this lane exists to prevent.
    """
    # One block per case: recovered and attainable, attainable but not recovered,
    # recovered though the layer never had it (the block the two counts disagree on).
    layer = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    missing_from_layer = "one two three four five six seven eight nine ten"
    blocks = [
        ("text_block", layer),
        ("text_block", "lambda mu nu xi omicron pi rho sigma tau upsilon"),
        ("text_block", missing_from_layer),
    ]
    emitted = f"{layer} {missing_from_layer}"
    pdf_text = f"{layer} lambda mu nu xi omicron pi rho sigma tau upsilon"

    report = article.measure_recall([("PMC1.1", blocks, emitted, pdf_text)])

    assert report.recovered == 2, "both the layer block and the layer-less block were emitted"
    assert report.attainable == 2, "the layer reproduces two of the three blocks"
    assert report.recovered_attainable == 1, "only one block is on both sides of the share"
    assert report.attainable_recall == pytest.approx(report.recovered_attainable / report.attainable)
    assert report.attainable_recall != pytest.approx(report.recovered / report.attainable)
