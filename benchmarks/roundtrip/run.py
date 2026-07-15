"""CLI for the Markdown roundtrip fidelity benchmark.

Runs both oracles (idempotency + HTML-equivalence) over the synthetic corpus and
prints a per-document table. This is a diagnostic / triage tool - it surfaces
which constructs currently fail to roundtrip, which is the point of Phase 0/1.
A blocking CI gate (Phase 3) will consume the same oracles + corpus later.

    python -m benchmarks.roundtrip                 # table to stdout
    python -m benchmarks.roundtrip --show-diff      # + unified diffs for failures
    python -m benchmarks.roundtrip --json out.json  # machine-readable results

Exit code is non-zero iff any oracle failed (skips don't count), so the tool can
double as an ad-hoc check while we burn issues down.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .corpus import Case, load_synthetic_corpus
from .oracles import CheckResult, html_equivalence_check, idempotency_check


def evaluate_case(case: Case) -> list[CheckResult]:
    """Run every oracle against one case, honoring policy skips."""
    results = [idempotency_check(case.markdown)]
    if case.has_raw_html:
        results.append(
            CheckResult(
                "html_equivalence",
                passed=True,
                skipped=True,
                detail="raw HTML present; lossy by policy (html_passthrough_mode='escape')",
            )
        )
    else:
        results.append(html_equivalence_check(case.markdown))
    return results


def _status(result: CheckResult) -> str:
    if result.skipped:
        return "SKIP"
    return "pass" if result.passed else "FAIL"


def _format_table(rows: list[tuple[Case, list[CheckResult]]]) -> str:
    name_w = max((len(c.name) for c, _ in rows), default=8)
    name_w = max(name_w, len("document"))
    header = f"{'document':<{name_w}}  {'idempotency':>12}  {'html_equiv':>12}"
    lines = [header, "-" * len(header)]
    for case, results in rows:
        by_oracle = {r.oracle: r for r in results}
        idem = _status(by_oracle["idempotency"])
        html = _status(by_oracle["html_equivalence"])
        lines.append(f"{case.name:<{name_w}}  {idem:>12}  {html:>12}")
    return "\n".join(lines)


def _summary(rows: list[tuple[Case, list[CheckResult]]]) -> tuple[int, int, int]:
    passed = failed = skipped = 0
    for _, results in rows:
        for r in results:
            if r.skipped:
                skipped += 1
            elif r.passed:
                passed += 1
            else:
                failed += 1
    return passed, failed, skipped


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="benchmarks.roundtrip", description=__doc__)
    p.add_argument("--json", type=Path, default=None, help="Write machine-readable results to this path")
    p.add_argument("--show-diff", action="store_true", help="Print unified diffs for every failing oracle")
    p.add_argument(
        "--corpus-dir",
        type=Path,
        default=None,
        help="Override the synthetic corpus directory (default: benchmarks/roundtrip/corpus/synthetic)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    cases = load_synthetic_corpus(args.corpus_dir)
    if not cases:
        print("No corpus documents found.", file=sys.stderr)
        return 2

    rows = [(case, evaluate_case(case)) for case in cases]

    print(_format_table(rows))
    passed, failed, skipped = _summary(rows)
    print()
    print(f"{passed} passed, {failed} failed, {skipped} skipped  ({len(cases)} documents x 2 oracles)")

    if args.show_diff:
        for case, results in rows:
            for r in results:
                if not r.passed and not r.skipped:
                    print(f"\n=== {case.name} :: {r.oracle} ===")
                    print(r.detail)
                    if r.diff:
                        print(r.diff)

    if args.json is not None:
        payload = {
            "documents": [
                {
                    "name": case.name,
                    "source": case.source,
                    "has_raw_html": case.has_raw_html,
                    "results": [asdict(r) for r in results],
                }
                for case, results in rows
            ],
            "summary": {"passed": passed, "failed": failed, "skipped": skipped},
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nWrote results to {args.json}", flush=True)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
