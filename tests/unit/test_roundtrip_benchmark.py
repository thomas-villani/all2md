"""Self-tests for the Markdown roundtrip benchmark oracles.

These guard the *judge*, not all2md. An oracle that cannot fail is worthless, so
each oracle is exercised on both a faithful case (must pass) and a deliberately
broken one (must fail). The broken cases are constructed by controlling the
roundtrip function directly (monkeypatching ``_roundtrip_once``) rather than by
relying on a current all2md bug, so the tests stay valid as all2md is fixed.

The HTML semantic normalizer is additionally checked to (a) ignore incidental
whitespace and (b) still distinguish the exact loss shape - a collapsed
paragraph - that motivated this benchmark (#85).
"""

from __future__ import annotations

import pytest

from benchmarks.roundtrip import corpus, oracles
from benchmarks.roundtrip.oracles import (
    html_equivalence_check,
    idempotency_check,
)
from benchmarks.roundtrip.run import evaluate_case

pytestmark = pytest.mark.unit


# --- the semantic (HTML) normalizer can tell real loss from noise -------------


def _norm(md: str) -> str:
    return oracles._normalize_html(oracles._reference_html(md))


def test_normalizer_ignores_incidental_whitespace() -> None:
    # Collapsible whitespace inside a paragraph is not a semantic difference.
    assert _norm("a  b") == _norm("a b")
    assert _norm("a\nb") == _norm("a b")


def test_normalizer_detects_paragraph_collapse() -> None:
    # The #85 loss: two paragraphs merged into one must be visible to the judge.
    two_paragraphs = _norm("first\n\nsecond")
    one_paragraph = _norm("first second")
    assert two_paragraphs != one_paragraph


def test_normalizer_detects_changed_table_cell() -> None:
    good = _norm("| a | b |\n|---|---|\n| 1 | 2 |")
    bad = _norm("| a | b |\n|---|---|\n| 1 | 9 |")
    assert good != bad


# --- idempotency oracle -------------------------------------------------------


def test_idempotency_passes_on_stable_document() -> None:
    result = idempotency_check("# Title\n\n- alpha\n- bravo\n")
    assert result.passed
    assert not result.skipped


def test_idempotency_flags_non_fixed_point(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force once != twice: first render appends a marker, second does not.
    calls = {"n": 0}

    def fake_roundtrip(md: str, _opts: object) -> str:
        calls["n"] += 1
        return md if calls["n"] == 1 else md + "\nMUTATED\n"

    monkeypatch.setattr(oracles, "_roundtrip_once", fake_roundtrip)
    result = idempotency_check("anything")
    assert not result.passed
    assert result.diff  # a unified diff is attached for triage


def test_idempotency_reports_render_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(md: str, _opts: object) -> str:
        raise ValueError("kaboom")

    monkeypatch.setattr(oracles, "_roundtrip_once", boom)
    result = idempotency_check("anything")
    assert not result.passed
    assert "kaboom" in result.detail


# --- HTML-equivalence oracle --------------------------------------------------


def test_html_equivalence_passes_on_faithful_reformatting(monkeypatch: pytest.MonkeyPatch) -> None:
    # A roundtrip that only reformats (bullet marker, blank lines) but preserves
    # meaning must PASS - otherwise the oracle would flag benign normalization.
    def reformat(md: str, _opts: object) -> str:
        return "- a\n- b\n"

    monkeypatch.setattr(oracles, "_roundtrip_once", reformat)
    result = html_equivalence_check("* a\n* b\n")
    assert result.passed


def test_html_equivalence_flags_semantic_loss(monkeypatch: pytest.MonkeyPatch) -> None:
    # A roundtrip that drops a paragraph must FAIL.
    def drop_paragraph(md: str, _opts: object) -> str:
        return "first\n"

    monkeypatch.setattr(oracles, "_roundtrip_once", drop_paragraph)
    result = html_equivalence_check("first\n\nsecond\n")
    assert not result.passed
    assert result.diff


# --- corpus loading + policy skips --------------------------------------------


def test_raw_html_detection() -> None:
    assert corpus._looks_like_raw_html("a <div>block</div> b")
    assert corpus._looks_like_raw_html("text with <br> tag")
    assert not corpus._looks_like_raw_html("plain *emphasis* and `code`")
    # HTML shown *inside* a fenced code block is an example, not raw passthrough.
    assert not corpus._looks_like_raw_html("```html\n<div>example</div>\n```")


def test_synthetic_corpus_loads() -> None:
    cases = corpus.load_synthetic_corpus()
    assert cases, "synthetic corpus should not be empty"
    names = {c.name for c in cases}
    assert "kitchen-sink" in names
    # The raw-html document must be flagged so the HTML oracle skips it.
    raw = next(c for c in cases if c.name == "raw-html")
    assert raw.has_raw_html


def test_evaluate_case_skips_html_oracle_for_raw_html() -> None:
    case = corpus.Case(name="x", markdown="<div>raw</div>\n", has_raw_html=True)
    results = {r.oracle: r for r in evaluate_case(case)}
    assert results["html_equivalence"].skipped
    assert "idempotency" in results
