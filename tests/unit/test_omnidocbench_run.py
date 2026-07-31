"""Behavioral tests for the OmniDocBench end-to-end command."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from benchmarks.omnidocbench import run

pytestmark = pytest.mark.unit


def _args(tmp_path: Path, *extra: str):
    return run._build_parser().parse_args(
        [
            "--cache-dir",
            str(tmp_path / "cache"),
            *extra,
        ]
    )


def _stub_scored_run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    dirty: bool,
    failure: bool,
) -> dict[str, object]:
    snapshot = SimpleNamespace(
        revision="pinned",
        pages=(SimpleNamespace(page_id="page-a"),),
        expected_pages=1,
        complete=True,
    )
    observed: dict[str, object] = {"events": [], "writes": []}

    def fake_identity() -> tuple[str, bool]:
        observed["events"].append("identity")
        return "a" * 40, dirty

    def fake_load(*_args, **_kwargs):
        observed["events"].append("load")
        return snapshot

    def fake_evaluate(*_args, **_kwargs):
        observed["events"].append("evaluate")
        error_type = "RuntimeError" if failure else None
        return [SimpleNamespace(error_type=error_type)]

    def fake_normalize(**kwargs):
        observed["normalize_kwargs"] = kwargs
        failures = {"page-a": "RuntimeError: broken PDF"} if failure else {}
        return {"provenance": {}, "conversion_failures": failures}

    def fake_write(payload, path):
        observed["writes"].append((payload, path))
        return path

    monkeypatch.setattr(run, "_git_identity", fake_identity)
    monkeypatch.setattr(run, "load_corpus", fake_load)
    monkeypatch.setattr(run, "_parser_runtime", lambda _languages: {"pymupdf": "1.28.4"})
    monkeypatch.setattr(run, "load_ground_truth", lambda _snapshot: {})
    monkeypatch.setattr(run, "evaluate_corpus", fake_evaluate)
    monkeypatch.setattr(run, "normalize_results", fake_normalize)
    monkeypatch.setattr(run, "write_result", fake_write)
    return observed


def test_limited_run_cannot_enter_the_full_corpus_gate(tmp_path: Path) -> None:
    """A convenient smoke subset must never be mistaken for the 981-page fidelity gate."""
    args = _args(tmp_path, "--limit", "5")

    with pytest.raises(ValueError, match="--limit requires --skip-gate"):
        run.run(args)


def test_limited_run_cannot_emit_a_baseline(tmp_path: Path) -> None:
    """A truncated denominator must not become the committed fidelity reference."""
    args = _args(
        tmp_path,
        "--limit",
        "5",
        "--skip-gate",
        "--write-baseline",
        str(tmp_path / "baseline.json"),
    )

    with pytest.raises(ValueError, match="complete 981-page corpus"):
        run.run(args)


def test_download_only_validates_corpus_without_parsing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Operators must be able to prefill the licensed cache without OCR work."""
    snapshot = SimpleNamespace(revision="pinned", pages=(object(), object()), expected_pages=981)
    calls: list[tuple[Path, int | None, int]] = []

    def fake_load(cache_dir: Path, *, limit: int | None, workers: int):
        calls.append((cache_dir, limit, workers))
        return snapshot

    monkeypatch.setattr(run, "load_corpus", fake_load)
    args = _args(
        tmp_path,
        "--limit",
        "2",
        "--skip-gate",
        "--download-only",
        "--download-workers",
        "3",
    )

    assert run.run(args) == 0
    assert calls == [(tmp_path / "cache", 2, 3)]


def test_parser_runtime_records_every_pdf_and_ocr_implementation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dependency or OCR-model change must alter ratchet identity instead of silently changing scores."""
    versions = {
        "PyMuPDF": "1.28.4",
        "pymupdf-layout": "1.28.2",
        "pytesseract": "0.3.13",
        "Pillow": "11.3.0",
    }
    (tmp_path / "eng.traineddata").write_bytes(b"english-model")
    (tmp_path / "chi_sim.traineddata").write_bytes(b"chinese-model")

    def fake_subprocess(command, **_kwargs):
        if command[1] == "--list-langs":
            return SimpleNamespace(stdout=f'List of available languages in "{tmp_path}" (2):\n', stderr="")
        return SimpleNamespace(stdout="tesseract 5.3.0\n leptonica-1.82.0\n", stderr="")

    monkeypatch.setattr(run.metadata, "version", versions.__getitem__)
    monkeypatch.setattr(run.subprocess, "run", fake_subprocess)

    assert run._parser_runtime("eng+chi_sim") == {
        "pymupdf": "1.28.4",
        "pymupdf_layout": "1.28.2",
        "pytesseract": "0.3.13",
        "pillow": "11.3.0",
        "tesseract": "tesseract 5.3.0",
        "tessdata_chi_sim_sha256": hashlib.sha256(b"chinese-model").hexdigest(),
        "tessdata_eng_sha256": hashlib.sha256(b"english-model").hexdigest(),
    }


def test_missing_ocr_language_data_fails_instead_of_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing traineddata file must stop the run, never silently change OCR behavior."""
    monkeypatch.setattr(
        run.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout=f'List of available languages in "{tmp_path}" (0):\n', stderr=""
        ),
    )

    with pytest.raises(RuntimeError, match="cannot read pinned OCR language data"):
        run._language_digests("eng")


@pytest.mark.parametrize(
    ("status", "dirty"),
    [("", False), (" M benchmarks/omnidocbench/run.py\n", True), ("?? new-file.py\n", True)],
)
def test_git_identity_records_explicit_worktree_state(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    dirty: bool,
) -> None:
    """Committed, modified, and untracked source states must remain distinguishable."""
    outputs = iter(["b" * 40 + "\n", status])
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs):
        commands.append(command)
        return SimpleNamespace(stdout=next(outputs))

    monkeypatch.setattr(run.subprocess, "run", fake_run)

    assert run._git_identity() == ("b" * 40, dirty)
    assert commands == [
        ["git", "rev-parse", "HEAD"],
        ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
    ]


@pytest.mark.parametrize(
    ("extra", "expected_status"),
    [([], 1), (["--allow-conversion-failures"], 0)],
    ids=["fail-closed", "explicitly-allowed"],
)
def test_skip_gate_requires_explicit_conversion_failure_permission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra: list[str],
    expected_status: int,
) -> None:
    """Skipping the ratchet must not silently turn failed page conversions green."""
    _stub_scored_run(monkeypatch, dirty=False, failure=True)
    args = _args(tmp_path, "--skip-gate", *extra)

    assert run.run(args) == expected_status


def test_gate_still_authorizes_recorded_conversion_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The normal gate remains the authority for reviewed expected failures."""
    observed = _stub_scored_run(monkeypatch, dirty=False, failure=True)
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text("{}", encoding="utf-8")
    baseline = {"expected_conversion_failures": {"page-a": "RuntimeError: broken PDF"}}
    verdict = SimpleNamespace(failed=False)
    comparisons: list[tuple[object, object]] = []
    monkeypatch.setattr(run, "_read_json", lambda _path: baseline)
    monkeypatch.setattr(
        run,
        "compare",
        lambda actual, expected: comparisons.append((actual, expected)) or verdict,
    )
    monkeypatch.setattr(run, "format_verdict", lambda _verdict: "gate passed")

    assert run.run(_args(tmp_path, "--baseline", str(baseline_path))) == 0
    assert comparisons == [(observed["writes"][0][0], baseline)]


def test_dirty_worktree_cannot_emit_a_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Baseline evidence must never claim a commit that excludes evaluated source edits."""
    monkeypatch.setattr(run, "_git_identity", lambda: ("c" * 40, True))

    def fail_load(*_args, **_kwargs):
        raise AssertionError("dirty baseline must fail before corpus work")

    monkeypatch.setattr(run, "load_corpus", fail_load)
    args = _args(tmp_path, "--write-baseline", str(tmp_path / "candidate.json"))

    with pytest.raises(RuntimeError, match="dirty worktree"):
        run.run(args)


def test_result_records_source_identity_before_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every result must identify both the loaded commit and its dirty-worktree state."""
    observed = _stub_scored_run(monkeypatch, dirty=True, failure=False)

    assert run.run(_args(tmp_path, "--skip-gate")) == 0
    assert observed["events"].index("identity") < observed["events"].index("evaluate")
    assert observed["normalize_kwargs"]["all2md_commit"] == "a" * 40
    assert observed["normalize_kwargs"]["worktree_dirty"] is True


def test_absent_baseline_is_a_red_gate_verdict_not_an_environment_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before the first accepted baseline the gate must fail closed with ABSENT_BASELINE.

    The lane ships without ``baseline.json`` and bootstraps it from a dispatched CI run. A
    missing file previously surfaced as ``cannot read JSON from ...`` and exit 2, which
    reports a reviewable bootstrap state as a broken environment. This pins the honest
    contract: the ratchet still refuses to pass, but it does so as a fidelity verdict.
    """
    _stub_scored_run(monkeypatch, dirty=False, failure=False)
    missing = tmp_path / "no-such-baseline.json"

    verdict = run.compare({"schema_version": 2}, {})
    assert verdict.failed
    assert [finding.status for finding in verdict.findings] == ["ABSENT_BASELINE"]

    seen: list[object] = []
    monkeypatch.setattr(
        run,
        "compare",
        lambda _actual, expected: seen.append(expected) or SimpleNamespace(failed=True),
    )
    monkeypatch.setattr(run, "format_verdict", lambda _verdict: "red")

    assert run.run(_args(tmp_path, "--baseline", str(missing))) == 1
    assert seen == [{}]


def test_unlistable_tesseract_is_reported_as_an_environment_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Tesseract that cannot list its languages must not masquerade as a fidelity regression.

    ``_tessdata_dir`` shells out to ``tesseract --list-langs`` with ``check=True``. A
    ``CalledProcessError`` is a ``SubprocessError``, not an ``OSError``, so it escaped
    ``run.main``'s handler entirely and exited 1, the gate-FAIL code. Every sibling
    subprocess call site converts failure into this module's ``RuntimeError`` contract so
    ``main`` can report exit 2 instead.
    """

    def fake_run(command, **_kwargs):
        raise run.subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(run.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="cannot list the installed Tesseract languages"):
        run._tessdata_dir()
