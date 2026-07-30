"""Self-tests for the Markdown roundtrip benchmark oracles.

These guard the *judge*, not all2md. An oracle that cannot fail is worthless, so
each oracle is exercised on both a faithful case (must pass) and a deliberately
broken one (must fail). The broken cases are constructed by controlling the
roundtrip function directly (monkeypatching ``_roundtrip_once``) rather than by
relying on a current all2md bug, so the tests stay valid as all2md is fixed.

The HTML semantic normalizer is additionally checked to (a) ignore incidental
whitespace and (b) still distinguish the exact loss shape - a collapsed
paragraph - that motivated this benchmark (#85).

The last section guards the *CI gate* built on those oracles: that it goes red on
a real failure, on an expected failure that has started passing, and on an
expected-failure entry that nothing evaluates any more.
"""

from __future__ import annotations

import pytest

from benchmarks.roundtrip import corpus, oracles, run
from benchmarks.roundtrip.oracles import (
    CheckResult,
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


def test_admonition_detection() -> None:
    assert corpus._looks_like_admonition("!!! note\n    body\n")
    assert corpus._looks_like_admonition('??? warning "T"\n    body\n')
    assert corpus._looks_like_admonition("???+ tip\n    body\n")
    assert not corpus._looks_like_admonition("plain text with !!! bang in the middle")
    # An admonition marker shown inside a fenced code block is an example.
    assert not corpus._looks_like_admonition("```\n!!! note\n    body\n```")


def test_synthetic_corpus_loads() -> None:
    cases = corpus.load_synthetic_corpus()
    assert cases, "synthetic corpus should not be empty"
    names = {c.name for c in cases}
    assert "kitchen-sink" in names
    # The raw-html document must be flagged so the HTML oracle skips it.
    raw = next(c for c in cases if c.name == "raw-html")
    assert raw.has_raw_html
    # The admonitions document must be flagged so the HTML oracle skips it.
    adm = next(c for c in cases if c.name == "admonitions")
    assert adm.has_admonitions


def test_evaluate_case_skips_html_oracle_for_raw_html() -> None:
    case = corpus.Case(name="x", markdown="<div>raw</div>\n", has_raw_html=True)
    results = {r.oracle: r for r in evaluate_case(case)}
    assert results["html_equivalence"].skipped
    assert "idempotency" in results


def test_evaluate_case_skips_html_oracle_for_admonitions() -> None:
    case = corpus.Case(name="x", markdown="!!! note\n    body\n", has_admonitions=True)
    results = {r.oracle: r for r in evaluate_case(case)}
    assert results["html_equivalence"].skipped
    # Idempotency still runs and should pass for a well-formed admonition.
    assert results["idempotency"].passed


# --- the CI gate itself can go red --------------------------------------------
#
# The gate is only worth having if it fails when it should, so its three red
# paths are pinned here rather than demonstrated once by hand: a genuine oracle
# failure, an expected failure that started passing (XPASS), and an
# expected-failure entry nothing evaluates any more (stale).


def _result(oracle: str, *, passed: bool, skipped: bool = False) -> CheckResult:
    return CheckResult(oracle, passed=passed, skipped=skipped, detail="synthetic")


def test_status_distinguishes_expected_from_unexpected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(run.EXPECTED_FAILURES, ("doc", "idempotency"), "accepted for test")

    # Same failing result is XFAIL when allowlisted, FAIL when not.
    assert run._status("doc", _result("idempotency", passed=False)) == "XFAIL"
    assert run._status("other", _result("idempotency", passed=False)) == "FAIL"
    # Same passing result is XPASS when allowlisted, pass when not.
    assert run._status("doc", _result("idempotency", passed=True)) == "XPASS"
    assert run._status("other", _result("idempotency", passed=True)) == "pass"
    # A policy skip outranks the allowlist - it was never judged either way.
    assert run._status("doc", _result("idempotency", passed=True, skipped=True)) == "SKIP"


def test_gate_is_green_on_expected_failures_only() -> None:
    counts = {"passed": 37, "failed": 0, "xfailed": 1, "xpassed": 0, "skipped": 2}
    assert run.gate_failed(counts, []) is False


@pytest.mark.parametrize(
    ("counts_delta", "stale", "why"),
    [
        ({"failed": 1}, [], "a genuine oracle failure"),
        ({"xpassed": 1}, [], "an expected failure that started passing"),
        ({}, [("gone", "idempotency")], "a stale expected-failure entry"),
    ],
)
def test_gate_goes_red(counts_delta: dict[str, int], stale: list[tuple[str, str]], why: str) -> None:
    counts = {"passed": 37, "failed": 0, "xfailed": 1, "xpassed": 0, "skipped": 2, **counts_delta}
    assert run.gate_failed(counts, stale) is True, f"gate should fail on {why}"


def test_stale_detection_flags_unevaluated_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    case = corpus.Case(name="present", markdown="hi\n")
    rows = [(case, [_result("idempotency", passed=False)])]

    # An entry for a document that no longer exists is stale...
    monkeypatch.setitem(run.EXPECTED_FAILURES, ("renamed-away", "idempotency"), "x")
    assert ("renamed-away", "idempotency") in run._stale_expected_failures(rows)
    # ...while the entry that did get evaluated is not.
    monkeypatch.setitem(run.EXPECTED_FAILURES, ("present", "idempotency"), "x")
    assert ("present", "idempotency") not in run._stale_expected_failures(rows)


def test_stale_detection_flags_entry_hidden_by_a_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    # The subtle rot case: the oracle now policy-skips the case, so the allowlist
    # entry can never fail again and silently guards nothing.
    case = corpus.Case(name="doc", markdown="<div>raw</div>\n", has_raw_html=True)
    rows = [(case, [_result("html_equivalence", passed=True, skipped=True)])]
    monkeypatch.setitem(run.EXPECTED_FAILURES, ("doc", "html_equivalence"), "x")
    assert ("doc", "html_equivalence") in run._stale_expected_failures(rows)


def test_every_expected_failure_records_a_reason() -> None:
    # The allowlist is a decision log; an entry without a justification is how it
    # decays into "this has always been broken".
    for key, reason in run.EXPECTED_FAILURES.items():
        assert reason.strip(), f"{key} has no recorded reason"


def test_summary_counts_match_the_reported_statuses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(run.EXPECTED_FAILURES, ("doc", "idempotency"), "accepted for test")
    rows = [
        (corpus.Case(name="doc", markdown="a\n"), [_result("idempotency", passed=False)]),
        (corpus.Case(name="ok", markdown="b\n"), [_result("idempotency", passed=True)]),
        (corpus.Case(name="bad", markdown="c\n"), [_result("idempotency", passed=False)]),
    ]
    assert run._summary(rows) == {"passed": 1, "failed": 1, "xfailed": 1, "xpassed": 0, "skipped": 0}
