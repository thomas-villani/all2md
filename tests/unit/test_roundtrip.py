#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for the round-trip fidelity scoring model (``all2md.roundtrip``)."""

import pytest

from all2md.ast.nodes import (
    CodeBlock,
    Document,
    Emphasis,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    MathBlock,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.roundtrip import (
    DIMENSION_WEIGHTS,
    TEXT_SIMILARITY_TOKEN_CAP,
    RoundTripReport,
    StructuralDelta,
    build_report,
    coalesce_deltas,
    net_block_deltas,
    score_roundtrip,
)

pytestmark = pytest.mark.unit


# --- Builders ----------------------------------------------------------------


def para(text):
    return Paragraph(content=[Text(content=text)])


def heading(level, text):
    return Heading(level=level, content=[Text(content=text)])


def tight_item(text):
    """A list item holding inline content directly, as tight Markdown lists do."""
    return ListItem(children=[para(text)])


def bullet_list(*texts):
    return List(ordered=False, items=[tight_item(t) for t in texts])


def table(rows):
    """Build a Table whose first row is the header."""
    header = TableRow(cells=[TableCell(content=[Text(content=c)]) for c in rows[0]], is_header=True)
    body = [TableRow(cells=[TableCell(content=[Text(content=c)]) for c in row]) for row in rows[1:]]
    return Table(rows=body, header=header)


def doc(*children):
    return Document(children=list(children))


def kinds(deltas):
    return {d.kind for d in deltas}


def by_kind(deltas, kind):
    return [d for d in deltas if d.kind == kind]


# --- Endpoints ---------------------------------------------------------------


class TestEndpoints:
    def test_identity_scores_perfect_with_no_deltas(self):
        source = doc(heading(1, "Title"), para("Hello world"), bullet_list("a", "b"))
        score, metrics, deltas = score_roundtrip(source, source)
        assert score == 100
        assert deltas == []
        assert metrics["structure"] == 100
        assert metrics["text"] == 100

    def test_empty_document_scores_vacuous_perfect(self):
        score, metrics, deltas = score_roundtrip(doc(), doc())
        assert (score, metrics, deltas) == (100, {}, [])

    def test_everything_lost_scores_zero(self):
        source = doc(heading(1, "Title"), para("Hello world"), table([["a", "b"], ["1", "2"]]))
        score, metrics, _ = score_roundtrip(source, doc())
        assert score == 0
        assert set(metrics.values()) == {0}

    def test_score_is_clamped_to_0_100(self):
        source = doc(para("one two three"))
        for candidate in (doc(), source, doc(para("one two three four five"))):
            score, _, _ = score_roundtrip(source, candidate)
            assert 0 <= score <= 100


# --- Normalization -----------------------------------------------------------


class TestNormalization:
    def test_loose_list_item_matches_tight_list_item(self):
        """A ListItem wrapping its text in a Paragraph is the same item.

        Markdown writes tight lists without the wrapping paragraph, HTML writes
        loose ones with it, and neither has lost anything.
        """
        tight = doc(List(ordered=False, items=[ListItem(children=[para("x")])]))
        loose = doc(List(ordered=False, items=[ListItem(children=[Paragraph(content=[para("x")])])]))
        score, _, deltas = score_roundtrip(tight, loose)
        assert score == 100
        assert deltas == []

    def test_nested_paragraph_chain_collapses(self):
        """Paragraph-inside-paragraph is always an artifact, never content."""
        flat = doc(para("hello world"))
        nested = doc(Paragraph(content=[Paragraph(content=[para("hello world")])]))
        score, _, deltas = score_roundtrip(flat, nested)
        assert score == 100
        assert deltas == []

    def test_table_rows_are_not_counted_as_blocks(self):
        """Table dimensions ride on the Table shape; rows/cells are not blocks."""
        source = doc(table([["a", "b"], ["1", "2"]]))
        score, metrics, _ = score_roundtrip(source, source)
        assert score == 100
        assert metrics["tables"] == 100

    def test_table_cell_text_survives_paragraph_wrapping(self):
        """A cell that wraps content in a paragraph has not lost its text."""
        plain = doc(table([["a"], ["1"]]))
        wrapped = Table(
            rows=[TableRow(cells=[TableCell(content=[para("1")])])],
            header=TableRow(cells=[TableCell(content=[para("a")])], is_header=True),
        )
        score, _, _ = score_roundtrip(plain, doc(wrapped))
        assert score == 100


# --- Structure / text independence -------------------------------------------


class TestStructureTextIndependence:
    def test_demoted_heading_costs_structure_but_not_text(self):
        """The regression this design exists to prevent.

        Aligning text through the structural match let one demoted heading shift
        every later pairing, so a document that lost no words scored near zero on
        text. Structure and text are now scored against independent alignments.
        """
        source = doc(heading(1, "Title"), para("alpha beta gamma"), heading(2, "Section"))
        demoted = doc(para("Title"), para("alpha beta gamma"), heading(1, "Section"))

        _, metrics, deltas = score_roundtrip(source, demoted)

        assert metrics["text"] == 100, "no word was lost, so text must be perfect"
        assert metrics["structure"] < 100
        assert deltas, "the demotion must still be reported"

    def test_single_block_reshape_reports_block_changed(self):
        source = doc(heading(1, "Title"))
        _, _, deltas = score_roundtrip(source, doc(para("Title")))
        changed = by_kind(deltas, "block_changed")
        assert changed and changed[0].detail == "heading(h1) -> paragraph"

    def test_reordered_text_is_reported_but_loses_no_words(self):
        source = doc(para("alpha beta"), para("gamma delta"))
        swapped = doc(para("gamma delta"), para("alpha beta"))
        _, metrics, deltas = score_roundtrip(source, swapped)
        assert metrics["structure"] == 100
        assert metrics["text"] < 100
        assert "text_reordered" in kinds(deltas)

    def test_added_text_is_reported_as_info(self):
        source = doc(para("alpha beta"))
        padded = doc(para("alpha beta gamma"))
        _, _, deltas = score_roundtrip(source, padded)
        added = by_kind(deltas, "text_added")
        assert added and added[0].severity == "info"

    def test_lost_words_are_counted(self):
        source = doc(para("alpha beta gamma delta"))
        trimmed = doc(para("alpha beta"))
        _, metrics, deltas = score_roundtrip(source, trimmed)
        assert metrics["text"] < 100
        lost = by_kind(deltas, "text_lost")
        assert lost and "2 of 4 words" in (lost[0].detail or "")

    def test_large_documents_fall_back_to_bag_similarity(self):
        """Above the token cap, order-sensitivity is traded for bounded runtime."""
        words = " ".join(f"w{i % 50}" for i in range(TEXT_SIMILARITY_TOKEN_CAP))
        source = doc(para(words))
        reversed_words = doc(para(" ".join(reversed(words.split()))))
        _, metrics, _ = score_roundtrip(source, reversed_words)
        # A bag comparison cannot see the reordering, so text reads as intact.
        assert metrics["text"] == 100


class TestBlockPayloadContent:
    """A leaf's string payload must be scored, not just its ``Text`` children.

    Code / math / raw-HTML / image-alt payloads live in a ``str`` attribute, not
    ``Text`` children. If the text dimension ignores them, a round trip that
    dropped or mangled a whole code block scores a false 100 -- the worst kind of
    blind spot for a fidelity tool.
    """

    def test_dropped_code_block_content_is_not_a_perfect_score(self):
        source = doc(CodeBlock(content="def f():\n    return secret_value", language="python"))
        emptied = doc(CodeBlock(content="", language="python"))
        score, metrics, _ = score_roundtrip(source, emptied)
        assert score < 100, "losing a code block's entire body must not score 100"
        assert metrics["text"] < 100

    def test_intact_code_block_still_scores_perfect(self):
        source = doc(CodeBlock(content="def f():\n    return 42", language="python"))
        score, _, _ = score_roundtrip(source, source)
        assert score == 100, "an unchanged code block must not be penalised"

    def test_mangled_math_body_loses_points(self):
        source = doc(MathBlock(content="E = mc^2"))
        mangled = doc(MathBlock(content="E = mc^3"))
        _, metrics, _ = score_roundtrip(source, mangled)
        assert metrics["text"] < 100

    def test_image_alt_text_is_scored(self):
        source = doc(Paragraph(content=[Image(url="a.png", alt_text="a red bicycle")]))
        stripped = doc(Paragraph(content=[Image(url="a.png", alt_text="")]))
        _, metrics, _ = score_roundtrip(source, stripped)
        assert metrics["text"] < 100


# --- Per-dimension deltas ----------------------------------------------------


class TestDeltas:
    def test_lost_block_is_reported(self):
        source = doc(para("a"), CodeBlock(content="x = 1", language="python"))
        _, _, deltas = score_roundtrip(source, doc(para("a")))
        lost = by_kind(deltas, "block_lost")
        assert lost and lost[0].detail == "code(python)"

    def test_added_block_is_info_not_warn(self):
        source = doc(para("a"))
        _, _, deltas = score_roundtrip(source, doc(para("a"), para("b")))
        added = by_kind(deltas, "block_added")
        assert added and added[0].severity == "info"

    def test_gaining_a_block_never_reports_losing_one(self):
        """Alignment reports a moved block as delete+insert; netting cancels them.

        Without netting, demoting a heading makes the paragraph count go *up* while
        the deltas claim a paragraph was lost.
        """
        source = doc(heading(1, "T"), para("body text"), heading(2, "S"))
        demoted = doc(para("T"), para("body text"), heading(1, "S"))
        _, _, deltas = score_roundtrip(source, demoted)

        assert "paragraph" not in {d.detail for d in by_kind(deltas, "block_lost")}
        assert by_kind(deltas, "block_lost"), "the lost h2 must still be reported"

    def test_netting_leaves_unmatched_losses_intact(self):
        merged = net_block_deltas(
            coalesce_deltas(
                [
                    StructuralDelta("block_lost", "paragraph", count=3),
                    StructuralDelta("block_added", "paragraph", count=1),
                    StructuralDelta("block_lost", "table(2x2)", count=1),
                ]
            )
        )
        assert {(d.kind, d.detail, d.count) for d in merged} == {
            ("block_lost", "paragraph", 2),
            ("block_lost", "table(2x2)", 1),
        }

    def test_flattened_nested_list_is_a_structural_change(self):
        nested = doc(
            List(
                ordered=False,
                items=[ListItem(children=[para("outer"), bullet_list("inner")])],
            )
        )
        flat = doc(bullet_list("outer", "inner"))
        _, metrics, deltas = score_roundtrip(nested, flat)
        assert metrics["structure"] < 100
        assert kinds(deltas) & {"block_lost", "block_changed"}

    def test_dropped_table_is_an_error(self):
        source = doc(table([["a", "b"], ["1", "2"]]))
        _, metrics, deltas = score_roundtrip(source, doc(para("a b 1 2")))
        assert metrics["tables"] == 0
        lost = by_kind(deltas, "table_lost")
        assert lost and lost[0].severity == "error"

    def test_resized_table_reports_old_and_new_shape(self):
        source = doc(table([["a", "b"], ["1", "2"]]))
        narrowed = doc(table([["a"], ["1"]]))
        _, metrics, deltas = score_roundtrip(source, narrowed)
        assert metrics["tables"] < 100
        changed = by_kind(deltas, "table_changed")
        assert changed and "2x2 -> 2x1" in (changed[0].detail or "")

    def test_lost_inline_formatting_is_reported(self):
        source = doc(Paragraph(content=[Strong(content=[Text(content="bold")])]))
        _, metrics, deltas = score_roundtrip(source, doc(para("bold")))
        assert metrics["inline"] == 0
        lost = by_kind(deltas, "inline_lost")
        assert lost and lost[0].detail == "strong"

    def test_inline_counts_are_a_multiset(self):
        source = doc(Paragraph(content=[Strong(content=[Text(content="a")]), Strong(content=[Text(content="b")])]))
        kept_one = doc(Paragraph(content=[Strong(content=[Text(content="a")]), Text(content="b")]))
        _, _, deltas = score_roundtrip(source, kept_one)
        lost = by_kind(deltas, "inline_lost")
        assert lost and lost[0].count == 1

    def test_lost_reference_names_the_url(self):
        source = doc(Paragraph(content=[Link(url="https://example.com", content=[Text(content="x")])]))
        _, metrics, deltas = score_roundtrip(source, doc(para("x")))
        assert metrics["references"] == 0
        lost = by_kind(deltas, "reference_lost")
        assert lost and lost[0].detail == "https://example.com"

    def test_image_targets_count_as_references(self):
        source = doc(Paragraph(content=[Image(url="pic.png", alt_text="p")]))
        _, metrics, _ = score_roundtrip(source, doc(para("")))
        assert metrics["references"] == 0

    def test_deltas_are_ranked_most_severe_first(self):
        source = doc(table([["a"], ["1"]]), para("x"), Paragraph(content=[Emphasis(content=[Text(content="y")])]))
        _, _, deltas = score_roundtrip(source, doc(para("x")))
        severities = [d.severity for d in deltas]
        assert severities == sorted(severities, key=["error", "warn", "info"].index)


# --- Weighting ---------------------------------------------------------------


class TestWeighting:
    def test_absent_dimensions_are_omitted_not_scored(self):
        """A document with no tables is neither rewarded nor punished for them."""
        source = doc(para("plain text"))
        _, metrics, _ = score_roundtrip(source, source)
        assert "tables" not in metrics
        assert "references" not in metrics
        assert "inline" not in metrics
        assert set(metrics) == {"structure", "text"}

    def test_weights_are_renormalized_over_present_dimensions(self):
        """With only structure and text present, their weights must still sum to 1.

        Structure is perfect and text is destroyed, so the score is exactly the
        renormalized text weight away from 100.
        """
        source = doc(para("alpha beta gamma delta"))
        gutted = doc(para(""))
        score, metrics, _ = score_roundtrip(source, gutted)

        assert metrics["structure"] == 100 and metrics["text"] == 0
        total = DIMENSION_WEIGHTS["structure"] + DIMENSION_WEIGHTS["text"]
        expected = round(100 * DIMENSION_WEIGHTS["structure"] / total)
        assert score == expected

    def test_structure_carries_the_most_weight(self):
        assert DIMENSION_WEIGHTS["structure"] == max(DIMENSION_WEIGHTS.values())
        assert sum(DIMENSION_WEIGHTS.values()) == pytest.approx(1.0)


# --- Report plumbing ---------------------------------------------------------


class TestReport:
    def test_build_report_labels_the_pipeline_and_bands_the_score(self):
        source = doc(heading(1, "T"), para("a b c"))
        report = build_report(source, source, source_format="docx", via="markdown")
        assert (report.score, report.band) == (100, "high")
        assert (report.source_format, report.via) == ("docx", "markdown")

    def test_low_score_bands_low(self):
        source = doc(heading(1, "T"), para("alpha beta gamma"))
        report = build_report(source, doc(), source_format="docx", via="latex")
        assert report.score == 0
        assert report.band == "low"

    def test_report_survives_a_json_round_trip(self):
        source = doc(heading(1, "T"), para("a b"), table([["x"], ["1"]]))
        report = build_report(source, doc(para("a b")), source_format="docx", via="rst")
        assert RoundTripReport.from_dict(report.to_dict()) == report

    def test_delta_omits_detail_when_unset(self):
        assert "detail" not in StructuralDelta(kind="text_reordered").to_dict()

    def test_coalesce_sums_counts_and_keeps_first_seen_order(self):
        merged = coalesce_deltas(
            [
                StructuralDelta("block_lost", "paragraph"),
                StructuralDelta("inline_lost", "strong", count=2),
                StructuralDelta("block_lost", "paragraph", count=3),
            ]
        )
        assert [(d.kind, d.count) for d in merged] == [("block_lost", 4), ("inline_lost", 2)]

    def test_coalesce_keeps_distinct_severities_apart(self):
        merged = coalesce_deltas(
            [
                StructuralDelta("text_lost", "x", severity="warn"),
                StructuralDelta("text_lost", "x", severity="info"),
            ]
        )
        assert len(merged) == 2
