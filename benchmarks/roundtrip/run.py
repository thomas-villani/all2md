"""CLI for the Markdown roundtrip fidelity benchmark.

Runs both oracles (idempotency + HTML-equivalence) over the synthetic corpus and
prints a per-document table. It is both a diagnostic / triage tool and the
**blocking CI gate** (see ``.github/workflows/ci.yml``): a fidelity regression is
a red build rather than something a human might notice.

    python -m benchmarks.roundtrip                 # table to stdout
    python -m benchmarks.roundtrip --show-diff      # + unified diffs for failures
    python -m benchmarks.roundtrip --json out.json  # machine-readable results

Exit code is non-zero if any oracle failed, if an ``EXPECTED_FAILURES`` entry
unexpectedly passed, or if such an entry is stale. Policy skips never count.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .corpus import Case, load_synthetic_corpus
from .oracles import CheckResult, html_equivalence_check, idempotency_check

# Oracle failures we knowingly accept, keyed by (document, oracle) -> why.
#
# This is a ratchet, not an excuse list. `main` is green with these failing, but
# the run also goes red if an entry here starts *passing* (XPASS) or stops being
# evaluated at all (stale) - either means this table has begun lying about the
# codebase, so it must be updated in the same commit that changes the behavior.
# An expected failure is for behavior we have *decided* to accept; never add an
# entry to silence a genuine regression.
# Emptied by #178: raw HTML used to fail idempotency because the Markdown renderer
# escaped it, so pass 2 saw &lt;div&gt; where pass 1 saw <div>. The default is now
# pass-through and the case passes on its own. This table found that out by going
# red on the XPASS, which is what it is for.
EXPECTED_FAILURES: dict[tuple[str, str], str] = {}


def evaluate_case(case: Case) -> list[CheckResult]:
    """Run every oracle against one case, honoring policy skips.

    Idempotency always runs. The HTML-equivalence oracle is skipped for the one
    case it cannot fairly judge: admonitions, where the reference mistune renderer
    has no method for all2md's custom admonition block token. Skips are neither a
    pass nor a failure.

    Raw HTML used to be skipped here too, on the grounds that the escape policy
    made it lossy. #178 made pass-through the default, so the oracle can judge it
    like anything else and the exemption is gone.
    """
    results = [idempotency_check(case.markdown)]
    if case.has_admonitions:
        results.append(
            CheckResult(
                "html_equivalence",
                passed=True,
                skipped=True,
                detail="admonitions present; reference renderer has no admonition token (idempotency still judges)",
            )
        )
    else:
        results.append(html_equivalence_check(case.markdown))
    return results


def _status(case_name: str, result: CheckResult) -> str:
    """One of SKIP / pass / FAIL / XFAIL / XPASS.

    XFAIL is an ``EXPECTED_FAILURES`` entry failing as documented; XPASS is one
    that has started passing, which is a gate failure because the table is now
    stale (see ``EXPECTED_FAILURES``).
    """
    if result.skipped:
        return "SKIP"
    expected = (case_name, result.oracle) in EXPECTED_FAILURES
    if result.passed:
        return "XPASS" if expected else "pass"
    return "XFAIL" if expected else "FAIL"


def _format_table(rows: list[tuple[Case, list[CheckResult]]]) -> str:
    name_w = max((len(c.name) for c, _ in rows), default=8)
    name_w = max(name_w, len("document"))
    header = f"{'document':<{name_w}}  {'idempotency':>12}  {'html_equiv':>12}"
    lines = [header, "-" * len(header)]
    for case, results in rows:
        by_oracle = {r.oracle: r for r in results}
        idem = _status(case.name, by_oracle["idempotency"])
        html = _status(case.name, by_oracle["html_equivalence"])
        lines.append(f"{case.name:<{name_w}}  {idem:>12}  {html:>12}")
    return "\n".join(lines)


def _summary(rows: list[tuple[Case, list[CheckResult]]]) -> dict[str, int]:
    """Count outcomes by the same five statuses ``_status`` reports."""
    counts = {"passed": 0, "failed": 0, "xfailed": 0, "xpassed": 0, "skipped": 0}
    key = {"SKIP": "skipped", "pass": "passed", "FAIL": "failed", "XFAIL": "xfailed", "XPASS": "xpassed"}
    for case, results in rows:
        for r in results:
            counts[key[_status(case.name, r)]] += 1
    return counts


def _stale_expected_failures(rows: list[tuple[Case, list[CheckResult]]]) -> list[tuple[str, str]]:
    """``EXPECTED_FAILURES`` keys that no oracle actually evaluated.

    Catches the third way the table can rot: a document renamed or deleted, or an
    oracle that now policy-skips the case, leaves an entry that can never fail and
    so silently stops guarding anything.
    """
    evaluated = {(case.name, r.oracle) for case, results in rows for r in results if not r.skipped}
    return sorted(k for k in EXPECTED_FAILURES if k not in evaluated)


def gate_failed(counts: dict[str, int], stale: list[tuple[str, str]]) -> bool:
    """Whether this run should fail the build.

    Three ways to go red: a genuine oracle failure, an expected failure that has
    started passing, or a stale expected-failure entry. The last two are gate
    *hygiene* rather than fidelity problems, but they are equally fatal - an
    allowlist nobody has to maintain is how a ratchet stops being one.
    """
    return bool(counts["failed"] or counts["xpassed"] or stale)


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
    counts = _summary(rows)
    stale = _stale_expected_failures(rows)
    print()
    # Only surface the categories that actually occurred, so a clean run reads as
    # "40 passed" rather than a row of zeros.
    parts = [f"{counts['passed']} passed"] + [f"{n} {label}" for label, n in counts.items() if label != "passed" and n]
    print(f"{', '.join(parts)}  ({len(cases)} documents x 2 oracles)")

    if args.show_diff:
        for case, results in rows:
            for r in results:
                if not r.passed and not r.skipped:
                    print(f"\n=== {case.name} :: {r.oracle} [{_status(case.name, r)}] ===")
                    print(r.detail)
                    if r.diff:
                        print(r.diff)

    # An expected failure that passed, or that nothing evaluated, means the table
    # above is out of date. Report it as loudly as a real failure - a rotting
    # allowlist is how a ratchet quietly stops being one.
    for case, results in rows:
        for r in results:
            if _status(case.name, r) == "XPASS":
                print(
                    f"\nERROR: {case.name}:{r.oracle} passed but is listed as an expected failure.\n"
                    f"  Recorded reason: {EXPECTED_FAILURES[case.name, r.oracle]}\n"
                    f"  If this was fixed on purpose, delete the entry from EXPECTED_FAILURES\n"
                    f"  in benchmarks/roundtrip/run.py so the gate protects the fix.",
                    file=sys.stderr,
                )
    for name, oracle in stale:
        print(
            f"\nERROR: expected failure {name}:{oracle} was never evaluated - the document is "
            f"missing/renamed, or that oracle now skips it.\n"
            f"  Update or remove the EXPECTED_FAILURES entry in benchmarks/roundtrip/run.py.",
            file=sys.stderr,
        )

    if args.json is not None:
        payload = {
            "documents": [
                {
                    "name": case.name,
                    "source": case.source,
                    "has_raw_html": case.has_raw_html,
                    "results": [
                        {
                            **asdict(r),
                            "status": _status(case.name, r),
                            "expected_failure_reason": EXPECTED_FAILURES.get((case.name, r.oracle)),
                        }
                        for r in results
                    ],
                }
                for case, results in rows
            ],
            "summary": {**counts, "stale_expected_failures": [list(k) for k in stale]},
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nWrote results to {args.json}", flush=True)

    return 1 if gate_failed(counts, stale) else 0


if __name__ == "__main__":
    sys.exit(main())
