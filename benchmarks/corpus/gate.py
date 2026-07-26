"""Turn a corpus benchmark run into a pass/fail verdict.

**What this gates, and what it deliberately does not.**

The sharp, non-flaky signal in a corpus run is *which documents fail to convert*.
That is a set of names, and sets compare exactly - no tolerance, no runner
variance, no threshold to argue about. So that is what this module gates.

Throughput is the other thing a corpus run measures, and it is *not* gated here.
It needs a variance study on the runners it will actually run on before any
threshold is defensible; guessing buys a flaky gate, and a flaky gate gets
disabled, which leaves the appearance of coverage. See ``benchmarks/startup_spread.py``
for the instrument and what it cost to learn that lesson on a much quieter metric.

**Only reproducible sources are judged.** ``corpus.toml`` marks each source with
``reproducible``; ``arxiv`` and ``poi`` resolve against upstream state that moves
(a live "most recent" query, and a branch ref), so a cold run gets different
documents and a failure-set comparison against them would be pure churn. They
still run and still appear in the report - they are an exploratory signal, not a
ratchet. ``ungated`` in the verdict names exactly what was skipped, because a gate
that silently judges 100 of 160 documents reads as judging all 160.

**Red paths**, following the roundtrip gate's allowlist shape so the baseline
cannot rot in any direction:

- ``NEW_FAILURE`` - a document failed that the baseline does not accept. The
  regression this exists to catch.
- ``FIXED`` - an accepted failure now converts. Red on purpose: an unrecorded win
  means the allowlist is describing a bug that no longer exists, and every later
  reader trusts it anyway. Record it in the commit that earned it.
- ``STALE`` - the baseline accepts a document the corpus no longer contains, so
  the entry is guarding nothing.
- ``MISSING_DOCS`` - a gated source returned fewer documents than the baseline
  recorded. This one is not about failures at all: a download that half-succeeds
  produces few documents, therefore few failures, therefore a green gate. Without
  this check the most likely infrastructure problem in the whole pipeline reads
  as success.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_BASELINE = HERE / "corpus_baseline.json"

RED_STATUSES = frozenset({"NEW_FAILURE", "FIXED", "STALE", "MISSING_DOCS"})


@dataclass
class Finding:
    """One thing wrong with this run relative to the baseline."""

    status: str
    doc: str
    detail: str = ""


@dataclass
class Verdict:
    """The full comparison: what failed, what was skipped, and why."""

    findings: list[Finding] = field(default_factory=list)
    gated_sources: list[str] = field(default_factory=list)
    ungated_sources: list[str] = field(default_factory=list)
    gated_docs: int = 0
    ungated_docs: int = 0

    @property
    def failed(self) -> bool:
        return any(f.status in RED_STATUSES for f in self.findings)


def doc_key(row: dict) -> str:
    """Stable identity for a document across runs.

    ``source_id`` rather than ``filename``: the filename is derived and could be
    re-derived differently, while the source id is what the fetcher resolved
    upstream.
    """
    return f"{row.get('source', '?')}/{row.get('source_id') or row.get('filename', '?')}"


def reproducible_sources(manifest: dict) -> set[str]:
    """Source names whose sample is fixed across cold runs.

    Absent ``reproducible`` means *not* reproducible. Defaulting the other way
    would silently gate a new source whose pool nobody has checked, and the whole
    point of this flag is that the unsafe case is the one that looks fine.
    """
    return {name for name, cfg in manifest.get("sources", {}).items() if cfg.get("reproducible") is True}


def compare(results: dict, baseline: dict, manifest: dict) -> Verdict:
    """Judge a results payload against the committed baseline."""
    gated = reproducible_sources(manifest)
    rows = results.get("results", [])

    verdict = Verdict()
    seen_sources = {r.get("source", "?") for r in rows}
    verdict.gated_sources = sorted(seen_sources & gated)
    verdict.ungated_sources = sorted(seen_sources - gated)

    gated_rows = [r for r in rows if r.get("source") in gated]
    verdict.gated_docs = len(gated_rows)
    verdict.ungated_docs = len(rows) - len(gated_rows)

    accepted: dict[str, str] = baseline.get("expected_failures", {})
    expected_counts: dict[str, int] = baseline.get("doc_counts", {})

    # A truncated download yields few docs, therefore few failures, therefore a
    # green gate. Check counts before looking at failures at all.
    by_source: dict[str, int] = {}
    for r in gated_rows:
        by_source[r.get("source", "?")] = by_source.get(r.get("source", "?"), 0) + 1
    for source, expected_n in sorted(expected_counts.items()):
        actual_n = by_source.get(source, 0)
        if actual_n < expected_n:
            verdict.findings.append(
                Finding(
                    "MISSING_DOCS",
                    source,
                    f"benchmarked {actual_n} of {expected_n} documents; the download or cache is incomplete",
                )
            )

    failing = {doc_key(r): (r.get("error_type") or "Error", r.get("error") or "") for r in gated_rows if r.get("error")}
    present = {doc_key(r) for r in gated_rows}

    for doc, (error_type, message) in sorted(failing.items()):
        if doc not in accepted:
            verdict.findings.append(Finding("NEW_FAILURE", doc, f"{error_type}: {message}"))

    for doc, reason in sorted(accepted.items()):
        if doc not in present:
            verdict.findings.append(Finding("STALE", doc, f"accepted as failing ({reason}) but not in this run"))
        elif doc not in failing:
            verdict.findings.append(Finding("FIXED", doc, f"accepted as failing ({reason}) but now converts"))

    return verdict


def format_verdict(verdict: Verdict, baseline: dict) -> str:
    lines: list[str] = []
    lines.append(
        f"Gated: {verdict.gated_docs} document(s) from {', '.join(verdict.gated_sources) or '(none)'}",
    )
    if verdict.ungated_sources:
        # Never silent: a reader who does not know these were skipped will read
        # the verdict as covering the whole corpus.
        lines.append(
            f"Not gated: {verdict.ungated_docs} document(s) from "
            f"{', '.join(verdict.ungated_sources)} - sample is not reproducible across runs, "
            f"so these are reported only."
        )
    lines.append("")

    if not verdict.findings:
        lines.append("OK - no new failures, no unrecorded fixes, no stale entries.")
        return "\n".join(lines)

    lines.append("CORPUS GATE FAILED")
    for f in verdict.findings:
        lines.append(f"  {f.status}: {f.doc}")
        if f.detail:
            lines.append(f"      {f.detail}")

    if any(f.status == "FIXED" for f in verdict.findings):
        lines += [
            "",
            "  A FIXED entry is a win, not a problem - remove it from expected_failures",
            "  in the commit that earned it, so the list keeps describing real bugs.",
        ]
    prov = baseline.get("provenance", {})
    if prov:
        recorded = prov.get("recorded", "?")
        run = prov.get("workflow_run", "unknown run")
        lines += ["", f"  Baseline: recorded {recorded} from {run}"]
    return "\n".join(lines)


def emit_baseline(results: dict, manifest: dict, provenance: dict | None = None) -> dict:
    """Derive a baseline from a results payload.

    For bootstrapping and for re-recording after a deliberate change. Hand-writing
    ~100 accepted failures is not realistic, and a list assembled by hand is a list
    with typos in it that read as passing documents.

    Every accepted failure carries the error type, so a document that keeps failing
    for a *different* reason is visible in the diff when this is regenerated. The
    reasons say ``TODO`` on purpose: a machine can record that something failed, but
    only a person can say whether it is acceptable, and an entry nobody justified
    should look unjustified.
    """
    gated = reproducible_sources(manifest)
    rows = [r for r in results.get("results", []) if r.get("source") in gated]

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["source"]] = counts.get(r["source"], 0) + 1

    failures = {
        doc_key(r): f"{r.get('error_type') or 'Error'} - TODO: why is this acceptable?"
        for r in sorted(rows, key=doc_key)
        if r.get("error")
    }

    return {
        "_comment": [
            "Corpus fidelity baseline. Covers only the sources marked reproducible=true",
            "in corpus.toml - arxiv and poi resolve against upstream state that moves, so",
            "their documents differ run to run and cannot be compared against anything.",
            "",
            "expected_failures is an allowlist, not a record: an entry that starts passing",
            "is red, and so is an entry for a document no longer in the corpus. Replace",
            "each TODO with a real reason or fix the bug and delete the line.",
        ],
        "provenance": provenance or {"recorded": "TODO", "workflow_run": "TODO"},
        "doc_counts": dict(sorted(counts.items())),
        "expected_failures": failures,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="benchmarks.corpus.gate", description=__doc__)
    p.add_argument("results", type=Path, help="Results JSON written by benchmarks.corpus.run")
    p.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE, help="Committed baseline to judge against")
    p.add_argument("--manifest", type=Path, default=HERE / "corpus.toml", help="Path to corpus.toml")
    p.add_argument(
        "--emit-baseline",
        action="store_true",
        help="Print a baseline derived from RESULTS instead of gating. For bootstrapping and re-recording.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    results = json.loads(args.results.read_text(encoding="utf-8"))
    with args.manifest.open("rb") as f:
        manifest = tomllib.load(f)

    if args.emit_baseline:
        print(json.dumps(emit_baseline(results, manifest), indent=2))
        return 0

    if not args.baseline.exists():
        print(
            f"No baseline at {args.baseline}. Record one from a CI run " f"(--emit-baseline) before gating.",
            file=sys.stderr,
        )
        return 2

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))

    verdict = compare(results, baseline, manifest)
    print(format_verdict(verdict, baseline))

    if not verdict.gated_sources:
        # Zero gated documents cannot produce a failure, so "green" here would be
        # vacuous. Almost always means the download stage did not run.
        print("\nNo gated sources present in these results; refusing to report a pass.", file=sys.stderr)
        return 2

    return 1 if verdict.failed else 0


if __name__ == "__main__":
    sys.exit(main())
