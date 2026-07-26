#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Self-tests for the corpus benchmark's pass/fail logic.

Two classes of test here, and the second matters more.

The first is the obvious one: every red path actually goes red. The second is
that the gate cannot pass *vacuously* - a corpus benchmark has several ways to
produce "no failures" by producing no work, and every one of them would read as
success. A download that half-succeeds, a results file with only ungated sources,
a baseline whose accepted-failure list has quietly stopped matching the corpus:
all of these are green under a naive implementation, and all of them mean the
gate has stopped guarding.
"""

from __future__ import annotations

import pytest

from benchmarks.corpus import gate

pytestmark = pytest.mark.unit


MANIFEST = {
    "sources": {
        "govdocs1": {"reproducible": True},
        "enron": {"reproducible": True},
        "arxiv": {"reproducible": False},
        "poi": {},  # absent flag must mean "not reproducible"
    }
}

BASELINE = {
    "provenance": {"recorded": "2026-07-25", "workflow_run": "run/1"},
    "doc_counts": {"govdocs1": 2, "enron": 1},
    "expected_failures": {"govdocs1/broken.pdf": "PdfSyntaxError - truncated xref upstream"},
}


def _row(source: str, source_id: str, *, error: str | None = None, error_type: str | None = None) -> dict:
    return {
        "source": source,
        "format": "pdf",
        "source_id": source_id,
        "filename": source_id,
        "size_bytes": 1024,
        "duration_seconds": 0.5,
        "output_chars": None if error else 500,
        "error": error,
        "error_type": error_type,
    }


def _results(rows: list[dict]) -> dict:
    return {"run": {"timestamp": "2026-07-25T00:00:00Z"}, "results": rows}


def _healthy_rows() -> list[dict]:
    return [
        _row("govdocs1", "ok.pdf"),
        _row("govdocs1", "broken.pdf", error="truncated xref", error_type="PdfSyntaxError"),
        _row("enron", "mail1.eml"),
    ]


# --- the green path -------------------------------------------------------------


def test_a_run_matching_the_baseline_is_green() -> None:
    verdict = gate.compare(_results(_healthy_rows()), BASELINE, MANIFEST)
    assert verdict.findings == []
    assert not verdict.failed


def test_ungated_sources_run_but_are_not_judged() -> None:
    # An arxiv doc failing must not fail the build: the arxiv sample is different
    # documents every run, so its failures are not comparable to anything.
    rows = [*_healthy_rows(), _row("arxiv", "2401.00001", error="boom", error_type="ValueError")]
    verdict = gate.compare(_results(rows), BASELINE, MANIFEST)

    assert not verdict.failed
    assert verdict.ungated_sources == ["arxiv"]
    assert verdict.ungated_docs == 1


def test_a_source_with_no_reproducible_flag_is_not_gated() -> None:
    # Defaulting to gated would silently judge a newly added source whose pool
    # nobody has checked - and an unchecked pool is exactly the unsafe case.
    rows = [*_healthy_rows(), _row("poi", "weird.docx", error="boom", error_type="ValueError")]
    verdict = gate.compare(_results(rows), BASELINE, MANIFEST)
    assert not verdict.failed
    assert "poi" in verdict.ungated_sources


# --- every red path -------------------------------------------------------------


def test_a_new_failure_is_red() -> None:
    rows = _healthy_rows()
    rows[0] = _row("govdocs1", "ok.pdf", error="kaboom", error_type="ValueError")
    verdict = gate.compare(_results(rows), BASELINE, MANIFEST)

    assert verdict.failed
    assert [(f.status, f.doc) for f in verdict.findings] == [("NEW_FAILURE", "govdocs1/ok.pdf")]


def test_an_unrecorded_fix_is_red() -> None:
    # The XPASS case. An accepted failure that now converts means the list is
    # describing a bug that no longer exists, and readers keep trusting it.
    rows = _healthy_rows()
    rows[1] = _row("govdocs1", "broken.pdf")
    verdict = gate.compare(_results(rows), BASELINE, MANIFEST)

    assert verdict.failed
    assert [(f.status, f.doc) for f in verdict.findings] == [("FIXED", "govdocs1/broken.pdf")]


def test_a_stale_allowlist_entry_is_red() -> None:
    # Everything in this run converts, so the only thing wrong is that the
    # baseline still accepts a document the corpus no longer contains.
    rows = [_row("govdocs1", "ok.pdf"), _row("enron", "mail1.eml")]
    baseline = {
        **BASELINE,
        "expected_failures": {"govdocs1/gone.pdf": "was failing once"},
        "doc_counts": {"govdocs1": 1, "enron": 1},
    }
    verdict = gate.compare(_results(rows), baseline, MANIFEST)

    assert verdict.failed
    assert [(f.status, f.doc) for f in verdict.findings] == [("STALE", "govdocs1/gone.pdf")]


def test_every_red_status_actually_fails_the_gate() -> None:
    # Guards against a status being reported in the table but forgotten in the
    # exit decision - the gate would then print a problem and exit 0.
    for status in sorted(gate.RED_STATUSES):
        v = gate.Verdict(findings=[gate.Finding(status, "x")])
        assert v.failed, f"{status} must fail the build"
    assert not gate.Verdict(findings=[]).failed


# --- the vacuous-pass modes -----------------------------------------------------


def test_a_truncated_download_is_red_rather_than_green() -> None:
    # Half a corpus means half the chances to fail. Without the doc-count check
    # this is the single most likely infrastructure fault in the pipeline, and it
    # reads as a clean pass.
    rows = [_row("govdocs1", "ok.pdf"), _row("enron", "mail1.eml")]
    verdict = gate.compare(_results(rows), BASELINE, MANIFEST)

    statuses = {f.status for f in verdict.findings}
    assert "MISSING_DOCS" in statuses
    assert verdict.failed


def test_a_run_with_no_gated_documents_at_all_refuses_to_pass(tmp_path) -> None:
    # Zero gated docs cannot produce a failure, so a "pass" would be meaningless.
    # main() must exit non-zero rather than report success.
    import json

    results = tmp_path / "results.json"
    results.write_text(json.dumps(_results([_row("arxiv", "2401.00001")])), encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(BASELINE), encoding="utf-8")
    manifest = tmp_path / "corpus.toml"
    manifest.write_text(
        "[sources.arxiv]\nreproducible = false\n[sources.govdocs1]\nreproducible = true\n", encoding="utf-8"
    )

    rc = gate.main([str(results), "--baseline", str(baseline), "--manifest", str(manifest)])
    assert rc == 2


def test_a_missing_baseline_is_an_error_not_a_pass(tmp_path) -> None:
    import json

    results = tmp_path / "results.json"
    results.write_text(json.dumps(_results(_healthy_rows())), encoding="utf-8")
    rc = gate.main([str(results), "--baseline", str(tmp_path / "nope.json")])
    assert rc == 2


# --- reporting ------------------------------------------------------------------


def test_the_report_names_what_it_did_not_gate() -> None:
    rows = [*_healthy_rows(), _row("arxiv", "2401.00001")]
    verdict = gate.compare(_results(rows), BASELINE, MANIFEST)
    text = gate.format_verdict(verdict, BASELINE)

    assert "Not gated" in text
    assert "arxiv" in text.split("Not gated")[1]


# --- bootstrapping a baseline ---------------------------------------------------


def test_an_emitted_baseline_makes_its_own_run_green() -> None:
    # The bootstrap property. If the emitter and the comparer disagree about doc
    # keys, counts, or which sources count, the very first gated run goes red for
    # no reason and the obvious fix is to stop trusting the gate.
    rows = [*_healthy_rows(), _row("arxiv", "2401.00001", error="x", error_type="ValueError")]
    emitted = gate.emit_baseline(_results(rows), MANIFEST)

    verdict = gate.compare(_results(rows), emitted, MANIFEST)
    assert verdict.findings == []
    assert not verdict.failed


def test_an_emitted_baseline_ignores_ungated_failures() -> None:
    # An arxiv failure recorded as "expected" would go STALE the moment the arxiv
    # sample rotates, which is daily.
    rows = [*_healthy_rows(), _row("arxiv", "2401.00001", error="x", error_type="ValueError")]
    emitted = gate.emit_baseline(_results(rows), MANIFEST)

    assert not any(doc.startswith("arxiv/") for doc in emitted["expected_failures"])
    assert "arxiv" not in emitted["doc_counts"]


def test_an_emitted_baseline_records_the_error_type_and_demands_a_reason() -> None:
    # The error type makes "still failing, but differently" visible in a re-record
    # diff. The TODO makes an unjustified entry look unjustified.
    emitted = gate.emit_baseline(_results(_healthy_rows()), MANIFEST)
    reason = emitted["expected_failures"]["govdocs1/broken.pdf"]

    assert "PdfSyntaxError" in reason
    assert "TODO" in reason


def test_a_fixed_finding_explains_what_to_do() -> None:
    rows = _healthy_rows()
    rows[1] = _row("govdocs1", "broken.pdf")
    verdict = gate.compare(_results(rows), BASELINE, MANIFEST)
    text = gate.format_verdict(verdict, BASELINE)

    assert "expected_failures" in text, "a FIXED verdict must say how to record the win"
