"""Wiring tests that compose real benchmark evidence with the real fidelity ratchet.

Every other OmniDocBench suite exercises one module against hand-built fixtures. That
left one gap wide open: ``benchmark.normalize_results`` stamped ``schema_version`` 2
while ``gate`` still accepted only 1, so every real ``--write-baseline`` run and every
scheduled gate run failed identity validation even though all module suites were green.
These tests refuse to let the two halves drift apart again by feeding genuine
``normalize_results`` output straight into ``emit_baseline`` and ``compare``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.omnidocbench import benchmark, gate, run
from benchmarks.omnidocbench.corpus import CorpusPage, CorpusSnapshot
from benchmarks.omnidocbench.oracles import GroundTruthPage, PageProjection

pytestmark = pytest.mark.unit

PARSER_RUNTIME = {
    "pymupdf": "1.28.4",
    "tesseract": "tesseract 5.3.0",
    "tessdata_eng_sha256": "b" * 64,
}


def _snapshot(tmp_path: Path, page_ids: tuple[str, ...]) -> CorpusSnapshot:
    return CorpusSnapshot(
        revision="f5f559bddf50e36f7f9899d842d0006f13ce8afc",
        annotation_path=tmp_path / "OmniDocBench.json",
        pages=tuple(
            CorpusPage(
                page_id=page_id,
                image_path=f"images/{page_id}.jpg",
                pdf_path=tmp_path / f"{page_id}.pdf",
                sha256="a" * 64,
                size_bytes=100,
            )
            for page_id in page_ids
        ),
        expected_pages=len(page_ids),
        complete=True,
    )


def _real_result(tmp_path: Path, scores: tuple[float, ...]) -> dict[str, object]:
    """Build ratchet input the same way a full corpus run does."""
    page_ids = tuple(f"page-{index}" for index in range(len(scores)))
    return benchmark.normalize_results(
        snapshot=_snapshot(tmp_path, page_ids),
        ground_truth={
            page_id: GroundTruthPage(
                page_id=page_id,
                projection=PageProjection(("Body",), ("text_block",), (), ()),
                unscored_categories={},
                explicitly_ignored=0,
                stratum="testsource",
            )
            for page_id in page_ids
        },
        evaluations=[
            benchmark.PageEvaluation(
                page_id=page_id,
                scores={"text_content_similarity": score, "reading_order_similarity": score},
                predicted_tables=0,
                predicted_formulas=0,
                duration_seconds=0.1,
            )
            for page_id, score in zip(page_ids, scores, strict=True)
        ],
        all2md_commit="c" * 40,
        parser_runtime=PARSER_RUNTIME,
    )


def test_emitted_baseline_accepts_the_run_that_produced_it(tmp_path: Path) -> None:
    """A real run must be able to bootstrap its own baseline; a schema mismatch here kills the lane."""
    result = _real_result(tmp_path, (0.4, 0.8))

    candidate = gate.emit_baseline(result, default_tolerance=0.005)
    verdict = gate.compare(result, candidate)

    assert candidate["schema_version"] == benchmark.SCHEMA_VERSION
    assert not verdict.failed, gate.format_verdict(verdict)


def test_gate_supports_exactly_the_schema_the_benchmark_emits() -> None:
    """The producer and the validator share one artifact contract, not two."""
    assert gate._SUPPORTED_SCHEMA_VERSION == benchmark.SCHEMA_VERSION
    assert gate._SUPPORTED_ORACLE_SCHEMA_VERSION == benchmark.ORACLE_SCHEMA_VERSION


def test_real_regression_beyond_tolerance_is_red(tmp_path: Path) -> None:
    """A measured fidelity drop past tolerance must fail the composed pipeline."""
    baseline = gate.emit_baseline(_real_result(tmp_path, (0.4, 0.8)), default_tolerance=0.005)
    regressed = _real_result(tmp_path, (0.3, 0.8))

    verdict = gate.compare(regressed, baseline)

    assert verdict.failed
    assert any(finding.status == "REGRESSION" for finding in verdict.findings), gate.format_verdict(verdict)


def test_real_improvement_requires_baseline_review(tmp_path: Path) -> None:
    """An unrecorded gain must also be red so the baseline stays the reviewed source of truth."""
    baseline = gate.emit_baseline(_real_result(tmp_path, (0.4, 0.8)), default_tolerance=0.005)
    improved = _real_result(tmp_path, (0.6, 0.9))

    verdict = gate.compare(improved, baseline)

    assert verdict.failed
    assert any(finding.status == "UNRECORDED_IMPROVEMENT" for finding in verdict.findings), gate.format_verdict(verdict)


def test_both_entrypoints_report_a_missing_baseline_as_a_red_verdict(tmp_path: Path) -> None:
    """``gate`` and ``run`` must agree that the pre-bootstrap state is red, not broken.

    Exit 1 means a fidelity verdict and exit 2 means a broken environment; any wrapper that
    distinguishes them misclassifies the documented ABSENT_BASELINE state if the two
    entrypoints disagree. The CLI used to print the red verdict and then return 2.
    """
    results_path = tmp_path / "current.json"
    results_path.write_text(json.dumps(_real_result(tmp_path, (0.4, 0.8))), encoding="utf-8")

    assert gate.main([str(results_path), "--baseline", str(tmp_path / "absent.json")]) == 1


def test_the_production_entrypoint_rejects_a_duplicate_key_baseline(tmp_path: Path) -> None:
    """The strict loader must guard the path CI actually runs.

    ``gate._load_json`` rejects duplicate keys and non-finite literals precisely because a
    reviewed ratchet cannot trust either: a human reads the first duplicate in a diff, while
    permissive ``json.loads`` keeps the last. The workflow only ever invokes
    ``python -m benchmarks.omnidocbench``, so reading the baseline there with plain
    ``json.loads`` left that hardening dead exactly where the baseline is trusted.
    """
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text('{"schema_version": 2, "schema_version": 99}', encoding="utf-8")

    with pytest.raises(RuntimeError, match="duplicate JSON key"):
        run._read_json(baseline_path)
