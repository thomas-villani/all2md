"""Unit tests for the conversion optimizer's objective and search.

The objective is the whole ballgame here: a search that hill-climbs the wrong
function finds the wrong settings faster. These tests pin the two ways the obvious
objective goes wrong -- rewarding kept boilerplate, and rewarding hallucinated
tables -- because both were real, both were measured, and both would silently come
back if someone "simplified" the scoring.
"""

import pytest

from all2md.ast.nodes import Document, Heading, Paragraph, Table, TableCell, TableRow, Text
from all2md.optimize import (
    DIMENSION_WEIGHTS,
    Candidate,
    DocumentMetrics,
    extract_metrics,
    score_candidates,
    search,
    tunable_knobs,
)


def _para(text: str) -> Paragraph:
    return Paragraph(content=[Text(content=text)])


def _table(rows: list[list[str]]) -> Table:
    return Table(
        rows=[TableRow(cells=[TableCell(content=[Text(content=c)]) for c in row]) for row in rows],
    )


def _doc(*children) -> Document:
    return Document(children=list(children))


@pytest.mark.unit
class TestExtractMetrics:
    """Reading structural yield off the AST."""

    def test_counts_words_headings_and_tables(self):
        doc = _doc(Heading(level=1, content=[Text(content="Title")]), _para("one two three"), _table([["a", "b"]]))

        metrics = extract_metrics(doc)

        assert metrics.headings == 1
        assert metrics.tables == 1
        assert metrics.table_cells == 2
        assert "one two three".split() == ["one", "two", "three"]
        assert metrics.words >= 3

    def test_text_is_found_through_inline_wrappers(self):
        """Text lives in Text.content; every other node uses content as a container.

        Reading ``.content`` directly instead of walking children yields zero words,
        which silently flattens the whole text dimension to a constant.
        """
        doc = _doc(_para("alpha beta gamma"))

        assert extract_metrics(doc).words == 3

    def test_table_cells_are_not_double_counted(self):
        """get_node_children already descends into rows and cells."""
        doc = _doc(_table([["a", "b"], ["c", "d"]]))

        assert extract_metrics(doc).table_cells == 4

    def test_a_sparse_ragged_table_scores_poorly(self):
        """A hallucinated table is mostly empty and has inconsistent column counts."""
        good = extract_metrics(_doc(_table([["a", "b"], ["c", "d"]])))
        junk = extract_metrics(_doc(_table([["x", "", ""], ["", ""], [""]])))

        assert good.table_quality == pytest.approx(1.0)
        assert junk.table_quality < 0.2

    def test_no_tables_means_zero_table_quality(self):
        assert extract_metrics(_doc(_para("no tables here"))).table_quality == 0.0


@pytest.mark.unit
class TestBoilerplateDetection:
    """Repeated furniture must not read as recovered body text."""

    def test_a_repeated_block_is_boilerplate(self):
        doc = _doc(_para("ACME CONFIDENTIAL"), _para("real body text here"), _para("ACME CONFIDENTIAL"))

        metrics = extract_metrics(doc)

        assert metrics.duplicate_blocks == 2
        assert metrics.boilerplate_words == 4  # both copies, not just the second
        assert metrics.unique_words == 4  # "real body text here"

    def test_page_numbers_do_not_defeat_the_match(self):
        """A footer reading 'Page 1 of 9' and 'Page 2 of 9' is one footer: digits are masked."""
        doc = _doc(_para("Page 1 of 9 confidential draft"), _para("body"), _para("Page 2 of 9 confidential draft"))

        assert extract_metrics(doc).boilerplate_words == 12

    def test_furniture_glued_into_a_body_block_is_still_caught(self):
        """The regression that made the objective anti-correlated with the truth.

        The PDF parser routinely glues a running footer onto the front of the next
        body block. That block is unique -- it contains body text -- so no block-level
        comparison can ever flag it, and its footer words get counted as recovered
        content. Only a repeated *word sequence* spanning blocks finds it.
        """
        doc = _doc(
            _para("Page 1 of 2 ACME CONFIDENTIAL alpha revenue climbed sharply this spring"),
            _para("Page 2 of 2 ACME CONFIDENTIAL beta margins held despite volatile costs"),
        )

        metrics = extract_metrics(doc)

        assert metrics.duplicate_blocks == 0  # neither block repeats as a whole
        assert metrics.boilerplate_words > 0  # ...but the footer sequence does

    def test_a_block_repeating_itself_internally_is_not_furniture(self):
        """Furniture repeats across blocks. One block echoing a phrase is just prose."""
        doc = _doc(_para("the same five words here the same five words here"))

        assert extract_metrics(doc).boilerplate_words == 0


@pytest.mark.unit
class TestScoreCandidates:
    """Pool-relative fitness."""

    def test_keeping_boilerplate_does_not_beat_trimming_it(self):
        """The load-bearing property.

        Naive "more text is better" makes the untrimmed conversion win, because the
        boilerplate is extra words. Measured against ground truth that objective was
        anti-correlated (r = -0.88) -- it picked the worst candidate. Excluding
        furniture makes the two tie on text, so cleanliness decides for the trimmed one.
        """
        untrimmed = Candidate(
            options={"trim": False},
            metrics=extract_metrics(
                _doc(
                    _para("ACME CONFIDENTIAL header"),
                    _para("alpha revenue climbed sharply after the spring reorganisation"),
                    _para("ACME CONFIDENTIAL header"),
                    _para("beta margins held despite unusually volatile freight costs"),
                )
            ),
        )
        trimmed = Candidate(
            options={"trim": True},
            metrics=extract_metrics(
                _doc(
                    _para("alpha revenue climbed sharply after the spring reorganisation"),
                    _para("beta margins held despite unusually volatile freight costs"),
                )
            ),
        )

        score_candidates([untrimmed, trimmed])

        assert trimmed.fitness > untrimmed.fitness

    def test_a_hallucinated_table_does_not_beat_finding_none(self):
        """More tables is not better; well-formed tables are better."""
        junk = Candidate(
            options={"mode": "aggressive"},
            metrics=extract_metrics(_doc(_para("body text"), _table([["x", "", ""], ["", ""], [""]]))),
        )
        clean = Candidate(
            options={"mode": "strict"},
            metrics=extract_metrics(_doc(_para("body text"), _table([["a", "b"], ["c", "d"]]))),
        )

        score_candidates([junk, clean])

        assert clean.fitness > junk.fitness

    def test_dimensions_the_pool_never_exercises_are_dropped(self):
        """A document with no tables must not be dragged down by the tables it lacks."""
        only = Candidate(metrics=extract_metrics(_doc(_para("just some prose here"))))

        score_candidates([only])

        assert "tables" not in only.dimensions
        assert only.fitness == pytest.approx(100.0)

    def test_breakage_is_subtracted(self):
        clean = Candidate(metrics=DocumentMetrics(blocks=1, words=10, unique_words=10))
        broken = Candidate(metrics=DocumentMetrics(blocks=1, words=10, unique_words=10, breakage=30.0))

        score_candidates([clean, broken])

        assert clean.fitness - broken.fitness == pytest.approx(30.0)

    def test_empty_pool_does_not_raise(self):
        score_candidates([])  # must not raise

    def test_weights_cover_every_dimension_once(self):
        assert set(DIMENSION_WEIGHTS) == {"text", "tables", "structure", "cleanliness"}
        assert sum(DIMENSION_WEIGHTS.values()) == pytest.approx(1.0)


@pytest.mark.unit
class TestSearch:
    """The search loop, driven by a synthetic objective so no parsing is involved."""

    def test_finds_the_option_the_objective_rewards(self):
        knobs = {"alpha": [True, False], "beta": ["x", "y", "z"]}

        def evaluate(options):
            # Only alpha=True and beta="z" pay, and they pay independently.
            words = 10 + (5 if options.get("alpha") else 0) + (5 if options.get("beta") == "z" else 0)
            return DocumentMetrics(blocks=1, words=words, unique_words=words)

        report = search(knobs, evaluate)

        assert report.best_options == {"alpha": True, "beta": "z"}
        assert report.improved

    def test_reports_no_improvement_when_defaults_already_win(self):
        knobs = {"alpha": [True, False]}

        def evaluate(options):
            return DocumentMetrics(blocks=1, words=10, unique_words=10)

        report = search(knobs, evaluate)

        assert not report.improved
        assert report.gain == pytest.approx(0.0)

    def test_each_option_set_is_evaluated_only_once(self):
        calls: list[dict] = []

        def evaluate(options):
            calls.append(dict(options))
            return DocumentMetrics(blocks=1, words=10, unique_words=10)

        search({"alpha": [True, False], "beta": [1, 2]}, evaluate, rounds=3)

        signatures = [tuple(sorted(c.items())) for c in calls]
        assert len(signatures) == len(set(signatures))

    def test_search_is_far_cheaper_than_a_full_grid(self):
        """Coordinate descent costs sum(len(values)), not prod(len(values))."""
        knobs = {f"k{i}": [0, 1, 2] for i in range(6)}  # a full grid would be 3**6 = 729
        calls = 0

        def evaluate(options):
            nonlocal calls
            calls += 1
            return DocumentMetrics(blocks=1, words=10, unique_words=10)

        search(knobs, evaluate)

        assert calls < 30

    def test_presets_are_scored_and_attributed(self):
        knobs = {"alpha": [True, False]}

        def evaluate(options):
            words = 20 if options.get("alpha") else 10
            return DocumentMetrics(blocks=1, words=words, unique_words=words)

        report = search(knobs, evaluate, presets={"quality": {"alpha": True}})

        origins = {c.origin for c in report.candidates}
        assert "preset:quality" in origins

    def test_a_preset_touching_no_searched_knob_is_skipped(self):
        """It would just be the defaults under another name."""
        knobs = {"alpha": [True, False]}

        def evaluate(options):
            return DocumentMetrics(blocks=1, words=10, unique_words=10)

        report = search(knobs, evaluate, presets={"irrelevant": {"something_else": 1}})

        assert not any(c.origin.startswith("preset:") for c in report.candidates)


@pytest.mark.unit
def test_tunable_knobs_is_empty_for_an_untuned_format():
    assert tunable_knobs("pdf")
    assert tunable_knobs("nonexistent-format") == {}
